/*
 * NFC Cartridges: songs that live entirely on an NFC sticker.
 *
 * Play: tap a sticker, the Flipper reads the RTTTL song stored inside it and plays it.
 * Burn: pick an RTTTL (.txt) or Flipper Music Format (.fmf) file and write it onto a
 *       blank NTAG/Ultralight sticker as a standard NDEF Text record, so phones can
 *       read (and write) cartridges too.
 *
 * Safety: only user-memory pages are written. Lock bytes, OTP, config and password
 * pages are never touched, and a sticker with locks set is refused.
 */

#include <furi.h>
#include <furi_hal.h>
#include <gui/gui.h>
#include <gui/elements.h>
#include <input/input.h>
#include <dialogs/dialogs.h>
#include <storage/storage.h>
#include <toolbox/path.h>
#include <notification/notification_messages.h>
#include <nfc/nfc.h>
#include <nfc/protocols/mf_ultralight/mf_ultralight.h>
#include <nfc/protocols/mf_ultralight/mf_ultralight_poller_sync.h>

#include "cart_ndef.h"
#include "cart_song.h"

#define TAG          "NfcCart"
#define CART_DIR     EXT_PATH("apps_data/nfc_cart")
#define TEXT_MAX     1024 /* biggest supported tag (NTAG216) holds 888 bytes */
#define AREA_MAX     1024
#define WORKER_STACK 4096
#define VOLUME       0.8f

typedef enum {
    ScreenMenu,
    ScreenScan,
    ScreenPlaying,
    ScreenBurnWait,
    ScreenBurning,
    ScreenMessage,
    ScreenAbout,
} Screen;

typedef enum {
    MenuPlay,
    MenuBurn,
    MenuAbout,
    MenuCount,
} MenuItem;

static const char* const menu_labels[MenuCount] = {"Play cartridge", "Burn cartridge", "About"};

typedef struct {
    FuriMutex* mutex;
    FuriMessageQueue* input_queue;
    ViewPort* view_port;
    Gui* gui;
    NotificationApp* notif;
    DialogsApp* dialogs;
    Nfc* nfc;
    FuriThread* worker;
    volatile bool worker_run;

    Screen screen;
    uint8_t menu_index;
    uint32_t tick;

    /* Play */
    CartSong* song;
    uint16_t note_index;
    bool song_done;

    /* Burn */
    char* burn_text;
    size_t burn_len;
    char burn_title[CART_SONG_TITLE_MAX];
    uint16_t burn_progress;
    uint16_t burn_total;

    /* Message */
    char msg_title[24];
    char msg_body[160];
} NfcCartApp;

/* ---------- small helpers ---------- */

static void set_screen(NfcCartApp* app, Screen s) {
    furi_mutex_acquire(app->mutex, FuriWaitForever);
    app->screen = s;
    furi_mutex_release(app->mutex);
    view_port_update(app->view_port);
}

static void show_message(NfcCartApp* app, const char* title, const char* body) {
    furi_mutex_acquire(app->mutex, FuriWaitForever);
    strlcpy(app->msg_title, title, sizeof(app->msg_title));
    strlcpy(app->msg_body, body, sizeof(app->msg_body));
    app->screen = ScreenMessage;
    furi_mutex_release(app->mutex);
    view_port_update(app->view_port);
}

/* Last page of user memory for the tag types we support, 0 if unsupported. */
static uint16_t user_end_page(MfUltralightType type, uint16_t pages_total) {
    switch(type) {
    case MfUltralightTypeNTAG213:
    case MfUltralightTypeNTAG215:
    case MfUltralightTypeNTAG216:
        return pages_total - 6; /* dyn lock, CFG0, CFG1, PWD, PACK follow */
    case MfUltralightTypeNTAG203:
        return 39;
    case MfUltralightTypeOrigin:
    case MfUltralightTypeUL11:
        return 15;
    case MfUltralightTypeUL21:
        return 35;
    default:
        return 0;
    }
}

static bool is_ntag21x(MfUltralightType type) {
    return type == MfUltralightTypeNTAG213 || type == MfUltralightTypeNTAG215 ||
           type == MfUltralightTypeNTAG216;
}

/* Copy the user data area (page 4..end) out of a read result. */
static size_t extract_area(const MfUltralightData* d, uint16_t end, uint8_t* out) {
    size_t n = 0;
    for(uint16_t pg = 4; pg <= end && pg < d->pages_read && n + 4 <= AREA_MAX; pg++) {
        memcpy(&out[n], d->page[pg].data, 4);
        n += 4;
    }
    return n;
}

static void sleep_while_running(NfcCartApp* app, uint32_t ms) {
    while(ms > 0 && app->worker_run) {
        uint32_t step = ms > 20 ? 20 : ms;
        furi_delay_ms(step);
        ms -= step;
    }
}

/* ---------- workers ---------- */

static void play_song(NfcCartApp* app) {
    if(!furi_hal_speaker_acquire(1000)) {
        show_message(app, "Speaker busy", "Another app is using\nthe speaker.");
        return;
    }
    for(uint16_t i = 0; i < app->song->count && app->worker_run; i++) {
        furi_mutex_acquire(app->mutex, FuriWaitForever);
        app->note_index = i;
        furi_mutex_release(app->mutex);
        view_port_update(app->view_port);

        uint32_t ms = app->song->ms[i];
        uint32_t on = ms * 9 / 10;
        if(app->song->freq[i] > 0.0f) {
            furi_hal_speaker_start(app->song->freq[i], VOLUME);
            notification_message(app->notif, &sequence_blink_cyan_10);
        }
        sleep_while_running(app, on);
        furi_hal_speaker_stop();
        sleep_while_running(app, ms - on);
    }
    furi_hal_speaker_stop();
    furi_hal_speaker_release();

    furi_mutex_acquire(app->mutex, FuriWaitForever);
    app->song_done = true;
    furi_mutex_release(app->mutex);
    view_port_update(app->view_port);
}

static int32_t play_worker(void* ctx) {
    NfcCartApp* app = ctx;
    MfUltralightData* data = mf_ultralight_alloc();
    uint8_t* area = malloc(AREA_MAX);
    char* text = malloc(TEXT_MAX);

    while(app->worker_run) {
        MfUltralightError err = mf_ultralight_poller_sync_read_card(app->nfc, data);
        if(!app->worker_run) break;
        if(err != MfUltralightErrorNone) {
            furi_delay_ms(150);
            continue;
        }

        uint16_t end = user_end_page(data->type, data->pages_total);
        if(end == 0) {
            show_message(app, "Not a cartridge", "This tag type is not\nsupported (use NTAG21x).");
            break;
        }
        size_t n = extract_area(data, end, area);

        if(cart_ndef_find_text(area, n, text, TEXT_MAX) &&
           cart_song_parse_rtttl(text, app->song)) {
            notification_message(app->notif, &sequence_success);
            furi_mutex_acquire(app->mutex, FuriWaitForever);
            app->note_index = 0;
            app->song_done = false;
            app->screen = ScreenPlaying;
            furi_mutex_release(app->mutex);
            view_port_update(app->view_port);
            furi_delay_ms(300);
            play_song(app);
        } else if(cart_ndef_is_empty(area, n)) {
            notification_message(app->notif, &sequence_error);
            show_message(app, "Blank sticker", "Nothing on it yet.\nUse Burn cartridge.");
        } else {
            notification_message(app->notif, &sequence_error);
            show_message(app, "Not a cartridge", "This sticker holds other\ndata, not a song.");
        }
        break;
    }

    free(text);
    free(area);
    mf_ultralight_free(data);
    return 0;
}

static int32_t replay_worker(void* ctx) {
    NfcCartApp* app = ctx;
    furi_mutex_acquire(app->mutex, FuriWaitForever);
    app->note_index = 0;
    app->song_done = false;
    furi_mutex_release(app->mutex);
    play_song(app);
    return 0;
}

static bool write_page(NfcCartApp* app, uint16_t page, const uint8_t* bytes) {
    MfUltralightPage pg;
    memcpy(pg.data, bytes, 4);
    for(int attempt = 0; attempt < 3; attempt++) {
        if(mf_ultralight_poller_sync_write_page(app->nfc, page, &pg) == MfUltralightErrorNone)
            return true;
        furi_delay_ms(30);
    }
    return false;
}

static int32_t burn_worker(void* ctx) {
    NfcCartApp* app = ctx;
    MfUltralightData* data = mf_ultralight_alloc();
    uint8_t* msg = malloc(AREA_MAX);
    uint8_t* check = malloc(AREA_MAX);
    char body[160];

    while(app->worker_run) {
        MfUltralightError err = mf_ultralight_poller_sync_read_card(app->nfc, data);
        if(!app->worker_run) break;
        if(err != MfUltralightErrorNone) {
            furi_delay_ms(150);
            continue;
        }

        /* ---- validate the sticker ---- */
        uint16_t end = user_end_page(data->type, data->pages_total);
        if(end == 0) {
            show_message(app, "Can't burn", "Unsupported tag type.\nUse NTAG213/215/216.");
            break;
        }
        if(data->pages_read <= end) {
            show_message(app, "Can't burn", "Sticker is password-\nprotected or unreadable.");
            break;
        }
        const uint8_t* lock = data->page[2].data;
        bool locked = lock[2] || lock[3];
        if(is_ntag21x(data->type)) {
            const uint8_t* dyn = data->page[end + 1].data;
            locked = locked || dyn[0] || dyn[1] || dyn[2];
        }
        if(locked) {
            show_message(app, "Can't burn", "This sticker has lock\nbits set (read-only).");
            break;
        }
        const uint8_t* cc = data->page[3].data;
        bool cc_blank = !cc[0] && !cc[1] && !cc[2] && !cc[3];
        if(!cc_blank && (cc[0] != 0xE1 || cc[3] != 0x00)) {
            show_message(app, "Can't burn", "Sticker is read-only or\nnot NDEF formatted.");
            break;
        }

        size_t capacity = (size_t)(end - 3) * 4;
        size_t need = cart_ndef_text_size(app->burn_len);
        if(need > capacity) {
            snprintf(
                body,
                sizeof(body),
                "Song needs %u bytes,\nsticker holds %u.",
                (unsigned)need,
                (unsigned)capacity);
            show_message(app, "Too big", body);
            break;
        }
        size_t len = cart_ndef_build_text(app->burn_text, app->burn_len, msg, AREA_MAX);
        while(len % 4)
            msg[len++] = 0x00;
        uint16_t pages = (uint16_t)(len / 4);

        furi_mutex_acquire(app->mutex, FuriWaitForever);
        app->burn_progress = 0;
        app->burn_total = pages;
        app->screen = ScreenBurning;
        furi_mutex_release(app->mutex);
        view_port_update(app->view_port);

        /* ---- write ---- */
        bool ok = true;
        if(cc_blank) {
            size_t cc_size = data->type == MfUltralightTypeNTAG216 ? 0x6D : capacity / 8;
            uint8_t new_cc[4] = {0xE1, 0x10, (uint8_t)cc_size, 0x00};
            ok = write_page(app, 3, new_cc);
        }
        /* Page 4 first with an empty NDEF length, so a torn write reads as blank. */
        uint8_t first[4];
        memcpy(first, msg, 4);
        if(msg[1] == 0xFF) {
            first[2] = 0;
            first[3] = 0;
        } else {
            first[1] = 0;
        }
        ok = ok && write_page(app, 4, first);
        for(uint16_t i = 1; ok && i < pages && app->worker_run; i++) {
            ok = write_page(app, 4 + i, &msg[i * 4]);
            furi_mutex_acquire(app->mutex, FuriWaitForever);
            app->burn_progress = i;
            furi_mutex_release(app->mutex);
            view_port_update(app->view_port);
        }
        ok = ok && app->worker_run && write_page(app, 4, msg);
        if(!ok) {
            notification_message(app->notif, &sequence_error);
            show_message(app, "Burn failed", "Sticker moved away.\nHold it still, try again.");
            break;
        }

        /* ---- verify ---- */
        bool verified = false;
        for(int attempt = 0; attempt < 3 && !verified; attempt++) {
            if(mf_ultralight_poller_sync_read_card(app->nfc, data) == MfUltralightErrorNone) {
                size_t n = extract_area(data, end, check);
                verified = n >= len && memcmp(check, msg, len) == 0;
            }
        }
        if(verified) {
            notification_message(app->notif, &sequence_success);
            snprintf(
                body,
                sizeof(body),
                "%s\nUsed %u of %u bytes.\nTap it in Play to hear it.",
                app->burn_title,
                (unsigned)need,
                (unsigned)capacity);
            show_message(app, "Cartridge burned!", body);
        } else {
            notification_message(app->notif, &sequence_error);
            show_message(app, "Check failed", "Written, but read-back\ndid not match. Retry.");
        }
        break;
    }

    free(check);
    free(msg);
    mf_ultralight_free(data);
    return 0;
}

static void start_worker(NfcCartApp* app, FuriThreadCallback cb) {
    app->worker_run = true;
    app->worker = furi_thread_alloc_ex("NfcCartWorker", WORKER_STACK, cb, app);
    furi_thread_start(app->worker);
}

static void stop_worker(NfcCartApp* app) {
    if(!app->worker) return;
    app->worker_run = false;
    furi_thread_join(app->worker);
    furi_thread_free(app->worker);
    app->worker = NULL;
}

/* ---------- burn file loading ---------- */

static bool load_song_file(NfcCartApp* app, const char* path) {
    Storage* storage = furi_record_open(RECORD_STORAGE);
    File* file = storage_file_alloc(storage);
    char* raw = malloc(TEXT_MAX * 2);
    bool ok = false;
    FuriString* rtttl = furi_string_alloc();
    FuriString* name = furi_string_alloc();

    do {
        if(!storage_file_open(file, path, FSAM_READ, FSOM_OPEN_EXISTING)) {
            show_message(app, "Can't open", "Could not open that file.");
            break;
        }
        size_t n = storage_file_read(file, raw, TEXT_MAX * 2 - 1);
        raw[n] = '\0';
        if(!storage_file_eof(file)) {
            show_message(app, "Too big", "That file is larger than\nany sticker can hold.");
            break;
        }

        path_extract_filename_no_ext(path, name);
        if(strncmp(raw, "Filetype: Flipper Music Format", 30) == 0) {
            if(!cart_song_fmf_to_rtttl(raw, furi_string_get_cstr(name), rtttl)) {
                show_message(app, "Bad file", "Could not read that\nFlipper Music file.");
                break;
            }
        } else {
            cart_song_compact_rtttl(raw, rtttl);
        }

        if(!cart_song_parse_rtttl(furi_string_get_cstr(rtttl), app->song)) {
            show_message(app, "Bad file", "Not a valid RTTTL or\nFMF song.");
            break;
        }
        size_t len = furi_string_size(rtttl);
        if(len >= TEXT_MAX) {
            show_message(app, "Too big", "That song is larger than\nany sticker can hold.");
            break;
        }
        free(app->burn_text);
        app->burn_text = strdup(furi_string_get_cstr(rtttl));
        app->burn_len = len;
        strlcpy(app->burn_title, app->song->title, sizeof(app->burn_title));
        ok = true;
    } while(false);

    furi_string_free(name);
    furi_string_free(rtttl);
    free(raw);
    storage_file_close(file);
    storage_file_free(file);
    furi_record_close(RECORD_STORAGE);
    return ok;
}

static void begin_burn(NfcCartApp* app) {
    Storage* storage = furi_record_open(RECORD_STORAGE);
    storage_simply_mkdir(storage, CART_DIR);
    furi_record_close(RECORD_STORAGE);

    FuriString* path = furi_string_alloc_set(CART_DIR);
    DialogsFileBrowserOptions opts;
    dialog_file_browser_set_basic_options(&opts, "*", NULL);
    opts.base_path = CART_DIR;
    opts.hide_ext = false;

    if(dialog_file_browser_show(app->dialogs, path, path, &opts)) {
        if(load_song_file(app, furi_string_get_cstr(path))) {
            set_screen(app, ScreenBurnWait);
            start_worker(app, burn_worker);
        }
    }
    furi_string_free(path);
}

/* ---------- drawing ---------- */

static void draw_header(Canvas* canvas, const char* title) {
    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str_aligned(canvas, 64, 1, AlignCenter, AlignTop, title);
    canvas_draw_line(canvas, 0, 12, 127, 12);
    canvas_set_font(canvas, FontSecondary);
}

static void draw_cartridge(Canvas* canvas, int x, int y) {
    /* a little cartridge: 18x20 */
    canvas_draw_frame(canvas, x, y, 18, 20);
    canvas_draw_box(canvas, x + 3, y + 3, 12, 8);
    for(int i = 0; i < 4; i++)
        canvas_draw_box(canvas, x + 3 + i * 3, y + 16, 2, 4);
}

static void draw_callback(Canvas* canvas, void* ctx) {
    NfcCartApp* app = ctx;
    furi_mutex_acquire(app->mutex, FuriWaitForever);
    canvas_clear(canvas);
    char buf[48];
    uint8_t dots = (app->tick / 3) % 4;

    switch(app->screen) {
    case ScreenMenu:
        draw_header(canvas, "NFC Cartridges");
        for(uint8_t i = 0; i < MenuCount; i++) {
            int y = 16 + i * 14;
            if(i == app->menu_index) {
                canvas_draw_rbox(canvas, 2, y, 124, 13, 2);
                canvas_set_color(canvas, ColorWhite);
            }
            canvas_draw_str(canvas, 8, y + 10, menu_labels[i]);
            canvas_set_color(canvas, ColorBlack);
        }
        break;

    case ScreenScan:
    case ScreenBurnWait:
        draw_header(canvas, app->screen == ScreenScan ? "Play cartridge" : "Burn cartridge");
        draw_cartridge(canvas, 6, 20);
        if(app->screen == ScreenScan) {
            canvas_draw_str(canvas, 30, 26, "Hold a cartridge to");
            canvas_draw_str(canvas, 30, 36, "the back of Flipper");
        } else {
            snprintf(buf, sizeof(buf), "%.18s", app->burn_title);
            canvas_draw_str(canvas, 30, 26, buf);
            snprintf(
                buf,
                sizeof(buf),
                "%u bytes. Hold a",
                (unsigned)cart_ndef_text_size(app->burn_len));
            canvas_draw_str(canvas, 30, 36, buf);
            canvas_draw_str(canvas, 30, 46, "blank sticker to back");
        }
        snprintf(buf, sizeof(buf), "Waiting%.*s", dots, "...");
        canvas_draw_str(canvas, 30, 58, buf);
        break;

    case ScreenPlaying: {
        draw_header(canvas, app->song->title[0] ? app->song->title : "Cartridge");
        draw_cartridge(canvas, 6, 18);
        uint16_t total = app->song->count;
        uint16_t idx = app->song_done ? total : app->note_index + 1;
        snprintf(buf, sizeof(buf), app->song_done ? "Done: %u notes" : "Note %u / %u", idx, total);
        canvas_draw_str(canvas, 30, 26, buf);
        elements_progress_bar(canvas, 30, 31, 94, total ? (float)idx / (float)total : 0.0f);
        if(app->song_done) {
            elements_button_center(canvas, "Again");
        } else {
            /* bouncing note */
            int bounce = (app->note_index % 2) ? 0 : 3;
            canvas_draw_disc(canvas, 74, 50 + bounce, 3);
            canvas_draw_line(canvas, 77, 50 + bounce, 77, 41 + bounce);
            canvas_draw_line(canvas, 77, 41 + bounce, 81, 44 + bounce);
        }
        break;
    }

    case ScreenBurning:
        draw_header(canvas, "Burning...");
        draw_cartridge(canvas, 6, 20);
        canvas_draw_str(canvas, 30, 26, "Keep the sticker still");
        snprintf(buf, sizeof(buf), "Page %u / %u", app->burn_progress + 1, app->burn_total);
        canvas_draw_str(canvas, 30, 38, buf);
        elements_progress_bar(
            canvas,
            30,
            42,
            94,
            app->burn_total ? (float)(app->burn_progress + 1) / (float)app->burn_total : 0.0f);
        break;

    case ScreenMessage:
        draw_header(canvas, app->msg_title);
        elements_multiline_text_aligned(canvas, 64, 16, AlignCenter, AlignTop, app->msg_body);
        elements_button_center(canvas, "OK");
        break;

    case ScreenAbout:
        draw_header(canvas, "About");
        elements_multiline_text_aligned(
            canvas,
            64,
            15,
            AlignCenter,
            AlignTop,
            "The song lives ON the\nsticker, not on the SD.\nPut .txt/.fmf songs in\napps_data/nfc_cart");
        break;
    }
    furi_mutex_release(app->mutex);
}

static void input_callback(InputEvent* event, void* ctx) {
    NfcCartApp* app = ctx;
    furi_message_queue_put(app->input_queue, event, FuriWaitForever);
}

/* ---------- main ---------- */

int32_t nfc_cart_app(void* p) {
    UNUSED(p);
    NfcCartApp* app = malloc(sizeof(NfcCartApp));
    memset(app, 0, sizeof(NfcCartApp));
    app->mutex = furi_mutex_alloc(FuriMutexTypeNormal);
    app->input_queue = furi_message_queue_alloc(8, sizeof(InputEvent));
    app->song = malloc(sizeof(CartSong));
    app->song->count = 0;
    app->song->title[0] = '\0';
    app->nfc = nfc_alloc();
    app->notif = furi_record_open(RECORD_NOTIFICATION);
    app->dialogs = furi_record_open(RECORD_DIALOGS);

    app->view_port = view_port_alloc();
    view_port_draw_callback_set(app->view_port, draw_callback, app);
    view_port_input_callback_set(app->view_port, input_callback, app);
    app->gui = furi_record_open(RECORD_GUI);
    gui_add_view_port(app->gui, app->view_port, GuiLayerFullscreen);

    bool running = true;
    InputEvent ev;
    while(running) {
        if(furi_message_queue_get(app->input_queue, &ev, 100) != FuriStatusOk) {
            app->tick++;
            /* a finished worker leaves its result on screen; reap it */
            if(app->worker && furi_thread_get_state(app->worker) == FuriThreadStateStopped) {
                furi_thread_join(app->worker);
                furi_thread_free(app->worker);
                app->worker = NULL;
            }
            view_port_update(app->view_port);
            continue;
        }
        if(ev.type != InputTypeShort && ev.type != InputTypeRepeat) continue;

        Screen screen = app->screen;
        if(screen == ScreenMenu) {
            if(ev.key == InputKeyUp)
                app->menu_index = (app->menu_index + MenuCount - 1) % MenuCount;
            else if(ev.key == InputKeyDown)
                app->menu_index = (app->menu_index + 1) % MenuCount;
            else if(ev.key == InputKeyBack)
                running = false;
            else if(ev.key == InputKeyOk) {
                if(app->menu_index == MenuPlay) {
                    set_screen(app, ScreenScan);
                    start_worker(app, play_worker);
                } else if(app->menu_index == MenuBurn) {
                    begin_burn(app);
                } else {
                    set_screen(app, ScreenAbout);
                }
            }
        } else if(screen == ScreenPlaying && ev.key == InputKeyOk && app->song_done) {
            stop_worker(app);
            start_worker(app, replay_worker);
        } else if(ev.key == InputKeyBack || (screen == ScreenMessage && ev.key == InputKeyOk) ||
                  (screen == ScreenAbout && ev.key == InputKeyOk)) {
            if(screen == ScreenBurning) continue; /* never abandon a half-written sticker */
            stop_worker(app);
            set_screen(app, ScreenMenu);
        }
        view_port_update(app->view_port);
    }

    stop_worker(app);
    if(furi_hal_speaker_is_mine()) furi_hal_speaker_release();
    gui_remove_view_port(app->gui, app->view_port);
    view_port_free(app->view_port);
    furi_record_close(RECORD_GUI);
    furi_record_close(RECORD_DIALOGS);
    furi_record_close(RECORD_NOTIFICATION);
    nfc_free(app->nfc);
    free(app->burn_text);
    free(app->song);
    furi_message_queue_free(app->input_queue);
    furi_mutex_free(app->mutex);
    free(app);
    return 0;
}
