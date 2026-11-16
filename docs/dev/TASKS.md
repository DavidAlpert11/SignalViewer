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
  desired.ts). Cleanup (§9) done. Next: the whole e2e suite, mkdocs, `npm run build` once, propose the tag v1.27.0.
- **2026-11-16 · Sweeps as one flow (PLAN_2026-11-16 §7a) - done.** Done: one stepper for every study (Data ·
  Columns · Goal · Results · Next runs; `sweeps/flow.ts`, `FlowNav.tsx`); the tables' column (Navigator) only in Data,
  resizable, a labelled *Remove from the study* with Undo; Next runs = the proposal + *Run from the app* (`NextStep.tsx`,
  `RunPanel.tsx` - the Run column is gone, *How to run* moved there from Set up); the systems together = a tab of
  Results. §7b file dialog done: New folder, Rename (F2), Delete (Del, to the recycle bin - `app/trash.py`, no new
  dependency), only in the user's own folders. The 404 on /api/object_track fixed (a map asked for a closed file's
  track). Stability round done: quick_check green; the whole e2e suite (4 workers, xdist) - 2 timing failures under
  load, both green alone (one wait made state-based); UI built. (Released as 1.27.0 - see R above.)
- **2026-11-16 · main is not stable (owner): Out of Memory, the 3D map's "Fragment shader failed to compile", slow
  maps.** Findings, numbers and plan: `docs/dev/PLAN_2026-11-16.md`. Found: every closed 3D map kept its WebGL
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
- 2026-11-16 · Out of Memory / render error (PLAN_2026-11-16.md): measured v1.26.0, 08f7fbd and main, light and full
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
