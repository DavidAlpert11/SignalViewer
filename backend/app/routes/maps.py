"""Offline map: terrain heights, places and map tiles."""

import asyncio
from typing import List, Optional

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import Response

from app.common import fail

router = APIRouter()




@router.get("/api/terrain/version")
def terrain_version():
    """P5: changes when fetched elevation arrived - the 3D view then asks its terrain again (the tile URLs
    carry it, so the browser's cache does not hold the coarser tile)."""
    from app import basemap
    return {"version": basemap.terrain_version()}


@router.get("/api/terrain/{z}/{x}/{y}")
def terrain(z: int, x: int, y: int):
    """Ground heights for the 3D view (from the bundled elevation grids; works offline)."""
    from app import basemap
    data = basemap.terrain_tile(z, x, y)
    if data is None:
        fail(404, "No terrain here.")
    return Response(content=data, media_type="application/octet-stream", headers={"Cache-Control": "max-age=86400"})



@router.get("/api/basemap/places")
def basemap_places():
    """Place and airport names for the offline map (it draws them itself, in the UI language)."""
    from app import basemap
    if not basemap.available():
        return {"places": [], "attribution": ""}
    return basemap.places()



def tiles_sources() -> set:
    from app import tiles
    return set(tiles.SOURCES) | set(tiles.COMPOSITES)


@router.get("/api/tiles/{src}/{z}/{x}/{y}")
async def map_tile(src: str, z: int, x: int, y: int, cached: int = 0):
    """A map tile (cached on disk). 404 when offline and not cached: the map then shows its own
    country borders only. `cached=1` (M1: the background picker's thumbnails): an online layer's tile only if
    it is on the disk already - opening the picker never downloads anything."""
    from fastapi.responses import Response

    from app.tiles import tile
    if cached and (src in tiles_sources() or src.startswith("my:")):
        from app import mapimage
        data = await asyncio.to_thread(mapimage._cached_online, src, z, x, y)
        if not data:
            return Response(status_code=404)
        media = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
        return Response(content=data, media_type=media, headers={"Cache-Control": "no-store"})
    r = await asyncio.to_thread(tile, src, z, x, y)
    if r is None:
        return Response(status_code=404)
    return Response(content=r[0], media_type=r[1], headers={"Cache-Control": "max-age=86400"})


# M3: KEEP AN AREA OFFLINE - only from sources whose terms allow bulk downloading (app/tilekeep.py)

class KeepBody(BaseModel):
    src: str
    bounds: List[float]
    zmin: int = 10
    zmax: int = 16
    name: str = ""


@router.post("/api/tiles/keep/estimate")
def keep_estimate(req: KeepBody):
    """How many tiles, about how big, how many are kept already, and whether the layer may be kept (and why)."""
    from app import tilekeep
    try:
        return tilekeep.estimate(req.src, req.bounds, req.zmin, req.zmax)
    except ValueError as e:
        fail(400, str(e))


@router.post("/api/tiles/keep")
def keep_start(req: KeepBody):
    """Start downloading the area in the background (progress: /api/tiles/keep/progress)."""
    from app import tilekeep
    try:
        return tilekeep.start(req.src, req.bounds, req.zmin, req.zmax, req.name)
    except ValueError as e:
        fail(400, str(e))


@router.get("/api/tiles/keep/progress")
def keep_progress():
    from app import tilekeep
    return tilekeep.progress()


@router.post("/api/tiles/keep/stop")
def keep_stop():
    from app import tilekeep
    return tilekeep.stop()


@router.get("/api/tiles/areas")
def kept_areas():
    """The kept areas with what of them is on the disk now."""
    from app import tilekeep
    return {"areas": tilekeep.areas()}


@router.delete("/api/tiles/areas/{area_id}")
def delete_kept_area(area_id: str):
    from app import tilekeep
    try:
        return tilekeep.delete(area_id)
    except KeyError:
        fail(404, "This kept area is not in the list any more (it was deleted already).")


# M4: MY MAPS - raster MBTiles files and the user's own tile server (app/mymaps.py), layers "my:<id>"

class MyMapBody(BaseModel):
    kind: str
    path: str = ""
    url: str = ""
    name: str = ""
    maxzoom: Optional[int] = None
    attribution: str = ""


@router.get("/api/mymaps")
def my_maps():
    from app import mymaps
    return {"maps": mymaps.listing()}


@router.post("/api/mymaps")
def add_my_map(req: MyMapBody):
    from app import mymaps
    try:
        return mymaps.add(req.kind, req.path, req.url, req.name, req.maxzoom, req.attribution)
    except ValueError as e:
        fail(400, str(e))


@router.delete("/api/mymaps/{mid}")
def remove_my_map(mid: str):
    from app import mymaps
    try:
        mymaps.remove(mid)
    except KeyError:
        fail(404, "This map is not in My maps any more.")
    return {"maps": mymaps.listing()}


# F5: THE HEIGHT PROFILE - an object's height and the ground under it along the distance (app/heightprofile.py)

class ProfileBody(BaseModel):
    lat: str
    lon: str
    alt: Optional[str] = None
    units: str = "deg"
    altRef: str = "msl"
    n: int = 800


@router.post("/api/profile")
async def height_profile(req: ProfileBody):
    from app.heightprofile import profile
    from app.store import store
    from svcore.analysis import align_to
    try:
        t, la = store.signal(req.lat)
        _, lo = store.signal(req.lon)
        alt = None
        if req.alt:
            ta, aa = store.signal(req.alt)
            alt = align_to(np.asarray(t, dtype=np.float64), np.asarray(ta, dtype=np.float64), aa, "linear")
    except KeyError as e:
        fail(404, f"Signal not found: {e.args[0] if e.args else ''} (its file was closed?)")
    try:
        return await asyncio.to_thread(profile, t, la, lo, alt, max(50, min(4000, req.n)), req.units == "rad", req.altRef)
    except ValueError as e:
        fail(400, str(e))


class VectorsBody(BaseModel):
    lat: str
    lon: str
    vn: str
    ve: str
    alt: Optional[str] = None
    units: str = "deg"
    altRef: str = "msl"
    n: int = 40


@router.post("/api/vectors")
async def vectors(req: VectorsBody):
    """F6: two signals (north, east) as arrows along an object's track, on the track's own times."""
    from app.heightprofile import vectors_along
    from app.store import store
    from svcore.analysis import align_to
    try:
        t, la = store.signal(req.lat)
        _, lo = store.signal(req.lon)
        t = np.asarray(t, dtype=np.float64)
        def on(sid: str) -> np.ndarray:
            ts, ys = store.signal(sid)
            return align_to(t, np.asarray(ts, dtype=np.float64), np.asarray(ys, dtype=np.float64), "linear")
        vn, ve = on(req.vn), on(req.ve)
        alt = on(req.alt) if req.alt else None
    except KeyError as e:
        fail(404, f"Signal not found: {e.args[0] if e.args else ''} (its file was closed?)")
    try:
        return await asyncio.to_thread(vectors_along, t, la, lo, vn, ve, alt, max(2, min(200, req.n)), req.units == "rad", req.altRef)
    except ValueError as e:
        fail(400, str(e))


# =============================================================================
# P7: PLACES - My places (~/.signalviewer/places.json, a file a colleague can be given), import / export,
# the coordinate parser, the ground under a point
# =============================================================================

class PlacesBody(BaseModel):
    places: List[dict] = []


class PlacesFile(BaseModel):
    path: str
    places: List[dict] = []
    title: str = ""


@router.get("/api/places")
def my_places():
    from app import prefs
    from svcore.places import clean_all
    doc = prefs._read("places.json", {})
    return {"places": clean_all(doc.get("places") or []), "path": prefs._path("places.json")}


@router.put("/api/places")
def put_my_places(req: PlacesBody):
    from app import prefs
    from svcore.places import clean_all
    out = clean_all(req.places)
    with prefs._lock:
        prefs._write("places.json", {"version": 1, "places": out})
    return {"places": out}


@router.post("/api/places/import")
async def import_places(req: PlacesFile):
    """Places from a .kml / .kmz / .geojson / .csv file (svcore/places.py)."""
    import os

    from svcore.places import read_places
    path = os.path.expanduser(req.path or "")
    if not os.path.isfile(path):
        fail(404, f"File not found: {req.path}")
    try:
        places, skipped = await asyncio.to_thread(read_places, path)
    except ValueError as e:
        fail(400, str(e))
    return {"places": places, "skipped": skipped}


@router.post("/api/places/export")
def export_places(req: PlacesFile):
    """Places as one .kml file (Google Earth opens it)."""
    import os

    from svcore.atomic import atomic_open
    from svcore.kml import write_kml
    from svcore.places import clean_all
    path = os.path.abspath(os.path.expanduser(req.path or ""))
    if not path.lower().endswith(".kml"):
        path += ".kml"
    if not os.path.isdir(os.path.dirname(path)):
        fail(400, f"Folder not found: {os.path.dirname(path)}")
    body = write_kml([], clean_all(req.places), title=req.title or "Places")
    with atomic_open(path, "w", "utf-8", "\n") as f:
        f.write(body)
    return {"path": path, "places": len(req.places)}


@router.get("/api/places/parse")
def parse_place(q: str = ""):
    """A typed position - decimal degrees or degrees-minutes-seconds - as {lat, lon}; ok false when not one."""
    from svcore.places import parse_coords
    p = parse_coords(q)
    return {"ok": True, "lat": p[0], "lon": p[1]} if p else {"ok": False}


@router.get("/api/ground")
def ground(lat: float, lon: float):
    """The ground height (m above sea level) at a point - a new place's height (null where none is known)."""
    import math

    import numpy as np

    from app import basemap
    g = float(basemap.ground_at(np.array([lat]), np.array([lon]), fetch=False)[0])
    return {"ground": round(g, 1) if math.isfinite(g) else None}
