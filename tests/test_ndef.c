/* Host-side test for the NDEF encoder/parser.
 * cc -Wall -Wextra -I nfc_cart tests/test_ndef.c nfc_cart/cart_ndef.c -o test_ndef && ./test_ndef
 */
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "cart_ndef.h"

int main(void) {
    uint8_t buf[1024];
    char out[1024];

    /* A freshly formatted NTAG215 user area: empty NDEF TLV + terminator. */
    uint8_t blank[504] = {0x03, 0x00, 0xFE};
    assert(cart_ndef_is_empty(blank, sizeof(blank)));
    assert(!cart_ndef_find_text(blank, sizeof(blank), out, sizeof(out)));

    /* Short and long records both round-trip. */
    char long_song[480];
    memset(long_song, 'c', sizeof(long_song));
    memcpy(long_song, "L:d=4,o=5,b=120:", 16);
    long_song[sizeof(long_song) - 1] = '\0';

    const char* songs[] = {"Twinkle:d=4,o=5,b=120:c,c,g,g,a,a,2g", long_song};
    for(size_t k = 0; k < sizeof(songs) / sizeof(songs[0]); k++) {
        size_t len = strlen(songs[k]);
        size_t n = cart_ndef_build_text(songs[k], len, buf, sizeof(buf));
        assert(n == cart_ndef_text_size(len));

        memset(out, 0, sizeof(out));
        assert(cart_ndef_find_text(buf, n, out, sizeof(out)));
        assert(strcmp(out, songs[k]) == 0);
        assert(!cart_ndef_is_empty(buf, n));
        printf("ok: %zu byte song -> %zu byte NDEF (%s record)\n",
               len, n, len + 3 <= 255 ? "short" : "long");
    }

    /* Refuses to build into a buffer that is too small. */
    assert(cart_ndef_build_text(long_song, strlen(long_song), buf, 100) == 0);

    /* Truncated or garbage data must not crash or match. */
    uint8_t junk[8] = {0x03, 0xFF, 0xFF, 0xFF, 0xD1, 0x01, 0x50, 'T'};
    assert(!cart_ndef_find_text(junk, sizeof(junk), out, sizeof(out)));

    printf("all NDEF tests passed\n");
    return 0;
}
