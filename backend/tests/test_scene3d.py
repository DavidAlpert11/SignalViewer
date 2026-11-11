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
                       capture_output=True, text=True, env=env, cwd=os.path.join(ROOT, "backend"))
    assert r.returncode == 0, r.stderr
    assert base64.b64encode(out.read_bytes()[:4]) == base64.b64encode(b"\x89PNG")
