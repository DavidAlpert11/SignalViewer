# Agent prompt – Signal Viewer, owner's round of 2026-11-12: the Map becomes one 3D view worth a "wow", Tacview that opens, damaged logs that still load

> **This prompt is self-contained.** You (Claude Opus 5.5) have not seen the earlier conversations. Everything
> you need to start is here and in the repository's own files named below. It replaces any earlier prompt of
> this date.

> ## Status – read this first (update at the end of every session)
>
> **Stage reached: the whole round done (P0–P11)** - one patch on `5e2e8ff`, ready for the 1.26.0 release.
> Code maps of P7–P10: TASKS.md ("P7 done" … "P11 done"). Left for the owner: ROADMAP Milestone 30's last line.
> Code map of P9: see TASKS.md "P9 done" (Globe3D sky / `sunMs` / drops / `recent` / cockpit / `errPrim`,
> `FlightDisplay.tsx`, `MiniMap.tsx`, `relation.errorAlong`, `scene3d.sun_position|scene_sun`, scene3d.html
> `glideTo`, `buildErr`, `tape`, `mini`).
> Code map of P8: `mapDefaults.ts` (one reader of `sv3.map.*`; `fmtDistance`, `fmtCoord`, `mgrs`, `newObjectLook`,
> `newMapFields`), `SettingsDialog.tsx` `MapSection`, `ui.mapPrefs`, `objectAdd.candidateObject` / `ObjectDialog` /
> `actions.addObjectsToNewPlot|addObjectsToMaps` use it; `plotSpec` geo `names|trackWidth|units` ->
> `mapimage.page_look` -> both pages (`svDist` in relation.js) and both pictures.
> Code map of P7: `svcore/places.py` (`parse_coords`, `read_places`, `clean`), `routes/maps.py` (`/api/places`,
> `/import`, `/export`, `/parse`, `/api/ground`), `svcore/kml.py` `place_kml`, `svcore/acmi.py` `_place_lines`;
> `store/model.ts` (`Place`, `Workspace.places`, `Plot.relPlace`), `places.ts` (lists, `nearestPlace`, icons,
> My places load / save), `store/actions/places.ts`, `globeBridge.ts` (`mapFly`, `mapCameraNow`, `mapObjectAt`),
> `PlacesPanel.tsx`, `PlaceDialog.tsx`, Globe3D (`placeGfx`, `flyTo` - P9.3 extends it to every camera change),
> GeoChart (places, `svGeo` on the right-click), `RelationPanel.tsx` (places in *Compared with*),
> `plotSpec.placesSpec`, `mapimage.page_places` / `_draw_places`, `scene3d` places, `relation.js` `svPlaceTag`.
> Left in B (notes in `docs/maps-and-3d.md`): the app's *Heights* in MapBar; arrows in 3D; the mouse readout in
> the offline 3D page; the flat page inside the 3D page's frame without WebGL; the Flight tab template still
> holds a map and a 3D view (both are now the 3D Map - one could go).
> Code map of P4: `mapObjects.ts` `isMapPlot`, `mapCamera`; `webgl.ts` `hasWebGL`; `PlotView.tsx` (no switch;
> `isMap`, `flatWhy`, `ui.mapFlat`, `.map-flat-note`); `MapBar.tsx` (four cameras, Track up); `Globe3D.tsx`
> (From above: fit straight down, follow, track up, tilt -> General; `.g3-readout` + `__svReadout`; `onFlat`);
> `Globe3DFallback.tsx` deleted; `plotSpec.ts` (`scene.camera`); `report._map_picture` / `_top`; `scene3d`
> `camera` -> the page opens From above. Owner (2026-11-12): keep the 2D engine as the fallback.
> Code map of P5 / P6:
> - P5 `app/basemap.py` (`ground_at(step_m, fetch)`, `_extra_heights`, `_hgt*`, `_terrarium*`, `_tr_fetch_later`,
>   `wait_terrain`, `terrain_version`, `step_at`, `elevation_folder`, `elevation_files`); `tiles.SOURCES["terrarium"]`;
>   `/api/terrain/version` (`routes/maps.py`); `Globe3D.tsx` remakes its terrain provider when it changes;
>   `scene3d.py` (`GRID` 129, `far` ground, `step`, the picture's far ground), `report_assets/scene3d.html`
>   (far mesh with a discard inside the near box, fog, sky, low sun, ×10, flat hint, coarse note, footer grid);
>   `tests/conftest.py` sets `SV_OFFLINE=1` for every test (no test touches the network).
> - P6 `MapObject.hidden`, `actions.toggleObjectHidden`, `shownObjects` (`mapObjects.ts`), loops in `Globe3D.tsx`
>   / `GeoChart.tsx` (`objects` = shown, `allObjs` for lookups; `__svMapDrawn` for tests), chips' `.obj-eye`
>   (`PlotView.tsx`), `RelationPanel.tsx` ("— hidden —"), `plotSpec.ts` carries `hidden`, `mapimage` / `scene3d`
>   skip it in pictures and Fit, `svLegend` (`report_assets/relation.js`) in both pages, `__page.hidden()`.
> Code map of group A:
> - P1 `backend/svcore/acmi.py` (`sample` - the one time grid every export uses; `write_acmi`; `fit_rate`;
>   `MODELS` - a model per kind that Tacview's database has a 3D shape for: an unknown `Name` is drawn as
>   Tacview's generic triangle, which the owner saw), `svcore/acmi_check.py` (`check`), `svcore/tacview_csv.py`
>   (`write_csvs`), `svcore/kml.py` (`write_kml`); routes `/api/export/acmi|tacview_csv|kml` in
>   `app/routes/export.py`; `sv.tacview_csv`, `sv.kml`; the menu `exportFlight` in `PlotView.tsx`.
> - P2 `app/routes/analysis.py` (`no_position_as_gap`, `track_of` -> `valid`, `/api/object_positions`);
>   `frontend/src/objectAdd.ts` (`positionCounts`, `byPosition`, `positionNote`), `ObjectSuggestBar.tsx`,
>   `ObjectDialog.tsx`, `noPosition.ts` (`markNoPosition`; `ui.objNoPosition`), GeoChart / Globe3D skip empty tracks.
> - P3 `svcore/bin_loader.py` (`DataFlash._repair`, `_to_next_healthy`, `faulty_report`; the 20 % rule;
>   follow-up: an FMT whose column names do not match its fields is kept for its length and left out -
>   `MsgFormat.names_off` - and a type with no FMT is learned - `_learn_nameless`, `nameless`),
>   `tools/make_bad_bin_fixture.py`, `tests/data/bad_len_*.bin`, `faultyNotes` in `files.ts`.
> Tests: `backend/tests/test_tacview_exports.py`, `test_bad_length_bin.py`, `frontend/src/objectPosition.test.ts`,
> `files.test.ts`; e2e `tests/e2e/test_round_1112.py` (+ `test_map_objects.py` updated; `save_as` waits for
> the picker's folder - a flake that existed on the base too).
>
> Work order: **P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9 → P10 → P11**.
> Groups – finish a group and stop cleanly rather than start the next one:
> **A – things that are broken** = P0–P3 (Tacview, objects with no real position, damaged logs);
> **B – one Map, in 3D** = P4–P6 (3D is the Map, a ground with relief, objects shown / hidden);
> **C – places and settings** = P7–P8; **D – the wow** = P9–P10; **E** = P11 (docs, patch).
>
> **Version: still 1.26.0.** Neither 1.25 nor 1.26 has been released. Do **not** bump the version; add to the
> existing `## 1.26.0` section of `CHANGELOG.md`.

---

## A. Who the owner is and how he wants the work done

- **The product.** Signal Viewer (`github.com/DavidAlpert11/SignalViewer`): a desktop app (local FastAPI
  backend in `backend/`, React + TypeScript UI in `frontend/`) for flight-test and simulation engineers:
  open a flight log or a test run, see what went wrong, judge it against a golden run, send the answer as
  one live HTML page. Fully offline. English and Hebrew.
- **The owner** applies each patch himself and pushes it to `main`. He reads Hebrew; write your reports to
  him in Hebrew, plainly, the outcome first. Code, comments, docs and commit messages stay in English.
- **His rules for a round (2026-11-11):** plan everything first; then write all the code; run the tests at
  the end and fix. Run **only the e2e files a change touches** – the whole e2e suite (~9 min) is his to run.
  Do not rewrite the README (P11 adds two pictures and a few lines).
- **Base and patch.**
  ```
  git clone https://github.com/DavidAlpert11/SignalViewer.git && cd SignalViewer
  git log --oneline -3     # the base. It must contain "1.26: one map bar in 2D and 3D…"; if it does not, stop and tell the owner
  pip install -r requirements.txt -r requirements-dev.txt && python -m playwright install chromium
  cd frontend && npm ci && npx tsc -b && npm test && cd ..
  ```
  At the end: **one commit**, then
  `git format-patch --binary <base>..HEAD --stdout > signalviewer-1.26-<date>.patch`
  (`--binary`: the patch holds pictures and the built `frontend/dist`), check it with `git am` on a fresh
  clone, update this Status box and `docs/dev/TASKS.md`, and hand the patch to the owner. Keep a copy of
  this prompt in the repo as `docs/dev/AGENT_PROMPT_2026-11-12.md`.
- **Read first:** `/CLAUDE.md` (the project's rules – they bind you: one way to do a thing, one place per
  control, en + he for every string, CSS variables only, sessions backward compatible, heavy work in the
  backend, always offline-capable, every workspace change through `commit` with Undo), `docs/dev/TASKS.md`
  ("Current state" and the Log), `docs/maps-and-3d.md`.

---

## B. The owner's words (2026-11-12) and what each becomes

| He said | Task |
|---|---|
| "Here is the file. It crashed Tacview." (`Plot_1.acmi`) – "maybe several CSV files instead? Or fix the ACMI." | P1 |
| (seen in his file) an object `EAHR` sitting at latitude 0, longitude 0 | P2 |
| "I loaded another ArduPilot .bin where one recorded message had a bug in the firmware code. Much of the file came out damaged and the app said too much of the file is damaged and did not show it. Maybe detect that the fault is in one message and drop just that." | P3 |
| "In the 2D map I see the latitude / longitude under the moving mouse – a great feature, also for the 3D map." | P4 |
| "Maybe give up 2D altogether. We have 3D and can always look from above. It simplifies things – we support only 3D." | P4 (with one reservation – read P4) |
| "The 3D map exported to HTML is a 3D track but the earth is a flat map – fix." | P5 |
| "There is a legend at the side of the map – click an object to hide or keep it." | P6 |
| "Maybe add places, as one can in Google Earth." | P7 |
| "In settings, let the default not be an aircraft icon… and maybe more belongs in general settings." | P8 |
| "Turn the map view into a wow view." / "Surprise me with an amazing idea." | P9, P10 (Story mode) |

---

## C. Findings (read in the code on the base, and in the owner's file; nothing here was run in Tacview)

### C1. The file that crashed Tacview (`Plot_1.acmi`, 150 KB, 556 frames, 55 s, 6 objects)

The file is **valid ACMI 2.2 text** by every rule of the published spec that was checked: the two header
lines, `ReferenceTime`, increasing frames, hexadecimal ids, a constant 6-field
`T=Lon|Lat|Alt|Roll|Pitch|Yaw` per object, plain decimal numbers, allowed colours, no id used again after
`-id`. So the crash is caused by **content**, not syntax. What stands out:

| # | In the file | Why it is a suspect | Where it comes from |
|---|---|---|---|
| T1 | Object `106`, `Name=EAHR`: `T=-124|-45|0|0|0|0` on every frame = latitude 0°, longitude 0°, altitude 0 – **13,000 km** from the other five objects (which are near 45.52° N, 124.29° E) | One scene spanning a third of the planet; the most likely trigger | ArduPilot logs `EAHR` (external AHRS) with zeros when none is fitted; the app found it as an object by its field names and exported it |
| T2 | `Name=XKF1[0]`, `Name=POS`, `Name=GPS[0]`… | The spec: `Name` is the **aircraft model** Tacview looks up in its database (`C172`…); the label belongs in `CallSign` ("displayed in priority over the object name"). Brackets in a model name are untested ground | `svcore/acmi.py` `write_acmi`, the first line of each object |
| T3 | `GPS[0]` (no attitude of its own) written with `0|0|0` angles for the whole flight | An aircraft flying sideways with a frozen nose; not a crash, but wrong – a 3-field `T=` is the honest form | the `att` handling in `write_acmi` |
| T4 | Position steps of ~170 m between two frames 0.1 s apart (objects 101–104 around t = 37–45 s) | Real data (EKF / AHRS resets), kept as is – but worth a note in the checker's report | the log itself |

**Probe files already made for the owner** (he will report which is the first that opens):
`1_without_EAHR`, `2_callsign` (Name → model, name → CallSign), `3_without_EAHR_and_callsign`, `4_minimal`
(position only), `5_only_POS`. Ask him for the answer in your first report; do P1 for **all** suspects
without waiting – each fix is right on its own.

**Tacview's CSV import** (their page "Real-life CSV data"): one file per object; the **file name** is
`Model name (Pilot name) [Color].csv` (e.g. `F-14A (Maverick & Goose) [Blue].csv`); columns by header, any
order: `Time` (seconds from the start, or ISO UTC) or `Timestamp` (Unix seconds), `Longitude`, `Latitude`
(degrees), `Altitude` (metres MSL), `Roll`, `Pitch`, `Yaw` (degrees); comma separated, point as decimal mark;
a blank cell = unchanged. Documented loading: *File → Open* the first, *File → Merge* the others (the owner
says dragging several in together also works). The page calls CSV a feature of **Tacview Standard**.

### C2. The ground is flat – and not only in the HTML page

- All elevation comes from `backend/app/basemap.py` (`ground_at`, `terrain_tile`, `_grids`): a **139 m** grid
  for 29.3–33.5° N, 34.1–36.0° E (Israel), **555 m** for 27.5–35.5° N, 31.5–39.0° E, and **11 km for the rest
  of the world**. The owner's log is at 45.5° N, 124.3° E: his ground **is** an 11 km grid – flat – in the
  page *and* in the app's 3D view (`Globe3D.tsx` feeds CesiumJS from `/api/terrain/{z}/{x}/{y}`, the same
  grids).
- The HTML page (`backend/app/scene3d.py` `scene_data`) also shows only the tracks' box plus a margin (≥ 3 km),
  one mesh of 97 × 97 heights, lit evenly, heights ×1: even in Israel a flight over the lake (every file in
  `examples/` flies over the Sea of Galilee) gets a flat blue tile that ends in a cliff.
- The map pictures already handle "online when allowed, cached, attribution written" for imagery
  (`mapimage.tile_bytes`, `ATTRIB`, the tile cache; the user's *Never use the network* setting and
  `SV_OFFLINE=1`). The bundled attribution already names **AWS Terrain Tiles** (Mapzen "terrarium" PNG:
  `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`, height = R·256 + G + B/256 − 32768,
  free, no key) – the same public source can fill the world at ~30 m when the network is allowed.

### C3. The damaged .bin

`backend/svcore/bin_loader.py`: messages are found by their 3-byte header and must form a chain (each starts
where the previous one ends, by the length its `FMT` declares). A break resynchronises at the next header.
The loader gives up with `BinFormatError("The log is too damaged to read.")` in two places: more than
1,000,000 chain runs, or more than 10,000 gaps that together skip over half the file. **A firmware that
writes one message type with a length different from its `FMT`** breaks the chain at *every* such message –
exactly the owner's case – and trips those limits although every other message is intact.

### C4. 2D and 3D today

- One *Map* plot type with a **2D | 3D** switch (`PlotView.tsx` `.map-view`); the saved `mode` is `"geo"`
  (2D canvas map, `GeoChart.tsx`, ~970 lines) or `"3d"` (CesiumJS, `Globe3D.tsx`, ~870 lines, lazy chunk
  4.7 MB + 2.7 MB of assets). Both share `MapBar.tsx` (camera General / On the object / Chase, the object,
  + − fit, *Relation*), `RelationPanel.tsx`, the object chips.
- Only 2D has: the mouse's latitude / longitude (`.geo-readout`), north-up / track-up, a plain longitude /
  latitude plot of two signals **without objects**, and it draws on any machine.
- 3D needs WebGL. Without it (remote desktop, virtual machines, blocked drivers – and Chrome / Edge 139+ have
  no software fallback) `Globe3D.tsx` shows `Globe3DFallback.tsx`: tracks on plain XYZ axes, no map. Flight-test
  labs use remote desktops a lot.
- Offline pages: `report_assets/map.html` (2D) and `scene3d.html` (3D, three.js r159 embedded) share
  `relation.js` + `mappage.css`. Static pictures: `mapimage.render` (2D, matplotlib) and `scene3d.render`.

### C5. Smaller facts the tasks rely on

- `frontend/src/objectAdd.ts` `candidateObject` writes `kind: "aircraft"` for every found object.
- Settings: `components/SettingsDialog.tsx`; values through `frontend/src/prefs.ts` (`getPref` / `setPref`,
  kept by the app in `~/.signalviewer/ui_settings.json`). Nothing about the map is there.
- The object chips (`PlotView.tsx` `.obj-chips`) open the object's dialog on click; `MapObject`
  (`store/model.ts`) has no "hidden" field. The pages' legend (`#legend`) has no action.
- The live report's one time bar is the `RP` block of `report_assets/viewer.js` (`setTime`, `RP.events`, the
  messages `{sv: "replay", t}` to map frames and `replay-seek` back).

---

## D. Testing policy

- pytest for every backend change; Vitest for every new pure frontend function; e2e only for new UI flows,
  in **one** new file `tests/e2e/test_round_1112.py`, plus the existing files a change touches (most likely
  `test_live_report.py`, `test_globe3d.py`, `test_map_objects.py`, `test_map_smooth.py`,
  `test_object_relations.py`, `test_map_export.py`, `test_replay.py`, `test_less_clutter.py`).
- The app's e2e browser has no WebGL by default; the existing 3D tests show how they cope – follow them. The
  offline pages are tested from a file in Chromium **with** software WebGL:
  `args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]` (see
  `tools/make_live_report_media.py`). Pages expose state for tests (`window.__scene.state`, `window.__page`,
  `window.__replay`): add fields there instead of reading pixels.
- After a frontend change: `cd frontend && npx tsc -b && npm run build` **before** any e2e (it runs
  `frontend/dist`). After touching the version or `docs/validation.md`'s numbers:
  `python tools/make_validation_doc.py`. Backend: `cd backend && python -m pytest -q -p no:cacheprovider` and
  `mypy --config-file ../pyproject.toml app svcore signalviewer`.

---

## E. The tasks, in order

### P0 – Baseline and the two requests — S

- Baseline numbers into the Log of `TASKS.md` (expect: backend 1135 passed / 14 skipped, mypy clean, 132
  Vitest tests). Note any failure that exists before you start.
- Your first report to the owner asks for: (1) which probe file was the first to open in Tacview, and his
  Tacview version; (2) the damaged `.bin` (or its first 20 MB) and the name of the message whose firmware
  code was wrong. Work on with the defaults below – do not wait.

### P1 – Tacview: a file it opens, and two more ways out — M

1. **A checker** `backend/svcore/acmi_check.py`: `check(text) -> list[str]` (empty = fine), one rule per
   test: the two header lines (a BOM allowed); object `0` lines before the first frame with an ISO
   `ReferenceTime`; frame times finite, ≥ 0, strictly increasing; object lines `<hex id>,<Prop>=<value>…`,
   id not `0`; `T=` with 3, 5, 6 or 9 fields and **the same count for an id for its whole life**; every
   non-empty field a plain decimal (no `nan`, `inf`, exponent); absolute longitude within ±180, latitude
   within ±90, altitude within −500…100,000 m; the first line of an id has every `T=` field, `Type` and
   `Name`; `Color` from the spec's seven; an id never used again after `-id`; **all objects within 2,000 km
   of the first one** (a warning, not an error: "EAHR is 13,000 km from POS"); a step of more than 1 km
   between two frames of one object is a warning. `write_acmi`'s tests run it on every fixture.
2. **The writer** (`svcore/acmi.py` `write_acmi`):
   - **T2:** first line of an object: `Name=<model>,CallSign=<the object's name>`. Models by the app's kind,
     in one table beside `TYPES`: aircraft `C172`, uav `MQ-9`, drone `Bell 206`, missile `AIM-9M`; ship and
     vehicle: no `Name` (the `Type` tag is enough).
   - **T3:** an object with no attitude of its own is written with the 3-field `T=`; never invented zeros.
     (Check what `routes/export.py` `acmi_objects` returns for an object whose angles are borrowed or
     derived from motion, and keep those – they are real.)
   - an altitude missing at a sample keeps the previous altitude (0 only if there never was one); an angle
     missing after the first line carries the previous value (no empty fields); a gap shorter than 2 s holds
     the last position instead of `-id`; an object that truly returns later gets a **new id**; a track with
     one sample is skipped.
   - the rate: 10 Hz by default (P8's setting); when frames × objects > 1,500,000, lower it to fit (≥ 1 Hz)
     and say so in the toast.
3. **CSV files, the second way** – `backend/svcore/tacview_csv.py` `write_csvs(objects, folder, rate)`: one
   file per object from the **same** `acmi_objects` output and time grid (import, do not copy):
   `Time,Longitude,Latitude,Altitude[,Roll,Pitch,Yaw]`, `Time` in seconds from the first sample of all
   objects; file name `<Model> (<object name>) [<Color>].csv` (model `C172` when the kind has none; colour
   from `acmi_color`; the name made file-safe; duplicates get ` 2`, ` 3`). Route
   `POST /api/export/tacview_csv`.
4. **KML, the third way – "Open in Google Earth"** – `backend/svcore/kml.py` `write_kml(objects, places)`:
   each object a `<Placemark>` with a `<gx:Track>` (`<when>` per sample when the recording has real dates,
   else a plain `<LineString>`; `altitudeMode` absolute), its colour, its name; P7's places as point
   placemarks. One `.kml` file (plain XML, no zip). This gives the owner a viewer that does not crash while
   Tacview is being sorted out, and his customers have it installed.
5. **UI:** the map's ⋯ entry *Export for Tacview (.acmi)* becomes a submenu **Export the flight →
   Tacview (.acmi) · Tacview CSV files (a folder)… · Google Earth (.kml)** – the same one place. Toasts say
   where the files are; the CSV toast adds: "In Tacview: File → Open the first, File → Merge the others (or
   drag them in together). CSV needs Tacview Standard." en + he.
6. Python: `sv.tacview_csv(rec, objects, folder)`, `sv.kml(rec, objects, path)` beside the existing map
   functions in `backend/signalviewer/__init__.py`, with one line each in `docs/api.md`.

**Done when:** the checker passes on every fixture and names the fault in eight hand-made bad files; a
re-export of a fixture shaped like the owner's file (five objects together, one at 0, 0 – see P2) has no
object at 0, 0, `CallSign`s, and a 3-field GPS; CSV: three files with the expected names and first rows;
KML parses as XML and holds every object; e2e: the submenu writes each of the three.

### P2 – An object that has no real position is not an object — S

`EAHR` with latitude 0 / longitude 0 was offered, added, drawn (at "null island") and exported.
- **One rule, in the backend**, where a track is made (`routes/analysis.py` `track_of`): a sample whose
  latitude **and** longitude are both exactly 0 (or outside ±90 / ±180, or not finite) is **not a position**
  – it becomes a gap (NaN). Receivers and autopilots write 0, 0 for "no fix". State the rule in the
  function's docstring and in `docs/maps-and-3d.md`.
- **At add time:** the found-objects list (`ObjectSuggestBar.tsx`, `ObjectDialog.tsx`) must not add an
  object with no valid sample. Detection works from names only (keep it so – `objectDetect.ts` never reads
  data); so when *Add all* / *Add* runs, ask the backend once for each candidate's valid-sample count (a
  small endpoint or an existing statistics call – look before adding one) and: none → not added, the row
  says "no position in this file (always 0, 0)" with the reason in *Why?*; fewer than 2 % valid → added,
  with a note. One toast: "5 objects added; EAHR left out – it has no position in this file".
- Objects already in a saved session that turn out empty: drawn as nothing, their chip marked "no position"
  – never a marker at 0, 0; *Fit* ignores them.
- Exports (ACMI / CSV / KML, pages, pictures) skip an object with no valid sample and say so.

**Done when:** pytest: a track with zeros is all gaps, a track with zeros only at its start begins at the
first fix; Vitest / e2e: a fixture with an `EAHR`-like group of zeros – *Add all* leaves it out with the
message; ArduPilot detection tests still pass.

### P3 – A .bin with one faulty message still loads — M

Goal: **never refuse a log because one message type is wrong; drop that type, say so, show the rest.**
In `backend/svcore/bin_loader.py`, in the block that builds the chain (`cand`, `ln`, `ends`, `brk`):
1. **Find the types that break the chain.** For each message type, count its candidates and how many of
   them are followed exactly by another candidate (`ends[k] == cand[k + 1]`). A healthy type is ≥ 99 %
   chained; a type whose written length differs from its `FMT` is near 0 %.
2. **Learn the real length.** For a type with ≥ 50 candidates and < 50 % chained: take the distances from
   each of its candidates to the **next candidate of any healthy type** at or after it; if one distance `L'`
   covers ≥ 90 % of them and `L' ≠` the declared length, the type is **mis-declared**: its messages are `L'`
   bytes long. (A header-looking byte pair inside its payload can sit before the true next header; that is
   why you look at healthy types and take the dominant distance. Document the choice.)
3. **Repair and re-chain.** Use `L'` as that type's length for the chain only; **do not decode its fields**
   (its layout is unknown) – its signals are left out. Re-run the chain. Report in the load report (the
   place `corruptBytes` is reported, near the end of the loader) a new entry, shown to the user by the
   existing damaged-file notice: "Message `XYZ` is written with a different length (47 bytes) than its
   format says (43) – a fault in the firmware that recorded it. Its signals were left out; everything else
   is read." (en + he – find where the `corruptBytes` text lives in the frontend).
4. **If no single length explains a bad type** (variable garbage): drop that type's candidates from `cand`
   altogether and re-chain; report "Message `XYZ` could not be read and was left out".
5. **Give up later, and partially.** Keep the two `BinFormatError` limits only for a file where, after
   steps 1–4, less than **20 %** of the bytes chain. Otherwise load what chained and report the share
   ("62 % of the log was readable"). The limits' numbers get a comment saying why.
6. Performance: the loader is vectorised numpy on purpose (a 1.2 GB log opens in seconds). Steps 1–2 must
   be array operations (`np.bincount`, `np.searchsorted`), not a Python loop over messages; run the existing
   speed test if there is one (`grep -rn "seconds\|perf" backend/tests/test_bin*`) and note the time before
   and after on `examples/copter_flight.bin`.
7. **Fixtures by script** `tools/make_bad_bin_fixture.py`, from `examples/copter_flight.bin`: (a) every
   message of one frequent type gets 4 extra bytes after it (written longer than declared); (b) the same
   type truncated by 3 bytes; (c) one type's payload replaced by random lengths. Write small outputs
   (first ~2 MB) to `tests/data/`.

**Done when:** pytest: (a) and (b) load, the faulty type's signals are absent, every other signal equals
the clean file's (same count, same values), the report names the type and both lengths; (c) loads with the
type dropped; a truly random file still raises `BinFormatError`; the clean file's load time is within 10 %
of before; the frontend shows the notice (Vitest for the text builder, or e2e if the notice has a test).

### P4 – The Map is 3D — L

**The decision, and one reservation.** The owner wants to drop 2D: "we have 3D and can always look from
above." For the user, yes: **one Map, and it is the 3D view**; "2D" becomes a camera – *From above*. But
the 2D engine is **not deleted** in this round: without WebGL (remote desktops, virtual machines – common in
his users' labs) the 3D view cannot draw, and today's fallback there (tracks on bare axes) is far poorer
than the 2D map. So `GeoChart.tsx` stays in the code as **the Map's automatic drawing when 3D is not
possible**, and is no longer something the user chooses. Tell the owner this in your report in two
sentences; if he still wants it removed entirely, that is one later task.

1. **What the user sees:** the plot-type list has *Map*; the **2D | 3D** switch (`PlotView.tsx` `.map-view`)
   is removed. The camera group in `MapBar.tsx` becomes **General · From above · On the object · Chase**
   (+ P9's Cockpit). *From above*: straight down, north up, the whole flight framed; drag moves, wheel
   zooms, the view stays flat (tilting it turns the camera to General). With an object chosen it stays
   centred on it; *track up* is a toggle beside it (what 2D's track-up was).
2. **How it is stored (backward compatible):** saved `mode` values do not change. A plot with
   `mode: "geo"` **and objects** is drawn by the 3D view with the camera *From above* (a new optional
   `Plot.camera` value, e.g. `"top"`; absent on such a plot = `"top"`); `mode: "3d"` as today. New maps
   are created as `"3d"`. No migration writes into old sessions; a session saved by this version opens in
   1.25 as a 2D or 3D map as before.
3. **When 3D cannot draw** (`hasWebGL()` false, or the context is lost): the Map is drawn by `GeoChart`
   with one quiet line "Shown flat – this computer cannot draw 3D" and the same bar (its *General* /
   *Chase* behave as 2D already does). `Globe3DFallback.tsx` is retired (delete it and its strings once
   nothing imports it). A setting (P8) *Map drawing: Automatic · Always flat (light)* lets a user on a slow
   machine choose the flat drawing.
4. **A plain longitude / latitude plot of two signals with no objects** (`mode: "geo"` without objects):
   unchanged, drawn by `GeoChart` – it is an X-Y plot on a map, not "the Map". Check the template and the
   e2e tests that use it (`grep -rn "lon_and_lat\|geo.csv" tests/e2e`).
5. **Parity – everything 2D had must be in 3D before the switch goes** (make a table in the notes: feature,
   where it was in `GeoChart.tsx`, where it is now):
   - **the mouse's position** (the owner asked): a readout in the 3D view – latitude, longitude (the
     precision rule of `.geo-readout`), **ground height** there, and distance / bearing from the reference
     object when there is one. From `scene.globe.pick(ray)` (already used by the measure tool around
     `Globe3D.tsx` line 225), throttled to one update per frame; hidden when the mouse leaves. Same readout
     in the offline 3D page (raycast the ground meshes) and keep the 2D page's.
   - north up / track up; the ring tooltips; the relation lines and their distance; track colouring by a
     value (`trackColors`); the object dialog from a click; *back to the object* after a drag; keyboard
     (`+ − 0`, arrows); the offline basemap and online imagery choice; the hover on a track point (time,
     position, altitude).
   - anything in the list that 3D lacks: build it in `Globe3D.tsx`; do not leave a 2D-only feature behind.
6. **Reports and pages:** a Map plot in an HTML report is the 3D page (`scene3d.html`), opening on the
   plot's camera (so a former 2D map opens *From above*); `map.html` stays as the page's drawing when the
   reader's browser has no WebGL (today that case shows a static picture – the 2D page is better: put it in
   the same frame and switch in the page). Static formats: *From above* → `mapimage.render` (the clear flat
   map picture); any other camera → `scene3d.render`.
7. **Words:** *Map* everywhere; "2D" / "3D" disappear from the UI except *3D (XYZ)* (the plot of any three
   signals). Guides en + he.
8. Lazy loading stays: CesiumJS loads only when a Map is on screen (CLAUDE.md "lazy parts stay lazy").

**Done when:** a 1.25 session with a 2D map and a 3D map opens as two Maps, the first *From above*; with
WebGL off the Map is the flat drawing with its line; the parity table is complete and each row has a test or
a note why not; e2e: the mouse readout in 3D shows a latitude within 0.01° of the object under it (the
existing 3D tests show how positions are checked); the tests that clicked the 2D | 3D switch are adapted
(say which).

### P5 – A ground with relief, anywhere — M

1. **Elevation for the whole world when the network is allowed** – `basemap.py`: a new source beside the
   bundled grids: **terrarium tiles** (C2) at zoom ≤ 12 (~30 m), fetched only when the user has not chosen
   *Never use the network* and `SV_OFFLINE` is not set, stored in the existing tile cache folder (find how
   `mapimage.tile_bytes` caches online imagery and use the same store and the same rules), decoded to
   heights. `ground_at` and `terrain_tile` take the **finest of: bundled fine grid → cached / fetched
   terrarium → bundled coarse grid**. A fetch never blocks the UI: `terrain_tile` answers from what it has
   and the tile improves on the next request (CesiumJS re-requests on camera moves; check, and if it does
   not, expose a "terrain updated" tick the view listens to). Attribution "Terrain Tiles (Mapzen: SRTM,
   GMTED2010, ETOPO1)" is already written by `ATTRIB` – make sure it is on the picture / page when used.
   Add `basemap.step_at(lat, lon)` → the step in metres of the best source there.
2. **A terrain file of your own, for offline sites** – Settings (P8) *Elevation files*: a folder
   (`~/.signalviewer/terrain/` by default) of SRTM `.hgt` files (plain big-endian int16 grids, 1201² or
   3601² – read with numpy, no library); the loader lists what it found. `.hgt` only in this round.
3. **Say what the ground is:** the 3D view (app and page) shows one quiet line when `step_at` at the scene's
   centre is over 1 km: "Only coarse heights here (11 km grid) – allow the network or add elevation files in
   Settings for real relief." The page's footer always says "terrain: N m grid".
4. **The page's ground reaches the horizon** (`scene3d.py`, `scene3d.html`): two meshes – **near** (the
   tracks' box + margin, 129 × 129, its picture 1024 px) and **far** (a square around the same centre,
   side = max(8 × the near side, 40 km), capped at 200 km, 129 × 129, its own 1024 px picture at the lower
   zoom `_ground_image` picks); the far one hidden under the near one (lower it 2 m there or discard those
   fragments – whichever shows no seam); `THREE.Fog` from 0.6 × to 1.4 × the far side so the edge fades into
   the sky; a sky gradient; the sun low (≈ 35°, from the north-west as on printed maps) so slopes shade.
   Heights stay **×1 by default** (honest); when the relief is under 4 % of the near side a hint beside
   *Heights* says "flat here – try ×2 or ×5"; add ×10. `scene3d.render` draws the far ground too.
   Curvature is not drawn (say so in `docs/maps-and-3d.md`).
5. The app's 3D view: check its lighting and exaggeration against the page's so both look alike
   (`Globe3D.tsx`: `scene.globe.enableLighting`, `verticalExaggeration`); add the same *Heights* choice to
   its bar if it is missing (one control, in `MapBar.tsx`, for both).

**Done when:** pytest with the network **mocked** (a fake terrarium tile): `ground_at` uses it where the
bundled grid is coarse and never when offline is forced; `.hgt` in a temp folder is found and used;
`step_at` gives 139 at (32.8, 35.6) and > 1000 at (45.5, 124.3) with no cache and no network; the page for a
track near (45.5, 124.3) holds the coarse note; `scene_data` on `examples/ardupilot_lanes.csv` returns a far
ground ≥ 40 km wide with `max − min > 300 m`. e2e (WebGL): `__scene.state` reports two grounds and fog.
**No test may touch the real network.**

### P6 – Click an object in the legend to hide or show it — S

One rule: **a hidden object is not drawn, not part of *Fit*, and keeps its place in the list (greyed, struck
through) so one click brings it back.**
- `MapObject.hidden?: boolean` (optional; absent = shown). One helper `shownObjects(plot)` in
  `mapObjects.ts`, used by every drawing loop in `Globe3D.tsx` and `GeoChart.tsx` (list the loops you
  changed in the notes).
- The app's chips (`PlotView.tsx`): a small eye button before the name (`aria-pressed`; "Hide on the map" /
  "Show on the map"); **Alt+click = only this one** (again: all). The chip's own click still opens the
  dialog.
- The pair: a hidden reference or compared object shows "— hidden —" on its side of the relation box (the
  pair is not moved silently); the camera on a hidden object goes to General.
- Specs and pages: `geoSpec` / the scene spec carry `hidden`; pictures skip hidden objects; in the pages each
  legend row is a button (click, Alt+click) – one implementation `svLegend` in `relation.js`;
  `window.__page.hidden()` for tests.

**Done when:** Vitest for `shownObjects` and an old session; e2e: hide an object in the app → gone from the
Map, *Fit* ignores it, a reopened session keeps it; in the page a legend click hides, Alt+click leaves one.

### P7 – Places, as in Google Earth — M/L

**What the user gets:** the airfield, the range, the target, the ground station – named points (and simple
lines / areas) that are **always on his Map**, in every session, in the pages and the exports.

1. **Model.** A place: `{id, name, lat, lon, alt?, icon, color, note?, kind: "point" | "line" | "area",
   points?: [lat, lon][]}`. Two lists:
   - **My places** – the user's own, for every session: kept by the app in
     `~/.signalviewer/places.json` (a small backend endpoint pair like the settings'; not inside
     `ui_settings.json`, so it can be copied to a colleague);
   - **Places of this session** – `Workspace.places?: Place[]` (optional; travels with the session and the
     template).
   Icons: a small fixed set drawn as vector shapes (pin, airfield, target, antenna, flag, home, camera) – no
   image files.
2. **Adding:** right-click on the Map → *Add a place here…* (name, icon, colour; the position filled from
   the click, height from the ground); *Add a place…* by typing coordinates (decimal degrees, or
   `32°41'13"N 35°23'24"E` – one parser with tests); from an object: its chip's menu → *Mark this spot*
   (the object's position at the cursor); **import** `.kml` (points, lines, polygons – plain XML with
   `xml.etree`; `.kmz` is a zip of one – `zipfile`), `.geojson`, and `.csv` (`name, lat, lon[, alt]`).
3. **A Places panel** – one place for the list (CLAUDE.md §3): the Map's ⋯ menu → *Places…* opens a small
   panel docked in the Map: search box, the two lists with eye toggles (P6's look), click = **fly there**
   (a smooth camera flight), edit, delete, *Keep in My places* / *Only this session*, import / export
   (`.kml`). Command palette: "Go to a place…", "Add a place…".
4. **Go to:** the panel's search box also takes coordinates ("32.687, 35.39") and flies there.
5. **Saved views:** *Save this view* stores the camera (position, heading, tilt) under a name beside the
   places ("Runway 27 final", "Over the range"); click = fly to it. Stored like places (a `kind: "view"`).
6. **Drawing:** in the 3D view places are billboards with a label and a thin pole to the ground; lines /
   areas are draped on the ground (Cesium ground primitives; if they cost frame rate in the software-WebGL
   light mode, draw them as lines at ground height + 2 m and say so); in the flat drawing and both pages
   the same shapes. Places take part in *Fit* only when the Map has no objects.
7. **The relation box and the mouse readout know places:** the readout adds "1.24 km from Runway 27" for the
   nearest shown place within 50 km; the relation box's *Compared with* list ends with the places (distance
   and bearing from the reference to a fixed point – `relate` already works on positions; a place is a
   constant track).
8. Exports: KML (P1) includes places; the pages draw them; ACMI: a place is a stationary object
   (`Type=Navaid+Static+Waypoint` – check the tag against the spec's list before using it).

**Done when:** pytest: KML / KMZ / GeoJSON / CSV import round-trips (a fixture of each, made by a script),
the coordinate parser's table; Vitest: places in a session survive save / load, an old session has none;
e2e: right-click → add → the place is in the panel and on the Map; click flies there (camera target within
100 m); it appears in the HTML page.

### P8 – Settings: "Map and objects" — S/M

A new group in `SettingsDialog.tsx`, values through `getPref` / `setPref` (keys `sv3.map.*`), read through
**one** module `frontend/src/mapDefaults.ts` (with the defaults below; nothing else reads those keys).
**Settings apply to new things only** – an existing session, template or object is never changed by a
setting; write that sentence under the group's title. A *Reset this group* link.

| Setting | Choices (default first) | Used by |
|---|---|---|
| Icon of a new object, per class – truth / navigation / receiver / other | aircraft · uav · drone · missile · ship · vehicle (aircraft for all = today) | `candidateObject` (instead of the fixed `kind: "aircraft"`) and the object dialog's new-object default; the class is the candidate's (`objectDetect.ts` – check the field's exact name and values) |
| Camera of a new Map | General · From above · On the object · Chase | a new Map plot |
| Map drawing | Automatic · Always flat (light) | P4.3 |
| Relation box | shown · hidden | `relHidden` of a new Map |
| Names on the Map | shown · hidden | labels (app, pages) |
| Track width | 2.5 px · 1.5 · 4 | the app, and through the spec the pages and pictures |
| Model size | medium (26) · small (18) · large (36) | `MapObject.size` default |
| Distances and heights | metres / km · feet / nautical miles | the relation box, readouts, hover, pages, story sentences – converted in **one** function per side (`fmtDistance` in the app, `dist()` in `relation.js`) |
| Coordinates | decimal degrees · degrees-minutes-seconds · MGRS | the mouse readout, the hover, places (MGRS: a small pure function with a test table; if it grows past ~120 lines leave MGRS out and say so) |
| Elevation files | a folder | P5.2 |
| Export rate for Tacview / KML | 10 · 5 · 2 · 1 samples a second | P1 |
| Story | on · off; length: about 90 s · 45 s · 3 min | P10 |

More general settings worth adding in the same pass, **only if each is a few lines** (otherwise list them in
the report for the owner to choose): the default theme of an exported page (as the app · light · dark); the
language of an exported page (as the app · English · Hebrew); *Ask before closing with unsaved changes*.

**Done when:** Vitest for `mapDefaults.ts` (no prefs → defaults; each pref read; a bad value falls back);
e2e: "navigation → drone" then *Add all* on `examples/ardupilot_lanes.csv` → the lanes are drones; a session
saved before still shows aircraft.

### P9 – The wow: a Map people stop to look at — L

Each item is independent; do them in this order and stop after any of them if time is short. All of them
must hold the frame rate: measure frames per second on `examples/ardupilot_lanes.csv` before and after
(the 3D view has a software-WebGL "light" mode – every effect below is **off** in it).

1. **Sky, sun and shadows.** CesiumJS: `skyAtmosphere`, `scene.globe.enableLighting`, the sun's position
   from the scene clock; shadows of the models on the ground (`shadows` on the models and the terrain) with a
   soft shadow map. When the recording has real dates (epoch seconds, the test `write_acmi` uses: first time
   > 1e9) the clock is the recording's time, so the light is **where the sun was**; otherwise a fixed
   mid-morning sun. The viewer was created with `skyAtmosphere: false` – read why (line ~194) before turning
   it on. In the page: the same sun direction (NOAA low-precision formulas in `scene3d.py`, ~25 lines,
   tested against two known values) and a sky gradient.
2. **The object reads in space:** a thin drop line from each object to the ground and a soft dark disc under
   it (its "shadow" even with shadows off); the last 10 s of its track as a brighter, slightly wider trail
   that fades (the app and the page) – on top of the whole track, which stays as it is.
3. **Camera flights.** Every camera change **flies** (ease, ~1.2 s) instead of jumping: choosing a camera
   mode or an object, *Fit*, a place, a story moment. One function in each renderer (`flyTo` in
   `Globe3D.tsx` – Cesium has `camera.flyTo` / `flyToBoundingSphere`; `glideTo` in `scene3d.html`) and
   nothing else moves the camera abruptly. *Reduce motion* (the OS setting, `prefers-reduced-motion`) → no
   flights.
4. **Cockpit camera** – a fifth camera: at the object, looking along its heading and pitch, **rolling with
   it** (the horizon tilts); its own model hidden; field of view 70°. App and 3D page.
5. **A flight display** for the object the camera is on (app and page, one look): the attitude indicator
   the page already has (`adi` in `scene3d.html`) plus two tapes – speed (ground speed from the track) and
   altitude (with height above ground) – and the heading. Shown / hidden by a *Display* toggle in the bar;
   off by default in *General*, on in *Chase* and *Cockpit*.
6. **A mini-map** in the corner while the camera is close to an object (*On the object*, *Chase*,
   *Cockpit*): the whole flight from above, north up, the object as a dot with its heading, the camera's
   view as a wedge; click = fly the camera there. A small 2D canvas over the view (not a second Cesium).
7. **The error, drawn.** When the relation box is shown and the pair is the **same vehicle** (median
   distance under 20 m – e.g. truth and a navigation solution): a thin translucent surface between the two
   tracks, coloured by the distance (green → amber → red at the 95th percentile), with its scale in the
   relation box and a toggle "Error surface". The reader sees *where* along the flight the solution left
   the truth, and by how much. App and page; in the flat drawing the compared track is coloured instead.

**Done when:** each item has a state field for tests and one assertion; the frame rate with all of them on
is within 20 % of before on the fixture (write both numbers); the light mode shows none of them; two new
pictures by `tools/make_live_report_media.py`: `docs/images/36_map_wow.png` (the app's Map or the page with
sky, shadows, trail and flight display) and `37_story.png` (P10).

### P10 – The surprise: Story mode – the flight tells itself — L

**The idea.** A live page today is a player: the reader must know where to look. Story mode makes it a short
guided film the page plays by itself – **"▶ Story"**. The time runs; at each moment that matters the film
slows, the camera flies to the object involved, and a card says what happened in one plain sentence with its
number – "nav drifts north: 6.2 m from truth", "closest: 41 m at 02:13", "GPS: 9 satellites (warning from the
log)" – then it moves on. In two minutes a manager or a customer has seen the flight and its problems without
touching anything, offline, from one file. Any card can be clicked to stop there and explore.

1. **The moments** – `backend/svcore/story.py` (pure numpy, tested):
   `moments(objects, events, pair, units) -> list[dict]`, each `{t, kind, title, text, object, level}`:
   - the marks the page already has (`replay.events`: the log's errors and warnings, health findings, the
     user's notes) → `kind: "event"`;
   - from the tracks: `takeoff` / `landing` (height above ground crossing 5 m), `highest`, `fastest` (ground
     speed, 1 s window), `steepest` (max |roll| over 30°), for the pair `largest error` (same vehicle: median
     distance under 20 m) or `closest` and `farthest` (two vehicles); entering / leaving 200 m of a place
     (P7) → "over Runway 27";
   - rules: drop a computed moment within 3 s of a stronger one (error > warning > finding > note > largest
     error > closest > takeoff / landing > the rest); at most 12; sorted by time; each `text` one sentence
     with one or two numbers in the user's units; en + he through a table **in this file**.
2. **Into the page:** `report.py`, when the request has `replay`: `replay.story` per tab, from the tab's
   first Map plot (a tab with no Map still gets the event moments). The standalone 3D page gets `D.story`.
3. **The player** – inside the one time bar (`viewer.js`, the `RP` block; not a second player): a
   **▶ Story** button beside Play (hidden when there are no moments); speed so the whole recording takes
   about 90 s (between ×1 and ×60) but ×1 from 3 s before a moment to 2 s after; a 4 s pause on the moment
   with its card (`#rp-story`: title, sentence, "3 / 9", ◀ ▶; an edge coloured by level;
   `aria-live="polite"`); Esc or a click on the timeline ends it; the moments are diamonds on the timeline
   and clickable; `#story=1` in the address starts it.
4. **The camera follows:** the message to the map frames gains
   `focus: {object, close}`; the 3D page flies (P9.3) to *On the object* at ~400 m, or *Chase* when
   `close`; when the story ends the reader's own camera comes back.
5. **In the app:** the same moments as a **Story** button on the Map's bar: it drives the app's cursor and
   the Map's camera the same way and shows the same card over the Map (the endpoint returns `moments` for the
   plot's objects and the session's findings / notes). If this takes more than a day's work, ship the pages
   first and say what is left.
6. **PDF / Word:** a section "The flight in N moments": a table (time, title, sentence) and the 3D picture at
   the first four moments, two per row.

**Done when:** pytest `test_story.py` on the Tabor flight that `tools/make_live_report_media.py` builds
(truth / nav / gps, nav drifts 6 m north): "largest error" near the end with 6.x m, `highest`, `fastest`,
the given events; never more than 12; never two within 3 s; Hebrew for every kind. e2e: the page's Story
button shows a card within 30 s (`window.__replay.story` → `{on, index, count}`), ◀ ▶ move the time, the 3D
frame's camera object becomes the moment's object, Esc restores the camera.

### P11 – Docs, checks, patch — S

- `CHANGELOG.md`, the existing `## 1.26.0` section, user wording, one bullet per task.
- Guides en + he (`docs/GUIDE.md`, `docs/GUIDE.he.md`): the Map (one view, its cameras, the readout), places,
  hiding objects, the three exports, the "Map and objects" settings, Story. `docs/maps-and-3d.md`: P4's
  drawing rule, P5's elevation sources and limits, P2's "no position" rule. `docs/features.md`,
  `docs/api.md` / `docs/command-line.md` for what was added. `docs/limitations.md`: what the flat drawing
  lacks; no curvature in the page.
- README: add `36_map_wow.png` and `37_story.png` with one sentence each under "New in 1.26", and change
  "2D / 3D" wording to "Map". Nothing else.
- `python tools/make_validation_doc.py`; `mkdocs build --strict`; backend pytest; mypy; `tsc -b`; Vitest;
  the e2e files of §D; `frontend/dist` built; `ROADMAP.md` Milestone 30 with done-notes; `TASKS.md`; the
  patch as in §A.

---

## F. Invariants most at risk in this round (CLAUDE.md binds; these are where it will be tempting to slip)

- **One way to do a thing:** one source of an object's track for every export (`acmi_objects`); one "is this
  a position" rule (`track_of`); one `shownObjects`; one `mapDefaults.ts`; one camera-flight function per
  renderer; one legend / toolbar / relation implementation for the pages (`relation.js`); one story player
  inside the one time bar; one units formatter per side.
- **Offline, always:** everything works with no network. Online elevation is an improvement that is asked
  for only when the user allows the network, cached, attributed – and never fetched in a test. The pages
  load nothing from outside; no new library, no CDN.
- **Backward compatible:** saved `mode` values unchanged; every new field (`MapObject.hidden`, `Plot.camera`
  values, `Workspace.places`) optional with the old behaviour as default; a 1.25 session opens; settings
  never alter existing sessions.
- **Honest:** heights ×1 by default; coarse ground says so; an object with no position is not drawn at 0, 0;
  a log that loaded partly says what was left out and how much was read; the Tacview fix is "not yet
  confirmed" in the docs until the owner confirms it; a story sentence states only what was computed.
- **Speed:** the 3D view's frame rate and the .bin loader's time are measured before and after; effects are
  off in the light mode; CesiumJS stays a lazy chunk.
- **en + he** for every string in the app and in the pages (`mapimage.PAGE_STRINGS`, the story's table), RTL
  checked, keyboard reachable, CSS variables / the pages' theme variables.
- **One place per control:** exports in one submenu; the eye on the chip / legend row; places in their
  panel; settings in the Settings dialog; Story beside Play.

---

## G. Open questions for the owner (work with the default; record his answers in `TASKS.md`)

- **Q1 – Tacview.** Which probe file opened first, and the Tacview version. *Default:* all of P1.
- **Q2 – The damaged .bin.** The file (or its start) and the faulty message's name. *Default:* P3 on made
  fixtures.
- **Q3 – 2D.** P4 keeps the flat drawing only as the automatic stand-in where 3D cannot draw, and for a plain
  lon / lat plot. *Default:* that. Alternative: delete it entirely (those machines then get tracks on bare
  axes).
- **Q4 – Elevation from the network.** *Default:* allowed only when the network is allowed, cached, with a
  note when the ground is coarse. Alternative: ship a 1 km world grid in the installer (+60–90 MB).
- **Q5 – Models in Tacview.** *Default:* C172 / MQ-9 / Bell 206 / AIM-9M.
- **Q6 – Story in the app.** *Default:* pages first, the app if time allows.

---

## H. More ideas – NOT part of this round (the owner picks later)

- **Split view:** two cameras on one time (chase + from above; cockpit + mini-map full size).
- **Uncertainty tube:** the EKF's own variances (ArduPilot `XKF4`, PX4 `eph` / `epv`) as a translucent tube
  around the track.
- **Wind:** arrows along the track from the logged wind estimate.
- **Ghost of the golden run:** *Compare*'s reference flown as a grey ghost beside the current flight.
- **Altitude profile strip** under the Map: height above ground along the flight with the terrain filled in.
- **Mission, geofence and home** from the log (ArduPilot `CMD`, MAVLink mission items) as places and lines.
- **A film file:** the story rendered to MP4 / GIF for a slide.
- **Hide the real place:** tracks moved to a made-up origin with no map, for flights whose location must not
  leave the building.
- **Line of sight:** is the ground station (a place) visible from the aircraft at each moment, given the
  terrain – a coloured strip on the timeline.
- **3D buildings / obstacles** from a user's file (GeoJSON footprints with heights).

---

## I. When you stop

Update the Status box (stage reached; a code map of what you built – file and function names; what is left),
the board and Log in `TASKS.md`, and make the patch (§A). If you stop in the middle of a task, say exactly
where (file, function, what is half-done). Your report to the owner, in Hebrew: what was done, what was
**not** done and why, which e2e files ran, the frame-rate and load-time numbers, and any of Q1–Q6 still open.
