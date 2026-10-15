"""Live MAVLink (T12): a fake vehicle sends over UDP, the receiver records a .tlog, the app opens
it and live mode reads what is added:  python -m pytest backend/tests/test_mavlink_live.py"""
import os
import socket
import sys
import time

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from pymavlink.dialects.v20 import ardupilotmega as mavlink  # noqa: E402

client = TestClient(app)


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeVehicle:
    """An ArduCopter that sends HEARTBEAT and ATTITUDE to a ground station's UDP port."""

    def __init__(self, port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.05)
        self.dest = ("127.0.0.1", port)
        self.mav = mavlink.MAVLink(None, srcSystem=1, srcComponent=1)
        self.ms = 0
        self.got = []                                   # messages the ground station sent back

    def send(self, n: int):
        for _ in range(n):
            self.ms += 100
            if self.ms % 1000 == 0 or self.ms == 100:
                self.sock.sendto(self.mav.heartbeat_encode(2, 3, 81, 4, 4).pack(self.mav), self.dest)   # quad, ArduPilot, guided
            roll = 0.001 * self.ms
            self.sock.sendto(self.mav.attitude_encode(self.ms, roll, 0.0, 1.0, 0, 0, 0).pack(self.mav), self.dest)
            time.sleep(0.002)

    def listen(self, seconds: float):
        parser = mavlink.MAVLink(None)
        end = time.time() + seconds
        while time.time() < end:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                continue
            for m in parser.parse_buffer(data) or []:
                self.got.append(m.get_type())

    def close(self):
        self.sock.close()


def _wait(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture()
def rec(tmp_path):
    yield str(tmp_path)
    client.post("/api/mavlink/stop")
    for rid in list(store.order):
        store.remove(rid)


def test_mavlink_records_and_live_mode_follows(rec):
    port = _free_udp_port()
    r = client.post("/api/mavlink/start", json={"conn": f"udpin:127.0.0.1:{port}", "folder": rec})
    assert r.status_code == 200, r.text
    path = r.json()["path"]
    assert path.startswith(rec) and path.endswith(".tlog")
    again = client.post("/api/mavlink/start", json={"conn": f"udpin:127.0.0.1:{port}", "folder": rec})
    assert again.status_code == 409                                     # one link at a time
    v = FakeVehicle(port)
    try:
        v.send(20)
        assert _wait(lambda: client.get("/api/mavlink/status").json()["frames"] >= 20 and os.path.getsize(path) > 0)
        st = client.get("/api/mavlink/status").json()
        assert st["running"] and st["vehicle"] == [1, 1] and st["sinceHeartbeat"] is not None
        run = client.post("/api/files/open", json={"paths": [path]}).json()["opened"][0]
        names = {s["name"] for s in run["signals"]}
        assert "ATTITUDE.roll [rad]" in names
        n0 = len(store.signal(f"{run['id']}/ATTITUDE.roll [rad]")[0])
        v.send(30)                                                      # live mode reads only what was added
        assert _wait(lambda: run["id"] in store.poll_appends() or
                     len(store.signal(f"{run['id']}/ATTITUDE.roll [rad]")[0]) >= n0 + 30)
        assert len(store.signal(f"{run['id']}/ATTITUDE.roll [rad]")[0]) >= n0 + 30
        st = client.post("/api/mavlink/stop").json()
        assert not st["running"] and st["frames"] >= 50
        # the recording is a normal .tlog: it reopens with everything that came in
        store.remove(run["id"])
        again = client.post("/api/files/open", json={"paths": [path]}).json()["opened"][0]
        t, y = store.signal(f"{again['id']}/ATTITUDE.roll [rad]")
        assert len(t) == 50 and abs(float(max(y)) - 5.0) < 1e-3          # every message, the last one included
    finally:
        v.close()


def test_mavlink_read_only_unless_asked(rec):
    """By default nothing is sent to the vehicle; with request=True it gets a ground station
    heartbeat and one request for its data streams."""
    for request in (False, True):
        port = _free_udp_port()
        r = client.post("/api/mavlink/start", json={"conn": f"udpin:127.0.0.1:{port}", "folder": rec, "request": request})
        assert r.status_code == 200, r.text
        v = FakeVehicle(port)
        try:
            v.send(3)
            v.listen(1.5)
            if request:
                assert "HEARTBEAT" in v.got and "REQUEST_DATA_STREAM" in v.got
            else:
                assert v.got == []
        finally:
            client.post("/api/mavlink/stop")
            v.close()


def test_mavlink_errors_say_what_to_do(rec):
    r = client.post("/api/mavlink/start", json={"conn": "  ", "folder": rec})
    assert r.status_code == 400 and "udpin:127.0.0.1:14550" in r.json()["detail"]
    r = client.post("/api/mavlink/start", json={"conn": "udpin:256.1.1.1:14550", "folder": rec})
    assert r.status_code == 400 and "Cannot open" in r.json()["detail"]
    assert client.get("/api/mavlink/status").json()["running"] is False
    p = client.get("/api/mavlink/ports").json()
    assert "udpin:127.0.0.1:14550" in p["presets"] and isinstance(p["ports"], list) and p["folder"]
