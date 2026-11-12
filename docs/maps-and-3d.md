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
draped on the bundled terrain (97 × 97 heights over the tracks' box and a margin), each track drawn as the app draws it (a fixed
width on screen; a navigation solution dashed, a receiver as points), the app's models with heading, pitch
and roll, heights ×1 / ×2 / ×5. The 2D map's page and the 3D page share one toolbar and one relation box
(`report_assets/relation.js`, `mappage.css`, the words in `mapimage.PAGE_STRINGS`): the camera *General · On the
object · Chase* on a chosen object (3D *Chase*: behind it, along its heading), + / −, *Fit*, *Trail* (whole / 60 s /
20 s), *Relation* (show / hide), light / dark; an attitude indicator in 3D; the address keeps the view
(`#t=…&cam=…&obj=…`); *Closest in* moves the time (inside a report: the report's time, `replay-seek`); the box is the app's (range, horizontal, Δalt, bearing, relative bearing, closure, closest-in,
heading Δ) with the pair's rings and a dashed line with the distance. The objects are read as the Tacview export reads them. Where the browser
has no WebGL the page shows the scene's picture (matplotlib, the same picture as in PDF / Word / PNG). The
scene is local east / north / up metres around the tracks' middle (a flat earth: fine for tracks of
kilometres, not for hundreds of them).

## What is a position (P2, 1.26)

One rule, in `track_of` (`backend/app/routes/analysis.py`, `no_position_as_gap`), used by every drawing and
export: a sample whose latitude **and** longitude are both exactly 0, or outside ±90 / ±180, or not finite,
is not a position - it is a gap. Receivers and autopilots write 0, 0 for "no fix" (ArduPilot's EAHR without
an external AHRS: 0, 0 for the whole flight; a GPS before its first fix). Detection still goes by names;
*Add all* and the found list then ask `/api/object_positions` and leave out an object with no position
(the message names it), and note one with under 2 % positions. An object already in a saved session that
turns out empty is drawn as nothing, left out of *Fit* and of every export, and its chip says *no position*.
A latitude of 0 alone (a place on the equator) is a position.

## The ground's heights (P5, 1.26)

`basemap.ground_at` and `terrain_tile` take the finest of: a bundled fine grid (the packs: Israel at 139 m)
→ the user's elevation files (SRTM `.hgt`, 1201² = 3" or 3601² = 1", in `~/.signalviewer/terrain/` or the
folder chosen in Settings; read with numpy) → terrarium tiles (Mapzen / AWS open data: SRTM, GMTED2010,
ETOPO1; level 12, ~30 m), fetched **only** when the network is allowed (not *Never use the network*, no
`SV_OFFLINE`) and kept in the tile cache with the same rules as online map tiles → the bundled world grid
(11 km). A fetch runs in the background: the answer comes from what is there, and `/api/terrain/version`
changes when finer heights arrived (the app's 3D view then asks its terrain again; the tile URLs carry the
version so the browser's cache does not keep the coarse one). `basemap.step_at(lat, lon)` is the step of
the best source at a point, never fetching.

The offline 3D page says what its ground is: the footer always ("terrain: 139 m grid"), and a line over the
scene when the step at its centre is over 1 km. Its ground reaches the horizon: the near mesh (the tracks'
box, 129 × 129) over a far one (8 × its side, 40 to 200 km, 129 × 129, 2 m lower and not drawn inside the
near box), fog from 0.6 × to 1.4 × the far side, a sky gradient, the sun 35° high from the north-west.
Heights ×1 by default (honest), ×2 / ×5 / ×10; "flat here" beside the choice when the relief is under 4 %
of the near side. The PDF / Word / PNG picture draws the far ground as far as twice the near box. The page is
a flat local frame: Earth's curvature is not drawn (at 100 km it would drop the horizon by ~800 m).

## Hiding an object (P6, 1.26)

One rule: a hidden object (`MapObject.hidden`) is not drawn, not part of *Fit*, and keeps its place in the
list (greyed, struck through). `shownObjects(plot)` (`mapObjects.ts`) is what the drawing loops of
`Globe3D.tsx` and `GeoChart.tsx` iterate (their track fetch, models, markers, labels, tracks, Fit); lookups
of another object (a borrowed attitude, the pair) use the whole list. A hidden one of the pair shows
"— hidden —" in the relation box; a camera on it goes to General. Pictures skip it; the offline pages start
with it hidden and their legend rows are buttons (`svLegend` in `report_assets/relation.js`; click, Alt+click
= only this one). Exports (Tacview, CSV, KML) keep every object.

## The Map is 3D (P4, 1.26)

One Map, and it is the 3D view; "2D" is its camera *From above*. Saved values do not change: `mode: "geo"`
**with objects** is drawn by the 3D view (`isMapPlot`, `mapObjects.ts`) with the camera From above
(`Plot.camera` absent on such a plot = `"top"`; `mapCamera`); `mode: "3d"` as before (absent = General, or
On the object with a followed object); new maps are `"3d"`. General writes `camera: "free"`. A 1.25 build
opening a session from this one draws its maps as before. `mode: "geo"` without objects - a lon / lat X-Y on
a map - is unchanged (GeoChart).

**When 3D cannot draw** (`hasWebGL()` false - `webgl.ts`, no CesiumJS loaded for the check - or the context
lost) the Map is drawn by `GeoChart` with "Shown flat – this computer cannot draw 3D" and the same bar.
`Globe3DFallback.tsx` (tracks on bare axes) is gone. `ui.mapFlat` forces the flat drawing (P8's *Map drawing:
Always flat*; the flat-map e2e tests use it implicitly - their browser has no WebGL).

**Reports and pages:** a Map goes out as the 3D view on its camera (`plotSpec` → `mode: "3d"`,
`scene.camera`); From above → the flat map picture (`report._map_picture` → `mapimage.render`), any other
camera → `scene3d.render`; the live page opens on that camera (`D.camera`). The flat page (`map.html`) inside
the 3D page's frame for a browser without WebGL is **not done** (the page shows its picture there, as before).

| 2D feature | where it was (GeoChart.tsx) | where it is now |
|---|---|---|
| the mouse's position | `.geo-readout` (lat / lon) | `Globe3D.tsx` `.g3-readout`: lat / lon (decimals by the camera's height), ground height, distance / bearing from the reference (`scene.globe.pick`, one update a frame) - e2e `test_the_map_from_above_and_the_mouse_readout` |
| north up / track up | `mapUp` | From above: north up; *Track up* beside it (`MapBar`) - heading of the chosen object up |
| ring tooltips | `ringTip` | the 3D rings and their hover (1.26, existing) |
| relation lines and distance | relation layer | existing in 3D (`relLines`) - `test_globe3d` related-objects test |
| track colouring by a value | `trackColors` | existing in 3D (`objColors`) |
| object dialog from a click | marker click | existing in 3D (a click on a model) |
| back to the object after a drag | `followOff` | 3D: drag while following orbits around it (no button needed) - note: not identical |
| keyboard `+ − 0`, arrows | key handler | `+ − 0` in the bar; arrows: not in 3D yet (note) |
| offline basemap / online imagery | `geoBase` | existing in 3D (the same layer choice) |
| hover on a track point | track hover | existing in 3D (`Readout` box) |
| the mouse's position in the offline 3D page | - | not done (the page's hover shows track points; the ground raycast is left) |


## Places (P7, 1.26)

Named points, lines and areas on every Map, and saved camera views. Two lists: **Places of this session**
(`Workspace.places`, saved with the session and with a template made from it) and **My places** (the user's
own, in every session - the app keeps them in `~/.signalviewer/places.json`, a file that can be given to a
colleague). One panel holds them (the Map's ⋯ → *Places…*); the command palette has *Go to a place…* and
*Add a place…*.

- **Positions** are read by one parser (`svcore/places.py` `parse_coords`): decimal degrees ("32.687, 35.39")
  or degrees-minutes-seconds (`32°41'13"N 35°23'24"E`, `N32 41 13 E35 23 24`); without hemisphere letters
  the order is latitude, longitude. A new point's height is the ground there (`/api/ground`).
- **Import**: `.kml` (points, lines, polygons - their outer ring), `.kmz` (the zip's KML), `.geojson`
  (Point / LineString / Polygon and their Multi- forms), `.csv` (`name, lat, lon[, alt]`, a header optional;
  degrees-minutes-seconds in the cells work). A shape with no valid position is left out and counted.
- **Drawing**: in 3D a point is its icon on a thin 30 m pole with its name; lines and areas are draped on the
  ground (Cesium ground primitives) - in the software-WebGL light mode, for the frame rate, plain lines 2 m
  over the ground under each vertex. The flat drawing, both offline pages and the pictures draw the same
  shapes. Places take part in *Fit* only when the Map has no objects.
- **Readout and relation**: the mouse readout adds the nearest shown place within 50 km; the relation box's
  *Compared with* list ends with the places (`Plot.relPlace`; a place is a fixed point).
- **Exports**: the KML file holds every shown place (a saved view as a `LookAt`); the ACMI file holds the
  points as stationary objects - `Type=Navaid+Static+Waypoint`, an airfield `Ground+Static+Aerodrome` (both
  from the ACMI 2.2 type list).

## Settings > Map and objects (P8, 1.26)

One module reads and writes these settings (`frontend/src/mapDefaults.ts`, keys `sv3.map.*`). They apply to
**new things only** - a new object, a new Map, the next export; an open session, a template or an object
already made is never changed by them. Drawn things (names, the track's width, units, coordinates) follow
the setting at once, in the app and in the pages and pictures made after.

| Setting | Choices (default first) |
|---|---|
| Icon of a new object, per class (truth / navigation / receiver / other) | aircraft · uav · drone · missile · ship · vehicle |
| Camera of a new Map | General · From above · On the object · Chase |
| Map drawing | Automatic · Always flat (light) |
| Relation box on a new Map / Names on the Map | shown · hidden |
| Track width | 2.5 px · 1.5 · 4 |
| Model size of a new object | medium (26) · small (18) · large (36) |
| Distances and heights | m / km · ft / NM (below 1 NM in feet) |
| Coordinates | decimal degrees · degrees-minutes-seconds · MGRS (80° S to 84° N; the polar grid is not done) |
| Elevation files | a folder of SRTM `.hgt` files (empty: `~/.signalviewer/terrain`) |
| Export rate for Tacview / KML | 10 · 5 · 2 · 1 samples a second |
| Story | on · off; about 90 s · 45 s · 3 min |

## The wow (P9, 1.26)

- **Light**: the sun where it was - the recording's own time when its times are Unix dates, else 10:00 local
  solar time at an equinox (`scene3d.sun_position`, NOAA's low-precision formulas, ~0.5°). The app: sky
  atmosphere, lighting, fog; soft model shadows only while the camera is on an object.
- **In space**: a drop line and a dark disc under each object; its last 10 s brighter over the whole track.
- **Flights**: every camera change eases there over ~1.2 s (none with the system's *reduce motion*).
- **Cockpit**: a fifth camera at the object, along its heading and pitch, rolling with it, 70°; its own model
  (and any within 20 m) hidden. The flat drawing treats it as Chase.
- **Flight display** (*Display* in the bar; on by default in Chase and Cockpit) and a **mini-map** while the
  camera is near an object (a click flies there).
- **The error, drawn**: when the relation box's pair is one vehicle (median distance under 20 m) a
  see-through surface between the tracks, green → amber → red at the distance's 95th percentile, with its
  scale and a toggle in the relation box. The app draws it while the camera is within 3 km (from further it
  is under a pixel); the flat drawing colours the compared track instead.
- **Light mode** (software WebGL): sky, shadows, drop lines, the 10 s trail and the error surface are off;
  the display, mini-map, cockpit and flights stay (no GPU cost).

## Story mode (P10, 1.26)

`svcore/story.py` picks the moments: the page's marks (the log's errors and warnings, health findings, the
user's notes) and, from the reference object of the tab's first Map, takeoff / landing (the height above the
ground crossing 5 m for 3 s), the highest and fastest points, the steepest bank (over 30°), passing within
200 m of a place, and for the pair the largest error (one vehicle) or the closest and farthest moments. A
moment within 3 s of a stronger one is dropped; at most 12. The live page's player runs the time so the
recording takes about the Settings' length (×1 to ×60), at ×1 from 3 s before a moment to 2 s after, and
stops 4 s on it; the map frames fly to its object (On the object ~400 m; Chase for a bank, an error, a
takeoff or a landing) and give the reader's camera back at the end.
