"""
Map tiles for the Geo plot, fetched through the app (so the page needs no outside access) and kept
in a disk cache (~/.signalviewer/tiles), so places already seen stay available without internet.

Every source asks for attribution, which the map shows. (CARTO's basemaps now need an API key, so
the light / dark maps are Esri's grey canvases.) OpenStreetMap's tile servers are for light
use: the cache, a real User-Agent and no bulk downloading keep within their policy.
"""
import os
import threading
import time
import urllib.request
from typing import Optional

from app.prefs import APP_DIR

CACHE = os.path.join(APP_DIR, "tiles")
UA = "SignalViewer/1 (desktop flight-data viewer; tiles cached locally)"

_ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/{svc}/MapServer/tile/{{z}}/{{y}}/{{x}}"
SOURCES: dict = {
    "osm": {"url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "max": 19, "ext": "png"},
    "esri": {"url": _ESRI.format(svc="World_Street_Map"), "max": 19, "ext": "jpg"},
    # Esri's grey canvases: the map and its labels are two layers (the labels are drawn on top)
    "light": {"url": _ESRI.format(svc="Canvas/World_Light_Gray_Base"), "max": 16, "ext": "jpg"},
    "light_ref": {"url": _ESRI.format(svc="Canvas/World_Light_Gray_Reference"), "max": 16, "ext": "png"},
    "dark": {"url": _ESRI.format(svc="Canvas/World_Dark_Gray_Base"), "max": 16, "ext": "jpg"},
    "dark_ref": {"url": _ESRI.format(svc="Canvas/World_Dark_Gray_Reference"), "max": 16, "ext": "png"},
    "satellite": {"url": _ESRI.format(svc="World_Imagery"), "max": 19, "ext": "jpg"},
    "topo": {"url": "https://tile.opentopomap.org/{z}/{x}/{y}.png", "max": 17, "ext": "png"},
}
_MAX_AGE = 30 * 24 * 3600          # refresh a cached tile after a month (when online)
_offline_until = 0.0               # after a failure, do not try the network again for a while
_lock = threading.Lock()


def tile(src: str, z: int, x: int, y: int) -> Optional[tuple]:
    """(bytes, media type) of a tile, or None when it is not available (offline and not cached)."""
    global _offline_until
    from app import basemap
    if src in basemap.STYLES:                                   # drawn here from bundled data: no network
        if not (0 <= z <= basemap.MAX_ZOOM) or not (0 <= x < 2 ** z) or not (0 <= y < 2 ** z):
            return None
        path = os.path.join(CACHE, f"{src}-{basemap.data_version()}", str(z), str(x), f"{y}.jpg")
        if os.path.isfile(path):
            with open(path, "rb") as f:
                return f.read(), "image/jpeg"
        data = basemap.render_tile(src, z, x, y)
        if data is None:
            return None
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
        except OSError:
            pass                                                  # served anyway, just not kept
        return data, "image/jpeg"
    s = SOURCES.get(src)
    if s is None or not (0 <= z <= s["max"]) or not (0 <= x < 2 ** z) or not (0 <= y < 2 ** z):
        return None
    path = os.path.join(CACHE, src, str(z), str(x), f"{y}.{s['ext']}")
    media = "image/jpeg" if s["ext"] == "jpg" else "image/png"
    cached = None
    if os.path.isfile(path):
        with open(path, "rb") as f:
            cached = f.read()
        if time.time() - os.path.getmtime(path) < _MAX_AGE or time.time() < _offline_until:
            return cached, media
    if time.time() < _offline_until:
        return (cached, media) if cached else None
    try:
        req = urllib.request.Request(s["url"].format(z=z, x=x, y=y), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        if not data:
            raise OSError("empty tile")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return data, media
    except Exception:
        with _lock:
            _offline_until = time.time() + 30          # no network: stop trying for half a minute
        return (cached, media) if cached else None


def cache_size() -> int:
    total = 0
    for here, _d, files in os.walk(CACHE):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(here, f))
            except OSError:
                pass
    return total
