# Work queue and handoff

This file is the **active work queue**: what to do next, in order, with enough detail that any
developer or agent can pick up a task cold. `ROADMAP.md` is the catalogue (every task ID, ticked
`[x]` when done) and `/CLAUDE.md` holds the rules. Read all three before starting.

**Keep this file current.** After every finished task (or when you stop in the middle):
1. Update "Current state" and the task's **Status** / **Progress** below.
2. Tick the task in `ROADMAP.md` with its done-notes, add the user-facing line to `CHANGELOG.md`.
3. Add a line to the "Log" at the end (date, task, commit, what is left).

---

## Current state

- Branch `main`. Released tags: `v1.0.0` ... `v1.5.0`; **1.6.0 prepared** (Q35, this commit) - the
  owner builds the Windows portable package, checks the four welcome examples are there (F10 could
  not be checked in the sandbox: python.org is unreachable), then tags `v1.6.0` and pushes the tag.
  (`v1.5.0` was tagged without its release patch - its packages say 1.4.0; CHANGELOG has both.)
- **Active plan: "Review 2026-10-18 (after 1.6.0)" below** - owner: polish what exists before new
  features. P1 (bugs F13-F21, Q36-Q44) aims at 1.6.1; P2 (T24 extended, T46-T52) joins Q30-Q34 in
  1.7.0. Next: Q38 (F15), then Q36.
- Tests at the last change: backend 642 passed; whole e2e suite 160 passed (Q29).
- Q1 (T12) waits for the owner's check with real SITL / a radio.
- **Behaviour changes the owner should know:** pan is Alt + drag now (Shift + drag zooms values).

## Releasing

1. `python tools/make_readme_media.py` (needs Playwright + ffmpeg) refreshes `docs/images` and
   `docs/media` from the app itself; it does not make `06_3d_terrain.png` and the
   `02_flight_map_3d` clip (headless, the 3D view runs on software WebGL) - keep or retake those
   by hand.
2. Version in `build.bat` (`VERSION`), `backend/app/version.py` (a test keeps the two equal),
   `installer/SignalViewer.iss` (`AppVersion`),
   `installer/version_info.txt` (four places); the workflow takes it from the tag, and a manual
   run (Actions -> build -> Run workflow) with the version left empty takes it from build.bat.
3. CHANGELOG: rename the open section to `## X.Y.Z – date` with a highlights line.
   **README review (owner's rule: before EVERY official release):** go through the CHANGELOG
   section and check each item against the README - the "What works" table (a new or changed
   feature in its row), the test commands and counts, "Known limitations" (remove what was
   fixed, add what is new), the Hebrew section ("חדש ב־X.Y" line), the file names with the
   version (build table), the format list at the top, and the pictures (step 1).
4. `cd frontend && npm run build` and commit `frontend/dist`; tag `vX.Y.Z` and push the tag.

## How to work here (practical notes)

- Setup: `pip install -r requirements.txt -r requirements-dev.txt`, `cd frontend && npm ci`.
- Run: `python run.py` (builds the UI once by itself when the sources changed, T17e).
- Checks after every change (CLAUDE.md): `cd backend && python -m pytest -q`;
  `cd frontend && npx tsc -b && npm run build`.
- e2e: Playwright, **one file per process**:
  `for f in tests/e2e/test_*.py; do python -m pytest -q "$f"; done`. A custom Chromium can be
  given with `SV_CHROMIUM=/path/to/chrome`. The full set takes several minutes; when time is
  short run the files / `-k` filters that touch what you changed, and say so in the log.
- CI (`.github/workflows/build.yml`) runs the backend tests on Linux, macOS and Windows: compare
  computed floats with a tolerance (`abs(x) < 1e-6`, `pytest.approx`, `np.allclose`), never `==` -
  the platforms' math libraries round differently (T17b's test failed on macOS / Windows at 1e-13).
  Waits in tests: wait for the END state (all the data in), not for "something changed", and allow
  for slow runners (seconds, not tenths).
- Tests reach the app state through `window.__sv.state()` / `window.__sv.setState(...)`
  (`frontend/src/main.tsx`).
- `frontend/dist` is committed. Patches between developers may leave it out (run.py rebuilds);
  rebuild and commit it before a release tag.
- Sandbox gotchas seen so far: a background server or test run started inside a tool call may
  die when the call ends - start it with `setsid nohup ... &`. Never `pkill -f <pattern>` in the
  same shell command line that contains the pattern (it kills its own shell).

## Queue (in this order)

Sizes: S < 1 day, M 1–3 days, L about a week. Each task lists where to start; read the code and
every caller first (CLAUDE.md), the pointers are a head start, not the whole picture.

### Q1 · T12 Live MAVLink (UDP / TCP / serial) — L
**Why:** in the field this is the first thing a flight-test engineer needs; today a second tool
(QGC / Mission Planner) must stay open for live data.
**Idea (extend, do not add a parallel mechanism):** a receiver writes what arrives to a `.tlog`
file (8-byte big-endian µs timestamp + raw MAVLink frame - the format `tlog_loader.py` already
reads), and the existing live mode follows that file like any growing file. One code path for
live and recorded data, and the session leaves a real `.tlog` behind.
**Where:** `backend/svcore/tlog_loader.py` (`append_tlog`, `TLogState`, `_scan` already parse
incrementally); stream endpoints `/api/stream/start|stop|poll` in `backend/app/main.py`;
`frontend/src/live.ts` (`startLive`); TopBar "Live" menu. pymavlink is already a dependency
(`mavutil.mavlink_connection` handles `udpin:`, `tcp:`, serial).
**Steps:** 1) `svcore/mavlive.py`: a thread reading a connection string, writing frames +
timestamps to `<recordings folder>/<date-time>.tlog`, start / stop / status, reconnect on drop.
2) API: `POST /api/mavlink/start {conn, baud?}` → opens the file as a run and starts following;
`stop`; `status` (bytes, messages/s, last heartbeat). 3) UI: in the Live menu "Connect to
MAVLink…" (connection string with presets UDP 14550 / TCP 5760 SITL / serial + baud), status
dot like the existing live dot. 4) en + he strings.
**Done when:** with ArduPilot SITL (`sim_vehicle.py`, UDP 14550) signals appear and grow live;
stop keeps the `.tlog` and it reopens identically; backend test feeds a recorded `.tlog` through
a local UDP socket and checks the run grows; e2e: connect / status / stop with that replay.
**Risks:** serial ports on Windows (pyserial, permissions); the app must still listen only on
127.0.0.1 - the MAVLink socket is an outgoing/listening data socket, keep it opt-in and say so in
the UI; heavy rates (>1000 msg/s) - batch the writes.
**Status:** implemented (see ROADMAP T12 for what and where). Tested with a simulated vehicle
(pymavlink over UDP: backend + e2e + by hand in Chromium). **Left for the owner:** run against
ArduPilot SITL (UDP 14550 via MAVProxy, and TCP 5760 with "Ask the vehicle to send data") and a
serial radio on Windows; then tick T12 in ROADMAP.
**Follow-ups (not queued):** choose the recordings folder in the UI (the API takes `folder`);
show the vehicle type / mode in the pill; several links at once.

### Q2 · T10b Same segment across runs — M
**Why:** "the 2nd AUTO of every flight, side by side" - almost no other tool does it.
**Where:** `/api/segments` + `_stretches` (main.py), Inspector segment list (T10),
`/api/compare/all` + `compare_table` (main.py), `svcore/compare.py`, `ComparePanel.tsx`,
`CompareTable.tsx`.
**Steps:** 1) Backend: for a state signal name + value + occurrence (1st, 2nd, last, all), find
the matching stretch in every open run (same-named state signal, link-files rules). 2) Compare
runs: a "Segment" choice (state signal, value, occurrence) that sets each run's window instead
of one common time window; the table gets per-run start / duration columns. 3) Optional: plot
the chosen segment of every run on a common "time since segment start" axis (per-signal
`tOffset` already exists - use it, do not add a new offset mechanism).
**Done when:** with the three example runs, choosing Gear = 2, occurrence 1 gives one row per
run with its own window, statistics match "Between cursors" on that segment; backend + e2e tests.
**Status:** done (see ROADMAP T10b for what and where). Step 3 (common "time since segment
start" axis) done with the existing per-signal `tOffset` in a tab of its own.
**Follow-ups (not queued):** "every occurrence" (all AUTOs of all flights as rows); match the
state by text when files number the same mode differently.

### Q3 · T11b Batch reports from a template — L
**Why:** a report per flight without opening each one.
**Where:** `frontend/src/templates.ts` (`autoBind`, `applyTemplate`, `fit`, `matchSignal`) -
the matching must move to ONE place in the backend first (ROADMAP note); report code in
main.py (`/api/report*`); `cli.py`.
**Steps:** 1) Port template matching to `svcore/templates.py` with tests that pin today's
behaviour (write the tests against the TS version's results first). 2) UI calls the backend
for matching; delete the TS copy. 3) `cli.py report --template T --out DIR files… [--format
html|pdf|docx]`. 4) Optional UI: "Report for each file…" in the Report panel.
**Done when:** existing template e2e files pass unchanged; CLI makes one report per file;
tests for the matcher and the CLI.
**Status:** done (see ROADMAP T11b). Step 4 ("Report for each file…" in the Report panel) not
done - optional; the CLI covers batches.
**Follow-ups (not queued):** a UI entry for batch reports; several files per report for
multi-slot templates (today each file gets its own report and fills the slot it fits best).
**Note for later tasks:** template matching is backend-only now - Q4 (smart start) should use
`/api/templates/fit` (TemplateStrip already does) and never re-implement matching in the UI.

### Q4 · T29 Smart start (new) — M
**Why:** the first minute decides whether people keep using the tool. Most users open the same
ten signals each time.
**Where:** `templates.ts` `fit` (how well a template matches open files), template library,
`svcore/health.py` (`health(run)`), welcome screen in `App.tsx`, file opening in `files.ts`.
**Steps:** 1) After a file opens, if a saved template fits it well (existing `fit` score) offer
it in one toast / strip ("Apply 'ArduCopter basic'?"); never apply silently. 2) Ship 2–3
built-in templates for ArduPilot / PX4 logs (attitude vs desired, vibration, battery, modes).
3) Health: when a flight log opens, show a short "3 things to look at" summary with links that
jump to the time (`goToTime` / `showSpan`).
**Done when:** opening an example `.bin` offers the built-in template and the health summary;
dismissing remembers the choice for the session; e2e test.
**Status:** done (see ROADMAP T29). Step 2 (built-in templates) needed nothing new. Step 3
("dismissing remembers the choice for the session"): the card appears only for the first file
into an empty workspace, so it does not come back by itself; there is no per-file memory.
**Lesson (for any task):** a test that passes alone but fails in the full file usually means state
left by an earlier test (here: remembered import settings in the shared test home) - and it found
a real bug (F04). Run the whole file before calling a task done.

### Q5 · T19 + T20 Calmer StageBar — M
**Why:** the bar has 7 layout icons, X/Y/XY, link X / Y - too much at once.
**Where:** `StageBar.tsx`, store layout actions, `fitLayout`, zoom mode in TimeChart.
**Steps:** T20 one layout button opening the grid picker (the "…" picker exists); T19 zoom by
modifier keys (Shift = Y, Ctrl = XY), X/Y/XY moves into a menu. Shortcuts and Ctrl+K stay.
**Done when:** every old action is reachable (bar, menu, shortcut or Ctrl+K); run **all** e2e
files (layout change - CLAUDE.md).
**Status:** done (see ROADMAP T19, T20). Owner reports fixed with it: F06 (middle click on a tab),
F07 (list checkboxes).
**Note:** middle-drag on a PLOT pans (since before T19); middle click on a TAB closes it - they
do not conflict (different elements), the Windows failure was autoscroll (F06).

### Q6 · T22 Signal list: unit, sample rate, sparkline — M
**Where:** `DataPanel.tsx` (virtualized rows, keep them cheap), `units.ts`, backend run
description (`Store.describe`). Rates / units come from the backend once per file; sparklines
lazily for visible rows only.
**Done when:** a 300-signal file scrolls as smoothly as before (measure); e2e.
**Status:** done (see ROADMAP T22).

### Q7 · T15 Video synchronised to the timeline — M
**Status:** done 2026-10-18 (see ROADMAP T15).
**Where:** Timeline / cursor state in store, a new lazy component (keep it out of the main
bundle). Local file served by the backend (range requests); offset set from a cursor pair, like
`syncCursorMenu`.
**Done when:** play / scrub moves video and cursor together; offset saved in the session
(optional field); e2e with a tiny generated video.
**Status:** not started.

### Q8 · T16b Motor-order marks on spectra — S
**Where:** `FFTChart.tsx`, plot fields like `fftMethod` (optional, default off).
**Steps:** choose an RPM / ESC signal per FFT plot; draw 1×, 2×, 3× (and blade-pass) lines at
its mean over the window.
**Status:** done (see ROADMAP T16b).
**Follow-ups (not queued):** the marks in reports (report FFT) and in templates (by name).

### Q9 · T27 Formats: MCAP (ROS 2), HDF5 — M each
**Where:** loaders in `svcore/*_loader.py`, `Store.open_file`, `DATA_EXTS` in `values.ts`,
`cli.py` (gets them for free through `Store.open_file`). New dependencies need a reason in the
task notes (CLAUDE.md).
**Status:** done 2026-10-18 (see ROADMAP T27). Owner asked 2026-10-18 whether ROS works: ROS 2
via .mcap now. Not done: ROS 1 .bag and ROS 2 .db3 (sqlite) - add if the owner needs them.

### Q10 · T30 Frames: suggest the conversion (new) — S
**Why:** fewer technical choices: `Lat/Lng/Alt` is LLA, `VN/VE/VD` is NED velocity.
**Where:** `AnalysisPanel.tsx` Frames tab, `mapObjects.ts` `guessRoles` (already guesses
lat / lon / alt), `frames.ts`.
**Steps:** when the Frames tab opens, guess quantity, source frame and the three signals from
the active plot / the file; show "Suggested: LLA → NED from GPS" with the fields filled; the
user only confirms.
**Status:** done (see ROADMAP T30).

### Q11 · T31 User Python operations (new) — L
**Why:** new analyses without changing the app.
**Decided (owner, 2026-10-15):** only Python files in a local folder the user chooses run,
listed in the UI; never code that comes with a session or template (a shared session must not
run code). Formulas keep the AST whitelist (`svcore/formula.py`).
**Status (2026-10-18):** backend done, UI next.
Done: `svcore/pyworker.py` - the WORKER process (spawn): loads the folder's `.py` files
(`operation` decorator available without an import; `_*.py` skipped; a broken file is listed
with its error and line, the others still load), runs `fn(t, *ys, **params)` - extra inputs
aligned onto the first one's time, parameters coerced to their default's type, returns y or
(t, y), wrong output explained, errors name the line in the user's file. `app/pyops.py` - the
server side: one worker started on first use, per-run timeout (`SV_PYOPS_TIMEOUT`, 120 s) -> the
worker is killed and restarted; a crash -> "crashed (exit code N)", restarted; folder in
settings.json (`pyopsDir`, default `~/.signalviewer/operations`); an example file. Analysis op
`"py"` with params `{"op": "file.py:function", "args": {...}}` (via `analysis.PY_RUNNER`, svcore
does not import app) - so preview, live recompute and sessions work like any derived signal, and
a session stores only the NAME (an operation the folder does not have: "not in your operations
folder"). Name: `despike(Speed, limit=3)`. Endpoints `/api/pyops` (list), `/reload`, `/folder`,
`/example`, `/reveal`. `run.py`: `multiprocessing.freeze_support()` (the packaged app starts
itself again for the worker). Tests: `test_pyops.py` (10: listing, params, 2 inputs, new time
base, error line, wrong output, endless loop, crash, missing op, reload, example, folder).
**UI: done 2026-10-18** (see ROADMAP T31).
**Check on Windows (owner):** the packaged app runs an operation (spawn + freeze_support).

### Also open (not queued yet - see ROADMAP)
T14c, T21b, T23, T24, T25, splitting `store.ts` (now Q23).

---

## Review 2026-10-17 - toward the leading tools (Q12–Q24)

Source: a full review of the code at `a28469e` (owner asked: "what would make it compete with the
best tools?"). Competitors in view: PlotJuggler, Foxglove (robotics), asammdf / Vector (automotive),
NI DIAdem / Dewesoft (test & measurement), Tacview (flight), MATLAB SDI (simulation),
UAV Log Viewer / MAVExplorer (ArduPilot). Conclusion: the code is strong; the gap is trust and
reach (licence, robustness on bad files, extensibility, formats, fleet-level work).

**Order update (2026-10-18, owner):** Q18 to the end - slow first opens are not felt by users.
Now: Q17 (finish), Q7 (video), then the rest as below.

**Order (set 2026-10-17, owner: "make the list, then start, tick as you go"):**
Q12, Q13, Q14, Q15, Q16, Q19, Q18, Q17, then Q7 (video), Q11 + Q20 (Python), Q9 + Q21 (formats),
Q22 (fleet), Q23 (store.ts), Q24 (release & reach - mostly owner actions).

Progress board (tick here AND in ROADMAP):

| # | Task | Size | Status |
|---|---|---|---|
| Q12 | T32 Licence file (MIT) + README section | S | ☑ done |
| Q13 | T33 Loaders survive damaged files (fuzz tests for .bin/.tlog/.ulg/.csv/.mat) | M | ☑ done |
| Q14 | T34 Review the broad `except Exception` handlers (54) | M | ☑ done |
| Q15 | T35 Split `backend/app/main.py` into routers | L | ☑ done |
| Q16 | T36 Static type check of the backend (mypy) in CI | S | ☑ done (T36b: shrink baseline) |
| Q17 | F02 The whole e2e suite in one process | M | ☑ done (closed: not reproducible; F09 fixed) |
| Q18 | T37 CSV first open: meet the 20M-row target | M | ◐ measured; moved to the end (owner: not felt by users) |
| Q19 | T38 Local crash report (log file + "copy details") | S | ☑ done |
| Q7  | T15 Video synchronised to the timeline (already queued) | M | ☑ done |
| Q11 | T31 User Python operations from a local folder (already queued) | L | ☑ done |
| Q20 | T39 Python API: push arrays from Jupyter / a simulation into the open app | M | ☑ done |
| Q9  | T27 MCAP (ROS 2) and HDF5 (already queued) | M each | ☑ done |
| Q21 | T40 Parquet, MF4 (ASAM MDF) and CAN decoding with a DBC | L | ◐ Parquet done; CAN / MF4 POSTPONED by the owner |
| Q22 | T41 Fleet view: an index of many logs, search by finding, trends | L | ☑ done |
| Q23 | T42 Split `frontend/src/store.ts` into slices | M | ☑ done |
| Q24 | T43 Release & reach: signed installers, docs site, public benchmark vs other tools, forum posts | M | ☐ |

### Q12 · T32 Licence — S
**Why:** without a LICENSE file the code is "all rights reserved"; no company may use it. The
old README (v2.6) said MIT, but the file was never in the repo.
**Steps:** `LICENSE` (MIT, holder David Alpert) at the root; README "Licence" section that also
names the third-party licences already shipped (uPlot MIT, fonts OFL, Cesium Apache-2.0);
installer and `pyproject.toml` show it.
**Done when:** GitHub shows the licence badge; the installer lists the licence.
**Owner check:** confirm MIT (vs Apache-2.0, which adds a patent grant).
**Status:** done (see ROADMAP T32). Owner confirmed MIT and the name (2026-10-18).

### Q13 · T33 Loaders survive damaged files — M
**Why:** logs from the field are cut off (battery pulled), half-copied or corrupt; that is where
users meet crashes or hangs, and one crash costs a user.
**Steps:** a test that takes every sample file, damages it in fixed seeds (truncate at many
points, flip bytes, zero blocks, random garbage with a right extension) and opens it through
`Store.open_file` with a time limit: it must either open (what was readable) or raise a
`ValueError`-type error with an engineer-readable message - never another exception type, never
hang. Fix what it finds.
**Done when:** the fuzz test runs in CI (fast, fixed seeds) and passes for every format.
**Status:** done (see ROADMAP T33). Before: 42 of 150 damaged CSVs and every cut-off .mat v5
failed to open; flight-log loaders had no failure in 1,000+ cases. e2e not run here (no Playwright
in this sandbox) - the UI change is two toast texts; run `test_templates_recent_badfiles.py`.

### Q14 · T34 Broad exception handlers — M
**Why:** 54 `except Exception` can hide real bugs (wrong results with no message).
**Steps:** list them; each one either narrowed to the exceptions that are expected there, or
kept and logged (`log.exception`) with a comment why it must be broad (e.g. a background thread
that must not die). No behaviour change for the user.
**Done when:** no silent `except Exception: pass`; each remaining broad handler logs or reports.
**Status:** done (see ROADMAP T34). The important find: the low/high-pass "filter" (a moving
average that returned raw data silently when it could not filter) - now Butterworth. Behaviour
change for the owner to know: filtered signals in old sessions get correct, slightly different
values; a cut-off at or above half the sample rate is now an error instead of a mild smoothing.

### Q15 · T35 Split main.py into routers — L
**Why:** 2,100 lines and 79 endpoints in one file; every task touches it.
**Steps:** `backend/app/routes/<area>.py` with `APIRouter` per area (files, plots/data, derived,
compare, report, stream/live, templates, map, prefs, jobs); shared request models and helpers in
`app/deps.py`; `main.py` keeps app creation, middleware (localhost guard) and static files.
Pure move - no endpoint path, request or response changes.
**Done when:** the OpenAPI schema (paths + models) is identical before/after (test compares it);
all backend and e2e tests green.
**Status:** done (see ROADMAP T35). The OpenAPI comparison was a one-time check during the move
(identical); a permanent snapshot test would fail on every new endpoint, so the lasting guard is
`test_routes_layout.py` (every router included, no duplicate route, catch-all last).
**Where things are now:** a new endpoint goes into the `app/routes/<area>.py` it belongs to;
shared helpers into `app/common.py`; a new area = a new module + one `include_router` line.

### Q16 · T36 mypy — S
**Steps:** `mypy` config in `pyproject.toml` (lenient first: `ignore_missing_imports`, check
`svcore` + `app`), fix real errors it finds, add a CI step.
**Done when:** CI runs mypy and it is clean.

**Status (2026-10-17):** started. First run: 104 findings (`mypy --ignore-missing-imports app
svcore signalviewer`). Done: `common.fail` is `-> NoReturn` (removed the "None has no attribute"
findings after every `fail(404, ...)`), the report's XYZ call unpacks its three signals
explicitly. Left: declare the dynamic `Run` attributes (`load_report`, `_flightlog`, `_tlog`,
`_dataflash`) as optional fields in `svcore/models.py`; look at `bin_loader.py:395/514`,
`tlog_loader.py:272`, `sync.py:138`, `compare.py:68`, `prefs.py:246/267` (possible None cases);
annotate the rest; then a `[tool.mypy]` section in pyproject.toml and a CI step.

### Q17 · F02 Whole e2e suite in one process — M
See ROADMAP F02 (hang only when detached from a terminal).
**Seen again 2026-10-17:** started with `setsid nohup` per file, `test_features.py` stopped after
31 tests and never finished; the same tests in the foreground pass. So it is not "one process for
all files" - detaching alone is enough. Also: one test in the third quarter of
`test_features.py` (ids 55-81 in collection order) failed once in three runs - flaky; rerun with
`-rf` to name it when it happens. Find the shared state (server / browser
fixtures, test home) and make the suite runnable as `pytest tests/e2e`.

**Investigated 2026-10-18 (Q17):** not reproduced. Detached (`setsid nohup`), with and without
stdin closed, `test_features.py` passed 108/108 twice (4:27); the WHOLE suite in ONE process,
detached: 151 passed, 1 failed, 8:33 - no hang (faulthandler_timeout=90 never fired). Earlier
"stuck at 31 tests" runs overlapped heavy work (mypy, the backend suite) on this sandbox's single
CPU, and the dots of a run whose output goes to a file arrive in bursts - read progress over
minutes, not one look. The one failure: `test_error_details.py` (T38, new) fails in the
whole-suite run and passes alone - an isolation problem in that test (it imports `env` / `pg`
from test_features like the other files; find what differs). **Next: fix that test first, then
make `pytest tests/e2e` the documented way (CLAUDE.md, pyproject comment) and close F02.**
The flaky `test_features.py` test (1 failure in 3 runs, 2026-10-17) did not fail in these 3 runs.

### Q18 · T37 CSV first open — M
**Why:** `benchmark_20M_rows.md`: 12.16 s vs a 11.5 s target (1 CPU).
**Steps:** profile the first open (parse vs cache write vs float conversion); overlap cache writes
with parsing or write the cache with one pass; re-run the benchmark.

**Measured 2026-10-18 (1 CPU, like the benchmark; 4M rows x 5 signals, 163 MB):** first open
1.06-1.08 s = ~150 MB/s, the benchmark's rate. Floor: Arrow alone on the file already in memory
parses in 0.62 s + 0.29 s to NumPy = 0.91 s, so the loader is at ~86% of it. Tried: zero-copy
parts (readinto + memoryview instead of three copies of every 64 MB part) - no measurable gain
(1.04-1.19 s), reverted. The 12.16 s vs 11.5 s miss is ~6%, within run-to-run noise on one CPU,
and Arrow parses in parallel, so any 2+ core machine is well inside the target.
**What could still pay (~10-15%, est.):** write each part's columns straight into the cache files
(append to per-column raw .npy, then memory-map) instead of `np.concatenate` + `_cache_store`
(two more full passes over the data). Do it only if a user's machine shows a slow first open;
else lower the priority of T37 (the owner decides).

### Q19 · T38 Local crash report — S
**Why:** when it breaks in the field, the owner needs the details without a debugger.
**Steps:** backend errors (unhandled in a request or a thread) and frontend errors
(`window.onerror`, unhandled rejections) go to a rotating log in the app's data folder; Help
shows "Copy error details" (version, OS, last errors - no data values). Nothing is ever sent.
**Status:** done (see ROADMAP T38).

### Q20 · T39 Python API (push from Jupyter / a simulation) — M
**Status:** done 2026-10-18 (see ROADMAP T39).
**Why:** simulation engineers live in Python; `signalviewer.show(t, {"x": x})` from a notebook
into the open window is what MATLAB SDI gives them.
**Steps:** a small client in the `signalviewer` package that posts arrays (binary, not JSON) to
the running app on 127.0.0.1 with a per-start token; they appear as a run that can be updated.

### Q21 · T40 Parquet, MF4, CAN + DBC — L
**Why:** MF4 + DBC is the entry ticket to automotive / systems test (asammdf, Vector).
**Steps:** Parquet via pyarrow (already a dependency); MF4 via `asammdf` (optional dependency);
CAN logs (MF4 bus logging, candump, .blf) decoded with `cantools` and a DBC the user picks.
**Status (2026-10-18):** Parquet done (ROADMAP T40). CAN / MF4 **postponed by the owner**
(2026-10-18, after the licence question: cantools needs python-can, LGPL-3.0; asammdf LGPLv3+).
When it comes back, the options are in ROADMAP T40 (A bundle LGPL / B own DBC decoder, MIT /
C all optional); Claude recommended B.

### Q22 · T41 Fleet view — L
**Why:** almost no free tool does it: "every flight with vibration above X", trends over months.
**Steps:** index a folder of logs (header, duration, modes, health findings) into a local SQLite;
a Fleet panel with search, filters and a trend plot per finding; open a flight at its finding.
**Status (2026-10-18):** backend done, UI next. `app/fleet.py`: SQLite (stdlib sqlite3) at
`~/.signalviewer/fleet.sqlite` - tables folders / logs / findings / metrics / modes; `scan` walks a
folder (sub-folders, .bin / .tlog / .ulg), reads only new / changed files (size + mtime), drops
removed ones, records unreadable files with their reason (so they are not read again until they
change); each file in a `Store()` of its own (the app's open files untouched). Per log: vehicle,
firmware (ArduPilot via DataFlash.log_info - the first version crashed on it, caught by the
test), duration, seconds per flight mode (mode events), the health findings and their numbers as
metrics (`vibration.max`...), the date from GPS time (GWk/GMS, time_utc_usec, SYSTEM_TIME) else
the file time ("date_source"). `query`: text, finding code at a level, a metric above / below,
a mode; `trend(key)` by date; `keys()`. Routes `app/routes/fleet.py`: GET /api/fleet,
POST /api/fleet/folder (a job), /rescan (a job), /remove, GET /logs, /trend. Tests:
`test_fleet.py` (6).
**UI: done 2026-10-18** (see ROADMAP T41). Planned then: a Fleet view - folders
with Add / Update / Remove and the job's progress; the search row (text, finding + level, a
number above / below, a mode); the list (date, name, vehicle, duration, error / warning badges,
the searched number); a trend plot of the chosen number (points by date, click -> the log);
open a log at a finding (open the file, cursor at the finding's time); e2e test.

### Q23 · T42 Split store.ts — M
Slices per area (workspace, plots, live, compare, UI); `commit` (undo/redo) stays the one way to
change the workspace.
**Status:** done 2026-10-18 (see ROADMAP T42). `store.ts` (1,114 lines) is now an entry point of
25 lines that re-exports `frontend/src/store/`; no importer changed (61 files). Slices: workspace
(ws, past, future, commit / undo / redo), data, view, live, ui - one interface + initial values
each, `AppState` = their intersection. Actions by area: plots (31), layout (14), view (16), notes (3),
merged into the same `actions` object. Done by a script that cut by line ranges; checked: every
action line identical to before (5 internal calls now name their area object), all 42 old exports
still exported, tsc + build clean, whole e2e suite.
**Direct writes of `ws` outside `commit` (kept on purpose):** `setActivePlot`, `switchTab`
(selection is not an undo step), `setSizes` (live resizing), `files.ts` session load (a new
history). The fifth, `transforms.ts` "delete all derived" Undo, was a bug - F12.

### Q24 · T43 Release & reach — M (mostly owner)
Signed Windows installer (needs a code-signing certificate - owner), GitHub Pages docs from
README + docs, a public benchmark on the same log against PlotJuggler / MAVExplorer, posts on the
ArduPilot and PX4 forums. Claude can prepare the docs site and the benchmark scripts.

---

## Plan 2026-10-18 (toward 1.6.0)

Set with the owner after the v1.5.0 tag. Work top to bottom; tick here AND in ROADMAP after each
task, with a Log line. **1.6.0 = phases A, B and Q29; Q30-Q34 are 1.7.0** (owner, 2026-10-18).

| # | Task | Size | Status |
|---|---|---|---|
| **A** | **Fixes and examples** | | |
| Q25 | F10 Examples missing from the Windows portable package | S | ☑ done |
| Q26 | T44 Example: two UAV flights of the same mission, to compare | S | ☑ done |
| Q27 | T45 Example: an ArduPilot .bin flight (GPS track, modes, vibration, battery) | S | ☑ done |
| —   | F11 Fleet: flight date of modern ArduPilot logs (found by Q27) | S | ☑ done |
| **B** | **Infrastructure** | | |
| Q23 | T42 Split `frontend/src/store.ts` into slices (spec above) | M | ☑ done |
| —   | F12 "Delete all derived" Undo overwrote later changes (found by Q23) | S | ☑ done |
| Q28 | T36b Shrink the mypy baseline | S | ☑ done |
| **C** | **Usability (open in ROADMAP)** | | |
| Q29 | T21b Signal context menus: one "Create signal ▸" entry | S | ☑ done |
| **C2** | **Usability, continued - 1.7.0** | | |
| Q30 | T24 Favourite folders and quick open (Ctrl+P) | S | ☐ |
| Q31 | T23 Notes over a time range (shaded span), listed in reports | M | ☐ |
| Q32 | T25 Sim-vs-flight error signal with RMS per segment | M | ☐ |
| Q33 | T14c Envelope plot zoom linked with the tab's time plots | S | ☐ |
| Q34 | T18 Settings dialog (language, theme, map layer, live defaults) | M | ☐ |
| **D** | **Release** | | |
| Q35 | Release 1.6.0 (moved before Q30 - owner) (see "Releasing"; CHANGELOG split 1.5.0 / 1.6.0; README "חדש ב־1.5" and "1.6") | S | ☑ done |
| Q24 | T43 Release & reach (spec above; mostly owner) | M | ☐ |

Waiting for the owner, not in the plan: Q1 (SITL / radio check), Q18 (T37, not felt by users),
Q21 (CAN / MF4, licences).

### Q25 · F10 Examples missing from the Windows portable package — S
**Why:** owner: "Open an example" disappeared from the welcome screen. The welcome code (T09) is
intact; `tools/make_windows_portable.py` (the Windows package since the embeddable-Python build)
never copied `examples/`, so `/api/examples` finds nothing and the line is hidden. PyInstaller
(`SignalViewer.spec`, Linux / macOS) does bundle them.
**Steps:** copy `examples/` into `app/examples` (where `routes/fs.py` looks from source:
`backend/app/routes/../../../examples`); add the files to the build's `must` list; a backend test
that every file of `EXAMPLE_SETS` exists in the repo (a renamed / missing example fails CI).
**Done when:** the portable folder has the examples; the test passes.

### Q26 · T44 Example: two flights of the same mission — S
**Why:** Compare runs and the map with two tracks, in one click; today the only flight example is
one file.
**Where:** `tools/make_demo_data.py` (`uav_flight`), `EXAMPLE_SETS` in `app/routes/fs.py`, the
welcome line in `App.tsx`, `api.examples` type, `i18n.ts`.
**Steps:** `uav_flight_a.csv` / `uav_flight_b.csv`: the same waypoints, B with a cross-wind
(track offset, larger roll, higher battery drain, slightly later); a "Two flights" link opens both.
**Done when:** the link opens both files; backend test lists the set; e2e opens it.

### Q27 · T45 Example: an ArduPilot .bin flight — S
**Why:** the drone users' main format; Smart start (T29) and the health summary only show with a
flight log.
**Where:** `tools/make_test_bin.py` (writer), `tools/make_demo_data.py`, `EXAMPLE_SETS`.
**Steps:** a short realistic copter flight (GPS track over the example area, ATT with desired,
MODE changes STABILIZE / LOITER / AUTO / RTL / LAND, VIBE with a burst, BAT draining, RCOU, MSG);
small (< 2 MB); an "ArduPilot log" link.
**Done when:** the link opens it, the health summary and the built-in template offer appear;
backend test opens it; e2e.

---

## Review 2026-10-18 (after 1.6.0) - polish before new features

Made by going through the app as a NEW user (empty `~/.signalviewer`, 1400x850 and 1100x700,
English and Hebrew), every button, menu and context menu, with the four examples. Owner's
direction: polish what exists before Q31-Q34. Phase P1 is bugs (aim: 1.6.1), P2 is usability
(1.7.0, together with Q30). Each item says how it was seen, so it can be reproduced.

| # | Task | Size | Status |
|---|---|---|---|
| **P1** | **Bugs (1.6.1)** | | |
| Q36 | F13 Templates without colours draw every signal in the same colour (Compare runs!) | S | ☑ done |
| Q37 | F14 First run: the Templates dialog shows "templates folder is not available" | S | ☑ done |
| Q38 | F15 Backend tests write to the developer's real `~/.signalviewer` | S | ☑ done |
| Q39 | F16 Compare runs: angles (yaw / heading) compared without wrapping 0/360 | S | ☑ done |
| Q40 | F17 Plot options menu (⋯) does not close on Esc / click outside | S | ☐ |
| Q41 | F18 File dialog: Esc does nothing at first, Tab leaves the dialog | S | ☐ |
| Q42 | F19 Opening a file that is already open adds a silent second copy | S | ☐ |
| Q43 | F20 Several files opened at once: smart start suggests a one-file view; one toast per file | S | ☐ |
| Q44 | F21 File dialog: Shift+click is not a range; one "last folder" for every dialog | S | ☐ |
| Q52 | F22 Many tabs: the hidden tabs cannot be reached (owner) | S | ☑ done |
| **P2** | **Usability (1.7.0, with Q30-Q34)** | | |
| Q30+ | T24 (extended) Places in the file dialog: recent folders, favourites, folders of open files | S→M | ☐ |
| Q45 | T46 File identity: every file has a colour + short tag, used everywhere | M | ☐ |
| Q46 | T47 Signals with different units in one plot: a second value axis | M | ☐ |
| Q47 | T48 First impression: examples open ready, one-click template chips | S | ☐ |
| Q48 | T49 Duplicate and unclear controls (list below) | M | ☐ |
| Q49 | T50 Small windows and crowded headers | S | ☐ |
| Q50 | T51 Built-in templates and their tabs in Hebrew | S | ☐ |
| Q51 | T52 e2e "fresh user" test (empty home folder) | S | ☐ |

Suggested order: Q38 first (so the tests stop touching the real profile), Q36, Q37, Q39, Q40-Q44,
Q51 (it would have caught Q37), then P2 starting with Q30+ and Q45.

### Q36 · F13 Templates without colours: every signal the same colour — S
**Seen:** "three car runs to compare" → template chip *Compare open files* → Open: all 3 runs in
every plot are the same blue; the runs cannot be told apart. Same for *Quick look*. Templates with
stored colours (ArduPilot) are fine.
**Cause:** `applyTemplate` in `frontend/src/templates.ts` builds the new plots and calls
`s.color ?? nextColor(ws)` for each signal, but the new plots are not in `ws` yet, so
`nextColor` (`store/selectors.ts`) sees the same usage counts every time and returns the same colour.
Map objects (`o.color ?? nextColor(ws)`) have the same problem.
**Steps:** a colour allocator for one apply (counts from `ws` + what this apply already gave out);
use it for signals and objects. For the Compare generator use the file colour of T46 once it
exists (same signal from several files = one colour per file).
**Done when:** e2e: open the three car runs, apply Compare open files, every plot has 3 different
colours; a unit test for the allocator.

### Q37 · F14 First run: "The templates folder is not available" — S
**Seen:** fresh profile → Templates → red line `The templates folder is not available:
~/.signalviewer/templates` at the bottom of the library.
**Cause:** `prefs.template_folder_info()` reports `exists: false` until the first template is
saved (the default folder is created only by a save); `TemplateLibrary.tsx` shows `tplFolderMissing`.
The e2e machines already have the folder, so no test saw it.
**Steps:** create the DEFAULT folder when it is asked about (or at start-up); keep the red line only
for a folder the user CHOSE that is gone (network drive, USB). Same check for the Python operations
folder (`pyops.DEFAULT_DIR`).
**Done when:** backend test with an empty home: `exists` is true for the default folder; e2e in
Q51 opens the library with no error line.

### Q38 · F15 Backend tests write to the real `~/.signalviewer` — S
**Seen:** after `pytest`, the app's *Recent files* listed `/tmp/pytest-of-.../s.csv`, `f.bin`,
`a.csv`... `recent.json`, `autosave.json`, `uploads/`, `push.json` are written by the tests; a
developer's own autosave and recent list are overwritten.
**Cause:** `conftest.py` redirects only the log folder (T38). The app folder is computed at import
in three places: `app/common.py` (`APP_DIR`), `app/prefs.py` (`APP_DIR`), `app/store.py`
(`UPLOAD_DIR`, its own `expanduser`).
**Steps:** one place for the folder (`app/common.py`), honouring `SV_HOME` (default
`~/.signalviewer`); prefs, store, fleet, push, pyops, crashlog take it from there. `conftest.py`
sets `SV_HOME` to a temporary folder BEFORE importing the app; the e2e server too.
**Done when:** a test that records the mtime of `~/.signalviewer` files before the session and
checks nothing changed after (or: SV_HOME set and `prefs.APP_DIR` starts with it); grep finds no
other `expanduser("~")` for the app folder.

### Q39 · F16 Compare runs: angles compared without wrapping — S
**Seen:** two-flights example → Compare runs: `ATT.Yaw [deg]` RMS Δ 75.8, max |Δ| 315.1. With
wrapped differences it is RMS 21.8, max 68.4 (checked on the CSVs). A heading of 359° vs 1° counts
as 358° apart, so the "least similar" ranking is wrong for every yaw / heading / course signal.
**Where:** `backend/svcore/compare.py` (the difference `d`); `analysis.py` already has `_unwrap` and
`formula.py` `wrap180` - reuse, do not add a third.
**Steps:** decide "is an angle" once (unit deg / rad and a full-turn range, or a name list:
Yaw, Heading, Hdg, Course, COG, Bearing - same rule as Frames uses); for angles d = wrap180(a - b)
(or ±π). The table and the small "where" curve use the same d. Note the rule in Help.
**Done when:** backend test: two yaw series crossing 0/360 give a small RMS; the example's yaw
comes out ~21.8; non-angle signals unchanged.

### Q40 · F17 Plot options menu (⋯) does not close — S
**Seen:** ⋯ on a plot opens Export / Save image / Axis limits / Clear plot. Esc, a click on the plot,
the file list or the status bar leave it open; it closes only when the mouse ENTERS and then leaves
it (`onMouseLeave` in `PlotView.tsx` ~289). With the keyboard it never closes, and a right-click
elsewhere opens a second menu next to it.
**Steps:** use the same menu mechanism as the other menus (signal / chip / tab context menus
close on Esc and click outside); drop the close-on-mouse-leave (a slip of the mouse closes it).
Check the other hand-made `menu` divs (`grep 'className="menu"'`).
**Done when:** e2e: open ⋯, Esc closes; open ⋯, click the plot, closed.

### Q41 · F18 File dialog: keyboard focus — S
**Seen:** Open files: the focus stays on the "Open files" button BEHIND the dialog, so Esc does
nothing until the user clicks inside; Tab walks through the app behind the scrim. (The Help dialog
does it right: the focus is on its close button.)
**Steps:** focus the dialog (the list or the path box) when it opens; keep Tab inside (a small
shared focus-trap used by every `.dialog`); give the focus back to the button on close. Check the
other dialogs with one e2e loop.
**Done when:** e2e: open the file dialog, Esc closes it; Tab x 30 never leaves the dialog.

### Q42 · F19 A file that is already open opens again, silently — S
**Seen:** opening `uav_flight.csv` again (dialog or recent) adds a second run named
`examples/uav_flight.csv` with all its signals; nothing says it was already open.
**Steps:** in `openPaths` (files.ts) split the paths into new and already open; for the open ones
ask once: *Reload from disk* (default) / *Open another copy* (a real use: the same log with
another time offset) / Cancel. Drag-and-drop the same.
**Done when:** e2e: open a file twice → the question; Reload keeps one run.

### Q43 · F20 Opening several files at once — S
**Seen:** the two-flights example (2 files) → the card says "Opened: uav_flight.csv · Suggested
view: Flight on the map & 3D" (a one-file view); the three car runs → no suggestion at all. And one
toast per file, all saying "1 text columns read as states (DriveMode)" (also: "1 text columns").
**Where:** `files.ts openPaths` (`offerStart(firstNew)` only for the first), `smartStart.ts`,
the `textColsRead` toast in files.ts ~101.
**Steps:** when 2+ files of the same kind were opened, the card offers *Compare open files* first
(with the overlay of T46 colours); one toast for the whole open ("DriveMode read as states in 3
files"), plural forms in en + he; consider putting this information in the file's tooltip instead
of a toast (it is not an action item).
**Done when:** e2e: the car runs → card with Compare; one toast.

### Q44 · F21 File dialog: selection and last folder — S
**Seen / cause:** in `FileBrowser.tsx` Shift+click is treated like Ctrl+click (toggle one file),
not a range; no Ctrl+A. `sv3.lastDir` is ONE key for every use of the dialog: saving a report or
exporting a template moves where *Open files* starts next time.
**Steps:** Shift+click = range from the last clicked row (in the shown order); Ctrl+A = all files
shown (after the filter); a last-folder key per purpose (open data / sessions / reports / exports /
templates); when there is no last folder, start in the folder of the last opened file, not home.
**Done when:** e2e for range and Ctrl+A; save a PNG elsewhere, Open files still opens the data
folder.

### Q52 · F22 Many tabs: the hidden tabs cannot be reached — S
**Seen (owner, 2026-10-18):** with many tabs there was no way to get to the hidden ones. The strip
(`.tabs` in `TopBar.tsx`) scrolls sideways but its scrollbar is hidden, a mouse wheel scrolls
vertically (nothing), switching tab does not bring the tab into view, and the "+" button scrolled
away with the tabs. Many tabs also pushed the search box down to "Commands a…".
**Steps:** an "All tabs (n)" button next to "+" (only when the tabs do not fit) with the list of
tabs, the active one ticked; the active tab scrolled into view; the wheel over the strip scrolls it
(RTL too); Ctrl+PageUp / Ctrl+PageDown (and Ctrl+Tab where the window lets it through) cycle the
tabs; "Go to tab: name" for every tab in the palette; the strip gives way, not the controls on
the right; a long menu scrolls.
**Done when:** e2e with 25 tabs at 1100 px: every way reaches a hidden tab and the active one is in view.

### Q30+ · T24 extended: places in the file dialog — S→M
Owner (2026-10-18): "in the favourites, not only the recent files but also the recent folders -
we often open more from the same folders". Extends Q30.
**Where:** `recent.json` already stores the folder of every item (`prefs.list_recent()` returns
`folder`), so recent folders need no new backend storage. `FileBrowser.tsx` `fs-recent`.
**Steps:** a narrow "Places" column on the side of the dialog (the right side in Hebrew):
1) **Folders of the open files**; 2) **Recent folders** (distinct folders of recent files /
sessions, newest first, 8, missing ones greyed); 3) **Favourites**: pin the current folder (star in
the path bar), unpin, reorder by drag, saved in `~/.signalviewer/settings.json`; 4) Home, Desktop,
Documents, the drives (Windows) / `/media` (Linux) / `/Volumes` (macOS). Ctrl+P (Q30's quick open):
fuzzy over favourites + recent folders + recent files. A message for a folder with no supported
files ("No CSV / MAT / BIN … files here - N other files hidden").
**Done when:** e2e: open a file from folder X, reopen the dialog in another folder, X is under
Recent folders and one click lists it; pin / unpin survives a restart.

### Q45 · T46 File identity: a colour and a short tag per file — M
**Why (owner):** "with two files or more and signals with similar names it is hard to tell which
belongs to which". Seen: two-flights example, GroundSpeed from both files: the chips read
`GroundSpeed [m/s] · uav_flight.csv` and `GroundSpeed [m/s] · uav_flight_win…` - the part that
differs is cut off; with the cursor on, both become `GroundSpeed [m/s] · uav…` (the value takes the
room), and the chip's tooltip is the generic hint, not the name. The Create signals picker shows
`GroundSpeed [m/s]` with no file at all. Compare runs already gives files colours, but locally
(`runColor` in `ComparePanel.tsx`, by position among the CHECKED runs - unchecking one recolours
the others).
**Design:**
- Every data file gets a **file colour** and a **tag** (A, B, C… or what the user types in
  *File options > Rename / Short name*) when it is opened; saved in sessions (optional fields,
  old sessions get them assigned in order).
- **Files panel:** a colour bar and the tag on each file header.
- **Legend chips:** a small coloured tag badge (`A`) instead of the long ` · file.csv` when 2+
  files are open; the name truncated in the MIDDLE, never the end; the tooltip = full signal name +
  full file path (+ the hint on a second line).
- **Plot colour mode** (Plot options, and a default in Settings Q34): *by signal* (today) /
  *by file* (each file its colour, several signals of one file in shades of it, or a dash pattern
  per signal). Automatic choice: when a plot holds the SAME signal name from 2+ files, colour by
  file (Compare open files, Link files, Compare runs' "show").
- **Everywhere else the file is named:** Compare runs (replaces the local `runColor`), the map
  and 3D tracks, the cursor table in the Inspector, the signal pickers (Create signals, X axis,
  formula `ExprInput`), the report legend.
**Done when:** e2e: two files, same signal from both → different colours, chips show A / B,
tooltip has the path; unchecking a run in Compare does not change colours; a session from 1.6
opens with tags assigned.

### Q46 · T47 A second value axis for different units — M
**Seen:** GroundSpeed [m/s] (0-60) and Battery [V] (14-16) in one plot: the battery is a flat line
at the bottom. Today only scale / offset per signal or a separate plot help.
**Steps:** per signal "axis: left / right" (chip menu *Move to the right axis*); automatic
suggestion when a signal's unit differs from the plot's first unit and its range is <10 % of the
axis; the right axis gets the unit label; linkY applies per side; reports and PNG/SVG export draw it
(`plotSpec`). Saved field optional (old sessions: all left).
**Done when:** e2e: speed + battery, battery to the right axis, both readable; export PNG shows
two axes.

### Q47 · T48 First impression — S
**Seen:** *Try an example* opens the files and leaves an empty plot with a card "Suggested view ·
Open it" (and for the car runs nothing). Someone who clicked an example wants to SEE something.
The template chips in the Files panel (Quick look, Compare open files…) open the template library
dialog with an *Open* button - two clicks for something that looks like one.
**Steps:** an example applies its view by itself (the drone: Flight on the map & 3D; two flights:
the map with both tracks + Compare; car runs: Compare open files; ArduPilot: Full review) - one
Undo returns to the empty view; the chip applies directly when the template fits the open files
without questions (choice of file needed → the dialog as today); the card stays for real files.
**Done when:** e2e per example: plots are not empty after one click.

### Q48 · T49 Duplicate and unclear controls — M
Found by listing every control (CLAUDE.md: one place per control, + shortcut / palette):
1. **Two buttons labelled "X"** side by side in the StageBar: *Link time axes* (🔗 X) and the zoom
   mode (🔍 X). Make the zoom mode a small segmented "Zoom: X | Y | XY" or an icon without the
   letter clash.
2. **The top bar's folder icon opens a SESSION**, while Ctrl+O and "Open files" (in the Files panel)
   open data files - the folder icon is where users look for Open files. Proposal: a **File**
   menu in the top bar (Open files… Ctrl+O, Open recent ▸, Open session… Ctrl+Shift+O, Save session
   Ctrl+S, Save session as…, Clear everything…) and the Files panel keeps "Open files" as the
   in-panel second entry (allowed: the panel is where files are). This also moves the Trash
   (*Clear everything*) away from Save, where a misclick is one dialog away from losing the work.
3. **Clear everything confirmation**: the button says "OK"; make it "Clear everything" in the
   danger style (Cancel default).
4. **Reload a file is in four places**: the per-file ↻ icon, File options > Reload from disk,
   Refresh all (F5) in the panel header, and Live ("refresh every file, then follow"). Keep the
   per-file icon and F5 / panel ↻; remove Reload from File options (or the icon).
5. **Templates have five entry points**: top-bar Templates ▾, the Files panel's Templates strip +
   All templates…, the tab context menu *Templates…*, the smart-start card, the palette. Keep the
   top bar + the strip (it shows what FITS the open files) + palette; drop the tab menu item.
6. **Signal menu (file list) wording:** "Add the result to the active plot" (the Create signals
   string reused - there is no result here) → "Add to the active plot", and when the signal is
   already in it → "Remove from the active plot". "Change the variable…" → "Scale / offset /
   function…" ("variable" is used nowhere else; the app says "signal").
7. **Two ways to change a signal in place:** "Change the variable…" (transform dialog: scale /
   offset / function) and Create signals > *Edit the original* (operations, marked ƒ). Same idea,
   two mechanisms and two markings. Merge into one (one list of steps on the signal), or at least
   name both the same and show both in one place in the Inspector.
8. **Create signals: "One signal" twice** - the mode tab *One signal* and below it the choice *One
   signal / Each of several*. Rename the second "Apply to: this signal / each of several".
9. **Plot mode bar** (Time, X-Y, XYZ, Map, 3D, FFT, Spectrogram, Envelope, Video) is repeated on
   every plot - 4 plots = 36 buttons, and it pushes the legend down. Show it on the active / hovered
   plot only, or as one dropdown with the current mode's name.
10. **Cursor buttons** are the letters "T" and "H" at the far right of the StageBar; give them the
   cursor icons with the tooltip, and put them next to the zoom controls (they are used together).
11. **Compare runs:** each row shows similarity (67.4 %) AND "err 33 %" - the same number twice
   (100 - x). Keep one; use the room for RMS Δ with the unit.
12. **No menu on a right-click in the plot area** (only on chips). Offer: Cursor here, Two cursors
   from here, Note here (N), Zoom back, Reset zoom, Save image.
13. **Help is only the tiny "?" in the status bar** (and *Copy error details* lives inside the
   shortcuts dialog). A Help entry in the top bar or the palette ("Keyboard shortcuts", "Copy error
   details", "Open the examples", "About / version").
**Done when:** each item done or explicitly rejected by the owner (note it here); e2e that use
the old labels updated; README pictures retaken (Releasing step 1).

### Q49 · T50 Small windows and crowded headers — S
**Seen:** Files panel header with 2+ files: ↻, ⇄, 🔗 *Link* and *Open files ▾* do not fit - "Link"
is cut and touches Open files (worse in Hebrew). At 1100x700 with 4 plots each time plot shows ONE
value label on its Y axis ("0") - unreadable. With 6 tabs the top search box shrinks to
"Commands a…".
**Steps:** the header's small actions go into one ⋯ (or wrap to a second row); a minimum of 3 Y
labels (smaller font / fewer X labels when the plot is short), and a hint "too many plots for this
window" below a height; the search box keeps a minimum width and the tabs scroll.
**Done when:** screenshots at 1100x700 en + he, 1 / 4 / 6 plots, 1 / 3 files: nothing cut, every Y
axis has 3+ labels.

### Q50 · T51 Built-in templates in Hebrew — S
**Seen:** in Hebrew the chips and library show *Quick look*, *Compare open files*, *ArduPilot ·
Attitude*…, and the tabs they make are "Compare 1", "Compare 2". `builtin_templates.json` has
English only; the generators name tabs in English.
**Steps:** optional `name_he` / `description_he` (and tab names) in the built-ins, read through
`tx()`; generators name tabs through i18n. User templates unchanged.
**Done when:** screenshot of the library and a Compare result in Hebrew.

### Q51 · T52 e2e "fresh user" — S
**Why:** Q37 and the empty-plot first impression are visible only with an empty profile; the e2e
machines have a used one.
**Steps:** a test file that starts the server with `SV_HOME` (Q38) set to an empty temp folder and
goes: welcome screen → each example → templates library (no error line) → file dialog (opens in a
sensible folder, Esc closes) → Hebrew → back. Collect `pageerror` / console errors and fail on any.
**Done when:** it runs in the suite and fails on 1.6.0 (Q37), passes after.

## Log

- 2026-10-15 · T17f frames as one nested group + preview (in the plot, a plot per axis under
  the grid) + "Add the result to" · `7400e45`, `2a4c321`, dist `80fc362` · done.
- 2026-10-15 · This file created; queue Q1–Q11 · next: Q1.
- 2026-10-15 · Q11: owner decided - user Python only from a local folder the user chooses.
- 2026-10-15 · Q1 / T12 Live MAVLink implemented (record to .tlog + existing live mode) ·
  backend 131, e2e live tests green · left: SITL / radio check by the owner · next: Q2.
- 2026-10-15 · Owner cannot test T12 now - continue with the queue.
- 2026-10-15 · Q2 / T10b same segment across runs · backend 133, e2e compare + workflows green ·
  next: Q3.
- 2026-10-15 · Q3 / T11b batch reports + template matching moved to `svcore/templates.py`
  (pinned to the TS answers) · backend 347, template e2e green · next: Q4.
- 2026-10-15 · Q4 / T29 smart start; F04 fixed (found by T29's test in the full run: a .bin /
  .tlog / .mat in a folder with remembered CSV settings opened with an error); F05 fixed (T11b
  regression: template "Open" before the binding arrived) · backend 348, every e2e file green ·
  next: Q5.
- 2026-10-15 · Owner: go on with every task in the order I set - Q10, Q8, Q5, Q6, Q7, Q9, Q11.
- 2026-10-15 · Q10 / T30 frames suggested from the names · e2e frames tests green · next: Q8.
- 2026-10-15 · Q8 / T16b motor-order marks on FFT plots · e2e fft tests green · next: Q5.
- 2026-10-16 · Owner: middle click no longer closed tabs; list checkboxes unclear - fixed as F06,
  F07 with Q5.
- 2026-10-16 · Q5 / T19 + T20 calmer StageBar, split by edge drop, + F06, F07 · backend 348;
  EVERY e2e file, one per process: 150 passed (features 107, globe3d 10, map_objects 4,
  object_templates 4, offline_map 2, templates_recent_badfiles 11, timeline 5, workflows 7) ·
  next: Q6.
- 2026-10-17 · Q6 / T22 unit, rate and picture per signal in the file list · backend 351; EVERY e2e
  file: 151 passed (features 108 + 43 in the others). The full run caught a test that read the
  template counts before they arrived from the server (since T11b) - the test now waits · next: Q7.
- 2026-10-17 · Release 1.3.0 prepared: version, CHANGELOG (1.1.0 / 1.2.0 / 1.3.0 by what each tag
  had), README, 17 screenshots + 4 clips regenerated by the new `tools/make_readme_media.py`
  (06_3d_terrain and the 02 clip kept from 1.0: see Releasing), dist rebuilt · next: Q7 after the tag.
- 2026-10-17 · v1.3.0 tagged and pushed by the owner (`442bc08`, main and tag). Workflow: a manual
  run without a version now names the files after build.bat's version (was a fixed 1.0.0).

- 2026-10-17 · The v1.3.0 build failed on macOS and Windows: `test_frame_longitude_across_antimeridian`
  compared a computed east of the origin with `== 0` (got 1.9e-13 there). Now a 1 µm tolerance; no
  other computed value is compared exactly. Also on macOS: `test_mavlink_records_and_live_mode_follows`
  stopped waiting at the first poll that saw ANY new data (part of the 30 messages) - now it polls
  until all are in, with longer waits for slow CI machines. The tag is to be made again on the
  fixed commit.
- 2026-10-17 · Review of the whole code; new tasks Q12–Q24 (T32–T43) with an order and a
  progress board in this file · next: Q12.
- 2026-10-17 · Q12 / T32 LICENSE (MIT), README section, installer page, in the builds · next: Q13.
- 2026-10-17 · Q13 / T33 damaged files: fuzz test (126 cases, CI) + CSV repair, zero blocks,
  cut-off .mat recovery · backend 482 · next: Q14.
- 2026-10-17 · Q14 / T34 filters are Butterworth (were a moving average returning raw data on
  failure); dead code out of ops.py; silent handlers narrowed or logged · backend 497 · next: Q15.
- 2026-10-17 · Q15 / T35 main.py split into app/common.py + 12 route modules; OpenAPI and
  route order identical; EXAMPLES path fixed · backend 501 · next: Q16.
- 2026-10-17 · EVERY e2e file run in the foreground after T33-T35 (test_features in 4 slices
  under the sandbox's 5-minute limit): 151 passed - features 108, globe3d 10, templates/recent/bad
  files 11, workflows 7, timeline 5, map_objects 4, object_templates 4, offline_map 2. One features
  test failed once in 3 runs (flaky, see Q17). A detached run hangs (F02) - see Q17.
- 2026-10-17 · Q16 / T36 mypy started (104 findings; `fail` -> NoReturn) · next: finish Q16.
- 2026-10-18 · Owner's Windows run: 2 failures, both in tests. (1) `test_routes_layout` (T35) only
  knew newer FastAPI, which keeps included routers nested; older FastAPI copies the routes into
  the app - the test now checks by endpoint function (verified on FastAPI 0.115 and 0.143, and that
  it still fails when a router is missing). (2) `test_basemap` (older): `os.symlink` needs admin /
  Developer Mode on Windows - falls back to copying.
- 2026-10-18 · F08 CI actions on Node 24 (upload v6, download v7) · Q16 / T36 mypy: 104 -> 0 with
  a per-module baseline; 2 real prefs bugs fixed (9 tests) · backend 510 · next: Q19.
- 2026-10-18 · Owner: MIT licence confirmed. Q19 / T38 local crash report: log file, request /
  thread / job / UI errors logged, Help > Copy error details · backend 517, mypy clean, new e2e
  `test_error_details.py` green, Hebrew layout checked by screenshot · next: Q18.
- 2026-10-18 · Q18 / T37 measured: first open at ~86% of Arrow's own floor; zero-copy parts gave
  nothing measurable (reverted); one idea left, the owner decides whether it is worth it · next: Q17.
- 2026-10-18 · Owner: Q18 is not felt by users -> end of the queue. Q17: F02 not reproduced
  (single file detached x2, whole suite in one process detached: 151 passed, 1 isolation failure
  in the new T38 e2e test) · Q7 read (Workspace, play loop in App.tsx, lazy components), not
  started · next: fix test_error_details in the full run, close F02, then Q7.
- 2026-10-18 · The T38 e2e failure in the whole-suite run was NOT isolation: F09 - run.py served
  the old committed UI (git restored frontend/dist with fresh file times). Fixed (git decides),
  regression test, e2e passes with the old dist in place.
- 2026-10-18 · Release 1.4.0 prepared: version in build.bat / version.py / installer / version_info /
  README, CHANGELOG 1.4.0 with highlights, frontend/dist rebuilt · owner: manual build, check, tag.
- 2026-10-18 · Owner: keep this file current after every task; check the README before every
  official release (now step 3 of "Releasing"). README reviewed for 1.4.0: filters (Analysis row,
  `lowpass` / `highpass` in Formulas), damaged files (Files row), new "Error details" row, test
  commands and counts, the e2e known limitation (whole suite passes in one run), Hebrew "חדש ב־1.4".
- 2026-10-18 · Q17 / F02 closed: the whole suite in one process passed 152/152 twice (detached,
  against a fresh and against the committed dist); `pytest tests/e2e` is the documented way
  (CLAUDE.md, README) · next: Q7.
- 2026-10-18 · Q7 / T15 video: plot mode "video", range-serving endpoint, lock / line-up flow
  (the first "Sync here" design could never change the offset - caught by the e2e test), Hebrew and
  English checked by screenshot (a first layout used half the plot - fixed) · backend 529, mypy
  clean, whole e2e suite 153 passed · next: Q11 + Q20.
- 2026-10-18 · Q11 / T31 backend: worker process, timeout / crash recovery, folder setting,
  op "py" in the analysis engine, endpoints, freeze_support, 10 tests · backend 539, mypy clean ·
  next: the UI of Q11.
- 2026-10-18 · Owner: patches 17-19 applied, backend 539 passed on Windows - the worker process
  (spawn) works there from source. Q11 / T31 UI: Python kind in Create signals, e2e, Hebrew checked
  by screenshot; backend 539, mypy clean, whole e2e suite 154 passed · next: Q20.
- 2026-10-18 · Q20 / T39 push from Python: one-file client, token file, .npz, replace in place,
  events with age (first design missed data sent while the page loaded - caught by e2e) ·
  backend 547, mypy clean, whole e2e suite 154 passed + 1 race fixed (below) · next: Q9.
- 2026-10-18 · The flaky e2e test named: `test_templates_share_mode_lane_and_compare_views` read the
  template's file slots once, before the automatic match filled them (whole-suite runs only) - it
  now waits for the filled state.
- 2026-10-18 · Q9 / T27 MCAP + HDF5: loaders, signatures, live, UI badges; the cut-off test and
  the damaged-files test found two real failures in the first versions (whole-file loss, a
  RuntimeError escaping) and a wrong main-time rule - all fixed · backend 603, mypy clean, whole
  e2e suite 155 passed · next: Q21.
- 2026-10-18 · Q21 / T40 Parquet done (loader, signature, live, UI, 5 tests + 24 damaged copies);
  CAN / MF4: cantools needs python-can (LGPL-3.0), asammdf is LGPLv3+ - asked the owner · backend
  632, mypy clean, whole e2e suite 155 passed.
- 2026-10-18 · Owner: CAN / MF4 postponed (licences). Q22 / T41 fleet backend: SQLite index,
  incremental scans, search by finding / number / mode / text, trends, GPS flight date, job
  routes, 6 tests · backend 638, mypy clean · next: the fleet UI.
- 2026-10-18 · Q22 / T41 fleet UI: side panel, folder jobs with progress, search, trend, open at a
  finding; the e2e test first waited on a STALE "1 flights" (the previous filter's) and assumed a
  vibration value - both fixed (wait for the new list; limit from the data) · backend 638, mypy
  clean, whole e2e suite 156 passed · next: Q23.
- 2026-10-18 · v1.5.0 was tagged without the release patch (version files say 1.4.0); owner: leave
  it, release 1.6.0 properly. New plan Q25-Q35 ("Plan 2026-10-18") · next: Q25.
- 2026-10-18 · Q25 / F10 examples copied into the Windows portable package + package check + test;
  CHANGELOG split: the old "Unreleased" is now "1.5.0" (what the tag had) · backend 639 · next: Q26.
- 2026-10-18 · Q26 / T44 two-flights example (windy twin of uav_flight.csv) + welcome link · backend
  640, mypy clean, e2e workflows example tests green · next: Q27.
- 2026-10-18 · F11 found while making Q27's example: Fleet dated every modern ArduPilot log by the
  file (GPS[0].GMS [s] not read) - fixed + test · backend 641.
- 2026-10-18 · Q27 / T45 ArduPilot example (.bin), welcome names every format · backend 642, mypy
  clean, e2e workflows 9 · next: whole e2e suite (on-screen text changed), then Q23. Note: frontend/dist
  is NOT in the commits from here on (patches stay small; run.py rebuilds; Q35 rebuilds and commits).
- 2026-10-18 · Whole e2e suite after Q25-Q27: 158 passed (one run had a 30 s timeout in
  test_object_templates while the backend suite ran beside it on this 1-CPU sandbox; alone and in a
  quiet full rerun it passes). `.gitattributes`: examples/ binary (a CRLF CSV lost its CRs through
  `git am`). Patches 0001-0007 for the owner (without frontend/dist) · next: Q23.
- 2026-10-18 · Q23 / T42 store.ts split into store/ (5 slices, 4 action files, one entry point) ·
  tsc + build clean, whole e2e suite 158 passed · found F12 (derived-delete Undo overwrote later
  changes) · next: F12, then Q28.
- 2026-10-18 · F12 fixed (toast undoesWs + restore through commit) + e2e that fails without it (a
  first version passed anyway: it waited, and toasts leave by themselves) · next: Q28.
- 2026-10-18 · Q28 / T36b mypy baseline removed (39 -> 0, no real bug among them) · backend 642 ·
  next: phase C, Q29 (T21b).
- 2026-10-18 · Q29 / T21b "Create signal ▸" submenu (menus can nest now) · e2e S06 + new test ·
  next: Q30 (T24).
- 2026-10-18 · Owner: release 1.6.0 now, Q30-Q34 to 1.7.0. Q35 done: version 1.6.0 (build.bat,
  version.py, .iss, version_info.txt), CHANGELOG 1.6.0 (New / Fixed / Inside), README review (examples
  in Quick start + the welcome row, Create signal ▸ in both menu rows, test counts 643 / 160, file
  name 1.6.0, Fleet date, "חדש ב־1.5" - missing since 1.5.0 - and "חדש ב־1.6"), quickstart clip
  retaken (it showed the old welcome screen), frontend/dist built. Found at the release: an index
  from 1.5.0 would keep F11's file dates (scans skip unchanged files) - fleet.INDEX_VERSION + test.
  backend 643, mypy clean · owner: build Windows portable, check examples, tag v1.6.0 · next: Q30.
- 2026-10-18 · Review after 1.6.0 (fresh profile, every control, en + he, 1400x850 and 1100x700):
  9 bugs F13-F21 (Q36-Q44) and usability T24 extended, T46-T52 (Q45-Q51) written down in "Review
  2026-10-18". Checks at the review: backend 643 passed, tsc + mypy clean, CI run 16 green · next: Q38.
- 2026-10-18 · Q38 / F15 tests no longer write to the real ~/.signalviewer; one APP_DIR · backend 645 · next: Q36 (F13).
- 2026-10-18 · Q36 / F13 template colours (allocator; colour per file when a plot holds one signal from several files) · e2e new test passed · next: tab overflow (owner, F22), then Q37.
- 2026-10-18 · Q52 / F22 (owner) many tabs: All tabs list, active tab in view, wheel, Ctrl+PgUp/PgDn, palette · e2e new test · next: Q37.
- 2026-10-18 · Q37 / F14 first-run templates folder · backend test fails without the fix · next: Q39 (F16).
- 2026-10-18 · Q39 / F16 compare wraps angles · backend 650, mypy clean · next: Q40 (F17).
