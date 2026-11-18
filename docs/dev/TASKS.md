# Work queue and handoff

The **active work queue**: what is open, the specs waiting for the owner, and a short log, so any developer or agent
can pick up cold. Every rule and practice (how to work, test, release, and the prompt to start a session) is in
`/CLAUDE.md`; `ROADMAP.md` is the catalogue (every task ID, ticked `[x]` when done).

History: the full log and the notes of earlier rounds were trimmed on 2026-11-18 and are in git -
`git show 7b16eef:docs/dev/TASKS.md` (up to 1.29.0 and the README / docs-site work), `git show 6477fd8:docs/dev/TASKS.md`
(up to 1.28.0). The removed planning files (the 2026-11-16 review, the modeFRONTIER research, the navigation sketch, the
e2e map, the outreach steps): `git show 7b16eef:docs/dev/<name>`.

**Keep this file current** after every finished task (or when you stop in the middle): "Current state", the
task ticked in `ROADMAP.md`, the user-facing line in `CHANGELOG.md`, and a line in the Log.

---

## Current state

| Task | Status | Next step |
|---|---|---|
| M34 FR9 - quick_check + the short e2e list in CI on every push | owner: not now | - |
| SW2 (b) - Run again with recording | spec agreed in parts | the owner's final yes on "Open specs" below - do not implement before |
| BR1 - the app as one process (README, docs home, welcome groups) | proposed | the owner's yes on the wording below |
| Stability on Windows with a GPU (Out of Memory, the 3D shader) | waiting for numbers | the owner runs `tools/measure_maps.py --gpu`; the e2e suite's memory |
| Films in Hebrew + a narration script; GitHub About texts | offered / with the owner (About texts proposed 2026-11-17) | his choice; he pastes the About texts |
| The branch `claude/readme-redesign` (merged) | to delete | the owner deletes it on GitHub (refused from a cloud session) |
| Known gap - the 2D double-click on a map object has no e2e test | open | add one when the Map is next touched |
| CL2 - cleanup round (owner, 2026-11-18: every change without a version change) | done (full e2e at the end: see the Log) | - |
| Release 1.30.0 (owner, 2026-11-18: "add and release") | prepared: version, CHANGELOG, README / docs reviewed, validation 29 / 29 | build (by hand, 0c42bd2), ci and docs green on all three systems; the owner deletes the v1.29.1 Release and tag, then releases v1.30.0 from the website |
| CP1 - copy a plot / a tab into a Confluence page (owner, 2026-11-18) | done - every sample, via an attachment (his Confluence itself not tested - no access) | the owner tries it on his Confluence 10.2: drag the file onto the page, Insert > HTML, paste |
| RE1 - the report as a document you write (owner, 2026-11-18) | built - 1.31.0 prepared (version, CHANGELOG, README, docs) | the owner looks at the examples and tags v1.31.0; next: RE1.3 (the written text in templates + CLI), the outline / numbering |
| Load: the e2e under heavy parallel load (5 browsers on 4 cores) still time out now and then (open_files > 30 s) | known | only under that load; the suite one file at a time is green |

## Open specs (waiting for the owner)

- **RE1 - done in 1.31.0 (2026-11-18).** The owner left the 10 questions to the agent ("most convenient and simple, e.g.
  [tab1.plot1], variables, formulas - decide, build, release"). Decisions: `docs/dev/REPORT_EDITOR.md` §0. Open: RE1.3
  (templates / CLI carry the text), RE1.4's outline and numbering, RE1.5 (Markdown export, Confluence of the document), RE1.6 (Sweeps).
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

## Log

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
  Later: `tools/make_validation_doc.py` re-run - 29 of 29 within tolerance on 1.29.0 (test_validation checks the page is current).
- 2026-11-17 · Owner: merged to main (fast-forward to 83e516d), only main to stay - the three claude/* branches were
  checked (every commit already in main) but deleting them is refused from the cloud session (HTTP 403): the owner
  deletes them. Charts: a pane's axes span its own group's sets (ScatterView scaleFor, Desk histogram extent), a
  non-empty histogram bin at least 2 px. e2e test_sweeps_charts.py::test_a_chart_spans_its_own_sets_and_shows_a_set_alone;
  test_sweeps_*.py + test_needle.py + test_settings.py: 74 passed; quick_check green (after the validation page was made again).
- 2026-11-17 · Owner: yes, into 1.29.0 - Keep / Exclude act on Show with no filter (PlotToolbar `narrows`); the chip
  counts what is on screen (setKeep + scope + Show; the runs: the plot's exact count). e2e
  test_sweeps_big_table.py::test_keep_works_on_show_and_the_chip_counts_what_is_on_screen; Sweeps + needle + settings
  e2e 75 passed; quick_check green. Whole e2e (-n 4): 509 passed, 3 failed (test_features compare_same_segment, test_flat_line_solo,
  test_name_tree pinned chips - none Sweeps); those three files alone: 142 passed. Ready for the owner's tag v1.29.0.
- 2026-11-17 · RD1: README rewritten on `claude/readme-redesign` (no version change): one-sentence what/for whom, 4 true
  badges (PyPI, Python 3.9+, MIT, docs; the CI badge dropped - CI runs only by hand, so it showed a stale status),
  quick start as a table (Windows / Linux-macOS .7z / pip / source), a picture per area (43, 09, 01, 41, 05, 42 - all
  existing), a formats table, Python + CLI, trust, docs links, Contributing / Citation; Hebrew section kept in line.
  Every relative link checked. Fixed on the way: command-line.md said validate prints "23 passed" (29), features.md
  said five welcome examples (six since 1.28). BR1 wording not used as the tagline - still waits for the owner.
  mkdocs build --strict green; no code changed, so no e2e run.
- 2026-11-17 · RD1 merged to main (owner: straight to main, no PR). RD2 (owner: "redo the whole README"; his idea of a
  satellite picture): new scene `img_44_satellite_flight` in tools/make_readme_media.py - the ArduPilot example in 3D over
  Esri's satellite photos and the terrain, every tile loaded, the cursor at 140.4 s mid-track, altitude and roll under it
  (needs the internet). README rebuilt after a look at PlotJuggler, Rerun, marimo, uv, Polars, napari, DuckDB READMEs:
  a one-command trial at the top, *Why* with bold-lead highlights, the tour as a 2 x 2 grid + the satellite picture +
  the report, CI lines with the validate result, limitations linked from trust. Links checked; no code changed.
- 2026-11-17 · RD3 (owner: pictures that show something happening): two README films, captured frame by frame
  (crisp, repeatable) and joined by ffmpeg into GIFs - 45_sweeps_filter (Show: All, then filters on energy and roll
  error: 810 -> 581 -> 194 ... lines, 661 KB) and 46_satellite_replay (the cursor runs 30 -> 230 s: the vehicle along
  its track over the photos, the cursor in altitude and roll, 2.3 MB). The hero and the other tour pictures stay
  still. 44 (the still) moved to the gallery. mkdocs --strict green; links checked.
- 2026-11-17 · RD4: third README film 47_what_changed (cursors pulled across the roll's jump, the question, the
  answer; 472 KB) in the tour. RD5 (owner: a modern docs home page): site_name shortened to *Signal Viewer*;
  overrides/home.html (theme custom_dir) puts a full-width hero under the tabs - eyebrow, a three-line headline,
  the lead, Download / Get started / Hebrew, `pip install`, the formats, the first picture in a glowing frame;
  docs/index.md rebuilt: five alternating text / picture rows (the three films + checks + report), eight cards,
  four numbers (29 cases, about 2 s for a million runs, all the data, offline), install tabs (Linux / macOS
  added), a closing call to action. extra.css: the landing styles for light and dark, phone widths stack.
  docs.yml also builds on overrides/** and the hooks. mkdocs 1.6.1 + material 9.7.7 (as CI) build --strict
  green; checked at 1440 light / dark and 390 phone.
- 2026-11-17 · RD6 (owner: "continue"): the docs site's other pages. extra.css for every page: bold page titles
  (Material's are thin grey), calmer tables, code in a table breaks between words, a wider grid (72rem) so the long
  tables get room. install.md reorganised for users first - one line on offline, tabs (Windows / Linux-macOS /
  Python / source), the unsigned-package warning as a box (anchor kept), the light install's extras as a table,
  From scripts, If the window does not open (moved up from the build part); then For developers (the build table
  as a list - its paths broke letter by letter). Stale counts fixed: ~1,450 server tests and ~510 browser tests
  (~30 min) - were ~980 / ~320. Nothing removed. mkdocs --strict green; checked at 1440 dark.
- 2026-11-17 · RD7: the PyPI description and keywords (tools/make_pypi.py) and CITATION.cff's abstract and keywords made
  generic as CLAUDE.md's identity rule (they said "flight log & test data"); flight keywords kept for search. PyPI shows
  it from the next release (built from the tag). Checked: pypi_readme already turns the README's relative pictures
  (the GIFs too) into links to the tag. backend -k citation/version/pypi 220 passed.
- 2026-11-18 · CL1 (owner: clean up old task files, no version change; agent guidance in one place): removed
  docs/dev/REVIEW_2026-11-16.md + review_2026-11-16/ (6 pictures), SWEEPS_MODEFRONTIER.md, NAVIGATION.md, E2E_MAP.md,
  OUTREACH.md (all history; in git at 7b16eef). CLAUDE.md is now the one guide: the rules + How to work here + Releasing
  (moved from this file) + the Sweeps exception to "decimated data only" + the prompt to start a session. This file
  trimmed to the queue: open rows (1.28.0 and 1.29.0 are tagged), Open specs, the log from 2026-11-17. References fixed
  (quick_check.py, test_navigation.py, ROADMAP's note). No code changed.
- 2026-11-18 · CL2 (owner: all the cleanup, no version change; "can many requests on big files crash it?"):
  (1) examples written by code - generators moved to backend/svcore/example_data (tools/make_*.py thin wrappers), the
  packages leave out the 24 generated files (12 MB; wheel 27 -> 22.7 MB), /api/examples/{id}/prepare writes them once
  per version under ~/.signalviewer/examples; byte-identical to git (test_example_data), make_pypi --check prepares
  one in a fresh venv, e2e test_fresh_user::test_a_package_writes... (2) ROADMAP reconciled (T12, B / M / D groups
  ticked; T40, T43, F annotated; 21 open, all real). (3) Flaky e2e reproduced under load: the template library's
  reload race (an earlier answer brought the old folder back), the slot note before the binding, a failed binding
  left Open disabled - fixed. (4) Stress test (48 threads, a 410 MB Parquet + a log): 500s from store.list() walking
  dicts without the lock, two derived signals at once took one name (one lost) - fixed with snapshots under the lock
  and a held name (test_concurrency); 48 FFTs at once -> 9.3 GB, the server killed (stats 12 GB) - heavy
  computations now through app.common.heavy (2-4 at once, SV_HEAVY_JOBS): 3-4 GB, drawing 4 ms median meanwhile.
  (5) routes/sweep.py split (sweeps_templates.py, sweeps_report.py). (6) ruff F401/F841/F811 clean on app / svcore /
  tools (ruff itself not added - a dev tool to decide on); mypy --check-untyped-defs: 17 findings, all false
  positives, not switched on. Backend 1442 passed; quick_check green.
- 2026-11-18 · CL2 end of round: whole e2e, one file per process, on a fresh build: 512 passed, 1 failed -
  test_globe3d::test_the_map_from_above_and_the_mouse_readout, failing in every run of the whole file (alone it passed):
  the readout is the pick when the mouse moved, the finer ground (fetched with the network allowed - the sea floor
  here is 2.6 km down) arrives later. The test now waits for the tiles, reads again, and compares the readout with
  the globe's own pick (0.001 deg) and the object (0.05 deg): the file 16 / 16 twice, the test alone green. No app
  change; the version is not changed.
- 2026-11-18 · Release 1.29.1 prepared (owner: yes): version in build.bat, version.py, CITATION.cff, the installer's two
  files; CHANGELOG 1.29.1 with highlights; README / docs review - install.md (the version, where the examples are
  written), performance.md (the load table), features.md, limitations.md (lite's Parquet example, heavy plots wait);
  validation page made again (29 / 29). No interface change: pictures not retaken. ci run by hand ([ci]).
- 2026-11-18 · The v1.29.1 tag's build failed: test_example_data compared generated files byte for byte - Windows / macOS
  differ in the math library's last bit (.bin, .mat), Linux CI in the Parquet bytes (another pyarrow). Now compared as
  the app reads them (the same signals and values to the file's precision; CSV still byte for byte; a changed seed
  still caught). Docs / CHANGELOG: "the same recordings". A build by hand on main started to check all three systems.
- 2026-11-18 · The v1.29.1 tag's second build failed on Windows only (test_loop: progress read while the loop
  saved its study - PermissionError during os.replace): svcore.atomic.read_text retries, the loop's progress written
  whole (64ca504). Then the owner asked for CP1 (copy into Confluence, interactive) -> the release becomes 1.30.0;
  handed to a new session (this one's context was full).
- 2026-11-18 · CP1 Copy for Confluence (interactive) - see Open specs. Checks: quick_check green; e2e:
  test_confluence_copy, test_live_report, test_findings_report, test_features -k "N20 or palette or tab".
- 2026-11-18 · CP1 reworked (owner: every sample must stay interactive): the page with all the data is attached to the
  Confluence page, the macro only fetches it. e2e: test_confluence_copy; quick_check green.
- 2026-11-18 · CP2 (owner): copy a line or a whole plot to another plot - the plot's *Copy to…*, Ctrl+drop of its ⠿,
  the chip's *Copy to plot* / *Move to plot* (any tab). Vitest movePlots; e2e test_move_plots, test_move_plots_tabs.
- 2026-11-18 · Release 1.30.0 prepared (owner: "add and release"): version in build.bat, version.py, CITATION.cff, the
  installer's two files; CHANGELOG 1.29.1 (never published) + CP1 + CP2 -> 1.30.0 with highlights; README (Confluence,
  English and Hebrew), docs "1.29.1" -> 1.30.0, validation page made again (29 / 29). Pictures not retaken (new menu
  items only).
- 2026-11-18 · Full e2e before the release: 94 files, 515 tests, all green (one file at a time).
- 2026-11-18 · build by hand on main (0c42bd2): green on Linux, macOS and Windows (test_loop fix confirmed); ci and docs
  green. Waiting for the owner: delete the v1.29.1 Release and tag, release v1.30.0 from the website.
- 2026-11-18 · RE1 planned (owner: a report written like Markdown / LaTeX with references to values, plots, tabs): studied the
  Report panel, report.py's builders, CP1, plotSpec, sessions / retarget (ids kept), templates (slots by name), batch
  reports, conditions, formulas, stats, areas. Spec `docs/dev/REPORT_EDITOR.md` with 10 questions for the owner. No code.
- 2026-11-18 · RE1 built (owner: "decide, propose, build, organise a release, show examples"). Decisions in REPORT_EDITOR.md §0
  (no new dependency: own Markdown subset, mathtext, a textarea editor). Syntax: [[tab.plot | 10..60, no table]], [[notes]] /
  [[investigation]]..., {{ max(Roll) }} / when="cond" / variables / :.2f. Server: app/reportdoc.py, svcore/docfields.py;
  page shell shared with report.build_html (fill_page, plot_section_html). Found and fixed on the way: Hebrew printed
  backwards in every PDF / picture with matplotlib 3.11 (libraqm orders bidi itself); a preview drawn while a session
  reopens had a plot without lines (now "its signals are not open"). Tests: backend test_report_doc (9), Vitest
  reportDoc.test (6), e2e test_report_doc (2); adapted test_findings_report, test_live_report, test_replay,
  test_workflows. quick_check green (backend 1454, Vitest 288, mypy clean); validation 29 / 29 on 1.31.0; mkdocs --strict.
  Version 1.31.0 in the five places; README / features / limitations / GUIDE / tutorial reviewed; README scenes 32/33/42 updated.
