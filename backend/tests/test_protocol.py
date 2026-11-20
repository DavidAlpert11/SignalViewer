"""MSG2: a message structure -> a recording. Known answers: the serial link demo's values (written by formulas in
make_serial_link: LSB / MSB first, signed, 32-bit, float, bits, scale), the NMEA file (positions, the lost fix, a bad
checksum, a maker's own sentence), the proposals (binary fields guessed, NMEA recognised), the .nmea reader."""
import json
import math
import os

import numpy as np
import pytest

from svcore import protocol as P
from svcore.example_data import make_gps_nmea as gn
from svcore.example_data import make_serial_link as sl

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def _link(col):
    d = np.genfromtxt(os.path.join(EX, "serial_link", "link_tx_rx.csv"), delimiter=",", names=True)
    return [(d["time"], d[col])]


def _struct(name):
    return json.load(open(os.path.join(EX, "serial_link", name), encoding="utf-8"))


def test_binary_fields_lsb_msb_signed_bits_float():
    tx = P.parse(_link("tx_byte"), _struct("link_tx.svmsg.json"))
    assert tx["report"]["messages"] == {"HELLO": 2, "CONFIG": 2, "SETPOINT": 1495, "COMMAND": 299, "HEARTBEAT": 29}
    t, roll = tx["signals"]["SETPOINT.roll_cmd"]
    want = np.array([round(sl.roll_cmd(x - 0.0003) * 100) / 100 for x in t])        # the frame's first byte: t + 0.3 ms
    assert np.allclose(roll, want, atol=0.011)                                      # i16 LSB first, x0.01, negative too
    assert roll.min() < -19.9 and roll.max() > 19.9
    _t, armed = tx["signals"]["SETPOINT.armed"]
    assert set(np.unique(armed)) == {0.0, 1.0} and armed[0] == 0                    # bit 0 of the flags byte
    _t, param = tx["signals"]["COMMAND.param"]
    assert np.allclose(param[:20], [1.5 * (n % 20) for n in range(20)])             # f32 LSB first
    rx = P.parse(_link("rx_byte"), _struct("link_rx.svmsg.json"))
    _t, alt = rx["signals"]["ATTITUDE.alt"]
    assert 50.0 <= alt.min() < 50.2 and 79.9 < alt.max() <= 80.0                    # i32 LSB first, cm -> m
    _t, yaw = rx["signals"]["ATTITUDE.yaw"]
    assert yaw.min() >= 0 and yaw.max() > 359                                       # u16 MSB first
    _t, temp = rx["signals"]["STATUS.temp"]
    assert temp.min() == 25 and temp.max() == 30                                    # i8
    assert rx["labels"]["STATUS.mode"] == {1: "MANUAL", 2: "AUTO"}
    assert rx["report"]["bad"] == 2                                                 # the two CRC errors left out, counted


def test_suggested_binary_structure_reads_like_the_real_one():
    s = P.suggest(_link("rx_byte"))
    assert (s["header"], s["length"], s["type"], s["checksum"]) == ("EB90", {"offset": 3, "add": 6}, {"offset": 2},
                                                                     {"scheme": "crc16ccitt", "from": 2})
    att = next(m for m in s["messages"] if m["id"] == 0xA0)
    got = [(f["offset"], f["type"], f["endian"]) for f in att["fields"]]
    assert got[3][0] == 10 and got[3][1] in ("i32", "u32") and got[3][2] == "le"       # a positive altitude: either reads
    assert got[:3] + got[4:] == [(4, "i16", "be"), (6, "i16", "be"), (8, "u16", "be"), (14, "i16", "le")]
    tx = P.suggest(_link("tx_byte"))
    sp = next(m for m in tx["messages"] if m["id"] == 0x20)
    assert [(f["offset"], f["type"]) for f in sp["fields"][:3]] == [(4, "i16"), (6, "i16"), (8, "u16")]
    cmd = next(m for m in tx["messages"] if m["id"] == 0x10)
    assert [f["type"] for f in cmd["fields"]] == ["u8", "u8", "f32"] and cmd["fields"][0]["name"] == "counter"
    # what it proposed is a structure the parser takes as it is
    out = P.parse(_link("rx_byte"), s)
    assert out["report"]["messages"]["MSG_A0"] == 1421


def test_nmea_file_and_uart():
    run, rep = P.load_nmea(os.path.join(EX, "gps_nmea", "receiver.nmea"), "receiver.nmea")
    assert rep["messages"] == {"GGA": 899, "RMC": 900, "VTG": 180, "GSA": 180, "GSV": 180}
    assert rep["bad"] == 1 and rep["unknown"] == {"PDEMO": 180}
    lat = run.signals["GGA.lat [deg]"]
    t = lat.time
    want = [gn.track(x)[0] for x in t]
    ok = np.isfinite(lat.data)
    assert np.allclose(lat.data[ok], np.array(want)[ok], atol=2e-6)                 # ddmm.mmmm -> degrees
    assert int((~ok).sum()) == 25                                                    # the fix lost 5 s (5 Hz)
    assert t[0] == 0 and t[-1] == pytest.approx(179.8)                               # time from the sentences' own clock
    st = run.signals["RMC.status"]
    assert set(st.labels.values()) == {"A", "V"}
    d = np.genfromtxt(os.path.join(EX, "gps_nmea", "receiver_uart.csv"), delimiter=",", names=True)
    s = P.suggest([(d["time"], d["rx_byte"])])
    assert s["kind"] == "text" and s["checksum"] == "nmea"
    assert [m["id"] for m in s["messages"]][:2] == ["RMC", "GGA"] or [m["id"] for m in s["messages"]][:2] == ["GGA", "RMC"]
    pd = next(m for m in s["messages"] if m["id"] == "PDEMO")
    assert [(f["index"], f["type"]) for f in pd["fields"]] == [(1, "number"), (2, "number"), (3, "number")]
    out = P.parse([(d["time"], d["rx_byte"])], s)
    assert out["report"]["messages"]["PDEMO"] == 180 and out["report"]["bad"] == 1
    t2, temp = out["signals"]["PDEMO.f1"]
    assert temp[0] == pytest.approx(31.0) and temp[-1] == pytest.approx(31 + 179 / 60, abs=0.05)


def test_structure_mistakes_said():
    with pytest.raises(P.ProtocolError, match="no messages"):
        P.check({"kind": "binary", "messages": []})
    with pytest.raises(P.ProtocolError, match="i17"):
        P.check({"kind": "binary", "header": "AA55", "size": 8, "messages": [{"id": 1, "name": "A", "fields": [{"name": "x", "offset": 2, "type": "i17"}]}]})
    with pytest.raises(P.ProtocolError, match="how long"):
        P.check({"kind": "binary", "header": "AA55", "messages": [{"id": 1, "name": "A", "fields": []}]})
    with pytest.raises(P.ProtocolError, match="No message matched"):
        P.to_run("x", "python:x", P.parse(_link("tx_byte"), {"kind": "binary", "header": "1234", "size": 8,
                                                             "messages": [{"id": 0, "name": "A", "fields": [{"name": "v", "offset": 2}]}]}))


def test_nmea_checksum_and_hemispheres():
    assert P.nmea_ok("$GPGGA,120000.00,3204.8000,N,03446.8000,E,1,09,0.9,35.0,M,18.2,M,,*52") is True
    assert P.nmea_ok("$GPGGA,120000.00,3204.8000,N,03446.8000,E,1,09,0.9,35.0,M,18.2,M,,*53") is False
    assert P._num("3204.8000", "lat", "S") == pytest.approx(-32.08)
    assert P._num("03446.8000", "lon", "W") == pytest.approx(-(34 + 46.8 / 60))
    assert P._num("235959.50", "hhmmss") == pytest.approx(86399.5)
    assert math.isnan(P._num("", "number"))


def test_demo_files_are_what_the_generators_write(tmp_path):
    gn.main(str(tmp_path / "g"))
    sl.main(str(tmp_path / "s"))
    for sub, f in (("g", "receiver.nmea"), ("g", "receiver_uart.csv"), ("s", "link_tx.svmsg.json"), ("s", "link_rx.svmsg.json")):
        folder = {"g": "gps_nmea", "s": "serial_link"}[sub]
        assert (tmp_path / sub / f).read_bytes() == open(os.path.join(EX, folder, f), "rb").read()


def test_parse_route_makes_a_recording_with_the_given_id():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    c = TestClient(app)
    lr = store.open_file(os.path.join(EX, "serial_link", "link_tx_rx.csv"))
    r = c.post("/api/messages/parse", json={"sources": [f"{lr.id}/tx_byte"], "params": {}, "structure": _struct("link_tx.svmsg.json"),
                                            "name": "tx - messages", "id": "msgtest1"}).json()
    assert r["run"] == "msgtest1" and "msgtest1/SETPOINT.roll_cmd [deg]" in r["signals"]
    s = c.post("/api/messages/suggest", json={"sources": [f"{lr.id}/rx_byte"], "params": {}}).json()["structure"]
    assert s["header"] == "EB90"
    bad = c.post("/api/messages/parse", json={"sources": [f"{lr.id}/tx_byte"], "params": {}, "structure": {"kind": "x"}})
    assert bad.status_code == 400 and "kind" in bad.json()["detail"]
    assert c.get("/api/messages/nmea").json()["structure"]["name"] == "NMEA 0183"
    n = store.open_file(os.path.join(EX, "gps_nmea", "receiver.nmea"))
    assert "GGA.lat [deg]" in n.run.signals


def test_footer_no_length_byte():
    """Owner, 2026-11-20: "a footer" - the sensor board: A5 5A | type | payload | xor8 | 0D 0A, no length byte."""
    d = np.genfromtxt(os.path.join(EX, "serial_link", "sensor_uart.csv"), delimiter=",", names=True)
    sig = [(d["time"], d["sensor_byte"])]
    out = P.parse(sig, _struct("sensor.svmsg.json"))
    assert out["report"]["messages"] == {"IMU": 1999, "BARO": 400, "MAG": 200} and out["report"]["bad"] == 1
    _t, az = out["signals"]["IMU.az"]
    assert -1.031 <= az.min() and az.max() <= -0.969                                # i16 LSB first, x0.001 g
    _t, p_ = out["signals"]["BARO.pressure"]
    assert p_[0] == 101325 and p_[-1] == pytest.approx(101325 - 12 * 19.95 * 10, abs=1)     # u32
    # the footer alone tells where a message ends: the same without the sizes
    s = P.suggest(sig)
    assert (s["header"], s["footer"], s["checksum"], s["length"]) == ("A55A", "0D0A", {"scheme": "xor8", "from": 2}, None)
    assert [(f["offset"], f["type"], f["endian"]) for f in s["messages"][0]["fields"][:5]] == [(3, "i16", "le")] * 1 + [
        (5, "i16", "le"), (7, "i16", "le"), (9, "i16", "le"), (11, "i16", "le")]
    baro = next(m for m in s["messages"] if m["id"] == 2)
    assert [(f["offset"], f["type"]) for f in baro["fields"]] == [(3, "u32"), (7, "i16")] or baro["fields"][0]["type"] in ("u32", "i32")
    st = _struct("sensor.svmsg.json")
    for m in st["messages"]:
        m.pop("size", None)
    assert P.parse(sig, st)["report"]["messages"]["IMU"] == 1999
    with pytest.raises(P.ProtocolError, match="footer"):
        P.check({**st, "footer": "0D0"})


def test_an_icd_layout_is_a_structure_too():
    """The ICD layout (T61) of the sensor board read as a structure: the same packets, the same values."""
    icd = {"name": "Sensor board", "byte_order": "little",
           "header": {"sync": "0xA55A", "size": 3, "id": {"offset": 2, "type": "u8"}},
           "packets": [{"id": 1, "name": "IMU", "size": 12, "fields": [
               {"name": "az", "offset": 4, "type": "i16", "scale": 0.001, "unit": "g"},
               {"name": "mode", "offset": 0, "type": "u8", "enum": {"0": "A"}}]},
               {"id": 3, "name": "MAG", "size": 6, "fields": [{"name": "mx", "offset": 0, "type": "i16", "byte_order": "big", "scale": 0.1}]}]}
    st = P.check(P.from_icd(icd))
    assert st["header"] == "A55A" and st["type"] == {"offset": 2} and st["messages"][0]["size"] == 15
    assert st["messages"][0]["fields"][0] == {"name": "az", "offset": 7, "type": "i16", "endian": "le", "scale": 0.001, "unit": "g"}
    d = np.genfromtxt(os.path.join(EX, "serial_link", "sensor_uart.csv"), delimiter=",", names=True)
    a = P.parse([(d["time"], d["sensor_byte"])], st)
    b = P.parse([(d["time"], d["sensor_byte"])], _struct("sensor.svmsg.json"))
    ta, ya = a["signals"]["IMU.az"]
    tb, yb = b["signals"]["IMU.az"]
    assert len(ta) == len(tb) + 1                           # no checksum in the ICD: the frame hit by noise is kept
    keep = np.isin(ta, tb)
    assert np.allclose(ya[keep], yb)
    assert np.allclose(a["signals"]["MAG.mx"][1], b["signals"]["MAG.mx"][1])
