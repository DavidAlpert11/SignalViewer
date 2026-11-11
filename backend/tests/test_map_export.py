"""L11: a map plot drawn by the server - PNG with the offline basemap (no network), the standalone HTML map
(tiles embedded, no outside URL), and maps in HTML / PDF / Word reports. On the fixture ardupilot_lanes.csv."""
import io
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.csv_loader import load_csv  # noqa: E402

client = TestClient(app)
EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "ardupilot_lanes.csv")


@pytest.fixture(scope="module")
def rid(tmp_path_factory):
    os.environ["SV_OFFLINE"] = "1"                         # the renderer must not need the network
    r = load_csv(EX, [EX])
    run = store.add_pushed("ardupilot_lanes", r)[0]
    yield run.id
    store.remove(run.id)


def _spec(rid, **geo):
    return {"mode": "geo", "title": "Lanes", "signals": [], "geo": {
        "objects": [{"name": "POS", "color": "#e5677a", "lat": f"{rid}/POS.Lat [deg]", "lon": f"{rid}/POS.Lng [deg]", "alt": f"{rid}/POS.Alt [m]"},
                    {"name": "GPS", "color": "#3d8bfd", "lat": f"{rid}/GPS[0].Lat [deg]", "lon": f"{rid}/GPS[0].Lng [deg]"}],
        "base": "offline", "cursor": 100.0, **geo}}


def test_png_with_offline_basemap_and_tracks(rid, tmp_path):
    from PIL import Image
    path = os.environ.get("SV_MAP_PNG") or str(tmp_path / "map.png")
    r = client.post("/api/export/image", json={"path": path, "format": "png", "plot": _spec(rid)})
    assert r.status_code == 200, r.text
    im = np.asarray(Image.open(path).convert("RGB")).astype(int)
    assert im.shape[1] >= 900 and im.shape[0] >= 600
    assert im.std() > 10                                                # not blank: tiles and tracks
    # GPS (blue) is drawn last, over POS on the same circle: its colour is the track's
    blue = (abs(im[..., 0] - 0x3D) < 25) & (abs(im[..., 1] - 0x8B) < 25) & (abs(im[..., 2] - 0xFD) < 25)
    assert blue.sum() > 500
    ys, xs = np.nonzero(blue)
    assert 0.1 < xs.mean() / im.shape[1] < 0.9 and 0.1 < ys.mean() / im.shape[0] < 0.9   # inside the view


def test_html_map_is_standalone(rid, tmp_path):
    path = str(tmp_path / "map.html")
    r = client.post("/api/export/image", json={"path": path, "format": "html", "plot": _spec(rid)})
    assert r.status_code == 200, r.text
    text = open(path, encoding="utf-8").read()
    assert 'src="http' not in text and "href=\"http" not in text and "<link" not in text   # nothing loaded from outside
    assert "data:image/jpeg;base64," in text and "Embedded:" in text and "Natural Earth" in text
    assert len(text) < 16 * 1024 * 1024


def test_a_map_with_nothing_to_draw_is_refused(rid, tmp_path):
    spec = _spec(rid)
    spec["geo"]["objects"] = []
    r = client.post("/api/export/image", json={"path": str(tmp_path / "x.png"), "format": "png", "plot": spec})
    assert r.status_code == 400


@pytest.mark.parametrize("fmt", ["html", "pdf", "docx"])
def test_reports_contain_the_map(rid, tmp_path, fmt):
    if fmt == "docx":
        pytest.importorskip("docx")
    path = str(tmp_path / f"report.{fmt}")
    body = {"path": path, "format": fmt, "title": "R", "tabs": [{"name": "Map", "plots": [_spec(rid)]}]}
    r = client.post("/api/report", json=body)
    assert r.status_code == 200, r.text
    raw = open(path, "rb").read()
    if fmt == "html":
        text = raw.decode("utf-8")
        assert 'class="mapframe"' in text and "Embedded:" in text
    elif fmt == "pdf":
        assert raw[:4] == b"%PDF" and b"/Image" in raw                    # the map as a picture
    else:
        import zipfile
        assert any(n.startswith("word/media/") for n in zipfile.ZipFile(io.BytesIO(raw)).namelist())
