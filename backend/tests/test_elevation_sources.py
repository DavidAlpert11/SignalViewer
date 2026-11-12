"""P5 (1.26): a ground with relief anywhere - the user's SRTM .hgt files and terrarium tiles (fetched only
when the network is allowed, kept in the tile cache), the finest source winning; `step_at` says how fine
the ground is. No test touches the real network: urlopen is replaced by a fake terrarium tile."""
import io
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import basemap, tiles  # noqa: E402

FAR = (45.5, 124.3)                       # outside every bundled fine grid: only the 11 km world grid


def _png(height: float) -> bytes:
    from PIL import Image
    v = height + 32768.0
    r, g = int(v // 256), int(v % 256)
    img = Image.new("RGB", (256, 256), (r, g, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class _Resp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A temp tile cache, no elevation folder, the network allowed - and urlopen faked."""
    calls = []
    monkeypatch.delenv("SV_OFFLINE", raising=False)
    monkeypatch.setattr(tiles, "CACHE", str(tmp_path / "tiles"))
    monkeypatch.setattr(tiles, "network_allowed", lambda: not tiles.offline_forced())
    monkeypatch.setattr(tiles, "_offline_until", 0.0)
    monkeypatch.setattr(basemap, "elevation_folder", lambda: str(tmp_path / "terrain"))
    monkeypatch.setattr(tiles.urllib.request, "urlopen", lambda req, timeout=8: (calls.append(req.full_url), _Resp(_png(1234.0)))[1])
    basemap._TR_MEM.clear()
    basemap._HGT.clear()
    yield calls
    basemap._TR_MEM.clear()
    basemap._HGT.clear()


def test_step_at_with_nothing_but_the_bundled_grids(sandbox):
    assert basemap.step_at(32.8, 35.6) == 139
    assert basemap.step_at(*FAR) > 1000


def test_terrarium_is_fetched_in_the_background_and_then_used(sandbox):
    lat, lon = np.array([FAR[0]]), np.array([FAR[1]])
    first = basemap.ground_at(lat, lon)
    assert abs(float(first[0]) - 1234.0) > 1                    # the first answer: what is there (the world grid)
    v0 = basemap.terrain_version()
    basemap.wait_terrain()
    assert sandbox and "terrarium/12/" in sandbox[0]
    assert basemap.terrain_version() > v0
    assert float(basemap.ground_at(lat, lon)[0]) == pytest.approx(1234.0, abs=0.5)
    assert basemap.step_at(*FAR) < 100                          # the cached tile: ~27 m here
    # where the bundled fine grid is, it wins
    assert float(basemap.ground_at(np.array([32.8]), np.array([35.6]))[0]) != pytest.approx(1234.0, abs=0.5)


def test_never_fetched_when_offline_is_forced(sandbox, monkeypatch):
    monkeypatch.setenv("SV_OFFLINE", "1")
    basemap.ground_at(np.array([FAR[0]]), np.array([FAR[1]]))
    basemap.terrain_tile(10, 865, 360)
    basemap.wait_terrain()
    assert sandbox == []


def test_an_hgt_file_is_found_and_used(sandbox, tmp_path, monkeypatch):
    monkeypatch.setenv("SV_OFFLINE", "1")
    d = tmp_path / "terrain"
    d.mkdir()
    h = np.full((1201, 1201), 777, dtype=">i2")
    h[0, 0] = -32768                                              # a void
    (d / "N45E124.hgt").write_bytes(h.tobytes())
    assert basemap.elevation_files() == [{"name": "N45E124.hgt", "lat": 45, "lon": 124, "step": 92.8}]
    assert float(basemap.ground_at(np.array([FAR[0]]), np.array([FAR[1]]))[0]) == pytest.approx(777.0)
    assert basemap.step_at(*FAR) == 93
    assert sandbox == []


# ------------------------------------------------------------------ the page's ground (P5.3 / P5.4)
def _scene(tmp_path, csv_text=None):
    from fastapi.testclient import TestClient

    from app import scene3d
    from app.main import app
    from app.store import store
    client = TestClient(app)
    if csv_text is None:
        path = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "ardupilot_lanes.csv")
    else:
        path = str(tmp_path / "far.csv")
        open(path, "w").write(csv_text)
    run = client.post("/api/files/open", json={"paths": [os.path.abspath(path)]}).json()["opened"][0]["id"]
    names = list(store.get(run).run.signals)
    pick = lambda k: f"{run}/" + next(n for n in names if n.startswith(k))
    objs = [{"name": "POS", "color": "#0072B2", "lat": pick("POS.Lat"), "lon": pick("POS.Lng"), "alt": pick("POS.Alt")}]
    sd = scene3d.scene_data(store, {"mode": "3d", "title": "t", "signals": [], "geo": {"objects": objs}, "scene": {"objects": objs}})
    return client, run, sd


def test_the_far_ground_reaches_the_horizon(tmp_path):
    from app import scene3d
    client, run, sd = _scene(tmp_path)
    try:
        f = sd["far"]
        assert f["extent"][1] - f["extent"][0] >= 40_000
        assert float(f["heights"].max() - f["heights"].min()) > 300
        page = scene3d.build_html(sd, fallback_png=b"x")
        assert "scene.fog = new T.Fog" in page and '"far":{' in page and '"step":139' in page
        assert len(scene3d.render(sd, "png")) > 10_000                 # the picture draws the far ground too
    finally:
        client.delete(f"/api/runs/{run}")


def test_a_coarse_ground_says_so(tmp_path):
    from app import scene3d
    rows = ["t,POS.Lat,POS.Lng,POS.Alt"] + [f"{k},{FAR[0] + k * 1e-4},{FAR[1] + k * 1e-4},300" for k in range(60)]
    client, run, sd = _scene(tmp_path, "\n".join(rows) + "\n")
    try:
        assert sd["step"] > 1000
        page = scene3d.build_html(sd, fallback_png=b"x")
        assert "Only coarse heights here" in page and '"step":11132' in page
    finally:
        client.delete(f"/api/runs/{run}")
