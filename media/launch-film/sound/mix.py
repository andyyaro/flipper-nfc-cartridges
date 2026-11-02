"""The NFC Cartridges soundtrack: Kokoro af_heart, "Tom" (Arulo) as a quiet bed, the Flipper's own tune, soft effects.

    python3 -I sound/mix.py

Inputs: assets/audio/music.wav + sound/grid.json (sound/music.py), narration/chosen/<id>.wav + narration/words.json
(narration/pick.py), sound/sfx-src/mixkit-<id>.mp3 (Mixkit free sound effects), and stage/tape.py (run from here).
Outputs:
- assets/audio/mix.wav: the soundtrack, -16 LUFS integrated, true peak under -1.5 dBTP.
- assets/audio/vo.wav, assets/audio/tune.wav: the voice alone and the Flipper's tune alone.
- assets/vo.js (window.VO), assets/timing.js + sound/timing.json (window.TM: scene windows, music points, picture
  cues), assets/tape.js (window.TAPE, by stage/tape.py). Every scene and stage/render.py read these.

Levels (Andy: "the sound should not be too loud, just present, the voice should be clear"):
- Speech at -16 LUFS on the spoken stretches. The bed 9 dB under the speech, ducked 4.5 dB more while she speaks.
- The tune (film 50.5-57.6, the bed is out): Ode to Joy as the app plays it (cart_song.c pitches and lengths, each
  note sounding 90 % of its length, onsets from the recorded screen), as a small square-wave speaker: band-limited
  square, a 2.5 kHz resonance, 3 ms edges. -19 LUFS over its span: present, under the voice level.
- Effects: one per picture event, levelled by measurement 3-6 dB over the bed (or over the tune in the solo), at least
  3 dB under the voice speaking around them, peak one frame after the picture.
"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf, librosa
from scipy.signal import lfilter

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
G = json.loads((ROOT / "sound/grid.json").read_text())
DROP, SOLO, RETURN, END_CARD, DUR, BAR = G["drop"], G["solo"], G["return"], G["end_card"], G["duration"], G["bar"]
fb = lambda k: round(k * BAR, 3)

# Each line's start in film seconds (film bar k starts at k * 2.5251 s; see sound/music.py).
#  hook   v01-v02 over the keys intro (bars 0-1) and the bass (bars 2-3)
#  title  v03 just after the drop (10.100): "NFC" on the downbeat
#  burn   v04 over the menu and the file browser; v05 so "page by page" sits on the real burn (dock 20.30);
#         v06 after the camera has gone round to the sticker on the back
#  board  v07-v09 with breaths of 0.7-0.8 s; 2 s after v09 to pull back to the whole board
#  play   v10 over the success screen and the menu; then the solo (no voice, no bed) from 50.502
#  proof  v11 from just after the drums come back (58.077); end card v12 on the track's ending (68.178)
SLOTS = {"v01": 1.00, "v02": 5.55, "v03": 10.15, "v04": 15.75, "v05": 19.30, "v06": 24.00, "v07": 28.50,
         "v08": 35.40, "v09": 40.60, "v10": 45.90, "v11": 58.60, "v12": 68.70}
# Scene windows on bar lines; a scene runs 0.4 s past the next one's start where it fades out over it.
SCENES = {"s1": [0, fb(4)],                    # hook: the sticker (3D)              bars 0-3
          "s2": [fb(4), fb(6) + 0.4],          # title on the drop (HTML)             bars 4-5
          "s3": [fb(6), fb(11) + 0.4],         # burn (3D, the real screen)           bars 6-10
          "s4": [fb(11), fb(18) + 0.4],        # board: how it is stored (HTML)       bars 11-17
          "s5": [fb(18), RETURN + 0.4],        # play (3D, the real screen, the solo) bars 18-22
          "s6": [RETURN, END_CARD + 0.4],      # proof: three stickers (3D)           bars 23-26
          "s7": [END_CARD, DUR]}               # end card (3D + lockup)               bars 27-30
SHOTS_3D = ["s1", "s3", "s5", "s6", "s7"]


def lufs(path):
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summ = out[out.rfind("Summary:"):]
    i = float(summ.split("I:")[1].split("LUFS")[0])
    tp = float(summ.split("Peak:")[1].split("dBFS")[0]) if "Peak:" in summ else 0.0
    return i, tp


def lufs_of(y, tmp, name):
    y = np.asarray(y)
    sf.write(tmp / f"{name}.wav", (y.T if y.ndim == 2 else y).astype(np.float32), SR)
    return lufs(tmp / f"{name}.wav")[0]


def load(path, sr=SR):
    y, s = sf.read(path, always_2d=True)
    y = y.T.astype(np.float64)
    if s != sr:
        y = np.vstack([librosa.resample(ch, orig_sr=s, target_sr=sr) for ch in y])
    return y



def W(meta, k, w, nth=0):
    """Film time of the nth word of line k that matches w (as the scenes' W() helper)."""
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    c = 0
    for x in meta[k]["words"]:
        if norm(x["w"]) == w or norm(x["w"]).startswith(w):
            if c == nth:
                return x["t0"]
            c += 1
    raise KeyError(f"{k}: no word {w!r}")


def picture_cues(meta):
    """Every timed picture event, in film seconds. Scenes read them from window.TM.cues; the effects below use them."""
    c = {}
    c["h_count"] = W(meta, "v01", "504"); c["h_song"] = W(meta, "v02", "whole")
    c["riser_to"] = DROP; c["mark_title"] = DROP; c["title_line"] = round(meta["v03"]["end"] + 0.3, 3)
    c["burn_nav"] = 16.00                       # the first press (DOWN) of the burn
    c["burn_fly"] = 19.05                       # the sticker starts towards the back
    c["burn_dock"] = 20.30                      # it touches; the real burn starts
    c["burn_orbit"] = 22.30                     # the camera goes round to the back (1.5 s)
    c["burn_bytes"] = W(meta, "v06", "100")
    c["b_sd"] = W(meta, "v07", "sd"); c["b_file"] = W(meta, "v07", "song"); c["b_ndef"] = W(meta, "v07", "ndef")
    c["b_phone"] = W(meta, "v07", "phones"); c["b_glide"] = round(meta["v07"]["end"] + 0.15, 3)
    c["b_len0"] = W(meta, "v08", "writes"); c["b_fill"] = W(meta, "v08", "length")
    c["b_len97"] = W(meta, "v08", "last"); c["b_torn"] = W(meta, "v08", "torn"); c["b_blank"] = W(meta, "v08", "blank")
    c["b_check"] = W(meta, "v09", "reads"); c["b_match"] = W(meta, "v09", "every")
    c["b_pull"] = round(meta["v09"]["end"] + 0.25, 3); c["b_locked"] = round(meta["v09"]["end"] + 1.3, 3)
    c["play_ok_success"] = 46.30                # OK on "Cartridge burned!" -> the menu
    c["play_fly"] = 48.95; c["play_contact"] = 49.86; c["play_away"] = 50.55
    c["play_note1"] = SOLO
    c["p_213"] = W(meta, "v11", "ntag"); c["p_215"] = W(meta, "v11", "215"); c["p_216"] = W(meta, "v11", "216")
    c["p_jingle"] = W(meta, "v11", "jingle"); c["p_250"] = W(meta, "v11", "250")
    c["p_chips"] = round(meta["v11"]["end"] + 0.3, 3)
    c["mark_end"] = END_CARD; c["end_line"] = round(meta["v12"]["end"] + 0.25, 3); c["end_url"] = round(meta["v12"]["end"] + 0.7, 3)
    return {k: round(v, 3) for k, v in c.items()}


def tune_stem(n, tmp):
    """Ode to Joy as the Flipper's speaker plays it, from sound/tune.json (stage/tape.py)."""
    T = json.loads((ROOT / "sound/tune.json").read_text())
    y = np.zeros(n)
    for nt in T["notes"]:
        a = int(round(nt["t"] * SR)); m = int(round(nt["on"] * SR)); f = nt["freq"]
        t = np.arange(m) / SR
        sq = sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, 40, 2) if f * h < 16000) * 4 / np.pi
        e = int(0.003 * SR); env = np.ones(m); env[:e] = np.linspace(0, 1, e); env[-e:] = np.linspace(1, 0, e)
        y[a: a + m] += (sq * env)[: max(0, min(m, n - a))]
    sf.write(tmp / "tune_raw.wav", y.astype(np.float32), SR)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "tune_raw.wav"), "-af",
                    "highpass=f=300,equalizer=f=2500:t=q:w=1.4:g=5,lowpass=f=7000,aecho=0.6:0.25:18:0.12",
                    "-ar", str(SR), str(ROOT / "assets/audio/tune.wav")], check=True)
    z = load(ROOT / "assets/audio/tune.wav").mean(0)[:n]
    z = np.pad(z, (0, n - len(z)))
    span = np.zeros(n, bool); span[int(T["notes"][0]["t"] * SR): int((T["notes"][-1]["t"] + T["notes"][-1]["on"]) * SR)] = True
    z *= 10 ** ((-19 - lufs_of(np.vstack([z, z])[:, span], tmp, "tune")) / 20)
    return z, span


def main():
    words = json.loads((ROOT / "narration/words.json").read_text())
    music = load(ROOT / "assets/audio/music.wav")
    n = music.shape[1]

    # ---------------------------------------------------------------- the voice
    vo = np.zeros(n)
    meta, prev_end = {}, 0.0
    for key, t0 in SLOTS.items():
        y = load(ROOT / f"narration/chosen/{key}.wav").mean(0)
        if t0 < prev_end + 0.3:
            print(f"warning: {key} starts {prev_end + 0.3 - t0:.2f} s too early (breath under 0.3 s)", file=sys.stderr)
        a = int(round(t0 * SR)); b = min(n, a + len(y))
        vo[a:b] += y[: b - a]
        end = t0 + len(y) / SR
        meta[key] = {"start": round(t0, 3), "end": round(end, 3), "text": words[key]["text"],
                     "words": [{"w": w["w"], "t0": round(t0 + w["t0"], 3), "t1": round(t0 + w["t1"], 3)} for w in words[key]["words"]]}
        prev_end = end
    assert meta["v10"]["end"] < SOLO - 0.8, "v10 must end well before the solo"
    tmp = Path(tempfile.mkdtemp())
    sf.write(tmp / "vo_raw.wav", vo.astype(np.float32), SR)
    chain = ("highpass=f=80,equalizer=f=3000:t=q:w=1.2:g=1.5,equalizer=f=250:t=q:w=1.0:g=-1,"
             "deesser=i=0.2:f=0.5,acompressor=threshold=0.1:ratio=2.5:attack=10:release=150:makeup=1.3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "vo_raw.wav"), "-af", chain, "-ar", str(SR),
                    str(ROOT / "assets/audio/vo.wav")], check=True)
    vo = load(ROOT / "assets/audio/vo.wav").mean(0)[:n]
    vo = np.pad(vo, (0, n - len(vo)))
    speech = np.zeros(n, bool)
    for m in meta.values():
        speech[int(m["start"] * SR): int(m["end"] * SR)] = True
    vo *= 10 ** ((-16 - lufs_of(np.vstack([vo, vo])[:, speech], tmp, "speech")) / 20)

    # ---------------------------------------------------------------- the bed
    sf.write(tmp / "m.wav", music.T.astype(np.float32), SR)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "m.wav"), "-af",
                    "bass=g=-4:f=110:w=0.7,equalizer=f=2500:t=q:w=1.5:g=-2", str(tmp / "m2.wav")], check=True)
    bed = load(tmp / "m2.wav")[:, :n]
    has_music = np.abs(bed).max(0) > 1e-6
    bed *= 10 ** ((-25 - lufs_of(bed[:, has_music], tmp, "bedref")) / 20)
    bed_open = bed.copy()
    hop = SR // 1000
    env = np.sqrt(np.convolve(vo ** 2, np.ones(int(0.05 * SR)) / int(0.05 * SR), "same"))[::hop]
    on = (env > 10 ** (-45 / 20)).astype(float)
    g = np.empty(len(on)); state = 0.0
    att, rel = 1 - np.exp(-1 / (0.04 * 1000)), 1 - np.exp(-1 / (0.45 * 1000))
    for i, target in enumerate(on):
        state += (att if target > state else rel) * (target - state)
        g[i] = state
    g = np.interp(np.arange(n), np.arange(len(g)) * hop, g)
    bed *= 10 ** (-4.5 * g / 20)

    # ---------------------------------------------------------------- timing for the picture, then the screen tape
    (ROOT / "assets/vo.js").write_text("window.VO = " + json.dumps(meta) + ";\n")
    cues = picture_cues(meta)
    tm = {"drop": DROP, "solo": SOLO, "return": RETURN, "end_card": END_CARD, "duration": DUR, "bar": BAR,
          **SCENES, "shots3d": SHOTS_3D, "cues": cues}
    (ROOT / "assets/timing.js").write_text("window.TM = " + json.dumps(tm) + ";\n")
    (ROOT / "sound/timing.json").write_text(json.dumps(tm, indent=1))
    subprocess.run([sys.executable, "-I", str(ROOT / "stage/tape.py")], check=True)
    tape = json.loads((ROOT / "assets/tape.js").read_text().split("=", 1)[1].rstrip().rstrip(";"))

    # ---------------------------------------------------------------- the tune
    tune, tune_span = tune_stem(n, tmp)

    # ---------------------------------------------------------------- effects, levelled against the bed (and the tune)
    sfx = np.zeros((2, n))
    vo_k = kpow(np.vstack([vo, vo]))
    bed_p, vo_s = Power(kpow(bed + np.vstack([tune, tune]))), Power(vo_k, speech)
    speech_l = Power(vo_k).level(speech)
    placed = []
    for t, name, over, pitch, what in sfx_events(cues, tape):
        placed.append((t, name, what) + place(sfx, name, t, over, pitch, bed_p, vo_s, speech_l))

    # ---------------------------------------------------------------- sum, level, limit
    mix = bed + sfx + np.vstack([vo, vo]) + np.vstack([tune, tune])
    gm = 10 ** ((-16 - lufs_of(mix, tmp, "mix")) / 20)
    mix *= gm
    sf.write(tmp / "mix2.wav", mix.T.astype(np.float32), SR)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "mix2.wav"), "-af",
                    "alimiter=limit=0.72:attack=3:release=60:level=disabled", "-ar", str(SR),
                    str(ROOT / "assets/audio/mix.wav")], check=True)
    fi, tp = lufs(ROOT / "assets/audio/mix.wav")

    # ---------------------------------------------------------------- the report
    gap = ~speech & has_music; gap[: int(0.5 * SR)] = False
    v_speech = lufs_of(gm * np.vstack([vo, vo])[:, speech], tmp, "r1")
    b_under = lufs_of(gm * bed[:, speech & has_music], tmp, "r2")
    b_gaps = lufs_of(gm * bed[:, gap], tmp, "r4")
    b_film = lufs_of(gm * bed_open[:, has_music], tmp, "r5")
    t_span = lufs_of(gm * np.vstack([tune, tune])[:, tune_span], tmp, "r6")
    print(f"mix.wav {DUR} s: {fi:.1f} LUFS integrated, true peak {tp:.1f} dBTP; voice, bed, tune and {len(placed)} effects")
    print(f"speech {v_speech:.1f} LUFS | bed {b_film:.1f} ({v_speech - b_film:.1f} dB under) | bed under the speech, ducked "
          f"{b_under:.1f} ({v_speech - b_under:.1f} dB under) | bed between lines {b_gaps:.1f} | tune {t_span:.1f}")
    print("lines: " + ", ".join(f"{k} {m['start']:.2f}-{m['end']:.2f}" for k, m in meta.items()))
    sfx_p = Power(kpow(sfx))
    rows = []
    for t, name, what, pk, ob, uv in placed:
        c = int(round(pk * SR)); e = sfx_p.at(c, 0.1)
        rows.append((t, name, ob, uv, e - bed_ref(bed_p, c), voice_ref(vo_s, c, speech_l) - e, what))
    print(f"effects ({len(rows)}): {min(r[2] for r in rows):.1f} to {max(r[2] for r in rows):.1f} dB over the bed, at least "
          f"{min(r[3] for r in rows):.1f} dB under the voice")
    for t, name, ob, uv, ob2, uv2, what in rows:
        flag = "  <-- check" if not (2.95 <= ob <= 6.05) or ob2 > 6.55 or uv2 < 2.95 else ""
        print(f"  {t:6.2f}  {name:11s} +{ob:3.1f} over the bed ({ob2:+4.1f} summed), {uv:4.1f} under the voice ({uv2:4.1f})  {what}{flag}")
    ks = list(meta)
    print("breaths: " + ", ".join(f"{ks[i]}>{ks[i + 1]} {meta[ks[i + 1]]['start'] - meta[ks[i]]['end']:.2f}" for i in range(len(ks) - 1)))
    shutil.rmtree(tmp, ignore_errors=True)


SFX = {  # Mixkit free sound effects, the vocabulary of the earlier films
    "pop": "mixkit-2357.mp3",          # soft pop: a part arriving or lighting up; at pitch 0.8 the low pop (refusal only)
    "tick": "mixkit-1120.mp3",         # tick: a step or a counter (a chip, a status dot + word, a row, an end line)
    "whoosh_air": "mixkit-1492.mp3",   # a token travelling along a wire
    "whoosh_wind": "mixkit-1465.mp3",  # the camera gliding between close shots
    "sweep": "mixkit-3115.mp3",        # the two big camera moves (into the board, the pull-back)
    "pop_hard": "mixkit-3005.mp3",     # the soft hit: the mark on the drop, the 14, the mark on the end card
    "riser": "mixkit-2408.mp3",        # swells into the drop
}
# picture kind -> (sound, dB over the bed, default pitch)
KINDS = {"pop": ("pop", 4.0, 1.0), "tick": ("tick", 4.0, 1.0), "whoosh": ("whoosh_air", 3.5, 1.1),
         "glide": ("whoosh_wind", 3.0, 1.0), "sweep": ("sweep", 4.5, 1.0), "lowpop": ("pop", 5.0, 0.8),
         "riser": ("riser", 3.0, 1.0), "hit": ("pop_hard", 4.5, 0.9), "click": ("tick", 2.5, 1.35),
         "chime": ("pop_hard", 4.0, 1.25)}
VOICE_MARGIN = 3.0   # an effect stays at least this far under the voice speaking around it (or the speech level)
_cache = {}

# K-weighting (ITU-R BS.1770 at 48 kHz): levels below are in LUFS-like units, comparable with the speech's -16
_KB1, _KA1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
_KB2, _KA2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]


def kpow(y):
    """K-weighted power per sample, summed over channels."""
    y = np.atleast_2d(y)
    z = lfilter(_KB2, _KA2, lfilter(_KB1, _KA1, y, axis=-1), axis=-1)
    return (z ** 2).sum(0)


class Power:
    """Window levels of a K-weighted power signal (cumulative sums, so each lookup is O(1)). With a mask, a window's
    level counts only the masked samples (the voice: what she says around a moment, not the pauses)."""
    def __init__(self, p, mask=None):
        self.p = p; self.c = np.concatenate([[0.0], np.cumsum(p if mask is None else p * mask)])
        self.k = np.concatenate([[0.0], np.cumsum(np.ones(len(p)) if mask is None else mask.astype(float))])

    def at(self, centre, half_s):
        h = int(half_s * SR); a = max(0, centre - h); b = min(len(self.p), centre + h)
        k = self.k[b] - self.k[a]
        return None if k < 1 else -0.691 + 10 * np.log10((self.c[b] - self.c[a]) / k + 1e-12)

    def level(self, mask):
        return -0.691 + 10 * np.log10(self.p[mask].mean() + 1e-12)


def bed_ref(bed_p, c):
    """The bed's level at sample c: the louder of its 400 ms momentary and 3 s short-term levels, so an effect in a
    pause between the intro's chords sits over the music's level in that bar, not over the silence."""
    return max(bed_p.at(c, 0.2), bed_p.at(c, 1.5))


def voice_ref(vo_s, c, speech_l):
    """The voice's level around sample c: her speech within 0.5 s (pauses not counted), else the film's speech level."""
    v = vo_s.at(c, 0.5)
    return speech_l if v is None or v < speech_l - 15 else v


def clip(name):
    if name not in _cache:
        y = load(ROOT / "sound/sfx-src" / SFX[name])
        if name == "riser":    # let it swell in from nothing (as secure-data-hub)
            f = int(1.2 * SR); y[:, :f] *= np.linspace(0, 1, f) ** 2
        _cache[name] = y
    return _cache[name]


def place(out, name, t, over_db, pitch, bed_p, vo_s, speech_l):
    """Put one effect in: its peak one frame after the picture at t, over_db over the bed there (K-weighted: the
    effect over 200 ms around its peak against bed_ref), capped VOICE_MARGIN under voice_ref.
    Returns (peak time, dB over the bed, dB under the voice), the effect alone."""
    y = clip(name)
    if pitch != 1.0:   # small pitch steps rotate repeated sounds (resampling also shortens or lengthens them)
        y = np.vstack([librosa.resample(ch, orig_sr=SR, target_sr=int(SR / pitch)) for ch in y])
    pk = int(np.argmax(np.convolve(np.abs(y).mean(0), np.ones(240) / 240, "same")))
    pad = int(0.2 * SR)                         # silence around the clip, so its 200 ms window is never cut short
    own = Power(kpow(np.pad(y, ((0, 0), (pad, pad))))).at(pk + pad, 0.1)
    c = int(round((t + 1 / 30) * SR))          # the peak lands one frame after the picture
    b_ref, v_ref = bed_ref(bed_p, c), voice_ref(vo_s, c, speech_l)
    target = min(b_ref + over_db, v_ref - VOICE_MARGIN)
    y = y * 10 ** ((target - own) / 20)
    a = c - pk
    s0 = max(0, -a); a = max(0, a)
    b = min(out.shape[1], a + y.shape[1] - s0)
    out[:, a:b] += y[:, s0: s0 + (b - a)]
    return (c / SR, target - b_ref, v_ref - target)



def sfx_events(c, tape):
    """(picture time, sound, dB over the bed, pitch, what). A whoosh peaks at its fastest point (the middle of a move)."""
    e = []
    add = lambda t, kind, what, **kw: e.append((t, *KINDS[kind][:1], kw.get("over", KINDS[kind][1]), kw.get("pitch", KINDS[kind][2]), what))
    add(c["h_count"], "tick", "504 bytes counter")
    add(c["h_song"], "pop", "the melody dots", pitch=1.15)
    add(DROP - 2.2, "riser", "into the drop")
    add(c["mark_title"], "hit", "the lockup on the drop")
    for t, k in tape["burn"]["presses"] + tape["play"]["presses"]:
        add(t, "click", f"button {k}")
    add((c["burn_fly"] + c["burn_dock"]) / 2, "whoosh", "the sticker flies to the back")
    add(c["burn_dock"], "pop", "the sticker touches", pitch=0.9)
    add(tape["burn"]["burned"], "chime", "Cartridge burned!")
    add(c["burn_orbit"] + 0.75, "sweep", "camera round to the back")
    add(c["burn_bytes"], "tick", "100 of 504 bytes")
    for k, what in [("b_sd", "SD chip"), ("b_file", "song file card"), ("b_ndef", "NDEF card"), ("b_phone", "phone chip")]:
        add(c[k], "pop", what)
    add(c["b_glide"] + 0.45, "glide", "camera to the sticker card")
    add(c["b_len0"], "tick", "page 4: length 0"); add(c["b_len97"], "pop", "page 4: real length", pitch=1.1)
    add(c["b_torn"], "tick", "torn note", pitch=0.9); add(c["b_check"], "tick", "check sweep"); add(c["b_match"], "pop", "matches", pitch=1.1)
    add(c["b_pull"] + 0.6, "sweep", "pull back"); add(c["b_locked"], "lowpop", "locked stickers refused")
    add((c["play_fly"] + c["play_contact"]) / 2, "whoosh", "the sticker taps the back")
    add(c["play_contact"], "pop", "tap", pitch=0.9)
    add(RETURN, "hit", "the drums come back", over=3.0)
    for k, p in [("p_213", 1.0), ("p_215", 1.06), ("p_216", 1.12)]:
        add(c[k], "pop", f"sticker {k[2:]}", pitch=p)
    add(c["p_chips"], "tick", "proof chips")
    add(c["mark_end"], "hit", "the lockup on the end card"); add(c["end_url"], "tick", "the URL")
    return e


if __name__ == "__main__":
    main()
