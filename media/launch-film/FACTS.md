# NFC Cartridges film: every claim and its source

The app repo is `andyyaro/flipper-nfc-cartridges` at `70693bf` ("Add project logo"), cloned read-only. "Captured" means
the real device, recorded over USB on 2026-11-01 (`research/flipper-capture/`: `frames.bin`, `log.txt`).

## The narration

| # | Line (as subtitled) | Source | Checked |
|---|---|---|---|
| v01 | "A plain NFC sticker holds 504 bytes." | README table: NTAG215, 504 bytes. The app's own screen: "Used 100 of 504 bytes". | captured screen s0057 |
| v02 | "That's room for a whole song." | README table: NTAG215, "100 to 150 notes". Ode to Joy (30 notes) uses 100 of the 504 bytes. | computed |
| v03 | "NFC Cartridges, for Flipper Zero." | README title "NFC Cartridges for Flipper Zero"; the app is under Apps > NFC. | read |
| v04 | "Pick a song, then hold a blank sticker to the back." | README "Using it": "Burn cartridge: pick a song file, then hold a blank sticker to the back." | read; captured |
| v05 | "It burns the tune on, page by page, in under two seconds." | Captured: "Page 1 / 25" to "Page 25 / 25" in 0.82 s, "Cartridge burned!" 1.32 s after page 1 (after the read-back check). | `stage/tape.py` prints both |
| v06 | "Ode to Joy takes 100 bytes." | The app's screen after the burn: "Used 100 of 504 bytes". By hand: TLV 03 + length (2) + record header (4) + status byte and "en" (3) + the song (90) + FE (1) = 100. | captured; computed |
| v07 | "Nothing goes on the SD card. The song is a standard NDEF text record, so phones can read it too." | README: "Nothing is stored on the SD card. The whole song sits on the sticker as a standard NDEF Text record containing RTTTL. Because it's plain NDEF, any phone NFC app can read a cartridge." | read |
| v08 | "It writes the length last, so a torn burn reads as blank, never half a song." | README "How burning works": page 4 first with NDEF length 0, then the song, then page 4 with the real length; "If the sticker is pulled away halfway through, it reads as blank instead of half a song." | read |
| v09 | "Then it reads the sticker back and checks every byte." | README: "After writing, it reads the sticker back and checks it matches." `nfc_cart/nfc_cart.c` 345-350: up to 3 read-backs, `memcmp` over the whole message. | read |
| v10 | "Tap it in Play, and the Flipper plays it straight off the sticker." | README "Play cartridge". Captured: "Hold a cartridge to the back of Flipper", "Waiting", "Note 1 / 30" ... "Note 30 / 30", "Done". | captured |
| v11 | "It burns NTAG213, 215 and 216 stickers, from a short jingle to 250 notes." | README table: NTAG213 144 bytes "a short jingle"; NTAG215 504 bytes "100 to 150 notes"; NTAG216 888 bytes "250+ notes". | read |
| v12 | "NFC Cartridges. Songs that live on a sticker." | README: "Songs that live entirely on an NFC sticker." | read |

## On screen

| Text | Source |
|---|---|
| "Real time: written and checked in 1.3 s" | captured (1.32 s from page 1 to "Cartridge burned!") |
| "100 of 504 bytes", "25 of 126 pages", "Pages 5 to 28" | NTAG215 user memory is pages 4 to 129 (126 pages of 4 bytes = 504). 100 bytes fill 25 pages: page 4 and pages 5 to 28. The captured screen counts "Page 1 / 25" to "Page 25 / 25". |
| "type 03, length 97"; "4 bytes"; "T, en"; "90 bytes"; "FE" | `nfc_cart/cart_ndef.c` (the encoder). The song file `songs/ode_to_joy.txt` is 90 characters plus a newline. 97 = 4 + 3 + 90. |
| "Page 4 first, with length 0" / "Page 4 last, with the real length: 97" | README "How burning works" |
| "Locked or password-protected: refused" | README: "It refuses stickers that have lock bits set, are password protected, or are read-only." |
| "Built for official firmware 1.2.0" | README "Building": "built against official firmware 1.2.0 (API 79.2)" |
| "NDEF encoder tests pass" | Host test run 2026-11-02, as the README says: `cc -Wall -Wextra -I nfc_cart tests/test_ndef.c nfc_cart/cart_ndef.c` then `./test_ndef`: "all NDEF tests passed" (36-byte song -> 46-byte NDEF, 479-byte song -> 494-byte NDEF). |
| "Open source, MIT" | [`LICENSE`](../../LICENSE) at the repository root |
| "github.com/andyyaro/flipper-nfc-cartridges" | the repo's `origin` |
| The LED blinking cyan on each note | `nfc_cart.c` 164: `sequence_blink_cyan_10` per note |
| Note 1 sounding 300 ms after "Note 1 / 30" shows | `nfc_cart.c` 209: `furi_delay_ms(300)` before `play_song` |

## What is real and what is reconstructed

- **The screen is real.** Every Flipper screen in the film is a frame recorded from the device over USB (the RPC screen
  stream), drawn 8 x with no smoothing. Nothing on it is redrawn or retyped.
- **One held frame.** Andy's blank sticker was already on the Flipper's back when the burn started, so the real burn
  followed the OK press at once. In the film, "Waiting..." is held until the 3D sticker arrives; from there the burn
  plays at its recorded speed. `stage/tape.py` documents this.
- **The tune is synthesized, not mic-recorded.** It is built from the app's own RTTTL parse (`cart_song.c`: note
  length = whole / d, dotted x 1.5, 440 Hz equal temperament) as a band-limited square wave, on the note times
  recorded from the device's screen (fitted with a 23.6 ms per-note overhead, within 13 ms of every recorded note).
  15 of the 30 notes are heard.
- **The 3D device and sticker are models**, posed by script (`stage/shots.js`), not footage. The button presses happen
  at the recorded presses.
