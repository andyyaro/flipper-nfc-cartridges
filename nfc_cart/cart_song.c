#include "cart_song.h"

#include <ctype.h>
#include <math.h>
#include <string.h>

static int note_semitone(char c) {
    switch(tolower((unsigned char)c)) {
    case 'c':
        return 0;
    case 'd':
        return 2;
    case 'e':
        return 4;
    case 'f':
        return 5;
    case 'g':
        return 7;
    case 'a':
        return 9;
    case 'b':
    case 'h':
        return 11;
    default:
        return -1;
    }
}

static bool is_pow2_duration(int d) {
    return d == 1 || d == 2 || d == 4 || d == 8 || d == 16 || d == 32 || d == 64;
}

bool cart_song_parse_rtttl(const char* s, CartSong* song) {
    song->count = 0;
    song->title[0] = '\0';

    const char* c1 = strchr(s, ':');
    if(!c1) return false;
    const char* c2 = strchr(c1 + 1, ':');
    if(!c2) return false;

    /* Title, trimmed */
    const char* t0 = s;
    const char* t1 = c1;
    while(t0 < t1 && isspace((unsigned char)*t0))
        t0++;
    while(t1 > t0 && isspace((unsigned char)t1[-1]))
        t1--;
    size_t tl = (size_t)(t1 - t0);
    if(tl >= CART_SONG_TITLE_MAX) tl = CART_SONG_TITLE_MAX - 1;
    memcpy(song->title, t0, tl);
    song->title[tl] = '\0';

    /* Defaults */
    int def_d = 4, def_o = 6, bpm = 63;
    const char* p = c1 + 1;
    while(p < c2) {
        while(p < c2 && (isspace((unsigned char)*p) || *p == ','))
            p++;
        if(p >= c2) break;
        char key = (char)tolower((unsigned char)*p++);
        while(p < c2 && isspace((unsigned char)*p))
            p++;
        if(p >= c2 || *p != '=') return false;
        p++;
        while(p < c2 && isspace((unsigned char)*p))
            p++;
        int v = 0;
        bool any = false;
        while(p < c2 && isdigit((unsigned char)*p)) {
            v = v * 10 + (*p - '0');
            p++;
            any = true;
        }
        if(!any) return false;
        if(key == 'd')
            def_d = v;
        else if(key == 'o')
            def_o = v;
        else if(key == 'b')
            bpm = v;
    }
    if(!is_pow2_duration(def_d) || def_o < 0 || def_o > 8 || bpm < 10 || bpm > 900) return false;

    const float whole_ms = 60000.0f * 4.0f / (float)bpm;

    p = c2 + 1;
    while(*p) {
        while(*p && (isspace((unsigned char)*p) || *p == ','))
            p++;
        if(!*p) break;
        if(song->count >= CART_SONG_MAX_NOTES) return false;

        int dur = 0;
        while(isdigit((unsigned char)*p))
            dur = dur * 10 + (*p++ - '0');
        if(dur == 0) dur = def_d;
        if(!is_pow2_duration(dur)) return false;

        bool rest = false;
        int semi = 0;
        char nc = (char)tolower((unsigned char)*p);
        if(nc == 'p' || nc == 'r') {
            rest = true;
            p++;
        } else {
            semi = note_semitone(nc);
            if(semi < 0) return false;
            p++;
        }
        if(*p == '#') {
            if(!rest) semi++;
            p++;
        }

        bool dotted = false;
        if(*p == '.') {
            dotted = true;
            p++;
        }
        int octave = def_o;
        if(isdigit((unsigned char)*p)) {
            octave = *p - '0';
            p++;
        }
        if(*p == '.') {
            dotted = true;
            p++;
        }
        while(*p && *p != ',') {
            if(!isspace((unsigned char)*p)) return false;
            p++;
        }

        float ms = whole_ms / (float)dur;
        if(dotted) ms *= 1.5f;
        if(ms > 65535.0f) ms = 65535.0f;

        float freq = 0.0f;
        if(!rest) {
            int midi = (octave + 1) * 12 + semi;
            freq = 440.0f * powf(2.0f, (float)(midi - 69) / 12.0f);
        }
        song->freq[song->count] = freq;
        song->ms[song->count] = (uint16_t)ms;
        song->count++;
    }
    return song->count > 0;
}

/* Copy the value after "Key:" on the line that starts with key. */
static bool fmf_field(const char* fmf, const char* key, FuriString* out) {
    size_t kl = strlen(key);
    const char* line = fmf;
    while(line && *line) {
        if(strncmp(line, key, kl) == 0 && line[kl] == ':') {
            const char* v = line + kl + 1;
            while(*v == ' ' || *v == '\t')
                v++;
            const char* e = v;
            while(*e && *e != '\n' && *e != '\r')
                e++;
            furi_string_set_strn(out, v, (size_t)(e - v));
            return true;
        }
        line = strchr(line, '\n');
        if(line) line++;
    }
    return false;
}

bool cart_song_fmf_to_rtttl(const char* fmf, const char* name, FuriString* out) {
    if(strncmp(fmf, "Filetype: Flipper Music Format", 30) != 0) return false;
    FuriString* bpm = furi_string_alloc();
    FuriString* dur = furi_string_alloc();
    FuriString* oct = furi_string_alloc();
    FuriString* notes = furi_string_alloc();
    bool ok = fmf_field(fmf, "BPM", bpm) && fmf_field(fmf, "Duration", dur) &&
              fmf_field(fmf, "Octave", oct) && fmf_field(fmf, "Notes", notes);
    if(ok) {
        furi_string_reset(out);
        for(const char* n = name; *n && furi_string_size(out) < 20; n++) {
            if(*n != ':' && *n != ',' && !isspace((unsigned char)*n)) furi_string_push_back(out, *n);
        }
        if(furi_string_size(out) == 0) furi_string_set(out, "Song");
        furi_string_cat_printf(
            out,
            ":d=%s,o=%s,b=%s:",
            furi_string_get_cstr(dur),
            furi_string_get_cstr(oct),
            furi_string_get_cstr(bpm));
        for(const char* c = furi_string_get_cstr(notes); *c; c++) {
            if(!isspace((unsigned char)*c)) furi_string_push_back(out, (char)tolower((unsigned char)*c));
        }
    }
    furi_string_free(bpm);
    furi_string_free(dur);
    furi_string_free(oct);
    furi_string_free(notes);
    return ok;
}

void cart_song_compact_rtttl(const char* in, FuriString* out) {
    furi_string_reset(out);
    const char* c1 = strchr(in, ':');
    const char* p = in;
    /* Keep the title as written (minus surrounding whitespace). */
    while(*p && isspace((unsigned char)*p))
        p++;
    if(c1) {
        const char* t1 = c1;
        while(t1 > p && isspace((unsigned char)t1[-1]))
            t1--;
        furi_string_set_strn(out, p, (size_t)(t1 - p));
        p = c1;
    }
    for(; *p; p++) {
        if(!isspace((unsigned char)*p)) furi_string_push_back(out, (char)tolower((unsigned char)*p));
    }
}
