"""Offline map: terrain heights, places and map tiles."""

import asyncio

from fastapi import APIRouter
from fastapi.responses import Response

from app.common import fail

router = APIRouter()




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
