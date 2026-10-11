"""
Build the offline basemap that ships with Signal Viewer (run once, on a machine with internet).

    python tools/make_basemap.py --dem      # elevation grids: world, region, Israel
    python tools/make_basemap.py --ne       # Natural Earth: land, lakes, rivers, roads, places, airports
    python tools/make_basemap.py --osm      # OpenStreetMap, Israel and surroundings: roads, places, airports
    python tools/make_basemap.py --all

Output: backend/app/basemap_data/ (read by backend/app/basemap.py). Sources and licences:
  * Elevation: AWS Open Data "Terrain Tiles" (Mapzen / Tilezen; SRTM, GMTED2010, ETOPO1 and
    others) - open, with attribution.
  * Natural Earth - public domain.
  * OpenStreetMap (Geofabrik extracts) - (c) OpenStreetMap contributors, ODbL: the map shows the attribution.
Needs: numpy, Pillow, pyshp and osmium (pyosmium) - only this tool needs the last two.
"""
import argparse
import concurrent.futures as cf
import gzip
import io
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
import zipfile

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "backend", "app", "basemap_data")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "sv-basemap")
UA = "SignalViewer-basemap-builder/1 (one-off download for an offline desktop app)"

# The areas. Region: Israel and its close surroundings; Israel: the detailed core.
REGION = (27.5, 31.5, 35.5, 39.0)        # south, west, north, east
ISRAEL = (29.3, 34.1, 33.5, 36.0)
GRIDS = {                                # name: (bounds, step in degrees, terrain-tile zoom)
    "world": ((-85.0, -180.0, 85.0, 180.0), 0.1, 4),       # ~11 km
    "region": (REGION, 0.005, 8),                           # ~500 m
    "israel": (ISRAEL, 0.00125, 10),                        # ~130 m
}


def fetch(url, data=None, tries=4, wait=3):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, urllib.parse.quote(url + (("?" + data.decode()) if data else ""), safe="")[-180:])
    if os.path.exists(key):
        with open(key, "rb") as f:
            return f.read()
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as r:
                body = r.read()
            with open(key, "wb") as f:
                f.write(body)
            return body
        except Exception as e:                                   # noqa: BLE001
            if i == tries - 1:
                raise
            print("  retry", url[:80], e, file=sys.stderr)
            time.sleep(wait * (i + 1))


# ------------------------------------------------------------------ elevation
def _tile_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _terrarium(z, x, y):
    from PIL import Image
    raw = fetch(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png")
    a = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"), dtype=np.float32)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


def build_grid(name, bounds=None, step=None, z=None, path=None):
    """An elevation grid: one of GRIDS by name, or any bounds / step (degrees) / tile zoom into `path`."""
    if bounds is None:
        bounds, step, z = GRIDS[name]
    (s, w, n, e) = bounds
    x0, y0 = _tile_xy(n, w, z)
    x1, y1 = _tile_xy(s, e, z)
    tx = range(int(x0), int(math.ceil(x1)))
    ty = range(int(y0), int(math.ceil(y1)))
    print(f"{name}: {len(tx) * len(ty)} terrain tiles at zoom {z}")
    mosaic = np.zeros((len(ty) * 256, len(tx) * 256), dtype=np.float32)
    jobs = {(i, j): (z, X, Y) for j, Y in enumerate(ty) for i, X in enumerate(tx)}
    with cf.ThreadPoolExecutor(6) as ex:
        for (i, j), arr in zip(jobs, ex.map(lambda a: _terrarium(*a), jobs.values())):
            mosaic[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] = arr
    lats = np.arange(n, s - step / 2, -step)                     # north to south
    lons = np.arange(w, e + step / 2, step)
    N = 2 ** z
    px = ((lons + 180) / 360 * N - tx.start) * 256 - 0.5
    lr = np.radians(lats)
    py = ((1 - np.log(np.tan(lr) + 1 / np.cos(lr)) / np.pi) / 2 * N - ty.start) * 256 - 0.5
    px = np.clip(px, 0, mosaic.shape[1] - 1.001)
    py = np.clip(py, 0, mosaic.shape[0] - 1.001)
    ix, iy = px.astype(int), py.astype(int)
    fx, fy = (px - ix)[None, :], (py - iy)[:, None]
    a = mosaic[np.ix_(iy, ix)]
    b = mosaic[np.ix_(iy, ix + 1)]
    c = mosaic[np.ix_(iy + 1, ix)]
    d = mosaic[np.ix_(iy + 1, ix + 1)]
    grid = (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy)
    # sea depths are not drawn (water comes from the land / lake shapes): floored at -500 m, which keeps
    # every place on land (the Dead Sea shore is ~ -430 m) and lets the oceans compress to almost nothing
    grid = np.clip(np.round(grid), -500, 9000).astype(np.int16)
    path = path or os.path.join(OUT, f"dem_{name}.npz")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, h=grid, bounds=np.array([s, w, n, e], dtype=np.float64), step=np.float64(step))
    print(f"  -> {path}: {grid.shape[1]} x {grid.shape[0]}, {os.path.getsize(path) / 1e6:.1f} MB,"
          f" heights {grid.min()}..{grid.max()} m")


# ------------------------------------------------------------------ vectors
def rdp(pts, eps):
    """Ramer-Douglas-Peucker on an (n, 2) array; iterative."""
    n = len(pts)
    if n < 3 or eps <= 0:
        return pts
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p, q = pts[a], pts[b]
        seg = q - p
        L = np.hypot(*seg)
        mid = pts[a + 1:b]
        d = np.abs(seg[0] * (mid[:, 1] - p[1]) - seg[1] * (mid[:, 0] - p[0])) / L if L > 0 else np.hypot(*(mid - p).T)
        k = int(np.argmax(d))
        if d[k] > eps:
            keep[a + 1 + k] = True
            stack += [(a, a + 1 + k), (a + 1 + k, b)]
    return pts[keep]


Q = 1e5                                                          # coordinates stored as integers (~1 m)


def _q(pts):
    return np.round(np.asarray(pts, dtype=np.float64) * Q).astype(np.int64).ravel().tolist()


def _shapes(name, kind):
    import shapefile
    raw = fetch(f"https://naciscdn.org/naturalearth/10m/{kind}/{name}.zip")
    z = zipfile.ZipFile(io.BytesIO(raw))
    base = name
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                         shx=io.BytesIO(z.read(base + ".shx")), encoding="utf-8", encodingErrors="replace")
    fields = [f[0].lower() for f in r.fields[1:]]
    for sr in r.iterShapeRecords():
        yield sr.shape, dict(zip(fields, sr.record))


def _parts(shape):
    pts, parts = shape.points, list(shape.parts) + [len(shape.points)]
    return [np.asarray(pts[parts[i]:parts[i + 1]], dtype=np.float64) for i in range(len(parts) - 1)]


def build_ne():
    out = {"land": [], "lakes": [], "rivers": [], "roads": [], "places": [], "airports": []}
    for shp, rec in _shapes("ne_10m_land", "physical"):
        for p in _parts(shp):
            p = rdp(p, 0.004)
            if len(p) >= 4:
                out["land"].append(_q(p))
    for shp, rec in _shapes("ne_10m_lakes", "physical"):
        for p in _parts(shp):
            p = rdp(p, 0.002)
            if len(p) >= 4:
                out["lakes"].append({"r": int(rec.get("scalerank", 9) or 9), "c": _q(p)})
    for shp, rec in _shapes("ne_10m_rivers_lake_centerlines", "physical"):
        for p in _parts(shp):
            p = rdp(p, 0.005)
            if len(p) >= 2:
                out["rivers"].append({"r": int(rec.get("scalerank", 9) or 9), "c": _q(p)})
    for shp, rec in _shapes("ne_10m_roads", "cultural"):
        t = str(rec.get("type", ""))
        if "Ferry" in t:
            continue
        cls = 1 if "Major" in t else 2 if "Secondary" in t else 3
        if cls == 3:                    # world layer: main roads only (Israel's details come from OSM)
            continue
        for p in _parts(shp):
            p = rdp(p, 0.003)
            if len(p) >= 2:
                out["roads"].append({"k": cls, "r": int(rec.get("scalerank", 9) or 9), "c": _q(p)})
    for shp, rec in _shapes("ne_10m_populated_places", "cultural"):
        lon, lat = shp.points[0]
        out["places"].append({"x": round(lon, 5), "y": round(lat, 5), "n": rec.get("name") or "",
                              "h": rec.get("name_he") or "", "r": int(rec.get("labelrank", 9) or 9),
                              "p": int(rec.get("pop_max", 0) or 0)})
    for shp, rec in _shapes("ne_10m_airports", "cultural"):
        lon, lat = shp.points[0]
        out["airports"].append({"x": round(lon, 5), "y": round(lat, 5), "n": rec.get("name") or "",
                                "c": rec.get("iata_code") or ""})
    _write("vectors_world.json.gz", out)


COUNTRIES = ["asia/israel-and-palestine", "asia/jordan", "asia/lebanon", "asia/syria", "africa/egypt"]
ROAD_RANK = {"motorway": 1, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4}
PLACE_RANK = {"city": 1, "town": 2, "village": 3}


def _inside(b, lon, lat):
    return b[0] <= lat <= b[2] and b[1] <= lon <= b[3]


def _osm_country(path, region=REGION, detail=ISRAEL):
    """One Geofabrik extract -> roads, places, airports, runways inside the region (cached as JSON).
    Main roads in the whole region; secondary / tertiary roads and villages only in Israel's box."""
    import osmium
    done = path + (".sv.json" if (region, detail) == (REGION, ISRAEL) else f".{'_'.join(f'{v:g}' for v in region + detail)}.sv.json")
    if os.path.exists(done):
        with open(done, encoding="utf-8") as f:
            return json.load(f)
    out = {"roads": [], "places": [], "airports": [], "runways": []}

    class H(osmium.SimpleHandler):
        def node(self, n):
            t = n.tags
            if not n.location.valid():
                return
            lon, lat = n.location.lon, n.location.lat
            if not _inside(region, lon, lat):
                return
            place = t.get("place")
            if place in PLACE_RANK and (place != "village" or _inside(detail, lon, lat)) and (t.get("name") or t.get("name:en")):
                pop = (t.get("population") or "0").replace(",", "")
                out["places"].append({"x": round(lon, 5), "y": round(lat, 5), "k": PLACE_RANK[place],
                                      "n": t.get("name:en") or t.get("name"), "h": t.get("name:he") or "",
                                      "p": int(pop) if pop.isdigit() else 0})
            if t.get("aeroway") == "aerodrome":
                out["airports"].append({"x": round(lon, 5), "y": round(lat, 5), "n": t.get("name:en") or t.get("name") or "",
                                        "h": t.get("name:he") or "", "c": t.get("iata") or t.get("icao") or ""})

        def way(self, w):
            t = w.tags
            hw, aw = t.get("highway"), t.get("aeroway")
            if hw not in ROAD_RANK and aw not in ("runway", "aerodrome"):
                return
            try:
                pts = np.array([[nd.lon, nd.lat] for nd in w.nodes if nd.location.valid()], dtype=np.float64)
            except osmium.InvalidLocationError:
                return
            if len(pts) < 2:
                return
            lon, lat = pts[:, 0].mean(), pts[:, 1].mean()
            if not _inside(region, lon, lat):
                return
            if hw in ROAD_RANK:
                if ROAD_RANK[hw] >= 3 and not _inside(detail, lon, lat):
                    return
                out["roads"].append({"id": w.id, "k": ROAD_RANK[hw], "c": _q(rdp(pts, 0.0002))})
            elif aw == "runway":
                out["runways"].append({"id": w.id, "c": _q(pts)})
            else:
                out["airports"].append({"x": round(lon, 5), "y": round(lat, 5), "n": t.get("name:en") or t.get("name") or "",
                                        "h": t.get("name:he") or "", "c": t.get("iata") or t.get("icao") or ""})

    H().apply_file(path, locations=True, idx="flex_mem")
    with open(done, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return out


def build_osm(only=None):
    merged = {"roads": [], "places": [], "airports": [], "runways": []}
    seen = set()
    for c in COUNTRIES:
        if only and only not in c:
            continue
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, c.replace("/", "_") + ".osm.pbf")
        if not os.path.exists(path):
            print("downloading", c)
            req = urllib.request.Request(f"https://download.geofabrik.de/{c}-latest.osm.pbf", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(path + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            os.replace(path + ".part", path)
        t0 = time.time()
        part = _osm_country(path)
        print(f"  {c}: " + ", ".join(f"{k} {len(v)}" for k, v in part.items()) + f" ({time.time() - t0:.0f} s)")
        for k in ("roads", "runways"):
            for it in part[k]:
                if it["id"] in seen:                          # a way in two extracts (at a border)
                    continue
                seen.add(it["id"])
                merged[k].append({kk: vv for kk, vv in it.items() if kk != "id"} if k == "roads" else it["c"])
        for k in ("places", "airports"):
            for it in part[k]:
                key = (k, it["x"], it["y"], it["n"])
                if key in seen:
                    continue
                seen.add(key)
                merged[k].append(it)
    if not only:
        _write("vectors_israel.json.gz", merged)


def build_pack(name, bounds, countries, zoom=10, out=None):
    """A detailed area for the offline map: elevation (~130 m at zoom 10, ~500 m at 8), OpenStreetMap
    roads down to regional ones, places down to villages, airports and runways inside `bounds`.
    Written to <out or backend/app/basemap_data/packs>/<name>/ - the app picks every pack up."""
    d = os.path.join(out or os.path.join(OUT, "packs"), name)
    os.makedirs(d, exist_ok=True)
    step = {8: 0.005, 9: 0.0025, 10: 0.00125, 11: 0.000625}.get(zoom, 0.00125)
    build_grid(name, bounds, step, zoom, os.path.join(d, "dem.npz"))
    merged = {"roads": [], "places": [], "airports": [], "runways": []}
    seen = set()
    for c in countries:
        path = os.path.join(CACHE, c.replace("/", "_") + ".osm.pbf")
        if not os.path.exists(path):
            print("downloading", c)
            os.makedirs(CACHE, exist_ok=True)
            req = urllib.request.Request(f"https://download.geofabrik.de/{c}-latest.osm.pbf", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(path + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            os.replace(path + ".part", path)
        part = _osm_country(path, bounds, bounds)
        for k in ("roads", "runways"):
            for it in part[k]:
                if it["id"] not in seen:
                    seen.add(it["id"])
                    merged[k].append({kk: vv for kk, vv in it.items() if kk != "id"} if k == "roads" else it["c"])
        for k in ("places", "airports"):
            for it in part[k]:
                key = (k, it["x"], it["y"], it["n"])
                if key not in seen:
                    seen.add(key)
                    merged[k].append(it)
    with gzip.open(os.path.join(d, "vectors.json.gz"), "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(merged, f, separators=(",", ":"), ensure_ascii=False)
    with open(os.path.join(d, "pack.json"), "w", encoding="utf-8") as f:
        json.dump({"name": name, "bounds": list(bounds), "countries": countries, "zoom": zoom}, f, indent=1)
    size = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)) / 1e6
    print(f"  -> pack {name}: {d} ({size:.1f} MB); " + ", ".join(f"{k} {len(v)}" for k, v in merged.items()))


def _write(name, obj):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
    print(f"  -> {path}: {os.path.getsize(path) / 1e6:.1f} MB; " + ", ".join(f"{k} {len(v)}" for k, v in obj.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", action="store_true")
    ap.add_argument("--grid", choices=list(GRIDS), help="only this elevation grid")
    ap.add_argument("--ne", action="store_true")
    ap.add_argument("--osm", action="store_true")
    ap.add_argument("--country", help="only download / read this extract (e.g. jordan); --osm then merges all")
    ap.add_argument("--pack", help="build a detailed area pack with this name (with --bbox and --countries)")
    ap.add_argument("--bbox", help="the pack's area: south,west,north,east (degrees)")
    ap.add_argument("--countries", help="Geofabrik extracts covering it, e.g. europe/cyprus,asia/lebanon")
    ap.add_argument("--zoom", type=int, default=10, help="elevation detail: 10 ~130 m, 9 ~250 m, 8 ~500 m")
    ap.add_argument("--out", help="folder for the pack (default backend/app/basemap_data/packs)")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.dem or a.all or a.grid:
        for g in ([a.grid] if a.grid else GRIDS):
            build_grid(g)
    if a.ne or a.all:
        build_ne()
    if a.pack:
        if not a.bbox or not a.countries:
            ap.error("--pack needs --bbox and --countries")
        build_pack(a.pack, tuple(float(v) for v in a.bbox.split(",")), [c.strip() for c in a.countries.split(",")], a.zoom, a.out)
    elif a.country:
        build_osm(a.country)
    elif a.osm or a.all:
        build_osm()


if __name__ == "__main__":
    main()
