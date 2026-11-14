"""M3 - *Keep this area offline*: an area's tiles downloaded into the cache before going to the field, only from
sources whose terms allow bulk downloading; the kept area then shows with "Never use the network" on; the list of
kept areas and Delete. The tile server is a stand-in (urlopen replaced): nothing leaves the PC."""
import os
import sys
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import prefs, tilekeep, tiles  # noqa: E402

AREA = [32.00, 34.80, 32.02, 34.83]           # ~2 x 3 km


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b"\x89PNG-tile"


@pytest.fixture
def server(tmp_path, monkeypatch):
    calls = []

    def fake(req, timeout=0):
        calls.append(req.full_url)
        return _Resp()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(tiles, "CACHE", str(tmp_path / "tiles"))
    monkeypatch.setattr(tiles, "_offline_until", 0.0)
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("SV_OFFLINE", raising=False)
    tiles._policy_cache.clear()
    tilekeep._job.clear()
    tilekeep._job["running"] = False
    return calls


def _wait():
    for _ in range(200):
        if not tilekeep.progress().get("running"):
            return tilekeep.progress()
        time.sleep(0.02)
    raise AssertionError("the download did not end")


def test_estimate_counts_tiles_and_says_why_not(server):
    e = tilekeep.estimate("terrarium", AREA, 10, 12)
    assert e["allowed"] and e["tiles"] == tilekeep.count(AREA, 10, 12) and e["tiles"] >= 3 and e["bytes"] > 0
    for src in ("osm", "satellite", "satroads", "topo", "esri"):
        e = tilekeep.estimate(src, AREA, 10, 12)
        assert e["allowed"] is False and ("bulk" in e["reason"] or "offline use" in e["reason"])
    assert server == []                                  # an estimate never downloads


def test_refused_sources_send_nothing(server):
    with pytest.raises(ValueError, match="forbid bulk"):
        tilekeep.start("osm", AREA, 10, 12)
    assert server == [] and tilekeep.areas() == []


def test_kept_area_shows_with_the_network_off_and_deletes(server):
    a = tilekeep.start("terrarium", AREA, 10, 12, "Field A")
    p = _wait()
    assert p["done"] == a["tiles"] and p["failed"] == 0 and len(server) == a["tiles"]
    [kept] = tilekeep.areas()
    assert kept["name"] == "Field A" and kept["present"] == a["tiles"] and kept["bytes"] > 0
    prefs.update_ui_settings({"offlineOnly": True})
    tiles._policy_cache.clear()
    z, x0, _x1, y0, _y1 = tilekeep.tile_ranges(AREA, 12, 12)[0]
    os.utime(tilekeep._path("terrarium", z, x0, y0), (0, 0))              # old: would be refreshed if online
    assert tiles.tile("terrarium", z, x0, y0) is not None and len(server) == a["tiles"]
    with pytest.raises(ValueError, match="Never use the network"):
        tilekeep.start("terrarium", AREA, 10, 12)
    out = tilekeep.delete(kept["id"])
    assert out["removed"] == a["tiles"] and tilekeep.areas() == []
    with pytest.raises(KeyError):
        tilekeep.delete(kept["id"])


def test_overlapping_areas_keep_shared_tiles(server):
    a = tilekeep.start("terrarium", AREA, 11, 12, "A"); _wait()
    b = tilekeep.start("terrarium", AREA, 12, 12, "B"); _wait()
    assert len(server) == a["tiles"]                       # B's tiles were kept already: not fetched twice
    tilekeep.delete(a["id"])
    [left] = tilekeep.areas()
    assert left["id"] == b["id"] and left["present"] == b["tiles"]


def test_too_big_and_bad_areas_are_explained(server):
    with pytest.raises(ValueError, match="smaller area"):
        tilekeep.start("terrarium", [-60, -170, 70, 170], 0, 15)
    with pytest.raises(ValueError, match="south < north"):
        tilekeep.estimate("terrarium", [32, 35, 31, 34], 10, 12)
    with pytest.raises(ValueError, match="zoom range"):
        tilekeep.estimate("terrarium", AREA, 12, 10)


def test_stop_ends_the_download(server, monkeypatch):
    real = tiles.tile

    def slow(*a, **k):
        time.sleep(0.01)
        return real(*a, **k)
    monkeypatch.setattr(tiles, "tile", slow)
    a = tilekeep.start("terrarium", AREA, 10, 15)
    tilekeep.stop()
    p = _wait()
    assert p["stopped"] and p["done"] < a["tiles"]


def test_routes(server):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    e = c.post("/api/tiles/keep/estimate", json={"src": "osm", "bounds": AREA, "zmin": 10, "zmax": 12}).json()
    assert e["allowed"] is False
    r = c.post("/api/tiles/keep", json={"src": "osm", "bounds": AREA, "zmin": 10, "zmax": 12})
    assert r.status_code == 400 and "bulk" in r.json()["detail"]
    r = c.post("/api/tiles/keep", json={"src": "terrarium", "bounds": AREA, "zmin": 10, "zmax": 11, "name": "X"})
    assert r.status_code == 200
    _wait()
    assert c.get("/api/tiles/keep/progress").json()["done"] == r.json()["tiles"]
    [a] = c.get("/api/tiles/areas").json()["areas"]
    assert c.delete(f"/api/tiles/areas/{a['id']}").json()["removed"] == a["present"]
    assert c.delete(f"/api/tiles/areas/{a['id']}").status_code == 404
