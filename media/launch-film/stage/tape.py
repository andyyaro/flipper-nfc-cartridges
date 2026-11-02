"""The edit of the Flipper's real screen: which recorded screen shows when, which button is pressed when, and when
each note of Ode to Joy sounds. Run by sound/mix.py after it writes sound/timing.json.

    python3 -I stage/tape.py

Inputs: sound/timing.json (the film's anchors), assets/screen/index.json (stage/screens.py: every distinct recorded
screen with its host time), research/flipper-capture/log.txt (the button presses sent over USB, with their times),
the repo's songs/ode_to_joy.txt (the song on the sticker).
Outputs: assets/tape.js (window.TAPE: per shot, [film time, screen id] steps, [film time, button] presses,
[film time] sticker contacts and note starts) and sound/tune.json (each note's film start, sounding length, pitch).

How the recording maps to the film (all screens are real; nothing is redrawn):
- Burn shot. The menu and file-browser steps are the recorded screens in the recorded order, pressed at a calm pace
  (the recording waited on Andy between presses). From the OK on ode_to_joy.txt the recording runs at its own speed:
  the sticker was already on the back, so the burn followed at once. "Waiting..." is held until the sticker arrives
  (the one liberty: a held frame), then the real burn plays: 25 pages in 0.82 s, "Cartridge burned!" 1.32 s after page 1.
- Play shot. Real time from the UP press onward, aligned so the first note sounds on the solo's bar line. Notes 1-15
  (the first phrase) are heard; the music returns on the next bar line and the shot ends.
- Note starts: the app sets "Note i / 30" just before each note sounds (nfc_cart.c play_song), so the screen changes
  are the note onsets. Their host times jitter by a few ms (USB), so they are fitted with the app's own timing
  (RTTTL lengths + a constant per-note overhead, measured here) and both the screen and the tune use the fit.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TM = json.loads((ROOT / "sound/timing.json").read_text())
IDX = {r["id"]: r for r in json.loads((ROOT / "assets/screen/index.json").read_text())}
SONG = "Ode to Joy:d=4,o=5,b=140:e,e,f,g,g,f,e,d,c,c,d,e,e.,8d,2d,e,e,f,g,g,f,e,d,c,c,d,e,d.,8c,2c"
LAT = 0.12    # press -> new screen, as recorded (0.12-0.17 s)


def rtttl(s):
    """The app's parser (cart_song.c): note length = whole / d (dotted x1.5), freq = 440 * 2^((midi - 69) / 12)."""
    _, defs, notes = s.split(":")
    d = dict(x.split("=") for x in defs.split(","))
    dd, do, bpm = int(d["d"]), int(d["o"]), int(d["b"])
    whole = 60000.0 * 4 / bpm
    out = []
    for n in notes.split(","):
        m = re.fullmatch(r"(\d*)([a-gp])(#?)(\.?)(\d?)(\.?)", n)
        dur = int(m.group(1) or dd); dotted = bool(m.group(4) or m.group(6)); octave = int(m.group(5) or do)
        ms = whole / dur * (1.5 if dotted else 1)
        semi = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}.get(m.group(2))
        freq = 0.0 if semi is None else 440 * 2 ** (((octave + 1) * 12 + semi + (1 if m.group(3) else 0) - 69) / 12)
        out.append({"name": m.group(2) + m.group(3), "ms": ms, "freq": round(freq, 3)})
    return out


def main():
    cue = TM["cues"]
    tape = {}

    # ---------------------------------------------------------------- burn
    dock = cue["burn_dock"]                       # the sticker touches the back
    r_page1 = IDX["s0032"]["t0"]                  # host time of "Page 1 / 25"
    real = lambda sid: dock + IDX[sid]["t0"] - r_page1
    presses = [[cue["burn_nav"] + dt, k] for dt, k in [(0.0, "DOWN"), (0.8, "OK"), (1.5, "DOWN"), (2.1, "DOWN"), (2.7, "OK")]]
    steps = [[TM["s3"][0], "s0017"],                                  # the menu, "Play cartridge" highlighted
             [presses[0][0] + LAT, "s0018"],                          # DOWN -> "Burn cartridge"
             [presses[1][0] + LAT, "s0023"], [presses[1][0] + LAT + 0.02, "s0024"], [presses[1][0] + LAT + 0.03, "s0025"],  # OK -> browser
             [presses[2][0] + LAT, "s0026"], [presses[3][0] + LAT, "s0027"],                                                 # DOWN, DOWN -> ode_to_joy.txt
             [presses[4][0] + 0.17, "s0028"], [presses[4][0] + 0.22, "s0029"]]                                               # OK -> "Waiting..."
    hold_end = real("s0030")
    assert hold_end > steps[-1][0] + 0.3, "the sticker must arrive after the waiting screen"
    for i in range(30, 58):                       # Waiting, Waiting., Page 1..25, Cartridge burned!
        steps.append([real(f"s{i:04d}"), f"s{i:04d}"])
    tape["burn"] = {"steps": steps, "presses": presses, "contacts": [dock], "burned": real("s0057"),
                    "pages": [real(f"s{i:04d}") for i in range(32, 57)]}

    # ---------------------------------------------------------------- play
    song = rtttl(SONG)
    note_ids = [f"s{i:04d}" for i in range(62, 92)]                 # "Note 1 / 30" .. "Note 30 / 30"
    host = [IDX[s]["t0"] for s in note_ids]
    # fit host[i] = a + sum(ms[0..i-1]) / 1000 + i * k  (k = the app's overhead per note), from notes 2..30
    cum = [sum(n["ms"] for n in song[:i]) / 1000 for i in range(30)]
    xs, ys = list(range(1, 30)), [host[i] - cum[i] for i in range(1, 30)]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    a = my - k * mx
    fit = [a + cum[i] + i * k for i in range(30)]
    resid = max(abs(fit[i] - host[i]) for i in range(1, 30))
    # note 1 sounds 300 ms after the screen shows it (furi_delay_ms(300) before play_song); its onset is the fit's a
    note1 = cue["play_note1"]                                        # = the solo's bar line
    off = note1 - fit[0]
    p_real = lambda sid: IDX[sid]["t0"] + off
    up, ok = [float(l.split()[0]) for l in (ROOT / "research/flipper-capture/log.txt").read_text().splitlines()
              if l.split()[1:3] in (["cmd", "press"],)][-2:]
    play_presses = [[cue["play_ok_success"], "OK"], [up + off, "UP"], [ok + off, "OK"]]
    psteps = [[TM["s5"][0], "s0057"],                                 # "Cartridge burned!" (as the burn left it)
              [play_presses[0][0] + LAT, "s0058"],                    # OK -> the menu, "Burn cartridge"
              [p_real("s0059"), "s0059"], [p_real("s0060"), "s0060"], [p_real("s0061"), "s0061"],   # UP, OK, Waiting
              [p_real("s0062"), "s0062"]]                             # "Note 1 / 30" (300 ms before it sounds)
    heard = 15
    for i in range(1, heard + 1):                                     # notes 2..16 shown on the fit
        psteps.append([fit[i] + off, note_ids[i]])
    contact = cue["play_contact"]
    assert p_real("s0060") < contact < p_real("s0062"), "the tap must land while the app is waiting"
    notes = [{"t": round(fit[i] + off, 4), "on": round(song[i]["ms"] * 0.9 / 1000, 4), "freq": song[i]["freq"],
              "name": song[i]["name"]} for i in range(heard)]
    tape["play"] = {"steps": psteps, "presses": play_presses, "contacts": [contact], "notes": [n["t"] for n in notes]}
    (ROOT / "assets/tape.js").write_text("window.TAPE = " + json.dumps(tape) + ";\n")
    (ROOT / "sound/tune.json").write_text(json.dumps({"notes": notes, "overhead_ms": round(k * 1000, 2),
                                                      "fit_residual_ms": round(resid * 1000, 1)}, indent=1))
    print(f"tape: burn {len(steps)} steps (dock {dock:.2f}, burned {real('s0057'):.2f}); play {len(psteps)} steps, "
          f"{heard} notes {notes[0]['t']:.2f}-{notes[-1]['t'] + notes[-1]['on']:.2f}; per-note overhead {k * 1000:.1f} ms, "
          f"fit within {resid * 1000:.0f} ms of the recorded screens")


if __name__ == "__main__":
    main()
