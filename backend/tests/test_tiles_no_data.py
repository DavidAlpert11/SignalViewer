"""Esri's "Map data not yet available" tiles (grey #CCCCCC with words, an ordinary 200 JPEG where a source has no
picture at that zoom) are never shown or kept: the parent tile, enlarged, is drawn instead. No real network."""
import io
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import tiles  # noqa: E402


def _jpeg(rgb) -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (256, 256), rgb)
    if rgb == (204, 204, 204):                                   # the placeholder's words
        d = ImageDraw.Draw(img)
        for k in range(6):
            d.text((20 + 30 * k, 40 * k), "Map data not yet available", fill=(255, 255, 255))
    else:                                                        # a picture: texture, not flat
        a = np.asarray(img).astype(np.int16) + np.random.default_rng(1).integers(-40, 40, (256, 256, 3))
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


PLACEHOLDER, GREEN = _jpeg((204, 204, 204)), _jpeg((40, 140, 60))


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
def net(tmp_path, monkeypatch):
    """A temp cache, the network allowed, and an imagery server with pictures up to zoom 17 only."""
    calls = []

    def urlopen(req, timeout=8):
        z = int(req.full_url.split("/tile/")[1].split("/")[0])
        calls.append(z)
        return _Resp(GREEN if z <= 17 else PLACEHOLDER)
    monkeypatch.delenv("SV_OFFLINE", raising=False)
    monkeypatch.setattr(tiles, "CACHE", str(tmp_path / "tiles"))
    monkeypatch.setattr(tiles, "network_allowed", lambda: True)
    monkeypatch.setattr(tiles, "_offline_until", 0.0)
    monkeypatch.setattr(tiles.urllib.request, "urlopen", urlopen)
    tiles._checked.clear()
    return calls


def _mean(data: bytes):
    from PIL import Image
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"), dtype=float).reshape(-1, 3).mean(axis=0)


def test_the_placeholder_is_told_from_a_picture():
    assert tiles.is_no_data(PLACEHOLDER) and not tiles.is_no_data(GREEN)


def test_no_picture_at_a_zoom_draws_the_parent_enlarged(net, tmp_path):
    got = tiles.tile("satellite", 18, 1000, 2000)
    assert got and got[1] == "image/jpeg"
    r, g, b = _mean(got[0])
    assert g > r + 50 and g > b + 50                              # the green parent, not the grey placeholder
    assert net == [18, 17]
    base = tmp_path / "tiles" / "satellite"
    assert not (base / "18" / "1000" / "2000.jpg").exists()      # the placeholder is not kept
    assert (base / "18" / "1000" / "2000.jpg.nodata").exists() and (base / "17" / "500" / "1000.jpg").exists()
    net.clear()
    assert tiles.tile("satellite", 18, 1001, 2000)                # its sibling: the parent from the cache
    assert tiles.tile("satellite", 18, 1000, 2000) and net == [18]   # the known one: not asked again
    assert tiles.tile("satellite", 19, 2000, 4000)                # one more level: enlarged from 17 through 18


def test_a_placeholder_kept_by_an_older_version_is_put_right(net, tmp_path):
    p = tmp_path / "tiles" / "satellite" / "18" / "7" / "9.jpg"
    p.parent.mkdir(parents=True)
    p.write_bytes(PLACEHOLDER)
    got = tiles.tile("satellite", 18, 7, 9)
    assert got and not tiles.is_no_data(got[0]) and not p.exists() and (p.parent / "9.jpg.nodata").exists()
