"""A small Flipper Zero RPC client over USB serial: device info, storage listing, the screen stream, button input
and app start/exit. Uses the official flipperzero-protobuf definitions (compiled into ./pb).

Frames arrive as 1024 bytes in the u8g2 page layout (128 x 64, 8 pages of 128 bytes, LSB = top pixel of the page).
"""
import sys, time, threading, queue
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pb"))
import serial  # noqa: E402
import flipper_pb2 as pb  # noqa: E402
import gui_pb2, storage_pb2, system_pb2, application_pb2  # noqa: E402,F401

PORT_GLOB = "/dev/cu.usbmodemflip_*"


def find_port():
    import glob
    ports = glob.glob(PORT_GLOB)
    if not ports:
        raise SystemExit("no Flipper on USB")
    return ports[0]


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


class Flipper:
    def __init__(self, port=None):
        self.ser = serial.Serial(port or find_port(), 230400, timeout=0.2)
        self.cid = 0
        self.responses = queue.Queue()
        self.frames = []          # (t, bytes, orientation)
        self.on_frame = None
        self._enter_rpc()
        self._stop = False
        self.rx = threading.Thread(target=self._reader, daemon=True)
        self.rx.start()

    # the CLI prompt is ">: "; "start_rpc_session" switches the port to protobuf framing
    def _enter_rpc(self):
        self.ser.reset_input_buffer()
        self.ser.write(b"\r")
        self._read_until(b">: ", 3)
        self.ser.write(b"start_rpc_session\r")
        self._read_until(b"start_rpc_session\r\n", 3)

    def _read_until(self, token, timeout):
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            buf += self.ser.read(256)
            if token in buf:
                return buf
        return buf

    def _read_exact(self, n):
        buf = b""
        while len(buf) < n and not self._stop:
            buf += self.ser.read(n - len(buf))
        return buf

    def _read_varint(self):
        shift = res = 0
        while not self._stop:
            b = self.ser.read(1)
            if not b:
                continue
            b = b[0]
            res |= (b & 0x7F) << shift
            if not b & 0x80:
                return res
            shift += 7

    def _reader(self):
        while not self._stop:
            n = self._read_varint()
            if n is None:
                return
            data = self._read_exact(n)
            m = pb.Main()
            m.ParseFromString(data)
            if m.WhichOneof("content") == "gui_screen_frame":
                f = (time.time(), bytes(m.gui_screen_frame.data), m.gui_screen_frame.orientation)
                self.frames.append(f)
                if self.on_frame:
                    self.on_frame(*f)
            else:
                self.responses.put(m)

    def send(self, **content):
        self.cid += 1
        m = pb.Main(command_id=self.cid, **content)
        data = m.SerializeToString()
        self.ser.write(varint(len(data)) + data)
        return self.cid

    def call(self, timeout=5, **content):
        cid = self.send(**content)
        out = []
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                m = self.responses.get(timeout=0.2)
            except queue.Empty:
                continue
            if m.command_id != cid:
                continue
            out.append(m)
            if not m.has_next:
                break
        return out

    def device_info(self):
        return {m.system_device_info_response.key: m.system_device_info_response.value
                for m in self.call(system_device_info_request=system_pb2.DeviceInfoRequest())}

    def ls(self, path):
        files = []
        for m in self.call(storage_list_request=storage_pb2.ListRequest(path=path)):
            for f in m.storage_list_response.file:
                files.append((f.name, "dir" if f.type == storage_pb2.File.DIR else f.size))
        return files

    def stream(self, on=True):
        if on:
            return self.call(gui_start_screen_stream_request=gui_pb2.StartScreenStreamRequest())
        return self.call(gui_stop_screen_stream_request=gui_pb2.StopScreenStreamRequest())

    def press(self, key, kind="SHORT"):
        """One button press as the hardware makes it: PRESS, then SHORT (or LONG), then RELEASE."""
        k = getattr(gui_pb2, key)
        seq = ["PRESS", kind, "RELEASE"]
        for t in seq:
            self.call(gui_send_input_event_request=gui_pb2.SendInputEventRequest(key=k, type=getattr(gui_pb2, t)))

    def app_start(self, name, args=""):
        return self.call(app_start_request=application_pb2.StartRequest(name=name, args=args))

    def app_exit(self):
        return self.call(app_exit_request=application_pb2.AppExitRequest())

    def close(self):
        try:
            self.call(timeout=1, stop_session=pb.StopSession())
        except Exception:
            pass
        self._stop = True
        time.sleep(0.3)
        self.ser.close()


def frame_to_rows(data, orientation=0):
    """128 x 64 booleans, row-major, from the u8g2 page layout."""
    rows = []
    for y in range(64):
        page, bit = divmod(y, 8)
        rows.append([(data[page * 128 + x] >> bit) & 1 for x in range(128)])
    if orientation == 1:   # horizontal flipped
        rows = [r[::-1] for r in rows[::-1]]
    return rows


def save_png(data, path, orientation=0, scale=1, on=(0, 0, 0), off=(255, 140, 0)):
    import zlib, struct
    rows = frame_to_rows(data, orientation)
    w, h = 128 * scale, 64 * scale
    raw = bytearray()
    for r in rows:
        line = bytearray([0])
        for px in r:
            line += bytes(on if px else off) * scale
        raw += bytes(line) * scale
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)
