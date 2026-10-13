# Roadmap

Audience: flight-test / drone engineers and simulation engineers (MATLAB and Python).
Rules for every task: see `/CLAUDE.md`. Tick `[x]` only when "Done when" is met.

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
- [ ] **T10b Same segment across runs** (e.g. the 2nd AUTO of every open flight, side by side
  in the comparison table).

- [x] **T11a Python API and command line** (MATLAB and Python users)
  `import signalviewer as sv; rec = sv.load(path)` -> `.signals`, `.signal(name)` (numpy),
  `.table()` / `.to_dataframe()` (one time base, same rule as Export CSV, reuses `align_to`).
  `python cli.py info FILE [--json]`, `python cli.py export FILE --out x.csv|x.mat
  [--signals a,b --t0 --t1]`; MATLAB: `system(...)` + `load`. Reuses `Store.open_file`, so
  every format and its auto-detection behave as in the app. Loader prints go to stderr so
  `--json` stays parseable. Tests: `backend/tests/test_cli_api.py`.
- [ ] **T11b Batch reports from a template** (`cli.py report --template T --out DIR files…`).
  Needs the template matching (`autoBind` / `applyTemplate`, now only in `templates.ts`)
  in ONE place: move it to the backend, have the UI call it, then the CLI uses the same code.
  Not duplicated in Python on purpose (CLAUDE.md: one way to do a thing).

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
  Works with SITL too.
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
- [ ] **T16b Motor-order marks** on spectra (needs the RPM / ESC signal chosen per plot).
  `q2roll` / `q2pitch` / `q2yaw` (Hamilton w-first quaternions, aerospace order, degrees).
  In the server list and in `formulaHelp.ts` (suggestions while typing; the sync test enforces
  both). Test: `test_formula_angles_and_quaternions`.
- [ ] **T17b Frames NED / ENU / body**: three components in, three out - does not fit one
  formula = one signal. Design first (an Analysis operation that creates three signals).

## Milestone 3 — 1.3.0: smoother work
- [ ] T18 Settings dialog (language, theme, map layer, live defaults); language and theme
  leave the TopBar.
- [ ] T19 Zoom mode by modifier keys (Shift = Y, Ctrl = XY); X/Y/XY moves to a menu.
- [ ] T20 One layout button (grid picker) instead of seven icons; split a plot by dragging a
  signal to its edge.
- [x] T21 Clearer names: Analysis → "Create signals", Compare → "Compare runs" (rail, panel
  titles, command palette; he: "יצירת סיגנלים" / "השוואת ריצות"). e2e selectors updated; the
  panel's button is now found by role, since "text=Create signal" also matched the new title.
- [ ] T21b Signal context menus: one "Create signal ▸" entry instead of repeated operations.
- [ ] T22 Signal list: unit, sample rate and a sparkline per signal.
- [ ] T23 Notes over a time range (shaded span), listed in reports.
- [ ] T24 Favourite folders and quick open (Ctrl+P, fuzzy over recent folders).
- [ ] T25 Sim-vs-flight error signal with RMS per segment.
- [x] T26 Parameter diff between two logs. *Re-assessed: already there* - the Log panel's
  Parameters tab has a "differences from another file" filter.
- [ ] T27 Formats: MCAP (ROS 2), HDF5 (generic).
- [x] T28 `worldCountries.ts` → JSON loaded with the map. *Re-assessed: already done* -
  GeoChart loads it with `import()` into its own chunk (not in the main bundle).

## Later
- [ ] Parquet, "copy as pandas code", MF4.
- [ ] Split `backend/app/main.py` into routers; split `store.ts` into slices.
