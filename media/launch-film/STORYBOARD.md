# NFC Cartridges launch film: storyboard and build

76.5 s, 1920 × 1080, 30 fps. H.264 with AAC at 256 kb/s; measured on the MP4: -16.2 LUFS
integrated, true peak -1.9 dBTP, loudness range 4.9 LU. Made against the app at `70693bf`
("Add project logo"). Every claim in it and its source is in [FACTS.md](FACTS.md).

## What is real and what is rebuilt

- **The screen is real.** Every Flipper screen in the film is a frame recorded from the device
  over USB on 2026-11-01 (the RPC screen stream, `research/flipper-capture/`), drawn 8 times
  larger with no smoothing. Nothing on it is redrawn or retyped.
- **One held frame.** The blank sticker was already on the Flipper's back when the real burn
  started, so the burn followed the OK press at once. In the film, "Waiting..." is held until the
  3D sticker arrives; from there the burn plays at its recorded speed: 25 pages in 0.82 s,
  "Cartridge burned!" 1.32 s after page 1. `stage/tape.py` documents this.
- **The tune is synthesized, not recorded with a microphone.** It is built from the app's own
  RTTTL parse (`cart_song.c`: note length = whole / d, dotted × 1.5, 440 Hz equal temperament)
  as a band-limited square wave, on the note times recorded from the device's screen. 15 of the
  30 notes are heard.
- **The Flipper and the sticker are 3D models**, posed by script (`stage/shots.js`), not
  footage. The button presses happen at the recorded presses.

## Build

Get the inputs first: `tools/fetch_vendor.sh` for three.js and GSAP, then the fonts, the Flipper
model, the music and the effects listed in [assets/audio/SOURCE.md](assets/audio/SOURCE.md). The
Python steps need numpy, soundfile, scipy, librosa, mlx-whisper and ffmpeg, or Playwright with
Chromium for the 3D stage; the capture needs pyserial and the flipperzero-protobuf definitions.

```sh
tools/fetch_vendor.sh
# The capture (reads only: the screen stream and button presses; nothing is written to the Flipper).
#   python3 -I research/flipper-capture/rec.py <session>    -> frames.bin, log.txt
python3 -I stage/screens.py                                      # assets/screen/sNNNN.png, index.json
blender -b --factory-startup --disable-autoexec <Flipper.blend> \
  --python stage/export_flipper.py -- assets/models/flipper.glb  # the Flipper, split into moving parts
# Voice each line of narration/lines-tts.json with Kokoro-82M (af_heart) at speeds 1.0 and 1.06,
# as narration/takes/<id>.<k>.wav
python3 -I narration/pick.py takes                               # best take per line, words.json
python3 -I sound/music.py                                        # assets/audio/music.wav, sound/grid.json
python3 -I sound/mix.py                                          # mix.wav, vo.js, timing.js, tape.js (stage/tape.py)
python3 -I stage/render.py                                       # assets/stage/<shot>.mp4 (s1, s3, s5, s6, s7)
python3 -I build.py                                              # scene windows, subtitles, the .vtt
npx --yes hyperframes@0.8.173 lint && npx --yes hyperframes@0.8.173 check
npx --yes hyperframes@0.8.173 render -o renders/raw.mp4 --fps 30
ffmpeg -y -i renders/raw.mp4 -i assets/audio/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k \
  -shortest -movflags +faststart renders/flipper-nfc-cartridges-v1.mp4
```

`stage/render.py --at <t> …` renders stills for checking a pose; `--encode` re-encodes the kept
frames without rendering again. The scenes and the 3D shots read the same timing (`window.TM`,
`window.VO`, `window.TAPE`), so a re-voiced line re-times the picture.

## The music edit

"Tom" by Arulo (Mixkit 244), 95 BPM in 4/4, so a bar is 2.5251 s. `sound/music.py` joins it on
bar lines with 20 ms crossfades:

| Film (s) | Track | What it is |
|---|---|---|
| 0–5.05 | bars 0–1 | The real opening, keys only |
| 5.05–10.10 | bars 6–7 | The bass and the build |
| 10.10–50.50 | bars 8–23 | The drop on the title, then grooves A and B; faded out over the last bar |
| 50.50–58.08 | none | No music: the Flipper plays Ode to Joy alone (it is in C; Tom is in C#) |
| 58.08–76.50 | bars 40–47 | The drums come back on the proof; the track's own ending under the end card |

## The film

| Time (s) | Scene | Narration | What you see |
|---|---|---|---|
| 0–10.1 | Hook (3D) | "A plain NFC sticker holds 504 bytes." "That's room for a whole song." | A 25 mm NTAG215 sticker turns to face the camera; "504 bytes" counts up; Ode to Joy's 30 notes as a pixel melody. |
| 10.1–15.2 | Title | "NFC Cartridges, for Flipper Zero." | The NFC Cartridges lockup on the music's drop, the tagline, "A Flipper Zero app · open source, MIT". |
| 15.2–28.2 | Burn (3D) | "Pick a song, then hold a blank sticker to the back." "It burns the tune on, page by page, in under two seconds." "Ode to Joy takes 100 bytes." | The Flipper's real screen: the menu, Burn cartridge, the file browser, ode_to_joy.txt, "Waiting...". The sticker flies round the right end onto the back, the burn runs at its recorded speed (25 pages), "Cartridge burned!". The camera goes round to the back; a ring marks the sticker; "100 of 504 bytes". |
| 27.8–45.9 | Inside a cartridge | "Nothing goes on the SD card. The song is a standard NDEF text record, so phones can read it too." "It writes the length last, so a torn burn reads as blank, never half a song." "Then it reads the sticker back and checks every byte." | On cream: the song file (RTTTL), the NDEF Text record field by field (100 bytes), the NTAG215's 126 pages. The camera moves into the sticker card: page 4 with length 0, pages 5 to 28, page 4 with the real length, then every page read back and checked. "SD card: nothing stored", "Any phone's NFC app can read it", "Locked or password-protected: refused". |
| 45.5–58.5 | Play (3D) | "Tap it in Play, and the Flipper plays it straight off the sticker." | Play cartridge, "Hold a cartridge to the back", the tap, then the music stops and the Flipper plays Ode to Joy alone, "Note i / 30" on its real screen, the LED blinking cyan on every note. |
| 58.1–68.6 | Proof (3D) | "It burns NTAG213, 215 and 216 stickers, from a short jingle to 250 notes." | NTAG213, 215 and 216 pop in with their sizes (144, 504, 888 bytes); "Built for official firmware 1.2.0", "NDEF encoder tests pass", "Open source, MIT". |
| 68.2–76.5 | End card | "NFC Cartridges. Songs that live on a sticker." | The lockup and "Songs that live on a sticker. Tap to play." on the left, the Flipper and a cartridge turning on the right, github.com/andyyaro/flipper-nfc-cartridges. |

## Look

- **Style:** a UI film, built like the EV-SIENT film (a 3D device on a soft ground, push-ins and
  orbits, the real screen on the device) in the Outbreak films' frame grammar: a Montserrat
  SemiBold capitals kicker, a bold headline at top left, small white chips with a status dot,
  subtitles burned in on a dark pill.
- **Brand:** the app's own: pink #FF9ACB ground, ink #141414, cream #FFF5E1 for the board,
  magenta #D10F6A for the song. The pixel lockup is the repository's (`assets/brand/`).
- **Type:** Geist (400 to 700) for everything, Montserrat SemiBold for the kickers. No monospace
  anywhere, the RTTTL text included, and no em dashes on screen. Icons: the HIG Native line glyphs
  (`scripts/vendor/hig-icons.js`, written into `index.html` by `scripts/build-icons.mjs`).
- **The 3D stage** (`stage/`): three.js r186, rendered frame by frame on the film's own frame grid
  in Chromium on the GPU, then encoded BT.709 so the pink matches the HTML scenes exactly.
  `stage/export_flipper.py` straightens the Flipper model in Blender, gives its screen UVs and
  splits off the D-pad, the back button and the LED so they can move; `stage/stage.html` rebuilds
  its materials by name (white body, orange D-pad, the screen as an emissive texture of the
  recorded frame). The model carries the FLIPPER wordmark, as the real device does. The sticker
  is the 25 mm, 0.8 mm thick NTAG215 model made for these films.

## Sound

- **Voice:** Kokoro-82M, voice af_heart, 12 lines, the 1.0 speed take of each, every take matching
  the script word for word. Spoken forms are in `narration/lines-tts.json`: "N F C", "S D", NDEF
  as /ˈɛndɛf/, NTAG as /ˈɛntæɡ/.
- **Music:** "Tom" by Arulo, cut as above: the real opening under the hook, the drop on the title,
  grooves under the burn and the board, then silence while the Flipper plays, the drums back on
  the proof and the track's own ending under the end card.
- **The Flipper's tune:** Ode to Joy as the app plays it, on the note times recorded from the
  device. It plays alone, at -17.9 LUFS, between 50.5 and 58.1 s.
- **Effects:** soft Mixkit interface sounds: a click on each button press, pops for parts
  arriving, whooshes for the sticker's flights and the camera's moves, a soft chime on "Cartridge
  burned!". The list is in [assets/audio/SOURCE.md](assets/audio/SOURCE.md).
- **Levels:** speech -16 LUFS, the bed 9 dB under it, master -16.2 LUFS, true peak -1.9 dBTP.

## The README preview

`docs/assets/readme/nfc-cartridges-in-action.webp` is the burn scene, 15.2–31.2 s of the film,
at 1200 × 676 and 15 fps, 6.2 MB at quality 90: the menu, the file browser, the sticker flying
onto the back, the real burn, "Cartridge burned!", "100 of 504 bytes", and the first seconds
inside the cartridge. At this quality the frames where the camera moves round to the back show
no blocking.

```sh
mkdir -p preview
ffmpeg -ss 15.2 -t 16 -i renders/flipper-nfc-cartridges-v1.mp4 \
  -vf "fps=15,scale=1200:676:flags=lanczos" preview/f%03d.png
img2webp -loop 0 -lossy -q 90 -m 6 -d 67 preview/f*.png \
  -o ../../docs/assets/readme/nfc-cartridges-in-action.webp
```
