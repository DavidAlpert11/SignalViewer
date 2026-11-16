# Work queue and handoff

This file is the **active work queue**: what is open, the current state and a short log, so any developer or agent
can pick up cold. `ROADMAP.md` is the catalogue (every task ID, ticked `[x]` when done) and `/CLAUDE.md` holds the
rules. The full history of the earlier rounds (plans, lane boards, the long log up to 1.28.0) was trimmed on
2026-11-15 and is in git: `git show 6477fd8:docs/dev/TASKS.md` (also the agent prompts, lane notes and mock-ups of
those rounds).

**Keep this file current.** After every finished task (or when you stop in the middle): update "Current state",
tick the task in `ROADMAP.md`, add the user-facing line to `CHANGELOG.md`, and add a line to the "Log".

---

## Current state

- **2026-11-16 · Milestone 33 - clear to a human (owner: "fix everything you think helps a human understand and
  benefit") - in progress.** From the fresh review (`docs/dev/REVIEW_2026-11-16.md`). Order RV1..RV7 (ROADMAP M33).
  RV1 done: a drag on a time plot zooms by its direction - `chartUtil.dragUni` sets uPlot's `drag.uni` during the drag
  to 0.4 × the longer side (within ~22° of an axis = that axis only; diagonal = a box); Shift = values only, Ctrl =
  always a box; the wheel zooms time (value axis / Shift: values); pan moves time, and the values once they are
  zoomed. `zoomMode` (state, actions, StageBar menu, Z, Ctrl+K x3, Help row) removed; an old session's `ui.zoomMode`
  is ignored. The link button reads *Link time* (always visible), not "X". Touches: TimeChart.tsx, StageBar.tsx,
  CommandPalette.tsx, shortcuts.ts, Help.tsx, files.ts, App.tsx, store view slice / actions / types, i18n plots /
  flightlog, docs/features.md.
  RV2 done: `GET /api/runs/{id}/checks-file` runs the checks file kept with the recording (`<name>.checks.json`, else
  the folder's `checks.json`; `app.checks.checks_file_for`) through the CLI's `run_checks` on the open run (new
  optional `store, run_id`); a file none of whose checks find their signals is not shown. `ChecksView.useChecksFile`
  (+ `checksFileCounts`): a *Checks file* card in Checks, counted in the verdict and in the strip's pill; the pill says
  *No limits set* / *none failed* / *n failed* by what was checked. Touches: app/checks.py (CLI unchanged), routes/files.py,
  api.ts, ChecksView.tsx, OverviewStrip.tsx, i18n flightlog / plots.
  RV3 done: `.run-name` min-width min(9ch, 45%); the row's reload / ⋯ in `.run-acts` (width 0 until hover - an
  overlay hid the amber *newer* time under them); `.badge-fmt` hidden below a 380 px list (container query); the
  header count reads *n signals* (the word hidden below 330 px). DataPanel.tsx, index.css, i18n signals.
  RV4 done: the *text read as states* notice dropped (files.ts; `textColsRead` removed); a template's *opened* notice
  2.5 s (templates.ts, TemplateLibrary.tsx). The dock's place (bottom-left, with the start card) unchanged.
  RV5 done: a demo's line above the plots (`demoGuide.ts` DEMO_STEPS + `DemoGuide.tsx`, UI state `demoGuide`; set by
  `Welcome.openExample` once `openPaths` - which now returns the opened ids and, with autoView, waits for the view -
  is done): text + one button per demo (sim: `syncSuggest` best offset -> `applySyncOffset`; investigate: cursors
  38.4-39.3 + Investigate; Compare / Checks / Play). twoFlights: *Position on the map* over every file (the objects
  generator bound to `*all` = a slot per file, objects named "<name> · <file>") as the first tab. The start card no
  longer offers a template made for other formats (the CSV flight got "ArduPilot · Flight on the map") - its own
  Position on the map instead. Card text of simVsFlight: "align their time in one click". Touches: templates.ts
  (objectTabs takes files), smartStart.ts, files.ts (openPaths' return), Welcome.tsx, App.tsx, ui slice, i18n welcome /
  templates, index.css.
  SW1 (owner, between RV5 and RV6) done: the sweep wrapper - `examples/smart_sweep_demo/sweep_wrapper.py` (stdlib;
  `--spec` name: values lines with MATLAB ranges / `--inputs` a CSV of rows / `--list` the app's params files; `--sim`
  "cmd {params}" else sim.py beside it in-process; `--set`, `--out` resumable, `--workers`), `grid.txt`, README;
  `study wrap <script.py> args` (the Portable has no Python: runs the wrapper in-process); launcher `run_as: "wrapper"`
  = the round command (round mode) runs on this PC in a background thread; the demo's launcher uses it (was
  demo-sim per run, local_workers 3). UI: setup.ts parseValues ranges, paramsText / applyParamsText /
  scenariosText / applyScenariosText (*Write as text* in Set up 1 and 2), RunWhere "wrapper" (RunHow 3 choices +
  *Put the example wrapper beside the study* -> POST /api/sweeps/study/wrapper; StudyPanel's select uses setRun),
  scenarios() falls back to demo.scenarios; the demo's About lists the wrapper command, the inputs and the hand run.
  demo.copy_to also copies .txt / .md. Owner's choices: JSON in, Python wrapper, MATLAB start:step:end, extend the
  existing demo.
  **FL1 done (2026-11-16): the Fleet area dropped, from the code and every user doc** (history docs - ROADMAP, REVIEW,
  older plans, CHANGELOG's released entries - keep their record). A folder of recordings = *Summarize a folder ->
  Sweeps*: `folderSummary.ts` is the one way in (Runs matrix, Sweeps' Data *From a folder of recordings…* and its Open ▾
  screen, the welcome card `folderOfFlights` in the Recordings group). The backend uses a folder's `measures.json` when
  no measures are given (`svcore.summary.folder_measures`, also `cli summarize`); `GET /api/summary/folder` says how many
  recordings, the first and its measures. Without measures.json the first recording opens with the Runs matrix
  (`ui.matrixFolder`: a step line, *Summarize <folder>* without asking, *Save measures* writes the folder's
  measures.json). The Sweeps data table: a tick per row with a recording + *Open n in Recordings* (openPaths autoView:
  Compare); the table fills the step (`.sw-raw` flex). examples/fleet -> examples/folder_of_flights (+ measures.json:
  vibration_max, battery_min_V; `{vehicle}_{date}`); its card pictures = the parallel plot. Not done: a chart of
  vibration by date coloured by vehicle (the parallel plot shows the story; Sweeps' scatter is in Results).
  **SW2 - the owner (2026-11-16): investigate chosen scenarios from Sweeps without loading everything.** "Many
  scenarios are run without recording, only a summary row each; to investigate, the interesting ones are run again
  with recording." Two ways from a set / selected rows of a Sweeps table, both on demand only (never load all):
  (a) open their recordings directly when they exist (exists: *Where are the runs' recordings?* / a `recording`
  column - make it one click for several rows: open them together in Recordings, Compare); (b) **Run again with
  recording**: the same inputs, written to one JSON file per run with `"record": "<path>"` added (a time-series
  file to write besides the summary row), run through the study's own way to run (this PC / the wrapper / the farm),
  then the recordings opened together in Recordings. Contract (document it in sweep_wrapper.py, the README,
  docs/launcher.md): a simulation that sees "record" writes its full time series there (CSV or any format the app
  reads); the wrapper gets `--record DIR` (record = DIR/<run_id>.csv) for hand runs; in a study the record path is a
  placeholder `{{record}}` the params template may use (the auto template adds it only for a recording run). The
  demo: sim.py writes a time series when asked (the closed-form attitude step response: t, roll command, roll,
  motor), so in the smart-sweep demo the best set -> *Run again with recording* -> its runs open in Recordings
  (one per scenario, compared). One home for the button: the set's details (SetDetail) and the re-run list
  (RerunList: today only Export) - not a third place. en + he, RTL; backend tests for the contract, e2e for the demo.
  **SW2 status:** (a) done by FL1 (the Sweeps data table's ticks + *Open n in Recordings*). **The owner's answers (2026-11-16, chat) for (b):** (1) which runs record is a **rule set in advance**, default *no recording*; (2) a simulation file takes **one run**, the wrapper **a parameter set** - choose accordingly; (3) the re-runs are **chained**, then a notice says a run is **ready to load** (not opened by itself); (4) a re-run whose summary row differs from the original is **loaded as another layer of results**.
  **SW2 spec - agreed answers, waiting for the owner's final yes (2026-11-16):**
  - A run = one row (inputs + summary outputs); a recording = its full time series. Default: **no recording**.
  - **When to record = a rule set in advance** (Set up, beside *How to run*): none (default) / a rule on inputs or
    outputs (`wind >= 10`, `overshoot > 8`, *every failed run*) / always. Runs the rule picks are **chained**: after the
    summary run they run again with recording by themselves.
  - **What is sent:** the same inputs + `"record": "<path>"`. A simulation file takes **one run** per call; a wrapper takes
    **a parameter set** (its runs in one list). Through the study's own way to run (this PC / wrapper / farm).
  - **Files (the owner's contract):** each run writes `statistic_<id>` (its summary row) and `record_<id>` (its
    recording); one common prefix per kind; both in one folder or each in its own (configurable). At the end the
    wrapper merges every `statistic_<id>` into ONE statistics table - deleting the single-row files by default (an
    option keeps them). Today's results glob (`results/{{table}}/{{run_id}}.csv`) and the demo keep working.
  - **When done:** a notice *N recordings ready* with *Open* - nothing opens by itself; each recording is linked to its
    row (same inputs), a row with a recording shows an icon; rows -> *Open in Recordings* together (FL1's ticks).
  - **A re-run's summary row that differs from the original** (noise, another sim version) is **loaded as another layer
    of results** (rounds already accumulate as layers: next/round_*/collected_<table>.csv) - the original kept.
  - Also by hand: rows / a group / a set (scenarios removable in its details) into the existing re-run list (RerunList),
    which shows the count, an estimate and where the files go - not a new place.
  Touches: study.Launcher (+ optional `record` rule, statistic / record prefixes and folders, keep singles), launcher.py
  (write_params `{{record}}`, chained record round, merge), sweep_wrapper.py (`--record DIR`, the merge), sim.py (a time
  series when asked), SetDetail / RerunList / Set up UI, README, docs/launcher.md.
  RV7 done: the findings chip says *n to look at* (the pill's word); the report's line names the log's own messages; the
  strip's how-to line shown on the first file only (`ovHintSeen` set once shown).
  RV8 done: the Report panel's one offline page (*Save the page (HTML)…* at the top = the HTML report with its replay and
  brand line); Ctrl+K's compact tab page kept.
  RV9 done: the Map's bar - camera, + − fit, Story; the rest under one ⋯ (MapBar `extras`).
  **BR1 - the owner's idea (2026-11-16): brand the tool as one process.** Proposed (in Hebrew to him): "Signal Viewer -
  from one run to a whole sweep, in one place, offline": 1. a run (open, look, find what went wrong); 2. runs (a folder
  of recordings or simulations -> one table, a row each, back to the recording); 3. a sweep (which parameters hold in
  every scenario, the next runs, a re-run with recording for the interesting ones). Waits for his yes; then README,
  docs/index.md and the welcome screen's groups.
  RV10 done: file B rose (was teal-green next to A's blue); setpoints drawn above their measurement.
  RV11 done: Space after a toolbar click = the cursor (keyup kept from the focused button), P plays in pages too;
  formula syntax errors at their place in the typed text, unknown functions named; camera following under Map.
  **1.28.0 ready (2026-11-16, owner: "prepare a release"):** version in build.bat / version.py / CITATION / installer;
  CHANGELOG section with highlights; docs checked against it (install file name, findings wording, From a folder in
  Sweeps' Open ▾); pictures 32, 33, 38 and the training film retaken (no Fleet); validation.md regenerated;
  finished plans removed; `frontend/dist` built. The whole e2e suite (482 passed, 1 failed -> fixed: W16 keeps folders
  in Open ▾, the FL1 button moved there), quick_check and mkdocs --strict green. **Waiting for the owner to tag v1.28.0.**
  Next: SW2 once the owner says yes to the spec above (do not implement before); BR1 waits for his yes.
- **2026-11-16 · The 3D map went black every ~10 s while moving (owner) - fixed.** Cause: each terrarium tile fetched
  in the background bumps `basemap.terrain_version()`; the view polled it every 4 s and replaced
  `scene.terrainProvider` - Cesium drops every tile on screen (the globe blank until reloaded). Now one provider; its
  callback asks with the current version (`terrainV` ref), so tiles asked later are not the browser's cached coarse
  ones; tiles on screen keep theirs until the view asks again. e2e `test_finer_ground_arriving_does_not_blank_the_globe`
  (fails on the old code: the provider replaced).
- **2026-11-16 · M7 Two cameras (owner) - done.** First a *Look freely* toggle in Cockpit (da51c45); the owner then
  asked for less: "enough to mark whether the camera is free or attached to the object; attached: nearer / further /
  turn, every zoom towards the object itself" - reverted (3003e80) and replaced: the Map's camera is *Free · On the
  object* in 2D and 3D. On the object (`Globe3D.tsx` update): `cam.lookAt` at the user's heading / pitch, the range
  read in the object's frame (a time jump keeps it on it), down to 1 m; within `SIT_M` (15 m) its model is hidden
  (checked after each frame drawn - `moveEnd` needs frames the request-render mode does not draw); + − never past it;
  the flight display off by default (it caught the wheel in the view's middle). `mapCamera` = `"free" | "object"` by
  `followObject` alone (old `camera` values unchanged in files); Settings: Free · On the object (an old `chase`
  setting reads as On the object). Removed: From above (and its tilt guard and straight-down fit), Behind it, Cockpit,
  Look at, their strings. The flat drawing: the N button turns track up on / off while on an object. Reports send
  `"centre"` / `"free"`. The owner: the offline pages too - done: `scene3d.html` / `map.html` / `relation.js`
  Free · On the object (On the object: wheel down to 1 m, `sitting()` hides its model within 15 m; the story's close
  moments glide to 70 m), old `#cam=` links mapped; `report._top` (the flat From above picture) removed - the
  report's map picture is the 3D scene. A double-click (2D: also 0) fits everything and sets Free (it fought the
  camera on the object). The owner: "all, in order" - done: (1) the 3D view's keys (arrows: On the object `rotate*`
  look around it, Free a move over the ground along the heading; + − 0 F Q X); (2) Ctrl+K *Map camera: on <object>* /
  *Free* (the active Map, else the tab's first); (3) a double-click on an object = the camera on it (3D: Cesium's
  LEFT_DOUBLE_CLICK marks it, the root's double-click acts; 2D: `objUnder`); (4) `.map-dock .g3-fd` pointer-events
  none (`.map-dock > *` had turned them back on - why it caught the wheel), the flight display shown by default
  while sitting on it (a React `sitting` from the per-frame check; the page the same). One way to set the camera:
  `actions.setMapCamera` (bar, F, double-click, Ctrl+K, Fit, a place's flight). Not tested by e2e: the 2D
  double-click on an object.
- **2026-11-16 · PLAN_2026-11-17 (the owner approved it) - in progress.** Order R, S1, S2, E1, M1, M3, M2 (plan §6).
  R done: the unreleased 1.27.0 and 1.28.0 are one release, **1.27.0** (CHANGELOG merged under `1.27.0 – unreleased`,
  the version files at 1.27.0, the docs' "1.28" -> "1.27"; history not rewritten). The owner tags v1.27.0 once the
  round is stable. S1 done (formula: if / compare / text / bins / rank / pct, a text column is a scenario, share per
  set). S2 done (Table tools: drop Not used, keep runs where, name / unit, fixed values; export CSV / Parquet /
  Excel as edited + recipe). E1 done (Export recording…: signals on screen / all, all / view / cursors / where a
  condition holds, as recorded / a rate with linear + held + anti-alias, CSV / Parquet / MAT / HDF5 + .export.json;
  `svcore/subset.py` also writes the plot's Export CSV and `cli.py export`). M1 + M2 done (Runs matrix: measures per
  run + parameters from the names -> Open in Sweeps; Summarize a folder -> Sweeps as a background job, one file at a
  time - memory measured flat; `cli.py summarize`). M3 done (a set's runs -> their recordings by a folder + a name
  from the row; the fetch command dropped as heavy). P done (Plot the commanded / measured pairs, one detector in
  desired.ts). Cleanup (§9) done. Release readiness done: the whole e2e suite, quick_check, mkdocs --strict green, `frontend/dist` built - **waiting for the owner to tag v1.27.0**.
- **2026-11-16 · Sweeps as one flow (PLAN_2026-11-16 §7a) - done.** Done: one stepper for every study (Data ·
  Columns · Goal · Results · Next runs; `sweeps/flow.ts`, `FlowNav.tsx`); the tables' column (Navigator) only in Data,
  resizable, a labelled *Remove from the study* with Undo; Next runs = the proposal + *Run from the app* (`NextStep.tsx`,
  `RunPanel.tsx` - the Run column is gone, *How to run* moved there from Set up); the systems together = a tab of
  Results. §7b file dialog done: New folder, Rename (F2), Delete (Del, to the recycle bin - `app/trash.py`, no new
  dependency), only in the user's own folders. The 404 on /api/object_track fixed (a map asked for a closed file's
  track). Stability round done: quick_check green; the whole e2e suite (4 workers, xdist) - 2 timing failures under
  load, both green alone (one wait made state-based); UI built. (Released as 1.27.0 - see R above.)
- **2026-11-16 · main is not stable (owner): Out of Memory, the 3D map's "Fragment shader failed to compile", slow
  maps.** Findings, numbers and plan: `docs/dev/PLAN_2026-11-16.md` (removed in the 1.28.0 cleanup: `git show c44fbbb:docs/dev/PLAN_2026-11-16.md`). Found: every closed 3D map kept its WebGL
  context alive (Cesium's static index-buffer cache) up to 16 - fixed in `Globe3D.tsx` (contexts released, render
  error -> light mode -> flat map). Guard `tests/e2e/test_map_memory.py`; measuring `tools/measure_maps.py`,
  `tools/measure_e2e_memory.py`. Waiting for: the owner's numbers on Windows with a GPU (`measure_maps.py --gpu`);
  the e2e suite's memory; the whole suite before the tag.
- **1.28.0 is finished on `main`, not tagged** (the owner tags). Round 2026-11-15: polish before the tag –
  repository cleanup, code reliability, the films and the pictures (marketing).
- Done 2026-11-15 (see the Log): repository cleanup, history rewritten to the owner's identity, e2e speed-up and two
  outdated tests, Align time in the palette, the camera line fades, the offline 3D page's cameras, the pictures
  retaken, the training film remade.
- Open: a Hebrew version of the films and a narration script (offered); GitHub About texts (the owner pastes them);
  the full e2e suite before the tag.
- Media made from the app itself (all in `tools/`): `make_readme_media.py` (pictures, the welcome cards'),
  `make_demo_video.py` (`docs/media/demo_simulation.mp4`), `make_training_video.py` (`docs/media/training.mp4`),
  `make_social_preview.py`, `make_bench_example.py`.

## Releasing

0. Run **ci** by hand first (Actions -> ci -> Run workflow, or `gh workflow run ci`; or put `[ci]` in
   the last commit's message): since 2026-11-01 a push to main runs it only when asked.
1. `python tools/make_readme_media.py` (needs Playwright) refreshes `docs/images` and the welcome cards' pictures
   (`frontend/public/examples`, `--only examples`) from the app itself; it does not make `06_3d_terrain.png`
   (headless, the 3D view runs on software WebGL) - keep or retake it by hand. The films: `tools/make_demo_video.py`
   and `tools/make_training_video.py` (need ffmpeg); `tools/make_social_preview.py` after scene 31.
2. Version in `build.bat` (`VERSION`), `backend/app/version.py` (a test keeps the two equal),
   `CITATION.cff` (`version` and `date-released`; a test checks the version),
   `installer/SignalViewer.iss` (`AppVersion`),
   `installer/version_info.txt` (four places); the workflow takes it from the tag, and a manual
   run (Actions -> build -> Run workflow) with the version left empty takes it from build.bat.
3. CHANGELOG: rename the open section to `## X.Y.Z – date` with a highlights line.
   **README review (owner's rule: before EVERY official release):** go through the CHANGELOG
   section and check each item against the README and the docs site (since Q73 the long parts
   live in `docs/`) - `docs/features.md` (a new or changed feature in its row; the test counts),
   `docs/limitations.md` (remove what was fixed, add what is new), `docs/install.md` (the file
   names with the version, the test commands), `docs/command-line.md`, the README's format list
   and highlights at the top, its Hebrew section (short and structured since Q74: install lines
   and what it does - no version history, the CHANGELOG has it; no `~` outside code, GitHub strikes
   text between two of them), and the pictures (step 1).
   `mkdocs build --strict` must pass (the docs workflow runs it on every push).
   Tests that compare byte lengths of a file they wrote: `write_bytes`, not `write_text` - on Windows
   `write_text` writes `\r\n` (the 1.18.0 tag failed there only).
4. `cd frontend && npm run build` and commit `frontend/dist`; tag `vX.Y.Z` and push the tag.

## How to work here (practical notes)

- **Patches to the owner (owner's rule, 2026-10-19):** every patch sent is ONE file with ALL the
  commits since what is on GitHub now (`git fetch origin` first; `git rebase origin/main` drops what
  the owner already applied; then `git format-patch --stdout origin/main..HEAD`), checked with
  `git am` on a fresh clone. The owner sometimes applies at once and sometimes later - a patch must
  never depend on an earlier patch having been applied.

- Setup: `pip install -r requirements.txt -r requirements-dev.txt`, `cd frontend && npm ci`.
- Run: `python run.py` (builds the UI once by itself when the sources changed, T17e).
- Checks after every change (CLAUDE.md): `cd backend && python -m pytest -q`;
  `cd frontend && npx tsc -b && npm run build`.
- e2e: Playwright, **one file per process**:
  `for f in tests/e2e/test_*.py; do python -m pytest -q "$f"; done`. A custom Chromium can be
  given with `SV_CHROMIUM=/path/to/chrome`. The full set takes several minutes; when time is
  short run the files / `-k` filters that touch what you changed, and say so in the log.
- CI: `.github/workflows/ci.yml` (T64) on every pull request, and on a push to main only when asked (`[ci]` in the last commit message, or Run workflow) - backend tests on
  Python 3.9 and 3.12, mypy, `validate`, tsc + build, and an e2e smoke run (test_fresh_user,
  test_workflows, test_file_help_menus) on the UI built from that commit; a few minutes. `build.yml`
  (tag / by hand) runs the backend tests on Linux, macOS and Windows: compare
  computed floats with a tolerance (`abs(x) < 1e-6`, `pytest.approx`, `np.allclose`), never `==` -
  the platforms' math libraries round differently (T17b's test failed on macOS / Windows at 1e-13).
  Waits in tests: wait for the END state (all the data in), not for "something changed", and allow
  for slow runners (seconds, not tenths).
- Tests reach the app state through `window.__sv.state()` / `window.__sv.setState(...)`
  (`frontend/src/main.tsx`).
- `frontend/dist` is committed. Patches between developers may leave it out (run.py rebuilds);
  rebuild and commit it before a release tag.
- **e2e: build first, then do not touch `frontend/src` while the suite runs.** `run.py` rebuilds the UI
  when the sources are newer than `frontend/dist`; the build takes longer than the fixture's 20 s wait
  for the server, so every file after an edit fails with *Connection refused* (2026-11-01).
- Sandbox gotchas seen so far: a background server or test run started inside a tool call may
  die when the call ends - start it with `setsid nohup ... &`. Never `pkill -f <pattern>` in the
  same shell command line that contains the pattern (it kills its own shell).

- Cloud sandbox: `pip install -r requirements.txt` without pywebview (`grep -vi pywebview requirements.txt > r.txt`),
  `pip install -r requirements-dev.txt`, `cd frontend && npm ci`. Chromium:
  `export SV_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` (the e2e files and media tools read it).
  Videos need Playwright's ffmpeg (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python -m playwright install ffmpeg`)
  plus the system `ffmpeg`. After a frontend change warm the UI build before e2e (`python run.py --port 8777
  --no-open --browser`, stop it after "running at"). A clean probe: `HOME=<tmp> python run.py ...` (no autosave).
  Clean `/tmp/pytest-of-*` between big e2e runs (small disk).

---

## Log

- Up to 2026-11-15: see `git show 6477fd8:docs/dev/TASKS.md`.
- 2026-11-15 · Cleanup (c3e7391→20ed5b5 after the rewrite): agent prompts, lane notes, plans, mock-ups, unused clips 01-08 and
  images 34-37 removed; TASKS.md trimmed; lane markers out of code comments.
- 2026-11-15 · History rewritten (owner's request): every commit and tag by David Alpert <davidalpert11@gmail.com>, the
  Co-Authored-By / Claude-Session lines removed; file trees identical (checked per tag). main force-pushed; tags not
  (proxy) - the owner runs the script from the report.
- 2026-11-15 · e2e: tests/e2e/conftest.py - one Chromium per run, a context per test; big.csv / wide.csv made once. Full
  run 22.6 min (was ~30), 459 passed, 2 failed - test_less_clutter (expected map + 3D: one map since 1.28) and
  test_settings (an external session leaked into the next test) - both fixed and green.
- 2026-11-15 · Align time in the palette (e2e test_calm_screen +1); the camera line fades 5 s after a change (test_map_smooth,
  test_globe3d, test_live_report green); the offline 3D page: five cameras in the app's order, neutral selection
  (test_live_report, test_round_1112, test_map_export, test_scene3d green).
- 2026-11-15 · Pictures: the welcome cards (one map), 20-24 / 32-33 / 39-43 with new scenes, the README and gallery set,
  the social preview. Dead code removed (vulture): 4 functions, 1 parameter; quick_check green.
- 2026-11-15 · Training film remade (each demo once, real actions, the map loaded behind its slide, the 3D relief
  tilted; the recording reports a hardware renderer so the 3D view is drawn as with a graphics card).
- 2026-11-15 · The owner moved the 28 release tags onto the rewritten history from his computer and deleted the old
  branches (the session's proxy refuses tag and branch-delete pushes); checked here: every tag equals the rewrite, every
  commit and tag by David Alpert, only `main` left. GitHub's API counts one contributor (its sidebar is a cache).
- 2026-11-16 · Out of Memory / render error (PLAN_2026-11-16.md, in git: `git show c44fbbb:docs/dev/PLAN_2026-11-16.md`): measured v1.26.0, 08f7fbd and main, light and full
  mode, 20 openings each; fixed the leaked WebGL contexts (0 alive after closing, browser memory flat at ~1.23 GB
  instead of 2.05-2.2 GB), the render-error fallback, the W9 listener and the click handler. e2e: test_map_memory (new,
  3 green); the map files - see the next line.
- 2026-11-16 · Owner's GPU run (Windows): 0 contexts after closing, browser 240-280 MB, draw 1.4 s - the fix holds. The
  start page over open files (brand / Ctrl+K, Back); e2e test_welcome_cards + test_first_minute green (13).
- 2026-11-16 · Sweeps as one flow (§7a): FlowNav (five steps for a table and a study file), Navigator only in Data
  (resizable), NextStep (proposal + Run from the app), Together a tab of Results, Remove from the study (Undo). Saved
  files unchanged (a table's Next runs is its saved `view.center = "next"`, as before). Vitest flow.test.ts; e2e
  test_sweeps_workspace / flow / data_columns / charts / groups, test_study_common / loop / demo, test_welcome_cards,
  test_owner_notes_1_20, test_tour, test_error_details, test_release_1_21 - green (updated for the new places).
- 2026-11-16 · File dialog (§7b): New folder / Rename / Delete inline in the dialog; /api/fs/mkdir, rename, delete
  (to the recycle bin: Windows shell with undo, ~/.Trash, freedesktop trash - app/trash.py; send2trash not needed).
  Refused outside home / data drives, in hidden folders, on a drive or main folder itself, on a file open in the app.
  pytest test_fs_edit (7); e2e test_file_browser_edit (new, 2) + the file-dialog tests of test_features,
  test_first_minute, test_fresh_user, test_templates_recent_badfiles, test_user_reader - 45 green.
- 2026-11-16 · The 404 on /api/object_track (owner's GPU run): a map still on screen while its file closes asked for
  that file's track (the runs changed before the plot unmounted). `positionOpen` skips objects whose position is not
  in an open file (GeoChart, Globe3D). measure_maps --cycles 1: 6 console messages (the 404s) before, 0 after. Vitest
  mapObjects; e2e test_map_memory, test_map_objects, test_globe3d - 26 green.
- 2026-11-16 · Stability round: quick_check green (a radius token fixed). The whole e2e suite with pytest-xdist
  (`-n 4 --dist loadfile`, added to requirements-dev) under measure_e2e_memory: all green except two timing failures
  under the 4-worker load (test_flat_line_solo::test_comparison_lines_wear_their_object, test_round_1112::
  test_the_wow_in_the_3d_page) - both green alone; the 3D one now waits on the state, not 300 ms. Memory: pytest
  123 MB, servers peak 2.5 GB, browsers peak 7.0 GB (4 workers at once), back to 1.7 GB at the end - no steady
  climb. Lesson: warm the UI build first (`python run.py --build`) - after a UI edit each worker built it at once
  and the machine ran out of memory. frontend/dist rebuilt.
- 2026-11-16 · R (PLAN_2026-11-17 §1): 1.27.0 and 1.28.0 merged into one release 1.27.0 - CHANGELOG (one section, the
  highlights written once), build.bat, app/version.py, CITATION.cff, the installer's two files, docs' "(1.28)" -> 1.27.
  pytest test_crashlog (the versions equal) green; mkdocs build --strict green.
- 2026-11-16 · S1 (PLAN_2026-11-17 §2a): Sweeps' row formula (`svcore/sweep/derived.py`) - text values, if() (nested;
  `where` kept as its older name), comparisons chained, Kleene and / or / not, in / not in, between, contains, text,
  bins, rank, pct; a missing value makes a comparison missing (was: false). A text result - or role "hold" - is a
  scenario (`prepare`: new columns before the kept values; `newHolds` in /evaluate with every value). share per set.
  UI: the editor completes text columns and the new functions, shows a text result, *Use as*; the conditions' cards
  include the new scenarios. pytest test_sweep_formula (18, new) + sweep tests; e2e test_sweeps_data_columns (11,
  one new), test_sweeps_flow, test_sweeps_workspace - green; quick_check green.
- 2026-11-16 · S2 (§2b, §2c): Question gets optional labels / units / rowFilter / cells (old studies open as before;
  templates drop cells). Backend: `with_cells`, `_row_filter`, `kept_runs`, `table_as_edited` (evaluate.py); /evaluate
  and /summary honour them ("n of m"); /export-table: csv | parquet | xlsx (Excel row limit said) as edited when a
  question is sent, + `<file>.recipe.json`. UI: `TableTools.tsx` (Columns step fold), `editTable` (one Undo each),
  colLabel shows the name + unit; the save dialog keeps another allowed extension typed. pytest
  test_sweep_table_tools (6, new); e2e every test_sweeps_* + test_file_browser_edit + test_templates_recent_badfiles
  (73) green; quick_check green.
- 2026-11-16 · E1 done (plan §4): **Export recording…** - `svcore/subset.py` (build: timing first / fastest / rate,
  ranges + margin -> a Segment column, states held (`hold_to`), anti-alias = 4th-order Butterworth sosfiltfilt at
  0.4 x the new rate when the source is > 1.25 x faster, MAX_ROWS guard; write: .csv / .parquet (field metadata
  unit) / .mat (valid names) / .h5 (attr unit), via `<path>.part` then replace, `<stem>.export.json`; from_store:
  scale / offset / tOffset, a condition via `store.evaluate_condition` in the first signal's run). Routes:
  `/api/export/recording` (new), `/api/export/csv` now through subset (states held instead of interpolated). CLI
  `export`: --rate --where --margin --no-antialias --from-zero, .parquet / .h5 too (the duplicate `_mat_name` removed
  from cli.py). UI: `ExportRecordingDialog.tsx` (TopBar ⤓ beside Save when a file is open, Ctrl+K "Export
  recording…"; one file or one per open file, the same signals by name), ui slice `exportRecOpen`, strings in
  i18n/files.ts. MAT / HDF5 kept (scipy and h5py are already the readers' dependencies - no new dependency).
  Tests: pytest test_subset_export (8: round trip per format through the app's readers, where, as recorded + from
  zero, anti-alias, mistakes), test_cli_api (+1); e2e test_export_recording (new) + test_features -k N06 green;
  quick_check green; mkdocs --strict green.
- 2026-11-16 · M1 + M2 done (plan §3 / §3a): `svcore/summary.py` - take() (max min mean rms std range first final at
  argmax argmin overshoot settle(2 %)), params_from_name (`kp_{kp}_wind_{wind}` -> groups, matched at the end of the
  name without extension), measure_run (a `where` condition -> its stretches), summarize_run (a Store + run id; names
  without units via resolve_signal_name), folder_files + summarize_files (open_file -> a store of its own per file,
  measured, removed). Route `/api/runs/summary`; job `summarizeFolder` (app/routes/jobs.py, a fresh Store per file);
  CLI `summarize` (files / globs / folders, `--measures` JSON as *Save measures…* writes it, `--pattern`). UI:
  RunsMatrix measures row (chips, + Measure: what / signal with a datalist / at t / only where), the name pattern,
  *Summarize a folder → Sweeps…*, *Save measures…*; ws.measures / ws.namePattern (optional, through commit = Undo);
  the matrix opens with files only (no condition needed), its title "Runs matrix"; Sweeps Navigator *From
  recordings…* opens it. Fixed: a parameter twice (pattern + detected) made Open in Sweeps fail - the matrix shows it
  once and `sweep.io.from_rows` makes duplicate column names unique. Measured (tools/measure_summary_memory.py, new):
  50 parquet files x 2 M rows x 8 signals: RSS 536 MB first 10, 542 MB last 10, peak 555 MB - flat; 8.6 s / file ->
  the folder summary is in the app too (a background job), not CLI-only. Tests: pytest test_summary (4, new),
  e2e test_runs_matrix (3, +1) green; quick_check green.
- 2026-11-16 · M3 done (plan §3a): `svcore/sweep/recordings.py` find_recordings(rows, id column, folder, pattern) -
  `{run_id}` = the Run id column, `{col}` any column, `*` glob, case-insensitive, with or without the extension;
  empty pattern = the stem ends with the run's number (leading zeros allowed); clear errors (no Run id column, a
  column not in the table, a missing folder). `/api/sweep/set` takes `recordings: {folder, pattern}` and, only when
  the table has no recording column, fills recordingPerRun + `notFound` (the folder listed when a set is shown,
  nothing read ahead; supported extensions only). UI: SetDetail *Where are the runs' recordings?* (folder via the
  file dialog, the name pattern, Forget), saved as the optional `question.recordings` (Undo, study file, autosave -
  old studies open as before); a wrong folder / pattern is said and the set still shows. Placement: in the set's
  details (*About this study* is a demo-only page). The fetch command (launcher.fetch) dropped - a new process to
  wait on, heavy for little. Tests: pytest test_sweep::test_recordings_found_from_the_row (new), e2e
  test_sweeps_flow -k recording (3, +1 test_a_runs_recording_found_by_its_number) green.
- 2026-11-16 · P done (plan §8): `desired.ts` - actualNames generalized to the owner's words (des desired dem demand
  cmd command commanded sp setpoint set target tgt ref reference; prefix / suffix, separator or camel case; ArduPlane
  TECS `hdem` / `h`; PX4 `<topic>_<word>.x`), `setpointPairs(ids)` the one detector (same file), `setpointsIn` built on
  it (the dashed look follows the wider words). Action `plotSetpointPairs(runId?)` (actions/plots.ts, through
  plotTabs: a new tab, a plot per pair measured + setpoint, one commit; none: a toast, no step). Entry points: the
  file's menu in the signal list (that file) and Ctrl+K (every open file) - no new button. copter_flight.bin: 6 pairs
  (ATT 3, RATE 3; CTUN.DAlt is not one of the words - left out). Tests: Vitest desired.test.ts (5, new: real
  ArduPilot names, PX4 / word forms, look-alikes rejected, one Undo), e2e test_setpoint_pairs.py (new) green.
- 2026-11-16 · Cleanup (plan §9) done. Removed: 8 unused TS exports (api NO_TOLERANCES, sweeps ShapeStats +
  StepNav's stepTitle / TITLE, events evTime, formulaHelp unknownNames, objectDetect POS_ROLES, studyStore newStudy,
  transforms conversionStep); 22 i18n keys no code uses (en + he; dynamic `prefix_${x}` keys and the keys the
  backend's builtin_templates.json names kept); 50 CSS selectors of components that are gone (sw-explore, sw-facts,
  sw-continue, tpl-row / tpl-pair, net-badge, g3-remove, map-view, wc-group…; dynamic class prefixes kept); the
  routes /api/readers/folder and /api/readers/example and userreaders.set_folder (no UI; the CLI writes the example
  itself). Merged: formula.bool_op - the one Kleene and / or for the signal formulas and the Sweeps columns (derived.py
  now imports _BIN / _CMP / bool_op from svcore/formula.py); app/atomic.py -> svcore/atomic.py, used also by
  study.save, the launcher's submit record and collected CSVs, tacview_csv and subset.write (they had their own
  tmp + replace - now with fsync and the Windows retry); svcore.subset.mat_name is also the Python package's
  Comparison.to_mat name maker (unique names now). Sizes (vite, gzip -9): main index.js 718,009 B / 230,962 gz
  (unchanged - dead exports were already tree-shaken), shared chunk 482,165 -> 480,242 B (157,245 -> 156,719 gz),
  CSS 279,092 -> 276,812 B (45,430 -> 45,026 gz); dist 11,093,597 -> 11,088,196 B. A bigger win left for later: the
  Hebrew dictionary (about half of the shared chunk) loaded only when Hebrew is chosen - it changes `translate`'s
  sync contract, so not before a release. Tests: test_subset_export::test_mat_names_valid_and_unique (new);
  quick_check green.
- 2026-11-16 · Release readiness: the whole e2e suite (4 workers, loadfile): 470 passed, 4 failed + 1 error - alone:
  test_all_runs_shows_the_scenarios, test_comparison_lines_wear_their_object, test_areas_rail_and_views_menu green
  (timing under load); test_less_clutter counted 55 controls > 54 - the one more is E1's TopBar *Export recording…*
  (the plan's place for it, §7; the same 55 on the commit before this session), its limit raised to 55 with the reason.
  quick_check green, mkdocs build --strict green, `npm run build` (frontend/dist committed). CHANGELOG 1.27.0
  highlights name E1 / M1 / M2 / M3 / P / S1 / S2. Proposed to the owner: tag v1.27.0.
- 2026-11-16 · CI (the owner's run, Linux / macOS / Windows) found 4 backend failures, fixed: (1) Excel export (S2)
  needed openpyxl, which was in no requirements - added to requirements.txt (MIT, pure Python), the .spec's hidden
  imports, svcore/extras.py "excel" for the lite package, and a plain 400 when it is missing; (2) test_fs_edit sent a
  file to the CI machine's real bin on Windows / ~/.Trash on macOS while checking the freedesktop one - the test now
  checks the freedesktop bin on every platform (to_trash patched) and _mac on its own; (3) `study submit` without
  --yes on Windows: NUL reads as a terminal, input() met EOF - an EOF is now "no" with the same message; (4) the demo's
  one-minute bound is 120 s on CI (a 3-CPU macOS runner took 64 s; the saving 64x held). quick_check green.
- 2026-11-16 · CI Windows: test_elevation_sources::test_terrarium_is_fetched_in_the_background_and_then_used flaked
  (green on the run before) - a race in the test: the faked fetch can finish before the test read terrain_version();
  it now reads the version before the ask. Not a change of the app.
- 2026-11-16 · Owner's report: satellite zoomed in showed grey "Map data not yet available" tiles (Esri's answer, a
  200 JPEG, where World Imagery has nothing at that zoom). tiles.py: is_no_data (small file, >60 % flat #CCCCCC) for
  the Esri pictures (satellite, esri, light, dark) - never kept, a `.nodata` marker beside the cache (a month), the
  parent tile's quarter enlarged instead (_overzoom, recursive); a placeholder cached by an older version is put right
  when read. One place for 2D, 3D, the exported picture and the composite *Satellite + roads*. Tests:
  test_tiles_no_data.py (3, new); quick_check green.
- 2026-11-16 · **1.27.0 released by the owner** (tag v1.27.0 = c249489, with the Python package). CHANGELOG: 1.27.0 dated,
  a "Next – unreleased" section above it (the satellite no-data fix, 9ab4914). Next: the 3D view's free camera on
  the object (owner's request) - in a new session.

- 2026-11-16 · M7 two cameras (see Current state). Tests: mapCamera.test.ts, mapDefaults.test.ts (+1); e2e
  test_globe3d (test_two_cameras, test_on_the_object_down_to_sitting_on_it new; the chase / look-at test removed;
  the 2D-era map test reads Free), test_live_report::test_one_bar, test_map_smooth (track up by the N); e2e run:
  test_globe3d, test_live_report, test_map_objects, test_map_smooth, test_round_1112; quick_check.
- 2026-11-16 · M7 the offline pages' two cameras + double-click fits Free (see Current state). Tests: test_scene3d,
  test_hidden_objects (the 3D picture whatever the camera); e2e test_round_1112 (the wow: sitting on it, Display),
  test_live_report (the page's two cameras); e2e run: test_round_1112, test_live_report, test_globe3d, test_map_smooth.
- 2026-11-16 · M7 gaps 1-4 (keys, Ctrl+K, double-click on an object, the flight display). e2e
  test_globe3d::test_camera_keys_double_click_and_palette (new), the sitting test (+ the display's pointer-events),
  test_round_1112 wow (the display shown while sitting); e2e run (53 green): test_globe3d, test_map_smooth,
  test_map_objects, test_live_report, test_round_1112, test_calm_screen; quick_check green.
- 2026-11-16 · The black flashes of the 3D map (the terrain provider replaced on each new terrain version) fixed; e2e
  test_globe3d (+1, checked to fail before the fix), test_offline_map, test_map_memory; quick_check.
- 2026-11-16 · The owner: the black flashes are gone. Next: a fresh review of the whole app (report only, no code changes) - handed to a new session (session_0146GPW261MFvWRxQrGUomSU); output docs/dev/REVIEW_2026-11-16.md + a Hebrew page.
- 2026-11-16 · Fresh-eyes review of the whole app (owner): `docs/dev/REVIEW_2026-11-16.md` + screenshots in
  `docs/dev/review_2026-11-16/`. No app code changed. Severe: the pump demo shows *Checks: 0 failed* while its
  checks.json fails 2 of 4 in the CLI. Bugs B1-B10 (file name squeezed away, Fleet "1 vehicle", demo cards that
  promise more than opens...), clarity issues, and a prioritised list for the owner to choose from. Checks run:
  quick_check green, `tools/benchmark.py --synthetic --samples 2000000 --check 3` all met; no e2e (review only).
- 2026-11-16 · M33 RV1 (zoom by the drag's direction, no zoom mode; *Link time*). Tests: chartUtil.test.ts (+1);
  e2e test_features::test_zoom_by_the_drag_direction (replaces test_zoom_y_only_and_back), test_zoom_keys...,
  test_workflows::test_clearer_controls; e2e run: test_aligned_plots, test_timeline, test_wheel, test_workflows,
  test_features -k zoom/drag/wheel/pan/... (51 green).
- 2026-11-16 · M33 RV2 (the checks file beside a recording runs in the window; an honest pill). Tests:
  backend test_checks (+1); e2e test_checks_view (+1), test_plot_polish (the cursors next to Reset zoom - RV1); e2e
  run: test_checks_view, test_plot_polish, test_welcome_cards.

- 2026-11-16 · M33 RV3 (a file's name keeps its room; *n signals*). e2e test_name_tree (the header count), run:
  test_name_tree, test_data_quality, test_refresh_feedback, test_templates_recent_badfiles, test_compare_params,
  test_judge_a_run, test_workflows, test_trust_badges.
- 2026-11-16 · M33 RV4 (fewer notices). e2e test_features::test_D04 (no states notice); run: test_features -k
  D04/template/toast, test_template_tabs, test_welcome_cards, test_first_minute, test_fresh_user.
- 2026-11-16 · M33 RV5 (each demo: what its card promises + one line of what to do next). e2e test_welcome_cards (+2);
  run: test_welcome_cards, test_features, test_first_minute, test_flat_line_solo, test_map_memory, test_object_templates,
  test_one_per_plot, test_overview_strip, test_study_common, test_study_demo, test_study_loop, test_sweeps_flow,
  test_sweeps_workspace, test_what_changed, test_workflows (254 green).
- 2026-11-16 · (owner: a user saw values near 0 shown as 0) checked on this version with a CSV of 1e-9..1e-4 values and one
  of 0.0002 next to 1000: cursor / legend values exact; the plots' value-axis ticks were rounded to one digit
  (`chartUtil.tickValues` toExponential(0): 2.5e-4 -> "3e-4", 1.5e-4 -> "1e-4" = the 1e-4 tick) - fixed (all digits
  needed; XYZChart likewise), Vitest chartUtil.test (+1). Not changed: the data is sent as float32 relative to the
  window's middle (P3), so a value 1e-7 of the window's range (0.0002 beside 1000) is drawn ~1e-5 off - only visible
  zoomed far into the values, and the readouts are exact.
- 2026-11-16 · SW1 sweep wrapper (owner). Tests: backend test_sweep_wrapper (new, 6); Vitest setup.test (+3); e2e
  test_study_loop (+1, the demo's how + the copy's command), run: test_study_loop, test_study_demo.
- 2026-11-16 · Owner: Fleet dropped (FL1, RV6 cancelled) - the plan in Current state; handed to a new session (context).
- 2026-11-16 · Owner: SW2 - from Sweeps, investigate chosen scenarios (open their recordings directly, or run them
  again with recording); queued after FL1 in the session that does FL1.
- 2026-11-16 · FL1 done: Fleet removed (code, strings, styles, tests, docs, site); folder of recordings -> Sweeps (card,
  Sweeps entry, measures.json, ticked rows opened together). Tests: backend test_summary (+2), full pytest green;
  Vitest green; e2e test_folder_of_recordings (new, 2), test_welcome_cards, test_navigation, test_file_help_menus,
  test_runs_matrix, test_sweeps_data_columns, test_sweeps_flow, test_sweeps_workspace, test_owner_notes_1_20 - all pass.
  Owner's answers for SW2 recorded (TASKS Current state, ROADMAP M33).
- 2026-11-16 · RV7 done. e2e run: test_less_clutter (also closes the demo line before counting - RV5 added 2 controls,
  it failed on main before RV7 too), test_workflows, test_flat_line_solo, test_features -k findings/health/report/strip.
- 2026-11-16 · RV8 done. Tests: backend test_replay (+1); e2e test_replay (scrolls to the plot - the report's text is
  above it now), test_live_report, test_workflows, test_features -k report/replay/html.
- 2026-11-16 · RV9 done. e2e: test_globe3d, test_height_profile, test_live_report, test_map_objects. Owner's idea BR1
  (brand as one process) noted, proposal sent.
- 2026-11-16 · RV10 done. backend test_file_marks; e2e test_setpoint_pairs, test_setpoint_style, test_plot_style,
  test_plot_polish, test_tab_band, test_what_changed, test_round_1112, test_release_1_21, test_compare_diff,
  test_runs_matrix.
- 2026-11-16 · RV11 done. backend test_formula_messages (new, 4); e2e test_space_and_settings (new, 2), test_settings,
  test_replay, test_features -k space/setting/replay/formula/fx/cursor.
- 2026-11-16 · Full e2e suite: 482 passed, 1 failed (test_calm_screen W16 - FL1's welcome button moved to Open ▾ and
  Ctrl+K; it and test_folder_of_recordings pass). 1.28.0 prepared: versions, CHANGELOG, docs, pictures 32/33/38,
  training film, validation.md, dist built; waits for the owner's tag.
