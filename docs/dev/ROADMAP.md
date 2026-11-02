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
  (`C:\Us` → `C:\Users`), a chosen file selects it. Also:
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
- [x] **F09 run.py served an old UI after git rewrote frontend/dist** (found by T38's e2e test in
  the whole-suite run): `committed_dist_is_current` trusted file times first, and git checkout /
  pull / clone give files fresh times - a dist restored or cloned after newer UI sources counted
  as "built later". Git history decides now; file times only for local changes (a dist built by
  hand, edited sources); no git: trust the committed UI. Tests: `test_launcher.py` (the old code
  fails `test_git_history_decides_not_file_times`); e2e `test_error_details.py` passes with the
  old dist in place (run.py builds the UI).
- [x] **F02 Whole e2e suite hangs when run in one process** (every file passes on its own).
  Closed 2026-10-18 (Q17): not reproducible - the whole suite in ONE process, detached from any
  terminal, passed 152/152 twice; the single failure in an earlier run was F09 (an old UI served).
  Earlier "stuck" runs overlapped heavy work on a 1-CPU sandbox. `pytest tests/e2e` is documented.
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
- [x] **T14c** Zoom of an Envelope plot is its own (not linked with the tab's time plots). Done 2026-10-19 (Q56): the tab's range.
- [x] **T15 Video synchronised to the timeline** (local file, offset by a cursor pair).
  Done (2026-10-18): a plot MODE "video" (fits the grid, saved with the tab, in undo, left out of
  reports - no signals). `Plot.video = {path, offset}`, data time = video time + offset;
  `actions.setVideo / setVideoOffset`. Backend `app/routes/video.py`: `/api/video?path=` with its
  OWN Range handling (206 / 416 / suffix ranges; older Starlette sends the whole file and the
  player cannot seek), mp4 / m4v / mov / webm / ogv / mkv. `VideoView.tsx` (lazy): LOCKED - the
  cursor moves the video (> 0.04 s apart; while playing > 0.3 s), timeline playback plays it at
  `playSpeed` (<= 16x; faster it follows by seeking), the video's own play / seek moves the cursor
  (own seeks remembered so they do not echo back); "Line up..." unlocks so the video and the cursor
  can each be put on the same moment, "Lock here" sets offset = cursor - video time and locks; offset
  also typed; "No video at this time" outside the clip. Design note: with only a "Sync here"
  button the two were always coupled, so a new offset could never be set - found while writing
  the e2e test. Tests: `test_video.py` (backend, ranges, 10), e2e `test_video.py` (a real VP8
  clip made with ffmpeg; skipped without it). Not done: audio (muted, so autoplay is allowed);
  several videos stay independent plots.
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
- [x] T18 Settings dialog (language, theme, map layer, live defaults); language and theme
  leave the TopBar. Done 2026-10-20 (Q34): theme, text size, time format in Settings; the language
  stays a top-bar button and live choices stay in Live (one place each), all kept in ui_settings.json.
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
- [x] T21b Signal context menus: one "Create signal ▸" entry instead of repeated operations.
  Done: menus get submenus (`MenuItem.items`; `ContextMenu` opens one on hover, click or the arrow
  toward it - ArrowLeft in Hebrew; beside its item, the other side / higher when out of room). One
  builder, `createSignalMenu.ts` `createSignalItem(sig, plotId?)`, used by the file list's and the legend's
  menus (each had its own Derivative / Integral code): Derivative, Integral, "Other operations…" -> the
  panel through its existing `analysisSeed`. e2e S06 updated, new
  `test_create_signal_submenu_from_the_file_list`; en + he checked by screenshot.
- [x] T22 Signal list: unit, sample rate and a sparkline per signal.
  Done: `Store.describe` adds `n` and `rate` per signal (`_rate_of`: length and the two ends of the
  signal's own time vector - O(1), also for wide files). `POST /api/sparks {signals, points}` ->
  min / max of equal slices (`store.spark`, spikes and NaN gaps kept), at most 200 per call.
  `sparks.ts` `useSpark`: rows on screen queue, one batched request after 60 ms, cache per signal
  + version (samples, change). Row: name without the unit (`unitOf`), unit badge, rate (container
  query: from 300 px panel width) and a 40x14 band; text signals get no picture. Measured: a
  352-signal list scrolls at 60 fps (p95 16.8 ms/frame). Tests: `test_signal_list_info.py`; e2e
  `test_signal_list_unit_rate_and_picture` (and only the visible rows ask).
- [x] T23 Notes over a time range (shaded span), listed in reports. Done 2026-10-20 (Q31): two cursors + N.
- [x] T24 Favourite folders and quick open (Ctrl+P, fuzzy over recent folders). Done 2026-10-19 with the extension below.
- [x] T25 Sim-vs-flight error signal with RMS per segment. Done 2026-10-20 (Q32): Create signals > Two signals, /api/error-segments.
- [x] T26 Parameter diff between two logs. *Re-assessed: already there* - the Log panel's
  Parameters tab has a "differences from another file" filter.
- [x] T27 Formats: MCAP (ROS 2), HDF5 (generic).
  Done 2026-10-18: `svcore/mcap_loader.py` (mcap + mcap-ros2-support, MIT, Foxglove, pure Python;
  lz4 / zstandard for compressed chunks): read record by record with `StreamReader` (the
  library's message iterator reads and SORTS everything first, so a damaged end lost the whole
  file - found by the cut-off test); decoders per channel, bulk types skipped BEFORE decoding;
  `_flatten` (ROS time -> seconds, text -> state labels, arrays <= 16, blobs listed); log_time from
  the first message. `svcore/hdf5_loader.py` (h5py): own walk object by object (h5py's visititems
  raises RuntimeError on the first damaged object - found by the damaged-files test, 48 cases now
  in it); main time = the root group's, else the one fitting the most signals (not the longest - the
  first version left a 10 Hz table without time next to a 100 Hz sensor). `check_file`: HDF5 and
  MCAP signatures (HDF5 was taken for ".mat with the wrong extension"). Live mode: read again when
  the file has settled. UI: DATA_EXTS, ROS 2 / HDF5 badges, report notes. Tests:
  `test_mcap_hdf5.py` (9), the damaged-files test. New dependencies: mcap, mcap-ros2-support,
  lz4, zstandard (requirements.txt says why).
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
- [x] T31 User Python operations from a local folder (decided: only a folder the user chooses).
  Done 2026-10-18 - backend: see TASKS.md Q11 (worker process, timeout / crash recovery, op "py").
  UI: `PyOpsSection.tsx` in Create signals (kind "Python"): the operations with their description,
  parameters typed by their defaults (number / text / checkbox), source pickers by `inputs`
  (1: Signal, 2: A and B, more: the multi picker), the folder (path as LTR inside RTL), Reload,
  Open folder, Make an example, Change folder / Default folder, the files that did not load.
  Tests: backend `test_pyops.py` (10), e2e `test_pyops.py`. Checked in Hebrew by screenshot
  (fixed: the description and errors are LTR text, a SyntaxError named its line twice).
  Spec: TASKS.md Q11.
- [x] T28 `worldCountries.ts` → JSON loaded with the map. *Re-assessed: already done* -
  GeoChart loads it with `import()` into its own chunk (not in the main bundle).

## Milestone 4 — 1.4.0: trust, robustness, reach
1.4.0 (2026-10-18) shipped T32-T36, T38, F08, F09; the open items here continue toward 1.5.0.
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
- [x] T36b Shrink the mypy baseline (pyproject.toml overrides): mostly `Signal.time` Optional
  Done 2026-10-18: the baseline is GONE (12 module overrides, 39 hidden findings -> 0). None was
  a real bug - each was a value the code knows is set where mypy cannot follow; narrowed with an
  `is None` branch, a type, or an assert for an invariant (frames: R_nb / R_ne exist when body / ECEF is
  converted). Also clearer: `fft_display` returns Optional peak (it always could; callers handled it),
  `_refresh_derived` returns (t, y), `transitions` no longer reuses `lo` as int then float,
  `_main_boot_arrays` returns None before any frame. backend 642, mypy clean with no overrides, e2e
  subset (frames, FFT, derived, templates, logs) 15.
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
- [x] T39 Python API: push arrays into the open app. Spec: TASKS.md Q20.
  Done 2026-10-18: client `backend/signalviewer/push_client.py` (one file, numpy only;
  `show(t, {name: y})`, `show(t, y)`, `show(df)`, `show(None, ...)` = sample numbers; checks
  lengths before sending; "not running" when push.json is missing). Server `app/push.py` +
  `routes/push.py`: POST `/api/push?name&replace&plot` with header `X-SV-Token` (hmac compare;
  token from `secrets`, new each start), body .npz read with `allow_pickle=False`; time sorted
  if needed; `store.add_pushed` - the same name keeps its run id (plots, derived signals follow by
  version). `run.py` writes `~/.signalviewer/push.json` {url, token, pid} 0600 after the server
  starts and removes it at exit only if it is still its own. Events `/api/push/events?since`
  with their age: the UI asks every second, refreshes runs + `dataVersion`, puts a NEW run in the
  active plot (up to 8 signals) with a toast; on its first ask only events < 10 s old count (so
  data sent while the page loaded is shown, and a page reload does not plot old pushes again -
  the first design skipped them all, found by the e2e test). Pushed runs: F5 skips them, live
  mode ignores them, reload says "send it again". "Save the Python client..." copies the file
  (bundled as data in the PyInstaller build: modules are archived there). Tests: backend
  `test_push.py` (8, the real client against the app on a real port), e2e `test_push.py`.
- [ ] T40 Parquet, MF4, CAN + DBC. Spec: TASKS.md Q21.
  Parquet done 2026-10-18: `svcore/parquet_loader.py` (pyarrow): time = the chosen column, else the
  pandas index (from the file's pandas metadata), else a time-named column, else the first
  timestamp column; date-times -> seconds from the first; dictionary / text -> states (<= 1000
  values); lists / structs listed as left out; sorted by time; signature PAR1. Tests:
  `test_parquet.py` (5), 24 damaged copies in the damaged-files test.
  CAN + DBC and MF4: WAITING FOR THE OWNER - licences (2026-10-18): cantools is MIT but requires
  python-can (LGPL-3.0-only); asammdf (MF4) is LGPLv3+ with heavy dependencies. Options: (A) use
  them, bundled with LGPL compliance (licence texts, source, replaceable); (B) our own DBC decoder +
  candump / ASC readers (MIT; cantools only in tests as a reference) and MF4 only when the user
  installs asammdf; (C) both optional (pip install), nothing LGPL in the installer.
  -> 2026-10-18: the owner POSTPONED CAN / MF4.
- [x] T41 Fleet view (index of many logs). Spec: TASKS.md Q22. Backend: see TASKS Q22.
  UI done 2026-10-18: `FleetPanel.tsx` (rail "Fleet", lazy; also in the command palette): folders
  (Add -> built-in folder picker -> a job via `followJob`, the jobs bar shows it; Update all;
  remove), search (text, level, finding by the health titles, a number above / below), the list
  (date - * when from the file -, name, error / warning badges, the number), a row opens to vehicle,
  firmware, duration, modes and the findings in the Log panel's own words with **Open here**
  (opens or reuses the file, cursor at the finding, Log panel). Trend: a small SVG of the chosen
  number by date, the limit dashed, points over it red, click -> open. `files.ts` `followJob`
  (runJob's loop for jobs other endpoints start). e2e `test_fleet.py`. Hebrew checked by
  screenshot (fixed: the intro's extension list in RTL, "1 flight" wording).
- [x] T42 Split `store.ts` into slices. Spec: TASKS.md Q23.
  Done: `store.ts` -> `frontend/src/store/` (model, types, slices/{workspace,data,view,live,ui},
  state, selectors, inspector, actions/{plots,layout,view,notes}); `store.ts` re-exports it (no importer
  changed). Mechanical: cut by line ranges with a script; every action line identical, all old exports
  kept; comment fixes only (geoBase / compareTable carried other fields' comments). CLAUDE.md points
  to the new layout. tsc, build, whole e2e suite (158) green. Found on the way: F12.
- [ ] T43 Release & reach (signing, docs site, public benchmark). Spec: TASKS.md Q24.

## Milestone 5 — 1.6.0: examples, fixes, cleaner code (released 2026-10-18)
v1.5.0 was tagged 2026-10-18 on T41 (T15, T27, T31, T39, T40 Parquet, T41) without the release
patch; 1.6.0 releases properly. Order and specs: TASKS.md "Plan 2026-10-18". In 1.6.0: F10, T44,
T45, F11, T42, F12, T36b, T21b (above / below).

## Milestone 6 — 1.7.0: usability
The open T24, T23, T25, T14c, T18 above (TASKS.md Q30-Q34; moved from 1.6.0 by the owner).
- [x] **F10 Examples missing from the Windows portable package**. Spec: TASKS.md Q25.
  Done: `make_windows_portable.py` copies `examples/` to `app/examples` (where `routes/fs.py`
  looks from source) and checks every file is in the package. Test
  `test_every_example_ships_in_every_package`: the files of `EXAMPLE_SETS` exist and both packagings
  (portable script, PyInstaller spec) ship `examples/` - fails without the fix. Not run here: the
  portable build itself (python.org is not reachable from this sandbox) - the owner's next build shows it.
- [x] **T44 Example: two flights of the same mission**. Spec: TASKS.md Q26.
  Done: `tools/make_demo_data.py` `uav_flight(..., wind=...)` - with wind=None the original
  `uav_flight.csv` is byte-identical (tests and README media use it); `uav_flight_windy.csv`: 9 m/s toward
  the east, per-leg drift smoothed and faded in after the climb (an earlier version took the drift
  from the track at hover speed - roll / yaw spikes at take-off), crab angle, gusts on roll, heading
  held while slow, drain 2.6 V, take-off 12 s later. `EXAMPLE_SETS` "twoFlights"; a set is offered only
  when ALL its files exist (a half set would be wrong). UI: `ExampleId` in api.ts, a label map in
  App.tsx (tsc enforces a label per id), en + he. Tests: backend
  `test_two_flights_example_is_ready_to_compare`, e2e `test_open_the_two_flights_example`; Hebrew line
  checked by screenshot (fits one line).
- [x] **T45 Example: an ArduPilot .bin flight**. Spec: TASKS.md Q27.
  Done: `tools/make_example_bin.py` (called by `make_demo_data.py`; deterministic, 1.0 MB, 246 s):
  a point-mass quad model at 25 Hz - tilt from acceleration + drag in a 3 m/s westerly, the attitude
  following the desired with lag, quad-X motor mix, current from throttle, 4S battery; FMTU as the
  firmware writes it (that is how F11 was found). Ein Gev, 2026-09-14 06:30 UTC by GPS time. Modes
  STABILIZE / ALT_HOLD / LOITER / AUTO (5 waypoints, "Reached command #n") / RTL / LAND, EV
  ARMED / LAND_COMPLETE / DISARMED. Planted: vibration 137-143 s mid-leg (an earlier version put it
  in a turn), clipping, "Vibration compensation ON/OFF"; everything else healthy. Fixed on the way:
  yaw flicker at 0/360 (now parked at 35 deg), take-off pitch -25 deg (drag / accel limit). Guards
  in the generator: the mission ends before RTL, it lands before the log ends. `EXAMPLE_SETS`
  "ardupilot"; welcome title / hint and the empty-list hint name every format (were "CSV or MAT";
  the Hebrew hint without the extension list - bidi). Tests: backend
  `test_ardupilot_example_health_and_modes`, fleet `test_flight_date_of_the_ardupilot_example`, e2e
  `test_open_the_ardupilot_example` (smart-start card, template + warning). Checked by screenshot:
  the card, the Full review template, en + he welcome.
- [x] **F12 The Undo of "Delete all derived" could wipe later changes** (found while splitting
  store.ts - it was the only direct write of the workspace that was not deliberate): the toast kept its
  Undo after other changes and wrote the old workspace back directly (no undo step). Done: the toast is
  `undoesWs` (goes with the next workspace change, like the other Undo toasts) and the restore is a
  `commit`. e2e `test_delete_all_derived_undo_never_overwrites_later_changes` (fails without the fix;
  the change and the check in one call - toasts also leave by themselves after 4 s).
- [x] **F11 Fleet gave modern ArduPilot logs the FILE's date** (found by T45's example, written like
  real firmware): `flight_date` read only `GPS.GWk` / `GPS.GMS` in ms, but an instanced GPS with FMTU
  arrives as `GPS[0].GWk` / `GPS[0].GMS [s]` - the loader applies GMS's 1e-3 multiplier. The old test
  built the names by hand. Done: `_ap_field` finds a field under any instance / unit suffix (first
  instance), GMS scaled by its unit. Test: `test_flight_date_from_gps_time` (+ the real naming, a
  second receiver) and, with T45, the example's date. At the release (Q35): an index already holding
  such logs would keep the file date (a scan skips unchanged files) - `fleet.INDEX_VERSION` 2 in
  `PRAGMA user_version`; an older index marks its file-dated .bin rows stale, read again once. Test
  `test_an_index_from_before_f11_reads_its_bin_logs_again`.

## Milestone 7 — 1.6.1: polish (review 2026-10-18) — prepared 2026-10-19
Found by the review after 1.6.0 (TASKS.md "Review 2026-10-18"). Order there.
- [x] **F13 Templates without colours draw every signal in one colour**. Spec: TASKS.md Q36.
  Done: `colorAllocator(ws)` in `store/selectors.ts` (nextColor uses it) counts the colours it gives out, so a template's plots built before they are in the workspace get different colours; `applyTemplate` uses one allocator for signals and map objects. A plot holding the same signal from several files colours by FILE (its order among the open files), so a run keeps its colour in every plot of Compare open files. e2e `test_compare_open_files_gives_each_file_its_colour`.
- [x] **F14 First run: "templates folder is not available"**. Spec: TASKS.md Q37.
  Done: `prefs.template_folder_info()` makes the DEFAULT folder when it is missing (a first run had none until the first save); a folder the user chose is never created there, so a missing network / USB folder is still reported. Test `test_first_run_default_folder_is_available` (fails without the fix). The e2e of a fresh profile (Q51) will cover the screen.
- [x] **F15 Backend tests write to the real ~/.signalviewer; one app folder (SV_HOME)**. Spec: TASKS.md Q38.
  Done: the app folder is defined once (`prefs.APP_DIR`; common, store's uploads, tiles take it from there - store and tiles had their own `expanduser`). `tests/conftest.py` points HOME / USERPROFILE (and SV_CACHE_DIR) at a temporary folder before the app is imported, as the e2e servers already did. Test `test_app_folder.py`: no app path under the real home, every module under the one folder. Checked: a whole backend run with no ~/.signalviewer leaves none behind.
- [x] **F16 Compare runs: angles without 0/360 wrapping**. Spec: TASKS.md Q39.
  Done: `svcore/compare.py`: `angle_period(name, values)` - unit deg / rad (not deg/s, degC) AND named like a direction (yaw, heading, hdg, course, cog, bearing, azimuth, psi, track, direction) or sweeping 3/4 of a turn; for an angle the series are unwrapped before resampling (no 359 -> 1 step through 180), differences wrapped to ±half a turn, the mean baseline is the circular mean, range / correlation on the unwrapped shape, the result carries `angle`. The example's yaw: RMS 75.8 -> 21.8, max 315 -> 68.4. Tests `test_compare_angles.py` (detection, across north, circular mean, the example, other signals unchanged).
- [x] **F17 Plot options menu does not close (Esc / click outside)**. Spec: TASKS.md Q40.
  Done: `PlotView.tsx`: the ⋯ menu closes on Esc (focus back to ⋯), a mouse-down anywhere outside it, the window losing focus; the close-on-mouse-leave is gone; the first item takes the focus. It was the only hand-made menu left (`grep 'className="menu"'`). e2e `test_plot_menu_closes_like_every_menu`.
- [x] **F18 File dialog keyboard focus (Esc, Tab)**. Spec: TASKS.md Q41.
  Done: one watcher for every modal dialog, `ModalFocus` in `Overlays.tsx` (mounted once in App): a new `.scrim > .dialog` (MutationObserver) takes the focus unless a field inside already has it, Tab / Shift+Tab cycle inside the top dialog (a picker over another dialog is the top), on close the focus returns where it was. Probed: file dialog, templates, help, the confirmation dialogs (Templates and Clear everything had the same problem). The StageBar popovers (layout, zoom) close on Esc wherever the focus is. e2e `test_dialogs_take_the_keyboard`.
- [x] **F19 An open file opens again silently**. Spec: TASKS.md Q42.
  Done: `openPaths` (files.ts) splits the paths: a file already open (same path, case-insensitive, not a dragged-in copy) is read again from the disk (`api.reload`) and one toast says so with *Open another copy* (`openPaths(..., { copy: true })`); the rest open as before. Covers the dialog, recent files, Ctrl+P later and examples. en + he. e2e `test_opening_an_open_file_reads_it_again`.
- [x] **F20 Several files at once: one-file suggestion, a toast per file**. Spec: TASKS.md Q43.
  Done: `openPaths` passes the number of files opened to `offerStart`; with 2+ the card offers the built-in Compare open files (`generator: compare`) - header "Opened: N files", line "the same signals of every file, side by side"; one file: as before. The reading notes are grouped: one toast per distinct note, naming the files (or "N files"); `textColsRead` says "text read as states: DriveMode" (no more "1 text columns"). en + he. e2e `test_several_files_at_once_suggest_compare`.
- [x] **F21 File dialog: Shift range, Ctrl+A, last folder per purpose**. Spec: TASKS.md Q44.
  Done: `FileBrowser.tsx`: Shift+click = the range from the last clicked file in the order shown, Ctrl+click toggles one, Ctrl+A = every file shown (after the filter); the last folder is kept per use (`sv3.lastDir` for data - unchanged, `sv3.lastDir:<mode>:<exts>` for each picker); a use with no folder yet starts in the folder of the last opened file, then the data folder, then the newest recent file's folder, then home. e2e `test_file_dialog_range_select_and_own_folders`.
- [x] **F22 Many tabs: the hidden tabs cannot be reached** (owner). Spec: TASKS.md Q52.
  Done: `TopBar.tsx`: the strip in `.tabs-wrap` with "+" and an "All tabs (n)" button (`.tabs-all`, shown when the tabs overflow - ResizeObserver) that lists every tab (✓ the active); the active tab `scrollIntoView` on every switch; wheel over the strip scrolls it (RTL sign); `actions.cycleTab` on Ctrl+PageUp / PageDown and Ctrl+Tab (App.tsx; Help row); palette "Go to tab: …" per tab; CSS: the strip shrinks, the right-side controls do not, the search box keeps 150 px; ContextMenu: a menu of more than 14 items without submenus scrolls (`.menu.ctx.long`). en + he; checked in Hebrew by screenshot. e2e `test_every_tab_is_reachable_with_many_tabs`.

## Milestone 6b — 1.7.0 additions from the review — in 1.7.0 (prepared 2026-10-19): all but T49 part 2; T50 mostly
- [x] T24 extended: places in the file dialog (recent folders, favourites, open files' folders). Spec: TASKS.md Q30+.
  Done 2026-10-19: `routes/fs.py` `GET /api/fs/places` (folders of the open files, favourites,
  recent folders from recent.json - `prefs.recent_folders`, home / desktop / documents / downloads
  incl. OneDrive and Hebrew folder names, drives from the OS bitmask / `/Volumes` `/media` `/mnt`)
  and `PUT /api/fs/favourites` (the whole ordered list, `settings.json` `favouriteFolders`, max 30);
  `/api/fs/list` also returns `hidden` (files of other types). `FileBrowser.tsx`: a places column
  (hidden under 720 px; a recent folder already listed as open / favourite is not repeated), ★ in
  the path bar pins / unpins the folder shown, × unpins, drag reorders; an empty folder says so and
  how many other files it holds. Ctrl+P = quick open in the palette (`paletteMode: "open"`):
  favourites, recent files, recent folders; a folder opens the dialog there (`browserStart`).
  Tests: `test_places.py`; e2e `test_file_dialog_places`, `test_file_dialog_recent_folders_and_empty_folder`, `test_quick_open`.
- [x] T46 File identity: colour + short tag per file, colour by file. Spec: TASKS.md Q45.
  Done 2026-10-19: `store.py` `Store.mark / set_mark` (tag A.., colour from FILE_COLORS, by id),
  in `describe`, `PATCH /api/runs/{id}` (tag, color), saved / restored with sessions; UI: tag in the
  file colour on the file header (click: colour picker; File options > Short tag…), on legend
  chips instead of the file name (tooltip: name + path), in the Inspector and the signal pickers;
  same-name signals from several files in a plot are coloured by file (`colorByFile`, shades),
  Plot ⋯ > Colour by file; Compare runs / Compare open files use the file colour. Left for later:
  map / 3D track colours and the report legend.
- [x] T47 Second value axis for different units. Spec: TASKS.md Q46.
  Done 2026-10-19: `PlotSignal.axis` "right"; TimeChart scale `y2` with its own unit label, cursor
  values and limits on it; chip menu to move a signal between the axes, a toast offering it when a
  signal in other units is added; reports: HTML (viewer.js), PDF / Word / images (matplotlib twinx).
  The value zoom, pan, limits and linked value axes stay on the left axis.
- [x] T48 First impression: examples open ready, one-click template chips. Spec: TASKS.md Q47.
  Done 2026-10-19: examples apply their suggested view (Undo to the empty plot), the start card
  keeps the findings after a view opens; chips open at once when every slot has a clear file
  (`openTemplateNow`), else the library; right-click a chip for the library.
- [ ] T49 Duplicate and unclear controls (13 items). Spec: TASKS.md Q48.
- [ ] T50 Small windows and crowded headers. Spec: TASKS.md Q49.
- [x] T51 Built-in templates in Hebrew. Spec: TASKS.md Q50. Done 2026-10-19: `tx()` / `BUILTIN_HE` in templates.ts.
- [x] T52 e2e "fresh user" with an empty profile. Spec: TASKS.md Q51. Done 2026-10-19: `tests/e2e/test_fresh_user.py`.

## Milestone 8 — 1.8.0: toward wide use (review 2026-10-19). Spec: TASKS.md Q53-Q63
- [x] F23 Statistics cache returns another signal's numbers (Q53). Done 2026-10-19: weak references to the arrays in each cache entry.
- [x] T53 Release assets: installer + zip on GitHub Releases (Q54). Done 2026-10-20: CI green on GitHub.
- [x] T54 Open files from outside: command line, file associations, one instance (Q55). Done 2026-10-19: app/instance.py, "open" push events, installer task "openwith".
- [x] F24 Linked time plots not lined up; spectrogram range (Q56, with T14c). Done 2026-10-19: column gutters (chartUtil `useGutter`).
- [x] F25 Menus clipped by the plot card (Q57, with T49 items 9, 12). Done 2026-10-19: the app's menu; type button; right-click menu.
- [x] F26 Shortcuts dialog describes the wheel wrongly (Q58, with T49 items 2, 13). Done 2026-10-19: File and Help menus.
- [x] F27 Mouse wheel on trackpads / sideways swipe (Q59). Done 2026-10-19: chartUtil wheelZoom.
- [~] T55 User guide and a 3-minute tour (Q60). Guide done 2026-10-19 (docs/GUIDE*.md, Help > User guide); the tour video: owner.
- [~] T56 PyPI package (Q61). Built and checked 2026-10-19 (tools/make_pypi.py, CI jobs); publishing after the owner's one-time PyPI setup.
- [x] F28 One time format (Q34, with T18). Done 2026-10-20: seconds as recorded by default.
- [x] F30 Choices forgotten at every start (localStorage per port). Done 2026-10-20 (Q34): ui_settings.json.
- [x] F29 Small labels, precision, autosave backup (Q63). Done 2026-10-20 (+ the push client without proxy).

## Milestone 9 — 1.9.0: into the test process (review 2026-10-20). Spec: TASKS.md Q65-Q79. Released 2026-10-20.
- [x] F31 Python API / CLI: names without the unit, "did you mean", `sv.show` (Q65). Done 2026-10-20: svcore/naming.py `resolve_signal_name`.
- [x] F32 Packaging consistency (Q66). Done 2026-10-20: make_pypi.py `pypi_readme` (pictures on PyPI), URLs, classifiers; badge 3.9+.
- [x] T57 `signalviewer-cli check`: requirement checks, exit code, JUnit XML (Q67). Done 2026-10-20: app/checks.py, examples/checks.json.
- [x] T58 Golden-run regression from the command line (Q68). Done 2026-10-20: `signalviewer-cli compare`, app/checks.py.
- [x] T59 Lighter pip install with extras (Q69). Done 2026-10-20: svcore/extras.py, 764 -> 346 MB.
- [x] T60 Reader plugins in the user's folder (Q70). Done 2026-10-20: svcore/readers.py, app/userreaders.py.
- [x] T61 Binary ICD decoder from a layout (Q71). Done 2026-10-20: svcore/icd.py, layouts in the readers folder.
- [x] T40b CAN logs (candump, ASC, CSV) with our own .dbc decoder, option B (Q72). Done 2026-10-20: svcore/dbc.py, can_loader.py.
- [x] T43 part: docs site and a shorter README (Q73). Done 2026-10-20: mkdocs.yml, docs/*.md, .github/workflows/docs.yml.

## Milestone 10 — 1.10.0: numbers you can trust (external review 2026-10-21). Prepared 2026-10-21.
- [x] A1 Spectra of signals with gaps / lost samples / NaN on an even time grid (svcore/ops.py `uniform_samples`, `isolated_gaps`); the plot says how many gaps were bridged.
- [x] A2 Low- / high-pass: the cut-off is the -3 dB point of the zero-phase result (`zero_phase_design_cutoff`).
- [x] A3 Mean / RMS / std weighted by time on uneven sampling (`time_weights`), ⏱ in the Inspector; evenly sampled results unchanged.
- [x] A4 Numerical validation: 23 cases (svcore/validation.py), `signalviewer-cli validate`, docs/validation.md (tools/make_validation_doc.py).
- [x] A5 Real-vehicle logs against pymavlink / pyulog (tests/test_real_logs.py, tools/fetch_real_logs.py); fixed: .tlog boots told apart by radio delay.
- [x] A6 `python -m signalviewer.cli` runs.
- [x] B7 Social preview (tools/make_social_preview.py); the GitHub About fields are the owner's (`gh repo edit`).
- [x] B8 README: download line, who it is for, short bullets, "Where it fits" table.
- [x] B9 Docs site on Material for MkDocs: front page, search, light / dark, Hebrew guide right to left (tools/mkdocs_hooks.py).
- [x] B10 docs/features.md as sections with pictures (no item dropped).
- [x] C13 Simulation against flight: examples/sim_vs_flight (tools/make_sim_vs_flight.py), docs/sim-vs-flight.md, `compare --align / --align-on`, `{"as": ...}`; fixed: names matched without the unit in Compare / Align / CLI, xcorr on flat overlaps.

## Milestone 11 — 1.11.0: adoption (review 2026-10-21, after 1.10.0). Spec: TASKS.md Q80-Q84. Prepared 2026-10-21.
- [x] F37 Small fixes (Q80). Done 2026-10-21: `sv.load()` progress to stderr, PyPI Documentation link, README / docs/install.md (desktop extra, shallow clone, unsigned packages).
- [x] T64 CI on every push and pull request (Q81). Done 2026-10-21: .github/workflows/ci.yml, README badge.
- [x] T65 `compare`: a share of samples allowed outside the tolerance (Q82). Done 2026-10-21: `outside_pct`, `--allow-outside`, app/checks.py `_share`.
- [x] T66 Help → Report a problem (Q83). Done 2026-10-21: /api/report-problem, errorReport.ts `reportProblem`.
- [x] T67 Contributor and community files, outreach steps (Q84). Done 2026-10-21: CONTRIBUTING, SECURITY, CITATION.cff, issue / PR templates, docs/dev/OUTREACH.md.

## Milestone 12 — 1.12.0: several signals at once (owner's report 2026-10-22). Spec: TASKS.md Q85-Q87. Prepared 2026-10-22.
- [x] F38 Several signals at once (Q85). Done 2026-10-22: groups close while searching (DataPanel `sClosed`), the selection's right-click menu (file list and legend), x = each target in the change dialog, *Expression in x* in Analysis (`exprx`, opToStep), group checkboxes, `listSelUsed` (the next pick starts a new selection), Esc / *Clear selection*.
- [x] T68 One piece of work for many runs (Q87). Done 2026-10-22: peers.ts (the same signal in another file, derived signals by operation + mapped sources), Link operations (`linkEdits`: transforms.ts, Analysis, *Create signal ▸*), Link plots through peers (derived too), *Add a run with the same work* (sameWork.ts, SameWorkDialog: edits, derived in order, overlay or tab copies).
- [x] F39 Shift ranges that add up, Shift + drag (Q86). Done 2026-10-22: DataPanel `shiftPress` / `rangeTo` (a new press of Shift starts a new range on top of the selection), the range on mousedown (no native drag of the row), hover extends while the button is held, auto-scroll at the edges.

## Sweeps redesign (owner, 2026-11-01) — 1.18.0: a clean, simple area - not more and more
The owner opened Sweeps after Milestone 23 and found it a mess. Redone, and the old things taken out:
- [x] Four steps, no areas: **Data** (load, merge, the table as CSV and as lines), **Columns** (parameter /
  output / scenario / run id / recording / not used - the old "clean columns" step is "not used"; constant
  columns marked in one click; new columns), **Goal** (one table: at least / at most on any column - a filter
  on it, an output in every scenario - and what to optimize; the rest under "More options"), **Results**
  (Parameter sets, All runs - both as lines with Keep / Exclude / undo / redo / export CSV -, Charts, Next
  runs, Report).
- [x] Taken out of the UI (owner: "remove the old things, only a clean new design"): Explore / Decide and its
  ranking methods (MF10), Which parameter matters (MF05), Model (MF04), the Map and Points tabs (still chart
  kinds in Charts), Data health, the Run area (MF06 / MF11 run step, MF03 DOE, MF07 optimisers, MF08 robust
  sheet), Compare studies. Then (owner: "delete everything old that is not used, clean the code") their
  code too: svcore/sweep/{doe,surrogate,sensitivity,runner,optimise,robust,mcdm,compare,quality}.py, their
  endpoints and tests, scikit-learn (requirements.txt and the extra sweeps-opt - only Kriging used it), the
  page's unused API calls, types, view fields (runStep, exploreAs, explore), strings (307) and styles.
  Kept because the new design uses them: the map and points as chart kinds, clusters / PCA / SOM (Charts),
  next runs, the report. Saved studies on an old step / tab open on its place in the four steps.
- [x] The report (owner, 2026-11-02): *Which parameter matters* out (not about a sweep's question);
  Map and Points kept - they draw the Charts' map / points / bubble panes on screen and next runs' maps.
- [x] Live in the Recordings bar (owner, 2026-11-02): it follows the open files and MAVLink.

## Milestone 24 — 1.18.0 (Q130-Q134): investigating signals: clusters of changes, the likely first, a plot beside each (owner's notes 2026-11-01, 3). Spec: TASKS.md Q130-Q138. After Milestone 23.
- [x] Q130 Changes that happen together, as clusters. Done 2026-11-01: firstchange.clusters (gap > max(3 x the coarser period, 2 % of the search window)); /api/firstchange returns `clusters` (the page does not recompute them); closed to one line (time, n, 3 names), the likeliest open; the reference runs (`refs`: the other open files) mark a member and sort it last.
- [x] Q131 The more likely first (a score with its parts). Done 2026-11-01: firstchange.WEIGHTS / score_parts (strength, timing, stays, unique, shape - the lag against the event signal for the 30 likeliest, leads); clusters by their best member (By time as an option), the event's own signal last; the parts in the row's tooltip.
- [x] Q132 A plot beside each cluster (normalised, the span, the change ticks). Done 2026-11-01: ClusterPlot from the 120-point pictures ((y - level) / noise, the span shaded, a tick per change, the pointer = names and real values); Open as a tab (the cursors on the span, in view from the earliest change), Add to the investigation (journal).
- [x] Q133 Less to wade through (counters, clocks, constants left out; groups by message; keyboard). Done 2026-11-01: firstchange.uninformative (constant; sequence number = the same step; clock = one s / ms / µs / ns per second - an accumulator stays in; heartbeat = toggling at an unchanged period), counted and shown on request; names grouped by message (ATT.*) with the best score, closed; ↑ ↓ → ← Enter.
- [x] Q134 Who leads whom - a small chain of lags. Done 2026-11-01: store._chain (the clusters' best members and the event's signal, a lag per pair bounded to the window, an edge only when positive, clear and a match >= 0.5, in time order); Chain above the clusters (a click opens the cluster); "leads", never "causes". Demo: Motor3 -> Roll +0.12 s.
- [ ] Q135 What is different in this run (against the other runs' envelope).
- [ ] Q136 The same event elsewhere: a consistent precursor.
- [ ] Q137 The investigation in the report.

## Milestone 23 — Sweeps toward modeFRONTIER. Spec: docs/dev/SWEEPS_MODEFRONTIER.md (findings verified 2026-11-01, MF00-MF11, brief in §6). Order: MF00, MF01, MF02, MF05, MF03, MF04, MF11, MF06, MF07, MF10, MF08, MF09.
- [x] MF00 Groups of designs (rule or ids, automatic groups, brush → group) and design status (feasible / fails / error / virtual).
  Done 2026-11-01. Model: `svcore/sweep/groups.py` + `frontend/src/sweeps/groups.ts` (set ids from parameter values, live rule / frozen ids, automatic groups, ∪ ∩ ∖); `view.groups` / `view.activeGroup` optional in .svsweep, undoable. UI: `GroupsPanel` in the results side (automatic groups with counts, marked = the ticked sets, Save as group - Shift frozen -, rename by double-click, freeze, ∪ ∩ ∖ with the active group, eye, delete); colour by group (`#group`, in the colour menu); a hidden group leaves plots and table (through `scopeMask`). Table: status stripe (fails amber, error red), ≈ virtual, the failing condition's cells marked, tooltip "fails in k of n" (`needed` now in the answer's conditions), group chips. Tests: tests/test_sweep_groups.py, tests/e2e/test_sweeps_groups.py (e2e NOT run in this container: no browser - CI / the owner).
- [x] MF01 The problem as one table (parameters incl. categorical, objectives, conditions).
  Done 2026-11-01 (with Q129). `NumField` (click → field, Enter / blur commits, Esc restores, arrows step, Shift ×10; outside the results kept and marked) on every Explore value; *Sliders | Table* in Explore (`view.exploreAs`), `ProblemTable` = the same `Draft` (parameters: type, from / to, in the results, n values, cuts; objectives: direction, weight, threshold, best; conditions: column, op, value, where, cuts). Categorical parameters: levels chosen as checkboxes (`Draft.levels`), saved as a condition `in: [...]` (new optional field; evaluate.py `_condition_in`, set_rows' why). Tests: test_sweep_groups.py (one-of), tests/e2e/test_sweeps_problem.py (not run here: no browser). Not yet: min / max / step / base / on-off columns - they belong to MF03 (DOE) and are added there.
- [x] MF02 More charts, all linked, colour by group.
  Part 1 done 2026-11-01: *Charts* tab = the desktop (`Desk.tsx`, `view.desk`, undoable): 1 / 2 / 4 panes, each a kind - points, bubble (size column), histogram (stacked by the colouring; a dragged range = the one brush), box (per group / holds), scatter matrix (Pearson / Spearman, histograms on the diagonal, coloured points above), broken conditions (fails per condition; a click keeps those that fail it) - and *show large*. `sweeps/stats.ts` (ranks, Pearson, Spearman, histogram, box). e2e tests/e2e/test_sweeps_charts.py (not run here). Part 2 done 2026-11-01: pane kinds lines (the same brush on its axes), map, history (the sets' order, best so far for the goal), Pareto, compare sets (the marked ones, else the group's best; differing values marked); a group per pane (`DeskPane.group`, `groupRows` in view.ts; a deleted group falls back to all). The tabs stay until the three areas (next task in TASKS.md).
- [x] MF02b The three areas (M23 §4): Problem | Run | Explore above the steps; each area shows its own steps (Problem: raw, clean, roles, goals; Explore: results, report); Run is quiet (no run step yet: how the loop closes today - next runs, your own tool, merge back) until MF06 / MF11. Today's *Explore* tab is named *Decide* (it becomes MF10's tool). The Lines / Map / Points... tabs stay inside Explore for this version beside *Charts* (owner's choice taken as recommended: drop them in a later version). Done 2026-11-01; e2e helpers (`_step` through the area) and test_three_areas_and_a_quiet_run updated / added, not run here.
- [x] MF05 Sensitivity (variance share per term, screening).
  Done 2026-11-01. `svcore/sweep/sensitivity.py` (numpy only - no SALib needed): per parameter Pearson / Spearman, ANOVA of the sets (main effect, pair interactions, the rest) as variance shares, first-order and total Sobol indices from the data (total = 1 - Var(E[y|x~i]) / Var(y), None when the others' combinations do not repeat), quantile bins above 12 values, text parameters by level; weak = main + interactions under the threshold. `/api/sweep/sensitivity` (column, sets = a group, threshold). UI: *How much each parameter matters* on top of *Which parameter matters* - for the active group, any per-set column; threshold typed; *take the weak ones off the lines* (undoable). Tests: Ishigami's indices on a grid (S1, ST within 0.02 / 0.03), additive shares, categorical, endpoint; e2e test_sweeps_sensitivity.py (not run here). Not done: disabling a parameter in the problem table (comes with MF03's on / off column); Sobol on a surrogate (MF04); §1's [U] items not re-checked against ESTECO (no web search in this session).
- [x] MF03 DOE (output = a group).
  Done 2026-11-01. `svcore/sweep/doe.py` (scipy.stats.qmc, already a dependency, BSD-3): space-filling (Latin hypercube, random-cd), Sobol, random, full factorial, Box-Behnken, face-centred CCD, fill the gaps (max-min from a space-filling pool); kinds continuous (6 significant digits, so ids round-trip) / integer / categorical / fixed; duplicates dropped; discrepancy and closest pair reported. `/api/sweep/doe`. UI: the Run area's *New sets to run* - vary / hold per parameter (held at the best set's value: the problem's on / off), range typed, method, how many (hint 2 x varied x objectives), preview pairs (new on the sets run), export through the next-runs exporter (every scenario or the sets alone), *Save as a group* (`source: "doe"`, frozen ids via `idOfParams` - fills when the results are merged in). Tests: test_sweep_doe.py (counts, bounds, kinds, discrepancy below random, BB 13 / CCD 15 points, gaps), e2e test_sweeps_doe.py (not run here). Not done: D-optimal, Taguchi.
- [x] MF04 Surrogates (validation table, virtual group, re-run).
  Done 2026-11-01. `svcore/sweep/surrogate.py`: quadratic polynomial (numpy), radial basis functions (scipy RBFInterpolator), nearest sets (numpy), Kriging (scikit-learn GP, ARD - the optional extra `sweeps-opt`: `requirements-sweeps-opt.txt`, licence BSD-3-Clause read in the 1.9.1 wheel's COPYING; joblib / threadpoolctl BSD-3; kept optional in both PyPI packages via `extras.ALWAYS_OPTIONAL`; not in the installer). k-fold CV (LOO under 20 sets): MAE, relative, normalised, R², best = R². Models kept by key (last 8) for `/api/sweep/surrogate/grid` (surface / cut, base values) and `/optimise` (LHS pool + L-BFGS-B, conditions as their own models). UI: *Model* tab - validation table with ★, predicted vs real, 2x2 (surface, contour bands, two cuts, base typed), virtual optimisation → group `source: "virtual"` and export to run for real. Kriging capped at 800 sets so a request stays seconds (not a job). Tests: test_sweep_surrogate.py (quadratic R² > 0.999, sine needs RBF, Kriging if installed, missing → message, categorical, grid, known optimum, constraint, endpoints); e2e test_sweeps_model.py (not run here). Not done: stepwise regression, neural network; residual plot (predicted vs real covers it); long training as a job with progress.
- [x] MF06 Runner.
  Done 2026-11-01 (part 1: local processes). `svcore/sweep/runner.py`: a command template split first (shlex; Windows quotes stripped) then each argument filled ({param}, {scenario}, {out}, {run}, {workdir}) - no shell; parsers JSON at {out}, CSV first row, printed `name = value`; parallel workers, time limit, kill on Stop; each run a row of the results CSV (inputs, outputs, run_status, run_seconds), ok rows not run again (resume / cache). `/api/sweep/run/{preview,start}`, a job (`app/jobs.py`) with live state at `/api/sweep/run/{job}`. UI: Run area *Run them from here* - template, folder, results, parser, at once, time limit, which sets (any group: designs and virtual sets by their ids), the first command shown before running; kept as `view.runStep`. Not done: queues (SLURM / PBS), a run on another machine, MATLAB engine (a template calling matlab -batch works).
- [x] MF07 Optimisers in the loop.
  Done 2026-11-01. Licence gate: pymoo (Apache-2.0) REJECTED - its required dependency moocore is LGPL-2.1-or-later (read in the released wheels' metadata; autograd, alive_progress, Deprecated MIT, cma BSD-3). Written here instead (`svcore/sweep/optimise.py`, numpy / scipy only): differential evolution rand/1/bin, NSGA-II (vectorised constrained non-dominated sort, crowding, SBX, bounded polynomial mutation), model-assisted (RBF of all runs: half best-predicted spread by max-min, half around the best); auto choice (objectives > 1 → NSGA-II; budget < 15 × parameters → model-assisted; else DE); Deb's rules for the conditions; worst case over scenarios per set; failed runs worst. `/api/sweep/optimise/start` runs each generation through MF06's runner (resume / cache, results file), live at `/api/sweep/run/{job}` (generation, best so far). UI: Run area *Optimise by running* - parameters, method, budget, the goal's objectives and conditions; the run monitor; at the end a group "Optimiser n" (all sets run) and the merge. Tests: sphere (DE, model-assisted), Rosenbrock, ZDT1 front (median error < 0.05, spread > 0.7), a constraint, failed runs, categorical / integer, the loop end to end through a script. Not done: CMA-ES, gradient methods, a group per generation.
- [x] MF08 Robust design / reliability. Done 2026-11-01: svcore/sweep/robust.py extends `question.robust` (the same tolerance band) with an optional `dist` (uniform / triangular / normal = band ±2σ); samples by Latin hypercube (scipy.stats.qmc) or Monte Carlo; mean, σ, percentile on the bad side, probability of failure; /api/sweep/robust/{sample,model,stats}; RobustSheet in the Run area (the 5 best sets on the best trained model, mean-vs-σ plot; *Run for real* = the samples as a group for the run step; a group's statistics), the distribution chosen in *Robust to*. No new dependency. Tests: test_sweep_robust (analytic: U / triangle / normal moments, a linear model), e2e test_sweeps_robust.
- [x] MF09 Clusters, SOM, PCA, MDS. Done 2026-11-01: svcore/sweep/clusters.py (numpy / scipy, no new dependency - the SOM is written here, so MiniSom needed no licence check): k-means++ (best of 8 starts), Ward hierarchical, PCA by SVD (signs fixed), classical MDS with its stress, a SOM with U-matrix and hits; columns standardised, cluster 0 = the largest; /api/sweep/clusters on a group's sets. Charts pane kinds *Principal components / clusters* (k-means / hierarchical / MDS, k, colour by cluster, the clusters kept as groups - source "cluster") and *Self-organising map* (a click keeps a node as a group). Tests: test_sweep_clusters (blobs, a line, a plane, two blobs on a SOM), e2e test_principal_components_clusters_as_groups_and_a_som.
- [x] MF10 Decide (weighted, TOPSIS, Hurwicz, Savage, pairwise). Done 2026-11-01: svcore/sweep/mcdm.py (numpy; every method on the same 0-1 utilities so "A above B because" is one arithmetic; AHP eigenvector, CI / CR with Saaty's RI, warning above 0.1; indifference margin = a share of the score range, ties with the run's leader), /api/sweep/mcdm; DecidePanel in the Decide tab (method, α, margin, pairwise matrix, top 10 explained, keep as a group); the *Explore this goal* button is now *Decide on this goal*; `Draft.decide` optional. Tests: test_sweep_mcdm (tables worked by hand, AHP consistent / contradicting), e2e test_decide_ranking_methods_pairwise_and_a_group. The table / best set still rank by the weighted sum (the panel's ranking is its own, kept as a group).
- [x] MF11 Run monitor (live history, Pareto, status counts, stop).
  Done 2026-11-01 with MF06: progress, counts by status (ok / errors / too long / done before), each output's history with the best so far (the goal's / an objective's direction), the Pareto front growing (two objectives), the last 20 failures with their message's end, Stop; when the runs end the results file is merged into the study (or by hand) - the design's group then holds its sets. Tests: test_sweep_runner.py (no shell injection, parsers, statuses, resume, stop, Windows split, endpoints); e2e test_sweeps_run.py (preview; not run here).

## Milestone 22 — work on a selection; typed values in Explore (owner's notes 2026-11-01, 2). Spec: TASKS.md Q127-Q129.
- [ ] Q127 Operations chosen by the selection (2: difference…, 3+: norm, 2N: difference per pair).
- [ ] Q128 The same formula for the other indices.
- [x] Q129 Explore: type a value, not only slide.

## Milestone 21 — new signals in the investigation; a signal's real updates (owner's notes 2026-11-01). Spec: TASKS.md Q124-Q126.
- [ ] Q124 A signal made with an operation, in What changed first and the other investigation steps.
- [ ] Q125 A signal slower than its recording: detected, its updates (when it changes / N Hz), operations over them.
- [ ] Q126 An update clock: a flag (set / rises / changes) or the updates of another signal; set for a selection.

## Milestone 20 — Sweeps, round 4: Explore, what S23 left. Spec: TASKS.md S24-S27. Closed 2026-11-02 (owner): Explore left with the Sweeps redesign.
- [x] S24 A condition added in Explore starts where it keeps every set. Closed, not done: no Explore any more.
- [x] S25 Explore's table: its own sort and columns? Closed, not done: no Explore any more.
- [x] S26 The axes in Explore's lines. Closed, not done: no Explore any more.
- [x] S27 Explore on Windows and macOS. Closed, not done: no Explore any more (the four steps on Windows / macOS: CI and the owner, as every release).

## Milestone 19 — 1.17.0: Sweeps, round 3. Spec: TASKS.md S20-S23. Prepared 2026-11-01.
- [x] S20 The journal for the report: the final story, hide lines, "the analysis starts here".
- [x] S21 Explore: a draft of a goal - conditions, limits and objectives together.
- [x] S22 Goals: the best set while editing.
- [x] S23 Explore visible, reachable and live in the plot and the table. Done 2026-11-01: ExploreButton (Goals side, Results side), every parameter's range / every objective's weight and threshold on screen, conditions added in Explore, `draftStudy` (explore.ts) feeds the existing ParallelPlot (`keep`) and SetsTable (`draft`), exports of what is left through the table's menu.

## Milestone 18 — 1.17.0: Sweeps, round 2 (the owner's notes after using S00-S08). Spec: TASKS.md S09-S18.
- [x] S09 Nothing overlaps in a small window.
- [x] S10 Where the optimization shows (best set, maps by the goal, what the numbers are).
- [x] S11 Points: axis titles, in the report.
- [x] S12 How the plots look (colour map, point size, grid...).
- [x] S13 Many columns: fit, or a slider to move along them.
- [x] S14 The sets that hold as an interactive plot.
- [x] S15 An axis taken off the plot comes back.
- [x] S16 Next runs: numbers that add up.
- [x] S17 Next runs: a compact view, more than CSV.
- [x] S18 Which parameter matters: titles, grid, in the report.
- [x] S19 The optimization in the plots; choosing on a Pareto plot.

## Milestone 17 — 1.17.0: the Sweeps area, the owner's requests (2026-10-31). Spec: TASKS.md S00-S08.
- [x] S00 Groundwork: Sweeps strings in `sweeps/i18n.ts`; `PanelResizer` / `usePanelWidth` shared.
- [x] S01 Fixes: removed parameters in the map / next runs / report; next runs' marks on the map's axes; a goal's weight; template save / delete errors.
- [x] S02 Undo / redo, autosave, messages, Ctrl+K.
- [x] S03 Resizable panels, many columns (scroll, ColumnPicker).
- [x] S04 Sets table: only holding, columns, export.
- [x] S05 Several maps and point plots.
- [x] S06 Next runs: parameters to explore, robustness.
- [x] S07 Templates dialog.
- [x] S08 The whole process in the report.

## Milestone 16 — 1.16.0: fixes to the investigation; when the file on screen was saved (review of 2026-10-28). Spec: TASKS.md Q122-Q123. Prepared 2026-10-29.
- [x] The review fixes (Q122). Done 2026-10-28: What changed first reads the usual level inside the data (and says when there is nothing before the span), exponent numbers in conditions and formulas, a state going down shown ↓, Hebrew in What changed first, "1 stretch".
- [x] When the file was saved (Q123). Done 2026-10-28: the saved time of the version on screen on each file row, amber when the file on the disk is newer (click / F5 reads it), a message per file after a refresh.
- [ ] Q120 a flag shows its signal; Q121 any signal in the stretches table (from Milestone 15).

## Milestone 15 — 1.15.0: Investigate; time axis while working; blank window offline (owner's report 2026-10-26 and the review of 2026-10-28). Spec: TASKS.md Q98-Q121. Prepared 2026-10-28.
- [x] F45 A blank white window offline (Q98). Done 2026-10-26: build target Chromium 87 / Firefox 78, polyfills, the WebView2 version check, safe graphics, the engine in About.
- [x] T74 Time axis while working (Q99). Done 2026-10-26.
- [x] Map objects from ECEF / NED / ENU, vector smoothing, the object dialog (Q101-Q103). Done 2026-10-26.
- [x] Investigate, the spec's steps 1-7 (Q104-Q112). Done 2026-10-26 - 2026-10-27: state lanes, conditions, stretches together and what differs, what changed first and lag, the example and tutorial, runs x conditions, findings and the report, the run at a glance and its rows.
- [x] The review of the investigation (Q113-Q119). Done 2026-10-28: Find similar on the signal that changed, What changed first on the event's file beside the other runs and on long logs, one into each plot, the error per axis, a candidate in a plot of its own, steps grouped, templates keep the conditions.
- [ ] Q120 a flag shows its signal; Q121 any signal in the stretches table.

## Milestone 14 — 1.14.0: big logs, live map, cache, typed signal choice (owner's report 2026-10-25). Spec: TASKS.md Q92-Q97. Prepared 2026-10-26.
- [x] T73 Very large ArduPilot logs (Q92). Done 2026-10-26: bin_loader `_find_heads` (blocks, threads), run-by-run chain, `LazyField` / models `LazySignal` + `LAZY_BUDGET`, float32 fields, index cache (`_index_save` / `_index_load`).
- [x] F40 The browser-mode server stopping (Q93). Done 2026-10-26: any request alive, `/api/bye`, 5 min, never during a job; `reload` job; "server stopped" message.
- [x] F41 Live / refresh on the map (Q94). Done 2026-10-26: `pinTimeToEnd`, `trackTime`.
- [x] F42 The cache (Q95). Done 2026-10-26: `prune_cache`, app/storage.py, Settings → Disk space used, `cli cache`; is_discrete / FFT cache / poll overlap fixed.
- [x] F43 Native window on Windows (Q96). Done 2026-10-26: unblock DLLs, WebView2 by folder, `/api/window_note`. Not checked on Windows.
- [x] F44 Typed signal choice, unit conversions (Q97). Done 2026-10-26: SignalField, Esc stack, units.ts `CONVERSIONS`, transform `unit`; tools/live_demo.py.

## Milestone 13 — 1.13.0: the work of one file, part by part (owner's report 2026-10-23). Spec: TASKS.md Q88-Q91. Prepared 2026-10-24.
- [x] T72 New signals of two files belong to one (Q91). Done 2026-10-24: `params.pinned` (source indexes kept when made for another file) from Expression in x `{file:Name}`, Formula `{file:name}`, Compare's baseline; peers.ts `pinnedOf` in homeRun / mapTo / copyDerived, `crossFileOf`; Copy the work's "Signals made from this file and another" (parts.cross).
- [x] T71 A signal of one particular file in an expression of x (Q90). Done 2026-10-24: `{file:Name}` -> stored `{@<run id>:Name}` (kept by sessions and Replace), shown by the file's name (displayX); backend reads that file, its data version in the edit's cache key; a closed file: not shown (KeyError), never made up.
- [x] T70 Other signals in an expression of x (Q89). Done 2026-10-24: `{Name}` in an edit's expression = that signal of the same file, as read (backend `apply_transform(..., ref)`, `_ref_reader`); xRefs.ts `canonX` (names -> `{Name}`, checked in every target's file) in the change dialog and Expression in x (new signals: the names become sources).
- [x] T69 Copy the work to another file, part by part; Clear this file (Q88). Done 2026-10-23: sameWork.ts `copyWork(from, {run} | {path}, parts)`, SameWorkDialog (open files first, the three parts - plots: same / beside each plot / new tabs / none - two link boxes), clearing.ts `fileWork` / `clearFileWork` / `clearFileItem`.

## Later
- [ ] "copy as pandas code".
