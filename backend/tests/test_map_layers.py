"""M2 - *Satellite + roads*: the imagery with Esri's transparent roads layer composed over it, in one tile
(the 2D map, the 3D globe, the exported picture and the offline page all ask the same tile). Fetched through
the app like any online layer, blocked by "Never use the network", the cached parts still shown offline."""
import io
import os
import sys
import urllib.request

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import mapimage, prefs, tiles  # noqa: E402


def _png(rgba) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", (256, 256), rgba).save(b, "PNG")
    return b.getvalue()


def _jpg(rgb) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (256, 256), rgb).save(b, "JPEG")
    return b.getvalue()


PHOTO = _jpg((0, 120, 0))
ROADS = _png((255, 255, 255, 255))         # an opaque "road" everywhere: easy to see in the result
NOROAD = _png((0, 0, 0, 0))


class _Resp:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.data


@pytest.fixture
def net(tmp_path, monkeypatch):
    calls = []
    answers = {"World_Imagery": PHOTO, "World_Transportation": ROADS}

    def fake(req, timeout=0):
        calls.append(req.full_url)
        for k, v in answers.items():
            if k in req.full_url:
                if v is None:
                    raise OSError("no network")
                return _Resp(v)
        raise OSError("unexpected " + req.full_url)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(tiles, "CACHE", str(tmp_path / "tiles"))
    monkeypatch.setattr(tiles, "_offline_until", 0.0)
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    monkeypatch.delenv("SV_OFFLINE", raising=False)
    tiles._policy_cache.clear()
    return calls, answers


def _pixel(data: bytes):
    return Image.open(io.BytesIO(data)).convert("RGB").getpixel((10, 10))


def test_satellite_and_roads_compose_into_one_tile(net):
    calls, _ = net
    data, media = tiles.tile("satroads", 5, 3, 4)
    assert media == "image/jpeg"
    assert min(_pixel(data)) > 230                              # the roads layer lies over the photo
    assert any("World_Imagery" in u for u in calls) and any("World_Transportation" in u for u in calls)
    assert os.path.isfile(os.path.join(tiles.CACHE, "satellite", "5", "3", "4.jpg"))      # each part kept for offline
    assert os.path.isfile(os.path.join(tiles.CACHE, "sat_roads", "5", "3", "4.png"))


def test_transparent_roads_leave_the_photo(net):
    net[1]["World_Transportation"] = NOROAD
    r, g, b = _pixel(tiles.tile("satroads", 5, 3, 4)[0])
    assert g > 90 and r < 40 and b < 40


def test_photo_alone_when_the_roads_cannot_be_had(net):
    net[1]["World_Transportation"] = None
    data, media = tiles.tile("satroads", 5, 3, 4)
    assert data == PHOTO and media == "image/jpeg"


def test_never_use_the_network_blocks_both_but_shows_what_was_seen(net):
    calls, _ = net
    assert tiles.tile("satroads", 5, 3, 4) is not None
    n = len(calls)
    prefs.update_ui_settings({"offlineOnly": True})
    tiles._policy_cache.clear()
    assert min(_pixel(tiles.tile("satroads", 5, 3, 4)[0])) > 230      # from the disk
    assert tiles.tile("satroads", 5, 3, 5) is None and len(calls) == n


def test_export_reads_the_composed_tile_from_the_cache_only(net):
    calls, _ = net
    tiles.tile("satroads", 5, 3, 4)
    n = len(calls)
    data, src = mapimage.tile_bytes("satroads", False, 5, 3, 4)
    assert src == "satroads" and data and min(_pixel(data)) > 230 and len(calls) == n
    assert "satroads" in mapimage.ATTRIB
