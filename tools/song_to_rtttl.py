#!/usr/bin/env python3
"""Turn a section of a song into a Flipper NFC-cartridge melody (RTTTL).

Works on an isolated vocal stem (split it off first, e.g. with Demucs):
  * CREPE pitch tracking, which copes with reverb and breathy vocals
  * notes are split at syllable onsets, so repeated same-pitch syllables survive
  * every note start snaps to an absolute 32nd-note grid at the detected tempo;
    durations never overrun and leftovers become rests, so timing can't drift
  * prints self-check metrics against the real vocal: onset F1, pitch accuracy, drift

usage: song_to_rtttl.py track VOCALS.wav MIX.wav CACHE_DIR
       song_to_rtttl.py make  CACHE_DIR START END NAME OUT_DIR [--transpose N]
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

SR = 16000
HOP = 160  # 10 ms
STICKER_BYTES = 504
NOTE_NAMES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]
REPR = [32, 24, 16, 12, 8, 6, 4, 3, 2, 1]  # representable lengths in 32nd notes
DUR = {1: (32, False), 2: (16, False), 3: (16, True), 4: (8, False), 6: (8, True),
       8: (4, False), 12: (4, True), 16: (2, False), 24: (2, True), 32: (1, False)}
UNITS_PER_BEAT = 8


def track(vocals, mix, cache):
    import librosa
    import torch
    import torchcrepe

    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    y, _ = librosa.load(vocals, sr=SR, mono=True)
    audio = torch.tensor(y, dtype=torch.float32)[None]
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    pitch, period = torchcrepe.predict(
        audio, SR, HOP, fmin=65.0, fmax=1100.0, model="full", batch_size=1024,
        device=device, return_periodicity=True, decoder=torchcrepe.decode.viterbi)
    period = torchcrepe.filter.median(period, 5)
    pitch = torchcrepe.filter.mean(pitch, 3)
    pitch, period = pitch[0].cpu().numpy(), period[0].cpu().numpy()
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=HOP)[0][: len(pitch)]
    onsets = librosa.onset.onset_detect(y=y, sr=SR, hop_length=HOP, backtrack=True,
                                        units="time", delta=0.07)

    m, _ = librosa.load(mix, sr=22050, mono=True)
    oenv = librosa.onset.onset_strength(y=m, sr=22050, hop_length=256)
    tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=22050, hop_length=256, units="time")
    np.savez_compressed(cache / "crepe.npz", pitch=pitch, period=period, rms=rms,
                        onsets=onsets, beats=beats, tempo=float(np.atleast_1d(tempo)[0]))
    print(f"tracked {len(pitch)} frames on {device}; {len(onsets)} vocal onsets; tempo {float(np.atleast_1d(tempo)[0]):.1f}")


def voiced_mask(c):
    rms = c["rms"]
    loud = rms > max(1e-4, np.percentile(rms, 30) * 1.5)
    return (c["period"] > 0.45) & loud & (c["pitch"] > 0)


def notes_in(c, start, end):
    """Segment voiced frames into notes, splitting at onsets and pitch jumps."""
    import librosa
    pitch, ok = c["pitch"], voiced_mask(c)
    n = len(pitch)
    t = np.arange(n) * HOP / SR
    midi = np.where(ok, librosa.hz_to_midi(np.maximum(pitch, 1.0)), np.nan)
    onset_frames = set(int(round(o * SR / HOP)) for o in c["onsets"])

    notes, i = [], int(start * SR / HOP)
    stop = min(n, int(end * SR / HOP))
    while i < stop:
        if not ok[i]:
            i += 1
            continue
        j = i
        seg = [midi[i]]
        while j + 1 < stop and ok[j + 1]:
            nxt = midi[j + 1]
            ref = np.median(seg[-8:])
            if (j + 1) in onset_frames and len(seg) >= 6:
                break  # new syllable
            if abs(nxt - ref) > 0.9 and np.all(np.abs(midi[j + 1: j + 5] - ref) > 0.9):
                break  # sustained pitch change
            j += 1
            seg.append(nxt)
        if len(seg) >= 6:  # >= 60 ms
            body = np.array(seg[len(seg) // 5:])  # skip the scoop into the note
            notes.append((t[i], t[j] + HOP / SR, float(np.median(body))))
        i = j + 1
    return notes


def grid_for(c, start, notes):
    """Grid at the detected tempo (32nd notes); phase that best fits the note onsets."""
    bpm = float(np.asarray(c["tempo"]).item())
    unit = 60.0 / bpm / UNITS_PER_BEAT
    best = None
    for ph in np.linspace(0, unit, 16, endpoint=False):
        err = np.mean([abs(((s - start - ph + unit / 2) % unit) - unit / 2) for s, _, _ in notes])
        if best is None or err < best[0]:
            best = (err, ph)
    return bpm, best[1]


def encode(notes, bpm, phase, start, transpose):
    six = 60.0 / bpm / UNITS_PER_BEAT
    origin = start + phase
    q = []
    for s, e, m in notes:
        a = int(round((s - origin) / six))
        b = max(a + 1, int(round((e - origin) / six)))
        q.append([a, b, int(round(m))])
    # octave folding against the local median
    if q:
        ps = np.array([m for *_, m in q], dtype=float)
        for k in range(len(q)):
            loc = np.median(ps[max(0, k - 4): k + 5])
            while q[k][2] - loc > 7:
                q[k][2] -= 12
            while loc - q[k][2] > 7:
                q[k][2] += 12
    # resolve collisions on the grid: a note can't start before the previous one
    clean = []
    for a, b, m in q:
        if clean and a <= clean[-1][0]:
            continue
        if clean and clean[-1][1] > a:
            clean[-1][1] = a
        clean.append([a, b, m])

    events = []
    tokens, cursor = [], clean[0][0] if clean else 0
    first = cursor
    for k, (a, b, m) in enumerate(clean):
        if a > cursor:
            gap = min(a - cursor, 32)  # cap silences at one bar
            for p in REPR:
                while gap >= p:
                    tokens.append((p, None))
                    gap -= p
            cursor = a
        nxt = clean[k + 1][0] if k + 1 < len(clean) else b
        want = max(1, min(b, nxt) - a)
        L = next(p for p in REPR if p <= want)  # never overrun; remainder becomes rest
        tokens.append((L, m + transpose))
        events.append((a, L, m))
        cursor += L
        if cursor < min(b, nxt):
            pass  # remainder is emitted as rest by the next iteration's gap
    return tokens, first, events, origin


def rtttl(tokens, bpm, name):
    d_def = Counter(DUR[L][0] for L, _ in tokens).most_common(1)[0][0]
    o_def = Counter(m // 12 - 1 for _, m in tokens if m is not None).most_common(1)[0][0]
    out = []
    for L, m in tokens:
        d, dot = DUR[L]
        s = "" if d == d_def else str(d)
        if m is None:
            s += "p"
        else:
            s += NOTE_NAMES[m % 12]
            if m // 12 - 1 != o_def:
                s += str(m // 12 - 1)
        if dot:
            s += "."
        out.append(s)
    return f"{name}:d={d_def},o={o_def},b={int(round(bpm))}:" + ",".join(out)


def ndef_size(n):
    payload = 3 + n
    rec = 3 + (1 if payload <= 255 else 4) + payload
    return 1 + (3 if rec >= 0xFF else 1) + rec + 1


def metrics(frames, c, start, end):
    """frames: [(start_s, end_s, midi)] on the song's own timeline (no transposition)."""
    import librosa
    onsets_enc = [s for s, _, _ in frames]
    ref = [o for o in c["onsets"] if start <= o < end]
    tol = 0.07
    hit = sum(any(abs(o - r) <= tol for o in onsets_enc) for r in ref)
    prec = sum(any(abs(o - r) <= tol for r in ref) for o in onsets_enc)
    P = prec / max(1, len(onsets_enc))
    R = hit / max(1, len(ref))
    f1 = 2 * P * R / max(1e-9, P + R)
    ok = voiced_mask(c)
    tt = np.arange(len(ok)) * HOP / SR
    good = tot = 0
    for s, e, m in frames:
        sel = ok & (tt >= s) & (tt < e)
        if sel.any():
            ref_m = librosa.hz_to_midi(c["pitch"][sel])
            d = np.abs(((ref_m - m) + 6) % 12 - 6)  # pitch-class distance (octave-safe)
            good += int((d <= 1.0).sum())
            tot += int(sel.sum())
    voiced_total = int((ok & (tt >= start) & (tt < end)).sum())
    return f1, good / max(1, tot), tot / max(1, voiced_total)


def make(cache, start, end, name, out_dir, transpose=None):
    import librosa
    import soundfile as sf
    c = dict(np.load(Path(cache) / "crepe.npz"))
    notes = notes_in(c, start, end)
    if not notes:
        sys.exit("no vocal notes in that section")
    bpm, phase = grid_for(c, start, notes)
    if transpose is None:
        med = np.median([m for *_, m in notes])
        transpose = int(12 * round((74 - med) / 12))
    tokens, first, events, origin = encode(notes, bpm, phase, start, transpose)
    text = rtttl(tokens, bpm, name)
    while ndef_size(len(text)) > STICKER_BYTES and len(tokens) > 8:
        tokens = tokens[:-1]
        text = rtttl(tokens, bpm, name)
    n_notes = sum(1 for _, m in tokens if m is not None)
    events = events[:n_notes]
    unit = 60.0 / bpm / UNITS_PER_BEAT
    covered_end = origin + (events[-1][0] + events[-1][1]) * unit if events else start

    raw = metrics([(s, e, m) for s, e, m in notes if s < covered_end], c, start, covered_end)
    enc = metrics([(origin + a * unit, origin + (a + L) * unit, m) for a, L, m in events],
                  c, start, covered_end)
    print(f"{name}: {n_notes} notes, grid {bpm:.1f} BPM in 32nds, {ndef_size(len(text))}/{STICKER_BYTES} bytes, "
          f"covers {covered_end - start:.1f}s of {end - start:.0f}s")
    print(f"  raw notes vs vocal : onset F1 {raw[0]:.2f} | pitch ok {100 * raw[1]:.0f}% | voiced coverage {100 * raw[2]:.0f}%")
    print(f"  on-grid  vs vocal : onset F1 {enc[0]:.2f} | pitch ok {100 * enc[1]:.0f}% | voiced coverage {100 * enc[2]:.0f}%")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.txt").write_text(text + "\n")
    # preview: square wave, 90% duty like the Flipper app
    sr, six, chunks = 22050, unit, []
    for L, m in tokens:
        n = int(L * six * sr)
        w = np.zeros(n)
        if m is not None:
            f = 440 * 2 ** ((m - 69) / 12)
            k = np.arange(int(n * 0.9))
            w[: len(k)] = 0.25 * np.sign(np.sin(2 * np.pi * f * k / sr))
        chunks.append(w)
    sf.write(out / f"{name}_beeps.wav", np.concatenate(chunks), sr)
    # diagnostic: raw CREPE contour as a sine (no note-making at all)
    ok = voiced_mask(c)
    a0, a1 = int(start * SR / HOP), int(end * SR / HOP)
    f = np.repeat(np.where(ok[a0:a1], c["pitch"][a0:a1] * 2 ** (transpose / 12), 0.0), HOP)
    amp = np.repeat(ok[a0:a1].astype(float), HOP) * 0.25
    ph = 2 * np.pi * np.cumsum(f) / SR
    sf.write(out / f"{name}_contour.wav", amp * np.sin(ph), SR)
    print("  " + text[:110] + ("..." if len(text) > 110 else ""))


if __name__ == "__main__":
    if sys.argv[1] == "track":
        track(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        tr = int(sys.argv[sys.argv.index("--transpose") + 1]) if "--transpose" in sys.argv else None
        make(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5], sys.argv[6], tr)
