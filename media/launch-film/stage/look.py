"""Render a few stage poses to stills (look development).

    $PW/bin/python -I stage/look.py poses.json outdir      (poses.json: [{"name": ..., ...pose}, ...])
"""
import functools, http.server, json, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    poses = json.loads(Path(sys.argv[1]).read_text()); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    srv = serve()
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        pg.on("console", lambda m: m.type in ("error", "warning") and print("console:", m.text))
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/stage/stage.html")
        pg.wait_for_function("window.stageReady === true || window.stageError", timeout=120_000)
        print("stage:", pg.evaluate("window.stageError || 'ready'"), pg.evaluate("window.modelInfo"))
        for ps in poses:
            pg.evaluate("p => window.pose(p)", ps)
            pg.locator("body").screenshot(path=str(out / f"{ps['name']}.png"))
            print("wrote", ps["name"])
        b.close()
    srv.shutdown()


if __name__ == "__main__":
    main()
