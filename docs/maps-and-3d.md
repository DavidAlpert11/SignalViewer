# Offline map and 3D view

## The network { #the-network }

The map's *Automatic* layer is the **offline map** the app draws from data it ships with: nothing is
sent. The layers under *Online – downloads map tiles* in the layer menu (streets: OpenStreetMap or
Esri; light / dark grey and satellite: Esri; topographic: OpenTopoMap) are used only when you choose
one; the app then requests the tiles of the area on screen from that provider - through its own
server, so the page itself never talks to the internet - and keeps them in `~/.signalviewer/tiles`.
Such a request carries the tile's coordinates (roughly where you are looking) and the app's name.
While online tiles are in use the plot shows an amber **Online map** sign.

**Never use the network** (*Settings*), or `SV_OFFLINE=1` in the environment (it locks the setting on,
for a whole installation): the online layers are off in the menu, a session that chose one shows the
offline map, and the server refuses every download (`app/tiles.py` checks it before any request) -
tiles already on the disk are still shown. Nothing else in the app uses the network: the 3D view's
terrain and imagery are the bundled ones (no Cesium ion), and there is no update check or telemetry.

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

**Country borders.** The offline map and the satellite photos get the borders and the country names
from the app itself (Natural Earth 1:50m, simplified to about 3 km - good for seeing which country,
not for a border's exact line): *Borders*, beside the map's layer. The street maps draw their own.

## 3D view

CesiumJS (pinned, `frontend/package.json`) is loaded only when a plot is switched to 3D; its web
workers and data files are copied into the UI build under `/cesium/` (`frontend/vite.config.ts`),
nothing comes from the internet. Terrain heights come from `/api/terrain/{z}/{x}/{y}` (the same
bundled elevation grids as the offline map: sea at 0 m, the Jordan rift really below it). The
object models are built by `python tools/make_models.py` into `frontend/public/models/`.
Graphics: with a graphics card Cesium draws at the display's frame rate; drawn in software (virtual
machines, remote desktop) it is slow - the app then uses one sample per pixel and less terrain
detail (about 3x faster) and shows a note.

**Outside the app** (1.26, `backend/app/scene3d.py`): the 3D view in reports, the replay page and its own
offline HTML file (its ⋯ menu; `signalviewer-cli map --3d`, `sv.scene_html` / `sv.scene_image`). CesiumJS
cannot go into one file, so the page draws the same data with three.js r159 (MIT, embedded): the offline map
draped on the bundled terrain (97 × 97 heights over the tracks' box and a margin), each track with a curtain
down to the ground and the flown part as a ribbon, the app's models with heading, pitch and roll, orbit /
zoom / follow, heights ×1 / ×2 / ×5. The objects are read as the Tacview export reads them. Where the browser
has no WebGL the page shows the scene's picture (matplotlib, the same picture as in PDF / Word / PNG). The
scene is local east / north / up metres around the tracks' middle (a flat earth: fine for tracks of
kilometres, not for hundreds of them).
