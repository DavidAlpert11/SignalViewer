"""
L11: a map plot's objects drawn by the server - a PNG / SVG (the map's ⋯ menu, PDF / Word / PNG reports)
and a standalone interactive HTML map (the ⋯ menu, HTML reports). Its own module (not report.py): the
export route and the three report builders all call it, and report.py is already the plots' module.

What is drawn: the offline basemap (app/basemap.py, no network) - or, when the user has an online layer
on, that layer's tiles ALREADY in the app's tile cache (never fetched from here; a missing tile falls back to
the offline one); each object's track in its colour; its marker and name at the cursor time (else its last
point); a legend, a scale bar, a north arrow and the attribution line (always, for every layer used).

The spec (from the UI's plotSpec): {"mode": "geo", "title", "geo": {"objects": [{"name", "color", "lat",
"lon", "alt"?}], "base": "offline" | "osm" | ..., "cursor": t | null, "bounds": [s, w, n, e] | null}}.
"""
import base64
import io
import json
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from app import basemap, tiles

TILE = 256
LAT_MAX = 85.05112878
ATTRIB = {
    "offline": basemap.ATTRIBUTION,
    "osm": "© OpenStreetMap contributors",
    "esri": "Esri, HERE, Garmin, © OpenStreetMap contributors, GIS User Community",
    "light": "Esri, HERE, Garmin, © OpenStreetMap contributors, GIS User Community",
    "dark": "Esri, HERE, Garmin, © OpenStreetMap contributors, GIS User Community",
    "satellite": "Tiles © Esri — Esri, Maxar, Earthstar Geographics, GIS User Community",
    "topo": "© OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)",
}


def mx(lon):
    return (np.asarray(lon, dtype=np.float64) + 180.0) / 360.0


def my(lat):
    s = np.sin(np.radians(np.clip(np.asarray(lat, dtype=np.float64), -LAT_MAX, LAT_MAX)))
    return 0.5 - np.log((1 + s) / (1 - s)) / (4 * np.pi)


def _decimate(t: np.ndarray, *cols: np.ndarray, n: int = 3000):
    if len(t) <= n:
        return (t, *cols)
    idx = np.unique(np.linspace(0, len(t) - 1, n).astype(int))
    return (t[idx], *(c[idx] for c in cols))


def map_data(store, spec: Dict) -> Dict:
    """The objects' tracks (decimated, finite points only), their markers at the cursor and the bounds."""
    from svcore.analysis import align_to
    geo = spec.get("geo") or {}
    objs: List[Dict] = []
    for o in geo.get("objects") or []:
        tl, la = store.signal(o["lat"])
        _, lo = store.signal(o["lon"])
        tl = np.asarray(tl, dtype=np.float64)
        la = np.asarray(la, dtype=np.float64)
        lo = np.asarray(lo, dtype=np.float64)
        n = min(len(la), len(lo), len(tl))
        tl, la, lo = tl[:n], la[:n], lo[:n]
        al = None
        if o.get("alt"):
            ta, aa = store.signal(o["alt"])
            al = align_to(tl, np.asarray(ta, dtype=np.float64), aa, "linear")
        ok = np.isfinite(la) & np.isfinite(lo) & (np.abs(la) <= 90) & (np.abs(lo) <= 180)
        if not ok.any():
            continue
        cols = [tl[ok], la[ok], lo[ok]] + ([al[ok]] if al is not None else [])
        d = _decimate(*cols)
        objs.append({"name": str(o.get("name") or ""), "color": str(o.get("color") or "#3d8bfd"),
                     "track": o.get("track") if o.get("track") in ("dash", "points") else None,
                     "t": d[0], "lat": d[1], "lon": d[2], "alt": d[3] if al is not None else None})
    if not objs:
        raise ValueError("The map has no object with a position to draw.")
    b = geo.get("bounds")
    if b and len(b) == 4 and all(isinstance(v, (int, float)) for v in b):
        s_, w_, n_, e_ = (float(v) for v in b)
    else:
        lat_all = np.concatenate([o["lat"] for o in objs])
        lon_all = np.concatenate([o["lon"] for o in objs])
        s_, n_, w_, e_ = float(lat_all.min()), float(lat_all.max()), float(lon_all.min()), float(lon_all.max())
    cur = geo.get("cursor")
    for o in objs:
        k = len(o["t"]) - 1 if cur is None else int(np.clip(np.searchsorted(o["t"], float(cur)), 0, len(o["t"]) - 1))
        o["at"] = k
    base = str(geo.get("base") or "offline")
    return {"title": spec.get("title") or "", "objects": objs, "bounds": (s_, w_, n_, e_), "cursor": cur,
            "base": base if base in ATTRIB else "offline", "pair": {"primary": geo.get("primary"), "secondary": geo.get("secondary")}}


# ---- tiles ---------------------------------------------------------------------------------------

def _cached_online(src: str, z: int, x: int, y: int) -> Optional[bytes]:
    """An online layer's tile only if it is already in the app's tile cache - never fetched here (Q9)."""
    s = tiles.SOURCES.get(src)
    if not s:
        return None
    path = os.path.join(tiles.CACHE, src, str(z), str(x), f"{y}.{s['ext']}")
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def tile_bytes(base: str, dark: bool, z: int, x: int, y: int) -> Tuple[Optional[bytes], str]:
    """(image bytes, the layer it came from): the chosen online layer from the cache, else the offline map."""
    if base != "offline":
        data = _cached_online(base, z, x, y)
        if data:
            return data, base
    style = "offline_topo_dark" if dark else "offline_topo"
    zz = min(z, basemap.MAX_ZOOM)
    if zz != z:                                                       # deeper than the offline data: its parent tile
        return None, "offline"
    got = tiles.tile(style, z, x, y)
    return (got[0] if got else None), "offline"


def _zoom_for(bounds, width_px: int, max_zoom: int = basemap.MAX_ZOOM) -> int:
    s_, w_, n_, e_ = bounds
    span = max(float(mx(e_) - mx(w_)), float(my(s_) - my(n_)), 1e-9)
    z = int(math.floor(math.log2(width_px / (span * TILE))))
    return max(1, min(max_zoom, z))


def _padded(bounds, frac=0.08, min_m=200.0):
    """The bounds with a margin, and at least a few hundred metres across (a point is still a map)."""
    s_, w_, n_, e_ = bounds
    dlat = max(n_ - s_, min_m / 111_320)
    dlon = max(e_ - w_, min_m / (111_320 * max(0.1, math.cos(math.radians((s_ + n_) / 2)))))
    cl, cn = (s_ + n_) / 2, (w_ + e_) / 2
    return (cl - dlat * (0.5 + frac), cn - dlon * (0.5 + frac), cl + dlat * (0.5 + frac), cn + dlon * (0.5 + frac))


def _image(data: bytes):
    from PIL import Image
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))


def _scale_len(m: float) -> float:
    """A round length (1, 2, 5 x 10^k metres) about a fifth of the view."""
    k = 10 ** math.floor(math.log10(max(m, 1e-6)))
    for f in (5, 2, 1):
        if f * k <= m:
            return f * k
    return k


# ---- PNG / SVG ----------------------------------------------------------------------------------

def render(mdata: Dict, fmt: str = "png", theme: str = "light", scale: float = 1.0, size=(9.0, 6.0)) -> bytes:
    """The map as a PNG (or SVG): tiles, tracks, markers at the cursor, legend, scale bar, north arrow, attribution."""
    from app.report import _pyplot
    plt = _pyplot()
    dark = theme == "dark"
    ink, paper = ("#e6edf3", "#151b23") if dark else ("#1f2a36", "#ffffff")
    dpi = int(110 * scale)
    fig = plt.figure(figsize=size, dpi=dpi, facecolor=paper)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    s_, w_, n_, e_ = _padded(mdata["bounds"])
    x0, x1, y0, y1 = float(mx(w_)), float(mx(e_)), float(my(n_)), float(my(s_))
    # keep the figure's aspect: widen the shorter side
    W, H = size[0] * dpi, size[1] * dpi
    if (x1 - x0) / (y1 - y0) < W / H:
        c = (x0 + x1) / 2; half = (y1 - y0) * W / H / 2; x0, x1 = c - half, c + half
    else:
        c = (y0 + y1) / 2; half = (x1 - x0) * H / W / 2; y0, y1 = c - half, c + half
    z = max(1, min(basemap.MAX_ZOOM if mdata["base"] == "offline" else tiles.SOURCES.get(mdata["base"], {"max": 19})["max"],
                   int(math.floor(math.log2(W / ((x1 - x0) * TILE))))))
    used = set()
    n = 2 ** z
    for tx in range(int(math.floor(x0 * n)), int(math.floor(x1 * n)) + 1):
        for ty in range(max(0, int(math.floor(y0 * n))), min(n - 1, int(math.floor(y1 * n))) + 1):
            data, src = tile_bytes(mdata["base"], dark, z, tx % n, ty)
            if not data:
                continue
            used.add(src)
            ax.imshow(_image(data), extent=(tx / n, (tx + 1) / n, (ty + 1) / n, ty / n), interpolation="bilinear", zorder=0)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    # tracks, then the markers and names at the cursor
    for o in mdata["objects"]:
        X, Y = mx(o["lon"]), my(o["lat"])
        ax.plot(X, Y, color=paper, lw=3.2 * scale, alpha=0.7, zorder=2, solid_capstyle="round")
        ax.plot(X, Y, color=o["color"], lw=1.8 * scale, zorder=3, label=o["name"], solid_capstyle="round")
        k = o["at"]
        ax.plot([X[k]], [Y[k]], marker="o", ms=7 * scale, mfc=o["color"], mec=paper, mew=1.5 * scale, zorder=5)
        ax.annotate(o["name"], (X[k], Y[k]), xytext=(7 * scale, 5 * scale), textcoords="offset points", fontsize=8 * scale,
                    color=ink, zorder=6, bbox=dict(boxstyle="round,pad=0.2", fc=paper, ec="none", alpha=0.75))
    leg = ax.legend(loc="upper left", fontsize=8 * scale, framealpha=0.85, facecolor=paper, edgecolor="none")
    for txt in leg.get_texts():
        txt.set_color(ink)
    # scale bar (metres at the view's middle latitude), north arrow, attribution
    lat_mid = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y0 + y1) / 2))))
    m_per_unit = 40_075_016.686 * math.cos(math.radians(lat_mid))
    L = _scale_len((x1 - x0) * m_per_unit / 5)
    bx, by = x0 + (x1 - x0) * 0.04, y0 + (y1 - y0) * 0.93
    ax.plot([bx, bx + L / m_per_unit], [by, by], color=ink, lw=2.5 * scale, zorder=7)
    ax.text(bx, by - (y1 - y0) * 0.015, f"{L / 1000:g} km" if L >= 1000 else f"{L:g} m", color=ink, fontsize=8 * scale, zorder=7)
    nx, ny = x0 + (x1 - x0) * 0.95, y0 + (y1 - y0) * 0.08
    ax.annotate("N", xy=(nx, ny), xytext=(nx, ny + (y1 - y0) * 0.07), ha="center", color=ink, fontsize=10 * scale, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=ink, lw=1.5 * scale), zorder=7)
    att = " · ".join(ATTRIB[s] for s in sorted(used or {"offline"}))
    fig.text(0.995, 0.005, att, ha="right", va="bottom", fontsize=6 * scale, color=ink,
             bbox=dict(boxstyle="square,pad=0.2", fc=paper, ec="none", alpha=0.75))
    if mdata.get("title"):
        fig.text(0.5, 0.985, mdata["title"], ha="center", va="top", fontsize=11 * scale, color=ink, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.3", fc=paper, ec="none", alpha=0.75))
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, facecolor=paper)
    plt.close(fig)
    return buf.getvalue()


# ---- standalone HTML ----------------------------------------------------------------------------

# The words of the offline map pages - the 2D map and the 3D view share their toolbar and relation box
# (report_assets/relation.js, mappage.css); the relation's words are the app's (i18n/mapsAnd3d.ts rel*).
PAGE_STRINGS = {
    "en": {"camera": "Camera", "camFree": "General", "camCentre": "On the object", "camClose": "Chase",
           "trail": "Trail", "trailAll": "whole", "tcaGo": "Go to the closest moment",
           "camFreeHint": "Move the view yourself", "camCentreHint": "Keep the chosen object in the middle",
           "camCloseHint": "Close to the chosen object (in 3D: behind it, looking where it goes)",
           "object": "Object", "zin": "Zoom in", "zout": "Zoom out", "fit": "Fit all tracks", "theme": "Light / dark",
           "relation": "Relation", "relationHint": "Show / hide the relation box (reference and compared object)",
           "ref": "Reference", "cmp": "Compared with", "swap": "Swap reference and compared", "hide": "Hide the box",
           "fold": "Fold the box", "unfold": "Unfold the box", "noTime": "— not both at this time —",
           "range": "Range", "horiz": "Horizontal", "dalt": "Δalt", "bearing": "Bearing", "relBearing": "Rel. bearing",
           "closure": "Closure", "tca": "Closest in", "hdgDiff": "Heading Δ", "time": "Time",
           "help": "Drag: move · wheel: zoom", "help3d": "Drag: turn · right-drag or Shift: move · wheel: zoom", "top": "From above", "ex": "Heights",
           "noGl": "This browser cannot draw 3D (WebGL is off) - the picture shows the moment the page was made.",
           "agl": "above ground"},
    "he": {"camera": "מצלמה", "camFree": "כללית", "camCentre": "על האובייקט", "camClose": "מרדף",
           "trail": "שובל", "trailAll": "כולו", "tcaGo": "לעבור לרגע הכי קרוב",
           "camFreeHint": "להזיז את התצוגה בעצמכם", "camCentreHint": "האובייקט שנבחר באמצע",
           "camCloseHint": "קרוב לאובייקט שנבחר (בתלת-ממד: מאחוריו, מסתכל לאן שהוא טס)",
           "object": "אובייקט", "zin": "התקרבות", "zout": "התרחקות", "fit": "כל המסלולים", "theme": "בהיר / כהה",
           "relation": "יחס", "relationHint": "הצגה / הסתרה של תיבת היחס (בסיס ומושווה)",
           "ref": "בסיס", "cmp": "מושווה", "swap": "החלפת הבסיס והמושווה", "hide": "הסתרת התיבה",
           "fold": "קיפול התיבה", "unfold": "פתיחת התיבה", "noTime": "— לא שניהם בזמן הזה —",
           "range": "טווח", "horiz": "אופקי", "dalt": "Δגובה", "bearing": "כיוון", "relBearing": "כיוון יחסי",
           "closure": "קצב התקרבות", "tca": "הכי קרוב בעוד", "hdgDiff": "Δכיוון", "time": "זמן",
           "help": "גרירה: הזזה · גלגלת: זום", "help3d": "גרירה: סיבוב · גרירה ימנית או Shift: הזזה · גלגלת: זום", "top": "מלמעלה", "ex": "גבהים",
           "noGl": "הדפדפן הזה לא יכול לצייר תלת-ממד (WebGL כבוי) - התמונה מראה את הרגע שבו הדף נוצר.",
           "agl": "מעל הקרקע"},
}


def page_parts(page: str) -> str:
    """The shared parts of an offline map page: its stylesheet and the toolbar / relation box script."""
    def read(n):
        with open(os.path.join(os.path.dirname(__file__), "report_assets", n), encoding="utf-8") as f:
            return f.read()
    return page.replace("/*__PAGE_CSS__*/", read("mappage.css")).replace("/*__RELATION__*/", read("relation.js"))

def _tiles_for(mdata: Dict, dark: bool, budget: int) -> Tuple[Dict[str, str], List[int], set]:
    """The tiles around the tracks' box at as many zoom levels as fit `budget` bytes (coarse first)."""
    s_, w_, n_, e_ = _padded(mdata["bounds"], frac=0.75)        # wide: a frame wider than the tracks shows no blank edge
    z0 = max(1, _zoom_for((s_, w_, n_, e_), 900) - 1)
    out: Dict[str, str] = {}
    levels: List[int] = []
    used = set()
    total = 0
    for z in range(z0, basemap.MAX_ZOOM + 3):
        n = 2 ** z
        xs = range(int(math.floor(float(mx(w_)) * n)), int(math.floor(float(mx(e_)) * n)) + 1)
        ys = range(max(0, int(math.floor(float(my(n_)) * n))), min(n - 1, int(math.floor(float(my(s_)) * n))) + 1)
        if len(xs) * len(ys) > 400:
            break
        got = {}
        for x in xs:
            for y in ys:
                data, src = tile_bytes(mdata["base"], dark, z, x % n, y)
                if data:
                    got[f"{z}/{x % n}/{y}"] = (data, src)
        size = sum(len(d) * 4 // 3 for d, _ in got.values())
        if not got or total + size > budget:
            break
        for k, (d, src) in got.items():
            mime = "image/png" if d[:4] == b"\x89PNG" else "image/jpeg"
            out[k] = f"data:{mime};base64,{base64.b64encode(d).decode()}"
            used.add(src)
        total += size
        levels.append(z)
    return out, levels, used


def build_html(mdata: Dict, theme: str = "light", budget: int = 15 * 1024 * 1024, lang: str = "en") -> str:
    """A map that opens anywhere with no network: the tiles embedded (a few zoom levels, within `budget`),
    the decimated tracks, pan / zoom, a time slider moving the markers, hover for name / time / lat / lon /
    alt, light / dark. Says in a comment and in its footer what was embedded."""
    light_t, light_lv, used_l = _tiles_for(mdata, False, budget // 2)
    dark_t, dark_lv, used_d = _tiles_for(mdata, True, budget // 2)
    objs = [{"name": o["name"], "color": o["color"], "track": o.get("track"), "t": np.round(o["t"], 3).tolist(), "lat": np.round(o["lat"], 7).tolist(),
             "lon": np.round(o["lon"], 7).tolist(), "alt": None if o["alt"] is None else np.round(o["alt"], 2).tolist()} for o in mdata["objects"]]
    data = {"title": mdata["title"], "objects": objs, "bounds": list(_padded(mdata["bounds"])), "cursor": mdata["cursor"],
            "tiles": {"light": light_t, "dark": dark_t}, "levels": {"light": light_lv, "dark": dark_lv},
            "attribution": " · ".join(ATTRIB[s] for s in sorted((used_l | used_d) or {"offline"})), "dark": theme == "dark",
            "pair": mdata.get("pair") or {}, "S": PAGE_STRINGS["he" if lang == "he" else "en"]}
    note = (f"Embedded: {len(light_t)} light and {len(dark_t)} dark map tiles, zoom levels {light_lv or '-'} / {dark_lv or '-'} "
            f"(budget {budget // (1024 * 1024)} MB); {len(objs)} tracks of at most 3000 points.")
    with open(os.path.join(os.path.dirname(__file__), "report_assets", "map.html"), encoding="utf-8") as f:
        page = f.read()
    page = page_parts(page)
    return (page.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
                .replace("<!--__NOTE__-->", f"<!-- {note} -->")
                .replace("__NOTE_TEXT__", note)
                .replace("__TITLE__", _esc(mdata["title"] or "Map"))
                .replace("__LANG__", "he" if lang == "he" else "en")
                .replace("__DIR__", "rtl" if lang == "he" else "ltr"))


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
