#include "cart_ndef.h"

#include <string.h>

#define TLV_NULL       0x00
#define TLV_NDEF       0x03
#define TLV_TERMINATOR 0xFE

#define REC_MB  0x80
#define REC_ME  0x40
#define REC_SR  0x10
#define REC_IL  0x08
#define TNF_WKT 0x01

static size_t record_size(size_t text_len, bool* short_record) {
    size_t payload_len = 1 + 2 + text_len; /* status byte + "en" + text */
    bool sr = payload_len <= 255;
    if(short_record) *short_record = sr;
    return 1 /* header */ + 1 /* type length */ + (sr ? 1 : 4) + 1 /* 'T' */ + payload_len;
}

size_t cart_ndef_text_size(size_t text_len) {
    size_t rec = record_size(text_len, NULL);
    return 1 + (rec >= 0xFF ? 3 : 1) + rec + 1;
}

size_t cart_ndef_build_text(const char* text, size_t text_len, uint8_t* out, size_t out_cap) {
    bool sr;
    size_t rec = record_size(text_len, &sr);
    size_t total = cart_ndef_text_size(text_len);
    if(total > out_cap || rec > 0xFFFE) return 0;

    size_t payload_len = 1 + 2 + text_len;
    size_t i = 0;
    out[i++] = TLV_NDEF;
    if(rec >= 0xFF) {
        out[i++] = 0xFF;
        out[i++] = (uint8_t)(rec >> 8);
        out[i++] = (uint8_t)(rec & 0xFF);
    } else {
        out[i++] = (uint8_t)rec;
    }
    out[i++] = REC_MB | REC_ME | (sr ? REC_SR : 0) | TNF_WKT;
    out[i++] = 0x01; /* type length */
    if(sr) {
        out[i++] = (uint8_t)payload_len;
    } else {
        out[i++] = (uint8_t)(payload_len >> 24);
        out[i++] = (uint8_t)(payload_len >> 16);
        out[i++] = (uint8_t)(payload_len >> 8);
        out[i++] = (uint8_t)(payload_len & 0xFF);
    }
    out[i++] = 'T';
    out[i++] = 0x02; /* UTF-8, language code length 2 */
    out[i++] = 'e';
    out[i++] = 'n';
    memcpy(&out[i], text, text_len);
    i += text_len;
    out[i++] = TLV_TERMINATOR;
    return i;
}

/* Walk TLVs; returns pointer/length of the first NDEF TLV value, or false. */
static bool find_ndef_tlv(const uint8_t* a, size_t n, size_t* start, size_t* len) {
    size_t i = 0;
    while(i < n) {
        uint8_t t = a[i++];
        if(t == TLV_NULL) continue;
        if(t == TLV_TERMINATOR) return false;
        if(i >= n) return false;
        size_t l = a[i++];
        if(l == 0xFF) {
            if(i + 2 > n) return false;
            l = ((size_t)a[i] << 8) | a[i + 1];
            i += 2;
        }
        if(l > n - i) return false;
        if(t == TLV_NDEF) {
            *start = i;
            *len = l;
            return true;
        }
        i += l; /* lock / memory control / proprietary TLVs */
    }
    return false;
}

bool cart_ndef_is_empty(const uint8_t* area, size_t area_len) {
    size_t start, len;
    if(!find_ndef_tlv(area, area_len, &start, &len)) return true;
    return len == 0;
}

bool cart_ndef_find_text(const uint8_t* a, size_t n, char* out, size_t out_cap) {
    size_t p, len;
    if(out_cap == 0 || !find_ndef_tlv(a, n, &p, &len)) return false;
    size_t end = p + len;

    while(p < end) {
        uint8_t hdr = a[p++];
        if(p >= end) return false;
        uint8_t type_len = a[p++];
        size_t payload_len;
        if(hdr & REC_SR) {
            if(p >= end) return false;
            payload_len = a[p++];
        } else {
            if(end - p < 4) return false;
            payload_len = ((size_t)a[p] << 24) | ((size_t)a[p + 1] << 16) |
                          ((size_t)a[p + 2] << 8) | a[p + 3];
            p += 4;
        }
        uint8_t id_len = 0;
        if(hdr & REC_IL) {
            if(p >= end) return false;
            id_len = a[p++];
        }
        if((size_t)type_len + id_len > end - p) return false;
        const uint8_t* type = &a[p];
        p += type_len + id_len;
        if(payload_len > end - p) return false;
        const uint8_t* payload = &a[p];

        if((hdr & 0x07) == TNF_WKT && type_len == 1 && type[0] == 'T' && payload_len >= 1) {
            uint8_t status = payload[0];
            if(status & 0x80) return false; /* UTF-16 text is not supported */
            size_t lang_len = status & 0x3F;
            if(1 + lang_len > payload_len) return false;
            size_t text_len = payload_len - 1 - lang_len;
            if(text_len > out_cap - 1) text_len = out_cap - 1;
            memcpy(out, payload + 1 + lang_len, text_len);
            out[text_len] = '\0';
            return true;
        }

        p += payload_len;
        if(hdr & REC_ME) break;
    }
    return false;
}
