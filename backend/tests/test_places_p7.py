"""P7 (2026-11-12): places - the coordinate parser, importing KML / KMZ / GeoJSON / CSV (fixtures made by
tools/make_places_fixtures.py), My places kept by the app, places in the KML and ACMI exports and in the
pages."""
import os
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

import app.prefs as prefs  # noqa: E402
from app.main import app  # noqa: E402
from svcore.acmi_check import check  # noqa: E402
from svcore.kml import write_kml  # noqa: E402
from svcore.places import clean, parse_coords, read_places  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data", "places")
client = TestClient(app)


@pytest.mark.parametrize("text, want", [
    ("32.687, 35.39", (32.687, 35.39)),
    ("32.687 35.39", (32.687, 35.39)),
    ("32.687;35.39", (32.687, 35.39)),
    ("-33.9, 151.2", (-33.9, 151.2)),
    ("32°41'13\"N 35°23'24\"E", (32.686944, 35.39)),
    ("32°41′13″N, 35°23′24″E", (32.686944, 35.39)),
    ("N32 41 13 E35 23 24", (32.686944, 35.39)),
    ("32 41 13 N 35 23 24 E", (32.686944, 35.39)),
    ("33°52'S 151°12'E", (-33.866667, 151.2)),
    ("35.39E 32.687N", (32.687, 35.39)),           # the letters decide which is which
    ("32.5N;35.5W", (32.5, -35.5)),
    ("32°41.22'N 35°23.4'E", (32.687, 35.39)),
])
def test_parser_reads_positions(text, want):
    got = parse_coords(text)
    assert got is not None, text
    assert got[0] == pytest.approx(want[0], abs=1e-5) and got[1] == pytest.approx(want[1], abs=1e-5)


@pytest.mark.parametrize("text", ["", "hello", "32.687", "95, 10", "10, 190", "32°61'N 35°E", "1, 2, 3", "N32 E35 W12"])
def test_parser_refuses_what_is_not_a_position(text):
    assert parse_coords(text) is None


def _by_name(places):
    return {p["name"]: p for p in places}


@pytest.mark.parametrize("name", ["places.kml", "places.kmz", "places.geojson"])
def test_import_point_line_area(name):
    places, skipped = read_places(os.path.join(DATA, name))
    got = _by_name(places)
    assert skipped == 1                                        # the one without a valid position
    pt = got["Megiddo airfield"]
    assert pt["kind"] == "point" and pt["lat"] == pytest.approx(32.5973) and pt["lon"] == pytest.approx(35.2286) and pt["alt"] == 60
    assert pt["note"] == "tower 122.8" and pt["icon"] == "pin"
    ln = got["Runway 27 approach"]
    assert ln["kind"] == "line" and len(ln["points"]) == 3 and ln["points"][0] == [32.599, 35.25]
    ar = got["Range A"]
    assert ar["kind"] == "area" and len(ar["points"]) == 4      # the closing point is not kept twice


def test_import_csv_decimal_and_dms():
    places, skipped = read_places(os.path.join(DATA, "places.csv"))
    got = _by_name(places)
    assert skipped == 0                      # a row with no position is not a place (it never became one)
    assert set(got) == {"Megiddo airfield", "Ground station"}
    assert got["Ground station"]["lat"] == pytest.approx(32.686944, abs=1e-5)
    assert "alt" not in got["Ground station"]


def test_import_refuses_other_files(tmp_path):
    p = tmp_path / "x.txt.gpx"
    p.write_text("<gpx/>")
    with pytest.raises(ValueError, match="kml"):
        read_places(str(p))
    bad = tmp_path / "bad.kml"
    bad.write_text("<kml><Placemark>")
    with pytest.raises(ValueError, match="not valid XML"):
        read_places(str(bad))


def test_kml_round_trip(tmp_path):
    places, _ = read_places(os.path.join(DATA, "places.kml"))
    places.append(clean({"kind": "view", "name": "Over the range", "lat": 32.71, "lon": 35.32, "alt": 1500,
                         "view": {"heading": 90, "pitch": -30, "range": 0}}))
    body = write_kml([], places, title="Places")
    ET.fromstring(body.encode())                                   # valid XML
    out = tmp_path / "out.kml"
    out.write_text(body, encoding="utf-8")
    again, skipped = read_places(str(out))
    assert skipped == 0
    assert _by_name(again).keys() == {"Megiddo airfield", "Runway 27 approach", "Range A"}   # a view is a LookAt, not a shape
    assert "<LookAt>" in body and "<tilt>60</tilt>" in body
    ar = _by_name(again)["Range A"]
    assert ar["kind"] == "area" and len(ar["points"]) == 4


def test_clean_drops_bad_and_unknown():
    assert clean({"name": "x", "lat": 95, "lon": 0}) is None
    assert clean({"name": "x", "lat": "nan", "lon": 1}) is None
    assert clean({"kind": "line", "points": [[1, 2]]}) is None
    c = clean({"name": "x", "lat": 1, "lon": 2, "icon": "rocket", "color": "red", "evil": "<script>"})
    assert c["icon"] == "pin" and "color" not in c and "evil" not in c


@pytest.fixture()
def appdir(tmp_path, monkeypatch):
    d = tmp_path / "app"
    d.mkdir()
    monkeypatch.setattr(prefs, "APP_DIR", str(d))
    return d


def test_my_places_kept_by_the_app(appdir):
    assert client.get("/api/places").json()["places"] == []
    r = client.put("/api/places", json={"places": [{"id": "a", "name": "Home", "kind": "point", "lat": 32.1, "lon": 34.8, "icon": "home"},
                                                   {"name": "broken", "lat": 300, "lon": 0}]}).json()
    assert [p["name"] for p in r["places"]] == ["Home"]
    assert (appdir / "places.json").exists()
    got = client.get("/api/places").json()
    assert got["places"][0]["icon"] == "home" and got["path"].endswith("places.json")


def test_import_export_and_parse_endpoints(tmp_path):
    r = client.post("/api/places/import", json={"path": os.path.join(DATA, "places.geojson")}).json()
    assert len(r["places"]) == 3 and r["skipped"] == 1
    out = tmp_path / "mine"
    e = client.post("/api/places/export", json={"path": str(out), "places": r["places"]}).json()
    assert e["path"].endswith("mine.kml") and os.path.exists(e["path"])
    assert client.post("/api/places/import", json={"path": str(tmp_path / "none.kml")}).status_code == 404
    assert client.get("/api/places/parse", params={"q": "32°41'13\"N 35°23'24\"E"}).json()["ok"] is True
    assert client.get("/api/places/parse", params={"q": "nowhere"}).json() == {"ok": False}
    g = client.get("/api/ground", params={"lat": 32.7, "lon": 35.3}).json()
    assert "ground" in g


def test_acmi_places_are_static_objects():
    import numpy as np

    from svcore.acmi import write_acmi
    t = np.arange(0, 10, 0.5)
    obj = {"name": "UAV", "kind": "uav", "color": "#0072B2", "t": t, "lat": 32.6 + t * 1e-5, "lon": 35.23 + t * 1e-5,
           "alt": np.full(len(t), 300.0), "roll": None, "pitch": None, "yaw": None, "group": ""}
    places = [{"name": "Megiddo airfield", "kind": "point", "lat": 32.5973, "lon": 35.2286, "alt": 60, "icon": "airfield"},
              {"name": "Ground station", "kind": "point", "lat": 32.687, "lon": 35.39},
              {"name": "Range A", "kind": "area", "lat": 32.7, "lon": 35.3, "points": [[32.7, 35.3], [32.72, 35.3], [32.72, 35.34]]}]
    text = write_acmi([obj], places=places)
    assert check(text) == [] or all("km" in w for w in check(text))
    assert "Type=Ground+Static+Aerodrome,Name=Megiddo airfield" in text
    assert "Type=Navaid+Static+Waypoint,Name=Ground station" in text
    assert "Range A" not in text                                  # lines / areas are not ACMI objects


def test_pages_and_pictures_draw_places():
    """The 3D page, the flat page and both pictures take the shown places (P7)."""
    from app import mapimage, scene3d
    from app.store import store
    from svcore.csv_loader import load_csv
    ex = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "ardupilot_lanes.csv")
    run = store.add_pushed("places_scene", load_csv(ex, [ex]))[0]
    try:
        rid = run.id
        pos = {"id": "POS", "name": "POS", "kind": "aircraft", "color": "#e5677a", "lat": f"{rid}/POS.Lat [deg]", "lon": f"{rid}/POS.Lng [deg]",
               "alt": f"{rid}/POS.Alt [m]"}
        md0 = mapimage.map_data(store, {"title": "", "geo": {"objects": [pos], "base": "offline"}})
        s_, w_, n_, e_ = md0["bounds"]
        lat, lon = (s_ + n_) / 2, (w_ + e_) / 2
        places = [{"id": "a", "name": "Tower", "kind": "point", "lat": lat, "lon": lon, "icon": "antenna", "img": "data:image/svg+xml;charset=utf-8,%3Csvg%2F%3E"},
                  {"id": "b", "name": "Strip", "kind": "line", "lat": lat, "lon": lon, "points": [[lat, lon], [lat + 0.001, lon + 0.001]]},
                  {"id": "c", "name": "Hidden one", "kind": "point", "lat": lat, "lon": lon, "hidden": True},
                  {"id": "d", "name": "Far away", "kind": "point", "lat": -40, "lon": 100}]
        geo = {"objects": [pos], "base": "offline", "cursor": None, "places": places}
        md = mapimage.map_data(store, {"title": "", "geo": geo})
        assert [p["name"] for p in md["places"]] == ["Tower", "Strip", "Far away"]
        assert md["places"][0]["img"].startswith("data:image/svg+xml")
        assert md["bounds"] == md0["bounds"]                       # places are not in Fit when there are objects
        assert mapimage.render(md)[:4] == b"\x89PNG"
        assert '"name":"Tower"' in mapimage.build_html(md, budget=1)
        sd = scene3d.scene_data(store, {"title": "", "geo": geo, "scene": {"objects": [pos]}})
        assert [p["name"] for p in sd["places"]] == ["Tower", "Strip"]          # outside the far ground: left out
        assert scene3d.render(sd)[:4] == b"\x89PNG"
    finally:
        store.remove(run.id)
