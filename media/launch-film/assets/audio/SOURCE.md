# Third-party sounds, pictures and type in the film

These are in the film but not in this repository. Their licences cover using them inside a film,
not handing the files on by themselves, so they are listed here instead. Download each one again
to the path shown to rebuild.

## Music

| Used as | Track | Licence | Put it at |
|---|---|---|---|
| The bed under the film, cut on its bar lines by `sound/music.py`; it stops while the Flipper plays its tune (50.5 to 58.1 s) | "Tom" by Arulo, Mixkit 244 | [Mixkit Stock Music Free License](https://mixkit.co/license/): free in any project, no credit required, not for use in a music-only track | `sound/track.mp3` |

## Sound effects

All from Mixkit, under the [Mixkit Sound Effects Free License](https://mixkit.co/license/).
The names are the ones `sound/mix.py` uses (`SFX`); each file goes in `sound/sfx-src/` as
`mixkit-<id>.mp3`.

| Name in `mix.py` | Mixkit id | What it marks |
|---|---|---|
| `pop` | 2357 | A part arriving: the melody dots, the cards on the board, the three stickers; the sticker touching the Flipper's back. Pitched down for "Locked or password-protected: refused" |
| `tick` | 1120 | A counter or a step: "504 bytes", "100 of 504 bytes", page 4 with length 0, the read-back sweep, the proof chips, the URL. Pitched up, the click of each button press |
| `whoosh_air` | 1492 | The sticker flying to the Flipper's back, in the burn and in the play scene |
| `whoosh_wind` | 1465 | The camera gliding to the sticker card on the board |
| `sweep` | 3115 | The two big camera moves: round to the Flipper's back, and the pull back from the board |
| `pop_hard` | 3005 | The soft hit on the title drop, the drums coming back and the end card. Pitched up, the chime on "Cartridge burned!" |
| `riser` | 2408 | The swell into the title drop |

## Voice

Kokoro-82M ([Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M)), voice af_heart, run
locally. The lines are `narration/lines-tts.json`; the audio is generated, so it is not kept.

## The Flipper's tune

Ode to Joy as the app plays it: `stage/tape.py` parses the song in the repository's
`songs/ode_to_joy.txt` (public domain; it keeps a copy of the line) and fits its notes to the
times recorded from the device, and `sound/mix.py` synthesizes it as a small square-wave speaker.
Nothing to download.

## 3D models

| Model | By | Licence | Put it at |
|---|---|---|---|
| [Flipper Zero](https://sketchfab.com/3d-models/flipper-zero-f8ad3fdf5f2b485ba46b0ac91626fc76) (most likely; see below) | blazitt, on Sketchfab | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): credit required | the source `Flipper.blend`, made into `assets/models/flipper.glb` by `stage/export_flipper.py` |
| NTAG215 sticker | Made for these films | Same as this repository | `assets/models/ntag215-sticker.glb` (kept here) |

The Flipper model came as a Blender file and one texture, with no readme or licence. Its eight
material names (`Flipper_Main`, `Flipper_Orange`, `Flipper_Screen` and so on) are the ones in the
glTF that Sketchfab serves for the listing above, which names blazitt as the author and CC BY 4.0
as the licence. Until that is confirmed it stays out of the repository. If it is that model, the
credit is due wherever the film is shown: it is in this folder's README and the release notes,
but not on the film's end card.

## Type

Geist (Regular, Medium, SemiBold, Bold) and Montserrat SemiBold, both under the
[SIL Open Font License 1.1](https://openfontlicense.org/), as `.woff2` files in `assets/fonts/`
with the names `index.html` loads (`Geist-Regular.woff2`, …, `Montserrat-SemiBold.woff2`).

## Pictures

Every Flipper screen in the film is a frame the device sent over USB on 2026-11-01 (its RPC
screen stream, recorded by `research/flipper-capture/rec.py`). `stage/screens.py` turns each
distinct screen into an image for the 3D display, drawn 8 times larger with no smoothing. The
recording itself (`research/flipper-capture/frames.bin`) is not kept here; `log.txt` beside the
capture scripts has every button press and its time.
