"""O1: "Never use the network" - the only network access of the app is the map tiles of an online
layer (app/tiles.py). With the setting (ui_settings `offlineOnly`) or SV_OFFLINE=1 no request leaves
the PC: a tile already cached is still served (it is on the disk), nothing is downloaded."""
import os
import sys
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import prefs, tiles  # noqa: E402


@pytest.fixture
def net(tmp_path, monkeypatch):
    calls = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"PNGDATA"

    def fake(req, timeout=0):
        calls.append(req.full_url)
        return Resp()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(tiles, "CACHE", str(tmp_path / "tiles"))
    monkeypatch.setattr(tiles, "_offline_until", 0.0)
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("SV_OFFLINE", raising=False)
    tiles._policy_cache.clear()
    return calls


def test_online_layer_downloads_when_allowed(net):
    assert tiles.network_allowed() is True
    assert tiles.tile("osm", 3, 4, 2) == (b"PNGDATA", "image/png") and len(net) == 1


def test_setting_blocks_every_download(net):
    prefs.update_ui_settings({"offlineOnly": True})
    tiles._policy_cache.clear()
    assert tiles.network_allowed() is False
    assert tiles.tile("osm", 3, 4, 2) is None and net == []
    assert tiles.tile("offline_topo", 0, 0, 0) is not None and net == []     # the bundled map still draws


def test_env_blocks_and_cached_tiles_still_show(net, monkeypatch):
    assert tiles.tile("osm", 3, 4, 2) is not None and len(net) == 1          # cached while online
    monkeypatch.setenv("SV_OFFLINE", "1")
    tiles._policy_cache.clear()
    assert tiles.network_allowed() is False and tiles.offline_forced() is True
    os.utime(os.path.join(tiles.CACHE, "osm", "3", "4", "2.png"), (0, 0))     # old: would be refreshed
    assert tiles.tile("osm", 3, 4, 2) == (b"PNGDATA", "image/png") and len(net) == 1
    assert tiles.tile("osm", 3, 4, 3) is None and len(net) == 1


def test_settings_endpoint_says_when_the_environment_forces_it(net, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.get("/api/settings").json()["offlineForced"] is False
    monkeypatch.setenv("SV_OFFLINE", "1")
    assert c.get("/api/settings").json()["offlineForced"] is True
