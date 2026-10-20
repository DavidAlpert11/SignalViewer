"""T40b: CAN logs (candump, Vector ASC, CSV) decoded with our own .dbc reader. Every decoded value
is checked against hand-made frames; when cantools is installed (not a dependency - only a
reference here) the decoder must agree with it on random frames."""
import os
import random

import numpy as np
import pytest

import app.prefs as prefs
from app.store import LoadError, Store
from svcore import dbc

DBC = '''VERSION ""

BO_ 256 Engine: 8 ECU
 SG_ RPM : 0|16@1+ (0.25,0) [0|16383] "rpm" Vector__XXX
 SG_ Temp : 16|8@1- (1,-40) [-168|87] "degC" Vector__XXX
 SG_ Gear : 24|3@1+ (1,0) [0|7] "" Vector__XXX
 SG_ Torque : 39|12@0- (0.5,0) [-1024|1023] "Nm" Vector__XXX

BO_ 2566844926 Battery: 8 BMS
 SG_ Volt : 7|16@0+ (0.01,0) [0|655] "V" Vector__XXX
 SG_ Mux M : 16|4@1+ (1,0) [0|15] "" Vector__XXX
 SG_ Cell0 m0 : 24|16@1+ (0.001,0) [0|65] "V" Vector__XXX
 SG_ Cell1 m1 : 24|16@1+ (0.001,0) [0|65] "V" Vector__XXX

BO_ 512 Aux: 8 ECU
 SG_ Ratio : 0|32@1- (1,0) [0|1] "" Vector__XXX
 SG_ Count : 32|32@1+ (1,0) [0|4294967295] "" Vector__XXX

VAL_ 256 Gear 0 "P" 1 "R" 2 "N" 3 "D" ;
SIG_VALTYPE_ 512 Ratio : 1;
'''


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path / "home"))
    return tmp_path


def engine(rpm, temp, gear, torque):
    raw = int(rpm / 0.25) | ((temp + 40) & 0xFF) << 16 | gear << 24
    b = bytearray(raw.to_bytes(8, "little"))
    tq = int(torque / 0.5) & 0xFFF                      # Motorola, MSB at bit 39 = byte 4 bit 7
    b[4] = tq >> 4
    b[5] = (b[5] & 0x0F) | ((tq & 0xF) << 4)
    return bytes(b)


def test_dbc_parse_and_decode_by_hand(tmp_path):
    msgs = dbc.parse_dbc(DBC)
    assert set(m["name"] for m in msgs.values()) == {"Engine", "Battery", "Aux"}
    assert dbc.frame_key(2566844926 & 0x1FFFFFFF, True) == 2566844926       # 29-bit ids: bit 31 in the .dbc
    frames = [engine(1500, 85, 3, -100.5), engine(800.25, -10, 1, 200)]
    data = np.frombuffer(b"".join(frames), dtype=np.uint8).reshape(2, 8)
    out = {n: y for n, _t, y, _l in dbc.decode_message(msgs[256], np.array([0.0, 1.0]), data)}
    assert np.allclose(out["Engine.RPM [rpm]"], [1500, 800.25])
    assert np.allclose(out["Engine.Temp [degC]"], [85, -10])        # signed, offset
    assert np.allclose(out["Engine.Gear"], [3, 1])                  # value names: raw codes
    assert np.allclose(out["Engine.Torque [Nm]"], [-100.5, 200])     # Motorola, signed


def write_log(tmp_path, kind):
    eng = [engine(1000 + 10 * k, 20 + k, k % 4, k - 5) for k in range(10)]
    ext_id = 2566844926 & 0x1FFFFFFF
    bat = []
    import struct
    for k in range(10):
        b = bytearray(8)
        b[0:2] = int((12.5 + k / 10) / 0.01).to_bytes(2, "big")
        b[2] = k % 2                                                 # mux 0 / 1 in the low nibble
        b[3:5] = int(3.3 * 1000 + k).to_bytes(2, "little")
        bat.append(bytes(b))
    aux = [struct.pack("<fI", 0.5 + k, 4000000000 + k) for k in range(10)]
    lines = []
    for k in range(10):
        t = 1700000000.0 + k * 0.1
        if kind == "candump":
            lines.append(f"({t:.6f}) can0 100#{eng[k].hex().upper()}")
            lines.append(f"({t + 0.01:.6f}) can0 {ext_id:08X}#{bat[k].hex().upper()}")
            lines.append(f"({t + 0.02:.6f}) can0 7FF#0102")          # not in the .dbc
            lines.append(f"({t + 0.03:.6f}) can0 200#{aux[k].hex()}")
        elif kind == "asc":
            tt = k * 0.1
            lines.append(f"   {tt:.6f} 1  100             Rx   d 8 {' '.join(f'{x:02X}' for x in eng[k])}")
            lines.append(f"   {tt + 0.01:.6f} 1  {ext_id:X}x        Rx   d 8 {' '.join(f'{x:02X}' for x in bat[k])}")
            lines.append(f"   {tt + 0.03:.6f} 1  200             Rx   d 8 {' '.join(f'{x:02X}' for x in aux[k])}")
        else:
            if not lines:
                lines.append("time,id,data")
            lines.append(f"{k * 0.1:.3f},0x100,{eng[k].hex()}")
            lines.append(f"{k * 0.1 + 0.01:.3f},0x{ext_id:08X},{bat[k].hex()}")
            lines.append(f"{k * 0.1 + 0.03:.3f},0x200,{aux[k].hex()}")
    ext = {"candump": ".log", "asc": ".asc", "csv": ".csv"}[kind]
    p = tmp_path / f"bus{ext}"
    p.write_text(("date Mon Oct 20 10:00:00 2026\nbase hex  timestamps absolute\n" if kind == "asc" else "")
                 + "\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.mark.parametrize("kind", ["candump", "asc", "csv"])
def test_logs_open_with_the_dbc_next_to_them(tmp_path, kind):
    (tmp_path / "car.dbc").write_text(DBC, encoding="utf-8")
    p = write_log(tmp_path, kind)
    lr = Store().open_file(str(p))
    s = lr.run.signals
    assert np.allclose(s["Engine.RPM [rpm]"].data, [1000 + 10 * k for k in range(10)])
    assert np.allclose(s["Engine.Torque [Nm]"].data, [k - 5 for k in range(10)])
    assert s["Engine.Gear"].labels == {0: "P", 1: "R", 2: "N", 3: "D"}
    assert np.allclose(s["Battery.Volt [V]"].data, [12.5 + k / 10 for k in range(10)])
    assert len(s["Battery.Cell0 [V]"].data) == 5 and len(s["Battery.Cell1 [V]"].data) == 5   # multiplexed
    assert np.allclose(s["Aux.Ratio"].data, [0.5 + k for k in range(10)])                     # float32 signal
    assert np.allclose(s["Aux.Count"].data, [4000000000 + k for k in range(10)])              # 32-bit unsigned
    assert s["Engine.RPM [rpm]"].time[0] == pytest.approx(0.0)        # Unix times start at 0
    assert lr.load_report["dbc"] == ["car.dbc"]
    if kind == "candump":
        assert lr.load_report["unknownIds"] == {"0x7ff": 10} and lr.load_report["startUnixTime"] > 1e9


def test_without_a_dbc_says_where_to_put_it(tmp_path):
    p = write_log(tmp_path, "candump")
    with pytest.raises(LoadError, match="put the .dbc next to the log"):
        Store().open_file(str(p))
    (tmp_path / "other.dbc").write_text('BO_ 999 X: 8 N\n SG_ A : 0|8@1+ (1,0) [0|1] "" N\n', encoding="utf-8")
    with pytest.raises(LoadError, match="None of the CAN ids.*0x100"):
        Store().open_file(str(p))


def test_a_plain_csv_next_to_a_dbc_is_still_a_table(tmp_path):
    (tmp_path / "car.dbc").write_text(DBC, encoding="utf-8")
    p = tmp_path / "t.csv"
    p.write_text("time,speed\n0,1\n1,2\n", encoding="utf-8")
    assert "speed" in Store().open_file(str(p)).run.signals


def test_agrees_with_cantools_on_random_frames():
    cantools = pytest.importorskip("cantools")
    db = cantools.database.load_string(DBC, "dbc")
    msgs = dbc.parse_dbc(DBC)
    rnd = random.Random(7)
    for key, m in msgs.items():
        frames = [bytes(rnd.randrange(256) for _ in range(8)) for _ in range(300)]
        data = np.frombuffer(b"".join(frames), dtype=np.uint8).reshape(-1, 8)
        mine = {n.split(".", 1)[1].split(" [")[0]: (t, y) for n, t, y, _ in dbc.decode_message(m, np.arange(300.0), data)}
        ref = db.get_message_by_frame_id(key & 0x1FFFFFFF)
        for i, fr in enumerate(frames):
            try:
                want = ref.decode(fr, decode_choices=False, scaling=True, allow_truncated=True)
            except cantools.database.errors.DecodeError:     # a multiplexer value the .dbc has no branch for
                continue
            for name, v in want.items():
                t, y = mine[name]
                hit = np.flatnonzero(t == i)
                if not len(hit):
                    continue                                     # another mux branch
                got = y[hit[0]]                                  # value names: raw codes, as decode_choices=False
                assert (np.isnan(v) and np.isnan(got)) or got == pytest.approx(float(v), rel=1e-6, abs=1e-6), (m["name"], name, i)
