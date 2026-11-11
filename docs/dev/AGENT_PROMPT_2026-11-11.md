# Agent prompt – Signal Viewer, owner's round of 2026-11-11: one live HTML page (plots, map and 3D on one time), the 3D view in reports, clearer names for the two maps

> ## Status – read this first (update at the end of every session)
>
> **Stage reached: done in one focused pass, 2026-11-11 - version 1.26.0, ready to tag.** The owner's answers
> (2026-11-11) changed the plan: **Q1 - one Map with a 2D | 3D switch** (built, not only renamed; "3D" alone is
> XYZ: *3D (XYZ)*); **Q2 - three.js** (r159 UMD, MIT, embedded in the page; `report_assets/three.min.js`).
> Built: H1 (as Q1), H2 (`plotSpec.ts` `pagePlot` / `pagePlots`), H3 (`app/scene3d.py` `scene_data`, `render`;
> always the backend's picture - Q3's alternative, simpler and the same everywhere), H4 (`report_assets/scene3d.html`,
> in a frame like the map's page, same `sv: "replay"` message), H5 (the report panel's HTML sends the replay block
> with `compact: false, link: false` - `body.live`, tables kept, a zoom per plot), H7 (`sv.scene_image` /
> `sv.scene_html`, `cli map --3d`), H8 (CHANGELOG, guides, features, maps-and-3d, README). **Not built (left
> for a next round):** XYZ live in the page (still a picture), H6's shared tiles / page budget / size choice,
> the screenshot as the static picture. Tests: `backend/tests/test_scene3d.py`, `frontend/src/pagePlots.test.ts`,
> `tests/e2e/test_live_report.py`; e2e run: test_live_report, test_replay, test_map_export, test_globe3d,
> test_less_clutter, test_object_templates, test_offline_map, test_map_objects, test_object_relations, and
> test_features / test_heuristics / test_hover_ghost / test_object_frames (-k map, mode, report, 3D) - 61 green;
> the whole suite is the owner's. README pictures: `tools/make_live_report_media.py`.
>
> **Base and patch.** As in the last round: the owner applies each patch and pushes it to `main`. Make every
> session's patch against `main` as it is when the session starts (at the time of writing: `18d3257`,
> 1.25.0 with group F).
> ```
> git clone https://github.com/DavidAlpert11/SignalViewer.git && cd SignalViewer
> git log --oneline -3          # the base: main's HEAD
> cd frontend && npm ci && npx tsc -b && npm test
> ```
> At the end: `git format-patch <base>..HEAD --stdout > signalviewer-<date>.patch`, check it with `git am` on
> a fresh clone of `main`, update this Status box and the board in `docs/dev/TASKS.md` ("Owner's plan
> (2026-11-11)"), and hand both files to the owner. Keep a copy of this prompt in the repo as
> `docs/dev/AGENT_PROMPT_2026-11-11.md` and keep the two copies equal.
>
> Milestone 29 in `ROADMAP.md` (add it); target version 1.26.0.

---

## The goal

The owner pushed 1.25.0, tried the replay page and the reports, and said (2026-11-11):

1. **The replay page shows only the map – the flat one.** The view he thinks of as "the real map" is the
   3D one, and it is not in the page at all. The replay should be able to include the 3D view.
2. **The names confuse.** The plot kind called *Map* is a 2D display; the 3D earth with terrain is called
   just *3D*. Someone looking for "the map" does not know which is which.
3. **One page, everything live.** An HTML report should itself contain all the plots, the maps and the 3D
   view, with **one time slider** that moves all of them – not a report where each plot is alone and a
   separate "replay" page that has the slider.
4. **Static formats show pictures.** When he chooses a static file (PDF, Word, PNG) each of those –
   including the 3D view – appears as an image.

**Much of the machinery exists – extend it, do not build a parallel one** (CLAUDE.md, "one way to do a
thing"). The replay page already *is* the HTML report with one extra block; this round finishes that idea.

---

## 0. Before you write any code

1. Read `/CLAUDE.md`, `docs/dev/TASKS.md` (Current state + "Owner's plan (2026-11-10)", decisions 1–34, group F),
   `docs/dev/UX_REVIEW_2026-11-11.md`, and `docs/dev/AGENT_PROMPT_2026-11-10.md` §L11 / §L12.
2. Read these files fully, and `grep` every caller of what you change across `frontend/src/` and `backend/`:
   - `frontend/src/replay.ts` (`replayPlots`, `replayBody`, `makeReplay`), `frontend/src/plotSpec.ts`
     (`plotSpec`, `geoSpec`), `frontend/src/components/ReportPanel.tsx` (`buildBody`, the plot list),
     `frontend/src/globeBridge.ts` (`globeImage`, `geoViewBounds`), `components/Globe3D.tsx` (tracks, models,
     camera, `saveImage`, the `ground` clamp, the software-WebGL settings), `Globe3DFallback.tsx`,
     `components/XYZChart.tsx`, `mapObjects.ts` (`derivedAttitude`, `objectAt`, `trackRequest`),
     `components/PlotView.tsx` (the mode list, the ⋯ menu), `templates.ts` (a plot titled with `mode3d`),
     `i18n/mapsAnd3d.ts`, `i18n/app.ts` (the replay strings).
   - `backend/app/report.py` (`plot_data`, `_geo_data`, `build_html`, `_replay`, `_replay_bar`, `REPLAY_CSS`,
     `_collect`, `build_pdf`, `build_docx`, `build_plot_html`, `build_image`, `_draw_xyz`),
     `backend/app/report_assets/viewer.js` (the `RP` block: `setTime`, the bar, play, `#t=`, the message to
     map frames) and `map.html` (its `message` listener), `backend/app/mapimage.py` (`map_data`, `render`,
     `_tiles_for`, `build_html`), `backend/app/basemap.py` (`terrain_tile`, `ground_at`, the tiles),
     `backend/app/routes/export.py` (`ReportRequest`, `ImageRequest`, `open_page`),
     `backend/signalviewer/__init__.py` (`map_image`, `map_html`, `report`), `backend/signalviewer/cli.py`.
   - Tests: `frontend/src/replay.test.ts`, `backend/tests/test_replay.py`, `tests/e2e/test_replay.py`,
     `tests/e2e/test_map_export.py`, the 3D e2e files (how they start a browser with WebGL).
3. Run the baseline and write the numbers into the Log: backend pytest, mypy, `tsc -b`, Vitest (commands in
   CLAUDE.md). Note any failure that exists before you start.

---

## 1. Findings (read on `18d3257`; the code was read, not run – H0 confirms each by running)

| # | What | Where | Effect |
|---|---|---|---|
| G1 | A 3D plot is filtered out of the replay, the report and the report panel's plot list | the test `p.signals.length \|\| (p.mode === "geo" && p.objects?.length)` – written three times: `replay.ts` `replayPlots`, `ReportPanel.tsx` `buildBody`, `ReportPanel.tsx` the list (and a fourth time in its "empty" hint) | a 3D plot has objects and no lines, so it is dropped **without a word**. A tab with a map and a 3D view gives a replay with only the flat map – the owner's report |
| G2 | The backend has no 3D case at all | `report.py` `plot_data`: `geo`, `spec`, `env`, `xyz`, `step`, `xy`, `fft`, `time` | even if the frontend sent a 3D plot, nothing would draw it |
| G3 | The only 3D picture is a screenshot taken in the browser | `Globe3D.tsx` `saveImage` (`scene.canvas.toDataURL`), registered in `globeImage` by plot id | works only for a 3D plot that is on screen; a report of all tabs, the CLI and Python cannot get one |
| G4 | Two HTML pages from one builder | `build_html`: with `replay` in the request the page has one time (bar, play, marks, `#t=`), one zoom for the time plots, and the maps follow; without it each plot has its own cursor and the map its own slider | the "report" is not live as a whole; the owner wants it to be |
| G5 | Only `time` plots and maps follow the time | `viewer.js`: `p.spec.mode === "time"` everywhere in the `RP` block | X-Y, XYZ, spectrogram and envelope stay still while the time moves; XYZ and the spectrogram are PNG images in the page |
| G6 | Each map in a page is a whole page of its own in a frame, with its own tiles in both themes | `_geo_data` → `mapimage.build_html(..., budget=4 MB)` → `<iframe srcdoc>` | two maps (or a map and a 3D view of the same place) carry the same tiles twice; nothing limits the whole page |
| G7 | Names | `i18n/mapsAnd3d.ts`: `modeGeo` "Map" / "מפה", `mode3d` "3D" / "תלת-ממד", `modeXyz` "XYZ"; `PlotView.tsx` the mode list | "Map" = 2D canvas map; "3D" = the earth with terrain (CesiumJS); "XYZ" = three signals on plain 3D axes. Nothing says the first two are the same thing seen two ways |
| G8 | What the 3D view is made of | `Globe3D.tsx`: CesiumJS (lazy, `/cesium/`), terrain from `/api/terrain/{z}/{x}/{y}` (`basemap.terrain_tile`, 65 × 65 heights), tiles from `/api/tiles/...`, models `frontend/public/models/*.glb` (six files, 116 KB together) | CesiumJS cannot reasonably go inside a single offline HTML file (its size, its workers and data files). The **data** it shows – heights, tiles, tracks, attitude, small models – can |

Things to be careful about:
- `frontend/src/replay.ts` says "It IS the HTML report – one builder, one viewer". Keep that true: no second
  page builder, no second time bar.
- `mode` values (`"geo"`, `"3d"`, `"xyz"`) are saved in sessions and templates. **Only the words on screen
  change** in H1.
- Where the attitude of an object without angles comes from (`derivedAttitude` in `mapObjects.ts`): if that
  rule lives only in TypeScript, the backend must not get a second copy of it. Check, write it in the notes,
  and choose: move the rule to the backend, or have the frontend send what it derived. Say which and why.
- Terrain heights and the objects' altitudes may use different references (last round's idea I1). Follow
  what `Globe3D.tsx` does today (its `ground` clamp) so the page and the app agree; do not "correct" it here.
- A browser without WebGL (remote desktop, a virtual machine, Chrome / Edge 139+ without software WebGL –
  see `hasWebGL` / `softwareWebGL`): the page must still open and show the 3D view as its picture.

---

## 2. Testing policy for this round

CLAUDE.md applies. In addition:
- Every row G1–G6 gets a test that fails on `18d3257` and passes after the change.
- Vitest: the one "what goes into a page" function (H2), the names (H1: both languages have the new keys).
- pytest: the 3D scene's data (shapes, units, the origin, an object on the ground is on the terrain), the
  static 3D picture (non-blank, the track's pixels where expected), the page (contains the scene, no
  external URL anywhere in the file – grep for `http` outside the attribution and the footer link – and its
  size within the budget), PDF and Word with a 3D picture.
- e2e (extend `test_replay.py`, `test_map_export.py`; new `tests/e2e/test_live_report.py`): the page opened
  **with the network blocked**; the time moved from the bar, from a plot and by Play moves the plots'
  cursors, the map's markers and the 3D objects (expose the scene's state for tests the way `map.html` does
  with `window.__markers` and the replay with `window.__replay`); the same page with WebGL disabled shows
  the picture. Start the browser for WebGL the way the existing 3D e2e files do.
- After each task only the relevant e2e files; the whole suite at the end of each group. Say in the Log
  which ran.

---

## 3. The tasks, in order

### H0 – Baseline, reproduction, measurements — S

- Baseline numbers into the Log (§0.3).
- Reproduce G1 by running: a tab with two time plots, a map and a 3D view (the "Position on the map & 3D"
  template on `examples/ardupilot_lanes.csv`) → the replay page and an HTML report; write what each
  contains. **If the owner's "only a map" turns out to be something else as well** (for example the time
  plots missing in some layout), write it down and treat it as G0 – a bug to fix first.
- Measure and write down: the size of a replay page today (one map; two maps), the size of the CesiumJS
  build the app ships, how long a page takes to make.
- A fixture tab for the tests: time plots + a map + a 3D view + an X-Y + an XYZ, saved as a session under
  `tests/data/` (made by a script, committed with the script).

**Done when:** logged; the reproduction written with what was seen; the fixture exists.

### H1 – The two maps named as what they are — S

- Words only (G7): `modeGeo` → **"Map (2D)"** / **"מפה דו-ממדית"**, `mode3d` → **"Map (3D)"** /
  **"מפה תלת-ממדית"**; `modeXyz` keeps "XYZ" and gets a tooltip "three signals on plain 3D axes – not a map".
  In the mode list the two maps sit next to each other. Check every place the two keys are used
  (`PlaceOnMapDialog`, `templates.ts` – a new plot's title; old sessions keep the titles they saved),
  the command palette, Help, the guides (en + he), `docs/maps-and-3d.md`, `docs/features.md`, README.
- Short forms where there is no room (a chip, a narrow select): "2D" / "3D" **only** right after the word
  Map on the same line.
- No saved value changes; a Vitest case opens a 1.25.0 session with both kinds and gets the same plots.
- See Q1 for the next step (one *Map* with a 2D / 3D switch) – not in this task.

**Done when:** nowhere on screen or in the docs is the 3D earth called just "3D" or the flat map just "Map"
where the two could be confused; RTL checked; e2e that select a mode by its label adapted.

### H2 – Nothing is dropped without a word — S

- One function, e.g. `pagePlots(tab)` in `plotSpec.ts` (or `replay.ts` – choose, say why): for each plot of
  a tab → `{ plot, index, include: boolean, why?: TKey }`. Used by `replayPlots`, `buildBody`, the report
  panel's list and its empty hint – delete the four copies of the test (G1).
- A 3D plot with objects is included (H3 gives it something to show; until H3 lands its reason is
  "not drawn yet" – do not ship H2 without H3 in the same patch).
- What still cannot go into a page is **listed, greyed, with its reason** in the report panel instead of
  missing: an occurrences plot ("needs a condition's stretches"), a video ("the video file is not put into
  the page"), an empty plot. The replay's toast says the same when it left something out
  ("2 of 3 plots – the video was left out").

**Done when:** Vitest for `pagePlots` (every mode, with and without lines / objects); the panel lists the 3D
plot; e2e: a tab with a video and a map → the panel shows the video greyed with its reason.

### H3 – The 3D view as a picture (PDF, Word, PNG – and the fallback everywhere) — M

- `plotSpec`: a 3D plot with objects → `mode: "3d"` with what the map sends (`geoSpec`) plus the objects'
  attitude ids, kind (model) and size, the camera (what it follows, its heading / pitch / range if the view
  has them), the vertical exaggeration if any.
- **Backend, one module** `backend/app/scene3d.py` (beside `mapimage.py`; reuse its `map_data`, do not copy
  it): `scene_data(store, spec)` → a local scene around the tracks' centre: per object `t`, east / north / up
  in metres (float32, decimated like the map's tracks), heading / pitch / roll, colour, name, kind; the
  terrain as one grid of heights over the padded bounds (from `basemap`, e.g. up to 129 × 129); the ground
  texture stitched from the same offline tiles the map uses (one image, ≤ 2048 px); the bounds, the origin,
  the attribution. `render(scene, fmt, theme, scale, camera)` → a PNG / SVG drawn with matplotlib's 3D axes
  (as `_draw_xyz` does): the terrain surface, each track in its colour with its shadow on the ground, the
  objects at the cursor with their names, north arrow, scale. No browser needed.
- **The picture the user sees, when there is one:** for a 3D plot that is on screen the frontend may send
  the view's own screenshot (extend the `globeImage` bridge to return the image instead of saving it) in
  the spec; the backend uses it for static formats and falls back to `render` otherwise (another tab, the
  CLI, Python). Write in the notes that the two pictures differ in look and why that is accepted (Q3).
- `plot_data` gets the `"3d"` case (`_scene_data`, like `_geo_data`); `_collect`, `build_pdf`, `build_docx`
  and `build_image` (`/api/export/image`) draw it; the 3D plot's ⋯ menu keeps its *Save image* (the
  screenshot) – one entry, as today.
- Until H4, the HTML page shows this picture for a 3D plot.

**Done when:** pytest: `scene_data` on `ardupilot_lanes.csv` (lane 1 is 1.5 m north of lane 0 in the scene;
an object at ground level sits on the terrain grid within the grid's step), `render` gives a non-blank PNG;
a PDF and a Word report of the fixture tab contain the 3D picture; `signalviewer-cli report` gets it with
no browser.

### H4 – The 3D view live in the page — L

One small viewer, `backend/app/report_assets/scene3d.js`, embedded like `viewer.js` – **no CesiumJS, no
network** (G8). Default: written on plain WebGL with no library (Q2 has the alternative).
- Draws `scene_data`: the terrain mesh with the ground texture (lit by its slope so relief reads), each
  track as a line with a faint curtain or shadow down to the ground, each object as a small model at the
  time – position, heading, pitch, roll – with its name; the primary's solid ring and the secondary's
  dashed one as in the app (L7).
- Models: the app's six `.glb` files are tiny. Read them in the backend into plain triangle lists (a `.glb`
  is a JSON header and a binary block – numpy can read it; no new dependency) and embed only the kinds the
  page uses; an object with no model, or a model that fails to read, is a simple dart shape.
- Camera: orbit (drag), zoom (wheel / pinch), pan (right-drag or two fingers); buttons *Fit*, *Top*,
  *Follow* (a select of the objects; default what the app followed); vertical exaggeration ×1 / ×2 / ×5.
  Keyboard reachable; touch works (the page is opened on phones).
- Hover an object or a track: name, time, lat / lon / alt, height above ground.
- Time: the page's one time (H5) – the same `setTime` that moves the plots; inside the page it is a
  component, not a frame of its own (so it shares the page's tiles and theme).
- Light / dark with the page's theme; the trail (the part of the track already flown brighter than the rest).
- **No WebGL:** the section shows H3's picture and one line saying why ("this browser cannot draw 3D – the
  picture shows the moment the page was made").
- The same viewer draws an **XYZ** plot live (an axes box instead of terrain, the point at the time on each
  curve) – XYZ stops being a PNG in the HTML page (G5). If this proves more than a day's work, leave XYZ a
  picture and say so in the Status box.
- The standalone file: the 3D plot's ⋯ menu gets *Save as HTML…* (as the map has, L11) – the same page
  with just this plot (`build_plot_html`).

**Done when:** e2e offline: the fixture's page shows the 3D scene; moving the time moves the objects (state
exposed for tests); *Follow* keeps the object centred; with WebGL off the picture shows; the page of the
fixture tab stays within H6's budget; opens in current Chrome, Edge and Firefox (say which were tried).

### H5 – One live page: the HTML report has the one time — M

- **Every HTML report is live** (G4): the time bar, Play / speed, the marks (errors, warnings, findings,
  notes), `#t=`, the keys – what the replay has – in every HTML report, for every tab of it (the bar's
  extent is the recording's; switching tabs keeps the time). The request's `replay` block stays the way to
  ask for it (old callers keep working); the report panel's *HTML* sends it too.
- **The replay stays as the quick way**: one click, the tab on screen, no text – a preset of the same page.
  The report panel's card and the palette command remain; their text says what differs ("just this tab,
  as it looks now" vs "the report with its title, text and chosen plots"). One builder, one viewer.
- **What follows the time** (G5), each in `viewer.js` next to the `time` case, not in a second viewer:
  - time plots (today), the map (today; see H6 for how it sits in the page), the 3D scene (H4);
  - X-Y: a point on each curve at the time (send the curve's time with it; check what `xy_pair` returns);
  - envelope (its X is time): the cursor line; spectrogram (its X is time): a line over the image;
  - FFT, step response: do not depend on the time – unchanged, and no cursor drawn on them.
- **Zoom:** in a report each time plot opens at the range the user gave it and zooms alone, as today;
  a *Link zoom* toggle in the page's bar (on in a replay, off in a report) makes one zoom for all (Q4).
- The report's own text stays above and below the plots; the bar is fixed at the bottom as in the replay
  and must not cover the last plot or the summary (the replay's bottom padding rule).
- Printing the page (Ctrl+P) gives a static page: the bar hidden, each canvas as it is at that moment –
  a `@media print` rule and a `beforeprint` step for the WebGL canvas.

**Done when:** e2e: an HTML report of the fixture (all tabs) – the bar moves every time plot's cursor, the
map's markers, the 3D objects and the X-Y points, on each tab; the replay page gives the same for its tab;
`test_replay.py` and the report tests still pass; a report made by a 1.25.0-style request (no `replay`
block, e.g. from the CLI) is still a valid page – and is live (state what its time extent is taken from).

### H6 – The page's weight: shared ground, a budget, a choice — S/M

- **The ground once per page** (G6): tiles and the 3D texture for the same place are embedded once and
  used by every map and scene of the page. Decide between keeping the map in its frame (handing it the
  shared tiles by message) and drawing it in the page as a component like the scene; prefer the component
  if `map.html` can stay the single source for the standalone map file too. Write the decision.
- **One budget for the whole page** (default 25 MB, Q5): the tile levels, the track points and the plots'
  resolution levels are chosen to fit it; the page's footer says what was embedded ("map tiles to zoom 14,
  tracks 3000 points, 12 plots").
- **A choice before making** in the report panel: *Small (to send)* / *Full detail* with the estimated size
  next to each; the replay uses *Small*. The estimate comes from the backend (a dry run that counts, does
  not build).
- The toast after making says the file's size.

**Done when:** pytest: a page with a map and a 3D view of the same place holds its tiles once; the page of
the fixture is under the budget in *Small* and the estimate is within 15 % of the real size.

### H7 – The same from Python, the CLI and REST — S

- Python: `sv.report(...)` gets the 3D view (`view3d=True` puts a 3D scene of the objects beside the map);
  `sv.scene_image(rec, objects=[...], path="view.png")`, `sv.scene_html(rec, objects=[...], path="view.html")`
  beside `map_image` / `map_html`; an HTML report from Python is live (H5).
- CLI: `signalviewer-cli map flight.bin --objects all --3d --out view.png|view.html`; `report` and
  `compare-objects --report` unchanged in their options, live in their HTML.
- REST: `/api/export/image` and the report endpoint take `mode: "3d"`; the Pydantic models describe it;
  one example each in `docs/api.md`.
- Parity test: the scene made from Python, the CLI and the REST client is the same data (1e-9).

**Done when:** the pytest of L12's whole process is extended with the 3D picture and page through the three
ways; `docs/api.md` and `docs/command-line.md` have a working example each; mypy clean.

### H8 – Docs, changelog, release — S

- `CHANGELOG.md` (user wording): "An HTML report is now one live page: one time for all of it – the plots,
  the map and the 3D view move together, with Play and the marks to jump to. The 3D view is in reports and
  in the replay page (live in HTML, a picture in PDF, Word and PNG). The two maps are called Map (2D) and
  Map (3D). A plot that cannot go into a report is listed with the reason instead of being left out."
- Guides (en + he), `docs/maps-and-3d.md`, `docs/features.md`, `limitations.md` (what the page's 3D view
  does not do that the app's does), README's "New in 1.26", the gallery (a picture of the live page).
- `ROADMAP.md` Milestone 29 ticked with done-notes; `TASKS.md` state, board, decisions, Log.
- Full checks from CLAUDE.md, the whole e2e suite, `mkdocs build --strict`; version 1.26.0; `frontend/dist`
  built; the patch.

---

## 4. Invariants most at risk in this round (from CLAUDE.md)

- **One way to do a thing:** one page builder (`build_html`), one viewer (`viewer.js` + `scene3d.js` as its
  3D part), one time bar, one "what goes into a page" rule, one source of the scene's data (`scene3d.py`
  on top of `mapimage.map_data`). The replay is a preset, not a second product.
- **Offline, always:** the page has no external URL, no CDN, no CesiumJS; it works from a file opened by
  double-click, on a machine with no network.
- Heavy work in the backend: the page receives decimated tracks and levels; the terrain and the texture are
  made by the backend.
- Sessions / templates / autosave backward compatible: `mode` values unchanged; any new `Plot` field
  optional with a default; a 1.25.0 report request still works.
- Lazy parts stay lazy: nothing of the 3D view enters the app's main bundle; `scene3d.js` is embedded only
  in a page that has a 3D or XYZ plot.
- English + Hebrew for every string in the app **and in the page** (`STRINGS` in `report.py`), RTL checked
  (the bar, the camera buttons), CSS variables / the page's own theme variables, no hard-coded colours.
- One place per control (CLAUDE.md §3): the size choice lives in the report panel only; *Save as HTML…*
  for the 3D plot in its ⋯ menu only; the palette is the allowed second entry.
- No new dependency without a reason written in the task notes (Q2).

---

## 5. Open questions for the owner (work with the default until answered; record the answer in TASKS.md)

- **Q1 – One *Map* with a 2D / 3D switch.** H1 only renames. A further step: the mode list shows one
  *Map*, and the map plot's own bar has a **2D | 3D** switch (the objects, the pair and the time stay; the
  saved `mode` still says `geo` or `3d`). *Default:* rename now, propose the switch with a sketch in the
  Log, build it only if approved.
- **Q2 – How the page draws 3D.** *Default:* a small viewer written on plain WebGL (no library, roughly a
  thousand lines, nothing to license or update). Alternative: embed three.js (about 0.7 MB, MIT) for less
  code of our own and easier models. Not an option: CesiumJS inside the page (size, workers, data files).
- **Q3 – The static 3D picture.** *Default:* the app's own screenshot when the 3D plot is on screen (what
  the user set up), the backend's drawing otherwise. Alternative: always the backend's drawing, so every
  report looks the same wherever it was made.
- **Q4 – Zoom in a live report.** *Default:* each plot keeps its own range and zoom; *Link zoom* is a
  toggle in the bar (on in the replay). Alternative: always one zoom, as the replay.
- **Q5 – The page's size budget.** *Default:* 25 MB for *Full detail*, about 8 MB for *Small*.
- **Q6 – A video plot.** *Default:* left out with its reason (H2). Alternative: the page links to the video
  file by a relative path, to be sent beside it, and plays it on the page's time.
- **Q7 – The replay's name and place.** With every HTML report live, is "Replay page" still the right name
  for the quick one-click page? *Default:* keep the name and the card; revisit after the owner has used both.

---

## 6. Ideas for this page – the owner ticks which to build after H8 (each is independent)

Not part of H0–H8. Sizes are guesses; each line says why a flight-test or simulation engineer would care.

**Reading the moment**
- **J1 – Values at the time, in one panel — S.** A side panel listing every signal's value at the page's
  time (and with a second cursor: the value there and Δ, as R3 does in the app). Today the reader has to
  look at each plot's legend.
- **J2 – The relation at the time — S.** For a map / 3D with a primary and a secondary: distance, bearing,
  height difference and closing speed at the time, as the app's relation box shows (the numbers from
  `relate`, embedded decimated).
- **J3 – Attitude indicator — S.** A small artificial horizon with heading for the followed object, beside
  the 3D view. Attitude read at a glance, on a phone too.
- **J4 – Trail length — S.** "Whole track / last 30 s / last 10 s" for the map and the 3D view, so a long
  flight over the same field is readable.

**Getting to the point**
- **J5 – The report's text jumps — S.** Every time written in the report (a note, a finding, the row of a
  statistics table, *worst error*) is a link that moves the page's time; the comparison's statistics table
  (L8) is in the report with *Go to worst* working in the page.
- **J6 – A link to this view — S.** *Copy link*: `#t=…&tab=…&z=a,b` reopens the page on the same moment,
  tab and zoom – to paste into an e-mail or a ticket next to the file.
- **J7 – Chapters — S.** Flight modes / the user's conditions as coloured stretches on the page's bar, with
  next / previous keys (the app's U8 event navigation, in the page).

**Static formats, better**
- **J8 – Moments in PDF and Word — M.** A static report cannot move, so it shows the moments that matter:
  for each finding / note (up to a limit) a small strip – the map and the 3D picture with the objects at
  that time and the plots' values there. Uses H3's renderer with a `cursor`.
- **J9 – A short film — M.** The replay as an MP4 / GIF for a slide (the backend draws frames with H3's
  renderer and matplotlib's writers; MP4 only if ffmpeg is present – say so, do not bundle it).

**Sending it outside**
- **J10 – Hide the real place — S/M.** An option when making a page: no map background and the tracks
  shifted to a made-up origin (shapes, distances and heights kept; coordinates in hover relative), with a
  line in the page saying so. For flights whose location must not leave the building.
- **J11 – The reader answers — M.** The reader adds notes on the page (kept in the browser), saves them as
  a small file, and the owner opens that file in the app – the notes land on the timeline. A review loop
  with someone who does not have Signal Viewer.
- **J12 – The data behind a plot — S.** A *Download CSV* on each plot of the page (what is embedded, with
  a line saying it is decimated when it is).

**Carried over from the last round's list** (still open, see `AGENT_PROMPT_2026-11-10.md` §6): I1 altitude
datum per object – it also decides whether objects sit correctly on the page's terrain; I7 the track
coloured by its error; I8 navigation events on the track; I12 a map and a 3D view side by side on one time
(the live page now does this by itself when the tab has both).

---

## 7. When you stop

Update the Status box at the top (stage reached, code map of what you built – file / function names, what
is left), the board, decisions and Log in `TASKS.md`, and make the patch as described. If you stop in the
middle of a task, say exactly where (file, function, what is half-done) so the next agent can continue cold.
