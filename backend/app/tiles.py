"""
Map tiles for the Geo plot, fetched through the app (so the page needs no outside access) and kept
in a disk cache (~/.signalviewer/tiles), so places already seen stay available without internet.

O1 - offline by default: the map's *Automatic* layer is the bundled offline map; an online layer is
used only when chosen. "Never use the network" (Settings, ui_settings `offlineOnly`, or the
environment variable SV_OFFLINE=1) is checked here before any request: this module is the app's only
network access. Tiles already in the cache are still shown then (they are on the disk).

Every source asks for attribution, which the map shows. (CARTO's basemaps now need an API key, so
the light / dark maps are Esri's grey canvases.) OpenStreetMap's tile servers are for light
use: the cache, a real User-Agent and no bulk downloading keep within their policy.

M2 - *Satellite + roads*: Esri's World Imagery with Esri's own transportation reference layer
(roads and their names, a transparent PNG made to be drawn over that imagery) composed here into one
tile, so the 2D map, the 3D globe, the exported picture and the offline page all show the same thing.
Terms: both layers are Esri ArcGIS Online basemaps - display in an application with the attribution
shown is allowed; bulk download / offline packaging is not (Esri's terms of use), so neither may be
"kept offline" in bulk (M3) - only what was seen stays in the cache.

No imagery at that zoom: Esri's services answer with a grey "Map data not yet available" picture (an ordinary
200 JPEG), common for satellite imagery zoomed in outside cities. Such a tile is never shown or kept: the
parent tile, enlarged, is drawn instead (overzoom), and a small marker beside the cache saves asking again.
"""
import os
import threading
import time
import urllib.request
from typing import Dict, Optional

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
    # M2: roads and road names, transparent - drawn over the imagery (never shown alone)
    "sat_roads": {"url": _ESRI.format(svc="Reference/World_Transportation"), "max": 19, "ext": "png"},
    "topo": {"url": "https://tile.opentopomap.org/{z}/{x}/{y}.png", "max": 17, "ext": "png"},
    # P5: elevation for the whole world (Mapzen / AWS open data: SRTM, GMTED2010, ETOPO1), heights encoded
    # in the colours - only for app/basemap.py's ground (never shown as a picture)
    "terrarium": {"url": "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png", "max": 15, "ext": "png"},
}
# M3: may a source's tiles be downloaded in bulk ("Keep this area offline")? Only where its terms allow it; the
# reason is shown to the user as it is. A user's own server (M4) may always be.
BULK: dict = {
    "terrarium": (True, "Terrain Tiles are open data (Mapzen / AWS Open Data): free to download."),
    "osm": (False, "OpenStreetMap's tile servers forbid bulk downloading (their tile usage policy). "
                   "Places you look at stay in the cache; for a whole area use your own map server or an MBTiles file (My maps)."),
    "topo": (False, "OpenTopoMap's servers are for light use only - no bulk downloading. "
                    "Places you look at stay in the cache; for a whole area use your own map server or an MBTiles file (My maps)."),
}
_ESRI_TERMS = (False, "Esri's terms do not allow downloading its maps for offline use outside ArcGIS. "
                      "Places you look at stay in the cache; for a whole area use your own map server or an MBTiles file (My maps).")
for _k in ("esri", "light", "light_ref", "dark", "dark_ref", "satellite", "sat_roads", "satroads"):
    BULK[_k] = _ESRI_TERMS


# M2: a layer made of two - the picture and a transparent reference drawn over it (composed in `tile`)
COMPOSITES: dict = {"satroads": ("satellite", "sat_roads")}
_MAX_AGE = 30 * 24 * 3600          # refresh a cached tile after a month (when online)
_offline_until = 0.0               # after a failure, do not try the network again for a while
_lock = threading.Lock()
_policy_cache: dict = {}           # {"at": time, "allowed": bool} - the setting is read at most once a second


def offline_forced() -> bool:
    """SV_OFFLINE=1 (or true / yes): the network is off whatever the Settings say."""
    return os.environ.get("SV_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def network_allowed() -> bool:
    """False when "Never use the network" is on (Settings or SV_OFFLINE)."""
    if offline_forced():
        return False
    now = time.monotonic()
    if _policy_cache and now - _policy_cache["at"] < 1.0:
        return bool(_policy_cache["allowed"])
    from app import prefs
    try:
        allowed = prefs.ui_settings().get("offlineOnly") is not True
    except Exception:                  # an unreadable settings file: stay on the safe side
        allowed = False
    _policy_cache.update(at=now, allowed=allowed)
    return allowed


# the Esri pictures that answer "Map data not yet available" where they have nothing at a zoom
NO_DATA_SOURCES = ("satellite", "esri", "light", "dark")
_NO_DATA_GREY = 204                     # #CCCCCC, the placeholder's background
_checked: Dict[str, float] = {}         # cached tiles already seen to be real pictures: path -> mtime


def is_no_data(data: bytes) -> bool:
    """Esri's grey "Map data not yet available" tile: most of it one flat #CCCCCC (a real picture never is).
    Only small files are decoded - the placeholder compresses well, a photo does not."""
    if len(data) > 24_000:
        return False
    try:
        import io

        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"), dtype=np.int16)
    except Exception:
        return False
    return bool((np.abs(a - _NO_DATA_GREY) <= 3).all(axis=2).mean() > 0.6)


def _overzoom(src: str, z: int, x: int, y: int) -> Optional[tuple]:
    """The parent tile's quarter, enlarged: what to draw where a source has no picture at this zoom."""
    if z <= 0:
        return None
    parent = tile(src, z - 1, x // 2, y // 2)          # itself enlarged from further up when it has none
    if not parent:
        return None
    try:
        import io

        from PIL import Image
        img = Image.open(io.BytesIO(parent[0])).convert("RGB")
        w, h = img.size
        qx, qy = x % 2, y % 2
        part = img.crop((qx * w // 2, qy * h // 2, (qx + 1) * w // 2, (qy + 1) * h // 2)).resize((w, h), Image.Resampling.BILINEAR)
        buf = io.BytesIO()
        part.save(buf, "JPEG", quality=88)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return None


def tile(src: str, z: int, x: int, y: int) -> Optional[tuple]:
    """(bytes, media type) of a tile, or None when it is not available (offline and not cached)."""
    global _offline_until
    from app import basemap
    if src in basemap.STYLES:                                   # drawn here from bundled data: no network
        if not (0 <= z <= basemap.MAX_ZOOM) or not (0 <= x < 2 ** z) or not (0 <= y < 2 ** z):
            return None
        path = os.path.join(CACHE, f"{src}-{basemap.data_version()}-{basemap.LOOK}", str(z), str(x), f"{y}.jpg")   # M5: a new look, new tiles
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
    if src in COMPOSITES:
        return _composite(src, z, x, y)
    if src.startswith("my:"):                                   # M4: an MBTiles file or the user's own server
        from app import mymaps
        return mymaps.tile(src, z, x, y)
    s = SOURCES.get(src)
    if s is None or not (0 <= z <= s["max"]) or not (0 <= x < 2 ** z) or not (0 <= y < 2 ** z):
        return None
    path = os.path.join(CACHE, src, str(z), str(x), f"{y}.{s['ext']}")
    media = "image/jpeg" if s["ext"] == "jpg" else "image/png"
    checks = src in NO_DATA_SOURCES
    marker = path + ".nodata"
    if checks and os.path.isfile(marker) and time.time() - os.path.getmtime(marker) < _MAX_AGE:
        return _overzoom(src, z, x, y)                   # known: nothing at this zoom here
    cached = None
    allowed = network_allowed()
    if os.path.isfile(path):
        with open(path, "rb") as f:
            cached = f.read()
        mtime = os.path.getmtime(path)
        if checks and _checked.get(path) != mtime:
            if is_no_data(cached):                       # kept by an older version: put right once
                _mark_no_data(path, marker)
                return _overzoom(src, z, x, y)
            if len(_checked) > 20_000:
                _checked.clear()
            _checked[path] = mtime
        if not allowed or time.time() - os.path.getmtime(path) < _MAX_AGE or time.time() < _offline_until:
            return cached, media
    if not allowed or time.time() < _offline_until:
        return (cached, media) if cached else None
    try:
        req = urllib.request.Request(s["url"].format(z=z, x=x, y=y), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        if not data:
            raise OSError("empty tile")
        if checks and is_no_data(data):
            _mark_no_data(path, marker)
            return _overzoom(src, z, x, y)
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


def _mark_no_data(path: str, marker: str) -> None:
    """Remember that a source has no picture here (the placeholder itself is not kept)."""
    try:
        if os.path.isfile(path):
            os.remove(path)
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        open(marker, "wb").close()
    except OSError:
        pass


def compose(under: bytes, over: Optional[bytes]) -> bytes:
    """A picture with a transparent reference layer drawn over it, as a JPEG (M2)."""
    if not over:
        return under
    import io

    from PIL import Image
    base = Image.open(io.BytesIO(under)).convert("RGBA")
    top = Image.open(io.BytesIO(over)).convert("RGBA")
    if top.size != base.size:
        top = top.resize(base.size)
    out = io.BytesIO()
    Image.alpha_composite(base, top).convert("RGB").save(out, "JPEG", quality=88)
    return out.getvalue()


def _composite(src: str, z: int, x: int, y: int) -> Optional[tuple]:
    """The picture tile with its reference layer over it; the picture alone when the reference is not to be had
    (it is not kept composed: the next ask adds the roads once they arrive)."""
    under_src, over_src = COMPOSITES[src]
    under = tile(under_src, z, x, y)
    if under is None:
        return None
    over = tile(over_src, z, x, y)
    try:
        return compose(under[0], over[0] if over else None), "image/jpeg"
    except Exception:                                   # a broken reference tile: the picture still shows
        return under

