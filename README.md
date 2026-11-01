# NFC Cartridges for Flipper Zero

Songs that live entirely on an NFC sticker. Burn a tune onto a cheap NTAG sticker with your Flipper, stick it on something, and tap it later to hear it play.

Nothing is stored on the SD card. The whole song sits on the sticker as a standard NDEF Text record containing RTTTL. Because it's plain NDEF, any phone NFC app can read a cartridge, and you can write one from a phone too.

## Using it

The app shows up under **Apps > NFC > NFC Cartridges**.

- **Play cartridge**: hold a cartridge to the back of the Flipper and it plays. Press OK to hear it again.
- **Burn cartridge**: pick a song file, then hold a blank sticker to the back. Keep it still until it says it's done.

Song files go in `/ext/apps_data/nfc_cart/` on the SD card (copy them over with qFlipper). Two formats work:

- RTTTL in a `.txt` file, e.g. `Twinkle:d=4,o=5,b=120:c,c,g,g,a,a,2g`
- Flipper Music Format `.fmf` files, the same ones the built-in Music Player uses. These are converted to RTTTL when you burn them.

There are a few public domain songs in `songs/` to get started.

## Stickers

Burning works on NTAG213, NTAG215 and NTAG216. Playing also reads NTAG203 and MIFARE Ultralight.

| Sticker | Space for songs | Roughly |
|---|---|---|
| NTAG213 | 144 bytes | a short jingle |
| NTAG215 | 504 bytes | 100 to 150 notes |
| NTAG216 | 888 bytes | 250+ notes |

Each song costs about 15 bytes of NDEF overhead on top of its RTTTL text.

## How burning works

The app is careful about what it writes:

- It only writes user memory pages, never the config, password or lock pages.
- It refuses stickers that have lock bits set, are password protected, or are read-only.
- The capability container is only written if it's blank (all zeros).
- Page 4 is written first with an NDEF length of zero, then the rest of the song, then page 4 again with the real length. If the sticker is pulled away halfway through, it reads as blank instead of half a song.
- After writing, it reads the sticker back and checks it matches.

## Building

You need [ufbt](https://github.com/flipperdevices/flipperzero-ufbt), with the SDK matching your firmware. The app was built against official firmware 1.2.0 (API 79.2):

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install ufbt
ufbt update -t f7 --url https://update.flipperzero.one/builds/firmware/1.2.0/flipper-z-f7-sdk-1.2.0.zip
cd nfc_cart
ufbt launch      # build, install and start it on a connected Flipper
```

If your Flipper runs a different firmware version, point `ufbt update` at that version's SDK instead. A mismatched API version won't load.

## Tests

The NDEF encoder and parser are plain C, so they can be tested on a computer:

```sh
cc -Wall -Wextra -I nfc_cart tests/test_ndef.c nfc_cart/cart_ndef.c -o test_ndef && ./test_ndef
```

## Turning recordings into cartridges (experimental)

`tools/song_to_rtttl.py` tries to pull a vocal melody out of a recording and turn it into RTTTL that fits on a sticker. Split the vocals off first with Demucs, then:

```sh
pip install -r tools/requirements.txt
demucs --two-stems=vocals song.mp3
python tools/song_to_rtttl.py track separated/htdemucs/song/vocals.wav song.mp3 cache/
python tools/song_to_rtttl.py make cache/ 42.0 58.0 MySong out/
```

`make` takes a start and end time in seconds. It writes the RTTTL plus a square wave preview so you can hear what the Flipper will play, and prints how closely the result follows the real vocal.

Results vary a lot. Simple, clearly sung melodies come out best. Fast or heavily processed vocals often don't survive being squeezed into one beeping voice. Only burn songs you have the rights to.

## Ideas for later

- Game cartridges: tiny games or levels stored on the sticker
- Save data written back to the cartridge
- Swapping and lending cartridges between Flippers

## License

MIT. See [LICENSE](LICENSE).
