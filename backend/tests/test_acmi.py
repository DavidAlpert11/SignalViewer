"""N8: Tacview's text ACMI 2.2 (svcore/acmi.py) - a known small file, and the export of map objects."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from svcore.acmi import acmi_color, text, write_acmi  # noqa: E402
from svcore.acmi_check import check  # noqa: E402

client = TestClient(app)
EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "three_objects.csv")


def test_a_known_small_file():
    t = np.array([0.0, 0.5, 1.0])
    plane = {"name": "Truth, main", "kind": "aircraft", "color": "#0072B2", "t": t,
             "lat": np.array([32.5, 32.5001, 32.5002]), "lon": np.array([35.25, 35.25, 35.25]), "alt": np.array([100.0, 101.0, 102.0]),
             "roll": np.array([10.0, 20.0, 30.0]), "pitch": np.array([1.0, 2.0, 3.0]), "yaw": np.array([350.0, 0.0, 10.0])}
    boat = {"name": "Boat", "kind": "ship", "color": "#D55E00", "t": np.array([0.0, 0.5]),
            "lat": np.array([32.6, 32.6]), "lon": np.array([35.3, 35.3]), "alt": None}
    body = write_acmi([plane, boat], rate=2, title="Test", recorder="Signal Viewer 1.24.0")
    assert body == (
        "FileType=text/acmi/tacview\nFileVersion=2.2\n"
        "0,ReferenceTime=2000-01-01T00:00:00Z\n0,ReferenceLongitude=35\n0,ReferenceLatitude=32\n"
        "0,DataSource=Signal Viewer 1.24.0\n0,DataRecorder=Signal Viewer 1.24.0\n0,Title=Test\n"
        "#0\n"
        "101,T=0.25|0.5|100|10|1|350,Type=Air+FixedWing,Name=C172,CallSign=Truth\\, main,Color=Blue\n"
        "102,T=0.3|0.6|0,Type=Sea+Watercraft,Name=Zodiac,CallSign=Boat,Color=Orange\n"
        "#0.5\n101,T=0.25|0.5001|101|20|2|0\n102,T=0.3|0.6|0\n"
        "#1\n-102\n101,T=0.25|0.5002|102|30|3|10\n")
    assert check(body) == []


def test_epoch_times_set_the_reference_time_and_angles_wrap():
    t = 1_700_000_000.25 + np.arange(3.0)
    o = {"name": "A", "kind": "drone", "color": "#009E73", "t": t, "lat": np.full(3, -10.5), "lon": np.full(3, -70.25),
         "alt": np.full(3, 5.0), "roll": np.array([-170.0, 190.0, 0.0]), "pitch": None, "yaw": np.array([359.0, 1.0, 3.0])}
    lines = write_acmi([o], rate=1).splitlines()
    assert "0,ReferenceTime=2023-11-14T22:13:20Z" in lines
    assert "0,ReferenceLongitude=-71" in lines and "0,ReferenceLatitude=-11" in lines
    assert lines[lines.index("#0.25") + 1].startswith("101,T=0.75|0.5|5|-170|0|359,Type=Air+Rotorcraft,Name=DJI300,CallSign=A,Color=Green")
    assert lines[lines.index("#1.25") + 1] == "101,T=0.75|0.5|5|-170|0|1"    # 190 is -170; no pitch: level, never an empty field


def test_colours_and_text():
    assert [acmi_color(c) for c in ("#ff0000", "#E69F00", "#F0E442", "#009E73", "#56B4E9", "#0072B2", "#CC79A7", "#7F7F7F")] == \
        ["Red", "Orange", "Yellow", "Green", "Cyan", "Blue", "Violet", "Blue"]
    assert text("a,b\nc") == "a\\,b c"


def test_export_the_objects_of_a_recording(tmp_path):
    run = client.post("/api/files/open", json={"paths": [EX]}).json()["opened"][0]
    try:
        s = lambda n: f"{run['id']}/{n}"
        objs = [
            {"name": "phys", "kind": "aircraft", "color": "#0072B2", "lat": s("phys.lat"), "lon": s("phys.lon"), "alt": s("phys.alt"),
             "roll": s("phys.att.roll"), "pitch": s("phys.att.pitch"), "yaw": s("phys.att.yaw"), "angleUnit": "deg", "cls": "truth"},
            {"name": "gps", "kind": "aircraft", "color": "#E69F00", "lat": s("gps.lat"), "lon": s("gps.lon"), "alt": s("gps.alt"),
             "attitude": "motion", "cls": "receiver"},
        ]
        r = client.post("/api/export/acmi", json={"path": str(tmp_path / "flight"), "title": "Three objects", "objects": objs})
        assert r.status_code == 200, r.text
        p = r.json()["path"]
        assert p.endswith("flight.acmi") and r.json()["objects"] == 2
        raw = open(p, "rb").read()
        assert raw.startswith(b"\xef\xbb\xbfFileType=text/acmi/tacview\nFileVersion=2.2\n") and b"\r\n" not in raw
        lines = raw.decode("utf-8-sig").splitlines()
        first = next(x for x in lines if x.startswith("101,"))
        assert ",Type=Air+FixedWing,Name=C172,CallSign=phys,Color=Blue,Group=truth" in first
        assert check(raw.decode("utf-8-sig")) == []
        f = first.split(",")[1][2:].split("|")
        assert len(f) == 6 and abs(float(f[3]) + 31.46) < 0.01 and abs(float(f[2]) - 300) < 0.01   # roll, altitude
        assert any(x.startswith("102,") and "Group=receiver" in x for x in lines)
        assert sum(x.startswith("#") for x in lines) > 10
        bad = client.post("/api/export/acmi", json={"path": str(tmp_path / "x"), "objects": [{**objs[0], "lat": "nope/x"}]})
        assert bad.status_code == 404
    finally:
        client.delete(f"/api/runs/{run['id']}")
