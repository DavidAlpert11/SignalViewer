"""P1 / P2 (owner, 2026-11-12): a Tacview file that opens and shows models (not triangles), Tacview CSV
files and Google Earth KML as two more ways out, and an object with no real position (EAHR at 0, 0 in
the owner's file) that is no object."""
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.routes.analysis import no_position_as_gap  # noqa: E402
from svcore.acmi import MODELS, fit_rate, write_acmi  # noqa: E402
from svcore.acmi_check import check  # noqa: E402
from svcore.kml import write_kml  # noqa: E402
from svcore.tacview_csv import write_csvs  # noqa: E402

client = TestClient(app)
HEAD = "FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime=2000-01-01T00:00:00Z\n"
OK1 = "#0\n101,T=124.29|45.52|100|0|0|0,Type=Air+FixedWing,Name=C172,CallSign=A,Color=Blue\n"


# ------------------------------------------------------------------ the checker
BAD = {
    "header": ("FileType=text/acmi/tacview\nFileVersion=2.1\n", "first two lines"),
    "no reference time": ("FileType=text/acmi/tacview\nFileVersion=2.2\n" + OK1, "ReferenceTime"),
    "time goes back": (HEAD + OK1 + "#2\n101,T=124.29|45.52|100|0|0|0\n#1\n101,T=124.29|45.52|100|0|0|0\n", "must increase"),
    "field count changes": (HEAD + OK1 + "#1\n101,T=124.29|45.52|100\n", "changes from 6 to 3"),
    "nan": (HEAD + "#0\n101,T=nan|45.52|100,Type=Air+FixedWing,Name=C172\n", "not a plain decimal"),
    "exponent": (HEAD + "#0\n101,T=1e2|45.52|100,Type=Air+FixedWing,Name=C172\n", "not a plain decimal"),
    "latitude": (HEAD + "#0\n101,T=10|95|100,Type=Air+FixedWing,Name=C172\n", "outside +-90"),
    "no name": (HEAD + "#0\n101,T=10|45|100,Type=Air+FixedWing,CallSign=A\n", "no Name"),
    "colour": (HEAD + "#0\n101,T=10|45|100,Type=Air+FixedWing,Name=C172,Color=Pink\n", "Color"),
    "id again": (HEAD + OK1 + "#1\n-101\n#2\n101,T=124.29|45.52|100|0|0|0\n", "used again"),
    "id 0 object": (HEAD + "#0\n000,T=10|45|100,Type=Air+FixedWing,Name=C172\n", "must not be 0"),
}


def test_a_good_file_is_fine():
    assert check(HEAD + OK1 + "#1\n101,T=124.2901|45.52|101|0|0|1\n") == []


@pytest.mark.parametrize("name", list(BAD))
def test_the_checker_names_the_fault(name):
    text, words = BAD[name]
    out = check(text)
    assert out and any(words in m for m in out), out


def test_the_checker_warns_about_a_far_object_and_a_jump():
    far = HEAD + OK1 + "102,T=0|0|0,Type=Air+FixedWing,Name=C172,CallSign=EAHR\n"
    assert any("EAHR is" in m and "km from A" in m for m in check(far))
    jump = HEAD + OK1 + "#0.1\n101,T=124.31|45.52|100|0|0|0\n"
    assert any("jumps" in m for m in check(jump))


# ------------------------------------------------------------------ the writer
def _owner_like():
    """Five objects together near 45.52 N, 124.29 E (one, the GPS, with no attitude: zeros), and EAHR
    at 0, 0 for the whole flight - the shape of the owner's Plot_1.acmi."""
    t = np.arange(0, 55, 0.1)
    objs = []
    for k, name in enumerate(["XKF1[0]", "POS", "AHR2", "SIM", "GPS[0]"]):
        lat = 45.52 + 0.0001 * k + 0.00001 * t
        lon = 124.29 + 0.00002 * t
        zero = name == "GPS[0]"
        objs.append({"name": name, "kind": "aircraft", "color": "#0072B2", "t": t, "lat": lat, "lon": lon,
                     "alt": 100 + t, "roll": np.zeros_like(t) if zero else np.sin(t), "pitch": np.zeros_like(t) if zero else np.cos(t),
                     "yaw": np.zeros_like(t) if zero else (t * 5) % 360})
    lat0, lon0 = no_position_as_gap(np.zeros_like(t), np.zeros_like(t))      # what track_of gives EAHR
    objs.append({"name": "EAHR", "kind": "aircraft", "color": "#D55E00", "t": t, "lat": lat0, "lon": lon0, "alt": np.zeros_like(t)})
    return objs


def test_a_re_export_of_the_owners_file_shape():
    left: list = []
    body = write_acmi(_owner_like(), rate=10, left_out=left)
    assert check(body) == []
    assert left == ["EAHR"] and "EAHR" not in body                                  # nothing at 0, 0
    first = [x for x in body.splitlines() if ",Type=" in x]
    assert len(first) == 5 and all(",Name=C172,CallSign=" in x for x in first)       # a model, the name aside
    gps = next(x for x in first if "CallSign=GPS[0]" in x)
    assert gps.split(",")[1].count("|") == 2                                         # 3-field T= (no invented zeros)
    pos = next(x for x in first if "CallSign=POS" in x)
    assert pos.split(",")[1].count("|") == 5


def test_every_kind_has_a_model():
    assert set(MODELS) == {"aircraft", "uav", "drone", "missile", "ship", "vehicle"}


def test_a_short_gap_is_kept_a_long_one_is_a_new_object():
    t = np.r_[np.arange(0, 10, 0.5), np.arange(11, 20, 0.5), np.arange(25, 30, 0.5)]   # 1 s gap, then 5 s
    o = {"name": "A", "kind": "uav", "color": "#009E73", "t": t, "lat": 32 + t * 1e-5, "lon": 35 + t * 1e-5, "alt": np.full(len(t), 50.0)}
    body = write_acmi([o], rate=2)
    assert check(body) == []
    assert "-101" in body and "102,T=" in body and "-102" not in body and ",Name=MQ-9" in body
    assert body.count(",Type=") == 2


def test_a_missing_altitude_keeps_the_last_one():
    t = np.arange(0, 5, 1.0)
    o = {"name": "A", "kind": "aircraft", "color": "#000000", "t": t, "lat": np.full(5, 32.0), "lon": np.full(5, 35.0),
         "alt": np.array([10, 20, np.nan, np.nan, np.nan])}
    lines = [x for x in write_acmi([o], rate=1).splitlines() if x.startswith("101,")]
    assert [x.split("|")[2].split(",")[0] for x in lines] == ["10", "20", "20", "20", "20"]


def test_the_rate_is_lowered_for_a_long_recording():
    t = np.arange(0, 3600 * 10, 1.0)
    o = {"t": t, "lat": t, "lon": t}
    assert fit_rate([o] * 50, 10) == pytest.approx(max(1.0, 1_500_000 / (t[-1] * 50)))
    assert fit_rate([o] * 50, 10) >= 1.0 and fit_rate([{"t": t[:100], "lat": t[:100], "lon": t[:100]}], 10) == 10


# ------------------------------------------------------------------ CSV and KML
def test_tacview_csv_files(tmp_path):
    objs = _owner_like()[:3]
    objs[2] = {**objs[2], "name": "POS", "color": "#E69F00"}                         # a duplicate name
    objs[1] = {**objs[1], "color": "#E69F00"}
    left: list = []
    paths = write_csvs(objs + [_owner_like()[5]], str(tmp_path), 10, left_out=left)
    names = sorted(os.path.basename(p) for p in paths)
    assert names == ["C172 (POS 2) [Orange].csv", "C172 (POS) [Orange].csv", "C172 (XKF1 0) [Blue].csv"]
    assert left == ["EAHR"]
    rows = open(tmp_path / "C172 (XKF1 0) [Blue].csv").read().splitlines()
    assert rows[0] == "Time,Longitude,Latitude,Altitude,Roll,Pitch,Yaw"
    assert rows[1].startswith("0,124.29,45.52,100,") and rows[2].startswith("0.1,")


def test_kml_holds_every_object_and_the_places():
    objs = _owner_like()
    body = write_kml(objs, [{"name": "Runway 27", "lat": 45.5, "lon": 124.3}], title="Flight")
    root = ET.fromstring(body)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    marks = [p.find("k:name", ns).text for p in root.iter("{http://www.opengis.net/kml/2.2}Placemark")]
    assert marks == ["XKF1[0]", "POS", "AHR2", "SIM", "GPS[0]", "Runway 27"]
    assert body.count("<LineString>") == 5                                           # no real dates: lines
    dated = [{**o, "t": o["t"] + 1.7e9} for o in objs[:1]]
    assert "<gx:Track>" in write_kml(dated) and "<when>2023-" in write_kml(dated)


# ------------------------------------------------------------------ P2 and the routes
def test_zeros_are_no_position():
    lat, lon = no_position_as_gap(np.array([0, 0, 32.1, 0, 95, np.inf]), np.array([0, 0, 35.2, 35.0, 35, 35]))
    assert np.isnan(lat[[0, 1, 4, 5]]).all() and lat[2] == 32.1 and lat[3] == 0        # 0 lat alone is a position


def _open(tmp_path):
    t = np.arange(0, 20, 0.2)
    rows = ["t,POS.Lat,POS.Lng,POS.Alt,EAHR.Lat,EAHR.Lng"]
    for k, x in enumerate(t):
        late = k >= 10                                                               # zeros only at the start
        rows.append(f"{x:.1f},{45.52 + x * 1e-5 if late else 0},{124.29 + x * 1e-5 if late else 0},100,0,0")
    p = tmp_path / "owner_like.csv"
    p.write_text("\n".join(rows) + "\n")
    return client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]


def test_tracks_and_exports_through_the_routes(tmp_path):
    run = _open(tmp_path)
    try:
        s = lambda n: f"{run['id']}/{n}"
        tr = client.post("/api/object_track", json={"lat": s("EAHR.Lat"), "lon": s("EAHR.Lng")})
        assert tr.status_code == 200, tr.text
        assert tr.json()["valid"] == 0                                               # all gaps
        pos = client.post("/api/object_track", json={"lat": s("POS.Lat"), "lon": s("POS.Lng")}).json()
        lat = np.frombuffer(__import__("base64").b64decode(pos["lat"]), np.float64)
        assert pos["valid"] == 90 and np.isnan(lat[:10]).all() and np.isfinite(lat[10:]).all()   # begins at the first fix
        objs = [{"name": "POS", "kind": "aircraft", "color": "#0072B2", "lat": s("POS.Lat"), "lon": s("POS.Lng"), "alt": s("POS.Alt")},
                {"name": "EAHR", "kind": "aircraft", "color": "#D55E00", "lat": s("EAHR.Lat"), "lon": s("EAHR.Lng")}]
        r = client.post("/api/export/acmi", json={"path": str(tmp_path / "f"), "objects": objs}).json()
        assert r["objects"] == 1 and r["leftOut"] == ["EAHR"] and r["rate"] == 10 and not r["lowered"]
        assert check(open(r["path"], encoding="utf-8-sig").read()) == []
        c = client.post("/api/export/tacview_csv", json={"path": str(tmp_path / "csv"), "objects": objs}).json()
        assert [os.path.basename(p) for p in c["files"]] == ["C172 (POS) [Blue].csv"] and c["leftOut"] == ["EAHR"]
        k = client.post("/api/export/kml", json={"path": str(tmp_path / "g"), "objects": objs}).json()
        assert k["path"].endswith("g.kml") and ET.parse(k["path"]).getroot() is not None
        none = client.post("/api/export/acmi", json={"path": str(tmp_path / "n"), "objects": objs[1:]})
        assert none.status_code == 400
    finally:
        client.delete(f"/api/runs/{run['id']}")


def test_the_python_api(tmp_path):
    import signalviewer as sv
    rec = sv.load(os.path.join(os.path.dirname(__file__), "..", "..", "examples", "ardupilot_lanes.csv"))
    paths = sv.tacview_csv(rec, folder=str(tmp_path / "tv"))
    assert len(paths) == 4 and all(os.path.basename(p).startswith("C172 (") for p in paths)
    k = sv.kml(rec, path=str(tmp_path / "f.kml"))
    assert len(list(ET.parse(k).getroot().iter("{http://www.opengis.net/kml/2.2}Placemark"))) == 4


def test_position_counts_before_adding(tmp_path):
    run = _open(tmp_path)
    try:
        s = lambda n: f"{run['id']}/{n}"
        r = client.post("/api/object_positions", json={"objects": [{"lat": s("EAHR.Lat"), "lon": s("EAHR.Lng")},
                                                                    {"lat": s("POS.Lat"), "lon": s("POS.Lng")},
                                                                    {"lat": "nope/x", "lon": "nope/y"}]}).json()
        assert r["objects"] == [{"valid": 0, "total": 100}, {"valid": 90, "total": 100}, {"valid": 0, "total": 0}]
    finally:
        client.delete(f"/api/runs/{run['id']}")
