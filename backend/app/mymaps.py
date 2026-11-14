"""
M4 - *My maps*: an organisation's own maps, used like any map layer (2D, 3D, exported pictures, offline pages).

Two kinds:
- a raster **MBTiles** file (SQLite; read with Python's standard library) - fully offline;
- a **tile server** of the user's (an XYZ or TMS address with {z} {x} {y}, e.g. a server on the local network).
  Fetched through the app and kept in the tile cache like the online layers. "Never use the network" blocks it,
  except when its host is this PC or a private (local-network) address - the setting is about the internet.
  It may be kept offline in bulk (M3): it is the user's own server.

The list lives in ~/.signalviewer/mymaps.json; a layer's id is "my:<id>".
"""
import ipaddress
import os
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import uuid
from typing import Dict, List, Optional, Tuple

from app import prefs

FILE = "mymaps.json"
PREFIX = "my:"
_MEDIA = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
_lock = threading.Lock()
_conns: Dict[str, sqlite3.Connection] = {}
_failed_until: Dict[str, float] = {}


def is_mine(src: str) -> bool:
    return src.startswith(PREFIX)


def _maps() -> List[Dict]:
    return [m for m in (prefs._read(FILE, {}).get("maps") or []) if isinstance(m, dict) and m.get("id")]


def _save(maps: List[Dict]) -> None:
    with prefs._lock:
        prefs._write(FILE, {"version": 1, "maps": maps})


def get(src: str) -> Optional[Dict]:
    mid = src[len(PREFIX):] if is_mine(src) else src
    return next((m for m in _maps() if m["id"] == mid), None)


# ---- MBTiles ---------------------------------------------------------------------------------------

def _connect(path: str) -> sqlite3.Connection:
    """A read-only connection (never changes the user's file)."""
    uri = "file:" + urllib.parse.quote(os.path.abspath(path)) + "?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def read_mbtiles(path: str) -> Dict:
    """The file's metadata, checked: name, format, zooms, bounds, attribution. ValueError saying what is wrong."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(path):
        raise ValueError(f"File not found: {path}")
    try:
        con = _connect(path)
        try:
            meta = dict(con.execute("SELECT name, value FROM metadata").fetchall())
            zr = con.execute("SELECT MIN(zoom_level), MAX(zoom_level) FROM tiles").fetchone()
        finally:
            con.close()
    except sqlite3.Error as err:
        raise ValueError(f"Not an MBTiles file (a SQLite file with 'metadata' and 'tiles' tables): {err}")
    fmt = str(meta.get("format") or "png").lower()
    if fmt == "pbf":
        raise ValueError("This MBTiles file holds vector tiles (pbf); only raster maps (png / jpg / webp) can be shown. "
                         "Export the map as raster tiles (e.g. with QGIS: Generate XYZ tiles (MBTiles)).")
    if fmt not in _MEDIA:
        raise ValueError(f"Unknown tile format '{fmt}' in the MBTiles metadata: png, jpg or webp is expected.")
    if zr is None or zr[0] is None:
        raise ValueError("The MBTiles file has no tiles.")
    bounds = None
    try:
        w, s, e, n = (float(v) for v in str(meta.get("bounds", "")).split(","))
        bounds = [s, w, n, e]
    except ValueError:
        pass
    return {"name": str(meta.get("name") or os.path.splitext(os.path.basename(path))[0]), "format": fmt,
            "minzoom": int(meta.get("minzoom", zr[0])), "maxzoom": int(meta.get("maxzoom", zr[1])),
            "bounds": bounds, "attribution": str(meta.get("attribution") or "")}


def _mb_tile(m: Dict, z: int, x: int, y: int) -> Optional[bytes]:
    path = m["path"]
    with _lock:
        con = _conns.get(path)
        if con is None:
            try:
                con = _connect(path)
            except sqlite3.Error:
                return None
            _conns[path] = con
        try:
            row = con.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                              (z, x, (2 ** z - 1) - y)).fetchone()       # MBTiles rows count from the south (TMS)
        except sqlite3.Error:
            _conns.pop(path, None)
            return None
    return bytes(row[0]) if row and row[0] else None


# ---- a tile server ---------------------------------------------------------------------------------

def _check_url(url: str) -> str:
    url = (url or "").strip()
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("The address must start with http:// or https://, e.g. http://maps.local/tiles/{z}/{x}/{y}.png")
    if not all(k in url for k in ("{z}", "{x}")) or not ("{y}" in url or "{-y}" in url):
        raise ValueError("The address must hold {z}, {x} and {y} (or {-y} for a TMS server), "
                         "e.g. http://maps.local/tiles/{z}/{x}/{y}.png")
    return url


def local_only(src_or_map) -> bool:
    """True for an MBTiles file, or a server on this PC / the local network (allowed with "Never use the network")."""
    m = get(src_or_map) if isinstance(src_or_map, str) else src_or_map
    if not m:
        return False
    if m["kind"] == "mbtiles":
        return True
    host = urllib.parse.urlparse(m["url"]).hostname or ""
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False                     # a name: it may be anywhere - treated as the internet
    return ip.is_loopback or ip.is_private or ip.is_link_local


def _cache_path(m: Dict, z: int, x: int, y: int) -> str:
    from app import tiles
    return os.path.join(tiles.CACHE, "my-" + m["id"], str(z), str(x), f"{y}.tile")


def _media_of(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _server_tile(m: Dict, z: int, x: int, y: int) -> Optional[bytes]:
    from app import tiles
    path = _cache_path(m, z, x, y)
    cached = None
    if os.path.isfile(path):
        with open(path, "rb") as f:
            cached = f.read()
        if time.time() - os.path.getmtime(path) < 30 * 24 * 3600:
            return cached
    if not (tiles.network_allowed() or local_only(m)) or time.time() < _failed_until.get(m["id"], 0.0):
        return cached
    url = m["url"].replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y)).replace("{-y}", str(2 ** z - 1 - y))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": tiles.UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        if not data:
            raise OSError("empty tile")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
        return data
    except Exception:
        _failed_until[m["id"]] = time.time() + 30
        return cached


# ---- the layer -------------------------------------------------------------------------------------

def tile(src: str, z: int, x: int, y: int) -> Optional[Tuple[bytes, str]]:
    m = get(src)
    if not m or not (0 <= z <= max_zoom(src)) or not (0 <= x < 2 ** z) or not (0 <= y < 2 ** z):
        return None
    if m["kind"] == "mbtiles":
        data = _mb_tile(m, z, x, y)
        return (data, _MEDIA.get(m.get("format", "png"), "image/png")) if data else None
    data = _server_tile(m, z, x, y)
    return (data, _media_of(data)) if data else None


def cached_tile(src: str, z: int, x: int, y: int) -> Optional[bytes]:
    """What is on the disk only (exported pictures / pages never fetch)."""
    m = get(src)
    if not m:
        return None
    if m["kind"] == "mbtiles":
        return _mb_tile(m, z, x, y)
    try:
        with open(_cache_path(m, z, x, y), "rb") as f:
            return f.read()
    except OSError:
        return None


def tile_file(src: str, z: int, x: int, y: int) -> Optional[str]:
    """The cache file of a server's tile (for keeping an area offline); None for an MBTiles file."""
    m = get(src)
    return _cache_path(m, z, x, y) if m and m["kind"] != "mbtiles" else None


def max_zoom(src: str) -> int:
    m = get(src)
    return int(m.get("maxzoom", 19)) if m else 19


def attribution(src: str) -> str:
    m = get(src)
    return (m.get("attribution") or m.get("name") or "") if m else ""


def keepable(src: str) -> Tuple[bool, str]:
    m = get(src)
    if not m:
        return False, "This map is not in My maps any more."
    if m["kind"] == "mbtiles":
        return False, "An MBTiles file is offline already: nothing to download."
    return True, "Your own map server: it may be kept offline."


def listing() -> List[Dict]:
    """My maps, each with whether it can be used now (the file is there) and its layer id."""
    out = []
    for m in _maps():
        ok, why = True, ""
        if m["kind"] == "mbtiles" and not os.path.isfile(m["path"]):
            ok, why = False, f"File not found: {m['path']} (moved or on a drive that is not connected)."
        out.append({**m, "src": PREFIX + m["id"], "ok": ok, "problem": why, "localOnly": local_only(m)})
    return out


def add(kind: str, path: str = "", url: str = "", name: str = "", maxzoom: Optional[int] = None,
        attribution: str = "") -> Dict:
    """Add an MBTiles file or a tile server. ValueError with what to do."""
    mid = uuid.uuid4().hex[:8]
    if kind == "mbtiles":
        meta = read_mbtiles(path)
        m = {"id": mid, "kind": "mbtiles", "path": os.path.abspath(os.path.expanduser(path)), "name": (name or meta["name"])[:80],
             "format": meta["format"], "minzoom": meta["minzoom"], "maxzoom": meta["maxzoom"], "bounds": meta["bounds"],
             "attribution": (attribution or meta["attribution"])[:300]}
    elif kind in ("xyz", "tms"):
        u = _check_url(url)
        if kind == "tms" and "{y}" in u:
            u = u.replace("{y}", "{-y}")
        host = urllib.parse.urlparse(u).hostname or "server"
        z = 19 if maxzoom is None else int(maxzoom)
        if not 0 <= z <= 24:
            raise ValueError("The last zoom must be between 0 and 24.")
        m = {"id": mid, "kind": kind, "url": u, "name": (name or host)[:80], "minzoom": 0, "maxzoom": z,
             "bounds": None, "attribution": (attribution or "")[:300]}
    else:
        raise ValueError("A map is an MBTiles file ('mbtiles') or a tile server address ('xyz' / 'tms').")
    _save(_maps() + [m])
    return {**m, "src": PREFIX + mid, "ok": True, "problem": "", "localOnly": local_only(m)}


def remove(mid: str) -> None:
    mid = mid[len(PREFIX):] if is_mine(mid) else mid
    maps = _maps()
    if not any(m["id"] == mid for m in maps):
        raise KeyError(mid)
    gone = next(m for m in maps if m["id"] == mid)
    with _lock:
        con = _conns.pop(gone.get("path", ""), None)
    if con is not None:
        con.close()
    _save([m for m in maps if m["id"] != mid])
    if gone["kind"] != "mbtiles":                       # the server's tiles kept in the cache go with it
        import shutil

        from app import tiles
        shutil.rmtree(os.path.join(tiles.CACHE, "my-" + mid), ignore_errors=True)
