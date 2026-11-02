"""The Flipper's real screen, as textures for the 3D display.

    python3 -I stage/screens.py

research/flipper-capture/frames.bin is the screen stream recorded from the device over USB (research/flipper-capture/
rec.py; 2026-11-01): one record per frame = float64 host time + uint8 orientation + 1024 bytes in the u8g2 page
layout (128 x 64, 8 pages of 128 bytes, bit 0 = top row of the page, 1 = a dark pixel). Every distinct screen becomes
assets/screen/sNNNN.png, numbered in order of appearance: 8 x nearest-neighbour (no smoothing), dark pixels on the
orange backlight, padded by 3.5 x 4 pixels so the image has the model's screen proportions (0.3274 x 0.1751).
assets/screen/index.json lists each screen's first and last host time.
"""
import json, struct, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REC = 8 + 1 + 1024
SCALE, PADX, PADY = 8, 28, 32                      # 3.5 and 4 source pixels at 8x
INK, LIT = (30, 18, 6), (255, 139, 43)            # dark pixel, backlight


def rows(data, orientation):
    r = [[(data[(y // 8) * 128 + x] >> (y % 8)) & 1 for x in range(128)] for y in range(64)]
    return [row[::-1] for row in r[::-1]] if orientation == 1 else r


def png(path, px):
    w, h = 128 * SCALE + 2 * PADX, 64 * SCALE + 2 * PADY
    lit, ink = bytes(LIT), bytes(INK)
    pad_row = b"\x00" + lit * w
    raw = bytearray(pad_row * PADY)
    for r in px:
        line = bytearray(b"\x00" + lit * PADX)
        for p in r:
            line += (ink if p else lit) * SCALE
        line += lit * PADX
        raw += bytes(line) * SCALE
    raw += pad_row * PADY
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + ch(b"IDAT", zlib.compress(bytes(raw), 9)) + ch(b"IEND", b""))


def main():
    d = (ROOT / "research/flipper-capture/frames.bin").read_bytes()
    out = ROOT / "assets/screen"; out.mkdir(parents=True, exist_ok=True)
    prev, runs = None, []
    for i in range(len(d) // REC):
        t, o = struct.unpack("<dB", d[i * REC: i * REC + 9]); fr = d[i * REC + 9: (i + 1) * REC]
        if fr != prev:
            runs.append({"id": f"s{len(runs):04d}", "t0": round(t, 3), "t1": round(t, 3), "o": o, "fr": fr}); prev = fr
        else:
            runs[-1]["t1"] = round(t, 3)
    for r in runs:
        png(out / f"{r['id']}.png", rows(r.pop("fr"), r["o"]))
    (out / "index.json").write_text(json.dumps(runs, indent=0))
    print(f"{len(runs)} screens -> assets/screen/ ({128 * SCALE + 2 * PADX} x {64 * SCALE + 2 * PADY})")


if __name__ == "__main__":
    main()
