"""
Live MAVLink (T12): receive from UDP / TCP / serial and RECORD to a .tlog file.

Nothing here parses signals: every packet is written as a .tlog record (8-byte big-endian
receive time in microseconds + the raw MAVLink frame, as MAVProxy / QGC write them), and the app
opens that file and follows it with the existing live mode (tlog_loader.append_tlog). One code
path for live and recorded data, and the session leaves a real log behind.

Read-only by default: nothing is sent to the vehicle. With request=True the receiver behaves like
a minimal ground station - a heartbeat once a second and one request for all data streams - for
links where the autopilot only talks once a ground station asks (ArduPilot SITL on TCP 5760,
some serial radios).
"""

import logging
import os
import struct
import threading
import time
from typing import List, Optional
from svcore.extras import missing

log = logging.getLogger("signalviewer").getChild(__name__)

PRESETS = ("udpin:127.0.0.1:14550", "tcp:127.0.0.1:5760", "udpin:0.0.0.0:14550")


class MavLiveError(Exception):
    pass


def _connect(conn: str, baud: int):
    # MAVLink 2 parser (reads MAVLink 1 too); pymavlink picks the wire version from this variable
    # when the dialect is set, so it must be there before the connection is made
    os.environ["MAVLINK20"] = "1"
    try:
        from pymavlink import mavutil
    except ImportError as e:                                    # pragma: no cover - a dependency
        raise MavLiveError(missing("Live MAVLink", "mavlink")) from e
    is_serial = not conn.split(":", 1)[0] in ("udp", "udpin", "udpout", "udpbcast", "tcp", "tcpin")
    if is_serial:
        try:
            import serial  # noqa: F401  (pymavlink opens serial ports through pyserial)
        except ImportError as e:
            raise MavLiveError("Serial ports need pyserial: pip install pyserial") from e
    try:
        # robust_parsing: a corrupt byte skips a frame instead of stopping the link
        return mavutil.mavlink_connection(conn, baud=baud, source_system=255, source_component=190,
                                          robust_parsing=True, autoreconnect=True, dialect="ardupilotmega")
    except Exception as e:
        raise MavLiveError(f"Cannot open {conn}: {e}. Check the address / port, or that no other "
                           "program (QGC, Mission Planner) holds it.") from e


class Receiver:
    """One connection, one recording. Thread-safe status for the UI."""

    def __init__(self, conn: str, path: str, baud: int = 57600, request: bool = False, rate_hz: int = 4):
        self.conn_str, self.path, self.baud, self.request, self.rate_hz = conn, path, baud, request, rate_hz
        self.frames = 0
        self.bytes = 0
        self.written = 0                                        # bytes in the file: the UI opens it once > 0
        self.last_rx: Optional[float] = None
        self.last_heartbeat: Optional[float] = None
        self.vehicle: Optional[tuple] = None                    # (system, component) of the first autopilot heartbeat
        self.error: Optional[str] = None
        self.started = time.time()
        self._stop = threading.Event()
        self._rate: List[float] = []                                         # receive times of the last ~2 s, for msg/s
        self._lock = threading.Lock()
        self._conn = _connect(conn, baud)                       # fails here, before the thread: the API reports it
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._file = open(path, "ab", buffering=0)
        self._thread = threading.Thread(target=self._run, name="mavlive", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ loop
    def _run(self):
        pack = struct.Struct(">Q").pack
        pending, flushed = [], time.time()
        next_hb, requested = 0.0, False
        try:
            while not self._stop.is_set():
                now = time.time()
                if self.request and now >= next_hb:
                    self._send_heartbeat()
                    next_hb = now + 1.0
                try:
                    m = self._conn.recv_match(blocking=True, timeout=0.2)
                except Exception as e:                          # link dropped; autoreconnect retries
                    self.error = f"Link problem: {e}"
                    time.sleep(0.5)
                    continue
                if m is None or m.get_type() == "BAD_DATA":
                    pass
                else:
                    buf = m.get_msgbuf()
                    if buf:
                        t = time.time()
                        pending.append(pack(int(t * 1e6)) + bytes(buf))
                        with self._lock:
                            self.frames += 1
                            self.bytes += len(buf) + 8
                            self.last_rx = t
                            self._rate.append(t)
                        self.error = None
                        if m.get_type() == "HEARTBEAT" and getattr(m, "type", None) != 6:   # 6: a ground station
                            self.last_heartbeat = t
                            if self.vehicle is None:
                                self.vehicle = (m.get_srcSystem(), m.get_srcComponent())
                            if self.request and not requested:
                                self._request_streams()
                                requested = True
                # many small writes cost more than the data: write in batches, at most ~5 times a second
                if pending and (len(pending) >= 200 or time.time() - flushed >= 0.2):
                    chunk = b"".join(pending)
                    self._file.write(chunk)
                    self.written += len(chunk)
                    pending, flushed = [], time.time()
        finally:
            if pending:
                chunk = b"".join(pending)
                self._file.write(chunk)
                self.written += len(chunk)
            self._file.close()
            try:
                self._conn.close()
            except Exception:                   # closing a dropped link: nothing left to do
                log.debug("closing the MAVLink connection failed", exc_info=True)

    def _send_heartbeat(self):
        try:
            mav = self._conn.mav
            mav.heartbeat_send(6, 8, 0, 0, 0)                   # MAV_TYPE_GCS, MAV_AUTOPILOT_INVALID
        except Exception:                       # link down: the reader thread reports it
            log.debug("heartbeat not sent", exc_info=True)

    def _request_streams(self):
        try:
            sysid, comp = self.vehicle
            self._conn.mav.request_data_stream_send(sysid, comp, 0, int(self.rate_hz), 1)   # MAV_DATA_STREAM_ALL
        except Exception:                       # link down / no vehicle yet: asked again later
            log.debug("stream request not sent", exc_info=True)

    # ------------------------------------------------------------------ API
    def stop(self):
        self._stop.set()
        self._thread.join(timeout=3)

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def status(self) -> dict:
        now = time.time()
        with self._lock:
            self._rate = [t for t in self._rate if now - t <= 2.0]
            rate = len(self._rate) / 2.0
            return {"running": self.running, "conn": self.conn_str, "path": self.path, "frames": self.frames,
                    "bytes": self.bytes, "written": self.written, "rate": rate, "request": self.request,
                    "sinceData": None if self.last_rx is None else now - self.last_rx,
                    "sinceHeartbeat": None if self.last_heartbeat is None else now - self.last_heartbeat,
                    "vehicle": list(self.vehicle) if self.vehicle else None, "error": self.error}


def serial_ports() -> list:
    """Serial ports on this computer ([{device, description}]); empty without pyserial."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [{"device": p.device, "description": p.description or ""} for p in sorted(list_ports.comports(), key=lambda p: p.device)]


def recording_path(folder: str) -> str:
    """A new file name in the recordings folder: mavlink-YYYYmmdd-HHMMSS.tlog (never overwrites)."""
    base = time.strftime("mavlink-%Y%m%d-%H%M%S")
    path, k = os.path.join(folder, base + ".tlog"), 2
    while os.path.exists(path):
        path, k = os.path.join(folder, f"{base}-{k}.tlog"), k + 1
    return path
