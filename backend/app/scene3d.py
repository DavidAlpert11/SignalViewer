"""
The map's 3D view outside the app (1.26): a 3D plot of a tab (a Map seen in 3D) in reports, the replay page
and its own offline HTML file. Beside `mapimage.py` (the same objects, tiles and attribution rules) and built
on it; report.py, the export route and the Python API call it.

Two outputs from one scene (`scene_data`):
- `render`: a picture (PNG / SVG) drawn by matplotlib - PDF, Word, PNG reports, the CLI; also the page's
  fallback where the browser has no WebGL.
- `build_html`: a live page (report_assets/scene3d.html) drawn by three.js (r159, MIT, embedded - no network):
  the ground (the offline map draped on the bundled terrain), each object's track with a curtain down to the
  ground, its 3D model at the time with its heading, pitch and roll, orbit / zoom / follow, a time slider -
  and, inside a replay or a live report, the page's one time (the same message as the 2D map's page).

The objects come as the app's views fetch them (mapObjects.ts `trackRequest`: a borrowed attitude already
resolved) and are read exactly as the Tacview export reads them (`routes.export.acmi_objects`): altitude by
its reference, angles in degrees. CesiumJS (the app's 3D view) is not used here: it cannot be put in one file.

The scene is local: east / north / up metres around the middle of the tracks (a flat earth - the tracks of a
flight test span kilometres, not hundreds of them).
"""
import base64
import functools
import io
import json
import math
import os
import struct
from typing import Dict, List, Optional, Tuple

import numpy as np

from app import basemap, mapimage

R_EARTH = 6378137.0
GRID = 97                      # terrain heights: GRID x GRID over the padded box
TEX_PX = 1024                  # the ground picture's longest side
POINTS = 3000                  # a track: at most this many points
ASSETS = os.path.join(os.path.dirname(__file__), "report_assets")
_FRONT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
# the app's models: where the app serves them from (SV_DIST in the packaged app), else the source tree
MODEL_DIRS = [d for d in (os.path.join(os.environ["SV_DIST"], "models") if os.environ.get("SV_DIST") else "",
                          os.path.join(_FRONT, "dist", "models"), os.path.join(_FRONT, "public", "models")) if d]
KINDS = ("aircraft", "drone", "uav", "ship", "vehicle", "missile")


# ---- the scene ----------------------------------------------------------------------------------

def _enu(lat, lon, lat0: float, lon0: float):
    e = np.radians(np.asarray(lon, dtype=np.float64) - lon0) * R_EARTH * math.cos(math.radians(lat0))
    n = np.radians(np.asarray(lat, dtype=np.float64) - lat0) * R_EARTH
    return e, n


def _course(e: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Direction of travel (degrees from north), held where the object does not move."""
    de, dn = np.gradient(e), np.gradient(n)
    c = np.degrees(np.arctan2(de, dn))
    still = np.hypot(de, dn) < 1e-6
    if still.any() and (~still).any():
        idx = np.where(~still, np.arange(len(c)), 0)
        np.maximum.accumulate(idx, out=idx)
        first = int(np.argmax(~still))
        idx[:first] = first
        c = c[idx]
    return c


def _ground_image(bounds, base: str, dark: bool, width: int = TEX_PX) -> Tuple[Optional[np.ndarray], set]:
    """The map tiles over `bounds` (s, w, n, e) stitched into one picture, north up, cropped to the box."""
    s_, w_, n_, e_ = bounds
    x0, x1, y0, y1 = float(mapimage.mx(w_)), float(mapimage.mx(e_)), float(mapimage.my(n_)), float(mapimage.my(s_))
    maxz = basemap.MAX_ZOOM if base == "offline" else 19
    z = max(1, min(maxz, int(math.floor(math.log2(width / ((x1 - x0) * mapimage.TILE))))))
    n = 2 ** z
    tx0, tx1 = int(math.floor(x0 * n)), int(math.floor(x1 * n))
    ty0, ty1 = max(0, int(math.floor(y0 * n))), min(n - 1, int(math.floor(y1 * n)))
    if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > 64:
        return None, set()
    T = mapimage.TILE
    canvas = np.zeros(((ty1 - ty0 + 1) * T, (tx1 - tx0 + 1) * T, 3), dtype=np.uint8)
    used, got = set(), False
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            data, src = mapimage.tile_bytes(base, dark, z, tx % n, ty)
            if not data:
                continue
            img = mapimage._image(data)
            if img.shape[:2] != (T, T):
                continue
            canvas[(ty - ty0) * T:(ty - ty0 + 1) * T, (tx - tx0) * T:(tx - tx0 + 1) * T] = img
            used.add(src)
            got = True
    if not got:
        return None, set()
    px0, px1 = int(round((x0 * n - tx0) * T)), int(round((x1 * n - tx0) * T))
    py0, py1 = int(round((y0 * n - ty0) * T)), int(round((y1 * n - ty0) * T))
    return canvas[py0:max(py1, py0 + 1), px0:max(px1, px0 + 1)], used


def _jpeg(img: np.ndarray, side: int = TEX_PX) -> str:
    from PIL import Image
    im = Image.fromarray(img)
    k = side / max(im.size)
    if k < 1:
        im = im.resize((max(1, int(im.size[0] * k)), max(1, int(im.size[1] * k))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def scene_data(store, spec: Dict) -> Dict:
    """The 3D plot's scene: tracks in local metres with attitude, the terrain grid, the ground pictures."""
    from fastapi import HTTPException
    from app.routes.export import acmi_objects
    sc = spec.get("scene") or {}
    geo = spec.get("geo") or {}
    want = sc.get("objects") or geo.get("objects") or []
    try:
        raw = acmi_objects([o for o in want if o.get("lat") and o.get("lon")], store)
    except (HTTPException, KeyError) as err:
        raise ValueError(f"A 3D view's object could not be read: {getattr(err, 'detail', err)}") from err
    sizes = {o.get("name"): o.get("size") for o in want}
    objs: List[Dict] = []
    for o in raw:
        t, lat, lon, alt = (np.asarray(o[k], dtype=np.float64) for k in ("t", "lat", "lon", "alt"))
        ok = np.isfinite(t) & np.isfinite(lat) & np.isfinite(lon) & (np.abs(lat) <= 90) & (np.abs(lon) <= 180)
        if ok.sum() < 2:
            continue
        cols = [t[ok], lat[ok], lon[ok], np.where(np.isfinite(alt[ok]), alt[ok], np.nan)]
        for r in ("roll", "pitch", "yaw"):
            cols.append(np.asarray(o[r], dtype=np.float64)[ok] if o[r] is not None else np.full(int(ok.sum()), np.nan))
        d = mapimage._decimate(*cols, n=POINTS)
        objs.append({"name": o["name"], "color": o["color"] or "#3d8bfd", "kind": o["kind"] if o["kind"] in KINDS else "aircraft",
                     "size": float(sizes.get(o["name"]) or 26), "t": d[0], "lat": d[1], "lon": d[2], "alt": d[3],
                     "roll": d[4], "pitch": d[5], "yaw": d[6], "own": o["yaw"] is not None})
    if not objs:
        raise ValueError("The 3D view has no object with a position to draw.")
    lat_all = np.concatenate([o["lat"] for o in objs])
    lon_all = np.concatenate([o["lon"] for o in objs])
    box = mapimage._padded((float(lat_all.min()), float(lon_all.min()), float(lat_all.max()), float(lon_all.max())), frac=0.45, min_m=3000.0)
    s_, w_, n_, e_ = box
    lat0, lon0 = (s_ + n_) / 2, (w_ + e_) / 2
    # the terrain: heights above sea level, north row first, west to east (as the picture's pixels)
    glat = np.linspace(n_, s_, GRID)
    glon = np.linspace(w_, e_, GRID)
    LA, LO = np.meshgrid(glat, glon, indexing="ij")
    H = np.asarray(basemap.ground_at(LA.ravel(), LO.ravel()), dtype=np.float64).reshape(GRID, GRID)
    if not np.isfinite(H).any():
        H = np.zeros_like(H)
    H = np.where(np.isfinite(H), H, np.nanmin(H))
    cur = geo.get("cursor", sc.get("cursor"))
    for o in objs:
        e, n = _enu(o["lat"], o["lon"], lat0, lon0)
        g = np.asarray(basemap.ground_at(o["lat"], o["lon"]), dtype=np.float64)
        g = np.where(np.isfinite(g), g, float(np.median(H)))
        u = np.where(np.isfinite(o["alt"]), o["alt"], g + 2.0)
        if not np.isfinite(o["yaw"]).any():
            o["yaw"] = _course(e, n)                      # no angles at all: it points along its course
        o.update(e=e, n=n, u=u, g=g)
        o["at"] = len(o["t"]) - 1 if cur is None else int(np.clip(np.searchsorted(o["t"], float(cur)), 0, len(o["t"]) - 1))
    E0, N0 = _enu(s_, w_, lat0, lon0)
    E1, N1 = _enu(n_, e_, lat0, lon0)
    base = str(geo.get("base") or "offline")
    base = base if base in mapimage.ATTRIB else "offline"
    return {"title": spec.get("title") or "", "objects": objs, "origin": (lat0, lon0), "bounds": box,
            "extent": (float(E0), float(E1), float(N0), float(N1)), "heights": H, "cursor": cur, "base": base,
            "follow": sc.get("follow"), "primary": sc.get("primary"), "secondary": sc.get("secondary")}


# ---- the picture ----------------------------------------------------------------------------------

def _exaggeration(sd: Dict) -> float:
    """Heights drawn this many times: enough that a flight over flat ground still shows its climb."""
    E0, E1, N0, N1 = sd["extent"]
    span = max(E1 - E0, N1 - N0)
    lo = min(float(sd["heights"].min()), min(float(np.nanmin(o["u"])) for o in sd["objects"]))
    hi = max(float(sd["heights"].max()), max(float(np.nanmax(o["u"])) for o in sd["objects"]))
    dz = max(hi - lo, 1.0)
    return float(min(10.0, max(1.0, round(0.18 * span / dz))))


def render(sd: Dict, fmt: str = "png", theme: str = "light", scale: float = 1.0, size=(9.0, 6.0)) -> bytes:
    """The 3D scene as a picture: the ground (map draped on the terrain), tracks with their shadow, the objects
    at the cursor with their names, a north arrow, the height scale and the attribution."""
    from app.report import _pyplot
    plt = _pyplot()
    dark = theme == "dark"
    ink, paper = ("#e6edf3", "#151b23") if dark else ("#1f2a36", "#ffffff")
    fig = plt.figure(figsize=size, dpi=int(110 * scale), facecolor=paper)
    ax = fig.add_axes((0, 0, 1, 1), projection="3d", computed_zorder=False)   # the ground under the tracks, always
    ax.set_facecolor(paper)
    ax.set_axis_off()
    E0, E1, N0, N1 = sd["extent"]
    ex = _exaggeration(sd)
    # the ground: a coarser grid (matplotlib draws one polygon per cell), coloured from the map picture
    k = 49
    idx = np.linspace(0, GRID - 1, k).round().astype(int)
    Hs = sd["heights"][np.ix_(idx, idx)]
    Es = np.linspace(E0, E1, k)
    Ns = np.linspace(N1, N0, k)
    EE, NN = np.meshgrid(Es, Ns)
    img, used = _ground_image(sd["bounds"], sd["base"], dark, 512)
    if img is not None:
        h, w = img.shape[:2]
        fc = img[np.ix_(np.linspace(0, h - 1, k).round().astype(int), np.linspace(0, w - 1, k).round().astype(int))] / 255.0
    else:
        fc = np.broadcast_to(np.array([0.55, 0.62, 0.5] if not dark else [0.2, 0.24, 0.22]), (k, k, 3))
    ax.plot_surface(EE, NN, Hs * ex, facecolors=fc, rstride=1, cstride=1, linewidth=0, antialiased=False, shade=False, zorder=0)
    for o in sd["objects"]:
        ax.plot(o["e"], o["n"], o["g"] * ex + 1, color="#000000", alpha=0.25, lw=1.0 * scale, zorder=2)
        ax.plot(o["e"], o["n"], o["u"] * ex, color=o["color"], lw=1.8 * scale, zorder=3, label=o["name"])
        a = o["at"]
        ax.plot([o["e"][a], o["e"][a]], [o["n"][a], o["n"][a]], [o["g"][a] * ex, o["u"][a] * ex], color=o["color"], lw=0.8 * scale, alpha=0.6, zorder=3)
        ax.scatter([o["e"][a]], [o["n"][a]], [o["u"][a] * ex], s=40 * scale * scale, c=o["color"], edgecolors=paper, linewidths=1.2 * scale, zorder=5, depthshade=False)
        ax.text(o["e"][a], o["n"][a], o["u"][a] * ex, "  " + o["name"], color=ink, fontsize=8 * scale, zorder=6)
    zs = np.concatenate([sd["heights"].ravel()] + [o["u"] for o in sd["objects"]]) * ex
    ax.set_xlim(E0, E1); ax.set_ylim(N0, N1); ax.set_zlim(float(zs.min()), float(zs.max()) + 1)
    ax.set_box_aspect((E1 - E0, N1 - N0, max(1.0, float(zs.max() - zs.min()))))
    ax.view_init(elev=32, azim=-62)
    leg = ax.legend(loc="upper left", fontsize=8 * scale, framealpha=0.85, facecolor=paper, edgecolor="none")
    for txt in leg.get_texts():
        txt.set_color(ink)
    att = " · ".join(mapimage.ATTRIB[s] for s in sorted(used or {"offline"}))
    fig.text(0.995, 0.005, att, ha="right", va="bottom", fontsize=6 * scale, color=ink)
    fig.text(0.005, 0.005, f"heights x{ex:g}" if ex > 1 else "", ha="left", va="bottom", fontsize=7 * scale, color=ink)
    if sd.get("title"):
        fig.text(0.5, 0.985, sd["title"], ha="center", va="top", fontsize=11 * scale, color=ink, fontweight="bold")
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, facecolor=paper)
    plt.close(fig)
    return buf.getvalue()


# ---- the live page --------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def model(kind: str) -> Optional[Dict]:
    """The app's 3D model of a kind (frontend/public/models/<kind>.glb) as plain triangles: parts of
    {p: positions, n: normals, i: indices, tint: drawn in the object's colour (a white material) or not}.
    A .glb is a JSON header and one binary block - read with struct / numpy, no glTF library."""
    path = next((p for p in (os.path.join(d, f"{kind}.glb") for d in MODEL_DIRS) if os.path.exists(p)), "")
    try:
        with open(path, "rb") as f:
            b = f.read()
        jl = struct.unpack("<I", b[12:16])[0]
        j = json.loads(b[20:20 + jl])
        bin_ = b[20 + jl + 8:]
        types = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}
        sizes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}

        def acc(i):
            a = j["accessors"][i]
            v = j["bufferViews"][a["bufferView"]]
            off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
            dt = types[a["componentType"]]
            n = a["count"] * sizes[a["type"]]
            return np.frombuffer(bin_, dtype=dt, count=n, offset=off)
        parts = []
        for prim in j["meshes"][0]["primitives"]:
            mat = j.get("materials", [{}])[prim.get("material", 0)] if j.get("materials") else {}
            col = (mat.get("pbrMetallicRoughness") or {}).get("baseColorFactor") or [1, 1, 1, 1]
            p = acc(prim["attributes"]["POSITION"])
            nn = acc(prim["attributes"]["NORMAL"]) if "NORMAL" in prim["attributes"] else None
            ii = acc(prim["indices"]) if "indices" in prim else np.arange(len(p) // 3)
            parts.append({"p": np.round(p, 4).tolist(), "n": None if nn is None else np.round(nn, 3).tolist(),
                          "i": ii.astype(int).tolist(), "tint": bool(min(col[:3]) > 0.9),
                          "color": "#%02x%02x%02x" % tuple(int(255 * c) for c in col[:3])})
        return {"parts": parts}
    except (OSError, KeyError, IndexError, ValueError, struct.error):
        return None                                   # a missing / unreadable model: the page draws a dart


def _r(a, d):
    return np.round(np.asarray(a, dtype=np.float64), d).tolist()


def _nan_none(a, d):
    a = np.asarray(a, dtype=np.float64)
    return [None if not math.isfinite(v) else v for v in np.round(a, d).tolist()]


STRINGS = {
    "en": {"fit": "Fit all tracks", "top": "From above", "follow": "Follow", "none": "Nothing", "ex": "Heights",
           "theme": "Light / dark", "noGl": "This browser cannot draw 3D (WebGL is off) - the picture shows the moment the page was made.",
           "agl": "above ground", "time": "Time", "help": "Drag: turn · right-drag or Shift: move · wheel: zoom"},
    "he": {"fit": "כל המסלולים", "top": "מלמעלה", "follow": "לעקוב אחרי", "none": "אף אחד", "ex": "גבהים",
           "theme": "בהיר / כהה", "noGl": "הדפדפן הזה לא יכול לצייר תלת-ממד (WebGL כבוי) - התמונה מראה את הרגע שבו הדף נוצר.",
           "agl": "מעל הקרקע", "time": "זמן", "help": "גרירה: סיבוב · גרירה ימנית או Shift: הזזה · גלגלת: זום"},
}


def build_html(sd: Dict, theme: str = "light", lang: str = "en", fallback_png: Optional[bytes] = None) -> str:
    """The scene as one page that opens anywhere with no network (three.js and every picture embedded)."""
    dark = theme == "dark"
    tex: Dict[str, str] = {}
    used: set = set()
    for th in ("light", "dark"):
        img, u = _ground_image(sd["bounds"], sd["base"], th == "dark")
        if img is not None:
            tex[th] = _jpeg(img)
            used |= u
    kinds = sorted({o["kind"] for o in sd["objects"]})
    data = {
        "title": sd["title"], "extent": list(sd["extent"]), "origin": list(sd["origin"]), "grid": GRID,
        "heights": _r(sd["heights"].ravel(), 1), "textures": tex, "cursor": sd["cursor"], "dark": dark,
        "follow": sd.get("follow"), "primary": sd.get("primary"), "secondary": sd.get("secondary"),
        "models": {k: model(k) for k in kinds}, "ex": 1,
        "attribution": " · ".join(mapimage.ATTRIB[s] for s in sorted(used or {"offline"})),
        "S": STRINGS.get(lang, STRINGS["en"]),
        "fallback": "data:image/png;base64," + base64.b64encode(fallback_png if fallback_png is not None else render(sd, "png", theme, 1.4)).decode(),
        "objects": [{"name": o["name"], "color": o["color"], "kind": o["kind"], "size": o["size"], "t": _r(o["t"], 3),
                     "e": _r(o["e"], 2), "n": _r(o["n"], 2), "u": _r(o["u"], 2), "g": _r(o["g"], 1),
                     "roll": _nan_none(o["roll"], 2), "pitch": _nan_none(o["pitch"], 2), "yaw": _nan_none(o["yaw"], 2)} for o in sd["objects"]],
    }
    note = (f"Embedded: three.js r159 (MIT), the ground picture ({', '.join(tex) or 'none'}), terrain {GRID} x {GRID}, "
            f"{len(data['objects'])} tracks of at most {POINTS} points, models: {', '.join(kinds)}.")
    with open(os.path.join(ASSETS, "scene3d.html"), encoding="utf-8") as f:
        page = f.read()
    with open(os.path.join(ASSETS, "three.min.js"), encoding="utf-8") as f:
        three = f.read()
    three = three.replace("</script", "<\\/script")
    return (page.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
                .replace("<!--__NOTE__-->", f"<!-- {note} -->")
                .replace("__NOTE_TEXT__", mapimage._esc(note))
                .replace("__TITLE__", mapimage._esc(sd["title"] or "3D"))
                .replace("__LANG__", "he" if lang == "he" else "en")
                .replace("__DIR__", "rtl" if lang == "he" else "ltr")
                .replace("/*__THREE__*/", three))
