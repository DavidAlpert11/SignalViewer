"""
M3 - *Keep this area offline*: before going to the field, the tiles of an area (the open recordings' box or the
view) at a range of zooms are downloaded into the tile cache (app/tiles.py), so the map shows them with no
internet and with "Never use the network" on.

Only sources whose terms allow bulk downloading may be kept (`tiles.BULK`): OpenStreetMap's, Esri's and
OpenTopoMap's servers forbid it - the request is refused with the reason, never sent. Everything goes
through `tiles.tile` (the one network access of the app: the policy, the cache, the User-Agent).

The kept areas are listed in ~/.signalviewer/kept_areas.json; what they hold is counted on the disk when
listed (the tile cache can be cleared in Settings - the list then says so).
"""
import math
import os
import threading
import time
import uuid
from typing import Dict, Iterator, List, Optional, Tuple

from app import prefs, tiles

MAX_TILES = 40000                    # one request; ~1 GB of photos - beyond that, a smaller area or fewer zooms
_AVG_BYTES = {"png": 18000, "jpg": 22000}
_TERRARIUM_BYTES = 90000
FILE = "kept_areas.json"

_lock = threading.Lock()
_job: Dict = {"running": False}
_stop = threading.Event()


def _xy(lat: float, lon: float, z: int) -> Tuple[int, int]:
    n = 2 ** z
    lat = max(-85.05112878, min(85.05112878, lat))
    x = int((lon + 180.0) / 360.0 * n)
    s = math.sin(math.radians(lat))
    y = int((0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tile_ranges(bounds, zmin: int, zmax: int) -> List[Tuple[int, int, int, int, int]]:
    """(z, x0, x1, y0, y1) for each zoom: the tiles covering bounds = (south, west, north, east)."""
    s_, w_, n_, e_ = (float(v) for v in bounds)
    out = []
    for z in range(zmin, zmax + 1):
        x0, y0 = _xy(n_, w_, z)
        x1, y1 = _xy(s_, e_, z)
        out.append((z, x0, x1, y0, y1))
    return out


def _tiles(bounds, zmin: int, zmax: int) -> Iterator[Tuple[int, int, int]]:
    for z, x0, x1, y0, y1 in tile_ranges(bounds, zmin, zmax):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                yield z, x, y


def count(bounds, zmin: int, zmax: int) -> int:
    return sum((x1 - x0 + 1) * (y1 - y0 + 1) for _z, x0, x1, y0, y1 in tile_ranges(bounds, zmin, zmax))


def _path(src: str, z: int, x: int, y: int) -> Optional[str]:
    s = tiles.SOURCES.get(src)
    return os.path.join(tiles.CACHE, src, str(z), str(x), f"{y}.{s['ext']}") if s else None


def allowed(src: str) -> Tuple[bool, str]:
    """May `src` be downloaded in bulk, and why (or why not)."""
    if src not in tiles.SOURCES and src not in tiles.COMPOSITES:
        return False, f"Unknown map layer: {src}."
    ok, why = tiles.BULK.get(src, (False, "This map's terms do not allow bulk downloading."))
    return ok, why


def _clean(src: str, bounds, zmin: int, zmax: int) -> Tuple[List[float], int, int, int]:
    """Checked arguments: (bounds, zmin, zmax, max zoom of the source) - ValueError with an engineer's message."""
    if not bounds or len(bounds) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in bounds):
        raise ValueError("The area must be four numbers: south, west, north, east (degrees).")
    s_, w_, n_, e_ = (float(v) for v in bounds)
    if not (-90 <= s_ < n_ <= 90 and -180 <= w_ < e_ <= 180):
        raise ValueError("The area is empty or outside the world: give south < north and west < east, in degrees.")
    top = tiles.SOURCES.get(src, {"max": 19})["max"]
    zmin, zmax = int(zmin), int(zmax)
    if not (0 <= zmin <= zmax):
        raise ValueError("The zoom range is empty: the first zoom must not be above the last.")
    return [s_, w_, n_, e_], zmin, min(zmax, top), top


def estimate(src: str, bounds, zmin: int, zmax: int) -> Dict:
    """How many tiles, about how many bytes, how many are already kept, and whether it may be done."""
    ok, why = allowed(src)
    b, zmin, zmax, top = _clean(src, bounds, zmin, zmax)
    n = count(b, zmin, zmax)
    ext = tiles.SOURCES.get(src, {}).get("ext", "png")
    avg = _TERRARIUM_BYTES if src == "terrarium" else _AVG_BYTES.get(ext, 20000)
    have = 0
    if n <= MAX_TILES:
        have = sum(1 for z, x, y in _tiles(b, zmin, zmax) if (p := _path(src, z, x, y)) and os.path.isfile(p))
    return {"src": src, "bounds": b, "zmin": zmin, "zmax": zmax, "maxZoom": top, "tiles": n, "have": have,
            "bytes": (n - have) * avg, "allowed": ok, "reason": why, "tooMany": n > MAX_TILES, "limit": MAX_TILES,
            "network": tiles.network_allowed()}


def _areas() -> List[Dict]:
    return list(prefs._read(FILE, {}).get("areas") or [])


def _save(areas: List[Dict]) -> None:
    with prefs._lock:
        prefs._write(FILE, {"version": 1, "areas": areas})


def areas() -> List[Dict]:
    """The kept areas, with what is on the disk now (tiles present, bytes)."""
    out = []
    for a in _areas():
        present, size = 0, 0
        for z, x, y in _tiles(a["bounds"], a["zmin"], a["zmax"]):
            p = _path(a["src"], z, x, y)
            if p and os.path.isfile(p):
                present += 1
                try:
                    size += os.path.getsize(p)
                except OSError:
                    pass
        out.append({**a, "present": present, "bytes": size})
    return out


def delete(area_id: str) -> Dict:
    """Forget an area and remove its tiles - except those another kept area of the same layer also covers."""
    all_ = _areas()
    gone = [a for a in all_ if a.get("id") == area_id]
    if not gone:
        raise KeyError(area_id)
    rest = [a for a in all_ if a.get("id") != area_id]
    keep: set = set()
    for a in rest:
        if a["src"] == gone[0]["src"]:
            keep.update(_tiles(a["bounds"], a["zmin"], a["zmax"]))
    freed, removed = 0, 0
    a = gone[0]
    for t in _tiles(a["bounds"], a["zmin"], a["zmax"]):
        p = _path(a["src"], *t)
        if t in keep or not p or not os.path.isfile(p):
            continue
        try:
            sz = os.path.getsize(p)
            os.remove(p)
            freed += sz
            removed += 1
        except OSError:
            pass
    _save(rest)
    return {"removed": removed, "freed": freed}


def progress() -> Dict:
    with _lock:
        return dict(_job)


def stop() -> Dict:
    _stop.set()
    return progress()


def start(src: str, bounds, zmin: int, zmax: int, name: str = "") -> Dict:
    """Start downloading an area in the background. ValueError (with the reason) when it may not be done."""
    est = estimate(src, bounds, zmin, zmax)
    if not est["allowed"]:
        raise ValueError(est["reason"])
    if est["tooMany"]:
        raise ValueError(f"{est['tiles']:,} tiles is more than {MAX_TILES:,} at once: choose a smaller area or a lower last zoom.")
    if not tiles.network_allowed():
        raise ValueError("\"Never use the network\" is on (Settings, or SV_OFFLINE=1): turn it off to download the area.")
    with _lock:
        if _job.get("running"):
            raise ValueError("An area is being downloaded already: wait for it or stop it.")
        area = {"id": uuid.uuid4().hex[:10], "name": (name or "").strip()[:80] or "Area", "src": src, "bounds": est["bounds"],
                "zmin": est["zmin"], "zmax": est["zmax"], "tiles": est["tiles"], "created": time.strftime("%Y-%m-%d %H:%M")}
        _job.clear()
        _job.update(running=True, id=area["id"], name=area["name"], src=src, total=est["tiles"], done=0, failed=0,
                    stopped=False, error="")
        _stop.clear()
    _save([a for a in _areas() if a.get("id") != area["id"]] + [area])
    threading.Thread(target=_run, args=(area,), daemon=True, name="keep-area").start()
    return {**area, "estimate": est}


def _run(area: Dict) -> None:
    fails_in_row = 0
    for z, x, y in _tiles(area["bounds"], area["zmin"], area["zmax"]):
        if _stop.is_set():
            with _lock:
                _job.update(stopped=True)
            break
        try:
            got = tiles.tile(area["src"], z, x, y)
        except Exception:
            got = None
        with _lock:
            _job["done"] += 1
            if got is None:
                _job["failed"] += 1
        fails_in_row = 0 if got is not None else fails_in_row + 1
        if fails_in_row >= 25:
            with _lock:
                _job.update(error="The map server does not answer (25 tiles in a row failed): check the network or the "
                                  "server's address, then keep the area again - tiles already kept are not fetched twice.")
            break
        if not tiles.network_allowed():
            with _lock:
                _job.update(error="\"Never use the network\" was turned on: the download stopped.")
            break
    with _lock:
        _job["running"] = False
