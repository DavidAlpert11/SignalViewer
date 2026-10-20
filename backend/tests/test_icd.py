"""T61: raw binary recordings decoded from a layout (ICD) in the readers folder."""
import json
import struct

import numpy as np
import pytest

import app.prefs as prefs
from app.store import LoadError, Store
from svcore import icd


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    return tmp_path


def test_example_layout_through_the_store(home, tmp_path):
    from app import userreaders
    userreaders.write_example_icd()
    rec = tmp_path / "run.tlm"
    icd.write_example_recording(str(rec), seconds=20)
    lr = Store().open_file(str(rec))
    sig = lr.run.signals
    assert {"NAV.alt [m]", "NAV.mode", "NAV.armed", "PWR.volt [V]", "PWR.amp [A]"} <= set(sig)
    assert "NAV.t_us" not in sig                                     # the time field is the time
    assert len(sig["NAV.alt [m]"].data) == 1000 and len(sig["PWR.volt [V]"].data) == 200
    assert sig["NAV.alt [m]"].data.max() == pytest.approx(120.0)
    assert sig["PWR.volt [V]"].data[0] == pytest.approx(16.8)          # big-endian field override
    assert sig["NAV.mode"].labels == {0: "IDLE", 1: "CLIMB", 2: "CRUISE"}
    assert set(np.unique(sig["NAV.armed"].data)) == {0.0, 1.0}         # a bit field
    assert lr.run.end_time == pytest.approx(19.98)
    rep = lr.load_report
    assert rep["packets"] == {"NAV": 1000, "PWR": 200} and rep["bytesSkipped"] == 4      # the noise, skipped
    assert rep["reader"] == "Example bench telemetry"


def test_fixed_records_header_time_and_cut_off(tmp_path):
    lay = icd.parse_layout({"byte_order": "big", "header": {"size": 4, "time": {"offset": 0, "type": "u32", "scale": 0.001}},
                            "packets": [{"name": "S", "fields": [{"name": "v", "offset": 0, "type": "i16"}]}]})
    p = tmp_path / "r.raw"
    p.write_bytes(b"".join(struct.pack(">Ih", k * 10, -k) for k in range(5)) + b"\x01\x02")     # 2 stray bytes
    r = icd.decode(lay, str(p))
    t, y = r["signals"]["S.v"]
    assert np.allclose(t, [0, 0.01, 0.02, 0.03, 0.04]) and np.allclose(y, [0, -1, -2, -3, -4])
    assert r["report"]["cutOff"] == 1


def test_unknown_ids_resync_and_numbered(tmp_path):
    lay = icd.parse_layout({"header": {"sync": [0xEB, 0x90], "size": 3, "id": {"offset": 2, "type": "u8"}},
                            "packets": [{"id": 7, "name": "A", "fields": [{"name": "x", "offset": 0, "type": "f32"}]}]})
    p = tmp_path / "r.raw"
    good = lambda v: b"\xeb\x90\x07" + struct.pack("<f", v)
    p.write_bytes(good(1.5) + b"\xeb\x90\x09junk" + good(2.5) + good(3.5))
    r = icd.decode(lay, str(p))
    t, y = r["signals"]["A.x"]
    assert np.allclose(y, [1.5, 2.5, 3.5]) and np.allclose(t, [0, 1, 2])
    assert r["report"]["unknownIds"] >= 1 and r["report"]["numbered"] == ["A"]


@pytest.mark.parametrize("layout, msg", [
    ({"packets": []}, "at least one packet"),
    ({"packets": [{"name": "A", "fields": [{"name": "x", "offset": 0, "type": "u24"}]}]}, "unknown type"),
    ({"packets": [{"name": "A", "size": 2, "fields": [{"name": "x", "offset": 0, "type": "u32"}]}]}, "past the packet"),
    ({"packets": [{"name": "A", "fields": [{"name": "x", "offset": 0, "type": "u8"}]},
                  {"name": "B", "fields": [{"name": "y", "offset": 0, "type": "u8"}]}]}, "several packets need an \"id\""),
    ({"packets": [{"name": "A", "fields": [{"name": "x", "offset": 0, "type": "u8", "bits": [6, 4]}]}]}, "do not fit"),
    ({"header": {"size": 2, "id": {"offset": 2, "type": "u8"}}, "packets": [{"name": "A", "fields": [{"name": "x", "offset": 0, "type": "u8"}]}]},
     "does not fit in a 2-byte header"),
])
def test_layout_errors_say_where(layout, msg):
    with pytest.raises(icd.LayoutError, match=msg):
        icd.parse_layout(layout, "bench.icd.json")


def test_broken_layout_is_listed_not_fatal(home, tmp_path):
    from app import userreaders
    d = home / "readers"
    d.mkdir()
    (d / "bad.icd.json").write_text("{not json", encoding="utf-8")
    (d / "noext.icd.json").write_text(json.dumps({"packets": [{"name": "A", "fields": [{"name": "x", "offset": 0, "type": "u8"}]}]}))
    info = userreaders.listing()
    errs = {e["file"]: e["error"] for e in info["errors"]}
    assert "not valid JSON" in errs["bad.icd.json"] and "extensions" in errs["noext.icd.json"]
    p = tmp_path / "x.tlm"
    p.write_bytes(b"\x00" * 10)
    with pytest.raises(LoadError, match="Unsupported"):
        Store().open_file(str(p))
