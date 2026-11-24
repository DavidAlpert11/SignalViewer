"""LINK1: a byte link (UDP / TCP) received and recorded to a .svraw with its structure beside it; the file opens as
the messages' signals (or as bytes without a structure); the route starts / stops it."""
import json
import os
import socket
import threading
import time

import numpy as np
import pytest

from svcore import rawlink

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def _sensor_bytes(n_frames=300):
    from svcore.example_data.make_serial_link import sensor
    data = bytes(b for _t, b in sensor())
    return data


def _free_port(kind=socket.SOCK_DGRAM):
    s = socket.socket(socket.AF_INET, kind)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        time.sleep(0.05)
    return cond()


def test_chunks_with_one_time_stay_in_order(tmp_path):
    """A coarse clock (Windows' time.time() moves in steps of ~16 ms) stamped several chunks with one time: read
    back, their bytes still follow each other - every time later than the one before."""
    path = str(tmp_path / "coarse.svraw")
    with open(path, "wb") as f:
        f.write(rawlink.MAGIC)
        for k, chunk in enumerate([b"\x01" * 200, b"\x02" * 200, b"\x03" * 50, b"\x04" * 10]):
            us = 1_700_000_000_000_000 + (0 if k < 3 else 16_000)       # three chunks in one tick, then the next tick
            f.write(rawlink.REC.pack(us, len(chunk)) + chunk)
    t, b, t0 = rawlink.read_svraw(path)
    assert len(t) == len(b) == 460 and np.all(np.diff(t) > 0)
    assert t[-10] == pytest.approx(0.016, abs=1e-6)                            # a later tick keeps its own time


def test_udp_link_recorded_and_decoded_by_its_structure(tmp_path):
    st = json.load(open(os.path.join(EX, "serial_link", "sensor.svmsg.json"), encoding="utf-8"))
    port = _free_port()
    path = str(tmp_path / "link.svraw")
    rx = rawlink.Receiver(f"udp:127.0.0.1:{port}", path, structure=st)
    data = _sensor_bytes()[:20000]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for i in range(0, len(data), 200):                      # packets cut anywhere - a message across two packets too
        s.sendto(data[i:i + 200], ("127.0.0.1", port))
        time.sleep(0.001)
    assert _wait(lambda: rx.status()["bytes"] == len(data))
    rx.stop()
    assert not rx.running and os.path.isfile(rawlink.structure_path(path))
    t, b, t0 = rawlink.read_svraw(path)
    assert b.tobytes() == data and np.all(np.diff(t) > 0) and t0 > 1e9
    run, rep = rawlink.load_svraw(path, "link.svraw")
    assert rep["messages"]["messages"]["IMU"] > 700 and "IMU.az [g]" in run.signals
    assert np.all(run.signals["IMU.az [g]"].data < -0.96)


def test_tcp_link_without_structure_is_bytes(tmp_path):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    data = bytes(range(256)) * 4

    def serve():
        c, _ = srv.accept()
        c.sendall(data)
        time.sleep(0.3)
        c.close()
    th = threading.Thread(target=serve, daemon=True)
    th.start()
    path = str(tmp_path / "t.svraw")
    rx = rawlink.Receiver(f"tcp:127.0.0.1:{port}", path)
    assert _wait(lambda: rx.status()["bytes"] == len(data))
    rx.stop()
    run, rep = rawlink.load_svraw(path, "t.svraw")
    assert list(run.signals) == ["byte"] and len(run.signals["byte"].data) == len(data) and rep["bytes"] == len(data)


def test_route_and_store(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    c = TestClient(app)
    port = _free_port()
    r = c.post("/api/link/start", json={"conn": f"udp:127.0.0.1:{port}", "folder": str(tmp_path),
                                         "structure": {"kind": "text", "start": "$", "sep": ",", "checksum": "nmea",
                                                       "messages": [{"id": "GGA", "name": "GGA", "fields": [{"name": "alt", "index": 9}]}]}})
    assert r.status_code == 200 and r.json()["running"]
    assert c.post("/api/link/start", json={"conn": f"udp:127.0.0.1:{port}"}).status_code == 409
    lines = open(os.path.join(EX, "gps_nmea", "receiver.nmea"), "rb").read().splitlines(keepends=True)[:60]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for ln in lines:
        s.sendto(ln, ("127.0.0.1", port))
    assert _wait(lambda: c.get("/api/link/status").json()["bytes"] == sum(len(x) for x in lines))
    path = c.post("/api/link/stop").json()["path"]
    lr = store.open_file(path)
    assert "GGA.alt" in lr.run.signals and len(lr.run.signals["GGA.alt"].data) == 21          # the GGA sentences among the 60 lines
    bad = c.post("/api/link/start", json={"conn": "udp:127.0.0.1:x"})
    assert bad.status_code == 400 and "port" in bad.json()["detail"]
