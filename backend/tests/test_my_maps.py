"""M4 - *My maps*: a raster MBTiles file (fully offline) and the user's own tile server, used like any map layer
("my:<id>"): the tile route, the exported picture's tiles, keeping a server's area offline; "Never use the network"
blocks a server on the internet but not one on this PC / the local network; vector MBTiles refused with what to do."""
import io
import os
import sqlite3
import sys
import urllib.request

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import mapimage, mymaps, prefs, tilekeep, tiles  # noqa: E402


def _png(rgb) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (256, 256), rgb).save(b, "PNG")
    return b.getvalue()


def make_mbtiles(path, fmt="png", tiles_=((3, 4, 2, (200, 10, 10)),)):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE metadata (name text, value text)")
    con.execute("CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob)")
    con.executemany("INSERT INTO metadata VALUES (?, ?)", [("name", "Base map"), ("format", fmt), ("minzoom", "0"),
                                                          ("maxzoom", "12"), ("bounds", "34.0,31.0,35.0,32.0"),
                                                          ("attribution", "© Our GIS department")])
    for z, x, y, rgb in tiles_:
        con.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (z, x, 2 ** z - 1 - y, _png(rgb)))
    con.commit()
    con.close()
    return str(path)


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return _png((10, 10, 200))


@pytest.fixture
def env(tmp_path, monkeypatch):
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
    mymaps._failed_until.clear()
    tilekeep._job.clear()
    tilekeep._job["running"] = False
    return tmp_path, calls


def _offline():
    prefs.update_ui_settings({"offlineOnly": True})
    tiles._policy_cache.clear()


def test_mbtiles_draws_offline_with_its_attribution(env):
    tmp, calls = env
    m = mymaps.add("mbtiles", make_mbtiles(tmp / "base.mbtiles"))
    assert m["name"] == "Base map" and m["maxzoom"] == 12 and m["bounds"] == [31.0, 34.0, 32.0, 35.0] and m["localOnly"]
    _offline()
    data, media = tiles.tile(m["src"], 3, 4, 2)                     # rows are flipped (TMS) inside the file
    assert media == "image/png" and Image.open(io.BytesIO(data)).getpixel((5, 5))[:3] == (200, 10, 10)
    assert tiles.tile(m["src"], 3, 4, 3) is None and tiles.tile(m["src"], 13, 0, 0) is None
    assert mapimage.tile_bytes(m["src"], False, 3, 4, 2) == (data, m["src"])     # the exported picture / page
    assert mapimage.attribution(m["src"]) == "© Our GIS department" and mapimage.max_zoom(m["src"]) == 12
    assert calls == []
    ok, why = tilekeep.allowed(m["src"])
    assert not ok and "offline already" in why


def test_vector_and_broken_files_are_explained(env):
    tmp, _ = env
    with pytest.raises(ValueError, match="vector tiles"):
        mymaps.add("mbtiles", make_mbtiles(tmp / "v.mbtiles", fmt="pbf"))
    (tmp / "junk.mbtiles").write_bytes(b"not sqlite at all, just bytes" * 10)
    with pytest.raises(ValueError, match="Not an MBTiles"):
        mymaps.add("mbtiles", str(tmp / "junk.mbtiles"))
    with pytest.raises(ValueError, match="File not found"):
        mymaps.add("mbtiles", str(tmp / "none.mbtiles"))
    m = mymaps.add("mbtiles", make_mbtiles(tmp / "gone.mbtiles"))
    os.remove(tmp / "gone.mbtiles")
    [row] = mymaps.listing()
    assert row["id"] == m["id"] and row["ok"] is False and "File not found" in row["problem"]


def test_a_server_on_the_internet_is_blocked_offline_a_local_one_is_not(env):
    _, calls = env
    far = mymaps.add("xyz", url="https://maps.example.org/t/{z}/{x}/{y}.png", name="Far")
    near = mymaps.add("tms", url="http://192.168.1.20/tiles/{z}/{x}/{y}.png")
    assert near["url"].endswith("{-y}.png") and near["localOnly"] and not far["localOnly"]
    assert tiles.tile(far["src"], 3, 4, 2) is not None and calls[-1] == "https://maps.example.org/t/3/4/2.png"
    _offline()
    n = len(calls)
    assert tiles.tile(far["src"], 3, 4, 2) is not None and len(calls) == n           # from the cache
    assert tiles.tile(far["src"], 3, 4, 1) is None and len(calls) == n               # blocked
    assert tiles.tile(near["src"], 3, 4, 2) is not None and calls[-1] == "http://192.168.1.20/tiles/3/4/5.png"


def test_keep_a_servers_area_offline(env):
    _, calls = env
    m = mymaps.add("xyz", url="http://localhost:8080/{z}/{x}/{y}.png")
    _offline()                                                   # a local server: allowed even so
    area = tilekeep.start(m["src"], [32.0, 34.8, 32.02, 34.83], 10, 12, "Field")
    import time
    for _ in range(200):
        if not tilekeep.progress()["running"]:
            break
        time.sleep(0.02)
    assert tilekeep.progress()["done"] == area["tiles"] and len(calls) == area["tiles"]
    [kept] = tilekeep.areas()
    assert kept["present"] == area["tiles"]
    mymaps.remove(m["src"])
    assert mymaps.listing() == [] and not os.path.isdir(os.path.join(tiles.CACHE, "my-" + m["id"]))


def test_bad_addresses_and_routes(env):
    with pytest.raises(ValueError, match=r"\{z\}"):
        mymaps.add("xyz", url="http://maps.local/tiles/")
    with pytest.raises(ValueError, match="http"):
        mymaps.add("xyz", url="ftp://maps.local/{z}/{x}/{y}")
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    tmp, _ = env
    r = c.post("/api/mymaps", json={"kind": "mbtiles", "path": make_mbtiles(tmp / "a.mbtiles")})
    assert r.status_code == 200
    src = r.json()["src"]
    assert c.get(f"/api/tiles/{src}/3/4/2").status_code == 200
    assert c.get(f"/api/tiles/{src}/3/4/3").status_code == 404
    assert [m["src"] for m in c.get("/api/mymaps").json()["maps"]] == [src]
    assert c.post("/api/mymaps", json={"kind": "xyz", "url": "nope"}).status_code == 400
    assert c.delete(f"/api/mymaps/{src}").json()["maps"] == []
    assert c.delete(f"/api/mymaps/{src}").status_code == 404
