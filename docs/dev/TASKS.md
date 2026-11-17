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

What is open, in order (the finished history is in the Log and in git: `git show 05f5ed0:docs/dev/TASKS.md`).

| Task | Status | Next step |
|---|---|---|
| M34 FR1-FR12 - the window back to the data (ROADMAP M34) | done, on main (FR9: owner said not now) | - |
| M34 end of round | done - 503 e2e green | the owner tags (the version is not updated here) |
| M34 FR9 - quick_check + the short e2e list in CI on every push | owner: not now | - |
| M34 FR10 - `frontend/dist` and `site/` out of git, built in the release job | done (owner: yes) | - |
| M34 FR11 - welcome cards 11 -> 6, the rest under Help -> Examples | done (owner: yes, one Sweeps) | - |
| M34 FR12 - e2e files named by feature, not by round | done (owner: yes) | - |
| Release 1.28.0 (with SF1 and M34; CHANGELOG 2026-11-17) | ready, not tagged | the owner tags v1.28.0 |
| SW2 (b) - Run again with recording | spec agreed in parts | the owner's final yes on "Open specs" below - do not implement before |
| BR1 - the app as one process (README, docs home, welcome groups) | proposed | the owner's yes on the wording below |
| Stability on Windows with a GPU (Out of Memory, the 3D shader) | waiting for numbers | the owner runs `tools/measure_maps.py --gpu`; the e2e suite's memory |
| Films in Hebrew + a narration script; GitHub About texts | offered / with the owner | his choice; he pastes the About texts |
| Known gap - the 2D double-click on a map object has no e2e test | open | add one when the Map is next touched |
| **M35 (1.29.0) Sweeps - exact numbers, the whole table drawn** (ROADMAP M35; branch `claude/sweeps-full-table-1.29`) | done - version 1.29.0 set, not tagged | the owner tags v1.29.0 |
| M35 FT1 - the brush of All runs resolved on the whole table | done | - |
| M35 FT2 - ParallelPlot in layers, progressive; measured | done | - |
| M35 FT3 - all rows up to the Settings cap, sample from kept rows, exact counts | done | - |
| M35 FT4 - HTML export of a table: all rows up to the cap | done | - |
| M35 FT8 - the rule "no point left out of a picture" + the needle tests | done | - |
| M35 FT9 - filters remember their tab; sets filters show every run of the sets in All runs; holds axis (ROADMAP FT9) | done | - |
| M35 FT7 - X-Y / 3D: extreme-keeping thinning instead of a stride | done | - |
| M35 FT6 - exact Charts in All runs (server statistics, scatter as density + outliers) | done | - |
| M35 FT5 - parallel plot above the cap: density by default, the sample a Settings choice | done | - |

**Decision (owner, 2026-11-17), the rule:** no point is ever left out of a picture - numbers on all the data, a
picture reduced only so every point counts (min/max per pixel, extreme-keeping thinning, density per pixel with the
sparse points drawn); a sample only when chosen, and said (CLAUDE.md). Above the cap the parallel plot draws density
by default, the sample stays a Settings choice. Everything goes into ONE release, 1.29.0, after these fixes.

**Decision (owner, 2026-11-17), M35:** the Sweeps tables are an exception to CLAUDE.md's "the UI receives
decimated data only": every row goes to the page once up to the cap set in Settings (*Most lines to draw*), and is
filtered and drawn there (HiPlot's approach, in our own code - not the hiplot package). Above the cap: a sample of
the rows the filters keep, said on screen. Anything that turns the brush into a result (Keep, Exclude, a group,
Export shown, counts) is resolved by the server on the whole table (`svcore/sweep/select.py`), never from the rows
drawn. Backend density drawing (2D histograms) is a follow-up only (FT5).

## FT9 notes (for the session that takes it over, 2026-11-17)

**Done (2026-11-17).** How it is built: `sweeps/tabs.ts` is the one place that reads the filters by tab -
`filterParts` (both / sets / runs), `ownFilters` (the brushes drawn on the axes of the tab on screen), `acrossFilters`
(the chip), `setKeep` (per set: sets-tab filters + the server's sets for runs-tab filters, `Study.runsTab`, asked by
`refreshRunsTab` from ResultsCenter; not saved), `modeKeep` (the lines kept: ResultsCenter, Desk, ScatterView).
`selection.describeStudy` folds sets-tab filters into `sets` of the description (runSelection, chartSelection: Keep /
Exclude / Export / groups / density / Charts). `view.tableRows` and the report use `setKeep`. A text column's filter
sent by its codes is read by the server's own labels (`select.column_mask`: Parameter sets without the runs on the
page). Saved: `view.filterTab` (optional; missing = "sets"). The holds axis: `state.optAxes` adds `#holds` when the
answer has conditions; `scales.labelOf` reads ✓ / ✗ on a flag column.

- Where the filters live: `view.filters` (sweeps/model.ts `View`, saved in .svsweep / autosave). Add an OPTIONAL saved field
  (e.g. `filterTab?: Record<column, "sets" | "runs">`; missing = "sets") - never rename `filters`. `setFilter` (state.ts)
  records the current `view.mode`.
- What reads the filters today (read every one before changing - CLAUDE.md): ResultsCenter `keep` (keptMask over the mode's
  columns), `selection.runSelection` / `describeRuns` (what the server resolves: Keep / Exclude / Export shown / Save as group,
  and the density / sample requests via `state.drawOf`), `runCharts.chartSelection` (Charts), `view.tableRows` (the table),
  groups' live rules (`groups.fromBrush`), ReportDialog, Desk `useRows`, ScatterView, PlotToolbar ("Clear n filters").
- The rule: in All runs, sets-tab filters -> a mask over the answer's set columns (every set is on the page: exact), folded
  into `sets` of the description (as Show / scope already are) and into the page's own `keep`; runs-tab filters stay run
  filters. In Parameter sets, runs-tab filters -> the sets with a passing run: `/api/sweep/select` answers `sets` - ask only
  when such a filter exists. A parameter's filter is the same either way.
- The chip: one line above the plot (by PlotToolbar), en + he in sweeps/i18n.ts, RTL checked.
- Holds axis by default: `state.defaultAxes` / `optAxes` add "#holds" when the question has conditions; a flag column's axis
  reads ✓ / ✗ (sweeps/scales.ts makeScale: category axis labels).
- Then: a CHANGELOG line in the 1.29.0 section, ROADMAP tick, TASKS log; relevant e2e (tests/e2e/test_sweeps_*.py,
  test_needle.py, test_settings.py); quick_check; the whole e2e suite once (last: 509 passed); then the version 1.29.0:
  build.bat VERSION, backend/app/version.py, CITATION.cff (version, date-released), installer/SignalViewer.iss,
  installer/version_info.txt (see "Releasing"; README checked against the CHANGELOG). Do not tag (the owner tags); no PR
  unless the owner asks.

## Open specs (waiting for the owner)

- **SW2 - the owner (2026-11-16): investigate chosen scenarios from Sweeps without loading everything.** "Many
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
- **SW2 (b) - the proposal, waiting for the owner's final yes (2026-11-16):**
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
- **BR1 - the owner's idea (2026-11-16): brand the tool as one process.** Proposed (in Hebrew to him): "Signal Viewer -
  from one run to a whole sweep, in one place, offline": 1. a run (open, look, find what went wrong); 2. runs (a folder
  of recordings or simulations -> one table, a row each, back to the recording); 3. a sweep (which parameters hold in
  every scenario, the next runs, a re-run with recording for the interesting ones). Waits for his yes; then README,
  docs/index.md and the welcome screen's groups.

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
4. Tag `vX.Y.Z` and push the tag - the build workflow builds the UI for every package (FR10: nothing built is
   committed; check the e2e suite ran on a fresh `npm run build`).

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
- `frontend/dist` and `site/` are not in git (FR10, 2026-11-16): `run.py` builds the UI (first start, changed
  sources), the release job builds it for the packages, the docs workflow builds the site.
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
- 2026-11-16 · SF1 done (Sweeps one flow, Send runs). Tests: Vitest setup.test (+1, readiness without output / goal);
  e2e test_sweeps_workspace (start from nothing and runs first rewritten for Send runs -> first results as a table ->
  goal in its Goal step -> round 2 -> Clear everything + Undo; one flow; the Open ▾ list now has FL1's *From a folder of
  recordings…* - it failed on main before SF1), test_study_loop (How to run in Send runs). Run: test_sweeps_*,
  test_study_*, test_calm_screen, test_folder_of_recordings, test_owner_notes_1_20.
- 2026-11-16 · 1.28.0 release round after SF1: pictures (make_readme_media --only 23 25 26 30 39 40 41 38, examples),
  mkdocs --strict, npm run build; whole e2e suite: 482 passed, 1 failed (test_map_objects follow_and_remove - a
  30 s timeout under load; passes alone). 1.28.0 ready - waiting for the owner's tag.
- 2026-11-16 · M34 opened (the owner's review of 2026-11-16): FR1-FR8 in ROADMAP and on the board; FR9-FR12 wait for the owner.
- 2026-11-16 · FR1 (code): the plot card's head one row (legend beside the title when it fits, no PLOT n · ACTIVE, a lone line's title not repeated), time axis 22 px with its unit, value-axis gutter 8 px narrower. The ArduPilot demo: 21.2 % -> 32.4 % of the window inside the axes; the rest of the 35 % is the rows above (FR2), where test_plot_room's floor goes from 32 to 35. e2e ran: test_plot_room (new, en / he / dark), test_plot_polish, test_plot_menus, test_tab_band, test_overview_strip, test_aligned_plots, test_move_plots, test_move_plots_tabs, test_one_per_plot, test_owner_notes_1_20, test_flat_line_solo, test_plot_style, test_state_lanes, test_less_clutter, test_features, test_workflows, test_wheel, test_setpoint_pairs, test_setpoint_style, test_hover_ghost, test_perf_budget, test_navigation, test_first_minute, test_range_notes, test_what_changed, test_live_report, test_release_1_21, test_round_1112 - 246 green; quick_check green.
- 2026-11-16 · FR1 ticked: with FR2's rows the ArduPilot demo's plots are 36.3 % of the window (test_plot_room asserts >= 35 in en / he / dark).
- 2026-11-16 · FR2: one track above the plots (the flags on the first lane), the run at a glance gives its row to a demo's line while it is up, a demo's line goes (or says its next step) once its button was pressed. First curve at 184 px on the ArduPilot demo (was 271). e2e ran: test_plot_room, test_overview_strip, test_tab_band (one line: closes the demo's line before the strip's ×), test_checks_view, test_flat_line_solo, test_less_clutter, test_plot_polish, test_what_changed, test_welcome_cards, test_first_minute, test_judge_a_run, test_calm_screen, test_fresh_user, test_state_lanes, test_findings_report, test_event_navigation + the 29 files of views that gain space (test_features, test_workflows, test_wheel, test_live_report...) - 304 green; quick_check green.
- 2026-11-16 · FR3: the cursors' labels in the time axis' margin (off the curves, never between the two cursors); a double-click on a signal plots it once. e2e ran: test_cursor_labels (new), test_plot_polish, test_features, test_workflows, test_navigation, test_range_notes, test_what_changed, test_name_tree, test_welcome_cards, test_hover_ghost, test_wheel, test_event_navigation, test_one_per_plot, test_first_minute, test_fresh_user, test_replay, test_timeline, test_plot_room, test_user_reader - 225 green; quick_check green.
- 2026-11-16 · FR4: one colour rule for the same signal from several files (the file's colour; a unit after the name no longer hides the pair) - the sim-against-flight demo: all A lines blue, all B rose. e2e ran: test_file_colours (new), test_compare_diff, test_compare_params, test_compare_similar, test_compare_tolerances, test_template_tabs, test_templates_recent_badfiles, test_object_templates, test_welcome_cards, test_plot_style, test_setpoint_pairs, test_setpoint_style, test_features, test_workflows, test_trust_badges, test_what_changed, test_error_segments, test_aligned_plots, test_owner_notes_1_20, test_release_1_21, test_round_1112 - 227 green; quick_check green.
- 2026-11-16 · FR5: a folder of recordings reads as recordings (4 steps, Limits, no Send / Next runs, no sets; status counts recordings); its demo line names X8-A with *Show X8-A*. e2e ran: test_folder_of_recordings, test_sweeps_flow, test_sweeps_workspace, test_sweeps_data_columns, test_sweeps_groups, test_sweeps_charts, test_study_demo, test_study_loop, test_study_common, test_runs_matrix, test_welcome_cards, test_plot_room, test_tab_band - 97 green; quick_check green.
- 2026-11-16 · FR6: the loop's answer in words at convergence; three equal starts on the empty Sweeps screen; a study's steps say to open one of its tables; "1 table". e2e ran: test_study_demo, test_study_loop, test_sweeps_workspace, test_study_common, test_sweeps_flow, test_sweeps_data_columns, test_sweeps_groups, test_sweeps_charts, test_calm_screen, test_owner_notes_1_20, test_folder_of_recordings, test_runs_matrix, test_welcome_cards, test_first_minute, test_fresh_user - 110 green (one count raced the examples list under load - the test now waits for it); quick_check green.
- 2026-11-16 · FR7: one formula whitelist in svcore/formula.py (signal formulas, Sweeps columns, study constraints); a name with __ is refused everywhere (it was read as a column of that name in Sweeps). Backend: tests/test_one_whitelist.py new, every formula test unchanged. e2e ran: test_conditions, test_sweeps_data_columns, test_sweeps_flow, test_study_common, test_study_loop, test_sweeps_groups, test_occurrences, test_trust_badges, test_error_details, test_features -k formula/derived/create - 67 green; quick_check green.
- 2026-11-16 · FR8: "Current state" is a table of what is open (19 lines; was 227). Its finished history - M33's RV1-RV11 notes, SF1, FL1, the 3D black-out fix, M7, PLAN_2026-11-17, the Sweeps flow, the stability findings, the 1.28.0 release notes - is in git: `git show 05f5ed0:docs/dev/TASKS.md`; the open specs (SW2 (b), BR1) moved whole to "Open specs". No code; no e2e.
- 2026-11-16 · The owner on FR9-FR12: FR9 not now; FR10 yes; FR11 six cards, one of them a Sweeps example; FR12 yes.
- 2026-11-16 · FR10: frontend/dist and site/ out of git; run.py builds the UI on the first start and when the sources changed (one stamp rule, no git history); build.bat / build.sh / the portable build it when missing; CLAUDE.md and the docs follow. Backend tests green (test_launcher rewritten), quick_check green; a fresh-clone start checked by hand. No e2e change (the suite serves the same UI).
- 2026-11-16 · FR11: six welcome cards (one Sweeps: the smart-sweep demo), every example in Help → Examples; tests through `open_example`. e2e ran: test_welcome_cards, test_map_memory, test_compare_diff, test_compare_params, test_compare_tolerances, test_folder_of_recordings, test_judge_a_run, test_study_common, test_sweeps_flow, test_sweeps_workspace, test_file_help_menus, test_workflows, test_first_minute, test_fresh_user, test_calm_screen, test_tour, test_plot_room, test_cursor_labels, test_file_colours, test_study_demo - 136 green (test_fresh_user's examples moved to open_example).
- 2026-11-16 · FR12: test_release_1_21 -> test_tuning_tools, test_round_1112 -> test_map_places_story_export, test_owner_notes_1_20 split into test_plot_polish / test_name_tree / test_map_objects / test_sweeps_flow; E2E_MAP says so at its top. e2e ran: those six files - 72 green.
- 2026-11-16 · M34 end of round: `npm run build` (frontend/dist, now untracked), quick_check green, the WHOLE e2e suite (`python -m pytest -q tests/e2e -n 4 --dist loadfile`): 503 passed, 0 failed, 9 min 55 s. Version not updated - the owner tags.
- 2026-11-17 · Release 1.28.0 prepared (owner: "is it ready?"): M34 folded into 1.28.0 (CHANGELOG dated 2026-11-17, highlights), CITATION dated; README / install / features checked against the CHANGELOG (from source needs Node.js; plot head, cursors, colours, recordings, Sweeps starts, formulas); mkdocs --strict green; pictures retaken (make_readme_media: every docs/images picture and the six cards' pictures - the five moved examples' card pictures removed; the tool waits for the cards and opens moved examples from Help). Owner on FR10: dist stays out of git; `build.bat wheels` / `build.sh wheels` now build the UI so an offline PC gets it. The whole e2e suite ran on 2026-11-16 (503 green) - only docs, pictures and build scripts changed since. Waiting for the owner's tag v1.28.0.
- 2026-11-17 · The v1.28.0 tag's build failed on Windows only: test_sweep_wrapper::test_a_table_of_rows_and_an_outside_simulation - the wrapper split `--sim` with shlex(posix=False), which keeps a quoted program path's quotes ("cannot find the file"). Fixed: `sweep_wrapper.split_command` (Windows: quotes taken off each part, backslashes kept); test_sweep_wrapper +1 checks the Windows rule on any OS. The tag is to be moved to the fix (the owner).
- 2026-11-17 · M35 FT1 (branch claude/sweeps-full-table-1.29, from 75755c1): the brush of All runs resolved by the server on the
  whole table - `svcore/sweep/select.py`, `/api/sweep/select`, export-rows `select`; the page's `sweeps/selection.ts`
  (Keep / Exclude / Export shown / Save as group in All runs); category codes from the whole column. Tests: backend
  test_sweep_select (4, incl. the tiny-cap guard), full backend 1419 green, mypy clean, Vitest 271 green; e2e
  test_sweeps_big_table (new, 200,000 rows), test_sweeps_flow, test_sweeps_groups, test_sweeps_charts - 41 green.
- 2026-11-17 · M35 FT2: ParallelPlot drawn in layers, a frame at a time (`sweeps/progressive.ts`); `setIds` kept per answer.
  Measured in the real app, `tools/measure_sweeps_plot.py` (headless Chromium in the cloud container, no GPU - software
  canvas, 4 cores; 12 axes; Parameter sets mode: a line per set, every line drawn), seconds to the first picture /
  to the full picture, and the longest frame (ms):
  | | open first / full (longest) | filter first / full (longest) | brush: longest frame dragging / full after | hover longest |
  | 50,000, DPR 1 | 0.06 / 1.2 (267) | 0.003 / 0.52 (100) | 17 / 0.68 | 17 |
  | 200,000, DPR 1 | 0.05 / 4.0 (467) | 0.18 / 2.4 (33) | 17 / 2.7 | 17 |
  | 200,000, DPR 2 | 0.07 / 4.5 (550) | 0.15 / 2.9 (33) | 17 / 3.8 | 34 |
  | before (7562c66, one canvas), 200,000, DPR 1 | 2.5 frozen | 1.4 frozen | 917 / 1.2 | 500 |
  (before, the lines left out were not drawn above 60,000; at DPR 2 it did not finish in the prototype). The open's
  long frame is the answer's decode and the first table, not the drawing. e2e: test_sweeps_flow, _groups, _charts,
  _data_columns, _big_table, _workspace - 65 green. Vitest progressive.test.ts (3).
- 2026-11-17 · M35 FT3: the cap in Settings (*Sweeps: most lines to draw*, 200,000), the sample of the runs kept, exact counts.
  Backend 1421 green; e2e test_sweeps_flow, _groups, _charts, _data_columns, _big_table, _workspace, test_settings - 69 green.
- 2026-11-17 · M35 FT4: a table's HTML page carries every row up to the cap and draws in layers. e2e test_sweeps_big_table (3),
  test_sweeps_flow, test_sweeps_charts - green. FT5 written in ROADMAP as a follow-up.
- 2026-11-17 · M35 end of round: quick_check green after a mypy fix (select.py reused a name with two types); whole e2e
  suite 503 passed, 3 failed (test_globe3d x2, test_cursor_labels - all 19 tests of those files green when run alone: load
  on software WebGL with 4 workers, not this round). The owner asked whether anything else samples silently: searched
  the backend and the UI (random samples, caps, strides, slices). Found: Sweeps Charts in All runs drawn from the runs'
  sample above the cap (now said above them - FT6 for exact statistics); X-Y / 3D plots thinned by stride, unsaid (FT7);
  a Checks group's cursor values for its first 200 columns. Not silent: clusters refuse above 20,000 sets; Tacview's
  lowered rate is in the reply; a report embeds signals above 150,000 samples as min/max levels (limitations.md);
  time plots are min/max (every peak kept); Runs x conditions' 200 files and places' 5,000 are said.
  e2e test_sweeps_big_table 4 green.
- 2026-11-17 · The owner's rule (CLAUDE.md): no point left out of a picture. FT8: backend needle tests (tests/test_needle.py) -
  failed on X-Y, the map track, the objects' error trace and the envelope (the time plot kept it). FT7 done: `path_thin` /
  `pathThin` everywhere a stride was (list in ROADMAP); e2e 208 green.
- 2026-11-17 · M35 FT5 done: density by default above the cap (every run a shade, the outliers lines), the sample a Settings
  choice; axes from the whole table's domain. e2e test_needle (2), test_sweeps_big_table (4) green; backend sweep tests green.
- 2026-11-17 · M35 FT6 done: Charts of All runs on every run above the cap (/api/sweep/run-charts); the matrix's stride gone also
  below it. e2e test_sweeps_big_table (4), test_needle (2) green.
- 2026-11-17 · End of round: whole e2e suite 509 passed (0 failed). quick_check found two of mine, fixed: `path_thin` kept the
  last partial chunk whole (192 points where ~100 were asked - test_api_parity; the needle test now checks the count too)
  and 5 mypy errors in routes/sweep.py (Optional narrowing). quick_check green.
- 2026-11-17 · Owner's questions (sets <-> runs): per-set results / best set are on every run (checked). Found: a filter
  made in Parameter sets is applied by name in All runs - on an output it becomes a per-run filter, on the goal / a
  condition / rank / score it is ignored, unsaid. Proposed (waiting for the owner): filters per tab - a sets filter
  means "every run of the sets it keeps" in All runs (a chip says so); a holds axis by default (✓ / ✗); see the reply.
- 2026-11-17 · FT9 done: filters remember their tab (`view.filterTab`, sweeps/tabs.ts); a sets filter on an output's
  mean shows every run of those sets in All runs; a runs filter keeps, in Parameter sets, the sets with a passing run
  (`/api/sweep/select`); the chip above the plot (en + he, RTL looked at); the holds axis ✓ / ✗ by default with
  conditions. Tests: backend `test_sweep_select.py` (+1: exact counts, tiny cap and none), Vitest `tabs.test.ts` (4),
  e2e `test_sweeps_big_table.py::test_a_filter_remembers_its_tab`. e2e run: test_sweeps_*.py + test_needle.py +
  test_settings.py - 73 passed.
- 2026-11-17 · End of round M35: quick_check green; backend 1438 passed (14 skipped), mypy clean; Vitest 279. Whole
  e2e (`-n 4 --dist loadfile`): 507 passed, 3 failed - test_templates_recent_badfiles, test_flat_line_solo,
  test_compare_tolerances (none Sweeps); the three files alone: 22 passed (timing under 4 workers). Version 1.29.0 in
  build.bat, version.py, CITATION.cff, SignalViewer.iss, version_info.txt; docs/install.md file name; docs/features.md
  FT9 line; README checked (nothing out of date). docs/validation.md still says "Signal Viewer 1.28.0" (a measured
  result - re-run the validation to change it). Not tagged (the owner tags).
- 2026-11-17 · Owner: merged to main (fast-forward to 83e516d), only main to stay - the three claude/* branches were
  checked (every commit already in main) but deleting them is refused from the cloud session (HTTP 403): the owner
  deletes them. Charts: a pane's axes span its own group's sets (ScatterView scaleFor, Desk histogram extent), a
  non-empty histogram bin at least 2 px. e2e test_sweeps_charts.py::test_a_chart_spans_its_own_sets_and_shows_a_set_alone;
  test_sweeps_*.py + test_needle.py + test_settings.py: 74 passed; quick_check green.
