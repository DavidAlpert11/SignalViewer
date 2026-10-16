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

- Branch `main`. Applied by the owner up to T29 (not pushed yet: GitHub still at `80fc362`).
  Delivered as a patch on top: T30.
- **Order from here (set 2026-10-15, the owner asked to go on in this order):** Q10 (done), Q8,
  Q5, Q6, Q7, Q9, Q11 - the two small ones first, Q11 (largest) last.
- Released tags: `v1.0.0`, `v1.1.0`, `v1.2.0`. Not yet tagged: T17b–T17f, T12, T10b, T11b, T29, T30.
- Tests at the last change: backend 348 passed; e2e `test_features.py -k "frames_suggested or
  frame_conversion or xyz"` passed (T29's full run: 146 passed in every file).
- Q1 (T12) waits for the owner's check with real SITL / a radio.
- **Next task: Q8 (T16b motor-order marks).**

## How to work here (practical notes)

- Setup: `pip install -r requirements.txt -r requirements-dev.txt`, `cd frontend && npm ci`.
- Run: `python run.py` (builds the UI once by itself when the sources changed, T17e).
- Checks after every change (CLAUDE.md): `cd backend && python -m pytest -q`;
  `cd frontend && npx tsc -b && npm run build`.
- e2e: Playwright, **one file per process**:
  `for f in tests/e2e/test_*.py; do python -m pytest -q "$f"; done`. A custom Chromium can be
  given with `SV_CHROMIUM=/path/to/chrome`. The full set takes several minutes; when time is
  short run the files / `-k` filters that touch what you changed, and say so in the log.
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
**Status:** not started.

### Q6 · T22 Signal list: unit, sample rate, sparkline — M
**Where:** `DataPanel.tsx` (virtualized rows, keep them cheap), `units.ts`, backend run
description (`Store.describe`). Rates / units come from the backend once per file; sparklines
lazily for visible rows only.
**Done when:** a 300-signal file scrolls as smoothly as before (measure); e2e.
**Status:** not started.

### Q7 · T15 Video synchronised to the timeline — M
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
**Status:** not started.

### Q9 · T27 Formats: MCAP (ROS 2), HDF5 — M each
**Where:** loaders in `svcore/*_loader.py`, `Store.open_file`, `DATA_EXTS` in `values.ts`,
`cli.py` (gets them for free through `Store.open_file`). New dependencies need a reason in the
task notes (CLAUDE.md).
**Status:** not started.

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
**Status:** not started (decision made).

### Also open (not queued yet - see ROADMAP)
T14c, T21b, T23, T24, T25, F02 (check on a developer machine / CI), Parquet / MF4,
splitting `main.py` and `store.ts`.

---

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
