# Roadmap

Audience: flight-test / drone engineers and simulation engineers (MATLAB and Python).
Rules for every task: see `/CLAUDE.md`. Tick `[x]` only when "Done when" is met.
The order of work and the detailed specs are in `TASKS.md` (the work queue).

---

## Milestone 1 — 1.1.0: fixes, file finding, cleaner screen

- [x] **T01 Decimation outside the data range** — *re-assessed: not a bug.*
  `decimate_for_view` deliberately keeps coarse context on both sides of the window (so
  panning never blanks and lines reach the edges). Clipping it would have broken panning.
  Done: behaviour documented in the docstring + `test_decimation_keeps_context_outside_the_window`.

- [x] **T02 Faster, safer folder listing**
  `list_dir` calls `stat()` twice per entry; drive listing on Windows probes A–Z with
  `os.path.exists`, which can hang on a disconnected network drive. Stat once; list drives
  with `GetLogicalDrives` (ctypes) and never touch them.
  Done when: test for listing; no behaviour change in the browser.
  Done: `_windows_drives` (bitmask, never touches a drive), `_entry` stats once;
  `~` is expanded in typed paths. Test: `test_fs_list_and_complete`.

- [x] **T03 Path autocomplete in the file browser** (user request)
  New `POST /api/fs/complete {text, exts}` → folders/files whose names start with the
  last path segment (case-insensitive on Windows), max 50, folders first.
  UI: dropdown under the path box while typing (debounced), ↑/↓ + Enter to choose,
  **Tab completes** the longest common prefix, a chosen folder continues completing
  (`C:\Us` → `C:\Users\`), a chosen file selects it. Also:
  - typing while the list has focus filters the current folder (type-to-filter);
  - clickable breadcrumbs above the list (each segment opens that folder).
  Impact: FileBrowser is shared by open / save / folder pickers (`pickPath`) — all three
  must keep working; folder mode lists folders only; RTL; Hebrew strings.
  Done when: backend tests for complete; manual check in all three picker modes.
  Done: `/api/fs/complete`; dropdown (combobox, ↑/↓/Enter/Tab/Esc), breadcrumbs,
  type-to-filter (first Esc clears the filter, the second closes). A lone letter is a
  drive only when no folder is shown. Found by the e2e test: a filtered-away row took the
  focus with it - the dialog now keeps the focus. Tests: backend + e2e
  `test_file_browser_autocomplete`; open / save / folder pickers covered by the existing
  e2e files (all green, run per file).

- [x] **T04 Investigate `/api/files/open` dropping the connection** when the server is
  started on its own (`uvicorn app.main:app`). Find the cause, fix, add a test.
  Done: *not a bug.* The server in that check had been started with `timeout 8` / in a
  shell that ended, so it was already gone. Started and called in one process, opening
  two files returns 200 with all signals. Existing tests already open files through the API.

- [x] **T05 One Follow control** — the "show last N seconds" select exists twice
  (Live settings popover and StageBar). Extract `<FollowSelect/>`; show it only in the
  StageBar while live (where it acts on the plots). Remove it from the popover.
  Done: removed from the Live settings popover; the StageBar select (live only) is the one place.

- [x] **T06 Two different "clear" actions, two different looks** — TopBar trash =
  "close all files" (asks first); StageBar trash = "clear plots of this tab". Give them
  distinct icons and labels; make "clear plots" undoable feedback (toast with Undo).
  Done: StageBar "Clear all plots" has its own eraser icon, a hint that files stay open,
  an Undo toast and a Ctrl+K entry. "Clear everything" keeps the trash and its confirmation.
  Found by the test: an old Undo toast undid the LATEST change. Toasts that undo the last
  workspace change (`undoesWs`) now go away on the next change / undo / redo, and the same
  message replaces the previous one instead of stacking.

- [x] **T07 Packaging and tests run from anywhere** — `pyproject.toml` with pytest
  `pythonpath = backend`, so `pytest` works from the repo root; silence the httpx warning.
  Done: `pyproject.toml` (pytest `testpaths`/`pythonpath`). The httpx warning is not
  silenced: `requirements-dev.txt` already installs `httpx2`, which removes it.

- [x] **T08 Inspector starts closed** and opens by itself the first time a signal chip is
  selected or the cursor is turned on. The user's own open/close choice is remembered
  (localStorage) and then wins. Impact: e2e S04/S05 click a chip first → still open.
  Done: `sv3.inspector` in localStorage (UI state, not in sessions); the cursor / dual
  cursor open it unless the user closed it; a chip click always opens it. e2e test added.

- [x] **T09 "Open an example" on the welcome screen** — bundle `examples/` in the
  PyInstaller spec, `GET /api/examples`, buttons on the welcome card (flight + car runs).
  Done: `GET /api/examples` (missing files left out; `SV_EXAMPLES` for the exe, set in run.py;
  examples bundled in the spec). Welcome line with two links that use `openPaths`. Tests: backend + e2e.

- [x] **T10 Flight segments** - any state signal (flight mode, gear, a text column), not only
  flight logs, so it lives in the Inspector (properties of the selection) when the signal is
  shown as states: total time per value + the list of segments. A row calls the existing
  `showSpan` (zoom + both cursors), so the existing "Between cursors" statistics are the
  per-segment statistics - no second mechanism. Backend: `/api/segments`; the stretch logic was
  moved out of `/api/stats` into `_stretches` and is shared by both. Tests: backend + e2e.
- [x] **T10b Same segment across runs** (e.g. the 2nd AUTO of every open flight, side by side
  in the comparison table).
  Done: `segment_windows` + `POST /api/segments/across {runs, state, value, occurrence}` (1-based,
  -1 = last) on the existing `_stretches`. `/api/compare` and `/api/compare/all` take optional
  `windows {runId: [t0, t1]}`: `_windowed` cuts each signal to its run's window and puts it on
  time since t0, so `compare_runs` and the per-file statistics work unchanged. UI: Compare runs >
  "Compare over: The whole runs | A segment" (state signals shared by >= 2 chosen files, value
  with its text, occurrence), per-file window list; only files with the segment take part.
  `segments.ts` `showSegmentPlot`: the files' lines with the existing per-signal `tOffset` =
  -t0, in a tab named after the segment, x range [0, longest]; used by the list and the table.
  "Plot differences" and "align in time" are hidden in segment mode (both work on absolute
  time). Tests: backend `test_segments_across.py`; e2e `test_compare_same_segment_across_runs`.

- [x] **T11a Python API and command line** (MATLAB and Python users)
  `import signalviewer as sv; rec = sv.load(path)` -> `.signals`, `.signal(name)` (numpy),
  `.table()` / `.to_dataframe()` (one time base, same rule as Export CSV, reuses `align_to`).
  `python cli.py info FILE [--json]`, `python cli.py export FILE --out x.csv|x.mat
  [--signals a,b --t0 --t1]`; MATLAB: `system(...)` + `load`. Reuses `Store.open_file`, so
  every format and its auto-detection behave as in the app. Loader prints go to stderr so
  `--json` stays parseable. Tests: `backend/tests/test_cli_api.py`.
- [x] **T11b Batch reports from a template** (`cli.py report --template T --out DIR files…`).
  Needs the template matching (`autoBind` / `applyTemplate`, now only in `templates.ts`)
  in ONE place: move it to the backend, have the UI call it, then the CLI uses the same code.
  Not duplicated in Python on purpose (CLAUDE.md: one way to do a thing).
  Done: `svcore/templates.py` is the one implementation of name matching, `expand`, `auto_bind`,
  `fit`, `slot_report` and `resolve` (a template's tabs with real signal ids; colour None = the
  caller picks). Pinned to the old TypeScript answers: `tests/data/template_matching_ts.json`
  (208 cases recorded from `templates.ts` before the move) + `test_template_matching.py`.
  Built-in templates are data now: `svcore/builtin_templates.json`, sent with `GET
  /api/templates` (`builtin`) and bundled in the spec. API `/api/templates/fit|bind|resolve`;
  the UI (TemplateStrip, TemplateLibrary, `applyTemplate`, now async) calls them. Kept in the UI:
  capturing tabs as a template, `expand` / `slotNames` / `includers` for showing a template's
  structure, and the three generators (their tabs go to `resolve` as `extraTabs`; the objects
  generator's fit stays in the UI because it uses `guessRoles`). Batch: `app/batch.py`
  (fresh `Store` per file, `auto_bind` + `resolve` + `fill_colors` -> report specs like
  `plotSpec.ts`, the same `report.build_*`), `cli.py report` / `cli.py templates`. Generator
  templates are refused with a message (their tabs come from what the app shows). Tests:
  `test_template_matching.py`, `test_batch_reports.py`; template e2e files all green.

### Found while working
- [x] **F03 3D measure test broke after T08** - not an app bug: with the Inspector closed the 3D
  view is wider, Cesium's field of view then shows less height, and one of the test's two fixed
  places fell below the canvas. The test now zooms out until both are on screen (a ground
  distance does not depend on zoom). CLAUDE.md: run every e2e file after a layout change.
- [x] **F01 Blank window with a POSIX locale** (`en-US@posix`, `C`): uPlot builds
  `Intl.NumberFormat(navigator.language)` at load and throws. `localeGuard.ts` (first import)
  normalises the tag. Verified with Node: those tags throw, `en-US` does not.
- [ ] **F02 Whole e2e suite hangs when run in one process** (every file passes on its own).
  Narrowed down: the same files hang only when pytest runs detached from a terminal
  (background / nohup) in the build sandbox; in the foreground every file passes. Check on a
  developer machine / CI before changing the fixtures.

## Milestone 2 — 1.2.0: flight-test tools
- [ ] **T12 Live MAVLink** (UDP / TCP / serial) as a source, next to file following.
  Works with SITL too. *Implemented, waiting for the SITL / radio check (see TASKS.md Q1).*
  `svcore/mavlive.py` `Receiver`: pymavlink connection (MAVLink 2, robust parsing,
  autoreconnect) in a thread; every frame is written as a .tlog record (8-byte BE µs + frame,
  batched ~5×/s) to `~/.signalviewer/recordings/mavlink-<date>-<time>.tlog`. No parser of its
  own: the UI (`mavlink.ts`) opens the file with `openPaths` once data is written and starts
  live mode, which reads it with the existing `append_tlog`. API `/api/mavlink/start|stop|
  status|ports`; one link at a time (409). Read-only unless `request` (GCS heartbeat 1 Hz +
  one REQUEST_DATA_STREAM ALL). UI: section in the Live popover (open state moved to the store
  `liveMenuOpen` for Ctrl+K), pill next to Live. New dependency pyserial (serial radios, pure
  Python); PyInstaller hidden imports for pymavlink.mavutil / serial. Tests: backend
  `test_mavlink_live.py` (fake vehicle over UDP: record, open, follow, reopen; read-only vs
  request; errors); e2e `test_live_mavlink`.
- [x] **T13 Limits (pass / fail)** - optional `limits {lo, hi}` on a plot signal (workspace ->
  undo, sessions, autosave; saved in templates and applied with them). Checked on the plotted
  value (scale, offset, time offset) by `svcore/limits.py` / `/api/limits`: violations, time
  outside, worst excess. Inspector: two fields + result; a violation row -> `showSpan`. Chart:
  dashed lines in the signal colour. Reports: a Limits column (pass / fail) in HTML, PDF and
  Word through one helper, only when a signal has limits. New theme colour `--ok`.
  Tests: backend (check, API, all three report formats) + e2e.
- [x] **T14 Monte-Carlo view** - plot mode "Envelope" (`env`): the plot's signals (one
  quantity from many runs - "Link files" adds it from all of them) on one time grid over their
  overlap: min-max, 5-95 % band, median (`svcore/envelope.py`, `/api/envelope`; scale, offset
  and time offset as plotted; between the cursors when both are on). Outliers: the biggest
  (> 3x) jump in the ranking of the runs' RMS distance from the median - ratios to the median
  distance flagged ordinary runs in testing (those distances are skewed). Own component
  `EnvelopeChart` (TimeChart untouched). Tests: backend (bands, one / two / no outliers) + e2e.
- [x] **T14b Envelope in reports** - the report computes the envelope with the same
  `svcore/envelope.py`: matplotlib `fill_between` (PDF, Word, images), uPlot bands in the HTML
  viewer (`viewer.js`), and the summary (runs, band, outliers named) as the plot's caption in
  every format and language. Found by the test: `_collect` dropped plots without `signals`, so
  the PDF / Word left the plot out while returning 200 - now checked by reading the PDF back
  (`pypdf`, tests only). Checked in Chromium: the HTML report draws it with no script errors.
- [ ] **T14c** Zoom of an Envelope plot is its own (not linked with the tab's time plots).
- [ ] **T15 Video synchronised to the timeline** (local file, offset by a cursor pair).
- [x] **T16 Vibration: Welch PSD** - FFT plots get "Spectrum: FFT | Welch PSD" (averaged power
  spectral density, units²/Hz, ~8 pieces with 50 % overlap). New optional plot field
  `fftMethod` (absent = fft, so old sessions/templates are unchanged), carried everywhere
  `fftWindow` goes: plot, FFTChart, api, template save + apply, plotSpec, report (PSD scales
  with scale²), server. Test: `test_welch_psd_finds_the_tone_and_is_smoother`.
- [x] **T16b Motor-order marks** on spectra (needs the RPM / ESC signal chosen per plot).
  Done: optional plot field `fftOrders {sig, unit: rpm | hz, blades?}`; FFT controls get a picker
  of the plotted files' rotation signals (`ORDER_NAME`: rpm, ESC rpm / erpm, motor / rotor / prop
  speed; unit rpm when the name says so) and a blades select. `FFTChart` takes the signal's mean
  over the spectrum's window from `/api/stats` and draws 1x / 2x / 3x (+ blade pass) with a
  uPlot draw hook; `data-orders` on the canvas holds the base frequency. Not in reports or
  templates yet (the report's FFT has no marks). e2e `test_fft_motor_orders`.
  `q2roll` / `q2pitch` / `q2yaw` (Hamilton w-first quaternions, aerospace order, degrees).
  In the server list and in `formulaHelp.ts` (suggestions while typing; the sync test enforces
  both). Test: `test_formula_angles_and_quaternions`.
- [x] **T17b Frames NED / ENU / body / ECEF / LLA** - Create signals > "Frames": three components
  in, three derived signals out. Design: operation `frame` with `params.axis` 0 / 1 / 2 - one
  output axis per derived signal, so sessions, autosave, restore and live recompute need nothing
  new (old files unchanged). `params.qty` separates the two kinds of maths:
  - "vector" (velocity, acceleration...): rotation only. NED / ENU / body / ECEF. Body needs the
    attitude (body -> NED as PX4 / ArduPilot log it): roll / pitch / yaw (deg or rad, same
    convention as `q2roll`...) or a w-first quaternion (normalised). ECEF needs the vehicle's
    lat / lon per sample (north depends on where you are). Never a reference point.
  - "position": LLA (WGS84 ellipsoid, iterative inverse) / ECEF / NED / ENU. NED / ENU are
    metres from a reference point: `ref` "first" (first valid sample - only from LLA / ECEF) or
    "manual" (`ref_lat`, `ref_lon`, `ref_alt` above the ellipsoid). NED <-> ENU needs none.
    Body is refused (not a place).
  Aligned onto the first component's samples; yaw and longitude are unwrapped and quaternion sign
  flips removed BEFORE interpolating (otherwise a sample between 179 and -179 deg points the
  wrong way / a track across the antimeridian sweeps the globe). Kind tabs wrap in a narrow
  panel. Tests: `test_frame_*` (8, backend) + e2e `test_frame_conversion`.
- [x] **T17c Plain 3D plot (XYZ) + place on map** - plot mode "XYZ": the plot's signals in threes
  (X, Y, Z, ...), any units, nothing geographic. Y / Z aligned onto X's samples by the server
  (`svcore/xyz.py`, `/api/xyz`). Drawn on a 2D canvas with its own orthographic camera
  (`XYZCanvas` - no new library): back walls with grid and ticks, the track's shadow on the floor,
  start mark, the cursor's point with a drop line, values at the cursor; drag rotates, Shift+drag
  moves, wheel zooms, double click resets; the timeline's draw / window modes apply. "Equal
  scale" (default, for positions) and "Z down" (NED down, depth). "Place on map": NED / ENU
  metres + an origin (first valid sample of lat / lon / alt signals - the GPS of the track's file
  is guessed - or typed in) -> three derived `frame` signals per track (new `ref: "signals"`, also
  offered in Create signals > Frames) and a map object on an existing or new map / 3D plot.
  Reports: matplotlib 3D axes in PDF / Word / images, an image in HTML (viewer.js skips it).
  Found: `placePlot` treated a map plot with only objects as empty and could overwrite it.
  Tests: `test_xyz_*`, `test_frame_reference_from_signals` + e2e `test_xyz_plot_and_place_on_map`.
- [x] **T17d 3D view without WebGL** - Chrome / Edge 139+ no longer fall back to software WebGL
  (SwiftShader), so old / virtual / remote-desktop machines with a blocked or missing GPU driver
  get no WebGL at all and the 3D view showed only an error. Now it checks first (no CesiumJS
  download then) and shows the objects as tracks in metres east / north / up from the first
  position on the XYZ canvas, with a note. The Map plot never needed WebGL (Canvas 2D, offline
  tiles). e2e `test_globe_without_webgl_falls_back` (WebGL blocked by an init script).
- [x] **T17e `run.py` serves the current UI** - from the source folder, a fingerprint of the UI
  sources (paths + contents) is compared with the one stored in `frontend/.local-dist` (git
  ignores it); when they differ and `frontend/dist` is older than the sources (its index.html
  is not newer than every UI source file - a hand / CI `npm run build` is - and by git:
  uncommitted UI changes, or a UI commit after the last `frontend/dist` commit) it runs
  `npm ci` (only when needed) and `npm run build -- --outDir .local-dist` once and sets
  `SV_DIST`. Packaged app, an explicit `SV_DIST`, `--no-build` / `SV_NO_BUILD`: untouched; no npm:
  a message and the last build. Tests: `backend/tests/test_launcher.py`.
- [x] **T17f Frames as one nested group + preview** - the three axes of a conversion are
  created by `frames.ts` `createFrameGroup` (also used by "Place on map") as `<group>.<axis>`
  with `params.group` (default `<to>_<Pos|Vec>_<from>`, numbered `_2`… when taken, all or
  nothing). `signalGroups.groupDerived` nests them in the file list and the Create signals list;
  old sessions have no group and stay flat. Added to the plot with `actions.addSignals` (one
  undo step); group menu: all to the active plot / `addSignalsToNewPlots`. Preview: the store's
  `preview` holds several lines (`lines[]`, told apart by `PREVIEW_DASH`) in a time plot (the
  active one, else the tab's first), or with `separate` `PreviewPlots` shows a plot per line under
  the grid: TimeChart with `previewOnly` and index -1, not in `ws` (no undo, not saved). TimeChart
  also draws a preview in an empty plot. "Add the result to": active plot / a new plot each
  (`actions.addSignalsToNewPlots`) / none. Touches TimeChart (preview series), App (stage),
  DataPanel, AnalysisPanel, PlaceOnMapDialog. Tests: backend
  `test_frame_group_nested_names`; e2e `test_frame_conversion` extended.

## Milestone 3 — 1.3.0: smoother work
- [ ] T18 Settings dialog (language, theme, map layer, live defaults); language and theme
  leave the TopBar.
- [x] T19 Zoom mode by modifier keys (Shift = Y, Ctrl = XY); X/Y/XY moves to a menu.
  Done: TimeChart decides each drag's mode on mousedown (Shift y, Ctrl / Cmd xy, else the zoom
  mode) and writes it into `u.cursor.drag` (uPlot reads x / y / uni live); `gestRef` feeds
  `setSelect`. Pan moved from Shift + drag to **Alt + drag** (middle button still pans); wheel:
  Shift = values, Ctrl = both, Alt = time. StageBar: one zoom button (magnifier + mode) opening a
  menu with X / Y / XY and the keys. Help lists Shift / Ctrl + drag.
- [x] T20 One layout button (grid picker) instead of seven icons; split a plot by dragging a
  signal to its edge.
  Done: one `.layout-btn` (icon + "r × c"); `GridPicker` got the 7 common layouts on top (same
  aria-labels "Layout r × c"; e2e helper `set_layout`). Edge drop: PlotView `edgeOf` (end band
  min(48 px, 15 %), bottom band min(40 px, 15 %), RTL-aware) -> `actions.splitPlot` (new plot
  after it, grid +1 column / row when full, sizes reset; a chip is moved, Ctrl / Alt copies).
- [x] **F06 Middle click on a tab did not close it on Windows** (owner report): the tab strip
  scrolls, so a middle press started the browser's autoscroll and no `auxclick` followed. Now
  mousedown(button 1) prevents autoscroll and mouseup closes. e2e
  `test_middle_click_closes_tab_and_clear_selection_bar`.
- [x] **F07 List checkboxes nobody understood** (owner report): every row got a checkbox as soon
  as one typed in the search box. Now they show only while there is a selection; the search bar
  (`.pick-bar`, "N results · select all") is the way to select results. The selection bar:
  "N signals selected", "Plot them" (`actions.addSignals`, one undo step, was one per signal),
  "Change them…", "New signals from them…", and the Ctrl / Shift hint.
- [x] T21 Clearer names: Analysis → "Create signals", Compare → "Compare runs" (rail, panel
  titles, command palette; he: "יצירת סיגנלים" / "השוואת ריצות"). e2e selectors updated; the
  panel's button is now found by role, since "text=Create signal" also matched the new title.
- [ ] T21b Signal context menus: one "Create signal ▸" entry instead of repeated operations.
- [x] T22 Signal list: unit, sample rate and a sparkline per signal.
  Done: `Store.describe` adds `n` and `rate` per signal (`_rate_of`: length and the two ends of the
  signal's own time vector - O(1), also for wide files). `POST /api/sparks {signals, points}` ->
  min / max of equal slices (`store.spark`, spikes and NaN gaps kept), at most 200 per call.
  `sparks.ts` `useSpark`: rows on screen queue, one batched request after 60 ms, cache per signal
  + version (samples, change). Row: name without the unit (`unitOf`), unit badge, rate (container
  query: from 300 px panel width) and a 40x14 band; text signals get no picture. Measured: a
  352-signal list scrolls at 60 fps (p95 16.8 ms/frame). Tests: `test_signal_list_info.py`; e2e
  `test_signal_list_unit_rate_and_picture` (and only the visible rows ask).
- [ ] T23 Notes over a time range (shaded span), listed in reports.
- [ ] T24 Favourite folders and quick open (Ctrl+P, fuzzy over recent folders).
- [ ] T25 Sim-vs-flight error signal with RMS per segment.
- [x] T26 Parameter diff between two logs. *Re-assessed: already there* - the Log panel's
  Parameters tab has a "differences from another file" filter.
- [ ] T27 Formats: MCAP (ROS 2), HDF5 (generic).
- [x] T29 Smart start: offer a fitting template when a file opens (built-in ArduPilot / PX4
  ones) and a short health summary with jump-to-time links. Spec: TASKS.md Q4.
  Done: `smartStart.ts` `offerStart` (from `openPaths`, only when the workspace had nothing
  plotted and no MAVLink link is recording): the backend fits (`/api/templates/fit`), ranked by
  `rankTemplates` (now shared with the library's first selection), suggested only at fit >= 0.5;
  for bin / tlog / ulg with a log, the health check's errors then warnings, at most 3. Store
  `startCard` (UI only). `StartCard.tsx` floats bottom-left over the plot area (no room taken
  from the plots); "Open it" = `api.bindTemplate` + `applyTemplate`, "Other templates…" opens the
  library on it. `HealthRow.tsx` extracted from the Log panel and shared. Built-in templates were
  already there (ArduPilot, MAVLink, PX4) - none added. Tests: e2e `test_smart_start_card`;
  all e2e files run (see TASKS.md log).
- [x] **F04 Opening in a folder with remembered import settings** (found by T29's e2e test, when
  it ran after the import-options test): `open_with_prefs` read `auto.run.load_report`, which only
  the CSV loader sets - a .bin / .tlog / .mat there opened and was ALSO reported as an error, so
  nothing after the open (toasts, the start card) ran. Now `LoadedRun.load_report` (all formats).
  Test: `test_open_remembered.py` (fails without the fix).
- [x] **F05 Template "Open" before the files were bound** (T11b made binding a server call):
  "Open" is disabled until the binding for that template and those files has arrived. Found by
  `test_object_templates.py` in the full e2e run.
- [x] T30 Frames: suggest the conversion and its signals from the names. Spec: TASKS.md Q10.
  Done: `frames.ts` `suggestFrames(run)`: LLA -> NED from `guessRoles` (the map's lat / lon /
  alt guess); NED velocity (VN/VE/VD, VelN.., vel_n.., x/y/z velocity of LOCAL_POSITION_NED /
  vehicle_local_position) -> body and body acceleration (AccX.., xacc.., acc_x..) -> NED, both
  with the attitude from `guessRoles` (Euler, else quaternion; unit from "[deg]" / "[rad]", MAVLink
  ATTITUDE = rad). Frames tab: the first suggestion fills the fields when they are empty, chips
  switch; without suggestions the old start (the active plot's signals) stays. e2e
  `test_frames_suggested_from_names`.
- [ ] T31 User Python operations from a local folder (decided: only a folder the user chooses).
  Spec: TASKS.md Q11.
- [x] T28 `worldCountries.ts` → JSON loaded with the map. *Re-assessed: already done* -
  GeoChart loads it with `import()` into its own chunk (not in the main bundle).

## Milestone 4 — 1.4.0: trust, robustness, reach
- [x] **F08 CI warned "Node.js 20 is deprecated"** (owner, manual build 2026-10-18):
  `upload-artifact@v4` -> `@v6`, `download-artifact@v4` -> `@v7` - the first majors on Node 24
  (checked each tag's action.yml; v5 / v6 of download-artifact are still Node 20). The inputs used
  (name, path, if-no-files-found, compression-level; path, merge-multiple) exist unchanged; the v5
  change (single artifact by id) does not apply to a merge-multiple download.
Spec and order: TASKS.md "Review 2026-10-17" (Q12–Q24).
- [x] T32 Licence file (MIT) + README section. Spec: TASKS.md Q12.
  Done: `LICENSE` (MIT, David Alpert); README badge + "License" section with the bundled parts'
  licences (uPlot, OFL fonts, Cesium, map data); installer licence page (`LicenseFile`);
  `LICENSE` in the PyInstaller build and the portable zip.
- [x] T33 Loaders survive damaged files (fuzz tests). Spec: TASKS.md Q13.
  Done: `tests/test_damaged_files.py` - 126 damaged copies (truncate / bit flips / zero block /
  junk / duplicated block, fixed seeds) of CSV, .mat v5, .mat v7.3, .bin, .tlog, .ulg: each opens
  or raises LoadError, within 10 s. Found and fixed: (1) CSV - an invalid UTF-8 byte that also
  breaks a row made Arrow's bad-row handler fail, then pandas failed on the same byte: 42 of 150
  damaged CSVs did not open at all. `_parse_pyarrow` now repairs ONLY a part that fails
  (`_repair_text_bytes`: drop NULs, invalid bytes -> U+FFFD) and reads it again; pandas gets
  `encoding_errors="replace"`; report `damagedText`. (2) `check_file` refused a CSV with a zero
  block in its first 4 KB as binary - now `_text_with_zero_block` (printable without the zeros).
  (3) .mat v5 cut off: `_read_v5_until_damage` keeps the complete variables; report `cutOff`; cut
  before the first one -> `badMat` saying so. Flight logs (.bin / .tlog / .ulg): no failure found.
- [x] T34 Review the broad `except Exception` handlers. Spec: TASKS.md Q14.
  Done: found that `ops.apply_filter` was a moving average and returned the RAW data on any
  failure (and for any type but low/high-pass) -> real zero-phase Butterworth (`sosfiltfilt`,
  median sample interval, NaN bridged and restored, short-signal padding) raising `FilterError`,
  turned into `OpError` / `FormulaError` (`tests/test_filters.py`, 15). ~500 dead lines removed
  from `ops.py` (Dash-era `apply_unary/binary/multi`, `align_two_signals`, `get_xy_plot_data`,
  `compute_psd`, `create_filtered_signal`). Every other silent handler narrowed to the expected
  errors (decimate, is_discrete, describe_derived, sparks, autosave, prefs, delimiter, drives) or
  kept broad AND logged with a comment why (live append fallback, restore, sync methods, bidi,
  templates folder, MAVLink close / heartbeat, PX4 defaults, live Arrow fallback). One logger
  tree, `signalviewer.*` - T38 attaches the file handler to it.
- [x] T35 Split `backend/app/main.py` into routers. Spec: TASKS.md Q15.
  Done: `app/main.py` 2,130 -> ~170 lines (app, local-only guard, JSON response, includes, static
  UI). `app/common.py` (paths, `b64`, `fail`, `open_with_prefs`, `_load_error`, log names) and
  `app/routes/`: files, live, data, analysis, compare, export, maps, jobs, system, templates, fs,
  session - one `APIRouter` each. Moved by an AST script (functions with their decorators and
  comments, cross-module imports computed; graph acyclic). Checks: OpenAPI (paths, methods,
  models) identical before / after; all 80 routes and the 14 pairs that can match the same request
  in the same order; the UI catch-all last. Found by the tests: `EXAMPLES` was built from
  `__file__`, now one folder deeper - fixed (the bundled app sets SV_EXAMPLES, source runs lost
  the examples). Guard: `tests/test_routes_layout.py`. `app.main` still exports `app`,
  `WATCHDOG`, `idle_too_long`, `_hostname` (run.py, tests).
- [x] T36 mypy for the backend in CI. Spec: TASKS.md Q16.
  Done: `[tool.mypy]` in pyproject.toml, a CI step (Linux), `mypy` in requirements-dev, the check
  in CLAUDE.md. 104 findings -> 0 with a baseline. Real bugs it found (tests in
  `test_prefs_damaged.py`, 9 - all fail on the old code): a settings file holding `null` / a list
  crashed remembering import settings (`prefs._read` now refuses the wrong shape); a template file
  of non-objects gave a server error (now "does not hold Signal Viewer templates"). Also: `Run`
  declares `load_report`, `_flightlog`, `_dataflash`, `_tlog` (were set from outside);
  `fail() -> NoReturn`; Pillow `Image.Resampling.LANCZOS`; local annotations for mixed dicts.
  Baseline: 12 modules x the error codes they have today (22 pairs) - a new kind of finding there,
  or any finding elsewhere, fails (checked with deliberate errors in both).
- [ ] T36b Shrink the mypy baseline (pyproject.toml overrides): mostly `Signal.time` Optional
  narrowed where mypy cannot follow (bin / ulog / tlog loaders), `analysis.py` frame maths.
- [ ] T37 CSV first open meets the 20M-row target. Spec: TASKS.md Q18.
- [x] T38 Local crash report. Spec: TASKS.md Q19.
  Done: `app/crashlog.py` - rotating `~/.signalviewer/logs/signalviewer.log` (1 MB x 4,
  `SV_LOG_DIR` overrides; tests use a temp folder) on the `signalviewer.*` logger tree (T34), a
  console copy of warnings, `sys.excepthook` / `threading.excepthook`; failed background jobs log
  their traceback; an unexpected error in a request answers 500 with a readable message (was "Internal
  Server Error") and is logged with the traceback. UI: `errorReport.ts` (window errors, unhandled
  promises, PlotBoundary) -> `/api/client-error` (20 per session in the UI, 50 per run in the
  backend). Help: "Copy error details" -> `/api/diagnostics` (version, packaged / source, OS,
  Python, the last ~48 KB of the log - covers the session that crashed). `app/version.py` (a test
  keeps it equal to build.bat). Tests: `test_crashlog.py` (7), e2e `test_error_details.py`.
- [ ] T39 Python API: push arrays into the open app. Spec: TASKS.md Q20.
- [ ] T40 Parquet, MF4, CAN + DBC. Spec: TASKS.md Q21.
- [ ] T41 Fleet view (index of many logs). Spec: TASKS.md Q22.
- [ ] T42 Split `store.ts` into slices. Spec: TASKS.md Q23.
- [ ] T43 Release & reach (signing, docs site, public benchmark). Spec: TASKS.md Q24.

## Later
- [ ] "copy as pandas code".
