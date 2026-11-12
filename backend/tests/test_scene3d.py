"""1.26: the map seen in 3D outside the app (app/scene3d.py) - its scene (local metres, attitude, terrain), its
picture (PDF / Word / PNG reports, the CLI) and its live offline page (three.js); in reports and in the replay;
an HTML report is live (one time) without the replay's layout; Python and the CLI make it too."""
import base64
import io
import json
import os
import re
import subprocess
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app import report, scene3d  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.csv_loader import load_csv  # noqa: E402

client = TestClient(app)
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
EX = os.path.join(ROOT, "examples", "ardupilot_lanes.csv")


@pytest.fixture(scope="module")
def rid():
    os.environ["SV_OFFLINE"] = "1"
    r = load_csv(EX, [EX])
    run = store.add_pushed("ardupilot_lanes_scene", r)[0]
    yield run.id
    store.remove(run.id)


def obj(rid, name="POS", color="#e5677a", **extra):
    return {"id": name, "name": name, "kind": "aircraft", "color": color, "lat": f"{rid}/{name}.Lat [deg]", "lon": f"{rid}/{name}.Lng [deg]",
            "alt": f"{rid}/{name}.Alt [m]", **extra}


def spec3d(rid, **extra):
    pos = obj(rid, roll=f"{rid}/ATT.Roll [deg]", pitch=f"{rid}/ATT.Pitch [deg]", yaw=f"{rid}/ATT.Yaw [deg]")
    gps = obj(rid, "GPS[0]", "#3d8bfd", kind="ship")
    return {"mode": "3d", "title": "Flight in 3D", "signals": [], "geo": {"objects": [pos, gps], "base": "offline", "cursor": 100.0},
            "scene": {"objects": [pos, gps], "follow": "POS"}, **extra}


def test_scene_is_local_metres_with_attitude_and_terrain(rid):
    sd = scene3d.scene_data(store, spec3d(rid))
    pos = sd["objects"][0]
    assert pos["name"] == "POS" and len(pos["t"]) <= scene3d.POINTS
    # east / north around the middle of the tracks: the ~2 km path fits in a few km either way
    assert np.nanmax(np.abs(pos["e"])) < 5000 and np.nanmax(np.abs(pos["n"])) < 5000
    # the altitude as recorded (above sea level), the ground under it from the bundled terrain
    t, a = store.signal(f"{rid}/POS.Alt [m]")
    assert abs(pos["u"][pos["at"]] - np.interp(pos["t"][pos["at"]], t, a)) < 0.5
    assert np.isfinite(pos["g"]).all() and sd["heights"].shape == (scene3d.GRID, scene3d.GRID)
    # its own angles (ATT); the GPS has none: it points along its course
    t, y = store.signal(f"{rid}/ATT.Yaw [deg]")
    k = pos["at"]
    d = (pos["yaw"][k] - np.interp(pos["t"][k], t, y) + 180) % 360 - 180
    assert abs(d) < 2.0
    assert np.isfinite(sd["objects"][1]["yaw"]).all() and sd["objects"][1]["kind"] == "ship"
    E0, E1, N0, N1 = sd["extent"]
    assert E0 < pos["e"].min() and pos["e"].max() < E1 and N0 < pos["n"].min() and pos["n"].max() < N1


def test_picture_is_drawn_without_a_browser(rid):
    png = scene3d.render(scene3d.scene_data(store, spec3d(rid)), "png", "light", 1.0)
    from PIL import Image
    im = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    assert im.shape[0] > 400 and im.shape[1] > 600
    assert im.std() > 20                                            # not blank
    # the POS track's colour is in the picture
    target = np.array([0xe5, 0x67, 0x7a])
    assert (np.abs(im.astype(int) - target).sum(axis=2) < 40).sum() > 50


def test_live_page_is_offline_and_complete(rid):
    page = scene3d.build_html(scene3d.scene_data(store, spec3d(rid)), "dark", "he")
    assert 'dir="rtl"' in page and "THREE" in page and '"REVISION"' not in page[:100]
    m = re.search(r"const D = (\{.*?\});\n", page, re.S)
    d = json.loads(m.group(1))
    assert d["follow"] == "POS" and set(d["models"]) == {"aircraft", "ship"} and d["models"]["aircraft"]["parts"]
    assert d["fallback"].startswith("data:image/png;base64,") and d["textures"]
    assert len(d["heights"]) == scene3d.GRID ** 2 and d["S"]["noGl"].startswith("הדפדפן")
    # nothing from the network: no script / style / image URL (the attribution and three.js's own comments aside)
    assert not re.search(r'(src|href)="https?://', page) and "@import" not in page


def test_reports_have_the_3d_view(rid, tmp_path):
    base = {"title": "Flight", "lang": "en", "theme": "light", "tabs": [{"name": "Flight", "plots": [spec3d(rid)]}]}
    html = report.build_html(store, {**base, "format": "html"})
    assert html.count('class="mapframe"') == 1 and "THREE" in html
    for fmt in ("pdf", "docx"):
        path = str(tmp_path / f"r.{fmt}")
        r = client.post("/api/report", json={**base, "format": fmt, "path": path})
        assert r.status_code == 200, r.text
        assert os.path.getsize(path) > 50_000                        # the 3D picture is in it
    # the plot's own picture and page (its ⋯ menu)
    for fmt, ext in (("png", ".png"), ("html", ".html")):
        path = str(tmp_path / f"v{ext}")
        r = client.post("/api/export/image", json={"path": path, "format": fmt, "plot": spec3d(rid)})
        assert r.status_code == 200, r.text
        assert os.path.getsize(path) > 10_000


def test_live_report_and_replay(rid):
    time_plot = {"mode": "time", "title": "Alt", "signals": [{"id": f"{rid}/POS.Alt [m]", "label": "Alt", "color": "#e5677a", "scale": 1, "offset": 0}]}
    req = {"title": "F", "lang": "en", "theme": "light", "tabs": [{"name": "F", "plots": [time_plot, spec3d(rid)]}],
           "replay": {"t": 50, "extent": [0, 300], "events": [], "compact": False, "link": False}}
    html = report.build_html(store, req)
    assert '<body class="live">' in html and 'id="rp-track"' in html           # one time for the page...
    assert "<table" in html and "Made with Signal Viewer" not in html          # ...with the report's tables and layout
    m = re.search(r'<script type="application/json" id="sv-data">(.*?)</script>', html, re.S)
    assert json.loads(m.group(1))["replay"]["link"] is False
    # a 1.25 replay request (no compact / link) is the replay as before
    req["replay"] = {"t": 50, "extent": [0, 300], "events": []}
    html = report.build_html(store, req)
    assert '<body class="replay">' in html and "Made with Signal Viewer" in html


def test_python_and_cli(tmp_path):
    import signalviewer as sv
    rec = sv.load(EX)
    png = sv.scene_image(rec, ["POS", "XKF1[0]"], str(tmp_path / "v.png"))
    page = sv.scene_html(rec, ["POS"], str(tmp_path / "v.html"))
    assert os.path.getsize(png) > 20_000 and "THREE" in open(page, encoding="utf-8").read()
    out = tmp_path / "c.png"
    env = {**os.environ, "PYTHONPATH": os.path.join(ROOT, "backend")}
    r = subprocess.run([sys.executable, "-m", "signalviewer.cli", "map", EX, "--3d", "--objects", "POS", "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=os.path.join(ROOT, "backend"))
    assert r.returncode == 0, r.stderr
    assert base64.b64encode(out.read_bytes()[:4]) == base64.b64encode(b"\x89PNG")


def test_both_pages_share_the_toolbar_and_the_relation_box(rid):
    """1.26: the 2D map's page and the 3D view's page have the same toolbar (camera Free / Centre / Close, the
    object, + − ⤢, Relation, theme) and the same relation box, started on the app's pair; tracks keep their look."""
    from app import mapimage
    sp = spec3d(rid)
    sp["geo"]["objects"][1]["track"] = "points"
    sp["scene"]["objects"][1]["track"] = "points"
    sp["geo"].update(primary="GPS[0]", secondary="POS")
    sp["scene"].update(primary="GPS[0]", secondary="POS")
    p3 = scene3d.build_html(scene3d.scene_data(store, sp), "light", "en")
    p2 = mapimage.build_html(mapimage.map_data(store, {**sp, "mode": "geo"}), "light", lang="he")
    for page in (p2, p3):
        for ident in ('id="cam"', 'data-cam="close"', 'id="obj"', 'id="zin"', 'id="zout"', 'id="fit"', 'id="rel"', 'id="theme"'):
            assert ident in page, ident
        assert "function svRelation" in page and ".svrel" in page and "/*__" not in page
    d3 = json.loads(re.search(r"const D = (\{.*?\});\n", p3, re.S).group(1))
    d2 = json.loads(re.search(r"const D = (\{.*?\});\n", p2, re.S).group(1))
    assert d3["pair"] == d2["pair"] == {"primary": "GPS[0]", "secondary": "POS"}
    assert [o["track"] for o in d3["objects"]] == [o["track"] for o in d2["objects"]] == [None, "points"]
    assert d2["S"]["camClose"] == "מרדף" and d3["S"]["camClose"] == "Chase"            # the app's words (g3CamChase)


def test_sun_where_it_was():
    """P9: NOAA's low-precision sun - two known values (within 0.5°) and the fixed mid-morning sun."""
    import datetime as dt
    f = lambda *a: dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp()     # noqa: E731
    az, el = scene3d.sun_position(f(2026, 6, 21, 12, 0), 51.48, 0.0)          # Greenwich at the solstice, noon
    assert el == pytest.approx(90 - 51.48 + 23.44, abs=0.5) and az == pytest.approx(180, abs=2)
    az, el = scene3d.sun_position(f(2026, 3, 20, 12, 7), 0.0, 0.0)           # the equator at the equinox, solar noon
    assert el == pytest.approx(90, abs=1.0)
    s = scene3d.scene_sun(150.0, 32.69, 35.39)                                # no date: 10:00 local solar at the equinox
    assert not s["dated"] and 90 < s["az"] < 150 and 35 < s["el"] < 55
    s = scene3d.scene_sun(f(2026, 6, 21, 6, 0), 32.0, 35.0)                   # a dated recording: its own sun
    assert s["dated"] and s["az"] == pytest.approx(85, abs=3) and s["el"] == pytest.approx(41, abs=2)


def test_scene_page_has_its_sun_and_wow(rid):
    sd = scene3d.scene_data(store, spec3d(rid))
    assert set(sd["sun"]) == {"az", "el", "dated"}
    html = scene3d.build_html(sd, "light", "en", fallback_png=b"x")
    for k in ('data-cam="cockpit"', 'id="disp"', 'id="errs"', 'id="mini"', "glideTo", '"sun":'):
        assert k in html, k
