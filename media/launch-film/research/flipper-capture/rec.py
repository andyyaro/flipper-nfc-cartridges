"""Record the Flipper's screen over USB while taking commands from a file.

    venv/bin/python -I rec.py <session_dir>

Writes <session_dir>/frames.bin: one record per frame = float64 time + uint8 orientation + 1024 bytes.
Reads <session_dir>/cmd.txt (appended to by hand) once every 50 ms:
    start <path-to.fap>      app_start
    press <UP|DOWN|LEFT|RIGHT|OK|BACK> [SHORT|LONG]
    exit                     app_exit
    mark <text>              a note in the log
    stop                     end the session
Every command and its time go to <session_dir>/log.txt.
"""
import sys, time, struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from flip import Flipper  # noqa: E402

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
fb = open(out / "frames.bin", "ab")
log = open(out / "log.txt", "a")
cmd = out / "cmd.txt"; cmd.touch()
pos = cmd.stat().st_size


def L(msg):
    log.write(f"{time.time():.3f} {msg}\n"); log.flush()


def on_frame(t, data, o):
    fb.write(struct.pack("<dB", t, o) + data); fb.flush()


f = Flipper()
f.on_frame = on_frame
f.stream(True)
L("stream on")
try:
    while True:
        time.sleep(0.05)
        size = cmd.stat().st_size
        if size <= pos:
            continue
        with open(cmd) as fh:
            fh.seek(pos); new = fh.read(); pos = size
        for line in new.splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            L("cmd " + line.strip())
            if parts[0] == "start":
                r = f.app_start(parts[1], " ".join(parts[2:]))
                L(f"start status {[m.command_status for m in r]}")
            elif parts[0] == "press":
                f.press(parts[1], parts[2] if len(parts) > 2 else "SHORT")
            elif parts[0] == "exit":
                f.app_exit()
            elif parts[0] == "mark":
                pass
            elif parts[0] == "stop":
                raise KeyboardInterrupt
except KeyboardInterrupt:
    pass
finally:
    try:
        f.stream(False)
    except Exception:
        pass
    L(f"stream off, {len(f.frames)} frames")
    f.close()
    fb.close()
