#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/*
 * Minimal NDEF helpers for NFC Forum Type 2 tags (NTAG21x / Ultralight).
 * The data area is the tag's user memory starting at page 4.
 */

/* Build an NDEF TLV holding one well-known Text record (lang "en"), followed by
 * the 0xFE terminator TLV. Returns the number of bytes written, or 0 if the
 * message does not fit in out_cap. */
size_t cart_ndef_build_text(const char* text, size_t text_len, uint8_t* out, size_t out_cap);

/* Bytes cart_ndef_build_text() would need for a text of this length. */
size_t cart_ndef_text_size(size_t text_len);

/* Find the first Text record inside the first NDEF TLV of a Type 2 data area.
 * Copies it NUL-terminated into out (truncated to out_cap - 1). */
bool cart_ndef_find_text(const uint8_t* area, size_t area_len, char* out, size_t out_cap);

/* True when the data area holds an empty NDEF message or nothing at all. */
bool cart_ndef_is_empty(const uint8_t* area, size_t area_len);
