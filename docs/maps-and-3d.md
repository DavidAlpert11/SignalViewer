# Offline map and 3D view

## Offline map data

`backend/app/basemap_data/` (17 MB) is built by `python tools/make_basemap.py --all` on a machine
with internet (needs `pyshp` and `osmium` besides the app's libraries) and ships with the app:
elevation grids (world ~11 km, Israel and surroundings ~500 m, Israel ~130 m) from the AWS
"Terrain Tiles" (Mapzen / Tilezen: SRTM, GMTED2010, ETOPO1), Natural Earth (public domain), and
OpenStreetMap from Geofabrik extracts (© OpenStreetMap contributors, ODbL). The app draws map tiles
from them (`backend/app/basemap.py`, cached in `~/.signalviewer/tiles`); the map shows the
attribution. To refresh the data, run the tool again.

**More detailed areas (packs).** Any area can get the same detail as Israel: elevation (~130 m),
OpenStreetMap roads down to regional ones, places down to villages, airports and runways:

    python tools/make_basemap.py --pack cyprus --bbox 34.5,32.2,35.75,34.65 --countries europe/cyprus

`--bbox` is south,west,north,east; `--countries` the Geofabrik extracts covering it (comma-separated);
`--zoom 9` or `8` for coarser (smaller) elevation. The pack is written to
`backend/app/basemap_data/packs/<name>/` (`pack.json`, `dem.npz`, `vectors.json.gz`; ~1.4 MB for
Cyprus) and the app uses every pack in that folder - copy a pack folder there on an offline machine.

## 3D view

CesiumJS (pinned, `frontend/package.json`) is loaded only when a plot is switched to 3D; its web
workers and data files are copied into the UI build under `/cesium/` (`frontend/vite.config.ts`),
nothing comes from the internet. Terrain heights come from `/api/terrain/{z}/{x}/{y}` (the same
bundled elevation grids as the offline map: sea at 0 m, the Jordan rift really below it). The
object models are built by `python tools/make_models.py` into `frontend/public/models/`.
Graphics: with a graphics card Cesium draws at the display's frame rate; drawn in software (virtual
machines, remote desktop) it is slow - the app then uses one sample per pixel and less terrain
detail (about 3x faster) and shows a note. Not in reports.
