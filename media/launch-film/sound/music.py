"""Cut "Tom" (Arulo, Mixkit 244, Mixkit Stock Music Free License) to the NFC Cartridges film.

    python3 -I sound/music.py     # -> assets/audio/music.wav, sound/grid.json

Andy, 2026-11-01: "calm but not too calm", a new track per film. Tom is relaxed and a little quirky (drum drive 2.60).
Measured (librosa, 2026-11-02): 95.0 BPM in 4/4, kicks on beats 1 and 3, track bar n starts at 0.025 + 2.5251 n
(the kick pairs at 20.225/21.478 ... 40.426/41.703 sit on that grid to within 10 ms). Key area C# / G#.
  bars  0-3    0.03-10.13  keys only (-29 dB)
  bars  4-6   10.13-17.70  bass enters
  bar   7     17.70-20.23  hats and a build
  bar   8     20.23        THE DROP: full drums
  bars  8-31  20.23-80.83  grooves A (8-15), B (16-23, more sub), C (24-31, fuller)
  bars 32-39  80.83-101.03 breakdown, no drums
  bar  40    101.03        the drums come back
  bars 44-47 111.13-121.2  it thins and fades to silence (its own ending)

The edit (joins on bar lines, 20 ms crossfades):
  film  0.000- 5.050  track bars 0-1    the real opening, keys only
  film  5.050-10.100  track bars 6-7    bass and the build (bar 6 repeats bar 2's chords)
  film 10.100-50.502  track bars 8-23   the drop on the title, grooves A and B; faded out over the last bar
  film 50.502-58.077  (no music)        the Flipper plays Ode to Joy from the sticker, alone (it is in C; Tom is in C#)
  film 58.077-76.500  track bars 40-47  the drums come back on the proof; the track's own ending under the end card
So film bar k starts at 2.5251 k.
"""
import json, subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
TRACK = ROOT / "sound/track.mp3"
SR, B0, BAR = 48000, 0.025, 2.5251
tb = lambda n: B0 + n * BAR
fb = lambda k: k * BAR
# (film start, track start or None for silence)
SEGMENTS = [(0.0, tb(0)), (fb(2), tb(6)), (fb(4), tb(8)), (fb(20), None), (fb(23), tb(40))]
DROP, SOLO, RETURN, END_CARD = fb(4), fb(20), fb(23), fb(27)
FILM_END = 76.5
XF = 0.020


def main():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(TRACK), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    track = np.frombuffer(raw, np.float32).reshape(-1, 2).T.astype(np.float64)
    n = int(round(FILM_END * SR))
    out = np.zeros((2, n))
    x = int(XF * SR); ramp = np.linspace(0, 1, x)
    for k, (f0s, t0s) in enumerate(SEGMENTS):
        f0 = int(round(f0s * SR)); f1 = int(round(SEGMENTS[k + 1][0] * SR)) if k + 1 < len(SEGMENTS) else n
        if t0s is None:
            continue
        t0 = int(round(t0s * SR))
        seg = track[:, t0: t0 + (f1 - f0)]
        seg = np.pad(seg, ((0, 0), (0, (f1 - f0) - seg.shape[1])))
        prev_music = k > 0 and SEGMENTS[k - 1][1] is not None
        if prev_music:   # equal-gain crossfade over the 20 ms before the bar line
            out[:, f0 - x: f0] = out[:, f0 - x: f0] * (1 - ramp) + track[:, t0 - x: t0] * ramp
        elif k > 0:      # out of the silence: a 10 ms click guard only, the downbeat comes in whole
            fi = int(0.010 * SR); seg[:, :fi] *= np.linspace(0, 1, fi)
        out[:, f0:f1] = seg
    # the bed bows out across the last bar before the solo (film bar 19): a cosine fade to silence by the bar line
    a, b = int(round((SOLO - 1.30) * SR)), int(round((SOLO - 0.05) * SR))
    out[:, a:b] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, b - a))) ** 1.5
    out[:, b: int(round(SOLO * SR))] = 0
    fi = int(0.010 * SR); out[:, :fi] *= np.linspace(0, 1, fi)
    fo = int(0.8 * SR); out[:, -fo:] *= np.linspace(1, 0, fo) ** 2   # the track is nearly silent by then anyway
    (ROOT / "assets/audio").mkdir(parents=True, exist_ok=True)
    sf.write(ROOT / "assets/audio/music.wav", out.T.astype(np.float32), SR)
    grid = {"track": "Tom (Arulo, Mixkit 244)", "bpm": 95, "bar": BAR, "film_bar_k": "k * bar",
            "drop": round(DROP, 3), "solo": round(SOLO, 3), "return": round(RETURN, 3), "end_card": round(END_CARD, 3),
            "duration": FILM_END, "segments": [[round(a, 3), None if b is None else round(b, 3)] for a, b in SEGMENTS]}
    (ROOT / "sound/grid.json").write_text(json.dumps(grid, indent=1))
    print(f"music.wav {FILM_END} s; drop {DROP:.3f}, solo {SOLO:.3f}, return {RETURN:.3f}, end card {END_CARD:.3f}")


if __name__ == "__main__":
    main()
