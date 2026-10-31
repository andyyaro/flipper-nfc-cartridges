#pragma once

#include <furi.h>
#include <stdbool.h>
#include <stdint.h>

#define CART_SONG_MAX_NOTES 400
#define CART_SONG_TITLE_MAX 32

typedef struct {
    char title[CART_SONG_TITLE_MAX];
    uint16_t count;
    float freq[CART_SONG_MAX_NOTES]; /* Hz, 0 = rest */
    uint16_t ms[CART_SONG_MAX_NOTES];
} CartSong;

/* Parse RTTTL ("name:d=4,o=5,b=120:c,8d#6.,p,..."). Case-insensitive. */
bool cart_song_parse_rtttl(const char* text, CartSong* song);

/* Convert Flipper Music Format text into compact RTTTL. name becomes the title. */
bool cart_song_fmf_to_rtttl(const char* fmf, const char* name, FuriString* out);

/* Strip all whitespace after the title so the song takes as few bytes as possible. */
void cart_song_compact_rtttl(const char* in, FuriString* out);
