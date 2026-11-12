"""Offline map: terrain heights, places and map tiles."""

import asyncio
from typing import List

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



@router.get("/api/tiles/{src}/{z}/{x}/{y}")
async def map_tile(src: str, z: int, x: int, y: int):
    """A map tile (cached on disk). 404 when offline and not cached: the map then shows its own
    country borders only."""
    from fastapi.responses import Response

    from app.tiles import tile
    r = await asyncio.to_thread(tile, src, z, x, y)
    if r is None:
        return Response(status_code=404)
    return Response(content=r[0], media_type=r[1], headers={"Cache-Control": "max-age=86400"})


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

    from app.atomic import atomic_open
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
