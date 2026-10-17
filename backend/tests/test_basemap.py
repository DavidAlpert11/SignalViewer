"""The offline map: tiles drawn from bundled data, correct water / land, names in Hebrew."""
import io
import math
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app import basemap  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
pytestmark = pytest.mark.skipif(not basemap.available(), reason="offline map data not built")
WATER = (170, 203, 230)


def _tile_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _pixel(lat, lon, z):
    """Colour of the offline map at a place."""
    from PIL import Image
    fx, fy = _tile_xy(lat, lon, z)
    x, y = int(fx), int(fy)
    img = Image.open(io.BytesIO(basemap.render_tile("offline_topo", z, x, y))).convert("RGB")
    return img.getpixel((min(255, int((fx - x) * 256)), min(255, int((fy - y) * 256))))


def _is_water(c):
    return all(abs(a - b) <= 12 for a, b in zip(c, WATER))


@pytest.mark.parametrize("name,lat,lon,z,water", [
    ("Mediterranean off Tel Aviv", 32.10, 34.60, 10, True),
    ("Jerusalem", 31.77, 35.21, 10, False),
    ("Dead Sea (a lake below sea level)", 31.50, 35.48, 10, True),
    ("Jericho (land below sea level)", 31.86, 35.45, 10, False),
    ("Kinneret", 32.82, 35.59, 11, True),
    ("Gulf of Eilat", 29.40, 34.92, 10, True),
    ("Negev", 30.60, 34.80, 9, False),
    ("Atlantic (world layer)", 40.0, -40.0, 3, True),
    ("Sahara (world layer)", 24.0, 12.0, 4, False),
])
def test_water_and_land_where_they_are(name, lat, lon, z, water):
    assert _is_water(_pixel(lat, lon, z)) == water, name


def test_tiles_are_served_and_kept(tmp_path, monkeypatch):
    from app import tiles
    monkeypatch.setattr(tiles, "CACHE", str(tmp_path))
    r = client.get("/api/tiles/offline_topo/9/305/209")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and len(r.content) > 2000
    kept = [os.path.join(d, f) for d, _s, fs in os.walk(tmp_path) for f in fs]
    assert len(kept) == 1 and kept[0].endswith(os.path.join("9", "305", "209.jpg"))
    assert client.get("/api/tiles/offline_topo_dark/9/305/209").status_code == 200
    assert client.get("/api/tiles/offline_topo/15/0/0").status_code == 404       # beyond the data's detail


def test_places_have_hebrew_names():
    p = client.get("/api/basemap/places").json()
    by_he = {x["h"]: x for x in p["places"] if x["h"]}
    for he in ("ירושלים", "חיפה", "באר שבע"):
        assert he in by_he, he
    assert any(x.get("a") for x in p["places"])                                  # airports too
    assert "OpenStreetMap" in p["attribution"]


def test_more_area_packs_are_picked_up(tmp_path, monkeypatch):
    """A pack folder (pack.json + dem*.npz + vectors.json.gz) adds detail where it covers; a folder
    without a valid pack.json is skipped."""
    import gzip
    import json
    import numpy as np
    data = tmp_path / "data"
    (data / "packs" / "testland").mkdir(parents=True)
    (data / "packs" / "broken").mkdir()
    for f in os.listdir(basemap.DATA):                       # the real world data next to the pack
        if not os.path.isdir(os.path.join(basemap.DATA, f)):
            try:
                os.symlink(os.path.join(basemap.DATA, f), data / f)
            except OSError:          # Windows: symlinks need admin rights or Developer Mode
                shutil.copy(os.path.join(basemap.DATA, f), data / f)
    # a 1000 m plateau in the open sea (33.0-33.2 N, 30.0-30.2 E) with one main road across it
    b = [33.0, 30.0, 33.2, 30.2]
    np.savez_compressed(data / "packs" / "testland" / "dem.npz", h=np.full((161, 161), 1000, dtype=np.int16),
                        bounds=np.array(b, dtype=np.float64), step=np.float64(0.00125))
    road = [[int(v * 1e5) for v in pt] for pt in ((30.0, 33.1), (30.2, 33.1))]
    with gzip.open(data / "packs" / "testland" / "vectors.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"roads": [{"k": 1, "c": [c for pt in road for c in pt]}], "places": [{"x": 30.1, "y": 33.1, "n": "Testville", "h": "בדיקה", "k": 1, "p": 500000}],
                   "airports": [], "runways": []}, f)
    (data / "packs" / "testland" / "pack.json").write_text(json.dumps({"name": "testland", "bounds": b}))
    (data / "packs" / "broken" / "pack.json").write_text("{ not json")
    monkeypatch.setattr(basemap, "DATA", str(data))
    monkeypatch.setattr(basemap, "_grids", None)
    monkeypatch.setattr(basemap, "_layers", None)
    assert [p["name"] for p in basemap._packs()] == ["israel", "testland"]
    assert abs(float(basemap.ground_at(np.array([33.1]), np.array([30.1]))[0]) - 1000) < 1
    assert any(p["n"] == "Testville" and p["h"] == "בדיקה" for p in basemap.places()["places"])
    # the road is drawn (main-road orange) where the pack says, at zoom 11
    from PIL import Image
    fx, fy = _tile_xy(33.1, 30.1, 11)
    img = np.asarray(Image.open(io.BytesIO(basemap.render_tile("offline_topo", 11, int(fx), int(fy)))).convert("RGB")).astype(int)
    row = int((fy - int(fy)) * 256)
    band = img[max(0, row - 3):row + 4].reshape(-1, 3)
    assert ((band[:, 0] > 190) & (band[:, 1] > 90) & (band[:, 1] < 160) & (band[:, 2] < 110)).sum() > 50
