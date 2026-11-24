"""
LINK1 (owner, 2026-11-20: "can the app listen to a UART and parse the variables from there, or listen to UDP; and save
it to a file and show it"): a byte link - a serial port, a UDP port, a TCP connection - received and RECORDED as it
comes, the way Live MAVLink records a .tlog (svcore/mavlive.py): one code path for live and recorded data, and the
session leaves a real recording behind.

The recording (`.svraw`): "SVRAW1\\n", then one record per chunk received - 8-byte big-endian receive time in
microseconds (Unix), 4-byte big-endian length, the bytes as they came. Beside it, `<same name>.svmsg.json`: the
messages' structure (svcore/protocol.py) when one was given - then the file opens as the messages' signals;
without one it opens as one signal of bytes (`byte`), for *Decode as messages…*.

Connections: `udp:0.0.0.0:5600` (listen), `tcp:192.168.1.10:4001` (connect to a device / a serial server),
`tcpin:0.0.0.0:4001` (wait for one to connect), a serial port (`COM5`, `/dev/ttyUSB0`, with its baud; pyserial).
Nothing is ever sent.
"""
import json
import logging
import os
import socket
import struct
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger("signalviewer").getChild(__name__)

MAGIC = b"SVRAW1\n"
REC = struct.Struct(">QI")
PRESETS = ("udp:0.0.0.0:5600", "tcp:127.0.0.1:4001", "tcpin:0.0.0.0:4001")


class RawLinkError(Exception):
    pass


def _parse(conn: str) -> Tuple[str, str, int]:
    kind, _, rest = conn.partition(":")
    kind = kind.lower()
    if kind in ("udp", "udpin", "tcp", "tcpin"):
        host, _, port = rest.rpartition(":")
        try:
            return kind, host or "0.0.0.0", int(port)
        except ValueError:
            raise RawLinkError(f"{conn}: give the port as a number, e.g. udp:0.0.0.0:5600.") from None
    return "serial", conn, 0


class Receiver:
    """One link, one recording. Thread-safe status for the UI."""

    def __init__(self, conn: str, path: str, baud: int = 115200, structure: Optional[Dict] = None):
        self.conn_str, self.path, self.baud = conn.strip(), path, int(baud)
        self.kind, self.host, self.port = _parse(self.conn_str)
        self.bytes = 0
        self.chunks = 0
        self.written = 0
        self.last_rx: Optional[float] = None
        self.error: Optional[str] = None
        self.peer: Optional[str] = None
        # the receive clock: the wall time at the start plus a high-resolution counter - time.time() alone moves in
        # steps of up to ~16 ms on Windows, and the chunks of one step got one time (their bytes then went back)
        self._wall0, self._perf0 = time.time(), time.perf_counter()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._rate: List[Tuple[float, int]] = []
        self._sock: Any = None
        self._serial: Any = None
        self._server: Any = None
        self._open()                                             # fails here, before the thread: the API reports it
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if structure:
            with open(structure_path(path), "w", encoding="utf-8") as f:
                json.dump(structure, f, indent=1)
        self._file = open(path, "ab", buffering=0)
        if self._file.tell() == 0:
            self._file.write(MAGIC)
        self._thread = threading.Thread(target=self._run, name="rawlink", daemon=True)
        self._thread.start()

    def _open(self):
        try:
            if self.kind in ("udp", "udpin"):
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.host, self.port))
                s.settimeout(0.5)
                self._sock = s
            elif self.kind == "tcp":
                self._sock = socket.create_connection((self.host, self.port), timeout=5)
                self._sock.settimeout(0.5)
                self.peer = f"{self.host}:{self.port}"
            elif self.kind == "tcpin":
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.host, self.port))
                s.listen(1)
                s.settimeout(0.5)
                self._server = s
            else:
                try:
                    import serial
                except ImportError as e:
                    raise RawLinkError("Serial ports need pyserial: pip install pyserial") from e
                self._serial = serial.Serial(self.host, self.baud, timeout=0.2)
        except RawLinkError:
            raise
        except OSError as e:
            raise RawLinkError(f"Cannot open {self.conn_str}: {e}. Check the address / port, or that no other program "
                               "holds it.") from e

    def _read(self) -> bytes:
        if self._serial is not None:
            n = max(1, self._serial.in_waiting)
            return self._serial.read(n)
        if self.kind == "tcpin" and self._sock is None:
            try:
                c, addr = self._server.accept()
            except socket.timeout:
                return b""
            c.settimeout(0.5)
            self._sock, self.peer = c, f"{addr[0]}:{addr[1]}"
        try:
            if self.kind in ("udp", "udpin"):
                data, addr = self._sock.recvfrom(65535)
                self.peer = f"{addr[0]}:{addr[1]}"
                return data
            data = self._sock.recv(65535)
            if not data:                                         # the other side closed: wait for it again
                self._sock.close()
                self._sock = None
                if self.kind == "tcp":
                    time.sleep(1.0)
                    self._sock = socket.create_connection((self.host, self.port), timeout=5)
                    self._sock.settimeout(0.5)
            return data
        except socket.timeout:
            return b""

    def _run(self):
        while not self._stop.is_set():
            try:
                data = self._read()
            except Exception as e:                               # a link that went away: said, and tried again
                self.error = str(e) or e.__class__.__name__
                time.sleep(0.5)
                continue
            if not data:
                continue
            now = self._wall0 + (time.perf_counter() - self._perf0)
            self._file.write(REC.pack(int(now * 1e6), len(data)) + data)
            with self._lock:
                self.error = None
                self.bytes += len(data)
                self.chunks += 1
                self.written = self.bytes
                self.last_rx = now
                self._rate.append((now, len(data)))
        for h in (self._sock, self._server, self._serial):
            try:
                if h is not None:
                    h.close()
            except Exception:
                pass
        self._file.close()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=3)

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def status(self) -> dict:
        now = time.time()
        with self._lock:
            self._rate = [x for x in self._rate if now - x[0] <= 2.0]
            return {"running": self.running, "conn": self.conn_str, "path": self.path, "bytes": self.bytes,
                    "chunks": self.chunks, "written": self.written, "rate": sum(n for _t, n in self._rate) / 2.0,
                    "sinceData": None if self.last_rx is None else now - self.last_rx, "peer": self.peer,
                    "error": self.error}


def structure_path(path: str) -> str:
    return os.path.splitext(path)[0] + ".svmsg.json"


def recording_path(folder: str) -> str:
    base = time.strftime("link-%Y%m%d-%H%M%S")
    path, k = os.path.join(folder, base + ".svraw"), 2
    while os.path.exists(path):
        path, k = os.path.join(folder, f"{base}-{k}.svraw"), k + 1
    return path


def read_svraw(path: str) -> Tuple[np.ndarray, np.ndarray, int]:
    """(time of each byte - its chunk's receive time, s from the first chunk; the bytes; the Unix time of the first
    chunk). A record cut off at the end (still being written) is left for the next read."""
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(MAGIC):
        raise RawLinkError(f"{os.path.basename(path)} is not a Signal Viewer link recording.")
    i = len(MAGIC)
    ts: List[np.ndarray] = []
    bs: List[bytes] = []
    t0 = None
    after = -np.inf                     # the time of the last byte read: a chunk never starts at or before it
    while i + REC.size <= len(data):
        us, n = REC.unpack_from(data, i)
        if i + REC.size + n > len(data):
            break
        chunk = data[i + REC.size: i + REC.size + n]
        t = us / 1e6
        t0 = t if t0 is None else t0
        # the bytes of a chunk at its receive time, a microsecond apart, kept in order: two chunks stamped with one
        # time (a coarse clock - recordings made on Windows before the high-resolution clock) follow each other
        start = max(t - t0, after + 1e-6)
        ts.append(start + np.arange(n) * 1e-6)
        if n:
            after = start + (n - 1) * 1e-6
        bs.append(chunk)
        i += REC.size + n
    if not bs:
        return np.zeros(0), np.zeros(0, dtype=np.uint8), 0
    return np.concatenate(ts), np.frombuffer(b"".join(bs), dtype=np.uint8), int(t0 or 0)


def load_svraw(path: str, name: str):
    """A link recording: by the structure beside it (the messages' signals), else one signal of bytes."""
    from svcore.models import Run, Signal
    from svcore.protocol import parse_binary, parse_text, to_run
    t, b, t0 = read_svraw(path)
    sp = structure_path(path)
    report: Dict = {"bytes": int(len(b)), "start": t0}
    if os.path.isfile(sp) and len(b):
        with open(sp, encoding="utf-8") as f:
            st = json.load(f)
        out = parse_text(b.tobytes().decode("latin-1"), st, t) if st.get("kind") == "text" else parse_binary(t, b, st)
        run = to_run(name, path, out)
        report["structure"] = os.path.basename(sp)
        report["messages"] = out["report"]
    else:
        if not len(b):
            t, b = np.zeros(1), np.zeros(1, dtype=np.uint8)
        run = Run(file_path=path, csv_display_name=name, time=t, signals={"byte": Signal(name="byte", data=b.astype(np.float64))})
        run.compute_metadata()
    run.import_settings = {**(run.import_settings or {}), "format": "svraw"}
    return run, report


def serial_ports() -> list:
    from svcore.mavlive import serial_ports as sp
    return sp()
