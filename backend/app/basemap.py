"""
The offline basemap: map tiles drawn by the app from data that ships with it (built by
tools/make_basemap.py), so the map shows terrain, water, roads and places with no internet at all.

  * elevation: world (~11 km), Israel and surroundings (~500 m), Israel (~130 m) - hill shading and
    a colour per height
  * water: everything that is not land (Natural Earth), and lakes (incl. the Dead Sea and Kinneret)
  * rivers, main roads (Natural Earth); in Israel and around it the roads of OpenStreetMap (main
    roads in the region, down to regional roads in Israel) and runways
Place names are not drawn into the tiles: the map draws them (crisp, in the UI language) from
places(). Tiles are cached on disk; the data does not change, so the cache is kept until it does.
"""
import gzip
import io
import json
import math
import os
import threading
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basemap_data")
MAX_ZOOM = 14
STYLES = ("offline_topo", "offline_topo_dark")
REGION = (27.5, 31.5, 35.5, 39.0)                 # the built-in pack (Israel and around): s, w, n, e
PACKS = "packs"                                    # more detailed areas: basemap_data/packs/<name>/ (tools/make_basemap.py --pack)
ATTRIBUTION = ("Natural Earth · Terrain Tiles (Mapzen: SRTM, GMTED2010, ETOPO1) · "
               "© OpenStreetMap contributors (ODbL)")

_lock = threading.Lock()
_grids: Optional[List[dict]] = None
_layers: Optional[Dict[str, object]] = None
_pack_boxes: List[Tuple[float, float, float, float]] = []      # where detailed (OpenStreetMap) data replaces the world's


def available() -> bool:
    return os.path.isfile(os.path.join(DATA, "dem_world.npz"))


def data_version() -> str:
    """Changes when the bundled data changes (part of the tile cache path)."""
    try:
        parts = sorted((os.path.relpath(os.path.join(d, f), DATA), os.path.getsize(os.path.join(d, f)))
                       for d, _sub, fs in os.walk(DATA) for f in fs)
    except OSError:
        return "none"
    import hashlib                                               # (hash() differs between runs)
    return hashlib.md5(repr(parts).encode()).hexdigest()[:10] if parts else "none"


# ------------------------------------------------------------------ loading
def _packs() -> List[dict]:
    """The detailed areas: the built-in one (Israel and around, files at the top of the data folder)
    and every folder under packs/ with a pack.json {name, bounds: [s, w, n, e]}, dem_*.npz and
    vectors.json.gz."""
    out = [{"name": "israel", "bounds": REGION, "dems": [os.path.join(DATA, f"dem_{n}.npz") for n in ("region", "israel")],
            "vectors": os.path.join(DATA, "vectors_israel.json.gz")}]
    root = os.path.join(DATA, PACKS)
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            try:
                with open(os.path.join(d, "pack.json"), encoding="utf-8") as f:
                    meta = json.load(f)
                b = tuple(float(v) for v in meta["bounds"])
            except (OSError, ValueError, KeyError, TypeError):
                continue                                          # not a pack (or a broken one): skipped
            out.append({"name": meta.get("name", name), "bounds": b,
                        "dems": sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith("dem") and f.endswith(".npz")),
                        "vectors": os.path.join(d, "vectors.json.gz")})
    return out


def _layer(items) -> dict:
    """One layer = one coordinate array + where each feature starts + its box and attributes (an object
    per feature took ~230 MB for all layers; this takes a fraction)."""
    coords = [np.asarray(it["c"] if isinstance(it, dict) else it, dtype=np.float32).reshape(-1, 2) / np.float32(1e5) for it in items]
    lens = np.array([len(c) for c in coords], dtype=np.int64)
    off = np.concatenate([[0], np.cumsum(lens)])
    xy = np.concatenate(coords) if coords else np.zeros((0, 2), np.float32)
    box = np.array([[c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()] for c in coords]).reshape(-1, 4)
    get = lambda key, d: np.array([it.get(key, d) if isinstance(it, dict) else d for it in items], dtype=np.int16)
    return {"xy": xy, "off": off, "box": box, "k": get("k", 0), "r": get("r", 9)}


def _load():
    global _grids, _layers, _pack_boxes
    with _lock:
        if _grids is not None:
            return
        grids = []
        p = os.path.join(DATA, "dem_world.npz")
        dems = [("world", p)] if os.path.isfile(p) else []
        packs = _packs()
        for pk in packs:
            dems += [(pk["name"], f) for f in pk["dems"] if os.path.isfile(f)]
        for name, f in dems:
            z = np.load(f)
            grids.append({"name": name, "h": z["h"], "b": tuple(float(v) for v in z["bounds"]),   # int16: half the memory
                          "step": float(z["step"])})
        grids.sort(key=lambda g: -g["step"])                       # coarse to fine (the finest wins where it has data)
        layers: Dict[str, object] = {}
        p = os.path.join(DATA, "vectors_world.json.gz")
        if os.path.isfile(p):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                d = json.load(f)
            for k, items in d.items():
                layers["ne_" + k] = items if k in ("places", "airports") else _layer(items)
        # the packs' OpenStreetMap layers, together
        osm: Dict[str, list] = {}
        boxes = []
        for pk in packs:
            if not os.path.isfile(pk["vectors"]):
                continue
            boxes.append(pk["bounds"])
            with gzip.open(pk["vectors"], "rt", encoding="utf-8") as f:
                for k, items in json.load(f).items():
                    osm.setdefault(k, []).extend(items)
        for k, items in osm.items():
            layers["osm_" + k] = items if k in ("places", "airports") else _layer(items)
        _grids, _layers, _pack_boxes = grids, layers, boxes


# ------------------------------------------------------------------ geometry
def _tile_bounds(z: int, x: int, y: int) -> Tuple[float, float, float, float]:
    n = 2 ** z
    lon0, lon1 = x / n * 360 - 180, (x + 1) / n * 360 - 180
    lat0 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat0, lon0, lat1, lon1                                  # s, w, n, e


def _to_px(xy: np.ndarray, z: int, x: int, y: int, size: int) -> np.ndarray:
    n = 2 ** z
    lat = np.clip(xy[:, 1], -85.05, 85.05)
    px = ((xy[:, 0] + 180) / 360 * n - x) * size
    py = ((1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * n - y) * size
    return np.stack([px, py], axis=1)


def _heights(z: int, x: int, y: int, size: int, pad: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """Height (m) of each pixel, and which grid gave it (0 world, 1 region, 2 Israel): the coarse grid
    everywhere, finer grids where they exist and the zoom is close enough for their detail (a much
    finer grid than the pixels would only add noise). `pad` pixels around the tile are included, so
    smoothing and shading do not leave seams between tiles."""
    n = 2 ** z
    cols = (np.arange(-pad, size + pad) + 0.5) / size
    lon = ((x + cols) / n) * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * np.clip(y + cols, 0, n) / n))))
    return _sample_grid(lat, lon, 360 / (n * size))


def _sample_grid(lat: np.ndarray, lon: np.ndarray, px_deg: float) -> Tuple[np.ndarray, np.ndarray]:
    """Heights on the grid of `lat` (rows) x `lon` (columns), `px_deg` apart: see _heights."""
    _load()
    H = np.zeros((len(lat), len(lon)), dtype=np.float32)
    G = np.zeros(H.shape, dtype=np.int8)
    filled = np.zeros(H.shape, dtype=bool)
    # finest first: a coarser grid only fills what the finer ones left (inside Israel the world and
    # region grids are not computed - nor smoothed - at all)
    for g in reversed(_grids or []):
        if filled.all():
            break
        if g["name"] != "world" and px_deg > g["step"] * 3:
            continue
        s, w, nn, e = g["b"]
        ci = (lon - w) / g["step"]
        ri = (nn - lat) / g["step"]
        inx = (ci >= 0) & (ci <= g["h"].shape[1] - 1)
        iny = (ri >= 0) & (ri <= g["h"].shape[0] - 1)
        if not inx.any() or not iny.any():
            continue
        c0 = np.clip(np.floor(ci).astype(int), 0, g["h"].shape[1] - 2)
        r0 = np.clip(np.floor(ri).astype(int), 0, g["h"].shape[0] - 2)
        fc, fr = np.clip(ci - c0, 0, 1)[None, :], np.clip(ri - r0, 0, 1)[:, None]
        h = g["h"]
        a, b = h[np.ix_(r0, c0)].astype(np.float32), h[np.ix_(r0, c0 + 1)].astype(np.float32)
        c, d = h[np.ix_(r0 + 1, c0)].astype(np.float32), h[np.ix_(r0 + 1, c0 + 1)].astype(np.float32)
        v = a * (1 - fc) * (1 - fr) + b * fc * (1 - fr) + c * (1 - fc) * fr + d * fc * fr
        m = iny[:, None] & inx[None, :] & ~filled
        if not m.any():
            continue
        # smoothing in proportion to the magnification: a bilinear surface shaded shows its grid cells
        mag = g["step"] / px_deg
        if mag > 2.5:
            from scipy.ndimage import gaussian_filter
            v = gaussian_filter(v, sigma=min(24.0, mag * 0.45), mode="nearest")
        H[m] = v[m]
        G[m] = 0 if g["name"] == "world" else 1
        filled |= m
    return H, G


# Below-sea-level LAND: the Jordan rift (the Dead Sea and the Kinneret themselves come from the lakes)
_RIFT = (29.6, 35.15, 33.2, 35.85)                               # s, w, n, e


# ------------------------------------------------------------------ colours
_STOPS_LIGHT = [(-500, (164, 196, 142)), (0, (180, 208, 152)), (200, (205, 222, 165)), (500, (232, 226, 176)),
                (900, (226, 204, 156)), (1400, (210, 178, 138)), (2000, (190, 160, 128)), (3000, (176, 160, 150)),
                (4500, (232, 228, 224)), (6500, (255, 255, 255))]
_STOPS_DARK = [(-500, (38, 56, 44)), (0, (42, 62, 48)), (300, (58, 70, 52)), (800, (72, 70, 54)),
               (1500, (82, 72, 60)), (2500, (88, 82, 78)), (4500, (120, 120, 124)), (6500, (150, 150, 155))]


def _tint(H: np.ndarray, stops) -> np.ndarray:
    xs = np.array([s[0] for s in stops], dtype=np.float32)
    out = np.empty(H.shape + (3,), dtype=np.float32)
    for k in range(3):
        out[..., k] = np.interp(H, xs, np.array([s[1][k] for s in stops], dtype=np.float32))
    return out


def _shade(H: np.ndarray, z: int, lat_mid: float, size: int) -> np.ndarray:
    """Lambert hill shading, light from the north-west; exaggerated when zoomed out."""
    m_per_px = 40075016.7 * math.cos(math.radians(lat_mid)) / (2 ** z * size)
    exag = max(1.0, 2 ** ((11 - z) * 0.45))
    gy, gx = np.gradient(H * exag, m_per_px)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(315), math.radians(45)
    s = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(s, 0, 1)


# ------------------------------------------------------------------ drawing
def _visible(name, b, pad, keep=None):
    """[(coordinates, class, rank)] of the features of a layer whose box meets the tile (+ pad);
    keep(class, rank) -> bool arrays can drop some."""
    L = (_layers or {}).get(name)
    if not L or not len(L["box"]):
        return []
    s, w, n, e = b
    bx = L["box"]
    m = (bx[:, 0] <= e + pad) & (bx[:, 2] >= w - pad) & (bx[:, 1] <= n + pad) & (bx[:, 3] >= s - pad)
    if keep is not None:
        m &= keep(L["k"], L["r"], bx)
    off, xy = L["off"], L["xy"]
    return [(xy[off[i]:off[i + 1]].astype(np.float64), int(L["k"][i]), int(L["r"][i])) for i in np.flatnonzero(m)]


def render_tile(style: str, z: int, x: int, y: int) -> Optional[bytes]:
    if style not in STYLES or not (0 <= z <= MAX_ZOOM) or not (0 <= x < 2 ** z) or not (0 <= y < 2 ** z):
        return None
    if not available():
        return None
    from PIL import Image, ImageDraw
    _load()
    dark = style.endswith("dark")
    S = 512                                                       # drawn at 2x, then scaled down (smooth lines)
    P = 48                                                        # margin around the tile (no seams)
    b = _tile_bounds(z, x, y)
    lat_mid = (b[0] + b[2]) / 2
    Hp, Gp = _heights(z, x, y, S, P)
    sh = _shade(Hp, z, lat_mid, S)[P:-P, P:-P]
    H, G = Hp[P:-P, P:-P], Gp[P:-P, P:-P]
    rgb = _tint(H, _STOPS_DARK if dark else _STOPS_LIGHT)
    rgb *= (0.55 + 0.6 * sh)[..., None] if not dark else (0.6 + 0.55 * sh)[..., None]
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")

    water = (31, 51, 70) if dark else (170, 203, 230)
    pad = (b[3] - b[1]) * 0.05
    # land: everything else is water
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    for xy, _k, _r in _visible("ne_land", b, pad):
        p = _to_px(xy, z, x, y, S)
        if len(p) >= 3:
            md.polygon([tuple(v) for v in p], fill=255)
    lake_mask = Image.new("L", (S, S), 0)
    ld = ImageDraw.Draw(lake_mask)
    for xy, _k, rank in _visible("ne_lakes", b, pad):
        if rank <= z + 3:
            p = _to_px(xy, z, x, y, S)
            if len(p) >= 3:
                md.polygon([tuple(v) for v in p], fill=0)
                ld.polygon([tuple(v) for v in p], fill=255)
    # where the detailed grids are (Israel and around), the coast comes from the heights (~130-500 m)
    # rather than from the world land shapes (~1 km): sea is below 0 m, except in the Jordan rift
    land = np.asarray(mask) > 127
    if (G > 0).any():
        n2 = 2 ** z
        cols = (np.arange(S) + 0.5) / S
        lon = ((x + cols) / n2) * 360 - 180
        lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (y + cols) / n2))))
        rift = ((lat >= _RIFT[0]) & (lat <= _RIFT[2]))[:, None] & ((lon >= _RIFT[1]) & (lon <= _RIFT[3]))[None, :]
        lake = np.asarray(lake_mask) > 127
        # sea: clearly below 0 m, and not a speck (low ground by the coast reads a little below 0)
        from scipy.ndimage import binary_opening
        sea = binary_opening((H < -1.5) & ~rift, iterations=3)
        land = np.where(G > 0, ~sea & ~lake, land)
    mask = Image.fromarray((land * 255).astype(np.uint8), "L")
    img = Image.composite(img, Image.new("RGB", (S, S), water), mask)
    d = ImageDraw.Draw(img)
    k = S / 256

    def lines(items, colour, width, casing=None):
        for xy, *_r in items:
            p = [tuple(v) for v in _to_px(xy, z, x, y, S)]   # (xy, class, rank)
            if len(p) < 2:
                continue
            if casing:
                d.line(p, fill=casing, width=int(round(width + 2 * k)), joint="curve")
            d.line(p, fill=colour, width=max(1, int(round(width))), joint="curve")

    rivers = _visible("ne_rivers", b, pad, lambda kk, rr, bx: rr <= z + 2)
    lines(rivers, water, (1.0 if z < 8 else 1.6) * k)
    # Natural Earth roads only outside the detailed areas (inside them OpenStreetMap's are drawn)
    def outside(kk, rr, bx):
        cx, cy = (bx[:, 0] + bx[:, 2]) / 2, (bx[:, 1] + bx[:, 3]) / 2
        out = np.ones(len(bx), dtype=bool)
        for s_, w_, n_, e_ in _pack_boxes:
            out &= ~((w_ <= cx) & (cx <= e_) & (s_ <= cy) & (cy <= n_))
        return out
    ne_roads = _visible("ne_roads", b, pad, outside)
    osm_roads = _visible("osm_roads", b, pad)
    road_light = {1: ((226, 120, 60), (150, 80, 40)), 2: ((246, 206, 100), (160, 130, 60)),
                  3: ((255, 255, 255), (150, 150, 150)), 4: ((255, 255, 255), (170, 170, 170))}
    road_dark = {1: ((200, 120, 70), (20, 20, 20)), 2: ((170, 150, 90), (20, 20, 20)),
                 3: ((130, 130, 135), (25, 25, 25)), 4: ((110, 110, 115), (25, 25, 25))}
    pal = road_dark if dark else road_light
    min_zoom = {1: 5, 2: 7, 3: 10, 4: 11}
    for cls in (4, 3, 2, 1):                                     # main roads on top
        if z < min_zoom[cls]:
            continue
        w = k * {1: 1.6, 2: 1.3, 3: 1.0, 4: 0.8}[cls] * (1 + max(0, z - 9) * 0.35)
        cas = pal[cls][1] if z >= 9 else None
        lines([it for it in osm_roads if it[1] == cls], pal[cls][0], w, cas)
        if cls <= 2:
            lines([it for it in ne_roads if it[1] == cls], pal[cls][0], w, cas)
    if z >= 10:
        lines(_visible("osm_runways", b, pad), (90, 90, 95) if not dark else (150, 150, 155), k * (2 + (z - 10) * 2.2))

    img = img.resize((256, 256), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88, optimize=True)
    return buf.getvalue()


def places() -> dict:
    """Names for the map to draw: cities and towns of the world (Natural Earth, with Hebrew names),
    and in Israel and around it those of OpenStreetMap (down to villages in Israel), plus airports.
    Each: x lon, y lat, n English name, h Hebrew name, r rank (1 = most important), a = airport."""
    _load()
    L: Dict = _layers or {}            # (places / airports stay lists of small dicts)
    inside = lambda p: any(b[0] <= p["y"] <= b[2] and b[1] <= p["x"] <= b[3] for b in _pack_boxes)
    out = []
    for p in L.get("ne_places", []):
        if not inside(p):
            out.append({"x": p["x"], "y": p["y"], "n": p["n"], "h": p.get("h", ""), "r": min(9, p.get("r", 9))})
    for p in L.get("osm_places", []):
        k = p.get("k", 3)
        pop = p.get("p", 0)
        r = 2 if k == 1 and pop > 300000 else 3 if k == 1 else 5 if k == 2 else 8
        out.append({"x": p["x"], "y": p["y"], "n": p["n"], "h": p.get("h", ""), "r": r})
    for a in L.get("ne_airports", []):
        if not inside(a):
            out.append({"x": a["x"], "y": a["y"], "n": a["n"], "h": "", "r": 7, "a": 1})
    for a in L.get("osm_airports", []):
        if a.get("n"):
            out.append({"x": a["x"], "y": a["y"], "n": a["n"], "h": a.get("h", ""), "r": 6 if a.get("c") else 9, "a": 1})
    return {"places": out, "attribution": ATTRIBUTION}


# ------------------------------------------------------------------ 3D terrain / ground heights
TERRAIN_SIZE = 65


def _sea_level(H: np.ndarray, lat, lon) -> np.ndarray:
    """The sea at 0 m (the data keeps depths floored at -500): below 0 only in the Jordan rift,
    where the land and the lakes (Dead Sea, Kinneret) really are below sea level."""
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    if lat.ndim == 1 and lon.ndim == 1 and H.ndim == 2:
        rift = ((lat >= _RIFT[0]) & (lat <= _RIFT[2]))[:, None] & ((lon >= _RIFT[1]) & (lon <= _RIFT[3]))[None, :]
    else:
        rift = (lat >= _RIFT[0]) & (lat <= _RIFT[2]) & (lon >= _RIFT[1]) & (lon <= _RIFT[3])
    return np.where((H < 0) & ~rift, 0, H)


def terrain_tile(z: int, x: int, y: int) -> Optional[bytes]:
    """Heights for the 3D view: a 65 x 65 grid (north to south, west to east, edges included) for
    tile (x, y) of level z in the geographic tiling scheme (2 x 1 tiles at level 0), float32."""
    # (any level up to 20: beyond the grids' detail it is interpolated - the 3D view must get an
    # answer for every tile it asks for, "no data" makes it ask again)
    if not available() or not (0 <= z <= 20) or not (0 <= x < 2 ** (z + 1)) or not (0 <= y < 2 ** z):
        return None
    d = 180 / 2 ** z
    w, n = -180 + x * d, 90 - y * d
    lon = np.linspace(w, w + d, TERRAIN_SIZE)
    lat = np.clip(np.linspace(n, n - d, TERRAIN_SIZE), -85, 85)
    H, G = _sample_grid(lat, lon, d / (TERRAIN_SIZE - 1))
    step_m = d / (TERRAIN_SIZE - 1) * 111_320
    if step_m < 5_000 and (G == 0).any():                # P5: where only the world grid had it, finer sources
        LA, LO = np.meshgrid(lat, lon, indexing="ij")
        m = G == 0
        v = _extra_heights(LA[m].astype(np.float64), LO[m].astype(np.float64), step_m)
        H[m] = np.where(np.isfinite(v), v, H[m])
    return _sea_level(H, lat, lon).astype(np.float32).tobytes()


def ground_at(lat: np.ndarray, lon: np.ndarray, step_m: Optional[float] = None, fetch: bool = True) -> np.ndarray:
    """Ground height (m above sea level) under each point: a bundled fine grid, else the user's elevation
    files or terrarium tiles (P5; `step_m`: the spacing wanted - a coarse grid asks coarser tiles), else the
    bundled world grid."""
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    if not available():
        return np.full(len(lat), np.nan, dtype=np.float32)
    _load()
    out = np.full(len(lat), np.nan, dtype=np.float32)
    for g in reversed(_grids or []):
        if g["name"] == "world":
            todo = np.isnan(out)
            if todo.any():
                out[todo] = _extra_heights(lat[todo], lon[todo], step_m, fetch)
        s, w, n, e = g["b"]
        todo = np.isnan(out) & np.isfinite(lat) & np.isfinite(lon) & (lat >= s) & (lat <= n) & (lon >= w) & (lon <= e)
        if not todo.any():
            continue
        ci = (lon[todo] - w) / g["step"]
        ri = (n - lat[todo]) / g["step"]
        h = g["h"]
        c0 = np.clip(np.floor(ci).astype(int), 0, h.shape[1] - 2)
        r0 = np.clip(np.floor(ri).astype(int), 0, h.shape[0] - 2)
        fc, fr = np.clip(ci - c0, 0, 1), np.clip(ri - r0, 0, 1)
        v = (h[r0, c0] * (1 - fc) * (1 - fr) + h[r0, c0 + 1] * fc * (1 - fr)
             + h[r0 + 1, c0] * (1 - fc) * fr + h[r0 + 1, c0 + 1] * fc * fr)
        out[todo] = v
    return _sea_level(out, lat, lon).astype(np.float32)


# ------------------------------------------------------------------ P5: elevation beyond the bundled grids
# The ground is the finest of: a bundled fine grid (the packs) -> the user's elevation files (SRTM .hgt) ->
# terrarium tiles (fetched only when the network is allowed, kept in the tile cache like any online
# layer) -> the bundled coarse world grid (11 km). A fetch never blocks: an answer comes from what is
# there now and the next request is finer; `terrain_version()` changes when new heights arrived.
TERRARIUM_Z = 12                                      # ~38 m a pixel at the equator
_TR_MEM: "Dict[Tuple[int, int, int], Optional[np.ndarray]]" = {}
_TR_PENDING: set = set()
_TR_LOCK = threading.Lock()
_TR_THREADS: List[threading.Thread] = []
_terrain_version = 0
_HGT: "Dict[str, Tuple[float, Optional[np.ndarray]]]" = {}


def terrain_version() -> int:
    """Changes each time fetched elevation arrives (the 3D view asks its terrain again)."""
    return _terrain_version


def elevation_folder() -> str:
    """The folder of the user's elevation files (Settings *Elevation files*; default ~/.signalviewer/terrain)."""
    from app import prefs
    try:
        f = prefs.ui_settings().get("elevationFolder")
    except Exception:
        f = None
    return os.path.expanduser(f) if isinstance(f, str) and f.strip() else os.path.join(prefs.APP_DIR, "terrain")


def elevation_files() -> List[dict]:
    """The .hgt files found (SRTM: 1201 x 1201 = 3", 3601 x 3601 = 1"): [{name, lat, lon, step}] - the
    Settings list them."""
    folder = elevation_folder()
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    for n in names:
        key = _hgt_key(n)
        if key is None:
            continue
        size = os.path.getsize(os.path.join(folder, n))
        side = {1201 * 1201 * 2: 1201, 3601 * 3601 * 2: 3601}.get(size)
        if side:
            out.append({"name": n, "lat": key[0], "lon": key[1], "step": round(111_320 / (side - 1), 1)})
    return out


def _hgt_key(name: str) -> Optional[Tuple[int, int]]:
    import re as _re
    m = _re.fullmatch(r"([NS])(\d{2})([EW])(\d{3})\.hgt", name, flags=_re.I)
    if not m:
        return None
    lat = int(m.group(2)) * (1 if m.group(1).upper() == "N" else -1)
    lon = int(m.group(4)) * (1 if m.group(3).upper() == "E" else -1)
    return lat, lon


def _hgt_name(lat0: int, lon0: int) -> str:
    return f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}.hgt"


def _hgt(lat0: int, lon0: int) -> Optional[np.ndarray]:
    """The heights of one .hgt file (north row first), NaN for its voids; None when there is none."""
    folder = elevation_folder()
    path = os.path.join(folder, _hgt_name(lat0, lon0))
    if not os.path.isfile(path):
        path = os.path.join(folder, _hgt_name(lat0, lon0).lower())
        if not os.path.isfile(path):
            return None
    mt = os.path.getmtime(path)
    got = _HGT.get(path)
    if got and got[0] == mt:
        return got[1]
    raw = np.fromfile(path, dtype=">i2")
    side = int(round(math.sqrt(len(raw))))
    arr = None
    if side * side == len(raw) and side in (1201, 3601):
        arr = raw.reshape(side, side).astype(np.float32)
        arr[arr == -32768] = np.nan
    _HGT[path] = (mt, arr)
    return arr


def _hgt_heights(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    out = np.full(len(lat), np.nan, dtype=np.float32)
    ok = np.isfinite(lat) & np.isfinite(lon)
    if not ok.any() or not os.path.isdir(elevation_folder()):
        return out
    la0, lo0 = np.floor(lat[ok]).astype(int), np.floor(lon[ok]).astype(int)
    idx = np.flatnonzero(ok)
    for a, b in set(zip(la0.tolist(), lo0.tolist())):
        h = _hgt(a, b)
        if h is None:
            continue
        sel = (la0 == a) & (lo0 == b)
        n = h.shape[0] - 1
        r = (a + 1 - lat[idx[sel]]) * n
        c = (lon[idx[sel]] - b) * n
        out[idx[sel]] = _bilinear(h, r, c)
    return out


def _bilinear(h: np.ndarray, r: np.ndarray, c: np.ndarray) -> np.ndarray:
    r0 = np.clip(np.floor(r).astype(int), 0, h.shape[0] - 2)
    c0 = np.clip(np.floor(c).astype(int), 0, h.shape[1] - 2)
    fr, fc = np.clip(r - r0, 0, 1), np.clip(c - c0, 0, 1)
    return (h[r0, c0] * (1 - fc) * (1 - fr) + h[r0, c0 + 1] * fc * (1 - fr)
            + h[r0 + 1, c0] * (1 - fc) * fr + h[r0 + 1, c0 + 1] * fc * fr).astype(np.float32)


def _tr_path(z: int, x: int, y: int) -> str:
    from app import tiles
    return os.path.join(tiles.CACHE, "terrarium", str(z), str(x), f"{y}.png")


def _tr_decode(data: bytes) -> Optional[np.ndarray]:
    try:
        from PIL import Image
        import io as _io
        a = np.asarray(Image.open(_io.BytesIO(data)).convert("RGB"), dtype=np.float32)
    except Exception:
        return None
    return a[:, :, 0] * 256.0 + a[:, :, 1] + a[:, :, 2] / 256.0 - 32768.0


def _tr_tile(z: int, x: int, y: int, fetch: bool) -> Optional[np.ndarray]:
    """A terrarium tile's heights: memory, then the tile cache; when missing (and allowed), fetched in the
    background - this call answers None now."""
    key = (z, x, y)
    if key in _TR_MEM:
        return _TR_MEM[key]
    path = _tr_path(z, x, y)
    if os.path.isfile(path):
        with open(path, "rb") as f:
            arr = _tr_decode(f.read())
        if len(_TR_MEM) > 256:
            _TR_MEM.clear()
        _TR_MEM[key] = arr
        return arr
    if fetch:
        _tr_fetch_later(z, x, y)
    return None


def _tr_fetch_later(z: int, x: int, y: int) -> None:
    from app import tiles
    if not tiles.network_allowed():
        return
    with _TR_LOCK:
        if (z, x, y) in _TR_PENDING or len(_TR_PENDING) > 64:
            return
        _TR_PENDING.add((z, x, y))

    def run():
        global _terrain_version
        try:
            got = tiles.tile("terrarium", z, x, y)          # the cache, the policy, the fetch: one place
            if got:
                _terrain_version += 1
        finally:
            with _TR_LOCK:
                _TR_PENDING.discard((z, x, y))
    th = threading.Thread(target=run, daemon=True)
    _TR_THREADS.append(th)
    th.start()


def wait_terrain(timeout: float = 10.0) -> None:
    """Wait for the background fetches started so far (tests; a report that wants the finer ground)."""
    end = time.time() + timeout
    while _TR_THREADS:
        th = _TR_THREADS.pop()
        th.join(max(0.0, end - time.time()))


def _terrarium_z(step_m: Optional[float]) -> int:
    """The tile level whose pixel is about half of `step_m` (no finer than TERRARIUM_Z)."""
    if not step_m:
        return TERRARIUM_Z
    z = int(math.floor(math.log2(156_543.0 / max(step_m / 2, 1.0))))
    return max(0, min(TERRARIUM_Z, z))


def _terrarium_heights(lat: np.ndarray, lon: np.ndarray, z: int = TERRARIUM_Z, fetch: bool = True) -> np.ndarray:
    out = np.full(len(lat), np.nan, dtype=np.float32)
    ok = np.isfinite(lat) & np.isfinite(lon) & (np.abs(lat) < 85)
    if not ok.any():
        return out
    n = 2 ** z
    fx = (lon[ok] + 180) / 360 * n
    fy = (1 - np.arcsinh(np.tan(np.radians(lat[ok]))) / math.pi) / 2 * n
    tx, ty = np.floor(fx).astype(int) % n, np.clip(np.floor(fy).astype(int), 0, n - 1)
    idx = np.flatnonzero(ok)
    keys = set(zip(tx.tolist(), ty.tolist()))
    if len(keys) > 400:                               # far too many tiles for this level: the caller's grid is coarse
        return out
    for x, y in keys:
        h = _tr_tile(z, x, y, fetch)
        if h is None:
            continue
        sel = (tx == x) & (ty == y)
        size = h.shape[0]
        out[idx[sel]] = _bilinear(h, (fy[sel] - y) * size - 0.5, (fx[sel] - x) * size - 0.5)
    return out


def _extra_heights(lat: np.ndarray, lon: np.ndarray, step_m: Optional[float] = None, fetch: bool = True) -> np.ndarray:
    """The user's .hgt files, then terrarium tiles: NaN where neither has the point."""
    out = _hgt_heights(lat, lon)
    todo = np.isnan(out)
    if todo.any():
        out[todo] = _terrarium_heights(lat[todo], lon[todo], _terrarium_z(step_m), fetch)
    return out


def step_at(lat: float, lon: float) -> float:
    """The step in metres of the best elevation source at a point (what the 3D view says about its ground).
    Never fetches."""
    _load()
    for g in reversed(_grids or []):
        if g["name"] == "world":
            continue
        s, w, n, e = g["b"]
        if s <= lat <= n and w <= lon <= e:
            return float(round(g["step"] * 111_320))
    a, b = math.floor(lat), math.floor(lon)
    h = _hgt(a, b)
    if h is not None:
        return float(round(111_320 / (h.shape[0] - 1)))
    nz = 2 ** TERRARIUM_Z
    x = int((lon + 180) / 360 * nz) % nz
    y = int((1 - math.asinh(math.tan(math.radians(max(-85.0, min(85.0, lat))))) / math.pi) / 2 * nz)
    if os.path.isfile(_tr_path(TERRARIUM_Z, x, y)):
        return float(round(156_543.0 * math.cos(math.radians(lat)) / nz))
    world = next((g for g in (_grids or []) if g["name"] == "world"), None)
    return float(round((world["step"] if world else 0.1) * 111_320))
