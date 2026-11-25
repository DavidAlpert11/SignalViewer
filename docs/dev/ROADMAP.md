# Roadmap

Audience: flight-test / drone engineers and simulation engineers (MATLAB and Python).
Rules for every task: see `/CLAUDE.md`. Tick `[x]` only when "Done when" is met.
The order of work and the detailed specs are in `TASKS.md` (the work queue).
Spec files named below for finished milestones (SWEEPS_MODEFRONTIER, NAVIGATION, REVIEW_2026-11-16, E2E_MAP,
OUTREACH) were removed on 2026-11-18: `git show 7b16eef:docs/dev/<name>`.

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
- [x] **T12 Live MAVLink** (UDP / TCP / serial) as a source, next to file following. Shipped (reconciled 2026-11-18;
  the check on a real radio / SITL stays with the owner).
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
- [ ] T40 Parquet, MF4, CAN + DBC. Spec: TASKS.md Q21. (2026-11-18: Parquet and CAN + DBC done; MF4 open.)
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
- [ ] T43 Release & reach (signing, docs site, public benchmark). Spec: TASKS.md Q24. (2026-11-18: the docs site is
  done; code signing and a public benchmark are open.)

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
- [x] T49 Duplicate and unclear controls (13 items). Spec: TASKS.md Q48. Done 2026-11-13 (item 10: the cursor buttons by the zoom, round 2026-11-13 L7).
- [x] T50 Small windows and crowded headers. Spec: TASKS.md Q49. Done 2026-11-13 (the "too many plots" hint, round 2026-11-13 L8).
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

## Sweeps, the owner's spec (2026-11-02) — 1.19.0
The Claude Doc "מפרט Sweeps: מסכי Data ו-Columns" (general, Data, Columns, Goal, Results, Next runs, Split by), with two
requests of 2026-11-03 for Recordings:
- [x] General: side panel 220-320 px, folded below 900 px; sticky name columns; names cut with …; the step's button kept in view; the parallel plots zoom / pan / pick a line.
- [x] Data: tables apart, merge into a new table (concat / join, source column, duplicates, preview), Continue with, export CSV / HTML with the view.
- [x] Columns: roles renamed (Conditions, Identifiers) with tooltips, tool row, numbers row, condition cards (search, +N more, range), new columns (completion, preview, edit), Template as a JSON file with a summary.
- [x] Goal: new columns marked, unused limits said, several rows edited together, the column search.
- [x] Results: Show ▾, the re-run list in Next runs, Charts (add / duplicate / remove / export / In report), Next runs' split (equal / proportional / manual).
- [x] Split by: All together / one value, best set per value, a group of each value, re-runs with their value, the report.
- [x] Recordings: derivative / integral of a signal's real updates (its rate, or a 0/1 flag); images for a report (2× PNG) and as an interactive page (HTML).
- [ ] Left: the report's charts reordered in the Report tab; a suggestion moved to the re-run list in one click; open questions - Next runs vs the re-run list, Goal limits vs Must meet.

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

## The owner's review notes (2026-11-03) — 1.20.0
- [x] Legend: beside the plot when many (auto / above / beside / hidden, filter, width), values in a fixed place, the header not lower while hovering, the time in the plot's corner, the unit once, the line under the pointer in front, 20 colours.
- [x] Made signals in the signal list: rename (`/api/derived/rename`, references follow), change the formula, delete (dependents asked, one Undo; `derivedOps.ts`, also Create signals).
- [x] Groups: named, nested by `/` (`ws.sigGroups`, *My groups*), drag onto a group; big automatic groups nest a second level.
- [x] Map / 3D: track colour by the object, a state (the lanes' colours) or a value, with a key; the plain track in the object's colour.
- [x] Fleet: the example (two copters, ten flights), *Try the example fleet*, the trend follows the typed search, the search kept across panels; tutorial (en / he).
- [x] Sweeps: All runs while loading, counts in the tabs; several objectives ranked by score or Pareto, *Show the Pareto front*, the Pareto chart (any pair, the balanced set, levels), fast fronts; *Clear ▾*.

## Milestone 25 — opening a file, first impression, smaller files (owner's plan 2026-11-07). Spec: TASKS.md "Owner's plan (2026-11-07)". Order: U1, U3, U2, M1, A1, U6, U4, U5, U7, A2, A3, U8.
- [x] U1 Choose which tabs a template opens: a dialog when opened by hand, optional `defaultTabs`, auto-open without a dialog, "+N more from <template> ▾", a Settings option. Done 2026-11-07: `defaultTabs` (built-in full reviews: Attitude + Flight), `ws.moreTabs`, TabChoice.tsx, Settings `tplTabChoice`, the editor's *Opened by default*; test_template_tabs.py.
- [x] U3 One flight-mode band per tab (cursors and hover on it, the mode under the cursor labelled; a plot can turn its own back on). Done 2026-11-07: TabBand.tsx, `tabBandLanes`, `plot.ownBand`; the overview strip shows the cursors and hover too (owner); test_tab_band.py.
- [x] U2 Health findings do not cover data: a docked, collapsible card; markers on the bottom timeline. Done 2026-11-07: FindingsDock beside the timeline, `findingMarks` (◆, a click plots), clustered.
- [x] M1 Hero image (2×2, dark, 2x) and a 1280×640 social preview from make_readme_media.py; README order; tagline (owner confirms the wording).
- [x] A1 Split backend/app/store.py: svcore/investigate.py (pure functions, a signal getter) and a LiveWatcher; store.py < 900 lines. Done 2026-11-07: 850 lines; also app/filecheck.py, svcore/transforms.py; tests/test_investigate.py.
- [x] U6 Hover moves a ghost point on the map / 3D (`s.hover.t`). Done 2026-11-07: `s.pointer` (also with the cursors on), GeoChart / Globe3D ghosts; test_hover_ghost.py.
- [x] U4 Desired vs actual: `Des<X>` / `<X>` and `*_sp` pairs - desired dashed and muted unless styled by hand. Done 2026-11-07: desired.ts, `PlotSignal.dash`, Inspector ▸ Line; test_setpoint_style.py.
- [x] U5 SDI-style difference view in Compare: difference plot with the tolerance band, out-of-tolerance in red, ✓ / ✗ per signal. Done 2026-11-07: `/api/compare` `trace`, DiffChart.tsx; test_compare_trace.py, test_compare_diff.py.
- [x] U7 Less clutter: help line as a tooltip, labelled or grouped icons, plurals, the points wording; < 70 visible buttons in the ArduPilot example; automatic flags and log events told apart (owner, 2026-11-07). 2026-11-07: 107 -> 85 buttons (59 controls + the log's data); owner: the strip's mode rows stay (they mark regions of interest); measured as controls < 70.
- [x] A2 Split frontend/src/i18n.ts by area (same key count, no file > 600 lines). Done 2026-11-07: frontend/src/i18n/ (11 areas + index), 1,785 keys.
- [x] A3 App.tsx cleanup: Welcome, RAIL, EXAMPLE_* to their own files; App.tsx < 450 lines. Done 2026-11-07: 434 lines; Welcome.tsx, rail.ts, PlotGrid.tsx, shortcuts.ts.
- [x] U8 Navigation design only (no code): Recordings / Sweeps, view tabs, left rail. Done 2026-11-07: docs/dev/NAVIGATION.md; the owner chose A.
- [x] U9 Navigation option A: the areas as a switch (Recordings · Sweeps · Fleet), Fleet an area, one views menu "+ ▾", Log greyed in the rail. Done 2026-11-07; test_navigation.py.
- Not decided (owner's approval first): M2 flight summary card; M3 forum-help export; finding Mission Planner / QGC log folders; opt-in update check; renaming.

## Milestone 26 — the offline judge: correctness, trust, performance, a calm UI (owner's plan 2026-11-08). Spec: TASKS.md "Owner's plan (2026-11-08)". IDs that collide with Milestone 25 are written 26.<id>.
- [x] C1 Compare judged at full resolution, in both directions. Done 2026-11-08: pass / withinPct / maxAbsDiff on the union of both runs' samples, descriptive numbers on all the baseline's samples, trace decimated only for drawing; CLI = UI; test_compare_fullres.py, test_checks.py (+1).
- [x] C2 Zero-order hold for state signals in formulas and conditions. Done 2026-11-08: `analysis.hold_to`; compute(states), formula.evaluate(holds), conditions(is_state); optional `params.hold: false`; test_state_hold.py.
- [x] C3 Explicit missing-data policy (`params.nan`: propagate | skip | legacy). Done 2026-11-08: NAN_OPS, compute report, cumulative_trapezoid policy, three-valued formula logic, restored recipes without `nan` = legacy; test_missing_policy.py.
- [x] C4 Validation cases V24-V28 in `cli.py validate` and docs/validation.md (28 cases). Done 2026-11-08; V29 (offset timing) moves to P1.
- [x] O1 Offline by default; "Never use the network" (pref + `SV_OFFLINE=1`); an indicator for online tiles. Done 2026-11-08: mapBase.ts, `offlineOnly` / `offlineForced`, tiles.network_allowed(); test_offline_switch.py, e2e test_offline_map (+2).
- [x] C2b Old sessions: derived signals restored without `hold` get `"hold": false` (owner's decision 2). Done 2026-11-08: `analysis.HOLD_OPS`, new recipes store `true`; test_state_hold.py (+1).
- [x] C3b Create signals: the missing-data choice (propagate / skip) for sum, mean, min, max, norm, integral; derived signals marked with what was skipped / bridged. Done 2026-11-08; e2e test_missing_choice.py.
- [x] O2 Honest damaged-file handling. Done 2026-11-08: .bin - the message before a damaged block and damage-only instances left out (`droppedMessages`, `phantomInstances`); .ulg - damaged parameters / messages / time stamps left out (`damagedParams`, `badTimestamps`); `unexpected_load_error`; test_damaged_files.py (+20), e2e test_damaged_note.py.
- [x] O3 Atomic writes for sessions, templates, settings, readers / layouts, reports and Recordings' saves. Done 2026-11-08: app/atomic.py (`atomic_path`, `atomic_open`, `atomic_write`, re-exported by app/common.py); test_atomic_write.py.
- [x] P1 Run time offsets without copying. Done 2026-11-08: `Run.signal_parts`, `Store.signal_parts`, `decimate.view_shifted` in /api/data, cursor, neighbor, stats, limits, envelope, sparks, spectrogram; V29; test_offset_nocopy.py. - [x] P2 One byte-bounded locked LRU. Done 2026-11-08: svcore/memcache.py for transforms, derived, FFT, summaries, stats; Settings ▸ Storage row; test_memcache.py. - [x] P3 Frontend data path. Done 2026-11-08: AbortController, binary /api/data, float32 relative to a float64 reference (/api/data, /api/xy), joinTables.ts; e2e test_data_path.py. - [x] P4 Concurrent open. Done 2026-11-08: app/openmany.py, common.open_paths (memory budget SV_OPEN_BUDGET_MB); test_open_many.py. - [x] P5 Benchmarks. Done 2026-11-09: `tools/benchmark.py --synthetic` (targets in SYNTH_ROWS, `--json`); the file mode works again.
- [x] 26.A1 Dead code in models.py. Done 2026-11-09 (with the unused SignalType / signal_type). - [x] 26.A2 Readers in a worker. Done 2026-11-09: app/subproc.py (also pyops), svcore/readerworker.py, SV_READER_TIMEOUT; test_readers.py (+2), e2e test_user_reader.py. - [x] 26.A3 Consistent sampling. Done 2026-11-09: filters in time (gaps, rate changes), smooth / RMS windows in seconds, `smooth_s()`, old recipes `sampling: samples`; test_sampling.py. - [ ] 26.A4 Transforms in the workspace (assessed 2026-11-09: larger than the task, waiting for the owner). - [x] 26.A5 Heuristics visible. Done 2026-11-09: "Read between samples as" (ws.readAs, /api/read_as), the automatic angle unit's why; test_heuristics.py, e2e test_heuristics.py.
- [x] 26.U1 Design tokens (done 2026-11-09: scale, radii, spacing, semantic colours; test_design_tokens.py). - [x] 26.U2 plot styling (done 2026-11-09). - [x] 26.U3 less clutter (done 2026-11-09: 58 -> 54 / 80 -> 71 controls). - [x] 26.U5 per-signal tolerances, the CLI's file (done 2026-11-09). - [x] 26.U4 judge a run: golden runs, verdict, report (done 2026-11-09). - [x] 26.U6 trust badges + the network in the status bar (done 2026-11-09). - [x] 26.U7 data quality per signal on open (done 2026-11-09). - [x] 26.U8 event navigation: one list, ] / [ (done 2026-11-09).
- [x] T1 Vitest (done 2026-11-09: 24 tests of the frontend's logic). - [x] T2 De-flake e2e (done 2026-11-09: 78 -> 30 sleeps, each left has a reason). - [x] T3 CI subset + validation + benchmarks (done 2026-11-09).
- Not started (owner's approval first): F1 test specs, F2 multi-run envelope, F3 measurement export, F4 reports from a spec.

## Milestone 27 — map objects, smooth motion, primary / secondary (owner's plan 2026-11-09, with a Tacview user's review). Spec: docs/dev/AGENT_PROMPT_2026-11-09.md; board and decisions: TASKS.md "Owner's plan (2026-11-09)". Order: N1, N5, N6, N7, N2, N3, N4, (N8), N9.
- [x] N0 Plan, baseline, fixture (examples/three_objects.csv, tools/make_objects_fixture.py), the prompt in docs/dev. Done 2026-11-09.
- [x] N1 Dot nesting, always and at any depth. Done 2026-11-09: `signalGroups.nameTree` / `pathCuts` (`.` and `/` between identifier-like segments, a trailing unit ignored, a leading `/` skipped, single-child chains folded, no group of one signal, the rest of the name as the label), the heuristics kept for `_` / `:` only (`HEURISTIC_SEPS`), flight logs (`LOG_FORMATS`: bin, tlog, ulg, can) on the old path; DataPanel walks the tree (`Row.label`); signalGroups.test.ts (11), e2e test_name_tree.py (3).
- [x] N5 Map objects (done 2026-11-09: objectDetect.ts, the found list with Add all / Why?, the template, the suggestion bar, looks by class, attitude source own / motion / borrowed; follow-up: motion from velocity signals): every nested prefix with lat / lon proposed (also position-only), classified (truth / navigation / receiver), Add all / Add selected, *Why?* with near misses, the naming convention, the attitude source (own / motion / another object), the suggestion bar on open.
- [x] N6 (done 2026-11-10; reverse playback not done) Smooth motion and an easy map: measured first; pan by transform, inertia, animated zoom, map controls, follow with offset, map keys, the hint; 3D camera modes (Chase, Orbit, Look at); a frame-time benchmark.
- [x] N7 (done 2026-11-10) Primary / secondary objects, the relation panel and line, relation and error signals in svcore, comparison and difference plots in NED / ENU / ECEF / LLA / track frame.
- [x] N2 (done 2026-11-10) Move plots: swap by drag, *Move to…*, a shortcut (`layoutActions.swapPlots`).
- [x] N3 (done 2026-11-10; opacity left out) Line defaults in Settings, `newPlotSignal`, `PlotSignal.lineStyle`, *Apply to all open plots*.
- [x] N4 (done 2026-11-10) Style a whole group of signals at once (group menu, legend multi-select, Inspector batch).
- [x] N8 (done 2026-11-10; approved by the owner) Export to Tacview `.acmi` (svcore/acmi.py, /api/export/acmi, the plot menu).
- [x] N9 (done 2026-11-10) Release 1.24.0 prepared: version, CHANGELOG, README, guides; the full checks green; `frontend/dist` committed; the owner tags.

## Milestone 28 — local-position objects, comparisons, moving plots, map export, an API (owner's plan 2026-11-10). Spec: docs/dev/AGENT_PROMPT_2026-11-10.md; board and decisions: TASKS.md "Owner's plan (2026-11-10)". Groups A L0-L6, B L7-L9, C L10-L11, D L12, E L13.
- [x] L0 Baseline, fixtures (tools/make_local_objects_fixture.py → examples/ardupilot_lanes.csv, local_frames.csv), notes. Done 2026-11-10.
- [x] L1 Metric positions by name: x / y / z under a frame word in any form (ned.x, x_ned, pos_ned_x, ecefX, X_ECEF), the frame decided per group, n / e / d under a position sub-group, flat velocities (shared `NED_VEL`), units flagged. Done 2026-11-10.
- [x] L2 Known groups with local positions: XKF1 / NKF1 lanes (own angles, VN / VE / VD, ORGN), vehicle_local_position, LOCAL_POSITION_NED (`NED_XYZ_GROUPS` shared with frames.ts); order POS → lanes → AHR2. Done 2026-11-10 (names from the loaders' code).
- [x] L3 Origins (own → known → sibling), origin groups never objects, NED / ENU addable through `ref: "signals"`, *Why?* explains the origin. Done 2026-11-10.
- [x] L4 One chain walk (`objectSources`) and one "already on the map" rule (`isAdded`, first recorded source). Done 2026-11-10.
- [x] L5 Rows show frame and origin; Advanced… fills the found origin or suggests the file's receiver. Done 2026-11-10.
- [x] L6 Downstream verified (relations, 3D, templates, Tacview path, old sessions). Done 2026-11-10.
- [x] L7 The rings explained (tooltip, icons, Help) and the pair chosen in one place - Reference ⇄ Compared with, in the relation box and the 3D bar; Ctrl+K. Done 2026-11-10.
- [x] L8 Compare objects… - positions, velocities, angles; values and errors; statistics (CSV); the relation box's four actions as presets; plotsInNewTab never drops silently. Done 2026-11-10.
- [x] L9 Compare with similar… - families of nested names (instance / number / class word, looser on request); angle-wrapped `sub`, the same rule in Errors between two lines. Done 2026-11-10.
- [x] L10 Move a plot to another tab / into another plot (drag onto a tab, Move to…, Add its lines to…, Shift+drop, Ctrl+K). Done 2026-11-10.
- [x] L11 Map export: PNG (this view / all tracks), standalone offline HTML, maps in HTML / PDF / Word reports. Done 2026-11-10.
- [x] L12 API: Python (objects, compare_objects, similar, maps, report), CLI (objects, compare-objects with --tolerance / JUnit, compare-similar, map), REST (/api/objects/*); one detection table and shared test vectors; parity to 1e-9. Done 2026-11-10.
- [x] L13 Docs (guides en + he: the naming convention for metre positions and origins, the rings, Compare objects…, Compare with similar…, moving plots, map export, the API; features.md, limitations.md, README), version 1.25.0, CHANGELOG 1.25.0, `frontend/dist` built. Done 2026-11-11, together with a human-factors review (docs/dev/UX_REVIEW_2026-11-11.md).

## Milestone 29 — one live HTML page, the 3D view in reports, one Map with 2D | 3D (owner's round 2026-11-11). Spec: docs/dev/AGENT_PROMPT_2026-11-11.md.
- [x] One Map with a 2D | 3D switch; "3D (XYZ)" for three plain signals. Done 2026-11-11.
- [x] One rule for what goes into a page (`pagePlot`); what cannot is listed with the reason. Done 2026-11-11.
- [x] The 3D view in reports: picture (PDF / Word / PNG) and live three.js page (HTML, replay, its own file). Done 2026-11-11.
- [x] Every HTML report is live (one time bar; tables and a zoom per plot kept). Done 2026-11-11.
- [x] Python / CLI (`scene_image`, `scene_html`, `map --3d`), docs, README. Done 2026-11-11.
- [ ] XYZ live in the page; shared tiles and a size budget per page; the app's screenshot as the static 3D picture (next round).

## Milestone 30 — the Map in 3D worth a "wow", Tacview that opens, damaged logs that still load (owner's round 2026-11-12). Spec: docs/dev/AGENT_PROMPT_2026-11-12.md.
- [x] P1 Tacview: `Name` a model Tacview draws, `CallSign` the name, 3-field `T=` without attitude, the ACMI checker; Tacview CSV and KML in one *Export the flight* submenu. Done 2026-11-12.
- [x] P2 One "is this a position" rule (0, 0 / out of range / not finite is a gap); *Add all* leaves such objects out. Done 2026-11-12.
- [x] P3 A .bin with one faulty message type loads (a mis-written length, an FMT whose names do not match, no FMT). Done 2026-11-12.
- [x] P4 One Map, drawn in 3D (From above for 2D; flat only where 3D cannot draw); the mouse readout. Done 2026-11-12.
- [x] P5 Relief anywhere (terrarium tiles when the network is allowed, `.hgt` files); the page's far ground, sky, fog. Done 2026-11-12.
- [x] P6 Hide / show objects (the eye; the pages' legend). Done 2026-11-12.
- [x] P7 Places: My places + the session's, the Places panel, import / export, drawn everywhere, the readout and relation box know them. Done 2026-11-12.
- [x] P8 Settings > Map and objects (`mapDefaults.ts`; m-km / ft-NM, decimal / DMS / MGRS). Done 2026-11-12.
- [x] P9 The wow: sun, sky, shadows, drop lines, the last 10 s, flights, Cockpit, the flight display, the mini-map, the error surface. Done 2026-11-12.
- [x] P10 Story mode: moments (`svcore/story.py`), the live page's player, the app's Story, PDF / Word "The flight in N moments". Done 2026-11-12.
- [x] P11 Docs, guides, README pictures 36 / 37, the full backend and e2e runs. Done 2026-11-12.
- [ ] Next (owner to choose): the default theme / language of an exported page, *Ask before closing with unsaved changes*, the app's *Heights* (Cesium exaggeration with the tracks), arrows in 3D, the mouse readout in the offline 3D page, the frame-rate check of P9 on a real graphics card; the ideas of the spec's §H.

## Milestone 31 — welcome pictures, the first minute, one gain set for many systems, the farm, a calmer screen, a "wow" pass (owner's round 2026-11-13). Spec: docs/dev/AGENT_PROMPT_2026-11-13.md; plan: docs/dev/PLAN_2026-11-13.md.
- [x] W11 The two flaky e2e files (wait on state, not a sleep), `tools/quick_check.py`, `docs/dev/E2E_MAP.md`. Code done 2026-11-13; the 10-of-10 measurement is FINAL's.

- [x] W1 Example cards with a picture (both themes, fallback to the icon card, 3 / 2 / 1 columns). Done 2026-11-13.
- [x] W2 The pictures made by the tool (`make_readme_media.py --only examples`). Done 2026-11-13 (FINAL reruns it for all cards).

- [x] W3 The chips in the empty plot (one place at a time; the start card's Quick look removed). Done 2026-11-13.
- [x] W4 The start card's next step. Done 2026-11-13.
- [x] W5 *Click places the cursor* (default off). Done 2026-11-13.
- [x] W6 The status bar's sentence. Done 2026-11-13.
- [x] W13.5 Empty states (plot, file list, findings). Done 2026-11-13.

- [x] W14 core: `svcore/sweeps_common.py` (vectorised; reference with loops in the tests), mapping, `/api/sweeps/common`, `study rank`; the drone example. Done 2026-11-13 (panel: L5).
- [x] W15 core: `svcore/sweeps_next.py`, `/api/sweeps/next-runs`, `study next / status`; the CLI loop finds the fine-grid optimum in 4 rounds of 20. Done 2026-11-13 (button: L5).

- [x] W17 engine: `svcore/placeholders.py`, `svcore/launcher.py`, `/api/sweeps/launcher/*`, `study submit / wait / loop`, `tools/launcher_mock.py`, run.py `study` routing. Done 2026-11-13 (button: L5; the Portable and a real launcher: owner).
- [x] W18 engine: `examples/smart_sweep_demo/`, `svcore/demo.py`, `/api/sweeps/demo/*`, `study demo / demo-sim`. Done 2026-11-13 (view: L5, card: L1).

- [x] W14 panel, W15 *Suggest next runs*, W17 *Send to launcher* + run states, W18 demo view (`StudyPanel.tsx`, `DemoView.tsx`, `SpaceView.tsx`, `ConvergenceChart.tsx`, `sweeps/studyStore.ts`). Done 2026-11-13.

- [x] W8 Command palette: recent first, group headers, keys column, icons. Done 2026-11-13.
- [x] W10 Ask before closing with unsaved changes (revision counter, browser prompt, window dialog, setting). Done 2026-11-13 (the pywebview close: needs a manual check).

- [x] W7 Two cursors' bar in the plot's head. Done 2026-11-13.
- [x] W9 "+8 views", dimmed message part, 3D labels declutter by priority. Done 2026-11-13.
- [x] W13.2 draw-in, W13.4 skeletons, W13.6 readout, W13.9 performance test (threshold set in FINAL). Done 2026-11-13.
- [ ] W13.3 Smooth zoom / pan easing - not shipped: 60 fps on a 1M-sample signal cannot be measured in a headless browser (software rendering, no real frame rate).
- [x] T49 item 10 the cursor buttons next to the zoom (icons + tooltips). Done 2026-11-13.

- [x] W16 A calmer screen: the audit (`tools/count_controls.py`, before → after: welcome 44 → 42, plotted 118 → 116, Settings 59 → 58, Sweeps 14 → 12), the moved controls; T49 ticked (item 10 in L7), T50's hint. Done 2026-11-13.
- [x] W13.7 Focus-visible and pressed states, card lift. Done 2026-11-13.
- [x] W13.8 The tour. Done 2026-11-13.
- [x] Owner's notes after the round (2026-11-13): the loop for any study (`svcore/loop.py`, *Run the loop*, the command / results fields), the demo explained with its real input / output and *Copy the demo to a folder*; What changed at a glance (a sentence + onset rows); the Fleet's questions, summary and first-past-the-limit; the Map story keeps a chosen camera. Done 2026-11-13.
- [x] The owner's review of every area (2026-11-13, R1-R13): each area screened light / dark, en / he, 1280 / 1920; fixes per area (TASKS.md Log). Done 2026-11-13.
- [x] A demo for every area: the welcome's cards grouped by area, *a sweep: which settings hold* (`examples/sweeps/drone_tuning.svsweep`) and *a fleet of flights*. Done 2026-11-13.
- [x] Reports open with *The process in brief* (`reportProcess.ts`, kind "process" first in HTML / PDF / Word). Done 2026-11-13.
- [x] Sweeps on 1M runs: the answer reused across Parameter sets / All runs, a 50k sample keeping every set, mark arrays for (set, combination); All runs shows the scenario axes. Done 2026-11-13.
- [x] README and the documentation site rewritten for 1.27; the design pass (segmented controls, hovers, the Sweeps ways in); texts and styles by area. Done 2026-11-13.

## Milestone 32 — the redesign: Sweeps as one workspace, modern plots and look (owner's round 2026-11-14). Spec: docs/dev/AGENT_PROMPT_2026-11-14.md; plan: docs/dev/PLAN_2026-11-14.md.
- [x] Phase 1: the plan – inventory and acceptance checklist, ArduDeck and other tools, the Sweeps model and layout options, the design system, mock-ups, phases. Done 2026-11-14; approved by the owner the same day (every recommendation); §3.6 (any data, not only ArduPilot) added at his request.
- [x] A1–A4 Tokens and components (new values, `--warn` and tints, elevation, IBM Plex Mono, one definition per component, cards / tables / KPI). A1 done 2026-11-14 (tokens + `--select` accent split, `src/tokens.test.ts` AA check). A2 done 2026-11-14 (Plex Mono for numbers, `@fontsource/ibm-plex-mono` – reason: decision 6, offline). A3 done 2026-11-14 (one definition per component in `index.css`, `test_components_are_defined_once`). A4 done 2026-11-14 (eyebrow, panel head, card, table, KPI, empty state; the Log's health rows as cards). Done 2026-11-14.
- [x] C1–C11 Sweeps as one study for both flows (results first / runs first, continue later): `start` for any study, tables by round, set-up from a table, one vocabulary, the Goal step writes the study, one store and Undo, `.svstudy.json` + `workspace`, New study + Set up, the navigator, the Run column, one Next runs, entry points, three walkthroughs as e2e. Done 2026-11-15 (L2): with L1 / L3's requests (the tables as top-row pills, `--role-output`).
  - [x] C1 `start` (start grid per parameter + scenarios) for any study; `demo.*` still read; a one-table study is ranked on its own. Done 2026-11-14 (L2): test_study_start.py.
  - [x] C2 The tables by round (`GET /api/sweeps/study/tables`) and the set-up guessed from a table (`POST /api/sweeps/setup/from-table`). Done 2026-11-14 (L2): test_study_tables.py.
  - [x] C3 One vocabulary both ways and the Goal step ↔ the study table (`sweeps/studyRoles.ts`; what cannot be written is *this table only*). Done 2026-11-14 (L2): studyRoles.test.ts.
  - [x] C4 One store (`useSweeps().common`, `useStudyPanel` a view on it) and one Undo order for the study file and its tables. Done 2026-11-14 (L2): oneUndo.test.ts; e2e study_common / study_loop / study_demo / sweeps_flow.
  - [x] C5 One study file: `.svstudy.json` + optional `workspace`; one table without Set up stays `.svsweep`; every example and its 1.27 copy round-trips. Done 2026-11-14 (L2): test_study_files.py, studyFile.test.ts.
  - [x] C6 *New study* (*I have results* / *Start from nothing*) and the Set up view (what varies, scenarios, outputs and goal, how to run). Done 2026-11-14 (L2): setup.test.ts, e2e test_sweeps_workspace.py.
  - [x] C7 The navigator: the study's name, Set up (✓ n/4), Together (≥ 2 systems), Tables (every open table, its merged parts, the study file's tables and rounds, *new* marked; Add table, Merge); the Data step's list and *Continue with* gone. Done 2026-11-15 (L2): e2e test_sweeps_workspace (+ rounds), test_sweeps_flow, test_sweeps_data_columns.
  - [x] C8 The Run column (right, beside every part of a study file): the next round - what round 1 runs (sets × scenarios = runs) or what is missing, a click to Set up -, *Only write the files* (W15, moved from the ranking's head), the loop (Next round / Until converged / Stop / Start over, the command, progress, convergence, rounds); the demo's controls, strip and chart too. Folds; remembered (`sv3.swRunHidden`). Done 2026-11-15 (L2): e2e test_sweeps_workspace, test_study_loop, test_study_demo, test_study_common.
  - [x] C9 One place for each next-runs action: one table - the Results step's *Next runs* (six kinds, *Export…*); several systems - W15's proposals on Together's ranking and space, written (*Only write the files*) and run (*Run them*, was *Send to launcher* above the ranking, with the runs' states) in the Run column; Together = the ranking + the space (+ its CSV); a demo study's explanation is its *About* page in the navigator. Done 2026-11-15 (L2): e2e test_study_common, test_study_loop, test_study_demo, test_sweeps_workspace, test_sweeps_charts.
  - [x] C10 Entry points (done 2026-11-15, L2): one Open ▾ (New study… · a table · a folder · a saved study of either kind - the *Common parameters* submenu and the welcome's second *Open study…* gone); one Save (Study ▾ / the palette save the study file when one is open); the study panel's own Undo / Redo / Save / × gone (the area bar's; *Close the study* in Clear ▾ and the palette); each palette command once (`sw-new-study`, no `cp-*`); the status line *Study: name · n tables · shown: part*. `count_controls` Sweeps 16 → 15. One report: Study ▾ → *Report of the study…* with a study file open (`POST /api/sweeps/study/report`: set-up, each table's goal, the shared answer with each table's verdict, the rounds; a table's own report stays in its Results). Open: the study pills in the top bar (TopBar is not L2's - requested from L3 / Final).
  - [x] B7 The Sweeps charts on the same styles: amber is the cursor's and time's only - a selection / active / the best (filters on the parallel plot, the brush, steps, goal tabs, the best value, the balanced choice) in `--select`, warnings (fails, to check, the edge kind, the deciding scenario) in `--warn`, proposals / changes / the convergence line in `--info`; the area's palette's amber moved from 2nd to 6th and *holds* is green (as the plots' traces, A1). The outputs' role colour waits for an L1 token (`TODO(L1 token)`). Done 2026-11-15 (L2): test_design_tokens, e2e test_sweeps_charts, test_study_demo, test_sweeps_groups; pictures dark / light.
  - [x] C11 The §4.7 walkthroughs as e2e (2026-11-15, L2): `test_sweeps_workspace.py` 10 / 10 green (1-2, 4, the rounds listed, the Run column, one Open, a study round read as its table with its goal + Undo, an old study file; walkthrough 3 - the example's question typed → 12 of 45, Next runs → Near the best → Export CSV, Save → `.svsweep`, reopened at the same step; 5 - a test program, Next round saves the `.svstudy.json`, Round 1 opens with the Set up's goal, Round 2 marked new; 6 - a table's goal edited in the area is the study table's, Together follows, one Ctrl+Z takes both back). Fixed on the way: Save after *I have results* wrote a `.svstudy.json` (C5's `fileKind` was never asked - now it routes the one Save); a round was never *new* (the loop rewrites the study file each round - *new* is now "written since you last looked": `seenAt`, UI only); a study table's goal edited in the four steps reaches the study file's table with no step of its own (`followTableGoals`; Undo gives back the table's own words). The demo has no Together ranking of its own, so 6's Together half runs on the three-drones study.
- [x] B1–B7 Plots (the plot card, legend with values, mode band, uPlot theme, timeline, Map / 3D chrome, Sweeps charts).
<!-- lane L3 -->
  - [x] B1 The plot card head: an eyebrow (*Plot n* when the plot has its own title, *Active* with several plots), the title, a muted meta (*n signals · two y axes*), the actions; the legend on a line of its own under the head; the card radius `--r-card`, the active ring `--select`. One head for every plot kind (time, X-Y, X-Y-Z, FFT, spectrogram, map, 3D). Done 2026-11-14 (L3).
  - [x] B2 The legend carries the cursor's values: the number in mono and ink (amber stays the cursor's), the unit muted after it (a span of its own, so a value reads as a number), Δ between the two cursors a quiet tag. The Inspector's cursor table stays (it has T2, Δ and the slope per signal - more than the legend); it is reviewed with D8. Done 2026-11-14 (L3).
  - [x] B3 The mode band inside the card: the tab's state lanes (TabBand) drawn as a thin strip inside the top time plot's card, between its legend and the plot, still lined up with the time axis and still once per tab (U3); a setting `bandInCard` (default on; off = above the plots as in 1.27). The overview strip keeps the lane it shows (no second mode row). Settings' row asked from L1. Done 2026-11-14 (L3).
  - [x] B4 The uPlot theme: axes' numbers in Plex Mono 10 px (`--mono`), PLOT_THEME synced with A1's token values (plot background, grid one step off it, axis), both cursors dashed amber with a dot where cursor 1 meets each line (its value in the legend; the value flags still on request), limits a dashed `--danger` line with a short tick in the signal's colour. No change to decimation or the data path: test_perf_budget 0.7–1.0 s before and after (budget 30 s). Done 2026-11-14 (L3).
  - [x] B5 Timeline: the run's modes as colour along the track (the lane the overview strip shows, else the tab's first state lane; one request over the whole recording), under the overview line (R3) and the amber window (R3). Done 2026-11-14 (L3).
  - [x] F2's legend (L3): the plot's ⋯ > Legend > *Statistics of the shown window* puts min · mean · max of the time on screen beside each line (L5's `/api/stats/window`, asked again 150 ms after a pan / zoom settles; a line's own time offset and scale applied; a view choice, not saved). Done 2026-11-14 (L3).
  - [x] D2 Files / signals panel: the head counts the open signals (`.ph-count`, A4); from 40 signals on, while the search is in use (focused, or a chip chosen), quick chips under it (`.chipbtn`, A3) – the groups the tab uses first, then the largest, any format (a log's messages, a .mat's structs, a table's prefixes); a click filters to the group, a second shows all. count_controls unchanged (welcome 42, plotted 105, settings 58, sweeps 16 – the plotted example has 9 signals: no chips). Done 2026-11-14 (L3).
  - [x] D1 One top row + the stage bar (decision 5): in Recordings the top row holds the area's tools (`.area-tools`: open / save session, Templates, Live, Undo / Redo, Clear, Inspector) beside the search and the app's own buttons; the area's second row is gone (the plots get its 40 px; `.app` drops the row when no `.areabar`); the plot tabs (`PlotTabs`: rename, reorder, close, drop a plot on a tab, + and the views menu) open the stage bar. Sweeps / Fleet keep their own bars (their lanes). Open files as pills in the top row: not done (it would add controls; the file panel lists them). count_controls 42 / 105 / 58 / 16 (unchanged). Done 2026-11-14 (L3).
  - [x] D8 Inspector, timeline findings, notes: the Inspector's section titles as eyebrows (A4), the numbers of its value and statistics tables in mono, end-aligned; each line's statistics can be pinned to the run at a glance (☆ on the line's row → min / max / mean / range, by the signal's name, Undo-able – L5's D14 request (3)); the timeline's warnings and findings ◆ in `--warn` (amber stays the cursor's), errors `--danger`, notes `--info`. The Inspector's cursor table stays (T2, Δ, the slope – more than the legend). count_controls 42 / 107 / 60 / 16 – the same with and without D8 (the +2 / +2 since D1 came with other lanes' merged work). Done 2026-11-15 (L3).
<!-- end lane L3 -->
- [x] M1–M6 The map, offline first (cameras named by what they do; a background picker, Satellite + roads, keep an area offline, My maps: MBTiles / own tile server, the offline map's look).
<!-- lane L4 -->
  - [x] M2 Satellite + roads – one composed layer (`app/tiles.py` `COMPOSITES`), in 2D, 3D, the exported picture and the offline page; Esri's terms noted (no bulk download). 2026-11-14.
  - [x] M3 Keep this area offline – `app/tilekeep.py` (terms per source in `tiles.BULK`), the dialog `KeepAreaDialog.tsx`. 2026-11-14.
  - [x] M4 My maps – `app/mymaps.py` (raster MBTiles, a user's XYZ / TMS server, `my:<id>` layers), *Add a map…* and the list in the picker (not Settings: one place). 2026-11-14.
  - [x] B6 Map / 3D chrome – one glass bar top-start, the bottom docks (data box as an instrument, attitude and relation box bottom-end), `styles/map.css`. 2026-11-14.
  - [x] M1 Map background picker – `MapLayers.tsx` done 2026-11-14; the plot head's old select removed (E1–E4, 2026-11-15).
  - [x] M6 Cameras named by what they do (Free · From above · Around it · Behind it · Cockpit 3D only), a picture each, Track up folded into Behind it; old sessions unchanged. 2026-11-15.
  - [x] M7 Two cameras (owner, 2026-11-16: "enough to mark whether the camera is free or on the object") – Free · On the object (2D and 3D); On the object: drag turns around it, wheel / + − towards it down to sitting on it (its model hidden within 15 m), the distance kept in the object's frame as the time jumps. From above, Around it, Behind it, Cockpit, Look at removed; old sessions read by `followObject` alone (`mapCamera`), an old *Behind it* setting = On the object; the flat drawing's N button = track up. The offline pages (`report_assets`) have the same two (an old link's `#cam=close / cockpit` reads as On the object, `top` as Free); the report's picture is always the 3D scene (the flat From above picture is gone). A double-click elsewhere (and 0) fits everything and sets Free; a double-click on an object, F and Ctrl+K *Map camera: on … / Free* put the camera (`actions.setMapCamera` - the one way); the 3D view's keys (arrows look around the object / move Free, + −, 0, F); the flight display a picture the wheel goes through, shown by default while sitting on the object (app and page). 2026-11-16.
  - [x] M5 The offline map's look: a quiet palette from the tokens' surfaces, roads wider close up, places under the tracks (2D). 2026-11-15.
  - [x] F5 Height profile – `app/heightprofile.py`, `/api/profile`, `HeightProfile.tsx` (*Profile* in the map bar); any format with positions; says why when the ground is coarse. 2026-11-15.
  - [x] F6 Vectors along the path – any two signals (north, east) as arrows on the track in 2D and 3D; a log's wind / a file's velocity offered by itself. 2026-11-15.
<!-- end lane L4 -->
- [x] D1–D14 Every area adopts the look (pictures and a recount per area); D13 wording / icons audit; D14 profiles (templates with their at-a-glance numbers and chips). D11 (welcome) done 2026-11-14. D12 (Settings, palette, dialogs, library, Help, tour) done 2026-11-14. D13 (wording / icons audit; requests to L3 / L5 for their strings) done 2026-11-14.
- [x] E1–E4 Docs, pictures, a test-bench example, 1.28.0 (the owner tags). Done 2026-11-15 (coordinator): E2 guides en + he and the
  positioning (any data), E4 `examples/bench` (Parquet + checks.json, welcome card), the lanes' requests finished (M1's last step, the
  Checks chip's run), dead backend code removed, CHANGELOG by theme, version 1.28.0, validation page, `frontend/dist`. Full e2e 460 / 461
  (the 3D click test then made robust: 13 / 13), quick_check, mkdocs --strict, test_perf_budget, the 1M-run measure (L2) green. E1: only the
  new card's pictures were made - the README pictures were not retaken this round.
- [ ] F1–F7 New capabilities (2026-11-18: F1–F6 done; F7 the pop-out window not started; F8 dropped with the Fleet in FL1) the owner picks (messages, window statistics, parameters + two logs compared, live instruments, height profile, vectors along the path, pop-out; F8 the Fleet for any format – later), all format-neutral (§3.6).
<!-- lane L5 -->
  - [x] F3 (backend) Parameters of a run for every format + two runs compared. Done 2026-11-14: `svcore/runinfo.py` (log PARM / PARAM_VALUE / PX4 · MAT scalars, texts, struct fields (`Run.file_params`, v5 and v7.3) · constant signals · file-name numbers; one source - `investigate.run_params` (Runs × conditions) reads it), `GET /api/runs/{id}/parameters`, `POST /api/runs/parameters/compare`; test_run_parameters.py. Its screens come with D7 (Log / Checks) and D4 (Compare), after S1.
  - [x] F1 (backend) *The file* - the structure of any recording. Done 2026-11-14: `svcore/filestruct.py` (groups = a log's message types / an MCAP's topics / MAT-HDF5 structs / a table's column prefixes; per group and column: samples, rate, unit, gaps, state, own time; the time base), `GET /api/runs/{id}/structure` (a followed file is read as it is now); values at the cursor stay `/api/cursor`'s. test_file_structure.py (CSV, .mat, .bin, .ulg, .mcap, a followed MAVLink .tlog). The panel comes with D7 (the Log panel's place), after S1.
  - [x] F2 (backend) Statistics of the visible window. Done 2026-11-14: `svcore/windowstats.py` (min / mean / max / samples over the window, NaN skipped; block summaries cached with the arrays, so a 20M-sample signal answers in < 5 ms per pan / zoom), `POST /api/stats/window` (shown time, each run's offset; states left out). test_window_stats.py (= numpy on the window). The legend's display is L3's (B2); the Inspector's third choice with D3 / D8.
  - [x] D10 Fleet in the new look. Done 2026-11-15: the fleet at a glance as the app's numbers (`.kpis` / `.kpi`, errors / warnings tinted only when not 0), section heads as `.eyebrow` (Folders, Find flights, Ask the fleet, the count), a flight's findings as tinted `.hrow` cards (error / warning), the trend in a `.card` with its limit line in the danger colour (amber is the cursor's / the time's alone). No logic or control changed (count unchanged); rules in `styles/panels.css`, 2 i18n keys. Pictures `docs/dev/mockups/D10/{before,after}`; e2e test_fleet, test_navigation, test_owner_notes_1_20, test_welcome_cards, test_file_help_menus.
  - [x] D9 + F4 Live instruments for any live source. Done 2026-11-15: *Instruments* - a tab of the Checks panel (no new rail button): tiles = each signal's value IN FORCE at the time (the last sample at or before it, never interpolated; a state shows its label), flagged *n s old* when older than 3 s and 5 of its own intervals (a state never: its age is how long it holds); the attitude indicator (FlightDisplay) of the object the map draws for the file (objectDetect / the user's map object: angles to degrees by the Automatic rule, a quaternion too, heading 0-360, ground speed from the positions). While live the time stays at the newest data, so one view serves MAVLink, *Send data from Python*, a followed file and a recording. Tiles: `ws.instruments` (names, "a|b"; ≤ 8; Undo), else the template's at-a-glance names; templates carry them (ArduPilot / MAVLink / PX4 review templates: altitude, speed, battery, GPS fix, satellites, mode). `svcore/instruments.py`, `POST /api/runs/{id}/instruments` (routes/live.py), `components/Instruments.tsx`. D9's look: the popovers' chosen values in `--ink` (were muted like their labels). Tests: test_instruments (4), profile.test.ts (+1), e2e test_live_report (3 new: a recording, a followed file, data from Python).
  - [x] D6 Report + preview in the new look. Done 2026-11-15: *Send it as a replay* a `.card.info` (was amber - plan decision: amber only for the cursor and time), the plots' head an `.eyebrow` with its `.ph-count` (the plots that go in), the empty report an `.empty-state`, inline sizes moved to `styles/panels.css` (`.r-summary`, `.r-preview`, `.r-htmlhint`); the preview dialog unchanged (it shows the report itself). Pictures `docs/dev/mockups/D6/{before,after}`; e2e test_replay, test_findings_report, test_judge_a_run, test_features -k report (test_live_report::test_one_map fails on main without D6 too - the map's mode menu, written under L4).
  - [x] D5 Investigate + What changed in the new look (the mock-up `what-changed.html`). Done 2026-11-15: What changed - the verdict first as one `.card.warn` (the summary sentence, moved out of the onset strip; the caveat folded in it), the onset rows with their time in mono, *Stack* the one primary action; Investigate - *how to start* a `.card.info`, the conditions' head an `.eyebrow`, empty states `.empty-state`, the occurrences `table.data` with `.num` columns and the statistic translated (was raw "max" / "min"). Pictures `docs/dev/mockups/D5/{before,after}`; e2e test_what_changed, test_conditions, test_occurrences, test_runs_matrix (21).
  - [x] D4 Compare (+ Compare objects) in the new look. Done 2026-11-15: the verdict a `.card` (ok / bad tint, `.card-list`, `.card-next`), the selected signal's numbers `table.data` with `.num` columns, the similarity head an `.eyebrow`; *Table of all signals* and Compare objects' statistics `table.data` (CompareObjectsDialog.tsx: one line, marked `L5 D4`); F3's *two runs compared* in the panel: per file the parameters that differ from the baseline file (read-only, follows the panel's choice - no new control). L1's D13 wording (compare / investigate). The old `table.vals.cmp2` rules in index.css are unused now. Pictures `docs/dev/mockups/D4/{before,after}`; e2e test_compare_params (new), test_compare_diff, test_compare_tolerances, test_judge_a_run, test_compare_similar, test_features -k compare/same_flight.
  - [x] D3 Analysis (Create signals) in the new look. Done 2026-11-15: the frame suggestions use `.chipbtn` (the old `.frame-sugs .chip-btn` rules in index.css are now unused - L1 may drop them), the derived list's head a `.ph-count`, its empty state `.empty-state`. No statistics live in this panel, so *pin to at a glance* is the Inspector's (L3, asked). Pictures `docs/dev/mockups/D3/{before,after}`; e2e test_features (create / formula / frame / derived), test_trust_badges, test_missing_choice, test_pyops.
  - [x] D14 Profiles (templates with their at-a-glance numbers and chips). Done 2026-11-14: optional template / workspace fields `glance` ({name, stat, label?}, ≤ 4; stats min · max · mean (plain sample mean) · first · final · range) and `searches` ({q, label?}); `POST /api/runs/{id}/glance` (by name, loose match, unit from the name, shown time; a missing name returned with sig null); the built-in ArduPilot / MAVLink / PX4 templates carry theirs; opening a template merges its own then its parts' (Undo), saving one keeps the session's; `actions.pinGlance / unpinGlance / pinSearch / unpinSearch`; `prefs._validate` drops malformed entries (old templates unchanged). Shown by L3 (strip, signal list chips – asked under L3); *Pin to at a glance* in Analysis comes with D3. test_glance.py, Vitest store/profile.test.ts.
  - [x] D7 One *Checks* view for any file. Done 2026-11-14: the Log panel's place is *Checks* for every open file (rail button enabled once any file is open): a verdict, then tinted cards – Limits (every tab's limits on the file's signals, `/api/limits`), Data quality (`svcore/quality.py`), the log's Health check; tabs Checks · Events (logs) · Parameters (a log's own view; other files F3's list + *compare with* another file) · The file (F1: groups, rates, gaps, units, values at the cursor, click to plot) · Hardware (logs). `components/ChecksView.tsx`, `styles/panels.css`; App.tsx / rail.ts: 4 lines (marked `L5 D7`). The *at a glance* strip's counts are L3's (OverviewStrip) – asked under L3. e2e test_checks_view.py (new); selectors / label updated in test_features, test_navigation, test_event_navigation, test_release_1_21. count_controls unchanged (42 / 105 / 58 / 16).
<!-- end lane L5 -->

## Milestone 33 — clear to a human: the fixes of the fresh review (owner, 2026-11-16). Spec: docs/dev/REVIEW_2026-11-16.md §6; board: TASKS.md "Current state".

- [x] RV1 A drag zooms by its direction (sideways = time, up / down = values, diagonal = a box) - the zoom-mode button, its menu, the Z key and the palette's three zoom commands removed (the owner); the link button says *Link time*, not "X"
- [x] RV2 Checks says what was checked: "no limits set" instead of "0 failed"; the pump demo opens with its limits (S1)
- [x] RV3 A file's name is never squeezed away by its badges (B1)
- [x] RV4 Notices do not cover the data (place, life, the informational ones quieter)
- [x] RV5 Each demo opens what its card promises, with one line saying what to do next (B4, B5, §4.4)
- [-] RV6 Fleet counts airframes, one line per vehicle, no duplicate numbers (B2, B3, B10) - cancelled: the Fleet area is dropped (FL1, owner 2026-11-16)
- [x] RV7 One count of a log's findings (B6: pill / findings chip / report); the line of instructions above the plots shown once, not always (§4.2). Done 2026-11-16: the chip `findingsN` reads "{n} to look at" (the pill's word); `rpLog` names the log's own messages; OverviewStrip `hintShown` stores `ovHintSeen` once shown. test_workflows (chip text), test_less_clutter (closes RV5's demo line before counting: 57 -> 55 controls).
- [x] RV8 Report: one offline page instead of *Make a replay page…* and *Create interactive HTML* (§4.7). Done 2026-11-16: the replay card's button runs the HTML report (`make("html")`, named after the recording without a title, *Open it* in its notice); the bottom HTML button and `makeHtml` / `htmlHint` gone (`reportOther` for PDF / Word); `report.py` the brand footer on every live page; Ctrl+K's compact replay kept. Tests: backend test_replay (+1); e2e test_replay, test_live_report, test_workflows, test_features -k report.
- [x] RV9 Map bar: Camera, Fit, Story always; the rest under one ⋯ (no second row with the Inspector open) (§4.6). Done 2026-11-16: MapBar `extras` (Globe3D's) + Profile + Relation in `.map-more-pop` under `.map-more-btn` (closes on a click away / Escape); `children` stay on the bar (2D: N / track up, back to the object); + − kept beside fit. Tests: e2e test_globe3d, test_height_profile, test_live_report (a `more()` helper), test_map_objects.
- [ ] BR1 (owner's idea, 2026-11-16) Position the app as one process: a run -> a group of runs and their recordings -> a sweep's results (README, the docs' home, the welcome screen's three groups). Proposed wording in TASKS.md; waits for the owner's yes.
- [x] RV10 Runs A / B colours further apart; a set point drawn above its measurement (§4.5). Done 2026-11-16: `store.FILE_COLORS` B = #E5677A (rose; teal-green third); TimeChart draws setpoints last (`setpointsIn` order in `aligned`), findSimilarHere reads the drawn order. e2e: test_setpoint_pairs, test_setpoint_style, test_plot_style, test_plot_polish, test_tab_band, test_what_changed, test_round_1112, test_release_1_21, test_compare_diff, test_runs_matrix.
- [x] RV11 Small ones: Space = the same meaning in the app and the report pages (B7); a formula's syntax error at its real position, an unknown function named (B8); *Camera following an object* under Map in Settings (B9). Done 2026-11-16: B7 - the app's Space keyup no longer reaches a focused button (`spaceTaken`), the pages take P for Play as the app (Space = cursor in the app, Play in a page - kept; asked the owner whether to change it); B8 - `formula._syntax_message` / `syntax_message_for` (the typed text, `{names}` kept) / `_unknown_function` (difflib); B9 - SettingsDialog MapSection. Tests: backend test_formula_messages (new, 4); e2e test_space_and_settings (new, 2), test_settings, test_replay, test_features -k cursor/fx.
- [x] SW1 (owner, 2026-11-16) Sweeps: a sweep wrapper - one simulation per set of inputs (one JSON file each, one row back); the inputs as `name: 1,2,5,8:0.1:9` lines (MATLAB-style), a table of rows or the app's round; *How to run* → A wrapper on this PC; the smart-sweep demo runs through it and shows how to run it by hand
- [x] FL1 (owner, 2026-11-16) Drop the Fleet area from the code and every doc; the many-recordings need through *Summarize a folder -> Sweeps* (a clear way in from Sweeps, the example folder as a Recordings demo card) and the rows' recordings opened together in Recordings (plan: TASKS.md Current state). Done 2026-11-16: app/fleet.py, routes/fleet.py, FleetPanel, the area, its strings (i18n/liveAndFleet.ts -> live.ts), styles, tests, tutorials and docs removed; `svcore.summary.read_measures` / `folder_measures` (a folder's measures.json, also the CLI), the summarizeFolder job falls back to it, `GET /api/summary/folder`; `folderSummary.ts` (summarizeFolder / fromFolder / openRecordings - the one way, used by the Runs matrix, Sweeps' Data and empty screen, the card, SetDetail); `ui.matrixFolder` (the Runs matrix defines on the folder's first file, saves measures.json there); RawTable ticks + *Open n in Recordings*; examples/folder_of_flights + measures.json, card `folderOfFlights` (open "summary"); tools/make_folder_example.py. e2e test_folder_of_recordings (new, 2).
- [x] SF1 (owner, 2026-11-16) Sweeps: one flow of five steps; *Send runs* in the side panel (what varies, scenarios, how to run - no outputs / goal for round 1); the first results open the usual flow (Columns, Goal, Results); the loop in Next runs once a goal exists; Clear everything closes the study (spec: TASKS.md Current state). Before SW2. Done 2026-11-16: `setup.readiness` missing = params / range / command, `hasGoal`, `setupDone` 3 parts; SetupView = Send runs (1 what varies, 2 scenarios, 3 How to run - RunHow moved from Next runs -, a sticky *Send round 1* card = loopAction next, saved first); `studyStore.showStudyFile` (the navigator's rounds and the first results), `firstResultsIn` (round 1 finished, no table open: its file opened as the study table, shown when on Send runs, marked seen); `applyStudyTable` - a study naming no output: every other number = output, run_id = id; RunPanel `LoopGoal` (linked table: its Goal step; else rank by / smallest-largest / must hold), above the proposal while missing (NextRunsView `lead`); LoopSection Next round / Until converged need a goal; Clear ▾ › Everything closes the study file too (one Undo restores it). Tests: Vitest setup.test (+1); e2e test_sweeps_workspace (start from nothing, runs first -> round 2 + Clear, one flow; the Open menu list fixed for FL1), test_study_loop.
- [ ] SW2 (owner, 2026-11-16) Sweeps: investigate chosen scenarios on demand - open several rows' recordings together in Recordings, or *Run again with recording* (the same inputs + `"record"`: the simulation writes its time series; the demo's sim.py too), then open them (plan: TASKS.md Current state). (a) done by FL1 (ticked rows -> *Open n in Recordings*). Owner's answers (2026-11-16, chat): (1) which runs record is a **rule set in advance**, default *no recording*; (2) a simulation file takes **one run**, the wrapper **a parameter set** - choose accordingly; (3) the re-runs are **chained**, then a notice says a run is **ready to load** (not opened by itself); (4) a re-run whose summary row differs from the original is **loaded as another layer of results**.

## Milestone 34 — the window back to the data, one way for each thing (owner's review, 2026-11-16). Board: TASKS.md "Current state". This round adds NO features: no new ways to run, formats or demos; SW2 (b) is not started.

- [x] FR1 Plots take the window. The plot card's header and legend share one row when they fit; a plot with one signal does not repeat its name as title and chip; "PLOT n - ACTIVE" is removed (the ring stays); the time axis shows its unit. Done when: on the ArduPilot demo at 1440x900, Inspector closed, the summed area of the plots inside their axes (.u-over) is at least 35 % of the window (21 % today) and an e2e test measures it; the same test passes in Hebrew and in dark; test_plot_polish, test_plot_menus, test_tab_band, test_overview_strip and the files of views that gain space are green. Code done 2026-11-16 (32.4 % alone; the 35 % with FR2's rows - ticked there): PlotView - the eyebrow (`plotActive`) and `.head-break` gone, `.plot-head .legend` flex-basis auto (shares the row when its chips fit), the head 28 px, a lone line's repeated title not shown (`titleShown`; *Rename the plot…* in the plot's menu then); TimeChart - time axis `xAxisSize()` 22 px (was 34) with the unit after its last number (`chartUtil.timeTicks`, `timeAxis.timeUnitOf`: the column's unit through the Time axis conversion, none when files differ), value axis ticks 4 px (gutter 82 -> 74), top padding 6. Callers read: .plot-head (TimeChart's sel-slot, PreviewPlots' own head, tools/make_readme_media EX_NO_TEXT), reportGutter / useGutter (Spec / Envelope share the column's gutter - unchanged), test_features V05 (renames an empty plot: title still there). Tests: e2e test_plot_room (new), Vitest chartUtil. Ticked with FR2: 36.3 % measured (test_plot_room's floor 35).
- [x] FR2 One row above the plots. The demo line, the run at a glance, Auto flags and the mode band take at most two rows by default. A demo's line changes to its next step, or goes away, once its button was pressed. Done when: on the ArduPilot demo the first curve starts no lower than 200 px from the top of the window; after "Open Checks" the line no longer offers "Open Checks"; e2e for both; old sessions open unchanged. Done 2026-11-16: OverviewStrip - the automatic flags are drawn on the strip's first lane (`.ov-flags.over` inside the first `.ov-row`; a file with no lane keeps the flags' row and its label); while a demo's line is up the strip's head (`.ov-head`: the run at a glance, +, ×) is not drawn and comes back when the line goes (`demoGuide.demoLineUp` - the one rule DemoGuide and the strip share; App no longer repeats it); DemoGuide - after its button a step with a `done` text shows it, any other line closes (was: kept offering the same button). Nothing saved changed (`overviewRows`, prefs): old sessions open as before. Callers read: demoGuide state (Welcome.openExample, ui slice), `.ov-head` users in e2e (test_tab_band closes the line before the strip's ×), tools/make_readme_media (guards with count). ArduPilot demo: first curve at 184 px (was 271), rows above the plots 2 (were 4). e2e: test_plot_room +3.
- [x] FR3 Cursor labels off the curve; double-click plots a signal. The two cursors' labels sit in the axis margin or above the plot, not on the data. A double-click on a signal in the list adds it once (today it adds and removes). Done when: in the "Find out what went wrong" demo after "Put the cursors there", no label box overlaps the plot area between the cursors (e2e checks the boxes); a double-click on an unplotted signal leaves exactly one new legend chip (e2e); a single click behaves as before. Done 2026-11-16: TimeChart.drawCursor writes the cursors' times in the time axis' margin under the plot (one cursor: centred on its line; two: each on the outer side of its line) - `chartUtil.flag` takes a placement and returns its box, the layer keeps the boxes in `data-flags` (CSS px) for the tests; the values beside the curves (*Values on the plot*, off by default, the user's choice) are unchanged. DataPanel: the second click of a double-click does nothing when the signal is already in the active plot. Callers read: flag (drawCursor, drawValues; sweeps/groups.ts' flag is another function), the signal row's onClick (Ctrl / Shift / Alt paths unchanged), actions.toggleSignal (AnalysisPanel's own button unchanged). e2e test_cursor_labels (new).
- [x] FR4 One colour rule for two runs. Wherever one plot holds the same signal from two or more files, each line takes its file's colour (A blue, B rose...), in every way such a tab is made (Compare tabs, the sim-against-flight demo, templates over several files). Find why the sim demo colours by signal and remove that second path. Done when: in the "A simulation against its flight" demo every line of A is the file's blue and every line of B its rose, matching the A / B badges; a Vitest case covers it; a colour chosen by hand and a saved session keep their colours. Done 2026-11-16. Why the sim demo coloured by signal: templates.ts had its own same-signal test (the exact name after the file id) - the model's `ATT.Roll` and its log's `ATT.Roll [deg]` never matched, so every line got the next palette colour. Removed: that second path (`byFile` in applyTemplate); now one rule, `selectors.colorByFile` with one key `sameSignalKey` (the name without the file and without a trailing unit - `units.withoutUnit`, which DataPanel's `nameOnly` now is too), used by: applyTemplate (Compare tabs, templates over several files, the demo; a colour the template gives is kept), a signal joining its namesake (`sameNameByFile`: a colour not from the automatic palette nor the file's - set by hand - stays), *Colour by file* in the plot menu, CompareTable's plot (was palette by order), showSegmentPlot's fallback (the file's colour). ComparePanel's runColor already was the file's. Saved sessions keep their stored colours (nothing recolours on open). Tests: Vitest sameColour.test.ts, e2e test_file_colours.
- [x] FR5 A folder of recordings reads as recordings. A Sweeps table made by "From a folder of recordings" shows the steps Data -> Columns -> Limits -> Results; "Send runs", "Next runs" and the words "sets hold" are not shown for it; the status line counts recordings. The welcome demo opens with a next-step line and its answer is pointed at (X8-A's vibration: 18 -> 67 over six flights). Done when: the "A folder of recordings" demo shows no text about sets, sending or next runs; its line names the copter and has one button that shows it; test_folder_of_recordings and test_sweeps_flow are green; a results table and a study behave as before; en + he. Done 2026-11-16: `Study.recordings` (UI only, not saved - neither are the handed-over rows) set by `openRows` (its two callers: folderSummary.summarizeFolder and RunsMatrix - both tables of recordings); `isRecordings` = it and no study file open. Read by: FlowNav / StepFoot (`flow.flowSteps`: Data, Columns, Limits, Results - no Next runs), Navigator (no Send runs; the list's column *recordings*), SweepsStatus (*n recordings*, *n of N within the limits* only with limits), ResultsSide (no *Next runs suggests where*). The words: one mechanism - `i18n.Words` (a context of key -> key that useT reads), given by SweepsArea with `RECORDING_WORDS` (sweeps/i18n.ts: 18 keys, en + he) while such a table is shown. The demo: DEMO_STEPS.folderOfFlights (`area: "sweeps"` - its line is drawn in Sweeps, the recordings stage leaves it out), started by Welcome.openExample after the summary; *Show X8-A* asks the Data table (`rawAsk`, UI only) to sort by vibration_max descending and tick X8-A's rows (its six flights, 18 -> 67), then says *Open 6 in Recordings*. e2e: test_folder_of_recordings +3 (en + he; a results table keeps 5 steps and Send runs).
- [x] FR6 Sweeps: the answer in words, three equal starts. At convergence the loop's page writes the best set in words (Kp = ..., Ki = ..., Kd = ... and its value). The empty Sweeps screen offers three equal buttons - "I have results", "Start from nothing", "A folder of recordings" - with the examples under them. Steps 2 and 3 of a study with tables do not read "needs a table". The status line does not say "1 tables" with none open. The "Send runs" design of SF1 stays as it is. Done when: after "Run until converged" in the smart-sweep demo the page contains the three gains as text; each of the three starts is one click from the empty screen; test_study_demo, test_study_loop and test_sweeps_workspace are green; en + he. Done 2026-11-16: `LoopAnswer` (components/sweeps/LoopAnswer.tsx; the existing BestSet.tsx is another thing) - the best set as "Kp = …, Ki = …, Kd = …" and its value, a sentence once converged; used by the demo's loop (RunPanel.DemoControls) and a study's own (LoopSection - it replaced the strip's inline best). The empty screen (SweepsWelcome): three equal cards `.sw-way[data-start=have|nothing|folder]`, each one `.sw-start` button - *I have results* (opens a results table, as *Open a table* did; Send runs is filled from it when opened), *Start from nothing* (`startFromNothing`: Send runs at once), *A folder of recordings* (`fromFolder`) - with the examples under them (example table, two sweeps merged, three drones / the converging demo / the folder demo); New study… stays in Open ▾ and Ctrl+K; the old two cards' strings removed. FlowNav: a study with tables and none open says *open one of its n tables (Data)* (`flOpenOne`), not *needs a table*. SweepsStatus: *Study: name · 1 table / n tables · none open*. SF1's Send runs unchanged. Tests: test_study_demo +2 (en / he), test_sweeps_workspace +2 (its _new_study helper goes through Open ▾), test_calm_screen and test_sweeps_flow follow the new labels.
- [x] FR7 One formula evaluator. svcore/sweep/derived.py and svcore/sweeps_common.py evaluate through the whitelist of svcore/formula.py (extended with what Sweeps needs: if, in, text, bins, rank, pct) instead of walking the AST themselves. Every caller read first and listed in the task notes. Done when: one module owns the AST whitelist and the other two import it; every existing formula test passes unchanged; a new test proves that a name refused by one (__import__, an attribute, a dunder) is refused by all three entry points; mypy clean. Done 2026-11-16. One module owns the AST whitelist: `svcore.formula.check(tree, rows=…)` - the nodes, operators, constants, calls and no name with __ (anywhere), for a signal formula (`parse`, unchanged messages) and a Sweeps row formula (`parse_rows`: text in quotes, in / not in, lists, `if(` read as `_if(`, `ROW_FUNCTIONS` incl. where, between, contains, text, bins, rank, pct, col); `split_and` / `margin_of` (a constraint's parts and margins) moved there from sweeps_common. derived.row_formula parses through parse_rows (FormulaError -> DerivedError "Formula: …") and only gives values (its FUNCTIONS asserted equal to ROW_FUNCTIONS); sweeps_common no longer imports ast. Closed a gap: a dunder name was read as a column of that name. Callers read (all unchanged): formula.evaluate / parse / FUNCTION_NAMES / syntax_message_for - conditions.py, transforms.py, analysis.py; row_formula - routes/sweep.py (preview, new column), sweep/evaluate.py (new columns, goals), sweeps_next.py (constraints of the next runs), sweeps_common.py (check, objective); _BIN / _CMP / bool_op - derived.py. Tests: every existing formula test unchanged and green (test_sweep_formula, test_formula_messages, test_sweeps_common, test_sweeps_next, test_sweep, test_conditions, test_backend, test_missing_policy, test_sweep_table_tools); new tests/test_one_whitelist.py (__import__, attributes, dunder names - also as a real column -, subscripts, lambdas, keywords, generators refused by formula.evaluate, row_formula and sweeps_common.check). mypy clean.
- [x] FR8 The handoff reads in five seconds. "Current state" in docs/dev/TASKS.md becomes a table of what is open (task, status, next step) of at most 30 lines; finished history moves to the Log or stays in git. Done when: the section is 30 lines or fewer and a reader can name the next task from it alone. Done 2026-11-16: the section is a 12-row table of open items (19 lines); SW2 (b) and BR1 kept whole under "Open specs"; the history in git (the Log names the commit).

Decisions, not code - ask the owner before doing any of these:

- [-] FR9 (ask) Run quick_check and the short e2e list in CI on every push to main (today CI is manual). Owner (2026-11-16): not now - CI stays manual.
- [x] FR10 (ask) Take frontend/dist and site/ out of git and build them in the release job; this changes the installer and pip builds and removes the "no build in a parallel lane" rule from CLAUDE.md. Owner: yes (2026-11-16). Done 2026-11-16: `frontend/dist/` and `site/` untracked and ignored (site/ was a committed MkDocs build nothing read - docs.yml builds its own for Pages; build.yml already built the UI before every package and the wheel). run.py: one rule, `ui_is_current` (its stamp in frontend/dist names the sources, or a hand build newer than every source) - the git-history check (`committed_dist_is_current`, `_git`) and `.local-dist` removed; a fresh clone builds on the first start, and says what to do without Node.js. build.bat / build.sh / make_windows_portable build the UI when it is missing. CLAUDE.md: the "no build in a parallel lane" rule replaced. Docs: install, development, CONTRIBUTING, the PR template, ci.yml comment, TASKS Releasing / practical notes. Tests: backend test_launcher rewritten (fresh clone, hand build, --no-build, no npm); a fresh-clone start checked by hand (built, served).
- [x] FR11 (ask) Cut the welcome cards from eleven to six, the rest under Help -> Examples. Owner: "six is ok but one of them needs to be a Sweeps example" (2026-11-16). Done 2026-11-16: `Welcome.FEATURED` = ardupilot, investigate, simVsFlight, twoFlights, folderOfFlights, smartSweepDemo (the Sweeps one), in that order, still grouped Recordings / Sweeps; a line under them points to Help → Examples, which already listed every example (the TopBar menu, unchanged). Callers: tests click cards by `data-example` - one helper `test_features.open_example` (card, else Help → Examples) used by 12 e2e files; tools make_readme_media / make_demo_video / count_controls open the moved ones from Help. Docs: GUIDE en + he, command-line, features. Open: the welcome picture (38_welcome_cards) shows eleven - retake with the release's pictures.
- [x] FR12 (ask) Rename the e2e files named after rounds (test_release_1_21, test_round_1112, test_owner_notes_1_20) by the feature they cover, and update docs/dev/E2E_MAP.md. Owner: yes (2026-11-16). Done 2026-11-16: `test_release_1_21` -> `test_tuning_tools` (filter review, step response, Hardware tab, Compare's time tolerance); `test_round_1112` -> `test_map_places_story_export` (all the Map: export, hidden objects, flat map, places, icons, the 3D page, the story); `test_owner_notes_1_20` (four unrelated features) split into the feature files: test_plot_polish, test_name_tree, test_map_objects, test_sweeps_flow. Tests unchanged; references updated (E2E_MAP top note, tools/make_live_report_media). The Log keeps the old names of its time.

End of the round: `npm run build`, the whole e2e suite, quick_check; the Log says which e2e ran. The version is not updated - the owner tags.

## Milestone 35 — 1.29.0: Sweeps - exact numbers and the whole table drawn (owner, 2026-11-17). Board: TASKS.md "Current state".

On a big table Sweeps drew a random sample of the runs (above 50,000) and several things the user sees or does were computed from that sample without saying so. Decided with the owner (2026-11-17): HiPlot's approach in our own code (not the hiplot package: unmaintained, no RTL / themes / groups) - every row sent to the page once up to a cap set in Settings, filtered there, drawn progressively; above the cap a sample of the rows the filters keep, said on screen; every action that turns the brush into a result is resolved by the server on the whole table. **An owner-approved exception to CLAUDE.md's "the UI receives decimated data only", for the Sweeps tables (owner, 2026-11-17).**

- [x] FT1 Correctness: the brush of All runs resolved on the whole table. Keep, Exclude, Save as group and Export shown in All runs send a selection description and the server resolves it on every run - no set or row list collected from what is drawn. Done when: a guard test runs the flows with the cap forced tiny (300) and with none and gets identical results (sets kept, runs exported, counts); e2e on a 200,000-row table: a brush on a run's own columns -> Keep keeps exactly the right sets, Export shown writes every matching run; Parameter sets behave as before. Done 2026-11-17: `svcore/sweep/select.py` (`run_mask`, `selection`: the filters on the runs' columns, a text column's by its labels, numbers compared as Float32 like the page, plus the sets the page shows) - one function for `/api/sweep/select` (new: the sets and the count) and `/api/sweep/export-rows` (`select`: the runs a description selects). The page: `sweeps/selection.ts` (`describeRuns` / `runSelection`: Show, the keep / exclude steps, hidden groups and the per-set columns #set / #holds / #group decided over every set - exact, the answer has every set; the other filters sent; `saveBrushGroup`). ResultsCenter's Keep / Exclude / Export shown and GroupsPanel's Save as group use it in All runs; Parameter sets keep the page's own (exact) path. Save as group in All runs with a filter on a run's own column (a scenario, an output per run) saves the sets the server finds, frozen - a live rule is over the sets and could not mean "has such a run"; a brush on parameters only stays live as before. Category codes now come from the whole column (`encode(values, whole)`, `category_labels`: FT3 needs it; the labels are the same as before for an unsampled column). `RUNS_MAX` in routes/sweep.py (the cap of All runs; FT3 makes it the Settings value). Callers read: narrow (ResultsCenter only), exportRows (ResultsCenter; RerunList / ReportDialog use sets), saveGroup (GroupsPanel; tests), encode (every route that sends columns - the labels of an unsampled column unchanged), run_rows (evaluate). Tests: backend test_sweep_select (selection = brute force, codes from the whole column, the tiny-cap guard); Vitest selection.test.ts; e2e test_sweeps_big_table (new, 200,000 rows; `__svSweeps.filter` sets an exact brush).
- [x] FT2 Drawing: ParallelPlot in layers, progressive. Two canvas layers - background (lines not kept, drawn once per data / axes / zoom / filter end, itself progressive) and foreground (kept lines) - drawn in chunks per animation frame, cancelled when the inputs change; hover and the picked line on a third small layer; while a brush is dragged only the foreground is redrawn; lower alpha when many lines are kept. Done when: measured in the real app (Playwright, 200,000 rows, DPR 1 and 2): time to the first picture, the full picture, the brush's response, the longest frame - written in the task's Log; no frame over ~50 ms while brushing. Done 2026-11-17: ParallelPlot - the lines left out and the lines kept are drawn into two detached canvases (`lineLayer`), 500 lines a stroke, ~6 ms a frame each (`sweeps/progressive.ts` `runProgressive`: the first frame at once, cancelled when its inputs change; `flush` - a 1-pixel read after each chunk - because a canvas only records strokes and draws them when shown, so without it the budget measured the recording and the frame that showed it was long), in a fixed shuffled order (`drawOrder`) so a part already looks like the whole; the one canvas on screen (tests and tools still find `.pp canvas`) puts them together under the overlay (axes, histograms - now worked out once per filter -, filters, the brush, the open set, hover), which alone is redrawn on hover and while a brush is dragged (a brush changes the filters only when released, as before). The lines left out are drawn at any number now (they were skipped above 60,000); alpha 0.06 above 100,000 kept lines; above 20,000 lines the layers are drawn at 1 px per CSS pixel (DPR 2 cost 4x for no visible gain at that density). `canvas.dataset.drawing` = 1 while lines are being drawn (the measurement reads it). Found on the way: `groups.setIds` was worked out for every set on every filter change through a default parameter (~100 ms at 50,000 sets) - now kept per answer (WeakMap). Measured with `tools/measure_sweeps_plot.py` (new; numbers in the Log). Callers read: ParallelPlot is used by ResultsCenter and RawPlot (props unchanged); setIds' callers read the array only.
- [x] FT3 Data and the cap. /api/sweep/raw and the runs of All runs send every row up to the cap (Settings: *Most lines to draw*, default from FT2's numbers, raisable to no limit with a warning); above it the server filters the whole table and samples from the rows kept (plus a little background), the picked run / open set always in; counts ("n of N") always of the whole table, from the server; the sample said in the Data step too. Done when: backend tests (whole-table counts, the sample from kept rows, the same category codes between requests, the picked row always in); e2e: exact "n of N" after a brush, the sample hint above the cap and gone when the filter is narrow, raising the cap draws more lines; old settings files open. Done 2026-11-17: Settings → Working → *Sweeps: most lines to draw* (`sweepLines`, ui slice + settings.ts; 50,000 / **200,000** (default: FT2 measured the full picture in 2.4-4.5 s without a graphics card) / 500,000 / 1,000,000 / No limit (0) - above a million or no limit the hint warns about time and memory); an old settings file has no `sweepLines`: the default. Backend: `select.sample_rows` (every row up to the cap; above it the rows the brush keeps - all when they fit in 90 % of the cap, else a sample, one run of each set first - plus 10 % background (`BACKGROUND`), plus the picked run / the open set's runs), `select.frame_mask` (the Data step's filters on the table as read); `run_rows(..., keep, must_sets)`; `/api/sweep/evaluate` (runs) and `/api/sweep/raw` take `cap`, `select` / `pinned` / `picked` and answer `cap` and `kept` (the whole table's count); a text column's labels from the whole column, kept per table version (`_encode_part`, `t["cats"]`); `RUNS_MAX` (the default when a page sends none) 200,000. The page: `state.drawOf` (the cap, `runSelection`, the open set and their key) with `evaluate`, and `refreshRuns` - All runs above the cap asks again 250 ms after the brush, the open set or the cap change (only `answer.runs` is replaced); RawPlot asks `/raw` with the cap and, above it, again for its filters and picked run; the count is the server's above the cap (shown as … until the answer for the brush now arrives, `data-exact`), the page's own below; `swSampled` says *a sample of those the filters keep* and shows only while kept runs are left out of the drawing. PlotToolbar's `shown` may be null (waiting). Callers read: sweepApi.raw (RawPlot only), sweepApi.evaluate (state.evaluate, refreshRuns; split.ts asks sets only), Answer.runs (modeColumns, SweepsArea), Settings rows. Tests: backend test_sweep_select +2 (the sample from kept runs, the count, the open set, cap 0; raw: kept rows all drawn, picked row in, labels the same); e2e test_sweeps_big_table +1 (Data step: the hint at 50,000, exact count after a drag, No limit draws every kept run) and the All runs test now sets the cap in Settings and checks the exact count and the hint going away.
- [x] FT4 The HTML export of a table / the report's plot: every row up to the cap inside the file, drawn the same progressive way. Done 2026-11-17: `/api/sweep/export-table` (html) and `/api/sweep/report` (raw plot) take `cap` (`_drawn`: every row up to it, a sample in table order above it; was a fixed 50,000 sample); the Data step's export sends the Settings value. The page's script (`sweep_report._PAGE`, also the report's plot of the sets): the lines in two layers (left out, kept) drawn ~8 ms a frame in a fixed shuffled order with the same flush, put together under the axes, filters and the brush - `show()` alone while a brush is dragged, `refilter()` once on release, `layers()` on zoom / pan / colour / resize; each column's range worked out once (`range`; it was scanned for every point of every draw); `#cv[data-drawing]` as in the app. Tests: backend test_sweep_select +1 (rows in the page by cap); e2e test_sweeps_big_table +1 (No limit: the 200,000-row page draws to the end and counts every row); test_sweeps_flow / _charts (their HTML exports) green; a brush on an exported page checked by hand (12,000 -> 5,607, no script error).
- [x] FT8 The rule and its guard (owner, 2026-11-17: "in analysis it is critical to see every point - a skip can hide the problem"; the rule is in CLAUDE.md). `tests/e2e/test_needle.py`: one extreme point / one short spike in a big recording or table, checked to be drawn - in the pixels or the drawing's own record - in the time plot, the X-Y plot, the 3D plot, the Sweeps parallel plot (Data step, Parameter sets, All runs), the histogram and the scatter of Charts. Done when: every view passes (each fix below turns its test green). Done 2026-11-17: backend tests/test_needle.py (7) and e2e tests/e2e/test_needle.py (2); the Charts' part is FT6.
- [x] FT7 X-Y and 3D plots of a long recording keep every excursion: `analysis.xy_pair` and the 3D track thin by a plain stride (16,000 / 20,000 points) - replaced by extreme-keeping thinning along the path (per chunk of samples: the first, the last and the samples of min / max x and y, in time order), again at the new resolution when zoomed. Done when: the needle test of X-Y and 3D passes; a 1-hour 400 Hz log draws as fast as today (measured). Done 2026-11-17: one function, `svcore.decimate.path_thin` (and its twin on the page, `frontend/src/thin.ts` `pathThin`), used wherever a path or a trace was thinned by a stride - found by searching the backend and the UI for strides, `linspace` picks and `% step`: X-Y (`xy_pair`: Y aligned on every sample of X first, then thinned on both), the 3D plot (`xyz_track`), the map's object track (`track_of`: on latitude, longitude and height - every jump kept; the other signals then put on the samples kept), the objects' value / error traces (`objects._thin`), the Monte-Carlo envelope (its min / max band from every sample of every run, not only those at its 2,000 grid points), the 3D globe's drawn track and its fit-to-view (Globe3D), the 2D map's receiver fixes (GeoChart), What changed's sparklines; `relation.errorAlong` computes its median / 95th percentile on every sample of the track it has (it took every n-th), only the drawn rows thinned keeping the largest errors. `stride_decimate` removed (no caller left). Not changed (already keep extremes or are not pictures of data): time plots and spectra (min/max per pixel), the spectrogram (max per pixel), Compare (all samples, C1), the clusters' 20,000-set limit (said). Measured, 1 hour at 400 Hz (1.44M samples): X-Y 19 ms (was 1), 3D 42 ms (was 26), envelope of 6 runs 164 ms (was 69) - each well under a frame of the request it serves. Tests: backend tests/test_needle.py (7: time plot, X-Y, 3D, map track, objects' error, envelope, path_thin), Vitest thin.test.ts; e2e (maps, 3D, objects, relations, What changed, aligned plots, features, less clutter) 208 green.
- [x] FT6 Exact Charts in All runs: the histogram counts, box statistics and correlations of the runs computed by the server on every run the brush and Show leave (one endpoint over `run_mask`); the scatter drawn as density + every point of a sparse cell (as FT5). Parameter sets' charts are exact already. Done when: the needle test of the histogram and the scatter passes above the cap; a test compares the server's counts with numpy on the whole table; the *sample* hint above Charts (swChartsSampled) goes. Done 2026-11-17: `/api/sweep/run-charts` (the brush, the sets the pane shows - keep / exclude steps, hidden groups, its group -, the colour series as the density's) answers per pane, on every run: `hist` (counts per series over the scope's range; a text column per label), `box` (per series; the points beyond the whiskers - the furthest out on each side when there are more than 200), `corr` (coefficients, the diagonal histograms, each cell's 40 x 40 counts + its sparse points), `history` (the runs in table order, min/max per pixel as a time plot - every peak - and the best so far), `scatter` (120 x 120 cells over the whole table's domain + the sparse cells' runs with their size and colour values). The page: `sweeps/runCharts.ts` (`useRunCharts`: only in All runs when not every run is on the page - else the charts work it out as before; asked 150 ms after a change, the previous answer kept until the new one); Histogram, BoxPlot, Matrix, History and ScatterPanel use it; the Matrix's cells no longer draw every m-th run (also with every set on the page: above 3,000 a cell is 40 x 40 shades + the rare points, below every point); the lines pane gets the density (with a group of its own above the cap it says to use Show: that group - its runs are not all on the page). `swChartsSampled` removed. Tests: backend test_sweep_select +2 (every count against numpy, the needle in the box's outliers and the scatter's points; a group and a brush; history keeps the peak); e2e test_sweeps_big_table: the histogram's bars add up to the 200,000 runs with a sample and with density.
- [x] FT5 Density drawing of the parallel plot above the cap - **the default** (owner, 2026-11-17), the sample kept as a choice in Settings (*Above the cap: density (every run) · a sample*). The server counts, per pair of adjacent axes, the runs through each pixel cell (kept and left out apart, a colour group each), the page draws the cells as shaded bands, and the runs in sparse cells (outliers) one by one; filters stay exact (server); zoom / resize asks again at the new resolution. Done when: the needle test of the parallel plot passes above the cap (Data step, All runs); the counts match; brushing stays smooth (measured like FT2); old settings files open (the default: density). Done 2026-11-17: server - `svcore/sweep/density.py` `parallel` (per pair of neighbouring axes the runs per cell pair, kept by colour series and left out apart; every kept run in a cell pair of at most 3 runs - the outliers - returned to draw as a line, the threshold lowered when that is more than 20,000), `domain` / `axis_cells` (each axis cut as the page's scale cuts it: a text column by its labels, a category / ordinal number axis by its values, linear / log in 64 even cells over the whole table's domain - arithmetic, not a search: 1M runs x 12 axes in ~0.3 s); `/evaluate` (runs) and `/raw` take `over` (density | sample), `axes` [{column, scale}] and `colour` ({column} a text column, or {sets} a code per set for a flag / the groups) and answer `density` + the outliers' and the open set's / picked run's rows as lines; every number column comes with its `domain` of the whole table (`_domain_of`; labels and domains kept per table object - `_kept`, dropped with the table: an id used again starts empty). Page - Settings → *Sweeps: above it, draw* (`sweepOver`: Every run (density) - default - / A sample; an old settings file: density); `Col.domain` → `makeScale` builds an axis from the whole table (it was the runs received: an outlier missing from a sample shrank the axis); the scoped columns keep their own range when every run is on the page (Keep still rescales as in HiPlot); `drawOf` / RawPlot's `spec` send the axes and the colour (`selection.axesSpec`, `colourSpec`) and ask again when they change; ParallelPlot draws `density` as bands under the lines (grouped by colour and 6 shades of log(count), each group one stroke, in the progressive layers; the left out grey in the back layer) and its axis histograms from every run's cell; `data-density`, `data-shown` = the whole table's count; the hint *Every one of the N runs is in the picture…* (`swDensityHint`). A new picture keeps the previous one on screen until it arrives (the count shows … meanwhile). The density is one colour when the colour is a number column (the outliers keep their colours). Callers read: ParallelPlot props (ResultsCenter, RawPlot), makeScale (every Sweeps axis: sets mode has no domain - unchanged), scopedColumns, drawOf / refreshRuns, Settings. Tests: backend test_sweep_density (4), test_sweep_select +2 (density: every run counted, the needle a line, the open set's runs, domains; raw) and the tiny-cap guard also in density mode; e2e tests/e2e/test_needle.py (the needle in the pixels: Data step and All runs; A sample said), test_sweeps_big_table now asks for *A sample* where it tests the sample.
- [x] FT9 Filters remember the tab they were made in (owner, 2026-11-17: yes, in 1.29.0). A filter made in **Parameter sets** acts on sets: on a parameter it is the same in both tabs; on anything per set (an output's mean / worst case, the goal, a condition's margin, rank, score...) it keeps sets - in **All runs** it shows **every run of the sets it keeps** (today it is applied by name to the runs' own values, or ignored when All runs has no such column - unsaid). A filter made in **All runs** acts on runs; in Parameter sets it keeps the sets with at least one run that passes (the rule Keep in All runs already uses). A chip above the plot says what applies across tabs ("Sets: mean error <= 5 -> 3 sets, all their 300 runs" ×). A **holds axis by default** when the goal has conditions, reading ✓ holds / ✗ fails. Done when: backend test (a sets filter on an output -> every run of those sets, exact counts), Vitest (a filter made in one tab carried to the other), e2e (filter an output in Parameter sets -> All runs shows all runs of the kept sets, exact "n of N"; back again); old studies open (their filters: made in Parameter sets); Keep / Exclude / groups / Export / the density and Charts requests use the same resolution (selection.ts `runSelection`, svcore/sweep/select.py). Notes: TASKS.md "FT9 notes".

## Milestone 36 — 1.29.1: steadier under load, a smaller download, a cleanup (owner, 2026-11-18). Board: TASKS.md.
- [x] CL2.1 The examples' recordings written by code on first use (svcore/example_data); the packages carry none.
- [x] CL2.2 Heavy computations a few at a time (app.common.heavy, SV_HEAVY_JOBS); the store's lists and new signals' names safe under concurrent requests (test_concurrency).
- [x] CL2.3 The template library's races (the latest reload wins, the note after the binding, a failed binding).
- [x] CL2.4 routes/sweep.py split (sweeps_templates, sweeps_report); unused imports; ROADMAP reconciled; test_globe3d's readout test made exact.
- [x] CP1 Copy a plot or a tab for a Confluence page, every sample interactive (owner, 2026-11-18: his HTML macro is on; a 4 MB page in the macro stalled his editor; then: "all the resolution, interactive"). The page with every sample (app/report.py build_clip_page: the report's page, the raw samples as the finest zoom level after the min/max ones) is saved and dragged onto the Confluence page (an attachment); the macro gets build_clip_macro's few lines: fetch /download/attachments/<ajs-page-id>/<name> into an iframe srcdoc (isolated; found by place, so one copy pasted twice works; a message when not attached). build_clip_static: picture + statistics + notes, inline styles (text/html). /api/export/clip; frontend/src/clip.ts; the plot's ⋯ menu, the tab's right-click menu, Ctrl+K. Tests: backend tests/test_clip.py, e2e tests/e2e/test_confluence_copy.py (a stand-in Confluence page serving the attachment). Measured: 2,000,000 samples = 35 MB attachment, shown in ~3 s, zoom to single samples. Also: negative numbers in a Hebrew report's table read left to right.
- [x] CP2 Copy a line / a whole plot to another plot (owner, 2026-11-18): layout.copyPlotInto (an empty target becomes a clone with the target's id; else mergePlotInto keepSource); dropSignal across tabs; the plot's ⋯ *Copy to…* (other plots, New plot on this tab, New tab - movePlotToTab copy), Ctrl+drop of the ⠿ on a plot, the chip's *Move to plot* / *Copy to plot*. Tests: movePlots.test.ts, e2e test_move_plots.py::test_copy_plot_and_a_line_to_another_plot.

## RE1 - 1.31.0: the report as a document you write (owner, 2026-11-18). Design: docs/dev/REPORTS.md.
- [x] RE1.1 MVP (1.31.0; the syntax simplified to [[tab.plot]] and {{ max(Roll) }} by name): the report screen, Markdown, fields stat / table / plot / tab / notes / meta, broken references, `ws.report.doc`, the default document (the side panel absorbed), HTML / PDF / Word by one path.
- [x] RE1.2 The investigation in the text: conditions (when=, stretches, holds), formulas, variables, findings, process / verdict; the Insert list with drag, *Add to report* (plot, tab, Ctrl+K). Not done: chips over the text (plain textarea).
- [ ] RE1.3 The document in a template, applied to a new recording: done in 1.32.0 (RE2: `report` in a template, signals by name). Left: the CLI batch makes it.
- [ ] RE1.4 Math, callouts, page breaks: done in 1.31.0. Left: the outline, figure / table numbering.
- [ ] RE1.5 Markdown + images export; Copy for Confluence of the document.
- [ ] RE1.6 Sweeps results as fields (a snapshot, refreshed when the study is open).
- [x] RE1.F Hebrew in PDF / pictures printed backwards with matplotlib 3.11 (libraqm orders it; report._bidi now only without it).

## RE2 - 1.32.0: ready reports made of ready-made parts (owner, 2026-11-19). Design: docs/dev/REPORTS.md.
- [x] RE2.1 Paste tables (Word / web HTML, Excel TSV) as Markdown; pictures pasted / dropped / chosen kept in the session (`ws.report.assets`), in page, PDF and Word; a PDF table goes on over pages.
- [x] RE2.2 Commanded vs actual `[[tracking]]` (pairs: Python twin of desired.ts, shared cases; error, delay, steps' overshoot / settling, tolerance pass / fail); `[[plot A, B]]`.
- [x] RE2.3 `[[differences]]`: overall and in-region difference, the central region, first divergence, zoomed plots, states and parameters that differ; the baseline guessed by name.
- [x] RE2.4 `[[states]]`, `[[trajectory]]`, `[[moments]]`, `[[navigation]]` (objcompare; reference guessed, per file).
- [x] RE2.5 The library: ready reports (auto / control / navigation / compare), parts by category with the reference / baseline choice, `[[summary]]`, the user's report templates, a session template carries the report; demo recordings examples/report_demo. Left: the CLI makes the written report.
- [x] CLR1 Clear and the report (owner, 2026-11-19): Clear → *The report* (text + pictures, asks, one Undo), *All tabs* / *the work* say when the written report pointed at the cleared tabs (+ *Clear the report too*), the Report screen's ↺ menu: *Empty* / *Back to the report from the tabs*; Ctrl+K. e2e test_report_doc.
- [x] MSG1 Messages in a byte stream (owner, 2026-11-19): svcore/bytestream.py (header, length / type / fixed, type byte, checksum sum8 / xor8 / -sum8 / ~sum8 / CRC-16 CCITT / Modbus / Fletcher-16, resync, a direction column), the op `messages`, *Decode as messages…*, `[[messages]]` + the ready report *Link review*, the demo examples/serial_link (TX / RX two signals, mixed with dir, columns).
- [x] MSG2 Messages to signals (owner, 2026-11-20): svcore/protocol.py (binary / text structures, NMEA built in, parse, suggest - fields LSB / MSB, signed, i32, f32, counter, flags), /api/messages/{suggest,parse,structure,nmea}, the .nmea reader, the dialog's structure editor (form / JSON, .svmsg.json), recordings re-made with the session, examples linkStructure and gpsNmea.
- [x] LINK1 Listen to a link (owner, 2026-11-20): svcore/rawlink.py (serial / UDP / TCP / TCP-in -> .svraw, the structure beside it), the .svraw reader (by its structure, else bytes), live follow (read again whole), /api/link/*, Live ▾ → Listen to a link, tools/send_link_demo.py.
- [x] MSG3 One home for messages (owner, 2026-11-20): the Messages panel (rail, beside Investigate / Report) - the open files' byte streams (/api/messages/streams, grouped by their definition's key; each opens into the stream editor: definition, structure, Plot the messages / Make the recording / Add to the report), the logs' message types (tlog / bin / ulg / mcap / svraw / recordings from messages: fields, count, rate; a click plots), what is running (link, MAVLink - read-only, Live ▾ starts / stops), the structure library (app/routes/messages.py: NMEA built in, ~/.signalviewer/structures/*.svmsg.json, the readers folder's ICD layouts; get / save / reveal) also in Live ▾ → Listen to a link; the dialog removed (right-click opens the panel: msgFocus); a .svraw without its structure offers the panel; `[[messages a, b]]` filters by either name. e2e test_messages (7).
- [x] MSG4 From raw bytes to variables, guided (owner, 2026-11-21: "alone it was not clear how"): the stream editor as four numbered steps (what it carries · the messages in the bytes · the variables · the recording); svcore/msginspect.py + /api/messages/inspect (patterns 2-4 bytes with count / regularity / role, the first frames with each byte's role and each field's value, the whole stream counted); ByteView.tsx (a click on a byte: header / length / type / footer / a value of a type / not a value - messages.ts applyRole, Vitest); the template proposed on opening; Save as a file (CSV / Parquet / MAT / HDF5); protocol.frames_binary shared with parse_binary. Tests: backend test_msginspect (4), Vitest messagesRole (4), e2e test_messages::test_guided_steps_from_raw_bytes_to_a_csv; picture 56.
- [x] RE3 LaTeX in the report (owner, 2026-11-21: "full LaTeX like Overleaf, everything offline"): svcore/latex.py (the computer's TeX: engines, latexmk, converters; compile with errors at a line; formula / block snippets as SVG / PNG), app/reportlatex.py (Markdown -> a LaTeX project; a LaTeX document with [[ ]] / {{ }} written as LaTeX, line map; preview PDF by token; Markdown -> LaTeX conversion), reportdoc: ```latex blocks and formulas mathtext cannot read drawn by TeX in page / PDF / Word; formats tex (.zip) and texpdf; Report screen: Written in Markdown / LaTeX, PDF (LaTeX), LaTeX (.zip), the LaTeX toolbar, the PDF preview with the error's line. Tests: backend test_report_latex (5), e2e test_report_doc::test_latex_report_written_in_latex_typeset_offline. Design: docs/dev/REPORTS.md RE3.
- [x] Release 1.33.0 (2026-11-21): MSG4, RE3, the agent skills (sv-flow, sv-patch, sv-ui, sv-messages); fixed the Sweeps step undone after a loop round (test_study_loop).
- [x] RE4 The built-in LaTeX (owner, 2026-11-22): Tectonic + a small TeX Live bundle (tools/get_tectonic.py, tools/make_tex_bundle.py, build.yml job tex-bundle); MathML for formulas with no TeX (latex2mathml). Tests: test_report_latex.
- [x] HL1 One zoom for the HTML page's time plots (owner, 2026-11-22: "in the HTML export, can all the plots be linked when zooming"): viewer.js - a tab's time plots share the x zoom (box, wheel, double click) and the cursor; the 🔗 button (shown with two time plots or more) unlinks; linked again, all go to the first one's range; a replay page keeps its own (RP.link). Tests: e2e test_report_linked_zoom.
- [x] CP3 Copy for Confluence through a user macro (owner, 2026-11-22: Confluence 10.2, interactive as the HTML page): one macro script for both ways (data-name / data-page / data-ctx / data-lang, Velocity-safe), report.build_user_macro_template (## @param file, height; $content.id, $req.contextPath), build_clip_markup ({signalviewer:file=...|height=...}), GET /api/export/clip/user-macro, ClipRequest.macro; Settings: Copy for Confluence HTML macro / Signal Viewer macro + Save the macro for the administrator (settings.ts confluenceMacro). Tests: backend test_clip::test_user_macro_template_is_velocity_safe_and_the_copy_is_its_markup, e2e test_confluence_copy::test_copy_for_confluence_with_the_signal_viewer_user_macro.
- [x] MSG5 Any column is the direction (owner, 2026-11-22: "any column with several values, the user says which value is TX and which RX"): bytestream.direction_values (2..32 values with counts), POST /api/messages/direction-values, MessageStream.rxValue (absent: every other value is RX, as before), streamsOf / reportparts.defined_streams, StreamEditor: any column, TX and RX from its values, the bytes in neither said. Tests: backend test_bytestream (2 new), e2e test_messages::test_any_column_says_the_direction_the_user_picks_tx_and_rx.
- [x] MSG6 The time tells the header from the footer (owner, 2026-11-22: "the automatic detection took the footer for the header too - maybe by time"): bytestream.pauses / by_time (a pause: > 4 x the usual step, or any step when bytes are stamped per packet; none when no pauses), decode scores each header pair by its share right after a pause minus right before one (22 of 24 wrong -> 0 of 24 on a recording started inside a message), msginspect patterns: afterPause / beforePause / time, a pattern across a pause dropped, inspect.pauses; StreamEditor: the chips and a line. Tests: backend test_msginspect (2 new), e2e test_messages::test_the_time_tells_the_header_from_the_footer_on_screen.
- [x] MSG7 What passed, in order, how often, and one message's variables (owner, 2026-11-22: "plot which messages passed in order, a histogram; choose one message type and get its variables"): protocol._sequence -> the recording's `message` (labels: the structure's names, then "? 0x20" / "? GSV" for types it does not describe; bad frames not in it), parse params.skip (values left out, report.skipped); StreamEditor step 4: the list (count, share bar, in the recording, Plot), messages.plotMessage, plotTabs lanes (sharedStates). Tests: e2e test_messages::test_messages_in_order_counted_picked_and_one_plotted.
- [x] MSG8 Hex, numbers, ASCII; double, text and a formula (owner, 2026-11-22: "convert hex to double and ascii, sometimes both"; "a variable of two bytes LSB / MSB with a conversion formula; 8 bytes to a double; is it clear"): ByteView Hex / Dec / ASCII / Hex + ASCII (byteShow, a setting), readsAs on each byte, the menu's choices with their value, f64 LE / BE, Text (ASCII) to the end of the values or 4 / 8 / 16; protocol: ascii fields (size, a state of its texts), convert() - a field's formula on x by the row formulas' whitelist (sweep.derived.row_formula), checked in check(); StructureEditor: ascii's size, the Formula column, a title per type. Tests: backend test_protocol::test_double_ascii_and_a_conversion_formula, e2e test_messages::test_bytes_as_hex_numbers_ascii_a_text_field_and_a_formula.
- [x] CP4 Send to Confluence (owner, 2026-11-22: "the most important now: a good way to throw an interactive plot from the app straight to Confluence, the easiest way"): app/confluence.py - REST API (Data Center / Server: a personal access token, Bearer; Cloud: e-mail + API token, Basic), a page's id from any of its links (pageId, /spaces/KEY/pages/ID, /display/KEY/Title by lookup), the attachment (new, or a new version of the same name), the macro (HTML or the Signal Viewer user macro, storage format) added at the page's end unless shown already; errors that say what to do (401, 403, 404, 413, unreachable); ~/.signalviewer/confluence.json (0600; the token never back to the page); SV_OFFLINE blocks it. Routes /api/confluence (get / set / test / open), /api/export/confluence; clip.ts sendToConfluence (the last page offered); Settings -> Confluence; plot / tab / Ctrl+K. Tests: backend test_confluence (3, tests/fake_confluence.py), e2e test_confluence_copy::test_send_to_confluence_from_the_app.
- [x] MSG9 The proposal and the form (owner, 2026-11-22: "yes - then release"): bytestream - a type rule that gives every value one length is a fixed length; with one length for all, a type byte must change often (not a slow value's high byte); protocol._guess_fields - a 16-bit counter (carries), a double, text; no 00 / FF footer; ByteView *Not the type byte* (applyRole notype); the Messages panel its own width (520). Tests: backend test_protocol::test_the_proposal_reads_a_counter_a_double_and_text, e2e test_messages::test_not_the_type_byte_makes_one_kind_of_message.
- [x] Release 1.34.0 (2026-11-22): CP4 Send to Confluence, CP3, HL1, the XY zoom, RE4 the built-in LaTeX, MSG5 - MSG9.
- [x] CP5 Drag a plot or a tab out (owner, 2026-11-22: "hold the plot or the tab by its grip and drag - HTML by default, else ask how"): clip.ts dragOutStart / dragOutEnd - DownloadURL (the page as a file, fetched from /api/export/drag/<token>/<name> at the drop), text/html (its picture from the canvas), text/plain; after a drop outside the app a toast offers Send / Copy for Confluence; the plot's grip and the tab; internal moves unchanged. Tests: backend test_clip::test_a_plot_dragged_out_is_its_page, e2e test_confluence_copy::test_drag_a_plot_or_a_tab_out_of_the_window; test_move_plots, test_move_plots_tabs, test_features green.
- [x] CP6 Where on the Confluence page (owner, 2026-11-22: "how do I control where on the page it goes?"; "after it is in Confluence, can it be copied and moved?"): confluence.place - a marker [[signalviewer]] / [[signalviewer: title]] (its paragraph replaced), else end / start / under a heading (before the next of its level); /api/confluence/outline (headings, marker, shown already); the send asks (Overlays.choose); the HTML macro carries data-page (a copy on another page shows the file from the first). Drag out: text/uri-list ?view=1 - a browser opens the page. Tests: backend test_confluence (6), test_clip; e2e test_confluence_copy (4).
- [x] CP7 Copied pictures at high resolution (owner, 2026-11-22): Settings copyScale 1 / 2 / 3 (default 2); POST /api/export/image-bytes (build_image at scale); Copy image through it (the canvas at 1, and for a map / 3D view); ClipRequest.scale for the static copy. Tests: backend test_clip::test_copied_pictures_at_high_resolution; e2e test_features, test_settings, test_confluence_copy.
- [x] Z1 The values axis zooms everywhere (owner, 2026-11-22: "I still cannot zoom on y, only x - fix it everywhere"): chartUtil BoxZoom / zoomRange / boxZoomSelect / attachBoxZoom - XY, FFT (a log axis in decades), step response, envelope (its x the tab's window); viewer.js - one wheel for every plot, a time plot's values by an up / down drag or the wheel over its axis, FFT / step / envelope a box; the wheel's keys as on a time plot (Shift values, Alt x, Ctrl both). Tests: e2e test_zoom_values (new), test_report_xy_zoom (2), test_report_linked_zoom.
- [x] MSG10 Remove one field, not its message; streams forgotten or removed; Add a stream (owner, 2026-11-23): StructureEditor - a row per field with its own ✕ (Undo in the notice), a message removed only from its own button after a question; MessagesPanel - each stream's ⋯ (fold, Start over, Forget the definition / Remove from the list, one Undo), *Add a stream* for any signal. Tests: e2e test_messages::test_remove_one_field_a_message_and_a_stream.
- [x] WC5 What changed keeps earlier spans (owner, 2026-11-23): ui.wcEarlier (UI only, not saved) - *Asked before*: open again, ✕, Clear all; a new span between the cursors while one is shown. Tests: e2e test_what_changed.
- [x] RE4 (editor) The report editor's own undo, comments, line keys (owner, 2026-11-23; the commits say RE4 - the ID of the built-in LaTeX above): editText.ts (history of runs of typing / pieces with the selection, Ctrl+/ `<!-- -->` / `%`, Tab, Alt+Up / Down, Ctrl+Shift+D); reportDoc strips Markdown comments with their references (LaTeX: `%` lines are code). Tests: editText.test.ts, reportDoc.test.ts, e2e test_report_doc.
- [x] FB1 The file dialog lost a click made while another folder was listed (2026-11-23; the flaky test_messages direction-column test): the old list inert until the new one is in. Tests: e2e test_file_browser_edit::test_a_click_while_another_folder_loads_is_not_lost.
- [x] Release 1.35.0 (2026-11-23): MSG10, WC5, RE4 (editor), FB1.
- [ ] RE2.6 The block editor (per-paragraph RTL, table grid, cards, drag, outline).
- [ ] RE2.7 *Expand to text*; report checks before export; numbering / toc; Confluence copy of the document; Sweeps parts.

## UX - one coherent app: modules, workspaces as pages, guided examples (owner, 2026-11-23)
Owner (Hebrew, translated): *"clean up and reorganise the code - modular, easy to maintain; then review the design: the
report got a full window but Investigate did not, other things only a corner on the side; defining a signal as messages
is reached only by a right-click; some examples load the finished result instead of showing how it is built - load,
then lead the user"*, and: *"if you define whole areas for these, design them really differently - in the end it must
look like one whole, flowing, coherent app, not sections cut off from each other."*
- [x] UX1 App.tsx is the frame only: shell/effects.ts (restore + autosave, ping, playback, live follow / poll, pushed
  data, the drop, conditions, log data - a hook each), shell/Dialogs.tsx, shell/CursorValues.tsx, shell/panels.tsx (the
  panels' views as a Record over PanelId, the rail); components/rail.ts is the one table of panels (button, width,
  place). No behaviour change.
- [x] UX2 Workspaces as pages: shell/PanelFrame.tsx - one frame, two places (beside: the side panel; on the stage: the
  page head = the Report's head, the demo's line, an index column = the Report's library column, the main column).
  rail.ts isFull: Report always, Messages by default, Investigate while What changed is shown; the ⤢ / ⤡ remembered
  (sv3.full.<id>); showPlotsBeside when the active tab, its plots or the cursor change (usePlotsComeBack), forgotten by
  a new What changed. App keeps the panel at one place in the React tree (only its grid column moves: .panel-slot /
  .stage-panel), so a page that moves beside the plots keeps what it had open. Messages as a page: master-detail (the stream chosen in the main column). Tests: Vitest
  panelPlace.test.ts; e2e test_messages (the serial link's steps check the page and the plots coming back).
- [x] UX3 Messages - *Add a stream* as a form (components/AddStream.tsx): one signal / TX and RX / byte columns; open by
  itself with no stream; msgFocus.carries "pair" passed to StreamEditor. Tests: e2e test_messages::test_add_a_stream_form.
- [x] UX4 Examples step by step (demoGuide.ts DEMOS: steps, done, setup; DemoGuide: n/N, *Show the result*): serialLink,
  linkStructure, gpsNmea, reportDemo open raw; the line also on pages (PanelFrame, ReportScreen). Tests: e2e
  test_messages (3 examples), test_report_parts::test_the_report_demo_example_opens_the_automatic_report.
- [x] UX5 The review's next steps (TASKS.md "UX review 2026-11-23"), one item per commit:
  - [x] UX5.1 The Inspector beside a page: hidden (it is the plots' cursor values, statistics, notes - a page is in
    their place), its top-bar button off with a hint; back with the plots, inspectorOpen kept (rail.ts pageOnScreen).
    Test: e2e test_messages::test_the_inspector_is_not_beside_a_page.
  - [x] UX5.2 Checks in the one frame (LogPanel through PanelFrame, `indexFirst` beside the plots): rail.ts full: false
    - beside by default (a click goes to a time), the ⤢ a page: the file, firmware, Align time and the sections
    (vertical tabs) in the index column, the section in the main column. Test: e2e
    test_checks_view::test_checks_as_a_page_and_back_beside_the_plots.
  - [x] UX5.3 Sweeps in the pages' anatomy: FlowNav's row is a `.page-head` with the study's name and the area's icon
    as its `.page-title` (useStudyName; the Navigator's own name head removed - one place for it), hidden under
    1100 px; the left column was already the index (a side panel), the step the main column. Markup and CSS only.
    Tests: e2e test_sweeps_* (6 files), test_folder_of_recordings, test_fresh_user, test_settings.
  - [x] UX5.4 The one-step demos in two or three steps (demoGuide.ts): each still opens what its card shows (its
    picture promises it), then leads through the work - flight: Play, Checks, the report; twoFlights / car: Compare,
    the report; bench / ardupilot: Checks, the report; simVsFlight: Align, Compare; investigate: the cursors, What
    changed? (openWhatChanged). The report step is openAutoReport (the parts that fit). Tests: e2e
    test_welcome_cards::test_a_demo_leads_on_to_its_report, test_plot_room (the line moves on), test_welcome_cards,
    test_cursor_labels, test_file_colours, test_less_clutter, test_tab_band, test_report_parts.
  - [x] UX5.5 Files past ~1000 lines split by part, no behaviour change, one commit each: app/report.py 1373 -> 1015
    (+ report_office.py PDF / Word, report_clip.py Confluence; callers import them directly), app/reportparts.py 1420 ->
    790 (+ reportparts_base.py, reportparts_messages.py), routes/sweep.py 1100 -> 681 (+ routes/sweep_tables.py, its own
    router), index.css 2185 -> 1011 (its later parts in order into styles/tools, mapobjects, features, messages.css,
    imported right after it - the built CSS byte for byte the same), sweeps/state.ts 1138 -> 699 (+ studyState.ts,
    re-exported). Left, with the reason: Globe3D.tsx, TimeChart.tsx, GeoChart.tsx (each one component of 1000+ lines -
    splitting means pulling out hooks, its own task with the 3D / map e2e), bin_loader.py (one 700-line class),
    csv_loader.py (its follow part and load_csv call each other - a cycle). Tests: backend all, mypy, Vitest; e2e
    test_confluence_copy, test_report_doc (4 / 5: the LaTeX one needs a TeX, as before), test_live_report,
    test_findings_report, test_sweeps_*, test_messages, test_report_parts, test_needle.
  - [x] UX5.6 Media: pictures 09 10 23 25 26 30 38-43 48-56 made again (make_readme_media.py), the narrated training
    film made again (make_training_video.py; ffmpeg for Playwright under /opt/pw-browsers/ffmpeg-1013).

## RW - the three-agent review of 1.36.0 (critic, advocate, judge; 2026-11-25)
The critic's items C1-C19 and the advocate's "must protect" list in `/home/claude/review/` (outside the repo); the
judge's decision per item there (decision.md). Branch `review-1125`, one commit per fix.
- [x] RW1 (C1) No green verdict when nothing was judged: ChecksView's verdict grey ("none") with no limits / checks
  file / health check; the automatic flags (svcore/overview.py, the strip's) counted as their own phrase and listed as
  cards (flagText shared with OverviewStrip). Sweeps with no limit in the goal: "No limits yet - all N sets shown, none
  judged" (ResultsSide, GoalsStep, FlowNav, SweepsStatus; rcNoGoalYet for recordings). Tests: e2e
  test_checks_view::test_no_green_verdict_when_nothing_was_judged, test_sweeps_flow (the four-steps test).
- [x] RW2 (C11) The report: How to reproduce by file name, samples and save time (rFileLine; Settings `reportPaths`
  "Files in a report: Name only / Full path", default name); parameters and transforms as name=value
  (investigation.ts nameValues); the process line only non-zero counts with singulars (rpInv*); reportparts.py moments:
  a change of state is "info", flags weigh by kind (FLAG_WEIGHT) in [[summary]]. Tests: backend
  test_report_parts::test_what_to_look_at_puts_a_flag_before_changes_of_state; e2e
  test_findings_report::test_journal_and_report_sections.
- [x] RW3 (C5) What changed?: changed / same / no data exclude the left-out (skip) ones, so the four groups add up to
  the signals asked about; a tally line (wcTally, data-total / -changed / -same / -left / -nodata); the headline's n =
  the changed ones (the event's own too) = the filter's m; the first change's absolute time beside the relative one
  (wcSummary {abs}), wcSpan says what the times count from; "What changed?" for the title, the Investigate button,
  the journal (jChanged, jk_changed); singulars (wcClusterOne, wcSummaryOne); the event alone in its cluster named.
  The wording pass on the long hints: later. Tests: e2e test_what_changed::test_the_counts_add_up_and_the_first_change_has_its_time,
  test_what_changed, test_features -k investigat, test_welcome_cards, test_plot_room, test_findings_report, test_conditions.
