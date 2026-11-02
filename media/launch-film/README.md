# NFC Cartridges launch film

The 77-second film at the top of the [repository README](../../README.md). It shows the app
burning Ode to Joy onto an NTAG215 sticker, what the sticker then holds, page by page, and the
Flipper playing the song straight off the sticker. Every Flipper screen in it is a frame the
device itself sent over USB, played at the recorded speed; the Flipper and the sticker around
that screen are 3D models.

[STORYBOARD.md](STORYBOARD.md) has the scenes, the look, the sound and every build step.
[FACTS.md](FACTS.md) has every claim in the film and where it comes from.

## What is here

| Path | What it is |
|---|---|
| `index.html`, `compositions/` | The composition (HyperFrames 0.8.173, GSAP): one file per scene, plus the burned-in subtitles |
| `build.py` | Writes the scene windows and subtitles into the composition, and the captions file |
| `stage/` | The 3D shots: `stage.html` and `shots.js` (three.js), `render.py` (frame by frame in Chromium), `screens.py` (the recorded screens as images for the Flipper's display), `tape.py` (which screen shows when, the button presses and the tune's note times), `export_flipper.py` (prepares the Flipper model in Blender), `look.py` |
| `sound/` | The music edit (`music.py`) and the mix (`mix.py`): narration, music, the Flipper's own tune and effects |
| `narration/` | The script (`lines.json`), the script as voiced (`lines-tts.json`) and `pick.py`, which chooses the best take of each line and times its words |
| `research/flipper-capture/` | The device capture: `flip.py` (a small Flipper Zero RPC client over USB), `rec.py` (records the screen stream while sending button presses) and `log.txt` (every press and its time) |
| `FACTS.md` | Every line of narration and every on-screen claim, with its source |
| `scripts/` | The HIG Native line icons and the script that writes them into `index.html` |
| `tools/fetch_vendor.sh` | Fetches three.js and GSAP at the pinned versions and checks each file's SHA-256 |
| `assets/brand/lockup-color.svg` | The NFC Cartridges lockup from [`docs/assets/brand/`](../../docs/assets/brand/), as the title and end card use it |
| `assets/models/ntag215-sticker.glb` | The sticker model, made for these films |
| `assets/audio/SOURCE.md` | Every third-party sound, model and font in the film, with its licence and where it goes |

## What is not here, and why

The working folder for the film is about 520 MB. This folder keeps the source and leaves out
everything that is generated, recorded, or that its licence does not let us hand on by itself:

- **Generated:** the Flipper's screen images, the 3D renders, the narration takes and word
  times, the music edit, the mix, the timing and tape files, the tune's note list and the
  renders. The build steps make them again.
- **The screen recording** from the device (`research/flipper-capture/frames.bin`, 1,742 frames).
  `stage/tape.py` and [FACTS.md](FACTS.md) say how it maps onto the film. `flip.py` also needs the
  official flipperzero-protobuf definitions compiled into `research/flipper-capture/pb/`.
- **Third-party media:** the music ("Tom" by Arulo, Mixkit), seven Mixkit sound effects and the
  Flipper Zero 3D model, which came without a licence (most likely "Flipper Zero" by blazitt on
  Sketchfab, CC BY 4.0). [assets/audio/SOURCE.md](assets/audio/SOURCE.md) lists each one with its
  licence and the path it goes to.
- **Libraries and fonts:** three.js r186 and GSAP 3.14.2 are fetched by `tools/fetch_vendor.sh`.
  The Geist and Montserrat fonts (SIL OFL 1.1) go in `assets/fonts/`. `node_modules/` and
  `.hyperframes/` are caches that the HyperFrames tools make again.

## Publishing

The MP4, its captions and its poster are assets of the
[`film-v1` release](https://github.com/andyyaro/flipper-nfc-cartridges/releases/tag/film-v1), so
the 27.2 MB film is not in the repository's history. The repository is private, so only people
with access to it can open the release asset. There is no watch page: a GitHub Pages site would
make the film public. If the repository goes public, a watch page (`deploy/film.html`) and the
workflow that publishes it (`film.yml`) can be added as
[nearsay](https://github.com/andyyaro/nearsay/tree/main/media/launch-film) has them.

After rebuilding the film, replace the release asset:

```sh
gh release upload film-v1 nfc-cartridges-launch.mp4 --clobber
```

## Credits

Narration: Kokoro-82M (Apache-2.0), voice af_heart. Music: "Tom" by Arulo (Mixkit). Sound
effects: Mixkit. 3D models: the Flipper Zero, most likely "Flipper Zero" by blazitt (Sketchfab,
CC BY 4.0), and the NTAG215 sticker, made for these films, drawn with three.js. Type: Geist and
Montserrat (SIL OFL 1.1). Icons: HIG Native.
