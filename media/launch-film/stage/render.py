"""Render the film's 3D shots (stage/stage.html + stage/shots.js) frame by frame.

    $PW/bin/python -I stage/render.py                      -> assets/stage/<shot>.mp4 for every 3D shot (window.TM.shots3d)
    $PW/bin/python -I stage/render.py s3                   -> one shot
    $PW/bin/python -I stage/render.py --at 15.5 20.3 ...   -> stills at those film times, to stage/test/
    $PW/bin/python -I stage/render.py --encode [s7 ...]     -> re-encode the kept frames in stage/frames/, no re-render

Each shot is rendered on the film's own frame grid: frame f shows film time f / 30, from round(start * 30) to
round(end * 30). index.html places the clip at that first frame's time (build.py), so picture and sound line up to
the frame. Chromium renders WebGL on the GPU (Metal), as for the EV-SIENT laptop.
"""
import functools, http.server, json, shutil, subprocess, sys, threading, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FPS = 30


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def encode(fr, out):
    """PNG frames -> H.264, converted and tagged as BT.709 (untagged, ffmpeg converts with BT.601 and Chrome decodes
    as BT.709, which lifts the pink from #ff9acb to #fea6cc)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(fr / "%05d.png"),
                    "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264", "-preset", "slow", "-crf", "12",
                    "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-color_range", "tv", "-movflags", "+faststart", str(out)], check=True)


def main():
    args = sys.argv[1:]
    tm = json.loads((ROOT / "sound/timing.json").read_text())
    if args[:1] == ["--encode"]:              # re-encode the kept frames only (stage/frames/<shot>/), no re-render
        for s in args[1:] or tm["shots3d"]:
            encode(ROOT / "stage/frames" / s, ROOT / "assets/stage" / f"{s}.mp4")
            print(f"re-encoded assets/stage/{s}.mp4")
        return
    srv = serve()
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        pg.on("console", lambda m: m.type in ("error", "warning") and "PCFSoftShadowMap" not in m.text and print("console:", m.text))
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/stage/stage.html")
        pg.wait_for_function("window.stageReady === true || window.stageError", timeout=120_000)
        err = pg.evaluate("window.stageError || null")
        if err:
            raise SystemExit(f"stage: {err}")
        body = pg.locator("body")
        if args and args[0] == "--at":
            out = ROOT / "stage/test"; out.mkdir(parents=True, exist_ok=True)
            for a in args[1:]:
                f = int(round(float(a) * FPS))
                r = pg.evaluate("f => window.renderFrame(f)", f)
                body.screenshot(path=str(out / f"t{float(a):06.2f}.png"))
                print("still", a, r)
        else:
            shots = args or tm["shots3d"]
            dst = ROOT / "assets/stage"; dst.mkdir(parents=True, exist_ok=True)
            for s in shots:
                f0, f1 = int(round(tm[s][0] * FPS)), int(round(tm[s][1] * FPS))
                fr = ROOT / "stage/frames" / s
                if fr.exists():
                    shutil.rmtree(fr)
                fr.mkdir(parents=True)
                t0 = time.perf_counter()
                for f in range(f0, f1):
                    pg.evaluate("f => window.renderFrame(f)", f)
                    body.screenshot(path=str(fr / f"{f - f0:05d}.png"))
                    if (f - f0) % 90 == 0:
                        print(f"{s} frame {f - f0}/{f1 - f0}  {time.perf_counter() - t0:.0f}s", flush=True)
                encode(fr, dst / f"{s}.mp4")
                (dst / f"{s}.json").write_text(json.dumps({"fps": FPS, "first_frame": f0, "frames": f1 - f0,
                                                           "start": round(f0 / FPS, 4)}))
                print(f"wrote assets/stage/{s}.mp4: frames {f0}-{f1 - 1} (film {f0 / FPS:.3f}-{f1 / FPS:.3f})")
        b.close()
    srv.shutdown()


if __name__ == "__main__":
    main()
