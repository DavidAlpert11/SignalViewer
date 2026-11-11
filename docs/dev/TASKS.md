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

- **Round of 2026-11-11 (done, 1.26.0)**: one live HTML page (one time bar for the plots, the map and the 3D
  view), the 3D view in reports and replay pages (three.js, offline; a picture in PDF / Word / PNG), one Map
  with a 2D | 3D switch ("3D (XYZ)" for three plain signals). Spec and status: `docs/dev/AGENT_PROMPT_2026-11-11.md`;
  Milestone 29. Left for later: XYZ live in the page, shared tiles / a page budget, the app's screenshot as the picture.

- **Round of 2026-11-10 (done, 1.25.0)**: the owner's round - objects whose position is in metres (NED,
  ENU, ECEF: every ArduPilot EKF lane through ORGN, PX4 / MAVLink local positions), the rings explained,
  comparisons, moving plots across tabs, map export, a scripting API. Spec:
  `docs/dev/AGENT_PROMPT_2026-11-10.md`; board, decisions, open questions (Q1-Q13 with defaults) and notes
  in "Owner's plan (2026-11-10)" below. **Done: all of it (L0-L13), version 1.25.0 (2026-11-11), ready to tag**, with a human-factors review on top
  (`docs/dev/UX_REVIEW_2026-11-11.md`: what was changed, and proposals that wait for the owner). Travels
  as one patch on `e2a75a8` (L7, the last pushed commit): L8-L12, the review, L13.

- **Round of 2026-11-09 (in progress)**: the owner's and a Tacview user's review - map objects found
  and added all at once with *Why?*, dot nesting at any depth, smooth motion and an easy map, primary /
  secondary objects with live relations, error and comparison plots in NED / ECEF, moving plots, line
  defaults, group styling. Spec: `docs/dev/AGENT_PROMPT_2026-11-09.md`; board, decisions and open
  questions (Q1-Q8, each with a default) in "Owner's plan (2026-11-09)" below. Done: N0 (plan, baseline,
  fixture), N1 (dot nesting at any depth), N5 (map objects found, added at once, with *Why?*, looks by class, attitude source, suggestion bar); N6 (measured; playback renders only what moves; map drag / zoom by transform, controls, keys, hint, follow offset, Track up; 3D Chase / Look at with a flight); N7 (primary / secondary, relation box, error / comparison plots, backend op `relate`), N2 (moving plots), N3 (line defaults and styles), N4 (styling a group of lines), N8 (Tacview export; approved), N9 (1.24.0 prepared, full checks green, `frontend/dist` committed; not tagged). The round is complete. The work travels as one cumulative patch on `dafea49`.

- **Round of 2026-11-08 (in progress)**: the owner's audit round - correctness, trust, performance,
  a calmer UI (spec and board in "Owner's plan (2026-11-08)" below; IDs there are qualified as
  `26.<id>` where they collide with Milestone 25). **Phase 1 done:** C1 (Compare judged on every sample
  of both runs), C2 (state signals held in formulas / operations / conditions), C3 (missing stays
  missing; `params.nan`), C4 (V24-V28; V29 moves to P1), C2b (old sessions restored with `"hold": false`),
  C3b (*Missing values* in Create signals, the mark). **Phase 2 done:** O1 (offline by default, Never use
  the network, the Online map sign), O2 (no phantom signals from damage; a damaged .ulg opens), O3 (every
  save atomic: `app/atomic.py`, re-exported by app/common.py). Applied by the owner up to `4c3c52f`
  (O1); the Phase 2 patch carries C2b, C3b, O2, O3. **Phase 3:** P1 done (offsets without a copy: ~50 ms -> ~3 ms per request at 20M samples; V29). P2 done (one memory cache, bytes, locked; Settings shows it). P3 done (cancellation, binary /api/data, float32 around a float64 reference, joinTables). P4 done (several files at once within a memory budget). P5 done (`benchmark.py --synthetic`; the file mode works again). **Phase 3 done** (patch sent, not applied yet - the next patch carries it). Phase 4: 26.A1 done. 26.A2 done (readers in a worker process). 26.A3 done (filters in time, windows in seconds). 26.A4 assessed: larger than the task - waiting for the owner. 26.A5 done (read-as correction, angle unit's why). **Phase 4 done** except 26.A4. Phase 5: 26.U1 done (tokens), 26.U2 done (palette, ink, hover, difference chart). 26.U3 done (58 -> 54 / 80 -> 71 controls). 26.U5 done before 26.U4 (per-signal tolerances, the CLI's file, one rule `svcore/tolerances.py`). 26.U4 done (golden runs, start-card proposal, verdict, worst failure, report). 26.U6 done (trust badges, network in the status bar). 26.U7 done (data quality on open). 26.U8 done (one events list, ] / [). **Phase 5 done** (whole e2e next). Phase 6: T1 done (Vitest, 24 tests), T2 done (78 sleeps -> 30), T3 done (CI: npm test, 18 e2e files, benchmarks --check 3). **Phase 6 done.** Final checks done (2026-11-09: backend 1081, mypy clean, validate 29/29, tsc + build, Vitest 24, whole e2e 332 + test_features alone 126, benchmark --synthetic --check 3, mkdocs --strict); the cumulative patch (23 commits on a39b8d5) sent. Release 1.23.0 prepared (version, CHANGELOG, README, pictures, dist) - the owner runs ci, builds on Windows and tags. Waiting for the owner: Phase 7 (F1-F4), 26.A4, the decisions listed in the log; 26.A4 (ask first if large), 26.A5, then a cumulative patch;
  the whole list is the board in "Owner's plan (2026-11-08)". Baseline before the round: backend 981
  passed / 14 skipped, `cli.py validate` 23 / 23 - no existing failure. `frontend/dist` is not in the
  patches (run.py rebuilds it); build and commit it before the 1.23.0 tag.

- **1.22.0 (2026-11-07)**: the owner's plan of 2026-11-07 - U1 a template's default tabs (`defaultTabs`,
  `ws.moreTabs`, the views menu), U3 the tab band (TabBand.tsx; the overview strip shows the cursors),
  U2 the findings docked beside the timeline (◆ marks), U6 the ghost on the map / 3D (`s.pointer`), U4
  setpoints dashed (desired.ts, `PlotSignal.dash`), U5 Compare's difference view (`trace`, DiffChart.tsx),
  U7 less clutter (107 -> 85 buttons, 59 controls), U9 navigation option A (Recordings · Sweeps · Fleet,
  Fleet an area, "+ ▾"), M1 hero / social preview / tagline, A1 store.py split (svcore/investigate.py,
  app/livewatch.py, app/filecheck.py, svcore/transforms.py), A2 i18n/ by area, A3 App.tsx 434 lines,
  U8 docs/dev/NAVIGATION.md. Left: test_offline_map's borders test fails here on main too (to check on
  the owner's machine); the built-in Flight tab has no time plot for U6's ghost (owner's choice);
  mypy's 4 numpy-2.5 errors in routes/analysis.py (environment). Not decided: M2, M3, log folders,
  update check, renaming.

- **Next (owner's plan, 2026-11-07)**: U1, U3, U2 (opening a file), M1 (hero / tagline), A1 (split
  store.py), U6, U4, U5, U7 (UX), A2, A3, U8 - spec and board in "Owner's plan (2026-11-07)" below.
  Testing rule changed in CLAUDE.md: relevant e2e per task, whole suite per group and at the end.
  The whole round done 2026-11-07 (U1-U9, M1, A1-A3); release 1.22.0 prepared.

- **1.21.0 (2026-11-05)**: a review before the ArduPilot forum (real logs: Copter 4.5.5, Plane 3.8,
  Copter 3.4 tlog, VTOL tlog; every button clicked in every example). Fixed: same-flight offer for
  unrelated logs (boot / events / signal confirmed by a pair changing together; the Align dialog says
  why), pre-3.4 STATUSTEXT severity, PreArm as a warning, ERR / EV names and levels, motors from
  SERVOn_FUNCTION and RC3_MIN / MAX, battery 2's limits, battery held for BATT_LOW_TIMER (VoltR with
  BATT_FS_VOLTSRC), CSV decimal comma / ISO date-times / no time column (row number, no sorting),
  Esc in a file dialog over another dialog, text Copy with the clipboard fallback, a template
  suggested that opens nothing. Changed: compare tolerance = the larger of abs / pct (SDI); units
  degheading -> deg, UNKNOWN -> none (old sessions mapped in files.ts legacyUnitNames).
  Added: Filter review (ISBH / ISBD decoding with pre / post by the instance offset, burst-averaged
  spectra, svcore/filters.py notch + low-pass response with ArduPilot's coefficients, FFT "Filters"),
  Step response plot (svcore/stepresp.py, Wiener deconvolution), Log ▸ Hardware (svcore/hardware.py,
  ap_names.json from AP_*_Backend.h enums), compare time tolerance (SDI).
  Next (ideas, not started): per-signal tolerances in the Compare panel; an RC sticks widget at the
  cursor (UAV Log Viewer); MAGFit; PX4 vibration metric in the health check; layouts shared as JSON.

- **1.20.1 (2026-11-04)**: a user's request - *Borders* (`geoBorders`, beside the map's layer for the
  offline map and the satellite photos): country borders with a halo, dashed, and names over the
  satellite photos too; the offline map's borders stronger. Left: borders on the 3D globe; finer
  borders (Natural Earth 1:10m) or provinces / states (admin-1) if asked.

- **1.20.0 (2026-11-04)**: the owner's review notes of 2026-11-03 - the legend (beside the plot when
  many, values that do not move it, the line under the pointer in front, 20 colours), made signals
  renamed / re-formulated / deleted from the signal list (dependents asked about, one Undo), named
  nested groups (`ws.sigGroups`, `userGroups.ts`) and a second automatic nesting level, the map / 3D
  track coloured by a state or a value (`trackColor`, `colorSig`; `/api/object_track` `color`), the
  example fleet (`examples/fleet`, `tools/make_fleet_example.py`, *Try the example fleet*), and in
  Sweeps: *All runs* no longer shows the sets while loading, counts in the tabs, rankBy (score /
  pareto), Pareto levels + the balanced set (`#front`, `#knee`, fast non-dominated sorting), *Show
  the Pareto front*, *Clear ▾*. Left: dashes after the 20 colours, groups in templates, the legend's
  auto choice by measuring rather than estimating; test_templates_recent_badfiles failed once and
  passed again (flaky here).
- **1.19.0 (2026-11-03)**: the owner's Sweeps spec (Data, Columns, Goal, Results, Next runs' split,
  Split by) and two Recordings requests (derivatives / integrals of a signal's real updates; images
  for a report and as a page). Left for a next round: the report's charts reordered in the Report
  tab, a suggestion moved to the re-run list in one click, Charts' own SVG / CSV export; the spec's
  open questions (Next runs vs the re-run list; Goal limits vs Must meet). test_plot_menus fails
  here on origin/main too (the window's size in this environment) - to check on the owner's machine.

## Releasing

0. Run **ci** by hand first (Actions -> ci -> Run workflow, or `gh workflow run ci`; or put `[ci]` in
   the last commit's message): since 2026-11-01 a push to main runs it only when asked.
1. `python tools/make_readme_media.py` (needs Playwright + ffmpeg) refreshes `docs/images` and
   `docs/media` from the app itself; it does not make `06_3d_terrain.png` and the
   `02_flight_map_3d` clip (headless, the 3D view runs on software WebGL) - keep or retake those
   by hand.
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

## Owner's plan (2026-11-10): L0-L13 - local-position objects, comparisons, moving plots, map export, an API

**Owner:** the full spec is `docs/dev/AGENT_PROMPT_2026-11-10.md` (kept equal to the copy handed to the
owner); this section is the board, the decisions, the notes and the log lines are in "Log" at the end.

**Work order:** L0 → L13. Groups (whole e2e at the end of each): **A** = L0-L6, **B** = L7-L9, **C** =
L10-L11, **D** = L12, **E** = L13. If time is short, finish a group and stop cleanly.

**How the work travels:** one cumulative patch against `d61ab6d` ("Release 1.24.0"), checked with
`git am` on a fresh clone; `frontend/dist` is **not** in the patch until L13 (the release builds it).

**Baseline (2026-11-10, at `d61ab6d`):** backend 1095 passed / 14 skipped; mypy clean (109 files);
`npx tsc -b` clean; `npm test` 15 files / 71 tests. No failure before the round.

**Decisions taken in group A (each easy to change; say if you disagree):**
1. A group whose last word is `origin`, `ref`, `home` or `datum` is never an object (the spec's L3 rule).
   **Risk:** a simulation's `ref.lat / lon` *trajectory* is no longer offered. Proposed as **Q14** below.
2. An origin "beside" an object counts only when its owner has a class word (`sim.nav_ref` beside
   `sim.tgt`); an origin group *above* (or at the root: `origin.*`) always counts; the nearest wins. Without
   the class-word condition any `x.origin` would attach to every top-level object.
3. A local row with no origin: Advanced… suggests the same file's LLA object, **a receiver first** (its
   first fix), else any; otherwise Manual (Q4's default).
4. The "Position on the map & 3D" template stays latitude / longitude only: templates store roles by
   name and cannot express a frame chain. Local objects come through the bar / found list. (Follow-up.)
5. Known groups get an `order` (POS 0, EKF lanes 1, AHR2 2; PX4 global 0 / local 1; MAVLink global 0 /
   local 1) used only among known groups of one class; other objects keep the file's order.

**Decisions taken in L7:**
6. The words: **Reference** / **Compared with** in English, **בסיס** / **מושווה** in Hebrew - not ראשי / משני
   (too close to ראשית, the origin of a local position) and not ייחוס (already "נקודת ייחוס", the NED origin).
   The code keeps `primary` / `secondary` (state names, sessions unchanged).
7. The 3D view's *Object* and *Second* selects are replaced by the same `RelationPicker` as the map's relation
   box; its *Third* select (a second dashed line) stays in the 3D bar. The 3D data box is unchanged (the map's
   relation box is not shown in 3D - its numbers are already in the data box).
8. The ring tooltip is on the 2D map (the hit-test the click already uses); in 3D the chips and the picker carry
   the ring icons and the same tooltips.

**Decisions taken in L8:**
9. Velocity *values* are shown as recorded (north / east / down), turned to ENU by the frame op when there
   are three components; for ECEF / LLA / track the *errors* are in that frame and the values stay NED (the
   tab says so). Velocity values in ECEF need the position too - a follow-up if wanted.
10. Attitude values are in degrees and every yaw is wrapped as the reference's is (0..360 or -180..180,
    from the reference's minimum) by an `expr` derived signal (`wrap360(deg(v0))`), reused when it exists.
    Quaternion attitudes are not compared yet - the dialog says so.
11. `err_hdg` already uses the yaw when both objects have angles of their own (checked, written in
    relate.py's docstring) - no new yaw error. New: `err_speed` (|v| difference, 2D or 3D as both have it).
12. The four old actions keep their exact results (same functions); re-running anything reuses the same
    relation / frame signals (`findDerived(…, ignore=["group"])`) instead of making `_2` groups.

**Code map of L8:** `relation.ts` (`comparable`, `cmpLayout` (pure, tested), `makeComparison`, `statsCsv`,
`frameOnce`, `exprOnce`; `makeGroup` reuses), `components/CompareObjectsDialog.tsx` (new), `RelationPanel.tsx`
(one `Compare…`, also folded), `ObjectSuggestBar.tsx` (the offer opens the dialog), `CommandPalette.tsx`
(`Compare objects…`), `store/actions/plots.ts` (`plotTabs`: several tabs in one commit, overflow to "name (2)",
left-out signals in a toast; `plotsInNewTab` calls it), `store/slices/ui.ts` (`compareDialog`), `peers.ts`
(`findDerived` ignore), `api.ts` (`Stats.abs_max / t_abs_max / p95_abs`); backend `svcore/relate.py`
(`err_speed`), `svcore/ops.py` (the three statistics), `app/routes/data.py` (`t_abs_max` on the shown axis);
i18n `cmp*` (en + he), `tabsLeftOut`. Tests: relation.test.ts (layout, availability, CSV),
backend/tests/test_local_objects.py (statistics = numpy, speed error), e2e test_local_objects (the dialog on the
EKF lanes), test_object_relations (presets in the dialog).

**Decisions taken in L9:**
13. One bucket of names equal but for one segment can hold several families: it is split by instance base
    (`XKF1[0]` / `XKF1[1]`), by number base (`nav1` / `nav2`), then the class words (`truth` / `nav`), and
    with *More matches* the rest within 1-2 edits - so `ATT.Roll` beside the lanes does not hide them.
14. One reference for all the chosen families (a segment: `phys`, `XKF1[0]`), default a truth-class one,
    else the first family's first member; a family without that segment uses its own default.
15. Angle rule (one helper, `similar.ts` `angleWrap` / `wrapFor`): the leaf is roll / pitch / yaw or an alias
    and the unit says deg / rad → `wrap` 360 / "2pi"; no unit → the backend's angle-unit guess. Used by Compare
    with similar…, `errors.ts` (Errors between two lines) and the Error segments panel. The backend `sub` op
    unwraps B before reading it between samples, then wraps A - B; absent `wrap`: exactly as before.
16. A family whose units differ is shown, values only (no difference made) - said in its row.

**Code map of L9:** `similar.ts` (new: `findFamilies`, `familiesOf`, `referenceOf`, `angleWrap`, `wrapFor`),
`components/CompareSimilarDialog.tsx` (new), `DataPanel.tsx` (group menu + signal menu item), `CommandPalette.tsx`
(`Compare similar signals…`), `App.tsx`, `store/slices/ui.ts` (`similarDialog`), `objectDetect.ts`
(`classOfSegment`, `ANGLE_WORDS` exported), `errors.ts` + `components/ErrorSegments.tsx` + `api.ts`
(`errorSegments(…, wrap)`); backend `svcore/analysis.py` (`wrap_period`, `wrap_diff`, `sub`'s `wrap`),
`app/routes/data.py` (error-segments `wrap`). Tests: `similar.test.ts`, `test_local_objects.py::test_sub_wraps_angles`,
e2e `test_compare_similar.py` (group menu on three_objects; the EKF lanes' yaw across north +0.5°; Ctrl+K).

**Decisions taken in L10:**
17. The tab strip that takes a dragged plot is TopBar's (the spec's "TabBand" is the state lanes' band, not the
    tabs). The handle now shows on a single plot too (it can go to another tab). Drop on a tab: move; Ctrl: copy
    (Q8's default); Shift on another plot: its lines join that plot (the target is outlined, a hint says so).
18. *Move to…* is one submenu (the menu has one level): this tab's cells (swap, as before), `→ <tab>` (its first
    free cell), `+ New tab`. A specific cell of another tab: drag onto that cell in its tab instead.
19. A full tab grows by a column while it is not wider than tall, else a row (every plot keeps its row and
    column), up to MAX_PLOTS (9); a 3x3 tab with no empty cell is refused with a toast.
20. Linked X axes are per tab: a moved plot follows the target tab's link setting.

**Code map of L10:** `store/actions/layout.ts` (`movePlotToTab`, `mergePlotInto`, `mergeKind`, `PLOT_ID_MIME`,
`hasRoom` / `placeIn` / `grown`), `PlotView.tsx` (menu, grip always, Shift+drop merge, cross-tab drop on a cell),
`TopBar.tsx` (tabs take a plot), `CommandPalette.tsx` (Move plot to a new tab / to tab: …), `store/slices/ui.ts`
(`plotDrag`), i18n `plotMove*` (en + he), CSS. Tests: movePlots.test.ts (4 new), e2e test_move_plots_tabs.py
(new, 3), test_move_plots.py (green).

**Decisions taken in L11:**
21. The renderer is its own module, `backend/app/mapimage.py` (not report.py): the export route and the three
    report builders call it, and report.py is already the module of the time / XY / FFT plots.
22. **What a report did before (recorded):** a map plot with objects and no lines was left out twice - the UI's
    report list kept only plots with signals, and the server's `_collect` kept only plot data with signals. A
    map of plain lat / lon lines was drawn as a lon-lat X-Y plot (still so). Now a map with objects is a map.
23. Imagery (Q9's default): the offline basemap always; an online layer only from the tiles already in the app's
    tile cache (never fetched here), a missing one falls back to the offline tile; the attribution of every
    layer used is written on the image / in the page. Note: the fixture's circle lies over the Sea of Galilee,
    so its picture is all water - expected.
24. The standalone page embeds the tiles of the tracks' box (25 % margin) from a zoom that shows it all, adding
    deeper levels while they fit the budget (15 MB for *Save as HTML*, 4 MB per map in an HTML report, half for
    light and half for dark); it says in a comment and in its footer what it holds. Tracks: ≤ 3000 points each.
25. The ⋯ menu of a map with objects: *Save image (PNG) - this view…* (GeoChart registers its view's bounds in
    `globeBridge.geoViewBounds`), *- fit all tracks…*, *Save as HTML (opens offline)…* (SVG / the generic HTML
    page are not offered for such a map: the map's own page replaces them). The 3D view keeps its PNG.

**Code map of L11:** backend `app/mapimage.py` (new: `map_data`, `render`, `build_html`, `tile_bytes`),
`app/report_assets/map.html` (new: the offline viewer), `app/report.py` (`_geo_data`, HTML iframe, PDF / Word
picture, `build_image` / `build_plot_html` for maps), `report_assets/viewer.js` (skips maps),
`app/routes/export.py` (400 on a map with nothing to draw); frontend `plotSpec.ts` (`geoSpec`, `mode: "geo"`),
`globeBridge.ts` (`geoViewBounds`), `GeoChart.tsx`, `PlotView.tsx` (menu), `ReportPanel.tsx` (maps kept),
i18n `mapSave*`. Tests: backend `tests/test_map_export.py` (PNG with the offline basemap and the track's colour,
standalone HTML, refused empty map, reports HTML / PDF / Word); e2e `test_map_export.py` (the page opened with
every request blocked, the slider moves the markers, dark mode, the ⋯ menu).

**Decisions taken in L12:**
26. Q10's default: the tables in one JSON file, `backend/svcore/object_names.json`, imported by objectDetect.ts at
    build time (tsconfig `resolveJsonModule`; the dev server may read `..`: `server.fs.allow`) and read by
    `svcore/objects.py` (the same algorithm, ported); packaged by SignalViewer.spec and (the whole svcore) by
    tools/make_pypi.py. The shared vectors: `tests/data/object_detect_cases.json`, expectations written from the
    app's rules (`SV_WRITE_VECTORS=1 npx vitest run src/objectVectors.test.ts`), checked by pytest.
27. The dialog's statistics (L8) stay on `/api/stats` over the very signals it plots; `svcore/objcompare.py` calls
    the same operations (`frame`, `relate`) and the same `compute_signal_stats`, and
    `backend/tests/test_api_parity.py` proves Python = CLI = REST = the dialog's path to 1e-9. (Routing the
    dialog through `/api/objects/compare` would compute the errors twice: once to plot, once to measure.)
28. The Automatic angle-unit rule moved to `svcore/objcompare.angle_units` (the route imports it): one place.
29. The API compares each object's own angles only (no borrowed attitude: the dialog's *from another row* is a
    UI choice); several files: an object named `file:name` where two files share a name, each on its recorded
    time, the compared object read onto the reference's samples (linear) - as the app's relation signals.
30. `--tolerance` (Q11's default): per quantity, the largest |error| of every component of it must stay within;
    exit 0 / 1 / 2 (2: not comparable), JUnit through `app.checks.junit_xml`, checks in the objects' order.

**Code map of L12:** `backend/svcore/object_names.json`, `objects.py`, `objcompare.py`, `similar.py` (new);
`backend/signalviewer/__init__.py` (`Recording.objects / object`, `Comparison`, `compare_objects`, `similar`,
`compare_signals`, `map_image`, `map_html`, `report`); `signalviewer/cli.py` (`objects`, `compare-objects`,
`compare-similar`, `map`); `app/routes/objects.py` (new: `/api/objects/detect`, `/compare`, `/similar`);
`app/routes/analysis.py` (angle_units imported); `frontend/src/objectDetect.ts` (tables from the JSON),
`objectVectors.test.ts`; docs `docs/api.md` (new, in mkdocs.yml), `docs/command-line.md`. Tests:
`backend/tests/test_objects_py.py` (the vectors), `test_api_parity.py` (four paths, 1e-9).

**Open questions (the work goes on with the default):**
| # | Question | Default if unanswered |
|---|---|---|
| Q1 | Lanes in *Add all* when POS exists | all offered and checked; POS first |
| Q2 | Origin / home as a map marker | never an object; a "home" marker later |
| Q3 | x / y / z with no frame (ROS `pose.position.x`) | a near miss with a better *Why?* |
| Q4 | No ORGN in an ArduPilot log | needs an origin; Advanced… suggests the GPS's first fix |
| Q5 | PX4 / MAVLink origin reset during a flight | first value used, said in *Why?* |
| Q6 | Positions in cm / mm | found, not added by *Add all*, *Why?* points to ƒ |
| Q7 | The relation box's buttons | one `Compare…` with four presets inside |
| Q8 | Move or copy a plot | move; Ctrl while dropping copies |
| Q9 | Map export imagery | offline basemap; online only if on and cached; 15 MB HTML |
| Q10 | One source for detection | shared JSON tables + the same algorithm in TS and Python + shared vectors |
| Q11 | Pass / fail in `compare-objects` | yes, `--tolerance`, JUnit |
| Q12 | Loose matches in *Compare with similar…* | off, behind *More matches* |
| Q13 | The 3D view's *Primary* select | moves into the relation-box header |
| Q14 | (new, L3) Is a group named `ref` (`ref.lat`, `ref_lat`) an origin or a reference trajectory? | origin (never an object) - as the spec says |

**Notes from reading the code (L0, 2026-11-10):**
- Callers: `detectObjects` - templates.ts (objectsFit / objectTabs, LLA only), mapObjects.ts (guessRoles: the
  first LLA candidate), ObjectSuggestBar, ObjectDialog (`detectAll`). `isAdded` / `addable` - ObjectDialog
  only (the bar had its own lat-only test - removed in L4). `ATT_GROUPS` - only `parseName`'s "top-level
  group" test (mapObjects.ts has its own regex of the same name for `guessRoles`, unrelated, unchanged).
- `NED_VEL` / `NED_XYZ_GROUPS` lived in frames.ts; now defined once in objectDetect.ts and imported by
  frames.ts (frames.ts already depended on objectDetect through mapObjects - no new cycle).
- Loader names checked **from the loaders' code** (no real two-lane .bin at hand - please send one):
  bin_loader `MSG[instance].Field [unit]` with the instance from FMTU `#` (XKF1's `C`, ORGN's `Type`);
  ulog_loader `topic.field`, `topic[multi_id].field` only when several instances; tlog_loader converts
  degE7 / mm, so `GPS_GLOBAL_ORIGIN.latitude [deg]`, `.altitude [m]`.
- `XKQ[n].Q1..Q4` not paired (ArduPilot's Q1 is w, the alias table maps q1 → qx) - follow-up, alias table
  unchanged. PX4 `vehicle_local_position.heading` is skipped (it would give a yaw-only attitude instead of
  `vehicle_attitude`'s quaternion).
- Live mode (mavlink.ts) is MAVLink, so LOCAL_POSITION_NED + GPS_GLOBAL_ORIGIN would be found by the same
  rule; not exercised live (not extended in this round, as asked).
- Idea I1 (altitude datum) is easier now: every local object's origin is known with its group (`origin.via`),
  so its datum (ORGN AMSL, ECEF ellipsoid) can be guessed from it.

**Code map of group A:**
- `objectDetect.ts`: `metricPosition()` (frame word in any form, glued `ecefX`, single letters under a
  position / frame sub-group, bare x / y / z a near miss); `Parsed.axis` + `detectNow`'s per-group decision
  (down → NED, up → ENU); `FLAT_VEL` from the shared `NED_VEL`; `KNOWN_GROUPS` new fields `ned / vel /
  origin / originMoves / skip / order / lane` (XKF1, NKF1, vehicle_local_position, LOCAL_POSITION_NED) and
  `NED_XYZ_GROUPS`; `isOriginGroup`, `ORIGIN_WORDS / ORIGIN_GROUPS`; `originOf()` (own → known → sibling);
  `Candidate.origin / badUnit / lane`; a quick pre-filter keeps 5000 names < 100 ms.
- `objectAdd.ts`: `addable` (origin, unit), `objectSources` / `firstSource` / `candidateSource` (the one chain
  walk and the one "already added" rule), `isAdded(c, plot, derived)`, `candidateObject` (NED / ENU with
  `ref: "signals"`), `linkAttitudes(…, derived)`, `whyLines` (origin, lane, unit).
- `ObjectDialog.tsx`: `readSetup` via `objectSources`; row label `frameLabel` ("NED · origin ORGN[0]");
  form preset from the found origin or `suggestedOrigin()`, with a line saying which. `ObjectSuggestBar.tsx`:
  `isAdded` on every map. `frames.ts`: imports the tables. i18n `mapsAnd3d.ts` (en + he), `index.css`.
- Tests: `objectDetect.test.ts` (F1-F10, origins, 5000 metric names), `mapObjects.test.ts` (L3 / L4),
  `backend/tests/test_local_objects.py` (lanes on POS, generic objects, relation lane 1 - lane 0),
  `tests/e2e/test_local_objects.py` (3 flows). Fixtures: `tools/make_local_objects_fixture.py` →
  `examples/ardupilot_lanes.csv`, `examples/local_frames.csv`.

**Code map of L7:** `RelationPanel.tsx` (`RingIcon`, `RelationPicker`; the header: fold + picker),
`GeoChart.tsx` (`objUnder` shared by click and hover, `hover` → `.ring-tip`), `Globe3D.tsx` (picker in the bar,
Third select builds `[secondary, third]`), `PlotView.tsx` (ring icon + tooltip on the chips),
`CommandPalette.tsx` (Set reference object: name / Swap), `Help.tsx` (Q · ⇧Q · X, the rings), i18n
`rel*` (en + he), `index.css` (`.rel-pick`, `.ring-tip`, `.ring-icon`). e2e: `test_object_relations.py`
(new test of L7, adapted words), `test_globe3d.py` (selects by their new labels).

Progress board:

| # | Task | Group | Status |
|---|---|---|---|
| L0 | Baseline, fixtures, notes | A | ☑ done |
| L1 | Metric positions by name (generic rules) | A | ☑ done |
| L2 | Known flight-log groups with local positions | A | ☑ done (names checked from the loaders' code; a real two-lane .bin wanted) |
| L3 | The origin: found, used, explained | A | ☑ done |
| L4 | "Already on the map" for every kind of object | A | ☑ done |
| L5 | The found list and the form for local positions | A | ☑ done |
| L6 | Everything downstream still works | A | ☑ done |
| L7 | Primary / secondary explained, chosen in one place | B | ☑ done |
| L8 | Compare objects: one dialog, values and errors | B | ☑ done |
| L9 | Compare similar nested signals | B | ☑ done |
| L10 | Move a plot to another tab / into another plot | C | ☑ done |
| L11 | Map export: PNG, HTML, maps in reports | C | ☑ done |
| L12 | A clear API (Python, CLI, REST) | D | ☑ done |
| L13 | Docs, changelog, release, full checks | E | ☑ done (1.25.0) |
| R1 | Replay page: the tab as one HTML page to send (one time, Play, marks, `#t=`) | F | ☑ done (1.25.0) |
| R2 | Δ between two cursors in the legend's chips | F | ☑ done (1.25.0) |
| R3 | The timeline maps the recording: the active line along it, the plots' window to drag | F | ☑ done (1.25.0) |

**Group F (2026-11-11, second session, folded into 1.25.0 - the owner's choice):** the design round after the
UX review. Code map: `frontend/src/replay.ts` (`replayBody`, `replayEvents`, `replayMoment`, `makeReplay`) +
the Report panel's `.replay-card` and Ctrl+K; backend `app/report.py` (`_replay`, `REPLAY_CSS`, `_replay_bar`,
`_brand_footer`; `ReportRequest.replay`), `report_assets/viewer.js` (the `RP` block: `setTime`, linked zoom,
Play, marks, `#t=`), `report_assets/map.html` (listens to `{sv: "replay"}`: time, theme, hides its own
slider), `/api/export/open` (HTML files only); `frontend/src/timelineView.ts` + `Timeline.tsx` (`.tl-env`,
`.tl-view`); `PlotView.tsx` (`.chip .dlt`, one narrow `dual` subscription). Decisions: 31. a replay is the
HTML report in one more form, not a second viewer; 32. it opens on the cursor, else the middle of what is
shown; 33. its marks are what the app's timeline marks (log errors / warnings, findings, notes; max 500);
34. Space on the replay's bar buttons plays (a focused button took it as a click). README made short
(306 → 120 lines; the full list is `docs/features.md`). Tests: `backend/tests/test_replay.py` (6),
`replay.test.ts` (5), `timelineView.test.ts` (5), `tests/e2e/test_replay.py` (2); objectDetect's two
timing tests take the best of three cold runs. README pictures `docs/images/32_replay_page.png` and
`33_send_replay_delta.png` (the ArduPilot example: a tab of map + roll + vibration, the replay made from the
Report panel; taken with a Playwright script, not yet a step of `tools/make_readme_media.py`). The standalone
map embeds its tiles with a 75 % margin around the tracks (was 25 %: a frame wider than the tracks showed a
blank edge - seen in the replay). Not done: the Windows build, the tag.

---

## Owner's plan (2026-11-09): N1-N9 - map objects, smooth motion, primary / secondary (Tacview-like)

**Owner:** a hands-on review by the owner and by a friend who uses **Tacview** (map objects tedious, the
map hard to move). The full spec is `docs/dev/AGENT_PROMPT_2026-11-09.md` (the owner's prompt, revised
with him); this section is the board, the decisions and the log. The friend's wishes come first.

**Work order:** N1 → N5 → N6 → N7 → N2 → N3 → N4 → (N8 only if approved) → N9. The task numbers are
IDs, not the order. If time is short, N2, N3 and N4 slip. (The review's findings are called "review
F1-F6" in the prompt; they are not the F1-F4 of Phase 7 of 2026-11-08.)

**How the work travels (owner, 2026-11-09):** the work is done in chat sessions whose machine does not
keep the clone. Every session ends with **one cumulative patch** from `dafea49` to HEAD
(`git format-patch dafea49..HEAD --stdout > signalviewer-2026-11-09.patch`, checked with `git am` on a
fresh clone at `dafea49`) and with this board and the prompt's "Status" section updated for the next
stage, so the owner or any other agent can continue. The next session starts with
`git clone … && git checkout dafea49 && git am < signalviewer-2026-11-09.patch`.

**Testing in this round (owner, overrides CLAUDE.md's "after every change" and per-group rule):** after
each task `cd frontend && npx tsc -b && npm test` (all of Vitest), a Vitest test for every piece of logic
without a screen, `python -m pytest -q -k <area>` on touched backend modules, and **only the e2e files
named in the task** plus the views that gain / lose space. No whole e2e suite, full backend suite,
mypy over everything, benchmarks or mkdocs between tasks: all of them run once, in N9. The checks that
ran are written in the Log.

**Baseline (2026-11-09, at `dafea49`):** `npx tsc -b` clean; `npm test` 8 files, 24 tests passed. (The
full baseline of the previous round, 2026-11-09: backend 1081 passed / 14 skipped, validate 29/29.)

**Owner's decisions (2026-11-09):**
1. Execution: in chat, one cumulative patch against `dafea49`, the prompt updated per stage (above).
2. N5: every nested prefix, at any depth, that holds the object signals (lat / lon / alt and roll /
   pitch / yaw or phi / theta / psi) is proposed; when several are found, add all or choose some.
   Position-only prefixes are proposed too.
3. N5: a position-only object gets an attitude for display from a chosen source: from motion (course
   over ground, flight-path angle; the default) or borrowed from another object (the primary first).
4. N7: once objects exist, offer comparison and difference plots, in NED / ENU / ECEF / LLA / track
   frame (differences in NED at the primary's position at each sample; overlays share one origin).
5. Q8 approved: the known flight-log groups apply to any file, so a CSV with ArduPilot names (`GPS.*` +
   `ATT.*`) stays one object.

**Open questions (the work goes on with the default; each is easy to change):**
| # | Question | Default if unanswered |
|---|---|---|
| Q1 | N2: shortcut to swap the active plot with its neighbour (not Ctrl+Alt+Arrow, not Alt+Shift) | Ctrl+Shift+Arrow |
| Q2 | N5: is the prefix word `ref` truth? (often a commanded / reference trajectory) | "other" |
| Q3 | N6: map keys when the map is focused - ask the friend how Tacview does it | arrows pan (Shift+←/→ still steps the cursor), + / − zoom, F follow, 0 fit all |
| Q4 | N7: keys for primary / secondary | Q / Shift+Q cycle the primary, X swaps |
| Q5 | N7: attitude error | Euler-angle differences wrapped to ±180°; the rotation-based error later if wanted |
| Q6 | N8: export to Tacview `.acmi` - do it at all? | **answered 2026-11-10: yes** (owner: "prepare the conversion to Tacview") |
| Q7 | N9: the version number | 1.24.0 |
| ~~Q8~~ | **Answered (decision 5): yes.** N5 (found in the code): CSVs with ArduPilot message names (`GPS.Lat`, `ATT.Yaw` - `examples/uav_flight.csv`, test_map_objects' file) are one aircraft today. Keep pairing ArduPilot / PX4 message groups as known log groups in CSV too? | yes: the known-groups table applies to any file, so GPS position + ATT attitude stay one object |

**Notes from reading the code (2026-11-09):**
- N1: names such as `GPS.Lat [deg]` (examples/uav_flight.csv) carry a unit in brackets; a trailing
  `[unit]` / `(unit)` is ignored when testing whether a segment is identifier-like (so `GPS.Lat [deg]`
  still nests under `GPS`, and `vel (m/s)` is not split at the `/`). Flight-log names (`GPS[0].Lat`)
  keep today's grouping exactly.
- N6: today bare ←/→ step the cursor, Home / End jump to the ends of the recording, R / Z / D / N / P /
  Space / 1-9 / ] / [ are taken, Ctrl+Tab cycles tabs, Ctrl+0 / Ctrl+= scale the UI (`shortcuts.ts`).
- N7: `svcore/analysis.py` already has `lla_to_ecef`, `_ecef_to_ned`, `_reference` (first / manual /
  signals) and the frame ops; the new relation / error / comparison ops build on them.
- N7 (found while doing N5): `Plot.primaryObject` and `Plot.relatedObjects` already exist (3D: the info box's
  object and dashed lines with distances to the related ones, a select in Globe3D) - N7 extends these
  saved fields rather than adding new ones; `MapObject.cls` (N5) gives the default primary / secondary.
- Fixture: `examples/three_objects.csv` (19 signals + time; phys / nav / gps, GPS at 5 Hz with empty
  cells between fixes), made by `tools/make_objects_fixture.py` (seeded, 120 s at 10 Hz, a circle so
  heading wraps through 0°).

Progress board:

| # | Task | Order | Status |
|---|---|---|---|
| N0 | Plan, baseline, fixture, prompt in the repo | 0 | ☑ done |
| N1 | Dot nesting, always and at any depth (bug) | 1 | ☑ done |
| N5 | Map objects: naming convention, all at once, why each guess; attitude source | 2 | ☑ done (follow-up: a motion attitude from the object's own velocity signals) |
| N6 | Smooth motion and an easy map (Tacview-like) | 3 | ☑ done (reverse playback, a nice-to-have, not done) |
| N7 | Primary / secondary, relations, error signals, comparison plots in frames | 4 | ☑ done |
| N2 | Move plots: swap places in the grid | 5 | ☑ done |
| N3 | Line defaults in Settings, one place that makes a PlotSignal | 6 | ☑ done (opacity left out) |
| N4 | Style a whole group of signals at once | 7 | ☑ done |
| N8 | Export to Tacview `.acmi` (approved 2026-11-10) | - | ☑ done |
| N9 | Release preparation (the only full verification) | 8 | ☑ done (1.24.0 prepared; the owner tags) |

---

## Owner's plan (2026-11-08): C, O, P, A, U, T, F - correctness, trust, performance, a calm UI

**Owner:** an audit before this round listed findings; implement them one at a time with tests, a
cumulative patch (`git format-patch origin/main..HEAD`, checked with `git am` on a fresh clone) at the
end of every phase and whenever work stops. Product identity: *the offline judge of engineering
recordings* - when in doubt, what makes comparing, validating and trusting results better. No scope
growth (no new areas, formats, map or 3D features); Sweeps in maintenance mode.

**IDs.** The owner's IDs are kept. U1-U8 and A1-A5 also name Milestone 25's / earlier tasks, so in
ROADMAP and commit messages this round writes them `26.U1` ... `26.A5` (C, O, P, T, F are not taken
in that form). *Owner to confirm.*

**Testing in this round (owner, overrides CLAUDE.md's "after every change"):** per task only the
backend test files / `-k` filters that touch the change (new behaviour: the test first), `cli.py
validate` for numerical changes, `npx tsc -b && npm run build` + the touched views' e2e files for
frontend changes (and the views that gain / lose space), mypy on the changed modules; the tests run
are written in each task's notes. At the end, before any version change: everything (all backend,
mypy app svcore signalviewer, validate, tsc + build, the whole e2e suite, tools/benchmark.py with the
new benchmarks, `mkdocs build --strict`, the Releasing checklist).

**Baseline (2026-11-08, at `77aaa4a`):** `python -m pytest backend/tests -q` 981 passed, 14 skipped;
`python cli.py validate` 23 passed, 0 failed. No failure existed before this round.

**Owner's decisions (2026-11-08, after Phase 1):**
1. IDs `26.U1`-`26.U8`, `26.A1`-`26.A5` for this round: approved.
2. C2: derived signals restored from a session saved before 1.23 get `"hold": false` (their old numbers
   kept) - **to do** (C2b below), the same way C3 restores old recipes as `"nan": "legacy"`.
3. Saved conditions with `!=` / `not` over a missing value now give false: accepted (the fix itself).
4. The "skip" choice on screen: answered "yes" to "now in Create signals, or wait for 26.U6?" - read as
   **now, in Create signals** (C3b below); confirm if 26.U6 was meant.
5. The next version is **1.23.0**.

**Stop and ask the owner:** a changed default users rely on (beyond O1), removing / hiding a feature,
a saved-format change that needs migration, a task clearly bigger than described, a finding that
cannot be reproduced.

Progress board:

| # | Task | Phase | Status |
|---|---|---|---|
| C1 | Compare judged at full resolution, both directions | 1 | ☑ done |
| C2 | Zero-order hold for state signals in formulas / conditions | 1 | ☑ done |
| C3 | Explicit missing-data policy (`params.nan`) | 1 | ☑ done |
| C4 | Validation cases V24-V29 | 1 | ☑ done (V24-V28; V29 with P1) |
| C2b | Old sessions: state-source derived signals restored with `"hold": false` (owner, decision 2) | 1 | ☑ done |
| C3b | Create signals: the missing-data choice (propagate / skip) for sum, mean, min, max, norm, integral (decision 4) | 1 | ☑ done |
| O1 | Offline by default + strict offline switch (`SV_OFFLINE=1`) | 2 | ☑ done |
| O2 | Honest damaged-file handling (.bin phantom instances, .ulg recovery) | 2 | ☑ done |
| O3 | `atomic_write()` for sessions, templates, readers, layouts, reports | 2 | ☑ done |
| P1 | Run time offsets without copying the time vector (+ V29 from C4) | 3 | ☑ done |
| P2 | One byte-bounded, locked LRU cache | 3 | ☑ done |
| P3 | Frontend data path: AbortController, binary `/api/data`, `y - y_ref` float32 | 3 | ☑ done |
| P4 | Open several files concurrently within the memory budget | 3 | ☑ done |
| P5 | New benchmarks in tools/benchmark.py | 3 | ☑ done |
| 26.A1 | Remove dead code in svcore/models.py | 4 | ☑ done |
| 26.A2 | User file readers in a worker process | 4 | ☑ done |
| 26.A3 | Consistent sampling (filters over gaps; smooth / rms windows in seconds) | 4 | ☑ done |
| 26.A4 | Transforms and derived recipes in the undoable workspace | 4 | ⏸ assessed - larger than expected, waiting for the owner |
| 26.A5 | Heuristics visible and correctable (angle unit, discrete detection) | 4 | ☑ done |
| 26.U1 | Design tokens audit (index.css) | 5 | ☑ done |
| 26.U2 | Plot styling (grids, axes, palette, hover, legend, band) | 5 | ☑ done |
| 26.U3 | Less clutter (count before / after) | 5 | ☑ done (58 -> 54 / 80 -> 71 controls) |
| 26.U4 | "Judge a run" as the main flow | 5 | ☑ done |
| 26.U5 | Per-signal tolerances in Compare, in `cli compare`'s JSON | 5 | ☑ done (before U4: the judge-a-run flow uses it) |
| 26.U6 | Trust badges + the network indicator | 5 | ☑ done |
| 26.U7 | Per-signal data-quality summary on open | 5 | ☑ done |
| 26.U8 | Event navigation (one list, next / previous keys) | 5 | ☑ done |
| T1 | Frontend unit tests (Vitest) | 6 | ☑ done |
| T2 | De-flake e2e (74 `wait_for_timeout`, test_quick_view) | 6 | ☑ done (78 -> 30, each left has a reason) |
| T3 | CI: larger e2e subset, validation and benchmarks with tolerances | 6 | ☑ done |
| F1-F4 | Test specs, multi-run envelope, measurement export, reports from a spec | 7 | ☐ (ask the owner before starting) |

### C1 · Compare judges at full resolution, in both directions
**Status: done 2026-11-08.**
**Reproduced first** (backend/tests/test_compare_fullres.py, failing on `77aaa4a`): the 10 Hz golden vs
1 kHz run with a spike between two golden samples: PASS, maxAbsDiff 1.4e-15 (exactly as the audit).
The 2M-sample 5 ms excursion: position-dependent - an excursion that covers a multiple of the stride
(10 at 200k points) is seen, others are not; on the UI list's 20k grid (stride 100) it passed. The mean
baseline missed it the same way. The trace's stretch was placed on the strided grid (1234.57 for
1234.567).
**Callers checked:** `app/routes/compare.py` (`/api/compare`, `compare_table` for `/api/compare/all`),
`app/checks.py` `run_compare` (CLI), tests; `metrics()` is also used by svcore/validation.py (V15-V17) and
test_compare_tolerance.py - kept unchanged. `difference_trace` had no other caller; `_band` removed.
**Made:** `svcore/compare.py` - each curve is piecewise linear between its own samples, so the largest
difference is at a sample of one of them: `pass` / `withinPct` / `maxAbsDiff` are computed on the
union of the run's and the baseline's samples in the overlap (`_union`, `_judge_band`, `_judge`; adds
`judgedSamples`). RMS / mean / std / correlation / profile use all the baseline's own samples (no
stride). The time tolerance keeps the SDI rule on the baseline's own samples (min / max within
+-tol_k), its envelope interpolated to the judging times; angles still have no time tolerance. The
mean baseline is accumulated run by run (`_mean_on`, memory O(samples), circular for angles). The
trace is computed on the full judging grid (stretches outside exact) and only the curve is decimated.
`max_points` is accepted and ignored, so the CLI (200k) and the UI (20k-50k) give identical numbers.
**Changed meaning (documented):** for runs at different rates `withinPct` (and the CLI's
`outside_pct` allowance) counts over both runs' samples, not the baseline's.
**Measured:** 2M vs 2M same times 0.28 s, 20M 2.4 s, 2M with offset times (union 4M) 0.46 s.
**Tests run:** test_compare_fullres.py (7, new), test_checks.py (+1 CLI exit-code test, fails on the
old code), test_backend, test_compare_angles / _tolerance / _trace, test_flightlogs_sync,
test_real_logs, test_segments_across, test_sim_vs_flight: 115 passed, 13 skipped; mypy
svcore/compare.py clean. Docs: command-line.md, features.md; CHANGELOG (Unreleased ▸ Fixed).
**Left:** V24 / V25 go into `validate` with C4. The compare list (`/api/compare/all`) now does full
resolution for every signal - fine on the examples; P5's benchmarks should include it.

### C2 · State signals use a zero-order hold in formulas and conditions
**Status: done 2026-11-08.**
**Reproduced first** (examples/copter_flight.bin, MODE.Mode 6 samples at 1.41 / 34.41 / 46.41 / 60.41 /
177.41 / 218.41): `{ATT.Roll [deg]} > -1000 and {MODE.Mode} == 5` gave [40.452, 53.452] (the
nearest sample: halfway between changes); a formula `v1` with MODE.Mode as v1 had 5,418 samples with
values the mode never had. Both exactly as the audit.
**Callers checked:** `analysis.compute` (store `_refresh_derived`, `/api/derived/preview`, validation
V10 / V11 - unary, untouched), `formula.evaluate` (compute, conditions, svcore/transforms.py),
`conditions.evaluate_condition` (investigate.py only), `investigate.Source.discrete` = `Store.is_discrete`.
**Made:** `analysis.hold_to` (the value in force; NaN before the first sample; blank samples hold - the
rule of `state_mask` / `decimate.hold_at`), `align_to(..., "hold")`. `compute(..., states=None)`: a
source that is a state (`Store.is_state`: labels, or `is_discrete`) is held in `expr`, the binary ops
and the several-signal ops; `formula.evaluate(..., holds=None)` (v0 a state: its blanks filled);
`conditions.evaluate_condition(..., is_state=None)`, investigate passes labels / discrete per name.
`states` / `holds` / `is_state` default to None = exactly the old behaviour for other callers.
Opt-out saved per derived signal: optional `params.hold: false` (no UI; documented in features.md).
**Owner to decide:** a derived signal in an OLD session whose source is a state now computes held
values when the session opens (values that never existed were the bug, so no stored flag was added;
`hold: false` exists if the old numbers must be kept).
**Tests run:** test_state_hold.py (6, new; the copter example included), test_backend, test_conditions,
test_investigate, test_derived_rename, test_filters, test_firstchange, test_occurrences, test_overview,
test_push, test_pyops, test_report_sections, test_stale_data, test_time_axis, test_update_rate,
test_vecsmooth, test_bin_text_live: 185 passed; `cli.py validate` 23 / 23; mypy on the 6 changed
modules clean.
**Left:** the overlap of a formula still ends at the state signal's LAST sample (a change-only mode
logged last at 218.41 cuts a formula there, although the mode stays in force to the end of the log) -
a separate decision (extend held sources to v0's end?), not changed here. Transform formulas with
`{Name}` references (svcore/transforms.py) still interpolate their references; the condition's exit
value is still aligned by the nearest sample. V26 / V27 go into `validate` with C4.

### C3 · Explicit missing-data policy
**Status: done 2026-11-08.**
**Reproduced first:** `sum` of 1, missing, 3 gave 4; `norm` / `mean` / `min` / `max` skipped the same way;
`cumulative_trapezoid` turned NaN into 0 (y = [1,1,NaN,1,1] integrated to 1.5 at the gap and went on);
`v0 != 1` was 1 on a missing v0; `1/v0` with v0 = 0 became NaN with nothing said.
**Callers checked:** `compute` (store `_refresh_derived`, `/api/derived/preview`, validation V10 / V11 -
finite data), `cumulative_trapezoid` (analysis integral, formula integ(), ops.on_updates - finite data
only), `formula.evaluate` (compute, conditions, transforms.py). Restore paths in the frontend:
files.ts (sessions / autosave), transforms.ts / derivedOps.ts / clearing.ts (Undo of delete / clear, a
formula edit) - all re-send the params from `/api/runs`, so an explicit `nan` written at creation
survives them.
**Made:** `analysis.NAN_OPS` (sum, mean, min, max, norm, integral, expr) and `NAN_POLICIES`
("propagate" default, "skip", "legacy" = exactly the numbers before 1.23); `nan_policy()` refuses an
unknown value. `compute(..., report=)` fills `nan` / `skipped` / `missing` / `bridged` / `infinite`.
Several-signal ops: propagate = plain numpy; skip = nan-functions (all missing stays missing); legacy =
nan-functions as before (nansum of nothing = 0). `ops.cumulative_trapezoid(t, y, nan, report)`:
propagate = NaN from the first missing sample on (`missing` stretches reported), skip = the gap
bridged linearly (`bridged`), legacy = 0 as before; `ops.missing_stretches`. Formulas: comparisons,
`not`, `where` missing on a missing operand; `and` / `or` three-valued (Kleene); integ() follows the
policy; infinity still becomes NaN (plots / JSON cannot carry it) but is counted in `infinite`.
`Store.add_derived(..., legacy=False)` writes `nan` into every NAN_OPS recipe ("propagate" new,
"legacy" when restored WITHOUT it - `/api/derived/restore` passes legacy=True); `DerivedDef.report`;
the derived listing has `quality` when something was skipped / bridged / lost. Transforms
(transforms.py) evaluate with `spec.get("nan", "legacy")` - saved in sessions without it.
**Saved files:** no format change and no migration step - `params.nan` is a new optional field; a
recipe without it is old by construction. Documented in features.md and the CHANGELOG.
**Owner to decide:** (1) named conditions are re-evaluated from their text, so a saved condition
with `!=` / `not` over a missing value now gives false where it gave true (this is the fix; no flag
added); (2) the GUI has no control yet for "skip" - the backend accepts it; the choice and the mark
belong to 26.U6 (trust badges) - or a small control in Create signals sooner?
**Tests run:** test_missing_policy.py (12, new), the 22 other files touching formulas / conditions /
derived / investigate / integrals / transforms: 259 passed; validate 23 / 23; mypy clean on the 6
changed modules. No frontend change (no build needed).
**Left:** V28 goes into `validate` with C4; filters / smoothing over missing values belong to 26.A3.

### C4 · New validation cases
**Status: done 2026-11-08 for V24-V28; V29 moved to P1.**
**Made:** svcore/validation.py V24 (2M samples, a 5 ms +5 violation, compared on the UI's old 20k grid
size: maxAbsDiff 5 and FAIL), V25 (a 10 Hz golden RAMP - its straight lines are exact, so the
reference is exactly 2 - against a 1 kHz run with +2 between golden samples), V26 (a condition on a
change-only mode starts at 20 s, the change), V27 (10 x mode makes no value outside 10 x the modes),
V28 (sum and norm with one missing input: 0 non-missing results there). Each returns 0 instead of the
difference when the verdict is PASS, so a regression fails the case. docs/validation.md regenerated
(tools/make_validation_doc.py: 28 of 28), docs/index.md says 28 cases.
**Checked against the code before the round** (a worktree at `77aaa4a` with the new validation.py):
V24, V25, V28 FAIL on their numbers (0, 0, 2); V26 / V27 fail there because the functions do not take
`is_state` / `states` yet (their old behaviour is shown by test_state_hold.py).
**Why V29 is not here:** it times a plot request with a run offset against one without (at most about
2x). Today it is about 50x (P1's numbers) - adding it now turns `validate` and the backend suite red
until P1 lands. It is written together with P1 (Phase 3); a timing case also needs a tolerance that
holds on slow CI runners - to be decided then (a ratio, not milliseconds).
**Tests run:** `cli.py validate` 28 / 28; test_validation.py 32 passed.

### C2b · Old sessions keep their numbers (owner's decision 2)
**Status: done 2026-11-08.**
**Reproduced first** (test_state_hold.py::test_old_session_keeps_its_numbers_new_recipes_hold, failing on
`4c3c52f`): a recipe restored without `hold` (`legacy=True`, i.e. `/api/derived/restore`) had no `hold`,
so a state source was held - new numbers for an old session.
**Why a stored `true` too:** the restore path serves sessions / autosave AND Undo / Clear, and cannot
tell a 1.23 session from an old one; C3 solved the same with an explicit `nan` on every new recipe. So
`analysis.HOLD_OPS` (binary, several-signal, formula: the operations that align sources) always store
`hold`: new `true`, restored without it `false` (for every such recipe, not only those whose source is a
state today - 26.A5 will let the user change what is a state, and the old numbers must stay old).
**Callers checked:** `Store.add_derived` (routes/analysis.py create + restore, transforms.ts /
derivedOps.ts / clearing.ts re-send the listed params - `hold` rides along like `nan`), sweeps tests
(unrelated "hold"). No frontend change.
**Tests run:** test_state_hold (7, +1), test_missing_policy, test_backend, test_stale_data, test_time_axis,
test_vecsmooth, test_derived_rename, test_conditions, test_investigate, test_pyops, test_report_sections:
129 passed; validate 28 / 28; mypy app/store.py svcore/analysis.py clean.

### C3b · The missing-data choice in Create signals (owner's decision 4)
**Status: done 2026-11-08.**
**Made:** AnalysisPanel.tsx - *Missing values* (`.nan-field`) under the operation for the several-signal
sum / mean / min / max / norm and for the integral as a NEW signal of every sample (not for an integral
of updates - `on_updates` has its own samples - nor *Change this signal*, a transform). *Keep missing*
(default, sent as `nan: "propagate"`) or *Use the signals that have a value* / for the integral *Bridge
the gap* (`nan: "skip"`); a hint under it says what each does. The mark: `QualityMark` beside a derived
signal whose listing has `quality` (the C3 report) - *skipped missing*, *gaps bridged*, *gap: unknown
after*, *infinite → missing*, the counts and the stretches in its title (`.dsig-quality`, amber tokens).
`SignalInfo.quality` / `DerivedQuality` in api.ts. Strings in i18n/files.ts (en + he). No backend change
(the backend accepted `nan` since C3). Formulas (`expr`, also a NAN_OPS op) keep the default - not in
the owner's list; 26.U6 can add it with the general trust badges.
**Callers checked:** `params` feeds `derivedCall` (create, batch, preview) and `opToStep` (edit in place -
gets no `nan`: `nanOp` is false there); peers.ts `findDerived` compares params (Link operations: a skip
and a propagate recipe are different signals - intended).
**Tests run:** `npx tsc -b && npm run build`; e2e test_missing_choice.py (2, new: the default, skip
saved and marked with its count, the integral's Bridge, no choice for a derivative or in place),
test_update_rate (2), test_features + test_workflows (154 - the Create signals panel gained a row).
Screenshots English light / Hebrew dark: the row and the mark, RTL correct.

### O1 · Offline by default, plus a strict offline switch
**Status: done 2026-11-08.**
**Reproduced first:** `tiles.tile("osm", 3, 4, 2)` downloaded an 11.7 kB tile and wrote it to
`~/.signalviewer/tiles/osm`; GeoChart.tsx and Globe3D.tsx both mapped `geoBase: "auto"` to "osm" (1.22.0).
**Network access in the code:** `app/tiles.py` is the backend's only `urlopen` (grep of app / svcore /
signalviewer); the frontend has no outside URL; Cesium has `Ion.defaultAccessToken = ""`,
`baseLayer: false` and its assets are copied into the build.
**Made:** `frontend/src/mapBase.ts` (GEO_BASES, `isOnlineBase`, `effectiveBase`, `useMapBase`: auto ->
offline; an online layer -> offline when the network is off), used by GeoChart, Globe3D and the layer
menu (PlotView: two option groups, *On this computer* / *Online - downloads map tiles*, the online
ones disabled when off; an amber `.net-badge` "Online map" with a tooltip while online tiles are drawn).
Setting `offlineOnly` (ui slice + settings.ts KEYS -> ui_settings.json), `offlineForced` (UI only, from
`/api/settings`' new `offlineForced`, i.e. SV_OFFLINE=1). Settings dialog row *Never use the network*
(locked On when forced). Backend: `tiles.offline_forced()`, `tiles.network_allowed()` (env, then the
setting; read at most once a second, cleared when `/api/settings` changes it) checked before any
request - cached tiles are still served. `geoBase` saved in sessions is unchanged (an old "auto" now
means the offline map - the intended change; an explicit "osm" stays).
**First tried:** a " · online" suffix on each option: it cut the chosen layer's name in the closed
menu (seen in the screenshot) - replaced by option groups.
**Docs:** README (English + Hebrew), docs/index.md, SECURITY.md, docs/features.md, a new section
docs/maps-and-3d.md#the-network; CHANGELOG (Unreleased ▸ Changed). `mkdocs build --strict` passes.
**Tests run:** backend test_offline_switch.py (4, new), test_basemap, test_app_folder: 18 passed;
`npx tsc -b && npm run build`; e2e test_offline_map.py (5: +2 new - Automatic asks only offline tiles,
no sign; an online layer shows the sign; the switch disables online layers, asks for none, and is
saved), test_settings (1), test_globe3d (10), test_map_objects (4) - all passed. The borders test
that 1.22.0's notes say fails here passed in this sandbox. mypy on tiles.py / routes/system.py: clean.
Screenshots (English light, Hebrew dark): the sign beside the layer, RTL correct; the Settings row.
**Left:** U6 puts the same network state in the general trust indicators.

### O2 · Honest damaged-file handling
**Status: done 2026-11-08.**
**Reproduced first** (backend/tests/test_damaged_files.py, 12 new cases failing on `4b2eaf1`):
`make_test_bin.py --corrupt`: 58 signals instead of 52 (`IMU[149].*`). The ArduPilot example (73 signals,
the audit's count) damaged by the fuzzer's own seeds: 31 phantom signals in 60 seeds (IMU[8], IMU[16],
IMU[190], IMU[247], BARO[87], VIBE[32]). sample.ulg with a flipped bit (seed 16): `ValueError: could not
convert string to float: b'\x00\x00\x00\x00'` from `flightlog.f32` on a parameter - the whole log failed
as "Unexpected error". Two other flips (seeds 1, 26) made 2 / 35 one-sample signals (a topic logged with
only zero time stamps gained one).
**Made:**
- `bin_loader.DataFlash.frame`: the last message before a skipped block (it ends where no message starts)
  is left out - a damaged block often starts with a header of a known type whose "message" fits the chain
  exactly up to there (at most one real message per damaged block goes with it); `droppedMessages`.
- `DataFlash._real_instances` (in `_emit`): an instance with fewer than 4 messages (and under 1/1000 of the
  largest) that is beyond the others + 1 or negative is left out (`phantomInstances`); instances read
  before are kept (`known_instances`: live mode reads small chunks). Covers bit flips in the instance field.
- `ulog_loader`: parameters / logged messages that do not convert are left out and counted
  (`damagedParams`, `damagedTexts`); `_damaged_times`: samples after the log's end (`_time_end`: the last
  time stamp, or the topics' 99.9th percentiles + 1 min when the header's is absurd), a lone sample far out
  of step with both neighbours (> max(1 s, 100 median steps)), and the few non-zero stamps of a topic that
  is otherwise unstamped (`badTimestamps`). No lower bound: PX4 stamps `commander_state` at boot (2 s, the
  log starts at 112 s) and a few messages slightly before logging starts - tried first, it dropped 680
  real samples of the undamaged sample. A damaged definitions block (pyulog cannot start) says so and
  what to do. `damaged: true` beside pyulog's `corruptBytes: 1` (it gives no count) - the note says "the
  file is damaged - what could be read was read", not "1 damaged bytes".
- `common.unexpected_load_error` (files.py, jobs.py): code `unexpected` + the exception, logged with its
  traceback; `err_unexpected` (en / he) says the file may be damaged, try another copy, *Help ▸ Copy error
  details*. files.ts shows the new report fields in the note after opening (i18n/compare.ts, en / he).
**Callers checked:** `frame` (load_bin, append_new_messages - a chunk's end has no gap after it, so live
mode drops nothing), `_emit` (signals, lazy jobs), the index cache (`_index_save` stores the report);
`load_ulog` (store.open_file only). Fuzz after the change: 0 phantom signals in the same 60 .bin seeds and
30 .ulg seeds, the undamaged files unchanged (73 / 249 signals, no new report fields).
**Tests run:** test_damaged_files (all, 217: +20 new), the 29 test files that open .bin / .ulg / use the
open routes: 482 passed, 13 skipped; validate 28 / 28; mypy on the 5 changed modules clean; tsc + build;
e2e test_damaged_note.py (new), test_templates_recent_badfiles, test_file_help_menus, test_error_details.
**Left:** .tlog has its own resync (pymavlink, CRC-checked) - not changed.
**Fix found in 26.A1 (2026-11-09):** a big log's index (`_index_save`, a pickled DataFlash) written before
O2 was still used after it: it keeps the phantom signals, and its DataFlash lacks the O2 fields that live
mode reads (an AttributeError on the first append). INDEX_VERSION 2 -> 3 (old indexes are rebuilt) and
`DataFlash.__setstate__` fills any field an older pickle lacks; test_big_files.py (+1).

### O3 · Atomic writes everywhere
**Status: done 2026-11-08.**
**Reproduced first** (backend/tests/test_atomic_write.py, 3 cases failing on `f6bacb0`): a session save
whose write fails half-way (a full disk) left the cut JSON in place of the saved session; a template
export the same; an HTML report whose building failed (a signal closed meanwhile: 404) left an EMPTY
file - `open(path, "w")` ran before `build_html`.
**Made:** `app/atomic.py` - `atomic_path(path)` (a temporary path in the same folder, with the target's
extension so PDF / Word writers that go by the name still work; fsync, the old file's permissions copied,
a symbolic link keeps pointing at its file, a few retries of the rename on Windows when a reader holds
the file; on any error the temporary file is removed), `atomic_open` (open() for writing on top of it),
`atomic_write` (text or bytes). **Why not in app/common.py itself:** app.prefs and app.userreaders need
it and app.common imports them - so the body is a module without app imports and app.common re-exports
it; the routes import it from app.common, as asked.
Used for: sessions (`session_save`), autosave (`write_autosave`, as before), templates (template export,
`prefs.save_template`, the v1 migration), settings (`prefs._write` - its `.tmp` was one name shared by two
apps saving at once), readers and layouts (the example reader and the example ICD layout, the example
Python operations), reports (`/api/report`, the report job: built into the temporary path, then
replaced), and the other files Recordings saves (CSV export, plot images, `save/text`, `save/image`). In
Sweeps (maintenance mode) only what the task names: the study (`save-text`), its templates, its report.
Not changed: Sweeps' table / row exports (not in the task), tiles / push / the .bin index (already a
temporary file + rename).
**Callers checked:** every `open(..., "w")` / `.save(` under app, svcore, signalviewer (grep); `build_pdf`
/ `build_docx` / `sweep_report.build` take the path given (only the target's extension matters).
**Tests run:** test_atomic_write.py (5, new); the 42 test files that save sessions / templates / settings
/ reports / exports or touch prefs, readers, pyops, jobs, sweeps: 829 passed, 14 skipped; mypy on the 10
changed modules clean; e2e test_workflows, test_findings_report, test_template_tabs (33).

### P1 · Run time offsets without copying
**Status: done 2026-11-08.**
**Measured before** (one signal of 20M samples, median of 7 requests through the API; tracemalloc peak):

| request | no offset | offset, before | offset, after |
|---|---|---|---|
| /api/data zoomed | 3.5 ms, 0.2 MB | 51.2 ms, 160 MB | 3.7 ms, 0.2 MB |
| /api/data whole | 3.2 ms | 48.2 ms, 160 MB | 3.4 ms |
| /api/cursor | 2.5 ms | 49.6 ms, 160 MB | 3.3 ms |
| /api/stats window | 2.6 ms | 458 ms, 570 MB (cache miss) | 2.6 ms |
| /api/neighbor | 3.0 ms | 52.8 ms, 160 MB | 2.4 ms |

**Made:** `Run.signal_parts(name)` -> (stored time, data, offset) (`get_signal_data` built on it, unchanged);
`Store.signal_parts(sig_id)` (a transformed or derived signal: its own time, offset 0 - their results
are cached once per version); `decimate.view_shifted` (window shifted by -offset, display points +offset).
Routes on it: /api/data, /api/cursor, /api/neighbor, /api/stats (window and state mask), /api/limits and
/api/envelope (one copy instead of two - they add the plot's own tOffset anyway), /api/sparks (shape only),
/api/spectrogram (redrawn on every pan). The stats cache (keyed on the time array's identity) hits again.
**Callers of store.signal() reviewed (46):** kept as they are, because they need the whole shifted time
and run once per user action, not per redraw - compare (both runs aligned), analysis.py (FFT, derived
previews, frames, XY / maps, conditions through investigate), export (CSV), report (figures), checks (the
CLI's own store), the segment list / windows / error segments, the store's derived recipes (computed once
per version). Run.get_signal_data's other callers (sync.py, health.py) also once per action.
**V29** (validate): a 5M-sample zoomed request on a run with an offset vs without, median of 9 (in svcore:
Run.signal_parts + view_shifted - what /api/data does). Reports 1 when within 2x, the ratio when not, so
docs/validation.md does not change with the machine. Measured 1.07; with the old copy 20.7 (fails).
**Tests run:** test_offset_nocopy.py (7, new: every changed endpoint gives exactly the answers of a run whose
time already includes the offset - binary-fraction times so both are exact; signal_parts returns the stored
array; the stats cache hits; 2 of them fail on the old code), the 14 files touching the data routes /
decimate / offsets / validation: 190 passed; validate 29 / 29 (docs/validation.md regenerated, index.md 29
cases); mypy on the 5 changed modules clean; e2e test_what_changed, test_aligned_plots, test_features -k
offset / align / sync / cursor / stats (23). No frontend change.

### P2 · One cache policy
**Status: done 2026-11-08.**
**Reproduced first:** the race - 8 threads reading 64 changed signals (sys.setswitchinterval(1e-6)): 33
KeyErrors from `Store._tcache` (`move_to_end` on a key another thread had popped; the routes read a
KeyError as "signal missing") - now test_memcache.py::test_two_requests_at_once_never_see_a_signal_missing,
failing on `89fd784`. The bounds by reading: `_tcache` 32 entries (20M samples: 32 x 160 MB = 5 GB), the
derived results on each DerivedDef with no bound, `_fft_cache` its own 256 MB / 32, decimate's block
summaries 256 entries, the stats cache 256 entries.
**Made:** `svcore/memcache.py` - `ByteLRU` (one RLock; `get` / `put(kind, nbytes, owners)` /
`get_or_compute` / `drop(pred)` / `clear` / `info`), `CACHE` (SV_MEMCACHE_MB, default 1024), `own_bytes`
(a changed signal's time vector that IS the file's, or a derived one's that is its source's, is not
counted). Owners: an entry dies with the arrays it was computed from (weak references) - the summaries
and the stats (their old id-with-weakref schemes folded in); a value bigger than the whole budget is not
kept. Used by: transforms (`Store._transformed`), derived signals (`_refresh_derived`: key name + serial
+ source versions; DerivedDef no longer holds time / data - `invalidate` gives a new serial), FFT
(`fft_for`), block summaries (`decimate._summary`), statistics (`compute_signal_stats`). An older version
of the same signal is dropped when the new one is put (as the FFT cache did).
Settings ▸ Storage: a fourth row *Results kept in memory* - "0 B of 1.00 GB" (each size isolated LTR in
the Hebrew sentence), the kinds with their sizes on hover, Clear (`/api/storage/clear` what "memory").
**Not moved into it:** `_LazyBudget` (models.py: lazily READ values of big logs, re-read from the file
rather than recomputed - a different budget, SV_LAZY_MB), tlog's message dtypes, the template name index
(tiny), the Sweeps tables (maintenance mode).
**Measured** (12 changed signals of 20M samples read once, RSS kept): before 1832 MB (all 12; would reach
32), after 916 MB (under 1 GB). 40 of 5M: 1298 -> 1069 MB. Speed unchanged (1.5 / 1.6 s).
**Tests run:** test_memcache.py (5, new), test_stale_data and test_big_files updated (they read the old
private caches), then the WHOLE backend suite (P2 touches the core): 1049 passed, 14 skipped; validate
29 / 29; mypy on the 7 changed modules clean; tsc + build; e2e test_settings, test_offline_map
(the borders test failed once, then passed twice alone - the flaky one 1.22.0's notes name). Screenshot
English light / Hebrew dark of the Storage rows.

### P3 · Frontend data path
**Status: done 2026-11-08.**
**Reproduced / measured first:** a value 1.7e9 + 3 sin(t) came back from /api/data (float32) with the
wave gone (error 3; steps of 128); a latitude through /api/xy (float32) off by > 0.05 m (up to ~0.2 m);
GeoChart also turned the map objects' float64 latitudes into Float32Array itself. TimeChart's request
per zoom step had no cancellation (a stale answer was dropped only after it arrived). uPlot.join, 30
signals x 6,400 points each on their own x (decimation picks other samples per signal): 162 ms
(node, median of 7) - 192,000 rows.
**Made:**
- **Cancellation:** api.ts `send()` / `call(..., signal)` pass an AbortSignal; an abort is rethrown as
  itself (`isAborted`), not turned into "the server is gone"; TimeChart aborts its request in the
  effect's cleanup (every new range / signal set) and shows no error for it.
- **Binary /api/data:** `format: "bin"` -> `pack_series` (routes/data.py): uint32 header length, JSON
  header (`id, n, total, decimated, yRef, xAt, yAt`), x float64 at multiples of 8 (viewed in place),
  y - yRef float32. `unpackSeries` (api.ts) rebuilds y as Float64Array (`Series.y` is now Float64Array).
  The JSON answer is unchanged (absolute float32) for any other client (tests, tools, scripts).
- **Precision:** `common.y_reference` (the middle of the finite values) for the binary answer and for
  /api/xy when asked `relative: true` (the app asks; `yRef` in the answer). GeoChart keeps object
  latitudes float64.
- **uPlot.join:** `joinTables.ts` - the same result (checked equal on 2 / 10 / 30 signals, nulls kept,
  missing rows undefined) with one sorted Float64Array merge and a linear walk: 2 x 3.2 -> 2.7 ms, 10 x
  28 -> 8.6 ms, 30 x 162 -> 77 ms. What is left is building 31 columns of 192k rows (uPlot's aligned
  table); faceted series (uPlot mode 2) would avoid it but change the cursor / legend logic - not done.
  FFTChart / StepChart keep uPlot.join (a few series).
**Measured** (30 signals of 5M samples, a 600 s window, 3200 points): payload JSON 1872 kB -> binary 1406
kB; server + transfer unchanged (64 / 65 ms); client decode 4.3 -> 1.4 ms (node, the same functions).
**Tests run:** backend test_offset_nocopy.py (+2: the binary answer = the JSON values and exact around
1.7e9; /api/xy relative keeps a latitude to < 1 mm, absolute stays for others), the 123 tests touching
/api/data, /api/xy and common; mypy clean; tsc + build; e2e test_data_path.py (new, 2: a zoom burst
against a slow server aborts the older requests, all binary, no error toast, the last window kept; a
Unix-time value exact through the binary path), test_wheel, test_plot_style, test_aligned_plots,
test_map_objects, test_setpoint_style, test_globe3d, test_workflows. test_offline_map's borders test fails
here - also on `a39b8d5` built alone (checked in a worktree): the satellite base needs the network.

### P4 · Open several files concurrently
**Status: done 2026-11-08.**
**Before** (the open job, files one after the other; this sandbox has 2 cores, SV_CACHE=0): 4 x 55 MB
.bin (make_test_bin.py --seconds 1800) 2.13 s; 4 x 52 MB CSV (1.5M rows) 1.16 s.
**Made:** `app/openmany.py` - `open_many(paths, open_one, cancelled, workers)` (a thread pool, up to
min(files, cores, 4); results in the order asked; an error stays with its file), `_Budget` (a file
starts when the bytes of the files being read leave room for it; a file bigger than the whole budget
is read alone), `budget_bytes()` (SV_OPEN_BUDGET_MB, else half the physical memory - sysconf, or
GlobalMemoryStatusEx on Windows - at most 8 GB, else 2 GB), `need_bytes` (file size x a factor per
format: compressed Parquet 5, ULog / tlog / MCAP 3, .bin 1.5, others 2), `Progress` (the bar = the mean
of each file's own fraction). `common.open_paths` (used by /api/files/open and the open job): per thread
progress context (csv_loader's is thread-local), `store.batch(paths)` (the batch's other files count
for display names - two log.bin from different folders get their folders from the start; one after the
other the first got the bare name), `store.order_as` (listed in the order asked), described in order
(tags A, B, C follow it). A cancellation inside a file is raised again; files not started are skipped.
**Callers checked:** /api/files/open (sync route, tests), the open job (the UI's runJob), open_with_prefs
(unchanged; reload / replace / session restore still open one at a time); thread safety: store.open_file
adds the run under the store's lock, prefs has its own lock, the loaders keep no module state between
files except tlog's dtype cache (filled idempotently).
**After:** 4 x .bin 1.42 s (1.5x), 4 x CSV 0.96 s (1.2x) - two cores here; more with more cores.
**Tests run:** test_open_many.py (5, new: side by side and in order, a file bigger than the budget alone,
cancelled files not started, the route's order / names / a bad file / the list / tags - fails on the
code before - and the job's progress to 1.0), then the whole backend suite: 1056 passed; mypy on the 5
changed modules clean; e2e test_templates_recent_badfiles, test_file_help_menus, test_fresh_user,
test_refresh_feedback, test_damaged_note, test_features -k open / files / mark / progress (33).

### P5 · New benchmarks
**Status: done 2026-11-09.**
**Found first:** `tools/benchmark.py FILE` had been answered 403 since the localhost-only middleware - its
TestClient sends `Host: testserver` (the backend tests set SV_ALLOWED_HOSTS; the tool did not), so every
request it "timed" was refused. Fixed: `base_url="http://127.0.0.1"`; the synthetic run also checks every
status code (a refused request must not be timed as fast).
**Made:** `--synthetic [--samples N] [--json file]` - a fresh process builds its own data and measures:
/api/data (binary, zoomed) with and without a run offset (ratio ≤ 2); 30 signals x N on a zoom step
(< 500 ms, ≤ 2 MB); a pan burst of 10 steps - all waited for vs only the last (what cancelling gives;
< 300 ms); a 52 MB .bin (make_test_bin.py --seconds 1800) with 10 changed IMU signals - RSS and the memory
cache against its budget (≤ 1); a live append of 1,000 rows on a 300-column CSV (< 1 s). `SYNTH_ROWS` holds
the targets (T3 uses them with a tolerance). docs/performance.md has a table of the round, install.md the
command.
**Measured** (5M samples, 2 CPUs): offset 0.97x (3.2 / 3.3 ms), 30-signal zoom 17 ms / 1380 KB, pan last
19 ms (all 10: 186 ms), cache 59 / 1024 MB (log +112 MB open, +202 MB with the changes), live 35 ms. The file
mode on a 46 MB CSV: everything passes except "memory for the data / binary size" 1.46x (target 1.2x;
+170 MB runtime) - not comparable with the 730 MB reference file the target is for; to measure with that
file in the release run (the tool could not measure it at all before).
**Tests run:** both modes run end to end (`--synthetic` at 1M and 5M samples, `run0.csv`).

### 26.A1 · Dead code in svcore/models.py
**Status: done 2026-11-09.**
**Checked first:** no reference outside models.py (grep -w over backend, tools, cli.py, tests) to
DerivedSignal, SubplotConfig, subplot_from_dict, Tab, ViewState, make_signal_key, parse_signal_key,
DERIVED_RUN_IDX ("Tab" appears only as a word in other files). SignalType: used only by Signal's own
`signal_type` field, which nothing reads or sets - both removed. Nothing removed is pickled (the log
index pickles a DataFlash, not Signals). The index-based keys ("run_idx:name") went with them.
**Tests run:** the whole backend suite (1056 passed); mypy svcore/models.py clean.

### 26.A2 · User file readers in a worker process
**Status: done 2026-11-09.**
**Reproduced first** (a script opening files through the Store with a readers folder): a reader calling
`os._exit(3)` ended the whole process (exit code 3); a reader with `while True: pass` still hung after 10 s.
**Made:** `app/subproc.py` - `Worker` (one spawn process, started on first use, one call at a time, killed
on a timeout, `WorkerGone(timed_out, exitcode)`): the mechanism app/pyops.py had, now shared - pyops.py
uses it (same messages, test_pyops unchanged). `svcore/readerworker.py` - the worker's loop: loads the
readers folder (readers.load_folder), answers "list" (each reader without its function) and "read" (the
reader's raw result through the pipe; `to_run` stays in the server, so the Run is built exactly as
before). `app/userreaders.py`: in isolated mode the Python readers come from the worker and each reader's
`fn` calls it (`_remote`): a timeout (SV_READER_TIMEOUT, default 600 s) or a crash becomes a ReaderError
naming the reader and its file; the worker is restarted whenever the folder changes (as the in-process
cache was re-read). The ICD layouts are data, decoded in the server as before. `readers.read` passes a
ReaderError through unchanged (no double prefix).
**Where it is on:** `app/main.py` calls `userreaders.isolate()` - the app. The Python API and the command
line run readers in the user's own script as before: a spawn worker re-imports the calling script, which
fails in a script without `if __name__ == "__main__":` (seen while reproducing). run.py already calls
`multiprocessing.freeze_support()` (the frozen build).
**Tests run:** test_readers.py (+2: a reader runs in another process and gives the same Run; a crashing
and a hanging reader give clear errors and the next file opens), test_pyops (10), then the whole backend
suite: 1059 passed; mypy on the 6 changed modules clean; e2e test_user_reader.py (new: in the running app
a crashing reader leaves it working, the next file opens).

### 26.A3 · Consistent sampling
**Status: done 2026-11-09.**
**Reproduced first** (backend/tests/test_sampling.py, 6 cases failing on `a5b8b90`): a step inside a 2 s
logger pause through a 1 Hz low-pass: the 0 before the pause pulled above 1 (filtered across it); a 2 Hz
tone, 100 Hz then 10 Hz logging, through a 5 Hz low-pass: below 0.3 in the 10 Hz half (the median rate
made it look like 20 Hz); smooth / rms windows in samples.
**Made:** `ops.apply_filter(..., sampling="time" | "samples", info)` - "time" (`_filter_in_time`): cut at
`isolated_gaps` (the spectra's / statistics' rule: an isolated long step, not sparse sampling), each
stretch on its own (fewer than 3 samples: missing), an even stretch (steps within +-50 % of its median)
filtered as it is at its mean rate, an uneven one interpolated onto an even grid of its median step,
filtered and read back at its own times (NaN kept); an absurd grid falls back to the samples; info
{gaps, resampled} -> the derived signal's report (`filter`, for 26.U6). "samples" = the code before
(`_filter_samples`). Even data gives the same numbers (checked to 1e-9). `compute`: smooth / rms with
`params.seconds` use `time_moving_average` (rms = sqrt of the time average of y^2); `window` (samples)
only without `seconds` or with `sampling: "samples"`; the formula label says "0.5 s".
`analysis.SAMPLING_OPS` (lowpass, highpass, smooth, rms): `Store.add_derived` writes `sampling` - new
"time", restored without it "samples" (as `nan` / `hold`). Formulas: lowpass / highpass in time except
with `nan: "legacy"` (a formula or a change saved before 1.23), new `smooth_s(x, seconds)`
(formulaHelp.ts lists it - test_ui_function_list_matches_server).
UI: Create signals' smooth / RMS field is *Window (s)* (default: 10 samples of the chosen signal, from
its rate; `seconds` in the recipe), *Change this signal* smooth / rms -> `smooth_s(x, s)`; the transform
dialog's Smooth too (an old `smooth(x, n)` change shows as its formula, unchanged). `windowSamples`
removed from i18n (unused).
**Not changed (to decide with 26.A4):** a change on a signal (a transform) has no saved marker of when it
was made - since C3 every transform is evaluated as "legacy", so `lowpass()` inside a transform keeps the
sample-based filter (smooth_s is new, so it is in time). When transforms become recipes (26.A4) they get
`nan` / `sampling` like derived signals.
**Tests run:** test_sampling.py (6, new), test_filters, test_backend, test_bin_text_live, then the whole
backend suite (1064 passed; one run had an extra failure that did not repeat); validate 29 / 29; tsc +
build; e2e test_features (126, one expectation updated: `smooth_s(abs(x), 0.1)`), test_missing_choice,
test_update_rate.

### 26.A4 · Transforms and derived recipes in the undoable workspace
**Status: assessed 2026-11-09 - larger than the task; not started (the task's own rule: ask first).**
**Where things are today:** derived recipes (`Store.derived`) and changes on signals (`Store.transforms`)
live in the backend; the frontend reads them from `/api/runs` and changes them through 5 api calls used in
39 places in 11 files (AnalysisPanel, ComparePanel, clearing.ts, derivedOps.ts, transforms.ts, frames.ts,
peers.ts - Link operations -, sameWork.ts, files.ts - sessions / autosave -, createSignalMenu.ts,
errors.ts). Undo for them is a toast action that re-sends the previous recipes / specs (clearing.ts,
derivedOps.ts, transforms.ts), beside the workspace's Ctrl+Z (clearing.ts already joins both for "Clear").
Sessions save them as top-level `derived` / `transforms`, restored after the files.
**What the task needs:** (1) `ws.derived` / `ws.transforms` in the workspace model (every change through
`commit`, so Ctrl+Z / Ctrl+Y cover them); (2) one sync layer: after every commit / undo / redo, the
difference between the workspace and what the backend holds is sent (restore / delete / set specs) -
including recipes that fail to compute and Link operations' copies; (3) all 39 call sites rewritten to
change the workspace instead of the backend; the toasts' Undo replaced by Ctrl+Z; (4) session / template /
autosave migration (top-level `derived` / `transforms` -> `ws`, both read; never renamed), with C3 / C2b /
26.A3's `nan` / `hold` / `sampling` markers; (5) e2e: every flow that deletes / renames / edits a made
signal or a change and undoes it (test_features alone has ~15). Estimated: several days, one entity at a
time (transforms first - fewer callers - then derived).
**Owner to decide:** start it (one entity at a time, each its own commit and migration), or leave it for a
later round. Until then: transforms keep "legacy" missing-data / filter rules (C3, 26.A3).

### 26.A5 · Heuristics visible and correctable
**Status: done 2026-11-09.**
**Found first:** the angle unit was already correctable (object dialog: automatic / degrees / radians) but
"automatic" did not say what it chose or why; discrete detection (`analysis.is_discrete`: a few whole-number
levels) had no correction at all - a counter of whole numbers was held, a mode logged as floats was
interpolated - and it drives cursor values, C2's hold in formulas / operations and conditions.
`ws.stateNames` ("Always as a state") is about LANES (drawing), not about reading between samples - kept
separate on purpose (a mode can be held and still drawn as a line).
**Made:** backend - `Store.read_as` {signal name: "state" | "value"} (by name: every file, as stateNames),
`set_read_as` (the whole map), `is_discrete` = the correction else `detected_discrete` (the old cached
detection), texts always states; `version()` carries the correction, so derived signals made from such a
signal are computed again; `/api/read_as` (replace the map, return the runs), `/api/discrete` adds
`detected`, `levels`, `readAs`. `angle_units(raw)` -> {role: (unit, why)} with why "name" / "beyond" /
"within" (the object track's old inline rule, now shared), `/api/angle_units`, `object_track` adds
`unitWhy`. Frontend - `ws.readAs` (optional; sessions without it read as detected), `readAs.ts`:
`watchReadAs()` (main.tsx) sends the workspace's map whenever it changes - commit, Undo, a session opened -
and refreshes the runs; `readAsItem` - one "Read between samples as ▸" submenu in the signal list's menu
(numeric file signals only): *Automatic - a state / a value* (what was detected; plain "Automatic" while a
wide file's detection has not run), *A state - held*, *A value - interpolated*, checked. ObjectDialog: the
Automatic option reads "automatic - degrees (one of the angles goes beyond 2π)" from `/api/angle_units`.
Strings en / he.
**Tests run:** test_heuristics.py (3, new: why a signal is a state and the correction - cursor value
interpolated after it -; a derived signal recomputed; angle units with why, also in object_track - all fail
on the code before), then the whole backend suite: 1068 passed; mypy clean; tsc + build; e2e
test_heuristics.py (new, 2: the submenu, the backend following, Ctrl+Z; the dialog's automatic unit),
test_map_objects, test_globe3d, test_state_lanes, test_file_help_menus, test_plot_menus (20).

### 26.U1 · Design tokens
**Status: done 2026-11-09.**
**Audit (index.css, after the theme blocks):** 45 distinct font-size literals (0.75 ... 1.692rem and px
sizes that ignored Settings ▸ Text size), 11 radius literals (2 ... 14px), 12 gap literals, 69 hex colours
outside the tokens - among them #e5534b / #3fb950 (14 + 12 uses: errors, pass / fail, live dots), fixed in
both themes (#3fb950 text on white is 2.6:1, below WCAG AA), a `var(--accent, #3D8BFD)` whose token never
existed, `var(--mono, ...)` the same; 11 inline `fontSize` literals in components.
**Made:** tokens in index.css - the type scale `--fs-3xs ... --fs-4xl` (rem: 9, 10, 10.5, 11, 11.5, 12,
12.5, 13, 14, 15 ... px at the default root, following Text size), radii `--r-xs/s/m/l/xl/round`, spacing
`--sp-0_5 ... --sp-6`, and colours by role: `--info` (per theme), `--overlay-*` (over imagery: the 3D
globe, satellite map - the same in both themes), `--own-time*`, `--paper`, `--letterbox`, `--kind-mode /
--kind-event`, `--on-color`, `--mono`. Every font-size / radius / gap literal mapped to the nearest step
(a size moves by at most ~0.4 px; radii 3 / 5 -> 4, 9 / 10 -> 8, 11 / 14 -> 12; gaps 3 -> 4, 5 -> 6);
#e5534b-family -> `--danger`, #3fb950 -> `--ok` (theme-aware), #1b1305 -> `--amber-ink`. What is left are relative `em`
sizes (by design) and the token definitions themselves. Inline styles: `var(--fs-*)`.
**Counts:** font-size literals 45 -> 0 (7 relative em sizes remain), radius literals 11 -> 0, gap literals
12 -> 8 (0, 1px and two-value gaps), hex colours outside tokens 69 -> 0. `test_design_tokens.py` keeps it so
(a new literal size / radius / colour fails the backend suite).
**Screenshots** (ArduPilot example, English light; Compare, Hebrew dark; before / after): the same picture -
U1 unifies, the visible changes come with U2 - except the pass / fail colours in the light theme.
**Tests run:** test_design_tokens.py (3, new - fail on the CSS before); tsc + build; e2e test_less_clutter,
test_tab_band, test_navigation, test_overview_strip, test_plot_menus, test_fresh_user, test_compare_diff,
test_timeline (19). **Left:** the data palettes in TS (OverviewStrip's state colours, Globe3DFallback) belong
to U2 (the trace palette).

### 26.U2 · Plot styling
**Status: done 2026-11-09.**
**Found:** the trace palette (20 colours) was not chosen for colour vision deficiencies and was one list
for both themes (no check against the plot background); What changed, conditions' file plots and four
fallbacks (`#3D8BFD`) had palettes of their own; uPlot's crosshair a fixed grey; the hover points solid
dots over the line's value; the Compare difference chart an SVG with `preserveAspectRatio="none"` - its
axis numbers were stretched with the panel's width - and outside stretches full-height red at 22 %,
which hid the lines when many (54 in the car example).
**Made:** `chartUtil.ink(color, theme)` - a hex colour with less than 3:1 against the plot's background
(PLOT_THEME bg) is mixed toward white (dark) / black (light) in 8 % steps until it reaches it, cached;
anything already readable, and non-hex colours, unchanged (the user's own colours too). Used where lines
are drawn: TimeChart (the aligned sigs - so lanes, cursor flags, limits follow), FFTChart, XYChart,
StepChart, GeoChart tracks, DiffChart, the legend swatches (PlotView). `TRACE_COLORS`: Okabe & Ito's eight
first, twelve companions; WhatChanged / conditions / OccChart / EnvelopeChart / StepChart / Globe3DFallback
use it. TimeChart's cursor points: rings (size 8, width 2, filled with the plot bg); `.u-cursor-x` dashed in
`--axis`. DiffChart: always-mounted wrapper measured with useSize -> real-width SVG (no stretch), plot bg +
border, band edges (`.diff-band-edge`), outside stretches 10 % + a 4 px solid mark along the bottom
(`.diff-out-mark`), hover points and a readout (t and each run's difference, LTR-isolated).
**Not changed (looked at):** grid colours (already one step above the background in both themes), the
legend (chips with file tags; 26.U3 may thin it), SpecChart's colour map, the map's track halo.
**Screenshots** (scratch, English light / Hebrew dark; car example Compare, ArduPilot example): the same
layout; the difference chart readable with 54 stretches outside; hover rings in both themes.
**Tests run:** tsc + build; e2e test_plot_style, test_setpoint_style, test_compare_diff, test_aligned_plots,
test_hover_ghost, test_owner_notes_1_20, test_release_1_21, test_features -k colour / legend / conditions
(22). `ink()`'s contrast is unit-tested with Vitest in T1.

### 26.U3 · Less clutter
**Status: done 2026-11-09.**
**Counted** (tests/e2e/test_less_clutter.py's COUNT - visible `<button>` / `<select>`; "controls" without
data items: signal rows, state stretches, flags, event marks), ArduPilot example, 1440x900:
| View | before (total / controls) | after |
|---|---|---|
| Attitude tab (default) | 78 / 58 | 74 / 54 |
| Flight tab (map + 3D) | 93 / 80 | 84 / 71 |
**Made (nothing removed - every function is still one click away):** TemplateStrip - when something is
plotted (the strip is folded) *All templates…* and *Save as template…* show only unfolded (both are in
Templates ▾ and the command palette). Overview strip: *+* (add a row) and *hide* at opacity 0 until the
strip is hovered or focused (keyboard still reaches them). PlotView (map): a plot with objects and no
x / y signal hides the Lon / Lat pickers and the alignment select; *⋯ ▸ Lat / lon track (beside the
objects)…* shows them (UI state, `geoPicks`). Globe3D: *Image ▾* and *✕ Remove* moved to the plot's ⋯
(`globeBridge.ts` - the globe registers its saveImage; the generic server-image items are replaced for 3D).
**Not changed (looked at):** the 3D view's toggles (data / events / measure - each used while looking);
the object chips (one per object, each with its follow / remove); the legend chips (they are the signals).
**Tests:** test_less_clutter (controls <= 54 + the Flight tab's hidden pickers / 3D menu), helper
`template_strip()` for tests that use the strip with plots (test_template_tabs, test_object_templates,
test_one_per_plot, test_templates_recent_badfiles); test_features S04 now expects the U2 palette's 4th
colour. e2e: test_globe3d, test_template_tabs, test_object_templates, test_one_per_plot,
test_templates_recent_badfiles, test_map_objects, test_features, test_overview_strip, test_tab_band,
test_workflows, test_less_clutter. Screenshots (scratch): EN light / HE dark, both tabs.

### T3 · CI: a larger e2e subset, validation and benchmarks with tolerances
**Status: done 2026-11-09.**
**Made:** `.github/workflows/ci.yml` - frontend: `npm test` after the build; backend (3.12): `cli.py
validate` (already there; its 29 cases include V24-V29 of this round) and `tools/benchmark.py --synthetic
--samples 2000000 --check 3` (new `--check SLACK`: exit 1 when a target is missed - times may be SLACK x
the target on a shared runner, a ratio of two times SLACK/2, sizes exactly; `misses()` unit-tested in
backend/tests/test_benchmark_check.py; ~7 s here); e2e: 3 -> 18 files (~2.5 min here: the flows this round
changed - judge a run, tolerances, the difference chart, trust badges, data quality, events, clutter,
missing values, heuristics, templates, plot style, aligned plots, the tab band, settings). The whole
suite stays a release step (build.yml / the owner's PC), as before. Not run here (no GitHub runner) -
the YAML parses; the commands are the ones run locally.

### T2 · De-flake e2e
**Status: done 2026-11-09.**
**Made:** 78 `wait_for_timeout` -> 30. Helpers in test_features.py: `settled` (busy 0, no job),
`autosaved` (the server's autosave equals the workspace - polled with `until`, because
`wait_for_function` does **not** await a promise: an async predicate returned at once, found while
doing this), `until` (poll an async page check), `range_changed`, `frames` (n animation frames, via
evaluate); test_offline_map `_wait_pixels` / `_wait_redrawn`; test_globe3d `at_lat` and waits on the
camera's own measure (centred, closer). test_quick_view waits for a number in `.val` (it read the "—"
kept for the value). test_plot_menus judges the menu where it ends up (it is placed after being
measured - failed 1 in 3 here). test_timeline waits for the autosave that holds the settings, then
for them to be put back. Side effect: test_offline_map's borders test - "fails also on origin/main
here" since 1.22 - passes: it was a fixed 800 ms, not the network.
**Left (30), each with a reason:** polls that use a short wait as their interval (offline tiles,
settings saved, Sweeps steps, the 3D image file, stat_max); gesture timing the test is about (the
wheel's trackpad grouping, the data path's burst under a slow route - the route holds the test's
thread); playback for a time (timeline, globe's own time); negatives over time (no request leaves the
PC in 1.5 s; the video not dragged); Sweeps' autosave (its state is not one comparable object).
**Tests:** the 14 changed files, each in its own process: all green (test_features 126, test_globe3d 10,
test_workflows 28, ...); test_plot_menus 4/4 after the change.

### T1 · Frontend unit tests (Vitest)
**Status: done 2026-11-09.**
**Why a new dev dependency:** the frontend's logic (undo, session migration, pairing, colours, the
verdict) was tested only through the browser (e2e: minutes, and a failure says little about where);
Vitest runs on Vite's own transform (no second build setup), with the project's tsconfig, in ~3 s.
`vitest@5.0.5` (devDependency; `npm i` needed `--legacy-peer-deps` here because of an npm 10 arborist
crash on peer sets - the lock file installs with a plain `npm ci`, checked). No DOM library: the tests
are of logic; `src/test/setup.ts` stubs window / localStorage / matchMedia / document for the store.
**Made:** `vitest.config.ts` (node, `src/**/*.test.ts`), `npm test`; tests: `store/undo.test.ts` (commit =
one step, undo / redo, a no-op commit records nothing, a new change drops redo, the function gets a copy,
UI state is not a step, 100 steps kept, undo drops the "undo" toasts), `files.test.ts`
(`legacyUnitNames` both ways; `applyState` with a mocked api: names mapped, a missing file's signals and
X axis dropped, not an undo step, a "missing" error, no 26.U4 field needed; `currentState`'s keys),
`sameWork.test.ts` (usedNames: plots, derived sources, map objects, this file only), `pairing.test.ts`,
`components/chartUtil.test.ts` (ink >= 3:1 for every trace colour in both themes, unchanged when
readable / not hex), `judge.test.ts`, `components/TrustBadge.test.ts`, `quality.test.ts` - 24 tests.
CLAUDE.md / CONTRIBUTING / docs/development.md say to run it. (CI: T3.)

### 26.U8 · Event navigation (one list, next / previous keys)
**Status: done 2026-11-09.**
**Found:** the Log panel's Events tab listed the log's msg / mode / event / error (flight logs); findings
were in its Health tab and on the timeline; conditions had ] / [ for the focused one only; limit
violations were in the Inspector of the selected signal.
**Made:** `events.ts` - `collectEvents(run?)`: the log's events (ensureLogs, + the file's offset), the
health findings (api.runHealth, kept per file version), the conditions' intervals (condResults), the
limits of the active tab's plotted signals (api.limits spans); `stepEvent(dir)` - ] / [ from the cursor
(else from the view's edge) over every kind but plain messages; `ui.eventAt` shown in the status bar
while the cursor is on it. shortcuts.ts: ] / [ = the focused condition as before, else events. Command
palette: Next / Previous event. LogPanel Events: kinds finding / condition / limit merged in time order
(times now as on the plots), a stretch is shown whole on click. Help: the key.
**Kept as is:** the list stays in the Log panel (flight logs) - no new control on screen (U3's counts);
for other files the keys and the palette work (conditions, limits). Ties (a limit starting at a mode
change) step in the order mode, event, …
**Tests:** e2e test_event_navigation (new: ] / [ / status, the list's kinds and order, a limit's
violations in the list and stepped), test_release_1_21, test_conditions, test_features -k
log/cond/palette/help/key/event (20).

### 26.U7 · Per-signal data-quality summary on open
**Status: done 2026-11-09.**
**Found:** the load report said what the reader skipped or sorted (columns, damaged bytes, rows put in
order), the overview strip flags a few gaps / stuck / spikes per run (places worth a look, capped at 30);
nothing per signal on missing values, repeated or backwards stamps or rate changes.
**Made:** `svcore/quality.py` (new - kept apart from overview.py, whose flags are moments; this is a
summary per signal): `time_quality` (rate, gaps by `ops.isolated_gaps` - the one gap rule -, duplicates,
backwards, rate changes: block medians of the step, a change must hold two blocks, at most 5),
`signal_quality` (missing, all missing), `run_quality` (a shared time vector checked once; a state /
event signal (Store.is_state) only for missing values - logged on change, its pauses are not gaps).
`GET /api/runs/{id}/quality` (in a thread; kept on the LoadedRun until the file is read again).
Frontend `quality.ts` (`checkQuality` after `openPaths` and after a re-read; one note per file with
issues, up to 3, *Show*), ui `quality` / `qualityFor`, DataPanel: **!** badge (a button) on the file head,
a mark on signals with issues, *Data quality…* in the file menu; `QualityDialog.tsx` (lazy; only
signals with issues / every signal; a click plots the signal). Speed: 20 signals x 1M samples 0.17 s;
the examples: 0.01 s, nothing to say (no clutter added there).
**Not done:** live mode does not re-check as a file grows (the summary is of the file as opened).
**Tests:** backend test_quality.py (time checks incl. jitter not a change, duplicates / backwards, the
shared time, an event signal, the route + its cache); e2e test_data_quality (new), test_less_clutter,
test_fresh_user, test_file_help_menus, test_templates_recent_badfiles, test_features -k D0/file/menu (47).
Screenshots EN light / HE dark (scratch).

### 26.U6 · Trust badges + the network indicator
**Status: done 2026-11-09.**
**Found:** the assumptions were reported in some places only - C3's mark in *Create signals*' list
(missing values), A1's line under a spectrum (gaps bridged), the Inspector's ⏱ (time-weighted
statistics), O1's *Online map* beside a map's layer menu; 26.A3's filter report (`quality.filter`) was
sent but shown nowhere; interpolation between samples (a sum of signals at other rates) was not reported
at all; the angle guess (26.A5) only in the object dialog.
**Made:** backend `svcore/analysis.py` `_note_interpolated` - `quality.interpolated = {method, sources}`
when a source is read at other sample times (linear / nearest; a held state (C2) is not counted; the same
samples are not). Frontend `TrustBadge.tsx`: `trustNotes(quality)` (short word, tooltip lines, level warn
for missing data / info for how values were read) and the badge - in *Create signals*' list (replaces
QualityMark, keeps `.dsig-quality`) and compact "≈" on legend chips of derived signals; `AngleGuessBadge`
on map / 3D object chips with *Automatic* angles (the A5 guess + why). Status bar: *● Online map* (an online
layer and a map / 3D plot in the active tab), *Network off* (the setting / SV_OFFLINE). Left as they were
(already badges): the spectrum's gap line, the Inspector's ⏱.
**Not done (to decide):** Compare's own interpolation (it judges every sample of both runs, C1 - said in
the docs, no badge); the formula editor's missing-data choice (formulas propagate, C3 - a *skip* choice
there is the owner's call); a badge on cursor values (would be on every value).
**Tests:** backend test_trust_notes.py (interpolated only with other sample times, nearest, several,
formula, a state held; a filter across a gap noted); e2e test_trust_badges (new), test_missing_choice,
test_less_clutter, test_map_objects, test_globe3d, test_heuristics, test_offline_map (borders: the known
failure), test_features -k derived/formula (3).

### 26.U4 · "Judge a run" as the main flow
**Status: done 2026-11-09** (after 26.U5).
**Found:** Compare's baseline was the first file; nothing said a run passes or fails as a whole (✓ / ✗
per signal only); a report had no comparison in it; opening a recording never proposed what to compare
it with.
**Made:** `judge.ts` - golden runs in the app's settings (`sv.goldenRuns`: path, name, the tolerances
last used; up to 20; **settings, not the session** - they belong to the test); `proposeBaseline` (an open
golden run, else a name like golden / ref / reference / baseline / nominal / expected, else the first -
as before); `goldenFor(run)` (a golden run with >= half of the file's signals, by `api.fileSignals`
without opening it); `judgeAgainst` (opens it with `openPaths(..., {noStart})`, sets its tolerances,
`compareJudge` -> the panel takes these files and baseline); `verdicts` / `reportVerdict`. StartCard:
*Judge it against …* (primary; the template's Open becomes outline beside it). ComparePanel: ★ Golden
run (checkbox under *Compare against*, ★ in the select), the verdict box (per file ✓ / ✗ k of N; only on
a list computed for the current choice - `simKey`), *Show the worst failure* (largest share outside;
scrolls to its comparison), *Report…* (a tab "Verdict · …" with up to 6 failing signals - or the most
different - and `ws.report.verdict` + `includeVerdict`, optional fields: old sessions open). ReportPanel:
*Include the verdict*; it is the report's first section (HTML / PDF / Word already draw sections). The
list's flip-through-one-plot now also renames that plot (its title stayed the first signal's).
**Tests:** e2e test_judge_a_run (new: mark golden with a tolerance, verdict, worst failure, report tab +
preview, clear, open run_014 alone -> card -> verdict with the remembered tolerance); test_compare_diff,
test_compare_tolerances, test_findings_report, test_release_1_21, test_workflows, test_fresh_user,
test_range_notes, test_features -k compare/start/report (50). Screenshots EN light / HE dark (scratch).

### 26.U5 · Per-signal tolerances in Compare, in `cli compare`'s JSON
**Status: done 2026-11-09** (done before 26.U4: "judge a run" uses the tolerances).
**Found:** the panel had one tolerance for every signal (three text fields, component state - lost when
the panel closed); `cli compare --tolerances` read `{"default", "signals": {name: {abs, pct, time,
outside_pct, skip, as}}}`; the panel ignored `outside_pct` (so a run the CLI passed could fail in the app).
**Made:** `svcore/tolerances.py` - the one rule: `parse` (checks numbers, keeps `as` and unknown keys so a
file round-trips), `entry_key` / `for_signal` (a key matches with or without its unit, any case when one
match), `judge(row, tol)` (pass when within, or outside share <= outside_pct; None with no limit or skip).
`run_compare` (CLI) and `/api/compare/all`, `/api/compare` use it; the two routes take `tolerances` (the
file's format; the old tolAbs / tolPct / tolTime still work - one tolerance for every signal), return per
row `tol`, `tolKey`, `skipped`, `outsidePct`; a wrong tolerance is a 400 before the job starts.
`/api/compare/tolerances/load|save` (atomic, `.json`). Frontend: `compareTol` in the ui slice (UI state -
**not in the session**; the file is where tolerances live, as for the CLI: decision to confirm with the
owner), `TolFields.tsx` (abs / % / time / allowed outside; placeholders show every signal's), the
selected signal's *This signal's tolerance* + *Leave out*, ± and *left out* marks in the list, Save /
Open / Clear in the settings; the detail is judged again 350 ms after a change.
**Not in the panel:** `as` (the panel pairs by name, C13) - kept in the file.
**Tests:** backend test_tolerances.py (parse / names / judge; the GUI's and the CLI's verdicts equal per
signal on run_012 vs run_014 with a per-signal tolerance, outside_pct and skip; the panel's file run by
`cli compare`); test_checks unchanged and green. e2e test_compare_tolerances (new), test_compare_diff.
Screenshots EN light / HE dark (scratch).

## Owner's plan (2026-11-07): U1–U8, M1, A1–A3 - opening a file, marketing, architecture, UX

**Owner:** the next round after 1.21.0. Patches as before (one `git format-patch` file per unit of
work, built on the latest `origin/main`, never depending on an earlier patch). Testing rule changed in
`/CLAUDE.md`: relevant e2e per task, the **whole** e2e suite at the end of each group below and at the
end. Before coding a task: check in the code what already exists for it and tell the owner if the
definition is wrong or partly done.

**Already verified (do not redo):** drag & drop of signals onto plots (`PlotView.tsx` onDrop: y / x /
right / bottom, chips between plots); filters are SOS (`ops.apply_filter`: butter(output="sos") +
sosfiltfilt); `frontend/dist` need not be committed by contributors (build.yml builds it); Compare has
tolerance abs / pct + time tolerance (1.21.0) - only its display is missing (U5); hover on a time plot is
`s.hover {plotId, t, vals}` (TimeChart.tsx ~674), read only by PlotView's legend - GeoChart / Globe3D
follow `cursor.t1` only.

**Not decided - do not build unless the owner approves:** M2 a flight summary card on open (duration,
distance, max altitude, modes, health green / yellow / red); M3 "Ask for help on the forum" export (image
+ text summary for discuss.ardupilot.org); auto-detecting Mission Planner / QGC log folders on first
start; an opt-in update check; renaming the product (postponed).

**Order:** U1, U3, U2 (group 1) · M1 (group 2) · A1 (group 3) · U6, U4, U5, U7 (group 4) · A2, A3, U8
(group 5). Whole e2e suite after groups 1 and 4 and at the very end.

Progress board (tick here AND in ROADMAP):

| # | Task | Group | Size | Status |
|---|---|---|---|---|
| U1 | Choose which tabs a template opens (`defaultTabs`, "+N more") | 1 | M | ☑ done |
| U3 | One flight-mode band per tab | 1 | M | ☑ done |
| U2 | Health findings must not cover data | 1 | S/M | ☑ done |
| M1 | Hero image, social preview, tagline | 2 | S | ☑ done |
| A1 | Split `backend/app/store.py` (investigate, live watcher) | 3 | M | ☑ done |
| U6 | Hover moves a ghost point on the map / 3D | 4 | S | ☑ done |
| U4 | Desired vs actual styled automatically | 4 | S | ☑ done |
| U5 | SDI-style difference view in Compare | 4 | M | ☑ done |
| U7 | Less clutter (< 70 visible buttons in the ArduPilot example) | 4 | M | ☑ done (owner: controls < 70; the strip's rows stay) |
| A2 | Split `frontend/src/i18n.ts` by area | 5 | M | ☑ done |
| A3 | App.tsx cleanup (< 450 lines) | 5 | S | ☑ done |
| U8 | Navigation design only (no code) | 5 | S | ☑ done (owner: option A) |
| U9 | Navigation option A: areas as a switch, Fleet an area, one views menu, a fixed rail | 5 | M | ☑ done |

**Checked in the code (2026-11-07, at `5b0ed7a`):** `store.py` 1,495 lines; `i18n.ts` 3,528; `App.tsx`
628. The built-in ArduPilot set is *ArduPilot · Full review* (`bi-ap-review`, no tabs of its own,
`includes` nine one-tab templates: Attitude, Rates (+ Step response), Vibration, Battery, GPS, Motors,
Altitude, EKF, Flight) - so U1's tab list for it is the included templates' tabs, and its `defaultTabs`
names those. State lanes exist: `Tab.sharedStates` (a lane at the bottom of every time plot of the tab)
and `ws.globalStates` (every tab), drawn per plot in TimeChart.tsx ~94 - U3 builds on them.

### Group 1 - opening a file (whole e2e suite at the end of the group)

### U1 · Choose which tabs a template opens — M
**Do:**
- A template opened by hand (Templates menu / library) with more than one tab: a dialog listing the tabs
  with checkboxes, *All* / *None*; by default all are checked (today's behaviour).
- A new OPTIONAL template field `defaultTabs` (tab names). When present only those are pre-checked.
  Old templates and sessions without it behave exactly as today. Saving a template lets the user mark
  which tabs are default.
- Opened automatically right after a file loads (smartStart): no dialog - open `defaultTabs` (all when
  absent).
- Tabs not opened stay available: "+N more from <template> ▾" next to the tab bar's "+" button; opens
  one or all.
- Settings: "Skip the tab choice and open the template's default tabs".
- Built-in ArduPilot template: a sensible `defaultTabs` - **propose it to the owner** (e.g. Attitude +
  Flight).

**Done when:** the dialog works; auto-open opens only the defaults; "+N more" opens the rest; old
templates and sessions unchanged; en + he strings, RTL checked; e2e for the flow.
**Status: done 2026-11-07.** Found first: the library's details already had a checkbox per tab
(`applyTemplate(..., chosen)`); smartStart never opened a template by itself for an ordinary file
(the start card's *Open it*; only the examples open at once, T48). Decided (owner agreed): the library
= the choice (now All / None, defaults pre-checked); a chip of a template with several tabs = the
"which tabs?" dialog (`TabChoice.tsx`, skipped by Settings `tplTabChoice: "defaults"`); *Open it* and
the examples = the default tabs, no question. Owner chose `defaultTabs: ["Attitude", "Flight"]` for
both built-in full reviews (also MAVLink's). Made: `Template.defaultTabs` (optional, names over the
expanded tabs; prefs `_validate` drops junk), `templates.ts` `defaultTabIdx` / `tabIdxByName` /
`openMoreTabs` / `forgetMore` / `announceOpened`, `applyTemplate` records the tabs left out in
`ws.moreTabs` (optional; one entry per template, in the same Undo step), one "+N more ▾" button beside
the + (a section per template when several; hidden when a bound file is closed), the editor's
*Opened by default* list (a renamed tab stays default; all / none checked = not stored).
Tests: test_templates.py (+2), e2e test_template_tabs.py (3). Left: "1 tabs" in the toast (plurals: U7).

### U3 · One flight-mode band per tab — M
**Do:**
- When all plots of a tab share the X axis, the mode band (e.g. `MODE.Mode`) is shown once at the top of
  the tab, not in every plot.
- Cursors 1 / 2 AND hover are drawn on that band as vertical lines; the mode under the cursor is
  highlighted / labelled, so it is clear which mode the inspected moment is in.
- Clicking a segment keeps today's behaviour. A plot can turn its own band back on from its ⋯ menu.
- First check whether a per-plot setting for this already exists (see `sharedStates` / `globalStates`
  above).

**Done when:** the ArduPilot example shows one band with the cursor and hover on it, the plots get the
freed height, sessions compatible.
**Status: done 2026-11-07.** Found first: the overview strip (`OverviewStrip.tsx`, above the plots)
already showed the run's phase signal (MODE.Mode) - for the WHOLE run, one file, with the zoom window
as a frame; a click there picks stretches for a condition. The per-plot lanes came from
`tab.sharedStates` / `ws.globalStates` (a lane's scope menu: this plot / tab / all tabs); no per-plot
opt-out of a tab lane existed. Owner (2026-11-07): keep the strip as it is, and show the plots'
cursor on it too. Made: `TabBand.tsx` above the plot grid (`tabBandLanes`: tab + global lanes when
X is linked, one column, two or more time plots - one band can line up with all of them); it follows
the first time plot's shown window (`xViews`, reported by TimeChart's draw hook, UI only) and its
drawing area (measured from `[data-plot] .u-over`); cursors 1 / 2 and hover as lines with the state
under each named, that stretch outlined; click = cursors on the edges, Shift = zoom; the lane name
opens the lane's scope menu. TimeChart leaves those lanes out unless `plot.ownBand` (optional; the
plot's ⋯ *State lanes in this plot too*). The strip draws the cursors and hover (`.ov-cur`).
Tests: e2e test_tab_band.py (2). Left: the hover line is drawn only on the hovered plot (as before).

### U2 · Health findings must not cover data — S/M
**Do:** today the "Opened: <file>" health card floats over the 3rd plot. Move it to a docked corner /
side panel (collapsible, e.g. "3 findings"), and show the findings as markers on the bottom timeline
(click = the same as *Plot*).

**Done when:** nothing covers plot data on open; the existing links (*Plot*, *All findings…*) still work.
**Status: done 2026-11-07.** The card is the start card (`StartCard.tsx`, T29) in the notices dock over the
plots' bottom-left corner. While it offers a template (nothing plotted yet) it stays as it was; with
findings only (the view is open) it folds into `FindingsDock` at the start of the timeline ("! 3
findings"; click = the card over the plots, its X folds it back, the dock's × closes it). Every
finding with a moment (all of the check's, not only the card's three) is a ◆ on the timeline
(`findingMarks`, UI only, per file; kept after the dock is closed); a click = its *Plot*
(`plotFinding`, HealthRow.tsx), marks closer than 1.5 % of the run are one mark with a list.
Tests: test_workflows (ArduPilot example), test_features (smart start) updated. Left: the toast
"<template>: 2 tabs, 5 plots opened" still sits over the third plot for 4 s.

### Group 2 - marketing basics

### M1 · Hero image, social preview, tagline — S
**Do:**
- A hero screenshot, 2×2 in one window, dark theme, 2x resolution, made by `tools/make_readme_media.py`:
  the map with the track coloured by flight mode and the vehicle at the cursor; the 3D attitude; Roll
  (desired vs actual) with the mode band and the cursor at the vibration moment (~140 s in the ArduPilot
  example); a health finding visible. Signal list hidden / narrow; no popups.
- README order: hero → one-line pitch → the play GIF (`02_flight_map_3d`) → health check → compare →
  quickstart later.
- A 1280×640 crop for GitHub's social preview (the owner uploads it).
- Tagline (package name stays `signalviewer`): "Signal Viewer – offline flight log & test data
  analysis" in the README, the pyproject description, mkdocs `site_name` / `site_description`.
  **Confirm the wording with the owner first.**

**Done when:** the hero and the crop are in `docs/images`, made by the tool; the README in the order
above; `mkdocs build --strict` passes.
**Status: done 2026-11-07** (the tagline approved by the owner the same day: README title line,
tools/make_pypi.py `description`, mkdocs `site_name` / `site_description`). Made:
`img_00_hero` in tools/make_readme_media.py (the ArduPilot example as a user opens it, its Flight tab
made 2 x 2 - map with the track by MODE.Mode, 3D behind the vehicle without the data box and the
events, Roll DesRoll / Roll, VIBE X / Y / Z - the cursor at 140.4 s, the findings docked, no signal
list; dark, device scale 2 -> 3200 x 1800); tools/make_social_preview.py now crops it to 1280 x 640
(the old card: `--card`); README: hero, a one-line pitch, then the map / 3D clip, the health check,
compare, then the feature list and the rest. Note: in a headless browser the 3D view's camera does not
come close (software WebGL, as for 06); the vehicle and its track show, its attitude only roughly -
retake that quadrant from a real screen if wanted. The tagline goes to the README title line,
tools/make_pypi.py (`description`) and mkdocs `site_name` / `site_description` once confirmed.

### Group 3 - architecture

### A1 · Split `backend/app/store.py` — M
**Do:**
- The investigate logic (`evaluate_condition`, `occurrence_rows` / `windows` / `differ`,
  `first_changes`, `change_clusters`, `_chain`, `suggest_condition`, `lag_between`) → pure functions in
  `svcore/investigate.py` that take a signal getter.
- Live polling (`poll_appends`, `_poll_appends`, `newer_on_disk`, `new_files`, `activity`) → a
  `LiveWatcher` class.
- No change to routes, API, sessions or behaviour.

**Done when:** `store.py` < 900 lines; pytest + mypy green; Investigate e2e green; unit tests for
`investigate.py` without a Store.
**Status: done 2026-11-07.** 1,495 -> 850 lines. Moving the two named parts gave ~1,050, so two more
self-contained parts left too: `app/filecheck.py` (LoadError, sniff_kind, check_file, the CSV failure
reasons) and `svcore/transforms.py` (normalize / apply a change on a signal); `overview` and
`run_params` (investigation steps 7 / 5) went with the investigate functions. `svcore/investigate.py`:
`Source` (signal getter, names + state texts per file, discrete, derived names, open runs) and pure
functions; Store methods are one-liners (`_source()`), LoadError for the user's mistakes as before.
`app/livewatch.py` `LiveWatcher` (state: lock, poll_errors, writing - Store properties keep the old
names; `_stat`, `run_format`, `UPLOAD_DIR`, SETTLE_* live there). `app.store` re-exports every moved
name. Tests: tests/test_investigate.py (5, no Store); pytest all, mypy (only the 4 known numpy-2.5
errors in routes/analysis.py, also on main); e2e test_conditions, test_what_changed, test_occurrences,
test_runs_matrix, test_overview_strip, test_refresh_feedback, test_findings_report.

### Group 4 - UX (whole e2e suite at the end of the group)

### U6 · Hover moves a ghost point on the map / 3D — S
**Do:** GeoChart and Globe3D draw a semi-transparent point at `s.hover.t`; it disappears when the mouse
leaves the plot and does not touch the cursor or undo.
**Done when:** in the Flight tab, hovering a plot moves the point.
**Status: done 2026-11-07.** Found: `s.hover` is empty while the cursors are on (the legend then shows the
cursor's values) - and on the Flight template the cursor is usually on. So TimeChart also publishes
`s.pointer {plotId, t}` (UI only), set whenever the pointer is over a time plot, cursors on or off,
cleared on leave; `hover` keeps its meaning. GeoChart draws each object's icon at 45 % there (no
name); Globe3D a faint point per object (`ghosts`, a PointPrimitiveCollection; not for a 3D view on
its own time). Only from plots of the same tab. Note: the built-in Flight tab (map + 3D) has no time
plot, so there the ghost needs a plot added (the e2e adds one) - an altitude / speed plot in the
template would make it show by default (owner's choice). Tests: e2e test_hover_ghost.py.

### U4 · Desired vs actual — S
**Do:** pairs `Des<X>` / `<X>` (ArduPilot) and `*_sp` (PX4) in one plot → the desired line dashed and
muted automatically; a style set by hand wins. First check whether the templates already set styles.
**Done when:** the ArduPilot Attitude tab shows desired dashed without a template change; a manual style
is kept; sessions compatible.
**Status: done 2026-11-07.** Found: the built-in templates give colours (desired blue #3D8BFD, actual
amber #F2A93B) and widths, no dash - and a plot line had no dash at all. Made: `desired.ts`
(`actualNames`: Des<X> / <X>Des / <x>_sp / <topic>_setpoint.<f> -> the measured name, same file, unit
ignored; `setpointsIn`, `lineLook`, `fade`), `PlotSignal.dash` (optional: true / false by hand, absent =
automatic), TimeChart draws dash + 72 % opacity, the legend swatch dashed, Inspector ▸ Line (Auto
(dashed / solid) / Solid / Dashed). Templates do not store `dash` (the automatic look comes back on
open). Tests: e2e test_setpoint_style.py.

### U5 · SDI-style difference view in Compare — M
**Do:** selecting a signal shows a difference plot under the overlay with the existing tolerance band,
out-of-tolerance regions in red, ✓ / ✗ per signal in the list. First check what the current "difference
profile" in ComparePanel shows.
**Done when:** the 3-car example shows where and why a signal fails.
**Status: done 2026-11-07.** Found: the list's "difference profile" is a 32-bin spark of |Δ| (its shape
only, no tolerance, no time); the detail had numbers per run and *Plot differences* (derived Δ
signals in a new plot, no band); a failing row had "!", a passing one nothing. Made: backend
`compare(..., trace=N)` / `/api/compare` `trace` -> each row's `trace` {t, d, lo, hi, out}
(`difference_trace`, `_band`: the same rule as `metrics` - max(abs, pct x |baseline|), the time
tolerance's envelope; min / max buckets keep spikes; `out` at full resolution, gaps under 0.2 % of the
span merged); `DiffChart.tsx` in the detail (band green, out red, zero line, a line per run in its
colour, click = cursor; the stretches listed, a click = both cursors + zoom; off in a segment
comparison); ✓ / ✗ per row. The 3-car example, ±2 km/h on Speed: run_014 fails during the
accelerations (it lags), run_013 only in slivers. Tests: test_compare_trace.py (3), e2e
test_compare_diff.py; test_features P01-P08 reads names with ✓ / ✗ (passed 3 of 4 runs here on the
first try, then every time - timing).

### U7 · Less clutter — M
**Do:** the plot-header help line ("Click: pick · Ctrl or Shift+click…") → a tooltip / first time only;
toolbar icons without labels get labels or move into a ⋯ menu; "1 files" fixed (singular / plural, en +
he); "Showing 3,840 of 12,300 points" reworded so it does not suggest missing data.
Also (owner, 2026-11-07): the overview strip's automatic flags and the plots' log events are the same
amber triangle - make them look different (e.g. a small diamond for automatic flags, its tooltip
starting "Automatic flag:"), with a short key in the strip.
**Done when:** fewer than 70 visible buttons in the ArduPilot example, measured in e2e (107 today).
**Status: done but the target's measure, 2026-11-07.** Measured as the owner did: visible `<button>` +
`<select>` in the example (107 on main at 1.21.0; with U1-U6 106). Now 85 - of them 26 are the log's
data shown as buttons (6 signal rows of the open group, the MODE stretches in the strip (6) and in the
tab band (6), 4 flag rings, 3 timeline marks, ...) and 59 controls. Made: DataPanel groups closed by
default above 40 signals unless a signal of the active tab is in them (above 200: all closed, as
before); TemplateStrip folds its chips once something is plotted (`.tpl-strip-fold`); `.mode-btn.is-time`
only on the active / hovered plot; StageBar ⋯ (`.stage-more`: Back, Clear all plots) instead of two
icon-only buttons; the strip's how-to line until first used (pref `ovHintSeen`), then the head's
tooltip; automatic flags as rings, *Auto flags* + "Automatic flag (found in the data):" (the log's
events stay ▼); "1 file", plurals in "tplOpened" (`openedCounts`), "N points drawn for M samples" with a
tooltip. Not changed (owner's earlier choices): the session open / save icons and the Inspector icon
in the Recordings bar (F35), the language / theme buttons in the top bar. To reach < 70 *buttons*:
the strip's MODE row could hide while the tab band shows the same signal (-7; the owner kept the strip,
2026-11-07), or the stretches could be drawn as one clickable track instead of a button each (-12,
fewer keyboard stops) - owner's choice. Tests: e2e test_less_clutter.py (controls < 70, buttons < 90);
test_features (V09 wording, Clear via ⋯), test_workflows (⋯, the folded chips), test_template_tabs.

### Group 5 - maintenance / design

### A2 · Split `frontend/src/i18n.ts` — M
**Do:** by area into `i18n/*.ts` and an index merging them; `he: typeof en` kept per file.
**Done when:** the same key count before and after; no file over 600 lines; tsc + build green.
**Status: done 2026-11-07.** `frontend/src/i18n.ts` (3,610 lines) -> `frontend/src/i18n/`: index.ts (48 lines:
the merge, `translate`, `useT`, the number formats; imports still `./i18n` / `../i18n`) and eleven
area files (app 183, common 247, compare 343, files 551, flightlog 299, investigate 405, liveAndFleet
163, mapsAnd3d 371, plots 365, signals 323, templates 397 lines), each `en` + `he: typeof en`. Keys
were assigned by their names' prefixes (a script; each key's line moved as it was, en and he in the
same order). 1,785 keys before and after, none in two files; the Sweeps texts (sweeps/i18n.ts) merged
first as before. CLAUDE.md / CONTRIBUTING.md point to the folder.

### A3 · App.tsx cleanup — S
**Do:** Welcome, RAIL and the EXAMPLE_* maps to their own files.
**Done when:** `App.tsx` < 450 lines; no behaviour change (relevant e2e green).
**Status: done 2026-11-07.** App.tsx 632 -> 434 lines: components/Welcome.tsx (the welcome screen with the
EXAMPLE_* maps), components/rail.ts (RAIL, RAIL_W), components/PlotGrid.tsx, shortcuts.ts
(`useShortcuts`, the keyboard listener - Welcome / RAIL alone left ~540). e2e test_fresh_user,
test_file_help_menus, test_wheel, test_timeline, test_workflows, test_features -k key / tab / V...

### U8 · Navigation design (no code) — S
**Do:** sketches for unifying the Recordings / Sweeps tabs, the view tabs and the left rail. After U1.
**Done when:** a design note with sketches in `docs/dev/`, for the owner to choose from.
**Status: done 2026-11-07.** docs/dev/NAVIGATION.md: today's three tab-like rows and the rail as a first-time
user meets them; Option A (the areas as a segmented switch, Fleet an area, one "+ ▾" for views, a
fixed rail - recommended), Option B (an activity bar on the left, one row of chrome less), Option C
(one strip for everything - rejected, why); three questions for the owner.

### U9 · Navigation option A (owner approved U8's recommendation, 2026-11-07) — M
**Do:** docs/dev/NAVIGATION.md option A: the areas as a segmented switch (not a tab row); Fleet an
area (was a rail panel); one views menu "+ ▾" beside the tabs (new tab, open a template or collection,
the tabs templates left out - U1's "+N more" folded in, their number on the ▾); the rail keeps its
tools, Log disabled with a tooltip while no flight log is open.
**Done when:** the three areas switch; the Fleet example works in its area and opening a flight goes
to Recordings with the Log; templates open from the views menu; tests follow.
**Status: done 2026-11-07.** `areas.ts` `fleet`; FleetPanel.tsx is the area (its bar, two columns, its
own messages), `openAt` switches to Recordings; `PanelId` without `fleet`, the palette's Fleet opens
the area; TopBar `.add-view` (+ and `.more-tabs` ▾ with `.more-count`), Templates ▾ keeps Save /
New collection (`templateMenuItems`); App's rail shows Log disabled (`railLogNone`); the status bar
only in Recordings / Sweeps. Tests: e2e test_navigation.py; test_fleet, test_owner_notes_1_20,
test_template_tabs, test_fresh_user, test_templates_recent_badfiles, test_features, test_object_templates,
test_one_per_plot follow the new places; tools/make_readme_media.py too. Docs: features, GUIDE (en / he),
fleet tutorials.

## Sweeps area plan (owner, 2026-10-31): S00–S08

The owner's requests for the Sweeps area (`components/sweeps`, `sweeps/`, `routes/sweep.py`,
`svcore/sweep`, `app/sweep_report.py`), in the order agreed. Each task is one or a few commits;
every patch to the owner holds ALL commits since `origin/main` (see the practical notes).

**Progress:** S00–S08 done (and S01b: optimize).

### S00 · Groundwork for working on two areas at once — S · **Done**
- The Sweeps strings live in `frontend/src/sweeps/i18n.ts` (`swEn`, `swHe: typeof swEn`), spread
  into `en` / `he` in `i18n.ts`: same `TKey`, tsc still checks Hebrew. New `sw*` keys go there.
- `PanelResizer` (`components/PanelResizer.tsx`) and `usePanelWidth` (`components/panelWidth.ts`)
  left `App.tsx`, so any area can have resizable panels (same prefs keys `sv3.w.<key>`).
- Still shared by both areas (expect conflicts there): `CHANGELOG.md`, this file, `ROADMAP.md`,
  `App.tsx` (area wiring), `index.css`, `components/Overlays.tsx`, `store` (`pickPath`).

### S01 · Fixes found in the review — S · **Done**
- A parameter taken out in *Clean columns* was still offered by the map, next runs and the report's
  map (the server answered `Choose two different parameters`); one list now: `activeParams(study)`.
- Next runs drew its marks against `mapX` / `mapY` as stored, the map against the checked
  pair: one function, `mapAxes(study)`, for both (and the report).
- A goal's weight (`defaultValue`) kept the previous goal's number after switching goals.
- Saving / deleting a template from the Study menu swallowed errors and said nothing on success.

### S02 · Undo / redo, autosave, one place for messages, Ctrl+K — M · **Done**
- Undo / redo of every change to a study (roles, question, goals, view steps that change what is
  shown: filters, keep / exclude, axes); not the hover / panel state. Ctrl+Z / Ctrl+Y when the Sweeps
  area is on screen; buttons in the area's bar.
- Autosave of the open studies (as `.svsweep` documents, in the prefs folder) and reopening them
  at start; a table that cannot be read any more is reported, not dropped silently.
- Messages through the app's message strip instead of a `note` per component.
- The area's main actions in the command palette.

### S03 · Layout: resizable panels, many columns — M · **Done**
- Steps panel and set panel resizable / collapsible (`PanelResizer`).
- Parallel plot: a minimum width per axis, horizontal scroll (the wheel scrolls sideways), *Fit
  to width*; the tooltip in columns; sticky rank / holds / re-run columns in the tables.
- `ColumnPicker`: fuzzy search (`fuzzy.ts`), grouped by role, several at once; replaces every
  column `<select>` of the area.

### S04 · The sets table: only those that hold, columns, export — M · **Done**
- *Only sets that hold*, chosen columns, sort by a header, pages instead of the 300-row cut.
- **Export**: the sets (a row per set, the columns shown) or their runs (set x scenario); all /
  shown / only holding. The report's table and CSV follow the same choice.

### S05 · Several maps and point plots — M · **Done**
- `view.maps` / `view.scatters` (optional; `mapX` / `mapY` become the first map); + map; the other
  parameters: every value (share) or at the best set (a slice); the holding boundary; a click on a
  cell filters its sets; every map in the report.

### S06 · Next runs: which parameters, robustness — L · **Done**
- Parameters to explore (all / those on the maps / chosen), the rest at the base set's values.
- Robust in: a tolerance per parameter (%, absolute or grid steps); the goal's worst case within
  it as a column and a ranking; a `robust` kind of suggestion that measures it.
- `best` from the Pareto front / score; marks on every map (a set that
  differs on a parameter not drawn is marked so); suggestions kept in the study and the report.
- With the defaults `suggest()` answers as before (test).

### S07 · Templates — S · **Done**
- A dialog like `TemplateLibrary`: save (ask before overwriting), update, export / import a file,
  delete; the new fields (maps, table columns, explore / tolerance) included.

### S08 · The whole process in the report — M · **Done**
- A journal of the study (optional field in `.svsweep`), consecutive changes of one kind merged;
  each merge an iteration (a convergence plot); the report: the journal, every map, the suggestions,
  provenance (file hash, app version).

## Sweeps, round 2 (owner, 2026-11-01, after using S00-S08): S09–S18

**Progress:** S09–S19 done.

### S09 · Nothing overlaps in a small window — S · **Done**
- The step's foot: *← Scenarios & parameters* and *See the results →* run into each other in a
  narrow side panel: they wrap (or shorten) instead.
- The plot's bar scrolls sideways under its own scrollbar, which covers the buttons: it wraps onto
  a second line instead. Every bar of the area checked at 1024 px and with the side panel wide.

### S10 · Where the optimization shows — M · **Done**
- With only something to optimize (no condition) every set holds: the maps are one colour and the
  table's order is the only trace. The answer's side panel gets **the best set** (its parameters,
  its goal, *open*), and the map can be coloured by **the best goal** instead of the share holding
  (a choice of the map; the default: the goal when there is one).
- The map's numbers: the best goal of the cell; with no goal there is none to show (not "1", which
  was the share). A key says what colour and number mean.
- The best set marked on the maps (★).

### S11 · Points: axis titles, in the report — S · **Done**
- The point plots get their axis titles (and ticks that read); every point plot on screen goes
  into the report (HTML, Word, PDF), as the maps do.

### S12 · How the plots look — M · **Done**
- Maps, point plots and *Which parameter matters*: a few choices each, kept with the study and used
  by the report - colour map (viridis, plasma, cividis, turbo, greys), the point's size and
  opacity, grid on / off and a minor grid, the numbers on the cells on / off.
- *Which parameter matters*: axis titles (the parameter, the goal), a grid with minor lines.

### S13 · Many columns: see all, or move along them — S · **Done**
- Checked on a table of 60 columns: *Fit to width* puts every axis in; otherwise a **slider** under
  the plot shows where the view is among all axes and moves it (dragged, or clicked), besides the
  wheel. Screenshots in both themes and in Hebrew.

### S14 · The sets that hold as an interactive plot — S · **Done**
- The table's *Export* also writes the sets shown as an interactive parallel plot (HTML, like
  HiPlot: filters by dragging, a click on a line), not only as CSV.

### S15 · An axis taken off the plot comes back — S · **Done**
- An axis removed from the plot (its menu, or the column picker) is easy to bring back: the
  removed ones stay listed under the bar (*+ name*), and the picker's button says it adds as well.

### S16 · Next runs: numbers that add up — M · **Done**
- *Sets to suggest* is what you get: each kind says **found** (how many it could suggest) and
  **taken** (how many of the budget went to it); the line under the budget says *N sets × M
  combinations = R runs* for what will really be suggested, and why fewer when fewer were found.
  How the budget is shared between the kinds is said (in turns, a fair share each, what one kind
  does not use goes to the others).
- A small budget still gives every chosen kind a share before any gets a second.

### S17 · Next runs: a compact view, more than CSV — M · **Done**
- The suggested sets shown compactly: a parameter with one value in all of them is said once above
  the table; each row shows what it changes from its set (bold) and why.
- Besides CSV: copy as a table (to paste into Excel / a spreadsheet), JSON, and a MATLAB / Python
  snippet (a struct array / a list of dicts) for a simulation script.

### S18 · Which parameter matters: in the report, like the screen — S · **Done**
- The figure on screen and in the report: axis titles, a grid (major and minor), the style of S12.

### S19 · The optimization in the plots, and choosing on a Pareto plot — M · **Done**
(owner, 2026-11-01: "show the optimization in the HiPlot... a Pareto plot, move on it and see the
parameter sets change in the HiPlot and the CSV")
- The lines' default axes take the rank, and the weighted score with several objectives: dragging
  on them keeps the best N, and the parameters' axes show what those have.
- In Points, *Pareto*: the first objective against the second, the front's sets marked and joined.
- A rectangle dragged on any point plot keeps what is in it - as the lines' filters on its two
  columns, so the lines, the table, its Export (CSV, HTML) and the report follow; a click outside
  clears it.

## Sweeps, round 3 (owner, 2026-11-01): S20–S23 - the journal as the report wants it; exploring

**Progress:** S20–S23 done.

### S20 · The journal for the report: the final story — S · **Done**
- The report's journal shows **the final steps only** by default: for each thing (a goal, the
  roles, robustness, columns taken out, keep / exclude...) its last change; changes that were
  undone or overwritten are not in it. *The whole journal* stays a choice of the report.
- Opening a file is not a line of the journal (*Where it comes from* names the tables); merging
  one still is.
- In the Report step: × on a line hides it from the report (and brings it back); **"The analysis
  starts here"** on a line hides everything before it. Kept with the study.

### S21 · Explore: a draft of a goal - conditions, limits and objectives together — L · **Done**
- A center tab **Explore** (by Lines, Map...). It opens as a copy of the active goal and changes
  nothing until **Save as a goal** (a new goal, or replacing the active one - asked) or **Back to
  the goal**. A line says how the draft differs from the goal.
- One result for all of it, at every move: the sets go through (1) the goal's conditions, dragged
  as *what if*, robustness included, (2) limits on the parameters (a range each), (3) thresholds
  on objectives; (4) the objectives - each with its direction, weight and optional threshold,
  added and removed by typing as everywhere - rank what is left.
- On screen: a funnel (all → after conditions → after the limits → after the thresholds), each
  slider's own cut (*alone it removes N*), a histogram strip under each slider with the holding
  sets coloured, the best set (and a note when a move changes it), the leading candidates, and with
  two objectives the Pareto plot (the front ringed, the best starred; more objectives: choose two).
- Save as a goal keeps everything: thresholds and parameter limits become conditions, objectives
  their directions and weights - the saved goal gives exactly what was explored. One journal line.

### S22 · Goals: the best set while editing — S · **Done**
- At the foot of the Goals step: how many sets hold and the best set with its objectives' values,
  updated while conditions, directions and weights are edited (the Results' card).

### S23 · Explore: visible, reachable and live in the plot and the table — M · **Done**
Owner's notes after S21: Explore was hard to find (a tab of the results, while the goal is edited in
Goals), most of its sliders hid behind an action (a picker for limits, weights only from two
objectives, a checkbox for thresholds), with one objective and no condition it looked empty, and the
optimization did not show in the parallel plot ("HiPlot") and the table.
- **Way in:** *Explore this goal →* in the Goals step's panel and in the Results' answer panel (not
  while Explore is on screen): a fresh draft of the active goal. The Explore tab goes back to a draft
  already there. Still a draft: the goal changes only on Save.
- **Everything on screen:** a two-thumb range per numeric parameter (the whole range = no limit;
  *limited: N*; a search box from 7 parameters); every objective's weight (disabled with one, with a
  line saying weights count from two) and threshold (its far end = *no threshold*); *+ condition* in
  Explore (column - outputs and parameters -, comparison, the value as a slider; × removes); an empty
  goal shows every parameter and *+ objective*.
- **Live:** controls on one side; on the other *N of M parameter sets left*, the existing
  ParallelPlot and SetsTable driven by the draft, the best set and (two objectives) the Pareto plot.
  How (no fork): `explore.ts draftStudy` - the study as the draft makes it: the draft structure's
  answer with #holds = the sets left, #rank = the draft's order (#score / #pareto of what is left),
  the question = the draft saved as a goal (an export's own columns say what Explore said; an "or"
  goal: its conditions only), the view without the goal's filters / keep-exclude steps and with
  onlyHolding. ParallelPlot takes `keep` (the rows left; the limits are drawn as filter marks only)
  and says its count in `data-shown`; dragging on a parameter's axis sets its limit. SetsTable takes
  `draft` (no *only those that hold*). Exports of what is left: the table's menu (CSV in rank order,
  their runs, the interactive plot).
- *Back to the goal* drops the draft and shows the Lines (the goal's own view: nothing of the draft
  was stored in it).
- Notes: `aria-busy` on `.sw-explore` while a new structure is asked (the last answer stays on screen
  with the draft it was asked for - its columns are that draft's, a condition added does not read
  another's worst case). Layout by a container query on Explore's own width (side by side down to
  600 px: at 1024 px with the side panel open they still fit). The strips under the sliders are
  mirrored in Hebrew, as the range inputs are. The S21 e2e follows the new controls (no picker, the
  threshold a slider); its equality check is unchanged.

## Sweeps, round 4 (2026-11-01): S24–S27 - Explore, what S23 left

**Progress:** **closed 2026-11-02 (owner)** - none done: the Sweeps redesign took Explore out, so none of
these applies any more. Kept below as a record.

### S24 · A condition added in Explore starts where it keeps every set — S
**Now:** *+ condition* (and a new column chosen on a row) starts at the far end of the column's
per-set value (`openValue` in ExploreView: the output's aggregate, the mean by default). The
condition is checked on the worst case over the combinations, which is often past the mean, so a
condition just added already takes sets out - the funnel moves before the user touched anything.
**Do:** start at the far end of the worst case: ask the server first (the new structure's
`#c<i>.worst`, then set the value), or take the column's largest / smallest value over all runs (the
table summary has it). **Done when:** adding a condition leaves the funnel's numbers as they were
(e2e: add one, compare the funnel).

### S25 · Explore's table: its own sort and columns? — S · **owner's choice first**
**Now:** the table in Explore is the goal's SetsTable on the draft's study; a sort or a column chosen
there is the goal's table's too (the same `view.tableSort` / `tableColumns`), and is undone with
Ctrl+Z like any table change. Consistent, but a sort tried in a draft stays after *Back to the goal*.
**Choice:** (a) keep it shared (and say so in the GUIDE), or (b) the draft's own sort / columns, kept
in `view.explore` beside the draft (not undone, like the draft). With (b): SetsTable takes them as props.

### S26 · The axes in Explore's lines — S/M
**Now:** in Explore a click on an axis's name does nothing (`onAxisMenu` / `onMoveAxis` are no-ops),
and a drag on an axis sets a limit on a parameter's axis only.
**Do:** the axis menu as in Lines (scale, reverse, colour by - stored in the study's view, as Lines
does); a drag on an objective's axis sets its threshold (the end of the range on the good side), on a
condition's worst case its value; axes reordered by dragging their names, kept for Explore.
**Done when:** each kind of axis does what its slider does (e2e: drag on the objective's axis - the
threshold slider moves and the funnel follows).

### S27 · Explore on Windows and macOS — S · **owner's check**
Not run here (Linux Chromium only): the window on Windows (WebView2) and macOS (WKWebView - container
queries need Safari 16+): the controls beside the lines at 1024 px, the two-thumb slider (both thumbs
draggable, the fill between them), Hebrew (the strips mirrored like the sliders), both themes.
**Done when:** checked, or the differences written here as tasks.

## Owner's notes (2026-11-01): Q124–Q126 - new signals in the investigation; signals slower than their recording; update flags

**Progress:** none started. Q125 and Q126 are one mechanism (a signal's *updates*): do Q125 first.
Two choices for the owner are marked **owner's choice**.

### Q124 · A signal made with an operation, in the investigation — S/M
**Now:** a new signal (ƒ, made in Create / with a formula) lives in the shared *derived* run, not in
the file it came from. *What changed first* asks for every signal of the event's file (scope *the
event's file*) or of every file (*all files*) - `store.first_changes(..., run_ids)` lists the runs'
own signals, and WhatChanged.tsx drops the derived run (`files` / `allFiles`: `!== "derived"`). Only
the scope *the tab* takes one, and only when it is on a time plot. The same filter is in
InvestigatePanel.tsx (`files = runs.filter(r => r.format !== "derived")`).
**Do:** a derived signal belongs to the file(s) of its sources - `DerivedDef.sources` (`run/Name`),
through derived sources recursively, and the `@run:Name` references of a formula. In
`first_changes` (and the other investigation steps that take "the signals of these files": *Find
similar* / `suggest_condition`, *What differs inside the stretches*, the overview strip, Runs ×
conditions - check each caller) a derived signal is counted with a file when all its sources are
in that file; one made from several files only with *all files* / *the tab*. Its row says ƒ. Under
it, *the same signal in the other files*: its copy there (Copy work to another file), if any.
**Done when:** backend: `first_changes` with a file's id lists a derived signal of that file and
not one of another file; e2e: a formula on the event's file, *What changed first* with its default
scope lists it (ƒ) in its place by time.

### Q125 · A signal slower than its recording: its real updates — M
**Now:** a value computed at 5 Hz and logged with everything else at 100 Hz is a staircase: 19
samples equal, then a step. Every operation reads all of them: the derivative (`np.gradient` in
svcore/analysis.py op `derivative`; `deriv()` in formulas) is 0 between updates and a spike of about
20× the real slope at each step; a difference between two such signals jumps the same way; a
spectrum sees the steps; *What changed first* counts samples (3 in a row) that are copies.
**Do:**
1. **See it:** per numeric signal, the typical number of equal samples in a row → *updates at about
   5 Hz (recorded at 100 Hz)*, where the signal's rate is shown today (the signal list, Inspector).
   Computed once and cached like `is_discrete`; skipped for states / text (they are steps by nature).
2. **Set it** (Inspector → the signal → *Updates*): *every sample* (as now) · *when it changes* (the
   first sample of each step) · *at N Hz* (the detected rate offered). Carried by the existing
   per-signal edit - `apply_transform` in store.py gets a `rate` part (`{"mode": "changes"|"hz",
   "hz": 5}`), applied before the formula / scale / offset - so every plot, operation, compare,
   check, report and investigation reads the updates, the edit is copied to other files with *Copy
   work* and kept in sessions and templates like any edit. A plot draws the result as steps (hold),
   as the value was.
   **Owner's choice - decided (2026-11-01): in place.** The signal itself becomes its updates;
   *every sample* undoes it. The signal list and the Inspector show a small tag (`5 Hz`) on a signal
   whose updates are set, so a session opened later does not hide why its derivative is smooth.
   **Rate mode, two more fields:** `{"mode": "hz", "hz": 5, "phase": null, "delay": 0}`.
   - `phase` - where the N Hz grid sits. `null` (default) = found from the detected steps (the
     median of the step times modulo the period); a number (ms) overrides it.
   - `delay` - a shift of the update times (ms, default 0), for a value measured before it was
     logged. It applies to every mode (changes, hz, flag, clock), not only to hz.
3. **Use it:** derivative, integral and the binary differences work on the updates of each signal;
   a result needed on another signal's time (A − B) is held between updates, not interpolated across
   a step. With a slower rate detected and *every sample* chosen, the derivative dialog says so
   (*Roll updates at 5 Hz: its derivative will be spikes - use its updates*).
**Caveat to keep in the UI:** *when it changes* also drops samples where the true value stayed the
same (a hover); *at N Hz* does not - offer it first when the rate is regular.
**Done when:** backend: a 5 Hz ramp sampled at 100 Hz - detected 5 Hz; its derivative over the
updates equals the true slope (±1%) with no spikes, over every sample unchanged; a session round-trip
keeps `rate`. e2e: Inspector shows *updates at about 5 Hz*, set it, the derivative plotted is flat.
A small example file in `tools/make_demo_data.py` (or the test's own), not a new example on the
welcome screen.

### Q126 · A flag that says "the value is new" — M (after Q125)
**Now:** some loggers write beside a value a flag (`valid`, `updated`, `new_data`) or a counter that
moves when the value is fresh; the value is meaningful only there. Nothing can use it: `where(c, a,
b)` keeps every sample (and `nan` is not a name a formula may use), conditions choose stretches, not
samples.
**Owner's notes (2026-11-01):** the *Updates* choice is one mechanism - **an update clock** - with
these sources: *every sample* · *when it changes* · *at N Hz* (phase, delay - Q125) · *a flag*
(below) · **the updates of another signal** (`{"mode": "clock", "of": "Name" | "@run:Name"}`): the
times another signal's updates were found (by any of the modes above) are this signal's updates.
That is how one detection serves a group (all of a GPS's fields). With a selection in the file
list, *Updates ▸ like <signal>* sets it for all of them in one undo step. The clock's source is
read like the flag: the existing references, previous sample, and a cycle (A by B, B by A) refused.
**Do:** the same *Updates* choice as Q125, one more mode: *when <signal> is set* (≠ 0) · *rises*
(0 → non-zero) · *changes* (a counter) - `rate: {"mode": "flag", "flag": "Name" | "@run:Name",
"when": "set"|"rises"|"changes"}`. The flag is read with the edit's existing references
(`transform_refs` / `ref_run`, Q89-Q90: same file or another, its reload recomputes), but taken at
the value's times by the **previous sample** (not `np.interp`: a 0/1 flag interpolated is 0.5).
The value's samples at those moments are its updates; everything in Q125 3 follows. A flag found by
name next to a value (`X_valid`, `X.new`, `XUpd`) is offered first in the list.
**Owner's choice (still open):** which flags your loggers write (a 0/1 per sample, a bit in a status
word, a counter) - a bit in a word needs *when bit k of <signal> is set* (`"bit": k`); a real log
with one would settle it. Build 0/1 and counter first; leave room for `bit` in the schema.
**Done when:** backend: a value with a `new_flag` (set at 5 Hz, random gaps) - its updates are
exactly the flagged samples, the derivative over them equals the truth; the flag from another open
file works; e2e: Inspector → *Updates: when new_flag is set*, the plot shows the steps at the flags. Clock:
three signals set *like* a fourth take its update times exactly; a cycle is refused with a message.

## Owner's notes (2026-11-01, 2): Q127–Q129 - work on a selection; the same formula for [1], [2]; typing values in Explore

**Progress:** Q129 done 2026-11-01 (with MF01). Q127, Q128 not started. Independent of Q124–Q126 and of each other.

### Q127 · Operations chosen by the selection — S
**Now:** the file list's selection (`listSel`) has *Create signal ▸* (createSignalMenu.ts), but its
quick operations are derivative and integral only, one new signal per source. The backend already
has `norm`, `mean`, `sum`, `min`, `max` (`MULTI` in svcore/analysis.py) and the binary operations;
they are reached only through *Other operations…* (Analysis, `analysisSeed`), where the signals are
chosen again.
**Do:** *Create signal ▸* offers by the selection's size: 2 signals - *A − B*, *A + B*, *A / B* (and
*B − A*); 3 or more - *Norm*, *Mean* (one new signal from all). 2N signals that split into two
groups of N by name (`pos[0..2]` and `nav_pos[0..2]`, `x/y/z` suffixes too) - *Difference per pair*:
the pairs shown before making them (a small dialog: left / right / result name, a pair can be
unticked or swapped), paired by the index in the name, never by click order. The results go into one
group (`pos − nav_pos [0..2]`) and the next menu on them offers *Norm*. Link operations (`linkEdits`)
applies as for the quick operations now.
**Done when:** unit: the pairing of `pos[0..2]` / `nav_pos[0..2]`, of `a_x a_y a_z` / `b_x b_y b_z`,
and a selection that does not split (no pair offered); e2e: select 6, *Difference per pair*, 3 new
signals, *Norm* on them, one more.

### Q128 · The same formula for the other indices — S/M
**Now:** a formula made on `pos[0] - nav_pos[0]` must be typed again for `[1]` and `[2]`.
**Do:** after a formula (or an operation) is made whose sources carry an index (`[k]`, `_k`, a
trailing `x/y/z`), a toast offers *Also for [1], [2]* - the same definition with every source's
index replaced, for the indices that exist for **every** source; the names follow. The same item in
the derived signal's menu (*Make for the other indices…*). Peers / Link operations are not involved.
**Done when:** unit: the index substitution (several sources, nested derived, a source without an
index left as is, an index missing in one source - not offered); e2e: the toast makes two more.

### Q129 · Explore: type a value, not only slide — S
**Now:** ExploreView.tsx has `type="range"` only: a parameter's limits, an objective's threshold, a
condition's value (and the weight). The value is shown (`fmtValue`) but cannot be edited; a
condition's slider is bounded by `extent()` of what was measured, so *what if the limit were 0.5*
cannot be asked when every result is above 0.8.
**Do:** each shown value becomes an editable number field (click → field, Enter / blur commits,
Esc cancels, the slider follows; arrows step, Shift + arrows step ×10). A typed value outside the
data's range is kept (the slider pins at its end and says *outside the results*). The weight stays a
slider (0–10). Same in Goals where a value has only a slider. This is the small fix; the table view
of the whole problem is MF01 (docs/dev/SWEEPS_MODEFRONTIER.md).
**Done when:** e2e: type a condition value below every result - the count of holding sets updates
and the field keeps the value; Esc restores it.

## Owner's notes (2026-11-01, 3): Q130–Q138 - investigating ordinary signals (what changed first, and more)

**Owner:** "I used *What changed first* today and it was tiring. Show the signals near each other that
change at about the same time; a plot of each group right beside it; the more likely ones first. Any
more ideas for investigating? Specify and queue them - after the current Sweeps tasks."

**Now (read before starting):** `svcore/firstchange.py` - per signal its first change (k × the
baseline's noise, `persist` samples) and `lag` (cross-correlation) between two; `WhatChanged.tsx` - a
ranked list in time order, groups only when the sample rates cannot tell signals apart, a small
spark per row, the same signal in the other open files under each, a lag between two picked rows.
What tires: a flight log gives hundreds of rows; changes a few ms apart sit in different places of
the list; to see them together one builds a plot by hand; "earlier" is the only order.

**Progress:** Q130-Q134 done 2026-11-01. Next: Q135-Q137.

### Q130 · Changes that happen together, as clusters — M
**Do:** after `first_change` for every signal, cluster the change times (1-D, gap-based: a new cluster
when the gap to the previous change is more than max(3 × the coarser sample period, a fraction of the
span); each cluster: its time range, its signals, its first signal). The list shows clusters in time
order, closed to one line each (time, n signals, the 3 most likely names), opened on click. A signal
that changes in the reference runs too (the other open files, already computed) is kept but marked
and sorted last in its cluster. The backend returns clusters (`/api/firstchange` gains `clusters`),
the page does not recompute them.
**Done when:** pytest: synthetic signals with changes at 1.00/1.01/1.02 s and 2.5 s → two clusters;
e2e: a flight example's event → clusters, each opens with its signals.

### Q131 · The more likely first — M
**Do:** a score per candidate, shown with its parts (no black box): how strong the change is (×
noise), how long before the event it starts (earlier in the window = more likely a cause, but a
change after the event's start is a consequence), how long it stays changed (a blip vs a step), not
seen in the reference runs, how well its shape matches the event signal (`lag`'s correlation and a
positive lead), and whether other signals in later clusters follow it (it leads a chain). Clusters
ordered by their best member's score (option: by time); within a cluster by score. A "why" tooltip
lists the parts. Weights in one place (`firstchange.py`), tested on cases where the answer is known.
**Done when:** pytest: a step that leads the event signal by 0.5 s scores above a larger blip after the
event and above a change the reference run also has.

### Q132 · A plot beside each cluster — S/M
**Do:** each opened cluster has a compact plot right there (not a new tab): its signals normalised
(each to its baseline: (y - mean) / noise, so different units share one axis), the event span shaded,
a tick at each signal's change time, hover = name and value. *Open as a tab* makes the full plot
(today's way); *Add to the investigation* records it in the journal. Rows' sparks stay.
**Done when:** e2e: open a cluster → a plot with as many lines as its signals; *Open as a tab* → a tab
with those signals and the span.

### Q133 · Less to wade through — S
**Do:** signals that cannot tell anything are left out by default, with a count and *show them*:
constant in the window, a counter or a clock (monotonic with a constant step: time-stamps, sequence
numbers), a heartbeat (periodic with no change of period). Names grouped by their message / prefix
(ATT.*, RCOU.*) with the group's best score, closed. Keyboard: ↑ ↓ through clusters, → opens, Enter
plots. The scope and baseline defaults stay (the file of the event).
**Done when:** pytest: counter / time-stamp / constant detection; e2e: a .bin event hides the time
columns and counts them.

### Q134 · Who leads whom - a small chain — M
**Do:** among the clusters' best members, the lag of each pair (existing `lag`, bounded) → a small
directed graph in time order: A → B (+0.30 s, correlation 0.8); an edge only when the lag is clear
(no near-equal second peak) and positive. Shown above the clusters, a click on a node opens its
cluster. Words: "leads", never "causes".

### Q135 · What is different in this run — M
**Do:** with several runs of the same kind open (or a Runs folder / fleet), for the event's span (aligned
by a condition or by phase), each signal's distance from the other runs' envelope (svcore/envelope.py:
median and the 5-95 % band) → a ranking "most unlike the others here". Complements Q131: a signal can
change first and still be normal for this manoeuvre.

### Q136 · The same event elsewhere: a consistent precursor — M
**Do:** when the event is a condition with several occurrences (in this file or across files), run Q130
/ Q131 on each occurrence and rank signals by how OFTEN they change before it, and with what lead
(median, spread). "Changes first in 7 of 8 occurrences, 0.4 s before (0.2-0.6)" is strong evidence; a
signal that does it once is not.

### Q137 · The investigation in the report — S
**Do:** the chosen clusters, their plots, the chain (Q134) and the consistency (Q136) into the
investigation report with the window, baseline, k and the files - reproducible from the journal.

### Q138 · Ideas to weigh later (not queued)
- Change-point detection per signal (PELT / binary segmentation on mean and variance) instead of one
  threshold - finds a slow drift's start; heavier, needs a licence check if not written here.
- Frequency changes: a signal whose spectrum changes (vibration, an oscillation starting) while its
  level does not - a short-time spectrum before / in the span.
- A "normal" model per signal from the healthy runs (MF04's surrogates over time) and the residual as
  the anomaly - ties Sweeps' models to Recordings.

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
| Q30 | T24 Favourite folders and quick open (Ctrl+P) | S | ☑ done (with Q30+) |
| Q31 | T23 Notes over a time range (shaded span), listed in reports | M | ☑ done 2026-10-20 (see the 1.8.0 plan) |
| Q32 | T25 Sim-vs-flight error signal with RMS per segment | M | ☑ done 2026-10-20 (see the 1.8.0 plan) |
| Q33 | T14c Envelope plot zoom linked with the tab's time plots | S | ☑ done (with Q56, 2026-10-19) |
| Q34 | T18 Settings dialog (language, theme, map layer, live defaults) | M | ☑ done 2026-10-20 (see the 1.8.0 plan) |
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
| Q40 | F17 Plot options menu (⋯) does not close on Esc / click outside | S | ☑ done |
| Q41 | F18 File dialog: Esc does nothing at first, Tab leaves the dialog | S | ☑ done |
| Q42 | F19 Opening a file that is already open adds a silent second copy | S | ☑ done |
| Q43 | F20 Several files opened at once: smart start suggests a one-file view; one toast per file | S | ☑ done |
| Q44 | F21 File dialog: Shift+click is not a range; one "last folder" for every dialog | S | ☑ done |
| Q52 | F22 Many tabs: the hidden tabs cannot be reached (owner) | S | ☑ done |
| **P2** | **Usability (1.7.0, with Q30-Q34)** | | |
| Q30+ | T24 (extended) Places in the file dialog: recent folders, favourites, folders of open files | S→M | ☑ done |
| Q45 | T46 File identity: every file has a colour + short tag, used everywhere | M | ☑ done |
| Q46 | T47 Signals with different units in one plot: a second value axis | M | ☑ done |
| Q47 | T48 First impression: examples open ready, one-click template chips | S | ☑ done |
| Q48 | T49 Duplicate and unclear controls (list below) | M | ◐ part 1 done (1, 3, 5, 6, 8, 11) |
| Q49 | T50 Small windows and crowded headers | S | ◐ mostly done |
| Q50 | T51 Built-in templates and their tabs in Hebrew | S | ☑ done |
| Q51 | T52 e2e "fresh user" test (empty home folder) | S | ☑ done |

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

## Review 2026-10-19 (after 1.7.0) - toward 1.8.0 and wide use

Made by running 1.7.0 from source in a browser (1440x900 and 1024x700, English and Hebrew, the
four examples, every menu reachable from the plots and the file list) and reading the code behind
what looked wrong. Not covered: 3D, Live MAVLink, Fleet, the reports' content, Windows-only items.
**Owner approved (2026-10-19):** T49 items 2, 4, 7, 9, 12, 13 and Q31-Q34; this order, ranked by
what brings the app into use; update this table after every step.

| # | Task | Size | Status |
|---|---|---|---|
| Q53 | F23 Statistics cache returns another signal's numbers | S | ☑ done |
| Q54 | T53 Release assets: the installer and a zip on GitHub Releases | S | ☑ done (CI green, 2026-10-20) |
| Q55 | T54 Open files from outside: paths on the command line, file associations, one instance | S→M | ☑ done (installer part: owner checks on Windows) |
| Q24 | T43 Signed installers (owner: certificate) | M | ☐ |
| Q56 | F24 Linked time plots not lined up (value-axis width; spectrogram range) + Q33 (T14c) | M | ☑ done |
| Q57 | T49 items 9 + 12 (mode bar on the active plot; plot right-click menu) + F25 menus clipped by the plot card | S→M | ☑ done |
| Q58 | T49 items 2 + 13 (File menu; Help in the top bar) + F26 the shortcuts dialog describes the wheel wrongly | S | ☑ done |
| Q59 | F27 Mouse wheel: trackpads zoom far too fast, a sideways swipe zooms out | S | ☑ done |
| Q60 | T55 A short user guide and a 3-minute tour | M | ◐ guide done; the tour video: owner |
| Q61 | T56 `pip install signalviewer` (PyPI package, `signalviewer` command) | M | ◐ built + checked in CI; publishing: owner sets up PyPI once |
| Q34 | T18 Settings dialog + F28 one time format (timeline m:ss vs axes seconds) | M | ☑ done (+ F30 found on the way) |
| Q62 | T49 items 4 + 7 (reload in four places; one way to change a signal in place) | S→M | ☑ done |
| Q31 | T23 Notes over a time range | M | ☑ done |
| Q32 | T25 Sim-vs-flight error signal | M | ☑ done |
| Q63 | F29 Small: untranslated / mistranslated labels, value precision, autosave backup | S | ☑ done |
| Q64 | Release 1.8.0 (see "Releasing") | S | ◐ prepared; owner pushes and tags v1.8.0 |

Still open from Q48: item 10 (cursor buttons "T" / "H") - not in the owner's list; decide later.

### Q53 · F23 Statistics cache returns another signal's numbers — S
**Seen:** `svcore/ops.py` `compute_signal_stats` caches by `(id(time), id(data), len, t0, t1)`.
CPython reuses the address of a freed array for the next one of the same size: 200 calls with new
arrays of the same length and different values gave **193 stale results**. Every caller that makes
arrays on the fly is hit: `/api/stats` with a state filter (`t[m]`, `y[m]` per signal - two signals
of one file show the same numbers), reports with scale / offset (`ys` per signal), Compare's
windowed arrays, and a file reloaded with the same length.
**Steps:** key the cache by something that cannot be reused: the arrays themselves held in the key
(identity is then safe while the entry lives) - or drop the cache for temporary arrays. Measure
that the panels stay fast on the 5 M-row benchmark file.
**Done when:** a unit test with fresh same-length arrays gets fresh results; an API test: state-
filtered statistics of two signals of one file differ; backend green.

### Q54 · T53 Release assets — S
**Seen:** the GitHub Releases carry only `.7z` portables (download counts 0-2); Windows 10 cannot
open .7z without 7-Zip; `build.bat installer` (Inno Setup) is not built by the workflow.
**Steps:** the workflow's Windows job also builds `SignalViewer-Setup-X.Y.Z.exe` (Inno Setup on
the runner) and a `.zip` of the portable folder; both attached to the release next to the .7z;
README "Download" names what to pick (installer for most users).
**Done when:** a manual workflow run produces the three Windows files; the release page lists them.

### Q55 · T54 Open files from outside — S→M
**Seen:** `run.py` takes no file paths (`SignalViewer flight.bin` fails), the installer registers no
file types, and a second start is a second app: both write `autosave.json`, the second's
`push.json` token replaces the first's.
**Steps:** paths on the command line open in the window; a second start hands its paths to the
running app (a small local request with the push token) and exits; the installer offers "Open
.bin / .tlog / .ulg / .mcap / .mat / .csv … with Signal Viewer" (Open with, not forced default).
**Done when:** backend tests for the hand-over; e2e opening with a path; installer checked by owner.

### Q56 · F24 Linked time plots not lined up — M
**Seen:** with Link X the plots of a column start at different x: the value axis is as wide as
its labels ("75" + unit vs "3000"). Vibration tab of the ArduPilot example: 22 px between plots;
the spectrogram's time axis also covers another range (30-230 s vs 10-245 s).
**Steps:** one value-axis width per column of a tab (the widest), right axis too; the spectrogram
uses the linked time range (empty where no window fits). Q33 (Envelope zoom linked) in the same pass.
**Done when:** e2e: the plot areas of a linked column have the same left and width.

### Q57 · T49 9 + 12, F25 — S→M
**Seen:** at 1024x700 a 3-plot tab leaves ~60 px of curve per plot (mode bar + legend). The ⋯ menu
is inside the plot card (`overflow: hidden`): *Axis limits* and *Clear plot* are cut off in short
plots. **Steps:** menus in a portal (all of them); the mode bar on the active plot only (or one
dropdown); a right-click menu on the plot area (cursor here, two cursors, note here, zoom back /
reset, axis limits, save image).

### Q58 · T49 2 + 13, F26 — S
**Seen:** the shortcuts dialog says "Ctrl / Alt + wheel: values only / time only" and "Double-click:
the whole time range"; the code: Shift = values, Ctrl = both, Alt = time; double-click resets both.
**Steps:** File menu (Q48 item 2); Help menu (shortcuts, copy error details, examples, guide, about
/ version); fix the two lines in both languages.

### Q59 · F27 Mouse wheel — S
**Seen:** `TimeChart.tsx` zooms by a fixed 0.8 / 1.25 per wheel event whatever `deltaY` is: a
trackpad sends dozens of events per gesture; `deltaY = 0` (sideways swipe) zooms out.
**Steps:** factor from `deltaY` (and `deltaMode`), ignore `deltaY = 0`; same in the other charts.

### Q63 · F29 Small — S
~~"Inspector" aria-label not translated; "Theme" is "נושא" in Hebrew~~ (done in Q58); the same value
with different digits in the legend chip and the Inspector; an unreadable `autosave.json` is
overwritten by the next autosave (keep it as `.bak`); the Python push client (`push_client.py`)
uses the system proxy settings for 127.0.0.1 - bypass them as `app/instance.py` does (found in Q55);
two apps started WITHOUT files still share `autosave.json` (last write wins; Q55 covers starts with files).

## Review 2026-10-21 (after 1.10.0) - from a tool that works to a tool people find and trust

The app is in good shape (backend 782 + 12 skipped, mypy / tsc clean, `validate` 23 / 23, the docs'
commands give the documented output, the Host / Origin guard answers 403). What is missing is mostly
around it: nobody finds the repository (no About text, no topics, no social preview), nothing tests a
push or a pull request, and a newcomer has no path to report a problem or contribute.

| # | Task | Size | Status |
|---|---|---|---|
| Q80 | F37 Small fixes found in the review: `sv.load()` printed on stdout, the PyPI *Documentation* link, README (desktop extra, shallow clone, unsigned packages), stale notes | S | ☑ done |
| Q81 | T64 CI on every push and pull request (backend tests, mypy, tsc + build), badge in the README | S | ☑ done (first run on GitHub: owner) |
| Q82 | T65 `compare`: a share of samples allowed outside the tolerance (`outside_pct`, `--allow-outside`), the share written exactly | S | ☑ done |
| Q83 | T66 *Help → Report a problem…*: copies the error details and opens the issue form | S | ☑ done |
| Q84 | T67 Contributor and community files: CONTRIBUTING, issue / PR templates, CITATION.cff, SECURITY; the owner's outreach steps | S | ☑ done (owner: docs/dev/OUTREACH.md) |

Still the owner's (cannot be done from a patch): `gh repo edit` (About, homepage, topics) and the
social preview - the exact command is in `docs/dev/OUTREACH.md` (Q84); Discussions on; code signing (Q24).

### Q80 · F37 Small fixes after 1.10.0 — S
- `signalviewer.load()` let the readers' progress line (`[OK] Loaded ...`) reach stdout: in a
  notebook or `python script.py > out.csv` it is in the user's output. It now goes to stderr, as the
  command line already did (the CLI's own wrapper is gone: one way). Test: `test_load_keeps_stdout_for_the_user`.
- PyPI *Documentation* pointed at `docs/GUIDE.md` on GitHub, not the documentation site (`tools/make_pypi.py` `DOCS`).
- README: `pip install signalviewer` opens in the browser - its own window is `[desktop]` (docs/install.md
  said so, the README said "everything"); `git clone --depth 1` (the history carries every picture);
  the packages are unsigned - what Windows / macOS say on the first start and what to do (new section
  in docs/install.md, linked from the README).
- `pyproject.toml` still said e2e "one file at a time until F02 is fixed" (F02 is closed).

### Q81 · T64 CI on every push and pull request — S
`build.yml` runs only on a tag or by hand: a broken commit was found at the release, a pull request
got no check at all, and the README had no "it builds" sign. New `.github/workflows/ci.yml`: backend
pytest on 3.9 (the oldest the package allows - checked here: 783 passed) and 3.12, mypy and
`cli.py validate` once, `npm ci && npm run build` (tsc included), then a Playwright smoke run on the
UI built in that run (downloaded over the committed dist; run.py then sees it as current). The CI
badge leads the README's badges. The whole e2e suite stays the owner's before a release.

### Q82 · T65 `compare`: a share of samples allowed outside — S
Found running the sim-vs-flight example: a limit on every sample is brittle. `--align auto` without
`--align-on` picked `ATT.Pitch` (26 ms from the documented shift) and 2 FAIL became 4; `RATE.R`
failed with "0.0 % of samples outside" (0.089 %: one spike). Now a tolerance may carry
`"outside_pct"` (per signal or in `default`; `--allow-outside PCT` on the command line): a signal
passes when at most that share is outside. The share is written exactly (`app/checks.py` `_share`:
never "0.0" when samples are outside, never "100.0" when some are inside), the JSON row has
`outsidePct`, a wrong value is an error row (exit 2). Default 0: every earlier result unchanged.
docs/sim-vs-flight.md: the output line (0.089 %), why to name `--align-on` in CI, the new key.
Tests: `test_compare_share_allowed_outside`, `test_share_is_never_rounded_to_zero_or_all`.

### Q83 · T66 Help → Report a problem — S
The app has no telemetry, so a user's report is the only way to hear of a problem - and *Copy error
details* left them to find where to send it. *Help → Report a problem…* copies the same details and
opens the bug form (`issues/new?template=bug_report.yml`, Q84) in the user's browser. The backend
opens it (`POST /api/report-problem`, app/routes/system.py): the address is fixed there, never sent
by the page, and in the pywebview window a link would open inside the app or not at all. No browser
(a bare server) or a PC without internet: the toast gives the address to open elsewhere. Nothing is
sent. i18n en / he. Tests: `test_report_problem_opens_the_fixed_issue_form`; e2e: the item is in the
Help menu (not clicked - it would open the test PC's browser).

### Q84 · T67 Contributor and community files; outreach — S
A newcomer had no way in: no CONTRIBUTING, no issue forms (a report came without version, install
kind or file), no private channel for a security problem, nothing to cite. Added: `CONTRIBUTING.md`
(what helps most, setup, the checks, CLAUDE.md's rules in short), `.github/ISSUE_TEMPLATE/`
(`bug_report.yml` - the form Q83 opens: what happened, steps, install kind, file, can you share it,
error details; `feature_request.yml` - the task, not the solution; `config.yml` - docs and the
private security link), `.github/pull_request_template.md`, `SECURITY.md`, `CITATION.cff` (validated
with cffconvert; `test_citation_names_the_same_version` keeps its version with app/version.py), and
`docs/dev/OUTREACH.md` - the owner's steps (`gh repo edit` with description / homepage / topics /
Discussions, social preview, private vulnerability reporting, `good first issue`) and post drafts.

## Owner's report 2026-10-23 (after 1.12.0) - the work of one file, part by part

| # | Task | Size | Status |
|---|---|---|---|
| Q88 | T69 Copy the work to a file that is open already, each part on its own (changes / new signals / plots: same, beside each plot, new tabs, none); Clear this file ▸ (plots / changes / new signals / all) | S | ☑ done |
| Q89 | T70 Other signals in an expression of x: `sin(x) + Speed`, in place and as new signals, on one or a group | S | ☑ done |
| Q90 | T71 A signal of one particular file in an expression of x: `x + {run_b.csv:Speed [km/h]}` | S | ☑ done |
| Q91 | T72 New signals of two files belong to one of them (pinned sources); the ones with no recorded intent asked about when copying | S | ☑ done |

### Q88 · T69 The work of one file, part by part — S
Owner: "two similar files open, not linked; I work on one; then I want to copy its operations to the
other, or its plots (same plot or separate), or both; and later remove all signals of one file and/or
undo all operations of one file only". 1.12.0 had *Add a run with the same work*: a NEW file only,
everything at once, and both links turned on by default; and Clear only for everything.
- `copyWork(from, target, parts)` (sameWork.ts, was `addRunLike`): target `{ run }` (open already)
  or `{ path }` (opened as before); `parts` = edits / derived / plots ("overlay" | "beside" | "tabs" |
  "none"). "beside" (the owner, after the first proposal: "a plot next to each plot, same tab"): each
  plot that shows the file gets its copy right after it; when every plot of the tab gets one and the
  tab is one column, it becomes two (each plot and its copy side by side), otherwise fitLayout; the
  dragged sizes are reset. A tab without room (MAX_PLOTS 9) is copied as a new tab and the toast
  says so (`besideFull`).
  A derived signal that is not copied (and has no copy already) is left out of the plots quietly,
  not reported as missing; copying again adds nothing twice (existing copies are found by peers.ts).
- SameWorkDialog → *Copy the work to another file…*: open files first (an optgroup; the first is
  chosen), then the suggestions; its names checked from the loaded file; the parts as boxes, the
  plots as three radios, Link plots / Link operations as two boxes, off unless ticked (already on:
  shown on, disabled). Copy is disabled when nothing is chosen.
- clearing.ts: `fileWork(run, parts)` (what would go: the derived signals made from the file plus
  everything made from those; its edited signals; plot entries whose home is the file), `clearFileWork`
  (plots / X axes / shared states / map objects in one commit, derived deleted last-made-first, edits
  set to none; one Undo: restoreDerived + the previous specs + the workspace), `clearFileItem` (the
  file menu's *Clear this file ▸* with the numbers, disabled at 0).
Tests: e2e `test_copy_parts_of_the_work_to_an_open_file_and_clear_one_file`,
`test_copy_the_plots_beside_each_plot` (2 plots -> 2x2 side by side; 7 plots -> a tab copy); the Q87 test now ticks
the two link boxes and uses the new menu name.

### Q89 · T70 Other signals in an expression of x — S
Owner, before pushing 1.13.0: "for one signal or a group, sin(x) + Speed, Speed another signal -
maybe one of the group". Before: *Change this signal…* and *Expression in x* took x, t, pi, e only
(a signal name was explained as "use Analysis → Formula"); Formula took any signals but made ONE
signal, not one per chosen signal.
- Meaning: a name is the signal of the SAME file as x (a group: each signal's own file), read as in
  the file (raw, before any edit). So a group that includes Speed sees one Speed in all of them, no
  order and no circles between edits; and the stored text `sin(x) + {Speed}` fits any file - copied
  (Copy the work) or linked (Link operations), it reads that file's Speed.
- Backend (store.py): `transform_refs`, `apply_transform(t, y, spec, ref)` - `{Name}` -> v1.., x ->
  v0, the others interpolated onto x's time (formula.evaluate keeps v0's samples). `_ref_reader`: the
  same file's raw data; the edit's cache key already holds the file's data version. Validation runs on
  all of x when names are used (they may start after x's first 64 samples). A name the file lacks:
  400 with the name.
- Frontend: xRefs.ts `canonX(text, homes, runs)` - names (bare, or `{Two words}`) -> `{Name}`,
  checked in every target's file (case-insensitive when unique), functions / x / t / pi / e /
  param("...") / 1e5 left alone; errors: unknown (with did you mean), missing in some files (named),
  a signal made from several files has no file of its own. `sharedSignalOptions`: the names every
  target's file has, suggested while typing. TransformDialog and AnalysisPanel (Expression in x) use
  it; for new signals the names become sources (`derivedCall` returns them: x -> v0, {Name} -> v1..),
  so copies for other files map them by name as any source. The old "only x" message is gone.
- ExprInput: no suggestions while a number is typed (`x*8`: with signals now suggested, "8" matched
  `g0.s008` and the list covered the Apply button - found by the full e2e run).
  test_transform_expression_autocomplete_and_checks: `RPM * 2` is now accepted, `Nope * 2` explained.
Tests: backend `test_change_with_other_signals_of_the_same_file`; e2e
`test_expression_of_x_with_other_signals` (a group in place incl. Speed, copied to run_b with run_b's
Speed, new signals x - Speed, an unknown name).

### Q90 · T71 A signal of one particular file in an expression of x — S
Owner, after applying Q89: "two files, x + {Speed [km/h]} - both have it; let me choose one file, or
each signal takes its own". Reproduced first (API and browser): `{Speed [km/h]}` already took each
file's own (fa 105 + 5, fb 205 + 10); missing: one file for all; and `Speed [km/h]` without braces
said "did you mean Speed [km/h]?" without the braces that make it work.
- `{file:Name}` (the file as the file list shows it - fileLabel - or its file name; the same form as
  Formula's): xRefs `canonX` stores it as `{@<run id>:Name}` - run ids survive a saved session
  (api.restore keeps them) and Replace the input files - and `displayX` shows it back as
  `{file:Name}` (describeTransform, the dialog when it reopens a change, a new signal's label).
  Suggestions add every open file's signals as `{file:Name}`.
- Backend: `ref_run(token)`; `_ref_reader` reads `{@id:Name}` from that file; `_ref_versions` - the
  other files' data versions - is in the edit's cache key and in `version()`, so a reload of that
  file (live mode) recomputes the edit and everything made from it. That file closed: KeyError
  (like a derived signal whose source file was closed - the signal is not shown, nothing made up).
- Create signals → Expression in x: `{@id:Name}` is a source from that file (no file of x's own is
  needed for it). Copy the work / Link operations copy an in-place edit as it is (still that file);
  a NEW signal that reads two files belongs to neither, so it is not copied (as Compare's Δ).
- The "did you mean" for a name with spaces or brackets gives it in braces.
Tests: backend `test_change_with_a_signal_of_another_file`; e2e `test_expression_with_a_signal_of_one_file`.

### Q91 · T72 New signals of two files belong to one of them — S
Owner, on Q90's note "a new signal that reads two files belongs to neither, so it is not copied":
"important for analyses - fix it first". What was missing is the INTENT: which source is fixed and
which follows the file.
- Recorded at creation, in the signal's own params (stored and restored like any parameter; the
  server computes with the others and ignores it): `pinned` = indexes of the sources to KEEP when
  the signal is made for another file. Expression in x: the `{file:Name}` sources; Formula
  (formulaRefs `resolveFormula` -> `pinned`): names written `{file:name}`; Compare *Plot differences*:
  the baseline (`sub(run, base)`, `pinned: [1]`; a mean baseline is pinned the same way).
- peers.ts `pinnedOf`: `homeRun` looks at the other sources only (so `x - {run_b:Speed}` on run_a's
  RPM belongs to run_a; a Δ to its run); `mapTo` / `copyDerived` keep the pinned sources. So Copy the
  work, Link operations (`linkNewDerived`), Link plots (`peersOf`) and Clear this file (`fileWork`)
  all handle such a signal as one of that file's - no code of theirs changed.
- No intent recorded (made before 1.13, or a Formula whose plain names fell in two files): `crossFileOf`
  lists the signals with no file of their own and a free source of the copied file; SameWorkDialog
  shows them under "Signals made from this file and another", each ticked; copyWork `parts.cross`
  makes each for the target with the copied file's sources swapped and the others KEPT - and records
  that as `pinned`, so the copy belongs to the new file from then on. Placed in the plots like the
  others (`counterpart` looks in `made` first).
- Older sessions: no `pinned` - as before (asked about when copying).
Test: e2e `test_signals_of_two_files_copied_to_a_new_run` (a Compare Δ of run_b -> run_c against the
same baseline; `x - {run_b.csv:Speed}` of run_a -> run_c with run_b kept; an old cross-file signal
asked about from both files - unticked once, ticked once, made with `pinned`; Clear this file on
run_c deletes exactly the three copies).


## Owner's report 2026-10-25 (after 1.13.0) - big logs, live map, cache, typed signal choice

| # | Task | Size | Status |
|---|---|---|---|
| Q92 | T73 A 1.2 GB ArduPilot .bin froze while opening; reopening a big log reads it from scratch | M | ☑ done |
| Q93 | F40 "Failed to fetch" after refreshing (browser mode): the server stopped itself | S | ☑ done |
| Q94 | F41 Refresh / live did not move the object on the map / in 3D | S | ☑ done |
| Q95 | F42 Where is the cache, how to clear it - it was never cleaned | S | ☑ done |
| Q96 | F43 The Windows package opens in the browser every time | S | ☑ done (not checked on Windows here) |
| Q97 | F44 Signals chosen by typing, with their unit and ƒ beside them; unit conversions | S | ☑ done |


## Review 2026-10-28 (after 1.15.0) - Investigate fixes, and when the file was saved (1.16.0)

| # | Task | Size | Status |
|---|---|---|---|
| Q122 | Review fixes: What changed first's baseline inside the data (+ "no room" message), exponent numbers in conditions / formulas, a state dropping shown ↓, Hebrew in What changed first, "1 stretch" | S | ☑ done |
| Q123 | Owner (a user pressed F5 and could not tell whether the file was read again - the changes were small): the time the version on screen was saved to the disk on each file row (tooltip: read at), amber ↻ when the file on the disk is newer (stat poll every 3 s, click / F5 reads it), a message per file that replaces the last one. (Change marks - fingerprints of every signal, dots on the signals that changed, ↻ / ✓ of the last refresh - were tried and dropped by the owner: too much for the need, and live mode has its own green dot.) | S | ☑ done |

Q123 notes: describe() sends `fileTime` (lr.stat mtime - the version read) and `readAt`
(LoadedRun.read_at: open, reload, live appends, pushed data). `store.newer_on_disk()` /
GET /api/runs/newer-on-disk: a stat per open file against lr.stat (copies and pushed data left out).
UI: `fileTimes.ts` (texts, `watchNewerOnDisk` - every 3 s, not in live mode or while the window is
hidden; `ui.newerOnDisk`, UI only), DataPanel `.run-ftime`, toasts carry a `key` (the next of that key
replaces it) and keep line breaks.

Q122 notes: `firstchange.fit_baseline` (the default baseline only; one the user gives is kept) per
signal in `store.first_changes` and `suggest_condition`; the route returns the baseline most signals
used and `noRoom` when every signal had nothing before the span. The bare-name regex in
`svcore/conditions.py` and `formulaRefs.ts` skips a name right after a digit or a point (`xRefs.ts`
and `formulaHelp.ts` already did). Plurals: separate `…One` keys, as elsewhere in i18n.ts.

## Owner's report 2026-10-26 (after 1.14.0) - blank window offline, time axis while working

| # | Task | Size | Status |
|---|---|---|---|
| Q98 | F45 A blank white window on one computer (old offline WebView2): build for Chromium 87 / Firefox 78, polyfills, version check + Edge/Chrome app window / Firefox / message box, boot guard in index.html, safe graphics, engine in About | M | ☑ done (not checked on Windows here) |
| Q99 | T74 Time axis…: another column as the time, its unit (conversions / any scale, own-time columns), the offset - with checks, what changes, linked files, Undo | M | ☑ done |
| Q100 | Idea (owner asked, not now): `rich` for the CLI's tables / progress - only as an optional extra, plain output when not a terminal, `--json` untouched | S | ☐ open |
| Q101 | Map object position from ECEF / NED / ENU (reference: first sample of signals, or typed) | M | ☑ done |
| Q102 | Vector smoothing over a window in seconds (`vecsmooth`): Create signals and the object dialog | M | ☑ done |
| Q103 | Object dialog: say that quaternions and a display-only angle unit exist | S | ☑ done |
| Q104 | Investigation spec step 1 - state lanes: name off the data (gutter), lane tooltip, scope (plot / tab / all tabs) from the lane, chip and signal list, Remove, "always as a state" by name | S | ☑ done |
| Q105 | Investigation spec step 2 - named conditions (svcore/conditions.py, /api/conditions/eval), Investigate panel (list, live-count editor, combine, hide, delete + undo, ] / [), drawn on time plots, selection bar with Find similar | M | ☑ done |
| Q106 | Investigation spec step 3 - occurrences table, "occ" plot (stretches together: start / end / peak), what differs inside (svcore/occurrences.py, /api/occurrences/*) | M | ☑ done |
| Q107 | Investigation spec step 4 - what changed first (svcore/firstchange.py, /api/firstchange), lag (/api/lag), WhatChanged section, dashed marks, show aligned | M | ☑ done |
| Q108 | Investigate example with a known answer (tools/make_investigation_demo.py, examples/investigate) + tutorial EN / HE (owner: "so I can check it too") | S | ☑ done |
| Q109 | Investigation spec step 5 - runs x conditions (RunsMatrix: params, counts / totals, odd cells, click to stretch, scatter + fit, folder of runs; /api/runs/params) | M | ☑ done |
| Q110 | Investigation spec step 6 - findings (note status + saved view), journal, report investigation sections (HTML / PDF / Word) with finding plots, reproduce appendix | M | ☑ done |
| Q111 | Investigation spec step 7 - the run at a glance: phases + conservative automatic flags (svcore/overview.py, /api/runs/{id}/overview), OverviewStrip | M | ☑ done |
| Q112 | Overview strip rows (state signals / conditions: add, replace, move, remove) and a combined selection (or in a row, and across rows) saved as a condition (owner, while testing) | M | ☑ done |
| Q113 | Review of the investigation (owner, 2026-10-28): Find similar on the signal most unusual in the selection (/api/condition/suggest, firstchange.selection_change); What changed first on the event's file, the other runs under each row; the strip under the plots' time axis; the selection bar on a plot made active later; Hebrew numbers / names | M | ☑ done |
| Q114 | What changed first on a long log (owner: "many groups at different times"): filter, × on rows / groups (their marks too), groups that close, measured from their first row; a steady drift judged against its own trend (firstchange: line vs curve) | M | ☑ done |
| Q115 | One into each plot (owner: true X/Y/Z beside the flight computer's): pairing.ts by the part of the names that differs, else by order; one colour for the set; the ▾ menu beside Plot them | M | ☑ done |
| Q116 | The error per axis: errors.ts (sub, reused), /api/error-segments for RMS / max / when and the worst flight mode (1.5 x the next), an "Errors" tab, the cursor on the largest | M | ☑ done |
| Q117 | A candidate (What changed first / What differs inside) opens in a plot of its own, Ctrl+click: active plot; long plot titles cut | S | ☑ done |
| Q118 | Steps so far grouped by kind (JournalStep.kind): a group ticked / closed / removed, a filter, "n of m in the report" | S | ☑ done |
| Q119 | Templates keep the conditions (Template.conditions, merged by name on apply, counted in the message) | S | ☑ done |
| Q120 | Open: a click on a strip flag also shows the flagged signal (it zooms there, the signal may be on no plot) | S | ☐ open |
| Q121 | Open: the stretches table offers any signal of the file, not only the condition's (the tutorial's step 7 asks for Motor3) | S | ☐ open |

Q98 notes: `vite.config.ts` build.target and run.py `MIN_CHROMIUM` / `MIN_FIREFOX` must name the same
engine (test_launcher checks). The WebView2 runtime is NOT bundled (owner's decision: a better
fallback and a message instead). Safe graphics adds `--disable-gpu --enable-unsafe-swiftshader` (the
page is only the app's own, from 127.0.0.1).
Q99 notes: `svcore/time_axis.py`; the scales live in `import_settings` (`time_scale`,
`own_time_scale`), applied in `store.open_file` after any loader (and to rows appended live), so
refresh / sessions / live read them alike. `store.set_time_axis` reads the file again in place
(`_read_again`, shared with reload); `before` is in file names, so Undo finds an old time column that
is a signal now (perhaps renamed `Time_2`). Positions map by row only with one data file open and no
re-sorting. CLI flags not added (each command would need them; the Python API takes the settings).

### Q92 · T73 Very large ArduPilot logs — M
- bin_loader: the file memory-mapped; headers found in 64 MB blocks on several threads (`_find_heads`);
  the FMT messages taken from the same pass; the chain of messages walked run by run (only the breaks
  looked up - the old pointer doubling ran again from every damaged block); no padded copy for decoding.
- Above `LAZY_MIN` (64 MB, `SV_BIN_LAZY_MB`): numeric fields are `LazyField`s (positions in time order,
  uint32 under 4 GB) and the run's signals `LazySignal`s (models.py) read on first use within
  `LAZY_BUDGET` (`SV_LAZY_MB`, LRU, re-read after eviction); a rewritten file raises "refresh it" instead
  of reading other bytes. Exact float32 / small-integer fields stay float32 (`COMPACT_MIN`). Live append
  extends the lazy fields. describe leaves `discrete` to on-demand for values not read yet.
- Index cache: time vectors + positions + the DataFlash state in `cache/bin-<key>` (size, mtime,
  fingerprint), memory-mapped on reopen; written in the background, only for a log quiet 60 s.
- Checked against the 1.13.0 reader value by value (eager / lazy, 1 / 4 threads, a real log, damaged
  blocks): identical. 1.2 GB synthetic: open 7 s / 0.46 GB kept (was ~13 GB needed), reopen 0.03 s.

### Q93 · F40 The browser-mode server stopping — S
- A background tab pings about once a minute (timer throttling): the 30 s limit stopped the server.
  Now any request counts (main.py middleware → `seen_page`), `/api/bye` on pagehide, `IDLE_LIMIT` 5 min,
  `BYE_LIMIT` 75 s, never while a job runs. "Failed to fetch" becomes a message saying the server stopped.
- Refresh of one file is a job (`reload`) with progress; refresh all reports each file's progress.

### Q94 · F41 Live / refresh on the map — S
- `actions.pinTimeToEnd`: a cursor at the old end moves to the new one (live poll, refresh, reload;
  forced when live starts); `trackTime`: in live mode a time past a track's end holds its last state.

### Q95 · F42 The cache — S
- csv_loader `prune_cache` (older copy of the same source, `SV_CACHE_DAYS`, `SV_CACHE_MAX_GB`, never an
  entry in use - `CACHE_IN_USE` from app/storage.py), uploads older than 7 days at start, Settings → Disk
  space used (`/api/storage`, `/api/storage/clear`), `signalviewer-cli cache [--clear …]`.
- Leaks found on the way: `is_discrete` keyed by version (one entry per signal per live update), the FFT
  cache (33 full spectra; now 256 MB and the newest version only), two polls that overlapped.

### Q96 · F43 Native window on Windows — S
- run.py `window_unavailable_reason`: removes the Zone.Identifier mark of the app's own DLLs (pythonnet,
  WebView2 loader), finds WebView2 by its folders too, and when it still falls back says why in the page
  (`/api/window_note`) and the log. Not checked on Windows here.

### Q97 · F44 Typed signal choice; unit conversions — S
- SignalField (SignalPicker over every open file + unit + ƒ → the change dialog for that signal) in the
  map object dialog, Place on the map, error segments. Esc closes only the dialog on top (Overlays stack).
- units.ts `CONVERSIONS`, `conversionsFrom`, `signalUnit`; the change dialog's *Convert units* and *Unit
  shown*; transforms carry `unit` (store `normalize_transform`; a unit alone does not recompute values).
- tools/live_demo.py: an aircraft and a ship written to two growing CSV files.

## Owner's report 2026-10-22 (after 1.11.0) - several signals at once

| # | Task | Size | Status |
|---|---|---|---|
| Q85 | F38 Several signals at once: groups closed while searching, one action on all selected signals (x = each), a new selection without removing one by one | S | ☑ done |
| Q86 | F39 Shift ranges that add up (1-3, then 7-11), Shift + drag | S | ☑ done |
| Q87 | T68 One piece of work for many runs: *Add a run with the same work* (same plots or new tabs), Link plots and Link operations each on its own | M | ☑ done |

### Q85 · F38 Several signals at once — S
The owner's three reports, and what was behind each:
1. *Nested groups cannot be closed while searching.* DataPanel forced `open = q ? true : ...` and
   ignored `closed[run]` while `q` was set. Now a separate map `sClosed` (`r:<run>` / `g:<run>|<group>`)
   holds what the user closed during a search - every match still starts open - and is dropped when
   the search is cleared. *Collapse all* / *Expand all* in the results bar (after *Choose these N only*:
   e2e clicks the bar's first link).
2. *"Apply to 1" - x cannot stand for several signals.* The file list's right-click *Change this
   signal…* always sent `[sig.id]`, even with that signal in a selection. A right-click on a selected
   signal (2 or more) now opens a menu for the selection: plot / each in a new plot / *Change the N
   selected…* / *New signals from the N selected ▸* (createSignalItem takes an array; quick results
   added in one undo step) / clear. The same in the legend (`multi`), and the Inspector's batch section
   now seeds *Create signals* (it opened it empty) and has *Change them…*. TransformDialog lists the
   targets as removable chips and says that x is each target in turn; *Apply to 1 variable* (singular).
   Analysis → One signal: *Expression in x…* (`exprx`): new signals through the existing `expr`
   operation with x → v0 (one per source, label with the signal's name); in place through
   `opToStep` → `composeTransform` (stacks on an earlier change like every step).
3. *A new selection meant removing the old one signal by signal.* `listSelUsed` (ui slice): set by
   every action on the selection (change, plot, quick ops, Analysis on several); the next Ctrl / Shift
   + click or checkbox starts a new selection - the selection stays for a chained action meanwhile
   (hint under the bar). MultiSignalPicker `stale` does the same in Analysis. Esc clears (list, search
   box); *Clear selection* is a named button. A group's checkbox (indeterminate when some) and
   Ctrl+click on the group select it whole.
i18n en / he. Test: e2e `test_multi_select_search_collapse_and_x_on_each`.

### Q86 · F39 Shift ranges that add up; Shift + drag — S
Owner, after applying Q85: "hold Shift, click 1 and 3, let go; hold Shift on 7, click 11 - I want
1-3 and 7-11"; and Shift + drag did nothing. Reproduced in Playwright: the second range ran from the
first anchor (1-11: `listAnchor` never moved on a Shift+click, and a Shift+click replaced the
selection unless Ctrl was held too); a Shift + drag started the row's native drag (it is `draggable`
to drop on a plot), so no click came at all.
Now the range is made on **mousedown** with Shift (`preventDefault`: no native drag, no text
selection); hovering other rows with the button held extends it (`onMouseEnter`), and near the top or
bottom of the list the list scrolls. A **new press of Shift** (keyup, or a mousemove without Shift -
also when the window missed the key) starts a new range at the signal pressed, ADDED to the selection
(`span.base` = what was selected before it, so the range can still grow or shrink while Shift is
held). A Ctrl+click just before is the start of the next Shift range (the classic way, kept).
After an action (`listSelUsed`) the range starts a new selection. The checkboxes behave the same.
Shift+Enter from the keyboard works as a Shift+click. Hint and tooltip say it (en / he).
Test: e2e `test_shift_ranges_add_up_and_shift_drag`.

### Q87 · T68 One piece of work for many runs — M
Owner: "I worked on a run (changes on signals, new signals, plots); now a similar simulation should
get the same - in separate tabs or on top of the first to compare, then a third, a fourth"; and once
two runs are there, "link plots and link operations separately". What existed: *Replace the input
files* keeps everything but SWAPS the files; a template keeps the layout but drops edits (ƒ) and
derived signals on purpose; *Link files* worked only for adds and removes of same-named data signals.
- `peers.ts` - one meaning of "the same signal in another file": a data signal by name; a derived
  signal by its operation + parameters (not the label) with its sources mapped to one other file
  (`homeRun`, `mapTo`, `peersOf`, `findDerived`). `copyDerived` makes a derived signal for another
  file, its derived sources first (name: "name (run_b)").
- **Link operations** (`linkEdits`, view slice, saved in the session's `ui` - optional, older
  sessions stay unlinked): `applyTransform` / `editInPlace` widen their targets with `withEditPeers`
  (each composes on its own edit; the Undo covers all); Analysis (every kind) and *Create signal ▸*
  call `linkNewDerived` after making a signal - skipping jobs whose signal a linked one already made
  (Speed of run_a and run_b both chosen); with Link plots on, the copies join the original's plots
  (`addBeside`). TransformDialog says how many more signals a linked change reaches.
- **Link plots** (the former Link files, `linkRuns`, same `.link-toggle`): `addSignalLinked` /
  `removeSignal` use `peersOf` - derived signals now follow too. Label "Link plots" (e2e updated).
- **Add a run with the same work…** (a file's right-click; `sameWork.ts`, `SameWorkDialog`):
  suggests the newest file with the same name pattern (as Replace), checks the names the work uses
  (`usedNames`: plots, X axes, states, map objects, edits, formula sources), opens it with the
  original's import settings, copies the edits, makes the derived signals in creation order (derived
  of derived through `copyDerived`), then either adds each counterpart beside its original in every
  plot (overlay; drawn like it, own colour) or copies every tab that uses the file (`"<tab> · run_b"`,
  new ids, its signals swapped, others kept). Missing names are listed in the toast. Default: also
  turn both links on. Not linked by design: Compare's Δ / mean signals (they span files) and frames
  made in Analysis → Frames (several outputs at once; Add a run copies them).
Test: e2e `test_linked_operations_and_a_run_with_the_same_work` (run_b on the same plots, linked
change / new signal / add, plots unlinked with operations linked, run_c in new tabs).

## Owner's review 2026-10-20 (after applying Q65-Q73)

| # | Task | Size | Status |
|---|---|---|---|
| Q74 | F33 README: the Hebrew section is one run-on paragraph with struck-through text - fix it | S | ☑ done |
| Q75 | T62 `pip install signalviewer` = everything again; the light install under another name | M | ☑ done (owner: PyPI publisher for signalviewer-lite) |
| Q76 | T63 One Clear button with a menu: this tab / the other tabs / all tabs / tabs + derived signals and edits / everything | M | ☑ done (e2e written, not run here) |
| Q78 | F35 No File menu: open / save session, Clear ▾, settings and day / night as top-bar buttons | S | ☑ done (e2e updated, not run here) |
| Q79 | F36 Owner's e2e run on Windows: 192 passed, 2 failed - the tab strip too narrow at 1100 px after F35; a test's "/tmp" | S | ☑ fixed (to re-run) |
| Q77 | F34 Nothing cached is used after the data changed (owner: "make sure there is no cache that is used although the data was updated") | M | ☑ done |

### Q74 · F33 The README's Hebrew section — S
**Why:** 40 lines without blank lines are ONE paragraph in Markdown (the line breaks vanish), and
two `~` (in `~/.signalviewer/templates` and `~/.signalviewer/logs`) make GitHub strike out everything
between them - the "deleted line in the middle" the owner saw. It had also become a version history.
**Done 2026-10-20:** rewritten short, inside `<div dir="rtl">` (right to left, blank lines so the
Markdown inside renders): what it is, install (3 lines), what it does (6 bullets), the Hebrew guide
and the CHANGELOG. Commands in `<code dir="ltr">`. The release checklist no longer asks for a
"חדש ב־X.Y" line.

### Q75 · T62 Full by default, light as `signalviewer-lite` — M
**Why:** the owner prefers `pip install signalviewer` to bring everything (Q69 had made it the core).
pip cannot subtract from a package, so the light install needs its own name.
**Choice:** two distributions of the same code, `signalviewer` (every reader and report a dependency;
only `[desktop]` an extra - pywebview needs GTK / Qt on Linux; `[all]` kept, = desktop) and
`signalviewer-lite` (Q69's core + extras). Not a meta-package (`signalviewer` -> `signalviewer-core`):
upgrading 1.8 -> 1.9 would install the new distribution's files and then uninstall 1.8's - the same
paths - and break the install. The cost: installing both makes them share files; the docs say one.
**Done 2026-10-20:** `tools/make_pypi.py` `FLAVOURS`, `flavour_metadata`, `stage(name)` (build/pypi/<name>),
`build()` builds both into dist-pypi/, `--check` checks each (full: every reader module imports and
Parquet opens; lite: the hint names `signalviewer-lite[parquet]`, then `[all]` opens it) - run in a
venv with only `build`, as in CI. `svcore/extras.install_hint`: lite (its distribution is installed)
-> `signalviewer-lite[extra]`; full / source -> reinstall `signalviewer` / requirements.txt.
Docs: README, install.md, command-line.md, limitations.md, CHANGELOG.
**Owner, once before the 1.9.0 release:** PyPI -> Your account -> Publishing -> "Add a new pending
publisher": PyPI project name `signalviewer-lite`, owner `DavidAlpert11`, repository `SignalViewer`,
workflow `build.yml`, environment `pypi` (the same as `signalviewer`). The release job uploads both.

### Q76 · T63 One Clear button, a menu of scopes — M
**Why (owner):** besides "Clear everything" (File menu) a way to clear the plots and the work and keep
the data; a button with a drop-down is handier than a File menu entry.
**Done 2026-10-20:** `frontend/src/clearing.ts` - `clearMenuItems()`: this tab's plots (the existing
`clearAllPlots`), `closeOtherTabs`, `clearAllTabs` (one empty tab; zoom / ranges / selection
forgotten), `clearWork` (tabs, notes, derived signals, in-place edits; files and their time
alignment stay; ONE Undo restores the derived signals from their formulas, the edits from
`/api/transforms`' `previous`, the workspace, and bumps `dataVersion`), and `clearEverything`
(unchanged, asks). The undoable ones use the toast's Undo (`undoesWs`: it goes away at the next
change, F12) and Ctrl+Z for the workspace. The stage bar's eraser became **Clear ▾**
(aria-label "Clear"); File menu: a *Clear* submenu with the four undoable scopes, then *Clear
everything* as before; Ctrl+K: other tabs / all tabs / work. Labels count what goes (tabs,
derived signals, edits, files). i18n en + he. Guide (en + he) section 9, features.md.
**Tests:** tsc, oxlint, vite build clean. e2e: `test_T63_clear_menu_scopes` (other tabs + Undo, work
+ Undo, all tabs, the File submenu) and the helper `clear_plots` for the tests that clicked the old
eraser - **written, not run** (no browser in this sandbox): run `pytest tests/e2e` before the release.

### Q78 · F35 The top bar without a File menu — S
**Why (owner, after applying Q74-Q77):** the File menu had few entries and was handier as buttons; opening
files is in the file list already; settings, clear and day / night as three buttons look better.
**Done 2026-10-20:** `TopBar.tsx` - the File menu is gone; buttons: open session (Icon.Open) and save
session (Icon.Save) next to the brand, **Clear ▾** after Undo / Redo (all of `clearMenuItems()`, the
last one "Clear everything…", danger, asks), the settings gear (was there), a day / night button
(`theme-btn`, Sun / Moon, aria-label "Theme", `aria-pressed` in dark). The stage bar's eraser is back as
in 1.8 (this tab's plots, aria-label "Clear all plots") - T63 had turned it into the menu, which now
lives in the top bar. i18n: `menuFile`, `menuRecent` removed; "Clear everything…" names the scope.
Guide (en + he) sections 2 and 9, features.md, CHANGELOG. e2e: `test_file_and_help_menus` (no File
button; the five buttons; the Clear menu; theme toggles and back; settings opens), helpers
`clear_plots` / `clear_everything`, `test_T63_clear_menu_scopes` and test_workflows use the top-bar
Clear - **written, not run here** (no browser). tsc + oxlint clean.

### Q79 · F36 The owner's full e2e run (Windows, 2026-10-20) — S
192 passed, 2 failed (11 min):
- `test_workflows::test_every_tab_is_reachable_with_many_tabs`: at 1100 px the active tab was not in
  view. **Cause: F35** - the top bar got ~110 px more buttons (open / save session, Clear ▾, day / night
  for the File menu), and the tab strip shrank below one tab's width. **Fixed:** below 1280 px the app
  name and the language button's text hide (`.hide-compact`, ~150 px; icons stay, with a tooltip and an
  aria-label). The search box keeps its 150 px (the same test checks it).
- `test_globe3d::test_log_events_on_the_track_and_image`: saved the PNG to `$TMPDIR or "/tmp"` - no
  such folder on Windows (not an app bug). **Fixed:** `tempfile.gettempdir()`.
Both fixes untested here (no browser): re-run the two tests.
**Re-run (owner):** the tab test passes; the 3D image test still had no file in `%TEMP%`. The test
typed the folder into the address box and saved at once, waiting only for the box's own text - not
for the dialog to be in that folder. Likely: Windows' Temp lists slowly (thousands of files) and the
picture went to the folder the dialog was still in. **Changed:** a fresh folder (`mkdtemp`) given
as a full path in the name box (the dialog takes a full path as it is - `FileBrowser.confirm`); on a
miss the failure now shows the toasts (an error from `/api/save/image` would be in them).

### Q77 · F34 Stale data after a change — M
**Audit (2026-10-20)** of every cache keyed on data, and what changes the data:
- `svcore/analysis.fft_for` and `Store.is_discrete` key on `Store.version(sig)`; a derived signal's
  version was ("d", name, the sources' versions) - **without the definition**. A derived signal
  replaced under the same name and sources (`/api/derived/restore` with other parameters, a Python
  operation's file edited) kept the old spectrum and the old "discrete" answer. **Bug, fixed:**
  `DerivedDef.serial` (new per definition and per `invalidate()`), part of the version.
- Python operations: after *Reload* / another folder their signals kept their computed data (the
  sources had not changed). **Bug, fixed:** `Store.invalidate_derived("py")` from
  `/api/pyops/reload` and `/folder`; the UI then refreshes the run list.
- The UI's data effects key on `dataVersion` + a key of the run list (id, offset, samples, signal
  count). Creating a derived signal under an existing name does not bump `dataVersion`, and the key
  did not change when only values did. **Bug, fixed:** the run list carries a `version` per file
  (`uid.data_version`) and per derived signal (hash of `Store.version`); `values.runsDataKey` uses
  them in TimeChart, FFT, XY, Geo, XYZ, Globe3D, and the file list's small pictures too.
- CSV binary cache (`.npy`, files >= 50 MB): key = path, size, mtime + settings - a file copied over
  with the same size and a coarse clock (FAT: 2 s, network shares) was served from the cache.
  **Fixed:** + `st_mtime_ns` + `content_fingerprint` (first and last MB, 16 blocks between).
- Live follow (`append_new_rows`): same size and a new time stamp was "touched, not changed" when the
  bytes just before the end were the same - a value fixed early in the file (a re-save) was never
  read. **Fixed:** the fingerprint, kept after every load / append, decides; a difference reloads.
- Checked, fine: statistics cache (weak references to the arrays, F23), compare table cache (key has
  dataVersion), reload / live / F5 bump `dataVersion`, fleet index (mtime + size per log, only an
  index), sessions (formulas, recomputed).
**Tests:** `test_stale_data.py` (5) - each fails without its fix.

## Review 2026-10-20 (after 1.8.0) - from a tool that works to a tool engineers adopt

Made by reading the repo at 1.8.0, installing `signalviewer` from PyPI in a clean venv (764 MB of
site-packages, a 22 MB wheel) and using its Python API and command line on the examples.
Found: the API needs the unit in every name (`rec.signal("ATT.Roll")` fails - the CLI's own
`--help` example fails); small packaging inconsistencies; the install is heavy for a notebook
user. Direction: lean into what few tools do - compare runs, offline / closed networks, data to
report - and into test automation (pass / fail in CI); new formats only without LGPL (T40 rule).
**Order proposed to the owner (2026-10-20), ranked by what brings the app into use:**

| # | Task | Size | Status |
|---|---|---|---|
| Q65 | F31 Python API / CLI: names without the unit, "did you mean", `sv.show` | S | ☑ done |
| Q66 | F32 Packaging consistency (badge, pyproject note, PyPI metadata, README pictures on PyPI) | S | ☑ done |
| Q67 | T57 `signalviewer-cli check`: requirement checks, exit code, JUnit XML for CI | M | ☑ done (limits; settling / response checks: follow-up) |
| Q68 | T58 Golden-run regression from the command line (`compare` with tolerances) | M | ☑ done |
| Q69 | T59 Lighter pip install: optional readers / reports as extras, a clear message when one is missing | M | ☑ done |
| Q70 | T60 Reader plugins: a file format as a Python file in the user's folder (like T-operations) | M | ☑ done (UI listing: follow-up) |
| Q71 | T61 Binary ICD decoder: raw packet recordings described in a layout (own code, MIT) | L | ☑ done |
| Q72 | T40 part 2: CAN - own DBC decoder (option B, MIT) + candump / ASC / CSV CAN logs | L | ☑ done (option B; MF4 not done) |
| Q73 | T43 part: README slimmed to a front page, the full catalogue in a docs site (GitHub Pages) | M | ☑ done (owner: enable Pages once) |

Not queued, to decide: ROS 1 bags (`rosbags`, Apache-2.0); TDMS (npTDMS is LGPL - own reader or
none); the wheel tested on Python 3.9 and 3.13 in CI before claiming those versions on PyPI.

### Q65 · F31 Python API: names without the unit — S
**Why:** the first thing a script user types is `rec.signal("ATT.Roll")`; it raised KeyError
because the name is `"ATT.Roll [deg]"` - also the CLI's own `--help` example
(`--signals "ATT.Roll,ATT.Pitch"`). The UI's search forgives this; the API did not.
**Where:** `svcore/naming.py` (`without_unit`, `resolve_signal_name`, `SignalNameError`),
`signalviewer/__init__.py` (`Recording.signal`; `table` / `to_dataframe` and the CLI go through it).
Touches nothing in the app's routes (they address signals by id, CLAUDE.md invariant).
**Rules:** exact name; else the name without its unit; else either in any case; more than one hit
is an error listing them (never a guess); nothing -> the three closest names (difflib).
DataFrame / CSV columns keep the names as the user wrote them.
Also `signalviewer.show` = the push client's `show` (one implementation, re-exported).
**Status:** done 2026-10-20. Tests: `test_signal_names_without_unit_and_suggestions`,
`test_resolve_signal_name_rules` (backend 675, mypy clean).

### Q66 · F32 Packaging consistency — S
README badge says Python 3.8+, PyPI requires 3.9; the root `pyproject.toml` still says "no package
metadata yet" (it lives in `tools/make_pypi.py` since T56); PyPI page without Changelog / Issues /
Documentation links and with few keywords. Do not add per-version classifiers before CI tests them.
**Found on the way:** the README's pictures and links are relative (`docs/images/...`), so the PyPI
page shows them broken - PyPI has no repository to resolve them against.
**Status:** done 2026-10-20. `tools/make_pypi.py`: `pypi_readme()` rewrites `src=` to
raw.githubusercontent.com at the tag `v<version>` and `href=` / Markdown links to the GitHub page
at that tag (the wheel is published from the tag; a manual run's links point at a tag that may not
exist yet - harmless, it is not published); project URLs Documentation / Changelog / Issues /
Releases; more keywords and classifiers (no per-version ones). Root `pyproject.toml` note says
where the metadata lives. README badge 3.9+. Tests: `test_pypi_readme_links_are_absolute`;
`make_pypi.py --check` passes (wheel installed in a fresh venv, app started).

### Q67 · T57 `signalviewer-cli check` — M
**Why:** moves the app from "looking at a run" into the test process: a run that breaks a limit
fails the build. `svcore/limits.py` and the health check already exist - extend them.
**Idea:** a checks file (YAML/JSON: signal, condition - max / min / within / settles within X s
after an event, optional state stretch) or the checks saved in a template; `check run.bin
--checks c.yaml [--junit out.xml] [--report out.html]`; exit code 0 / 1 / 2 (pass / fail / error).
**Done when:** the example runs give a known pass / fail set; JUnit XML opens in a CI viewer.
**Status:** done 2026-10-20 for limits. `app/checks.py` (like `app/batch.py`: a Store of its own per
file): `load_checks` (JSON, validated with the check's number in the message), `template_checks`
(the template matched to the file as in batch reports; every plotted signal with `limits`, with its
scale / offset; duplicates dropped), `run_checks` (names through `resolve_signal_name`; windows:
t0 / t1, either may be left out; `during` {state, value as number or label in any case,
occurrence 1, 2.., -1 or all} via `_stretches`, which now takes the Store - default the app's;
each window through `svcore/limits.check_limits`, the worst one reported), `junit_xml`.
Statuses pass / fail / error / skipped (no stretch, no samples - never counted as a pass). CLI
`check` (exit 0 / 1 / 2, `--json`, `--junit`). JSON, not YAML: no new dependency.
Example `examples/checks.json` (run_013 fails the cruise speed, everything else passes).
Tests `test_checks.py` (4). **Follow-ups:** checks on derived signals / formulas; settling time and
overshoot after a step; the health check's findings as checks (`--health`); a button in the app
that saves the plot's limits as a checks file.

### Q68 · T58 Golden-run regression — M
`signalviewer-cli compare golden.csv new.csv [--tolerances t.yaml]`: the Compare panel's
similarity list (`svcore/compare.py`) as a table + exit code, the worst signals first.
**Status:** done 2026-10-20. `app/checks.py` `load_tolerances` (file default / per signal / skip; the
flags are the default), `run_compare` (golden + file in a Store of their own; names resolved like the
API; `svcore.compare.compare` with the golden as baseline - the same metrics and angle wrapping as
the panel; a signal passes when every sample is within min(abs, pct of |golden|), the panel's rule;
no tolerance = status "info", exit 0). CLI `compare` with `--signals`, `--top` (failures always
shown), `--json`, `--junit` (info rows = passing testcases with the numbers in system-out); output
shared with `check` (`_print_results`). Tests: 2 in `test_checks.py`. **Follow-ups:** `--auto-shift`
(svcore.compare.auto_shift) for runs that start at different moments; the same segment of each
run (T10b windows) from the command line.

### Q69 · T59 Lighter install — M
Today every reader is required (pyarrow, scipy, h5py, matplotlib, pymavlink, mcap...). Core =
CSV / Parquet viewing; extras `[mavlink] [px4] [ros] [matlab] [reports] [all]`. Needs: every
loader / report imports lazily and a missing extra says *"pip install signalviewer[ros] to open
.mcap"*; the installer and portable builds keep everything.
**Status:** done 2026-10-20. `svcore/extras.py` (EXTRAS: parquet, hdf5, mavlink, px4, ros, reports,
desktop; `missing()` = the message) is the one list: `tools/make_pypi.py` builds the package's
extras + `all` from it (and stops when it names a package requirements.txt lacks). Core = FastAPI,
numpy, pandas, scipy (filters, spectrograms, MATLAB v5 - kept: the analysis needs it). Messages in
the readers that already imported lazily (parquet, hdf5, ulog, mcap, mavlive) and new ones where a
missing package crashed or was misreported: .tlog (`_mav()` -> TLogError), MATLAB v7.3 without h5py
(was "not a valid .mat": `MatNeedsExtra` from the file's header), PDF / Word / images
(`report.ReportNeedsExtra`, 400 from /api/report; the HTML report of time plots needs neither).
The CSV reader already fell back to pandas without pyarrow. Site-packages 764 -> 346 MB.
`make_pypi.py --check` now also: the plain install opens the .bin example, a .parquet fails naming
`[parquet]`, then `[all]` opens it. Tests: `test_extras.py` (5, the modules hidden via sys.modules).
requirements.txt (source, installer, portable) unchanged.

### Q70 · T60 Reader plugins — M
A file format as a Python file in `~/.signalviewer/readers` (same model as the Python operations:
own process optional, listed with load errors). Lets users add in-house formats without a fork.
**Status:** done 2026-10-20. `svcore/readers.py` (`reader` decorator, `load_folder` - like
pyworker.load, `to_run`: one time or a tuple (time, values) per signal, unsorted time sorted, labels,
start / end over every signal; `EXAMPLE`: a key=value reader). `app/userreaders.py`: folder
(settings.json `readersDir`, default `~/.signalviewer/readers`), re-read when a .py file there is
added / removed / saved (names + mtime + size), `for_ext`, `extensions`, `listing`, `write_example`.
`Store.open_file`: the user's readers for the extension first (None = not theirs, then the built-in
reader); `check_file` lets their extensions through and skips the content sniffing for them.
`common.supported_now()` (file dialog listing, drag & drop uploads); frontend `addDataExts` at start
(`/api/readers`). Routes `/api/readers`, `/folder`, `/example`; CLI `readers [--example] [--json]`.
**Decision:** readers run in the app's process, not a worker like the operations - a reader returns
whole files (copying them through a pipe would double memory and time) and it is the user's own code
from their own folder. A hanging reader blocks only that file's opening thread.
Found on the way (Q69): MatNeedsExtra had the code "badMat", which the UI translates to "damaged" -
now "needsExtra" (no translation, the message is shown). Tests: `test_readers.py` (4).
**Follow-ups:** the readers in the UI (a list with errors, like Create signals > Python); live append
for a reader's files (today: reloaded whole).

### Q71 · T61 Binary ICD decoder — L
Many test benches record raw packets (header, id, fields with type / scale / offset / bit fields,
endianness) and every team writes its own decoder. A layout file (YAML) describes the packets;
the reader turns a recording into signals named `<packet>.<field> [unit]`. Own code, MIT.
**Status:** done 2026-10-20. `svcore/icd.py`: `parse_layout` (every item checked, the message names the
packet / field: types, offsets inside the packet and the header, bits, ids unique, several packets
need a header id), `read_layout` (JSON; YAML only when PyYAML is installed - not a new dependency),
`_frames` (sync candidates found with numpy, the walk in plain bytes - about 1.5 µs a packet,
240,000 packets in 0.36 s; fixed records without a header loop-free; resync byte by byte after a bad
id / short length; cut-off end counted), `decode` (each field for all packets at once by fancy
indexing + `view(dtype)`; bit fields; enums as labels, scale / offset_value not applied to them;
time: the packet's field x time_scale, else the header's time, else numbered and said so), EXAMPLE +
`write_example_recording`. It is a reader of T60: `app/userreaders.py` turns every `*.icd.json /
.icd.yaml` in the readers folder into one (`kind: "icd"`); `readers.to_run` keeps a reader's
`report` in the load report. CLI `readers --example-icd [recording]`. Tests: `test_icd.py` (10).
**Follow-ups:** checksums (CRC-16 / sum per packet: drop the bad ones); arrays and strings in a
payload; packets whose layout depends on a field (variants); live follow of a growing recording.

### Q72 · T40 part 2 · CAN with DBC — L (owner decides)
Option B from ROADMAP T40: an own DBC parser + decoder (MIT), CAN logs as candump / ASC / CSV;
.blf and MF4 later or never.
**Decision (2026-10-20):** the owner asked for every task of the plan to be done; option B was the
recommendation of 2026-10-18 and keeps everything MIT, so it was taken. MF4 / .blf stay undone.
**Status:** done 2026-10-20. `svcore/dbc.py`: `parse_dbc` (BO_, SG_ incl. M / m<k>, VAL_,
SIG_VALTYPE_; a line that cannot be read names its number), `frame_key` (29-bit = bit 31, as in the
file), `_raw_bits` (all frames of an id at once; Intel from the LSB, Motorola from the MSB in the
"sawtooth" numbering via its big-endian bit index; up to 8 bytes vectorized, a 9-byte span exact in
Python), `decode_signal` (two's complement, float32 / 64, factor / offset - not for value names),
`decode_message` (multiplexed signals only where the switch matches; a signal past a frame's real
length is NaN, not the zero padding). `svcore/can_loader.py`: candump log / screen output, Vector
ASC classic lines, CSV (time, id, data), the .dbc files next to the log + the readers folder (the
log's first), Unix times start at 0 (`startUnixTime` in the report), unknown ids counted.
`Store.open_file`: .asc / .log, and a .csv with id + data columns when a .dbc is next to it (a plain
table next to a .dbc stays a table). Extensions added to SUPPORTED_EXTS, TEXT_EXTS, common.SUPPORTED
and DATA_EXTS. Tests: `test_can.py` (7) - hand-made frames for each format, and agreement with
cantools on ~1,900 random values (cantools only if installed; not a dependency).
**Follow-ups:** ASC CAN FD lines; several buses with the same id (channel per .dbc); the installer's
*Open with* for .asc; MF4 (asammdf, LGPL - optional only, owner's call).

### Q73 · T43 part · Docs site and a shorter README — M
README: what it is, one clip, install, three uses, a comparison with similar tools; the
"What works" table and build details move to a MkDocs site on GitHub Pages (English + Hebrew).
**Status:** done 2026-10-20. README 68 KB -> 17 KB: the top (highlights + two new: CI, any recording),
the clips, Quick start, a short Install, Command line and CI, "Where it fits" (what it brings
together; when PlotJuggler / Foxglove / MATLAB SDI fit better - no feature table about other tools,
those change and would go stale), Documentation, the Hebrew section, License. Moved, unchanged
except paths: `docs/features.md` (What works + Keyboard; three new rows: own formats, CAN, command
line), `install.md` (Download / build + Run from source), `performance.md`, `limitations.md`,
`maps-and-3d.md`, `development.md` (Structure + Icon), `gallery.md`; new `index.md`,
`command-line.md`. `mkdocs.yml` (built-in theme - no plugin to install; docs/dev and the benchmark
notes excluded; `--strict` passes) and `.github/workflows/docs.yml` (build + deploy to Pages on a
push that touches docs). The release checklist (Releasing step 3) points at the docs pages now.
**Owner:** Settings -> Pages -> Source: GitHub Actions, once; then the site is
https://davidalpert11.github.io/SignalViewer/ (the README badge and links already point there).

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
- 2026-10-18 · Q40 / F17 plot menu closes on Esc / click outside · e2e · next: Q41.
- 2026-10-18 · Q41 / F18 dialogs take the keyboard (all of them, one watcher) · e2e · next: Q42.
- 2026-10-18 · Q42 / F19 an open file opened again is re-read, copy on request · e2e · next: Q43.
- 2026-10-18 · Q43 / F20 several files: Compare suggested, one note toast · e2e · next: Q44.
- 2026-10-18 · Q44 / F21 file dialog: Shift range, Ctrl+A, a last folder per use · e2e · next: the whole e2e suite, then the 1.6.1 release check.
- 2026-10-18 · F21 follow-up: listing the folder already shown kept clearing the selection (a click during the load was lost, Open disabled - 5 flaky test_features tests after F21 started the dialog in the data folder); now the picked files that are still there are kept. e2e `test_relisting_the_same_folder_keeps_the_selection` (fails without the fix). Whole e2e suite file by file: all pass (features 110, workflows 17, templates 11, globe3d 10, the rest) · backend 650 · next: 1.6.1 release patch.
- 2026-10-19 · 1.6.1 release patch: versions (build.bat, version.py, .iss, version_info.txt), CHANGELOG dated with highlights, README review (test counts 650 / 168, Files / Plots / Similarity rows, keyboard Ctrl+PageUp/PageDown, a browser limitation for those keys, Hebrew "חדש ב־1.6.1", installer name), dist rebuilt · next: owner tags v1.6.1; then Q30+.
- 2026-10-19 · Q30 + Q30+ / T24: places column in the file dialog (open files' folders, favourites - pin with ★, unpin, drag to reorder, kept in settings.json -, recent folders, this computer: home / desktop / documents / downloads incl. OneDrive and Hebrew names, drives / volumes), the message for a folder with nothing to open (+ how many other files), Ctrl+P quick open (favourites, recent files, recent folders). Backend `/api/fs/places`, `PUT /api/fs/favourites`, `hidden` in `/api/fs/list`; tests `test_places.py` (4) and e2e `test_file_dialog_places`, `..._recent_folders_and_empty_folder`, `test_quick_open` · next: Q45 (T46).
- 2026-10-19 · Flaky `test_create_signal_submenu_from_the_file_list` (failed in 2 of 4 whole runs): the hover that comes with a click opened the submenu and the click's toggle closed it; a click now only opens (`Overlays.tsx`). Repeated 3x alone + whole test_features 110 passed. Whole e2e suite file by file at this commit: all passed (workflows 20) · backend 654 · next: Q45 (T46).
- 2026-10-19 · Q45 / T46 file identity: backend gives every open data file a tag (first free A..Z, AA...) and a colour (least used of FILE_COLORS = the trace palette) - `Store.marks` by id, so reload / replace / live keep them; in `describe`, `PATCH /api/runs/{id}` tag (4 chars) / colour (#RRGGBB), sessions save and restore them. UI: file list header shows the tag in the file's colour (one file: a swatch) - click = colour picker; File options > Short tag…; legend chips show the tag instead of " · file.csv" when 2+ files, tooltip = full name + path; Inspector cursor / statistics rows and the Create signals pickers show the tag; a signal joining the same name from another file colours that group by file (shades for several names of a file); Plot ⋯ > Colour by file; Compare runs and Compare open files use the file colour (Compare no longer recolours when a run is unchecked). Tests `test_file_marks.py` (2), e2e `test_each_file_has_a_colour_and_a_tag`, `test_compare_keeps_file_colours`. Not done (left for later): map / 3D tracks and the report legend still use their own colours / the file name; the plot colour mode is an action, not a stored setting · backend 656 · next: Q46 (T47).
- 2026-10-19 · File dialog: Tab in the path box completed again and again (a keyboard user could not leave it; seen as a flaky `test_dialogs_take_the_keyboard` in a whole run) - Tab completes only after typing (`edited` ref; still continues inside a folder chosen by completion). Whole e2e file by file: all passed (features 110, workflows 22) · next: Q46 (T47).
- 2026-10-19 · Q46 / T47 second value axis: `PlotSignal.axis = "right"` (optional; old sessions all left). TimeChart: scale `y2` (auto range, room for state lanes), a right axis with its unit label (the left label from the left signals only), per-signal scale for the series, the values drawn at the cursor and the limit lines; chip shows "right axis"; chip menu *To the right axis* / *Back to the left axis*; adding a signal in other units than the plot's (one known unit vs another) offers the right axis in a toast once per plot and unit - nothing moves by itself. Reports: `plotSpec` passes `axis`; HTML report (viewer.js `y2`), PDF / Word / PNG / SVG (matplotlib `twinx`, one legend). Value zoom / pan / axis limits / linked value axes act on the left axis; the right axis follows its data. Tests `test_right_axis.py`, e2e `test_second_value_axis` · backend 657 · next: Q47 (T48).
- 2026-10-19 · Q47 / T48 first impression: a welcome-screen example opens with its suggested view applied (`openPaths(..., { autoView })` -> `offerStart(..., auto)` -> `openSuggested`): the drone flight its best view, the car runs / two flights Compare open files, the ArduPilot log its view; one Undo returns to the empty plot. After *Open it* (or the automatic open) the start card keeps the log's findings, if any (it used to close with them). Template chips in the file panel open the template at once when every slot has a clear file (the best by signal count, or "*all" for Compare) - `openTemplateNow` in smartStart.ts, a toast with Undo; a tie (Quick look with two files) opens the library as before; right-click on a chip = the library. Tests updated (examples now check the plots are filled; smart-start card; F13's chip) + e2e `test_template_chip_opens_at_once_or_asks` · next: Q48 (T49).
- 2026-10-19 · T48 follow-up in tests: `test_object_templates` / `test_templates_in_file_panel_for_csv` click a chip and now get the template at once (right-click for the library); `test_template_slot_...` asserted the slot select before the binding arrived (a race, failed once) - waits for the note first. Whole e2e file by file: all passed (workflows 24, features 110, templates 11, object templates 4) · backend 657.
- 2026-10-19 · User request (owner): telemetry ("tlog") exports where each value has its own time column, told apart by name - the user had to plot value vs time as X-Y. New `svcore/time_pairs.py` (`find_time_pairs`, `clean_pair`): (1) own pairs by name (Speed + Speed_time / Speed.time / time_Speed / t_Speed / Speed_t / Speed_timestamp / SpeedTime, units in [] ignored), (2) a message's time column for its fields (`ATTITUDE.time_boot_ms` / `.timestamp` / `.time`...; with "_" only the MAVLink names time_boot_ms / time_usec / timeus, so a data column gps_time is not taken), (3) alternating time / value columns (time, Speed, time, RPM - duplicate headers). CSV / TXT: pairs are split off before the rows without a main time are dropped (pairs have different lengths), each value gets its own time (Signal.time), the time columns are not listed, not cached, live append reloads the file; import option *Columns with a time column of their own* (on by default, `CSVImportSettings.time_pairs`); a reading note says how many. MAT: variables with an own time variable of their own length are kept (they were skipped for a length different from the main time). A .tlog that is a TEXT table (not a MAVLink recording) opens as CSV. Tests `test_time_pairs.py` (6), e2e `test_columns_with_their_own_time`. Not done: time units are not converted (time_boot_ms stays in ms, as the main time column always has); a real binary MAVLink .tlog already gives every message its own time. Asked the user for a sample file to confirm the layout.
- 2026-10-19 · Owner: "with live mode and a file that keeps being updated, does the app follow it or stay stuck until the writing ends?" Checked with a writer process and the app in a browser, polling the state every second for 22 s: a growing CSV (20 rows / 0.1 s) is followed every poll (samples 1980 -> 4980, the plot and the status bar follow). A MAT file saved again every 0.3 s was NOT: 16 s at the same 10,580 samples, "0 of 2 updating", the idle countdown running ("stops in 5"); it showed only once the writing stopped. Cause: files rewritten as a whole (MAT, ULog, MCAP, HDF5, Parquet) were read only after two polls saw the same size and date - never true while a program saves every second - and only a read counted as activity. Fix (`store.py`): read once quiet for SETTLE_QUIET (0.4 s) or at least every SETTLE_MAX (2 s) while it keeps changing; a read caught mid-write fails quietly and is tried again; a file being written counts as activity (`last_change`, poll `writing`), so live mode does not stop itself as idle. Also: one poll at a time - a slow poll (a big file read again) was overtaken by the next ones every second (backend lock + the UI skips a tick while a poll runs). Re-checked: the MAT now updates every ~2-3 s while written (6000 -> 16400 samples). Tests `test_live_rewritten.py` (2; the first fails without the fix) · backend 665.
- 2026-10-19 · Q48 / T49 part 1 (the items that change wording or remove an exact duplicate, no new structure): (1) the zoom-mode button always says "Zoom: X" (in a narrow window it was a bare "X" next to the link button's "X"); (3) Clear everything asks with a red "Clear everything" button (`confirmAsk(title, text, okLabel, danger)`); (5) "Templates…" removed from the tab menu and the + button menu (top bar, file panel strip and palette remain); (6) the file list's signal menu says "Add to the active plot", or "Remove from the active plot" when it is there (it said "Add the result…"), and "Change the variable…" is now "Scale, offset or function…"; (8) Create signals: "One signal / Each of several" -> "This signal / Each of several" (the mode tab above is also "One signal"); (11) Compare runs rows no longer show "err %" next to the match % (100 - it; still in the row's tooltip). e2e `test_clearer_controls`; test_features' transform test uses the new name. Left (need a design decision or a bigger change, see the list in Q48): 2 File menu in the top bar, 4 reload in four places, 7 two in-place edit mechanisms, 9 the plot-mode bar on every plot, 10 cursor buttons, 12 plot-area right-click menu, 13 a Help entry.
- 2026-10-19 · Q51 / T52: `tests/e2e/test_fresh_user.py` - a server per test with an EMPTY home folder; any page or console error fails. First run: welcome screen with examples, the template library without an error line (F14), the file dialog with its places and the keyboard (F18, T24), Hebrew and back; each of the four examples opens with its view applied (T48). 5 tests, passed.
- 2026-10-19 · Q50 / T51: built-in template names and the tabs they make in Hebrew - `tx()` in templates.ts translates the built-in names part by part (`BUILTIN_HE`: "ArduPilot · Attitude" -> "ArduPilot · זוויות"; ArduPilot / MAVLink / PX4 stay); a built-in template's tabs are named through it when applied; a user's own names are not touched; the generators' tabs were already translated. Frontend only (`builtin_templates.json` unchanged). e2e `test_builtin_templates_in_hebrew`.
- 2026-10-19 · Q49 / T50: the file panel header - the link toggle is an icon (pressed when on; its name and meaning in the tooltip), the title "Files" never gives way, the "Open files" label shrinks with an ellipsis if it must (its + stays); value axes (left and right) allow labels closer in a short plot (`space` = plot height / 4, 12-30 px) - more than one label at 1100x700 with four plots; the search box keeps its width with many tabs (F22). e2e `test_small_window_file_header`. Left: in a very short plot (4 plots at 700 px: ~40 px of curve) the mode bar + legend take most of the height - T49 item 9 (mode bar only on the active plot) is the real fix; a "too many plots for this window" hint was not added.
- 2026-10-19 · 1.7.0 release patch: versions (build.bat, version.py, .iss, version_info.txt), CHANGELOG dated with highlights, README review (installer name, "חדש ב־1.7" in Hebrew, two known limitations: the right axis follows its data; own time columns keep their unit), README pictures and clips retaken with `tools/make_readme_media.py` (17 images, 4 clips; 06_3d_terrain and the 3D clip kept from a real screen; vid_04 / vid_05 timed out in the whole run and were made again alone), dist rebuilt · next: owner tags v1.7.0; then the T49 decisions, Q33, Q31, Q34, Q32.
- 2026-10-19 · 1.7.0 tests: backend 665; e2e file by file all passed (features 110, workflows 28, fresh user 5, globe3d 10, templates 11, the rest) - `test_log_events_on_the_track_and_image` once waited too little for the 3D picture under load (10 s, software WebGL); it waits up to 30 s now (passed alone and with its file).
- 2026-10-19 · Review after 1.7.0: plan Q53-Q63 (+ Q24, Q31-Q34, rest of Q48) written, ranked; owner approved. Next Q53.
- 2026-10-19 · Q53 / F23: `compute_signal_stats` (svcore/ops.py) keeps weak references to the arrays with each cached result and uses it only when they are the same objects (an id alone was reused by new arrays: 193 of 200 fresh arrays got old numbers; `/api/stats` with a state filter showed B's mean for D). Cached call still ~0.02 ms (5 M samples: 46 ms first). Test `test_stats_never_reuse_another_arrays_numbers` (fails without the fix). Backend only, no e2e needed.
- 2026-10-19 · Q54 / T53: build.yml - the Windows job also makes the portable `.zip` (7z -tzip of the assembled folder) and the installer (PyInstaller `SignalViewer.spec` + Inno Setup, `choco install innosetup` when the runner has none, `/DAppVersion`), then installs it silently for the current user into the runner's temp folder, starts it and waits for `/api/runs` (the PyInstaller Windows build had no CI check before); the artifact carries the three Windows files; the release job uploads everything with a "which file?" note (`--notes-file` + `--generate-notes`). README "Download" names the file to take. **Not run here** (no Windows runner in the sandbox; YAML and the shell steps were syntax-checked, the notes rendered): the owner runs the workflow once. Open question for the owner: a 1.7.1 with F23 + these assets, or wait for 1.8.0.
- 2026-10-19 · Owner: no 1.7.1; F23 and the release assets go out with 1.8.0.
- 2026-10-19 · Q55 / T54: `run.py [paths…] [--new-window]`. `app/instance.py`: `hand_over` posts the paths to the running app (push.json url + token, `/api/open-external`, no proxy); `wait_or_lead`: a start lock (`~/.signalviewer/starting.lock`, O_EXCL; stale after 30 s) so Explorer's one-process-per-file starts end in ONE app - the others wait and hand over. The paths become an "open" push event; the page takes them once it has restored the autosave (`/api/push/events?opens=1`) and the server hands each out ONCE (a reload does not open them again - first version re-read them); `.svsession` goes to `openSession(path)`. The window comes forward (`push.ON_OPEN`, pywebview restore/show/on_top). Found on the way: TopBar and the palette passed the click event to `openSession` (now `() => openSession()`). Installer: task "openwith" (checked) - `SignalViewer.DataFile` ProgID, `OpenWithProgids` + `Applications\SignalViewer.exe\SupportedTypes` for 11 extensions under HKA, `.svsession` default only if unset, `ChangesAssociations`; the .iss is now UTF-8 with BOM (Hebrew task text). Tests: backend 4 (token, once-only events, no / stale push.json, start lock incl. a stale one), e2e `test_open_external` (a second `run.py file.csv` exits and the file opens in the page). Not checked here: the installer on Windows (no Windows in the sandbox).
- 2026-10-19 · Owner's rule for patches: one cumulative patch since origin/main every time (written under "How to work here"). Owner: decide and continue without asking.
- 2026-10-19 · Q56 / F24 + Q33 / T14c: `useGutter` / `reportGutter` (chartUtil.ts, UI-only `gutters` in the ui slice): each time / spectrogram / envelope chart reports the room left and right of its plot area, and the plots of a column (index % cols) use the largest. TimeChart counts the axis label (uPlot puts `labelSize` next to `size` - the first try missed it: 14 px off); the right axis's room evens out the right edge. SpecChart: margins from the gutter; with no zoom the image spans the signal's own extent (`sigT0` / `sigT1` from /api/spectrogram), empty where no window fits. EnvelopeChart: the tab's range (rangeKey): drag sets it, double-click clears it, a change elsewhere moves its axis without a rebuild. Measured on the ArduPilot example: Vibration tab 419/966 px for both time plots (was 91 vs 69 / different widths). Tests: backend spectrogram extent; e2e `test_aligned_plots` (units vs no units line up; Envelope lines up, its drag zooms the tab, double-click resets).
- 2026-10-19 · Q57 / T49 items 9 + 12 + F25. Decision (owner: "decide"): item 9 as ONE type button for every plot (`.mode-btn`, "Time ▾", a menu of the nine types with the current one checked - `MenuItem.checked`, role menuitemradio) rather than the bar on the active plot only: no header that changes height when another plot becomes active. With it the legend may share the header line (`.plot-head .legend { order: 4; flex: 1 1 240px }`, it wraps when it does not fit): ArduPilot Attitude at 1024x700 - 94 px of curve per plot (was ~60). The ⋯ menu is the app's ContextMenu now (no local menu, nothing clips it); a right-click in a plot opens the same items after "Cursor here / Second cursor here / Note here… / Previous zoom / Show everything" - the charts put the time under the pointer on the native event (`svTime`: TimeChart, EnvelopeChart via u.posToVal, SpecChart via toT); plots without a time axis get the plot items only. Tests: e2e `test_plot_menus` (one type button with Time checked; ⋯ in a short plot fully visible and on top; right-click order and cursors; type switch); every `.mode-seg button` in the e2e files and tools changed to the button + menu.
- 2026-10-19 · Q58 / T49 items 2 + 13 + F26. Top bar: "File" (text button after the app name; open files, recent and favourites = Ctrl+P, refresh all, open / save session, clear everything - the three loose icons are gone) and "Help" (before the Inspector button: keyboard shortcuts, Examples submenu from /api/examples, copy error details, about = version from /api/diagnostics in a toast). `MenuItem.keys` shows a shortcut at the end of a menu item. `copyErrorDetails` moved to errorReport.ts (the shortcuts dialog and the Help menu share it). F26: "Shift / Ctrl / Alt + wheel - values only / both / time only", double-click "Show everything (time and values)" (both languages). From Q63: the Inspector button's name translated (`inspector`), Hebrew "theme" = "ערכת נושא". The status bar's "?" stays. Tests: e2e `test_file_help_menus`; the three e2e places that clicked the "Clear everything" icon open File first.
- 2026-10-19 · Q59 / F27: chartUtil `wheelPixels` (deltaMode lines x16, pages x window height) and `wheelZoom` (exp(dy * 0.00223), dy clamped to +-120 px, factor 0.5-2: a 100 px notch = 1.25 as before; null when the scroll is not vertical). TimeChart and SpecChart: a sideways swipe pans the time window; wheel steps closer than `WHEEL_GESTURE_MS` (400 ms) are one zoom-history step (setView / setRange `history: false`). XYChart, XYZChart (`zoom / f^0.626` = 1.15 per notch as before) and GeoChart (`z - log2(f) * 1.09` = 0.35 per notch as before) use the same factor. Not done: a trackpad pinch arrives as Ctrl+wheel and zooms both axes - that is what Ctrl+wheel does. Tests: e2e `test_wheel` (a notch ~25 %; ten 4 px steps ~9 % and one history step - 89 % before; a sideways step keeps the width).
- 2026-10-19 · Q60 / T55: `docs/GUIDE.md` and `docs/GUIDE.he.md` - 12 short sections (start, open, the screen, plot, zoom, measure, compare, create signals, keep and share, flight logs, live, when something goes wrong), every name checked against the UI strings. In the app: Help > User guide, F1, the command palette - `GuideDialog.tsx` loads the guide of the UI language (`?raw` import from docs/, its own small chunk, 6-8 kB) and draws it with a small Markdown reader (headings, paragraphs, lists, tables, code, bold, italic) as React elements. README links both. Decision: the "3-minute tour" is a recorded video with a voice - the owner's (the README's pictures and clips, tools/make_readme_media.py, stay). Note: run.py's "rebuild the UI when the sources changed" watches frontend/ only - a guide edit is in the app after the next build. Tests: e2e `test_user_guide_in_the_app` (Help menu, a table, code; F1 in Hebrew).
- 2026-10-19 · Q61 / T56: `tools/make_pypi.py` stages build/pypi (signalviewer/ = backend/signalviewer + `launcher.py`; signalviewer/_core = app, svcore, run.py unchanged, the built UI as ui/, examples/) and builds wheel + sdist (~22 MB, setuptools>=77, MIT); `signalviewer/__init__.py` puts `_core` on sys.path when it exists, so `app` / `svcore` are not top-level names in site-packages; push.py also finds the client at signalviewer/push_client.py. Commands: `signalviewer` (the app: SV_DIST / SV_EXAMPLES to _core, then run.py) and `signalviewer-cli`. pywebview is the extra `[desktop]` (needs GTK / Qt on Linux; without it the browser opens). `--check`: a fresh venv, pip install the wheel, start it (UI page, /api/examples), `signalviewer-cli info`, `import signalviewer` + load, push client saved - green here. CI: job `pypi-build` (every run, artifact `signalviewer-python-package`, also on the release page), job `pypi-publish` on a tag only when the repository variable `PYPI_PUBLISH` = "true" (trusted publishing, environment `pypi`, no token). The name `signalviewer` is free on PyPI (2026-10-19). **Owner, once:** pypi.org -> Your projects -> Publishing -> add a pending publisher (owner DavidAlpert11, repo SignalViewer, workflow build.yml, environment pypi); GitHub -> Settings -> Environments -> new "pypi"; Settings -> Variables -> PYPI_PUBLISH = true. Not run here: the CI jobs themselves.
- 2026-10-20 · Q34 / T18 + F28, and **F30 found on the way**: the app starts on a free port each time (run.py `free_port`), and a browser keeps localStorage per origin (port included) - so everything kept there (panel widths, the Inspector's open / closed, the file dialog's sort and last folders, the MAVLink address) was forgotten at every start; it only seemed to work inside one run. Now: `prefs.py` (backend) `ui_settings.json` + GET / PUT `/api/settings` (merge, None removes, 64 kB cap); frontend `prefs.ts` (loaded before the first render in main.tsx; sync `getPref`, `setPref` written through within 300 ms; the first start takes over the `sv3.*` keys the browser still has) - every localStorage use moved to it. `settings.ts`: theme, lang, uiScale, timeFormat, liveAutoStop, liveNewFiles come from it and are written back on change (store subscription); `applyState` takes those from a session only when the user never chose them (`hasSetting`). Settings dialog (gear in the top bar where the theme button was, File > Settings…, Ctrl+,, the palette): theme, text size, time on the timeline. Decision - one place per choice: the language stays the top-bar button and live mode's choices stay in Live ▾ (both now kept between starts the same way); the map layer stays in the map. F28: the timeline writes seconds as recorded by default (the axes' number; 2 / 1 / 0 decimals by span), the clock from the start is the setting. e2e fixtures that clean the autosave also remove ui_settings.json (each test starts like a new user). Tests: backend `test_ui_settings_are_kept_in_the_app_folder`; e2e `test_settings` (timeline = cursor seconds; choices written to the file; kept over a reload; a session opened from outside does not change them); `test_V10_theme` through Settings.
- 2026-10-20 · Q62 / T49 items 4 + 7. Item 4: *Reload from disk* left the file's ⋯ menu, and the File menu's *Refresh all files* (added in Q58) went too - reload stays the ↻ next to each file, F5 and the panel's ↻ (all files), and Live. Item 7: the two ways were already ONE mechanism underneath (both write `signal.transform`; Create signals' edit composes a step onto it - transforms.ts `composeTransform`), so the merge is in the UI: one name, *Change this signal…* (menu, dialog title "Change the signal") = *Create signals → Change this signal* (button "Apply the change"), its hint says they are the same; in the file list's signal menu it moved after Add / New plot / Use as X (it was first). e2e updated (`test_edit_original_steps_and_undo_all`, `test_transform_expression_autocomplete_and_checks`).
- 2026-10-20 · Q31 / T23: `Note.t2` (end of a range). `addNoteAtCursor`: with two cursors (and t1 != t2) the note covers min..max ("From a to b s" in the prompt), one cursor as before; the plot's right-click *Note here…* goes through it. TimeChart: range notes are a shaded span in the note colour (10 %) with a line at the end, the marker and text at the start; the Inspector lists "a – b". Report: `_note_when` ("20 – 26.5 s") in the HTML / PDF / Word lists, `axvspan` on PDF / Word plots (the HTML report's plots draw no notes, as before - their list is under the summary). Tests: backend `test_report_with_spectrogram_and_notes` (a range note in all three formats); e2e `test_range_notes` (range from two cursors whatever their order, Inspector text, a shaded pixel inside and not outside, one cursor still a point).
- 2026-10-20 · Q32 / T25: the error signal itself already existed (Create signals > Two signals, A − B, aligned onto A); what was missing is the per-segment answer. `/api/error-segments` {a, b, state?, alignment}: e = A − B on A's samples (linear: NaN outside B; nearest: A's samples outside B's time dropped), RMS / mean / max |e| (+ its time) over the overlap and, with a state signal, for each stretch (`_stretches`, label + occurrence; stretches without overlap left out). UI `ErrorSegments.tsx` under Two signals when the operation is A − B or |A − B|: "For each stretch of" (signals with texts or few values, A's file first) → a table, the worst stretch marked, a stretch click zooms the active plot's time to it, a max click puts the cursor there. Tests: backend `test_error_between_two_signals_per_segment` (CRUISE off by 2 stands out, others ~0, only where both have data, 404); e2e `test_error_segments`.
- 2026-10-20 · Q63 / F29 (labels done in Q58): the Inspector's single-cursor value uses 5 significant digits like the legend chip (was 6; the exact value is in its tooltip). An unreadable autosave is moved to `autosave.damaged.json` and GET /api/autosave says so (`damaged`) - the UI shows where, 15 s - instead of being overwritten by the next autosave; the autosave's temporary file is per process (two apps writing at once no longer write into one .tmp; the last write still wins - two apps started WITHOUT files remain two apps, by design since Q55). The Python push client opens 127.0.0.1 without any proxy (`ProxyHandler({})`, as app/instance.py). Tests: backend `test_damaged_autosave_is_kept_aside`.
- 2026-10-20 · Owner: the CI run passed on GitHub (Windows installer built, installed silently and started; zip; Python package checked) - Q54 done.
- 2026-10-20 · Q64 release 1.8.0 prepared: versions (build.bat, version.py, .iss, version_info.txt incl. the tuples), CHANGELOG dated with highlights, README review (Download section, rows: timeline seconds / clock, A − B per stretch, range notes, trackpad wheel, installer "Open with"; test counts 673 / 193; three known limitations added: Open with is the installer's, pip opens the browser without [desktop], the HTML report lists notes without drawing them; "חדש ב־1.8"), README pictures and clips retaken with `tools/make_readme_media.py` (06_3d_terrain and the 3D clip kept). Found on the way: the media tool's Hebrew scene left every later scene in Hebrew - settings are kept in the app folder since Q34 - so `reset()` removes ui_settings.json too (as the e2e fixtures do). dist rebuilt.
- 2026-10-20 · Review after 1.8.0 (plan Q65-Q73 above). Q65 / F31: `svcore/naming.py` `resolve_signal_name` (exact, without the unit, any case; several hits = error; else the closest three), used by `Recording.signal` and so by `table`, `to_dataframe` and `signalviewer-cli export`; the messages say where the full names are. `signalviewer.show` re-exports the push client's `show`. Tests: backend 675, mypy clean.
- 2026-10-20 · Q66 / F32: README for PyPI with absolute pictures / links (tag v<version>), project URLs, keywords, classifiers; badge 3.9+; pyproject note. Backend 676, mypy clean, `make_pypi.py --check` OK.
- 2026-10-20 · Q67 / T57: `signalviewer-cli check` (app/checks.py): checks file or a template's limits, windows and state stretches, JUnit XML, exit 0 / 1 / 2; `_stretches(..., where=store)`. Backend 680, mypy clean.
- 2026-10-20 · Q68 / T58: `signalviewer-cli compare` (app/checks.py `run_compare`, `load_tolerances`), shared result printing with `check`. Backend 682, mypy clean.
- 2026-10-20 · Q69 / T59: pip extras from svcore/extras.py, messages for .tlog / MAT v7.3 / reports, wheel check covers the plain and [all] installs. Backend 687, mypy clean.
- 2026-10-20 · Q70 / T60: user readers (svcore/readers.py, app/userreaders.py, /api/readers, CLI readers), extensions in the file dialog and drops; MAT v7.3 extra message code fixed. Backend 691, mypy clean, tsc + build clean (dist not in the patch).
- 2026-10-20 · Q71 / T61: binary layouts (svcore/icd.py) as readers in the readers folder, CLI example. Backend 701, mypy clean.
- 2026-10-20 · Q72 / T40b: CAN logs + own DBC decoder (svcore/dbc.py, can_loader.py), checked against cantools. Backend 708, mypy clean, tsc clean.
- 2026-10-20 · Q73 / T43 part: docs site (mkdocs.yml, docs/*.md, workflow docs.yml), README shortened to a front page. Plan Q65-Q73 done.
- 2026-10-20 · Owner's review after Q65-Q73: plan Q74-Q77. Q77 / F34: derived versions name their definition (serial), Python operations recomputed on reload, run / derived versions in the run list and the UI's data keys, CSV cache + live follow with a content fingerprint. Backend 713, mypy and tsc clean.
- 2026-10-20 · Q74 / F33: README Hebrew section rewritten (RTL div, structured, no `~`).
- 2026-10-20 · Q75 / T62: two PyPI distributions (signalviewer = full, signalviewer-lite = core + extras), hints per flavour, both checked. Backend tests green.
- 2026-10-20 · Q76 / T63: Clear button with scopes (clearing.ts), File submenu, Ctrl+K; e2e written (not run here). Plan Q74-Q77 done.
- 2026-10-20 · Q78 / F35: no File menu - session, Clear, settings, day / night as top-bar buttons; the stage bar's eraser as in 1.8.
- 2026-10-20 · docs workflow: actions/upload-pages-artifact@v5 and deploy-pages@v5 (Node 24; v3 / v4 gave the Node 20 deprecation warnings); the 404 of the first runs = Pages not enabled yet (owner: Settings -> Pages -> Source: GitHub Actions), said in the workflow's header.
- 2026-10-20 · Q79 / F36: owner's e2e 192/194; tab strip room at 1100 px (.hide-compact), the 3D image test on Windows (tempfile).
- 2026-10-20 · Q79: owner re-run - tab test green; 3D image test: own folder, full path in the name box, toasts in the failure message.
- 2026-10-20 · **Release 1.9.0** prepared: version in build.bat, version.py, SignalViewer.iss, version_info.txt (+ the installer name in docs/install.md); CHANGELOG `## 1.9.0 – 2026-10-20` with highlights ("No File menu" moved to Changed); README / docs review: features.md test counts (111 / 194 / 714), install.md (~710), limitations.md (CAN: no ASC FD / .blf / MF4, one message per id across buses; ICD: no checksums, arrays, variants; readers in-process, reloaded whole in live mode); README's own text already matched. `tools/make_readme_media.py`: all 17 pictures and the 01, 03, 04, 05 clips retaken (06_3d_terrain.png and the 02 clip kept, as the tool says); in the full run vid_04 and vid_05 timed out after the other scenes and were made on their own (`--only vid_04 vid_05`) - follow-up: the scenes share one App, give the clips a fresh one. frontend/dist rebuilt. Owner: tag v1.9.0 after the push (PyPI pending publisher for signalviewer-lite first).
- 2026-10-21 · External review (A1-A6, B7-B10, C13): spectra on an even time grid, -3 dB filters, time-weighted statistics, numerical validation (23 cases, `validate`), real-vehicle log tests (the .tlog radio-delay fault fixed), docs site on Material, features page in sections, the sim-vs-flight example with `compare --align`; names matched without the unit in Compare / Align / CLI.
- 2026-10-21 · **Release 1.10.0** prepared: version in build.bat, version.py, SignalViewer.iss, version_info.txt (+ the installer name in docs/install.md, the version on docs/validation.md); CHANGELOG `## 1.10.0 – 2026-10-21` with highlights and the results that change from 1.9.0; README review (Hebrew section: sim vs flight, validate); frontend/dist rebuilt. Left for the owner: the e2e suite on Windows, tag v1.10.0.
- 2026-10-21 · Review after 1.10.0 (plan Q80-Q84 above). Q80 / F37: sv.load() progress to stderr (+ test), PyPI Documentation = docs site, README (desktop extra, --depth 1, unsigned packages -> docs/install.md *First start*), pyproject note. Backend green, mkdocs --strict clean.
- 2026-10-21 · Q81 / T64: .github/workflows/ci.yml (backend 3.9 + 3.12, mypy, validate, frontend build, e2e smoke on that build), README badge. Here: backend on 3.9 783 passed; the three e2e files 35 passed.
- 2026-10-21 · Q82 / T65: `outside_pct` / `--allow-outside` in compare (app/checks.py), exact share in the message, docs (command-line, sim-vs-flight). Backend green.
- 2026-10-21 · Q83 / T66: Help > Report a problem (errorReport.ts `reportProblem`, /api/report-problem). Backend green; tsc + build clean; e2e test_file_help_menus, test_fresh_user, test_workflows 35 passed (dist not in the patch).
- 2026-10-21 · Q84 / T67: CONTRIBUTING.md, SECURITY.md, CITATION.cff (+ version test), issue forms, PR template, docs/dev/OUTREACH.md; README links. Plan Q80-Q84 done.
- 2026-10-21 · **Release 1.11.0** prepared: version in build.bat, version.py, CITATION.cff (+ date), SignalViewer.iss, version_info.txt (+ the installer name in docs/install.md, docs/validation.md regenerated); CHANGELOG `## 1.11.0 – 2026-10-21` with highlights; README review (compare --allow-outside, the Hebrew section: desktop extra, report / contribute line), features.md (compare, validate), install.md test counts; frontend/dist rebuilt. Here: backend 787 + real logs 12, e2e 194 / 194, make_pypi --check OK. Left for the owner: tag v1.11.0, publish the draft.
- 2026-10-21 · CI #2 (the first `ci` run) red on e2e: test_user_guide_in_the_app counted the guide's h3 before its text arrived (the dialog's own title is the h2 it waited for; the text is a lazy chunk). Now waits for the 10th h3. Running the trio 6 times here found a second race: an Esc pressed as the shortcuts dialog appeared was lost and its scrim blocked the next click - `close_dialog()` waits for the scrim and presses Esc again. ci.yml: download-artifact@v7 (Node 24, as build.yml). Trio 5 / 5 runs green. Tests and CI only: no change to 1.11.0.
- 2026-10-21 · Google Search Console: the owner's verification file docs/google93a24742f4c5f4f6.html (copied as-is to the site's root, /SignalViewer/; not in the sitemap). Keep it: deleting it un-verifies the site. Then: Sitemaps -> sitemap.xml, URL inspection -> Request indexing (docs/dev/OUTREACH.md).
- 2026-10-22 · Q85 / F38 (owner's report): groups close while searching, the selection's right-click (list and legend) acts on all selected, x = each target in the change dialog, *Expression in x* in Analysis, group checkboxes, the next pick after an action starts a new selection, Esc. tsc + build clean, oxlint 39 warnings (as before); e2e test_features, test_pyops, test_plot_menus, test_workflows green (+1 new test).
- 2026-10-22 · Q86 / F39 (owner, after applying Q85): Shift ranges that add up (1-3, then 7-11), Shift + drag (the range on mousedown, no native drag), auto-scroll at the edges. Reproduced first in Playwright (1-11 instead of 1-3 + 7-11; drag: nothing). tsc + build clean, oxlint 39; e2e test_shift_ranges_add_up_and_shift_drag + the selection tests green.
- 2026-10-22 · Q87 / T68 (owner): Add a run with the same work (same plots / new tabs), Link plots and Link operations each on its own (peers.ts: derived peers by operation + mapped sources). tsc + build clean, oxlint 39; e2e test_linked_operations_and_a_run_with_the_same_work green; guide en / he.
- 2026-10-22 · Release 1.12.0 again, with Q87: the owner had pushed Q85-Q86 + the release commit and the tag v1.12.0 (not published: PyPI 1.11.0, draft only), so Q87 comes on top of origin/main as its own commit plus a release commit (dist, these notes) - no reset, no force push; the tag moves to the new release commit. The full e2e run found two things the single runs did not: the new button shared `.link-toggle` (test_small_window_file_header's locator found two - now `.link-edits`; the header still fits at 1100 px), and the Q87 test chose run_b from the 12 suggestions, which earlier tests' run_* files push out - it uses *Other…* now.
- 2026-10-22 · **Release 1.12.0** prepared: version in build.bat, version.py, CITATION.cff (+ date), SignalViewer.iss, version_info.txt (+ the installer name in docs/install.md, docs/validation.md regenerated); CHANGELOG `## 1.12.0 – 2026-10-22` with highlights; README review (Math line, the Hebrew section's calculate line), features.md (file list, legend, analysis, new runs - in Q85-Q87), the guide (en / he: compare runs); frontend/dist rebuilt. Here: backend 787 + 12 skipped, mypy clean, e2e 197 / 197 in one process, mkdocs --strict, validate 23 / 23, make_pypi --check OK. Left for the owner: tag v1.12.0, publish the draft.
- 2026-10-23 · Q88 / T69 (owner): Copy the work to another file - an open one too - part by part (changes / new signals / plots: same, beside each plot, tabs, none; the links as two boxes, off by default); Clear this file ▸ (plots / changes / new signals / all, one Undo). **Release 1.13.0** prepared: versions (build.bat, version.py, CITATION.cff + date, .iss, version_info.txt, install.md, validation.md), CHANGELOG, README, guide en / he, features, frontend/dist. Here: backend 787 + 12 skipped, mypy clean, tsc + build clean (oxlint 39, as before), e2e 199 / 199 in one process, mkdocs --strict, validate 23 / 23, make_pypi --check both 1.13.0 wheels OK. (One earlier full run had test_globe_without_webgl_falls_back time out while the PyPI build ran beside it; alone 3 / 3, then test_features 115 / 115, then the whole suite 199 / 199.)
- 2026-10-24 · Q89 / T70 (owner, before pushing 1.13.0): other signals in an expression of x (`sin(x) + {Speed}`: the same file, as read), in place and as new signals; 1.13.0 re-prepared with it (dist, CITATION date, notes) on top of the owner's applied but unpushed 1.13.0 commits. Here: backend 788 + 12 skipped (+1), mypy clean, tsc + build clean (oxlint 39), e2e 200 / 200 in one process, mkdocs --strict, validate 23 / 23. An earlier full run found the number-suggestion bug and the old "only x" test; the templates test that failed with them passes alone and in this run.
- 2026-10-24 · Q90 / T71 (owner, after applying Q89): `{file:Name}` in an expression of x - one particular file's signal for every signal changed; stored by the file's id, shown by its name; the braces hint. 1.13.0 re-prepared with it on top of the owner's applied, unpushed Q89 commits. Here: backend 789 + 12 skipped (+1), mypy clean, tsc + build clean (oxlint 39), e2e 201 / 201 in one process, mkdocs --strict, validate 23 / 23.
- 2026-10-24 · Q91 / T72 (owner, before pushing 1.13.0): new signals of two files belong to one (pinned sources from {file:Name}, Formula {file:name}, Compare's baseline); copy / link / clear handle them; ones with no recorded intent are asked about in the copy dialog. 1.13.0 re-prepared on top of the owner's applied, unpushed Q90 commits. Here: backend 789 + 12 skipped, mypy clean, tsc + build clean (oxlint 39), e2e 202 / 202 in one process (a first full run had test_template_files_are_found_from_tabs_and_matched_by_name time out once - alone 3 / 3, its module 2 x 11 / 11, untouched code), mkdocs --strict, validate 23 / 23.
- 2026-10-26 · Q92-Q97 / T73, F40-F44 (owner's report after 1.13.0; applied by the owner as one commit, then 1.14.0 prepared on top): big .bin logs (one pass, run-by-run chain, lazy values, float32, index cache), the browser server's watchdog, live / refresh keep the time at the newest data, the cache (pruning, Settings, `cli cache`, three leaks), the Windows window (unblock, WebView2 by folder, the reason shown), typed signal choice with unit and ƒ, unit conversions, tools/live_demo.py. Here: backend 805 + 12 skipped (+16), mypy clean, tsc + build clean (oxlint 39), e2e 205 / 205 one file per process (in earlier runs in one process test_globe_without_webgl_falls_back timed out once - alone 4 / 4, its path untouched; test_compare_same_segment_across_runs fails about 1 in 8 on 1.13.0 too - left as it is). mkdocs --strict, validate 23 / 23.
- 2026-10-26 · Q98 / F45 + Q99 / T74 (owner): blank window on old offline WebView2 (build target, polyfills, launcher fallback chain, boot guard, safe graphics); Time axis… dialog (column, unit, offset; checks; linked files; Undo) replacing Time offset…. Tests: test_time_axis (13), test_launcher (+6), e2e D11 updated + D11b-d + test_N_blank_window_says_why. Full run: backend 823 passed, mypy clean, tsc + build clean, e2e 208 + 1 passed.
- 2026-10-26 · Q101-Q103 (owner, from a user): object position from ECEF / NED / ENU via the existing frame conversion (frames.ts createAxesGroup shared with Place on map), vecsmooth (svcore/analysis.py time_moving_average), object dialog reads its chain back (vecsmooth -> frame) and saves unchanged without new signals. Velocity in the object: not wanted (owner). Tests: test_vecsmooth (8), e2e test_object_frames (3).
- 2026-10-26 · Q104 (owner): state lanes - the lane name moved from over the last stretch to the left margin (TimeChart drawStates), lane tooltip, ws.globalStates (every time plot of every tab) beside tab.sharedStates, setLaneScope (one place at a time; toggleSharedState removed), ws.stateNames + setAlwaysState (by name, newPlotSignal follows), lanes.ts menus from the lane / chip / signal list, lanes capped at a quarter of the plot. Tests: e2e test_state_lanes (3).
- 2026-10-26 · Q105 (owner): conditions - formula.py gains and / or / not; svcore/conditions.py (names, state texts, stretches with exit / min / merge); store.evaluate_condition per file as shown; ws.conditions + ui condResults / condFocus / condEdit; conditions.ts (evaluate all, combine and / or, step, save / delete); InvestigatePanel; TimeChart drawConds + selection bar (two cursors; Shift+drag kept for value zoom - spec deviation, see limitations); condition strips along the top instead of the bottom lanes (no value-axis room needed). Tests: test_conditions (4), e2e test_conditions (4).
- 2026-10-26 · Q106 (owner): occurrences - svcore/occurrences.py (stats per stretch, windows on one relative axis with padding, differ_one: |mean in - mean out| / std out); store.occurrence_rows / _windows / _differ (names averaged over files, weighted by time inside); OccSection in the Investigate panel (table, overlay, differ); plot mode "occ" (OccChart; listed in the mode menu only on such a plot). Tests: test_occurrences (4), e2e test_occurrences (3).
- 2026-10-26 · Q107 + Q108 (owner): what changed first - baseline well before the span (default_baseline: lead max(L, 1 s), length max(L, 2 s); the first try, right before the span, put every cause at the search start), k = 4 noise (MAD), 3 samples in a row (k 3 / 2 samples gave 22% false alarms on pure noise), states by a new value; lag by FFT, normalised per shift by the overlapping energy (plain full correlation biased the lag toward 0). WhatChanged.tsx (scope tab / all, groups by sample rate, sparkline, stacked tab, lag sentence + curve, show aligned with tOffset). The demo: wind -> vibration +0.1 -> motor 3 saturation +0.1 (heavy) -> roll +0.15; the tools find exactly that. Tests: test_firstchange (5), e2e test_what_changed (2).
- 2026-10-27 · Q109 (owner): runs x conditions - store.run_params (constant signals when the file has <= WIDE signals, numbers in the file name: name=value, nameVALUE, name_VALUE); RunsMatrix dialog (only parameters that differ; odd = robust z > 3 or the one differing when the rest agree; scatter with least-squares line and r). Spec deviation: a folder of runs is OPENED (up to 200), not indexed in the Fleet's sqlite - the Fleet index stays for flight logs (limitations). Tests: test_run_params (1), e2e test_runs_matrix (2).
- 2026-10-27 · Q110 (owner): findings and report - Note.status / view (investigation.ts captureView / restoreView / setFindingStatus), journal in UI state saved by currentState / applyState (no undo steps; last 200), recorded from saveCondition (its own evaluateOne - evaluateAll rounds can be overtaken), WhatChanged, lag, differ, overlay; report.py sections (HTML _sections_html, PDF pages via _section_lines, Word headings / bullets / tables); ReportPanel buildBody shared by preview and save (was duplicated), a "Findings" report tab of finding plots at their view, occ plots left out, range notes send t2. Tests: test_report_sections (2), e2e test_findings_report (2).
- 2026-10-27 · Q111 (owner): overview strip - svcore/overview.py (phase signal by name / first with texts; stuck / saturated only for signals that change on >= 80% of samples, never in the first / last 5%, saturated only when <= 10% of the run at that edge; gaps > 20 steps and >= 0.5 s; spikes 8x the robust diff noise and back); the first rules flagged dozens of ground / set-point stretches on the example logs - now 0 on the quiet examples, the 3 built saturations on the demo, a real cluster at 138 s on copter_flight.bin. OverviewStrip above the plots (pref overviewOff), clusters close flags. Tests: test_overview (3), e2e test_overview_strip (2).
- 2026-10-27 · Q112 (owner, while testing): ws.overviewRows (state by name / condition id; absent = the phase signal), /api/runs/{id}/overview?rows= (stretches of those state signals), ui.stripSel (picks per row, "or" = union, "and" = intersect, in the strip's run; TimeChart shades it like the condition in focus), Save as a condition (state rows -> Name == "TEXT" / number; plain conditions inlined; conditions with options -> a combined condition with the plain part saved beside it). A click on a stretch now picks; double-click zooms (it zoomed on click before). Tests: test_overview (+1), e2e test_overview_strip (+1, two adapted).
- 2026-10-28 · Q113-Q119 (review of the investigation with the owner, applied as one commit + a mypy fix) and 1.15.0 prepared: version 1.15.0 (version.py, CITATION.cff, build.bat, the installer, install.md); CHANGELOG 1.15.0 with highlights - the fixes to features not released yet folded into their entries; README (en / he), features, guide (en / he), tutorial reviewed; validation report regenerated (23 / 23, only the version line changed). Here: backend 854 + 12 skipped, mypy clean, tsc + build clean, validate 23 / 23, mkdocs --strict, e2e 240 / 240 in one process on this tree with the rebuilt frontend/dist (test_globe_without_webgl_falls_back timed out in 2 of 5 full runs while the review was made, alone 3 / 3 - its path untouched).
- 2026-10-28 · Q122 (review): baseline fitted to the data + noRoom, exponent numbers, discrete direction, Hebrew in What changed first, "1 stretch".
- 2026-10-28 · Q123 (owner): change marks on refresh tried (fingerprints, dots, ↻ / ✓) and dropped; kept: the saved time on the file row, newer on the disk (stat poll, click / F5), a message per file.
- 2026-10-29 · 1.16.0 prepared: the 1.15.0 release commit (tagged, never on main) brought back; version 1.16.0 (version.py, CITATION.cff, build.bat, the installer, install.md); CHANGELOG 1.16.0; docs reviewed; frontend/dist rebuilt.
- 2026-10-31 · S00 (owner's Sweeps plan): Sweeps strings moved to `sweeps/i18n.ts`; `PanelResizer` / `usePanelWidth` out of App.tsx; the plan S00-S08 written here and in ROADMAP Milestone 17. No change on screen.
- 2026-10-31 · S01: `activeColumns` / `activeParams` / `mapAxes` (sweeps/view.ts) used by MapView, NextRunsView, ReportDialog, ConditionRow, SweepsArea; a goal's weight input keyed by goal; template save / delete messages (swTemplateSaved / swTemplateDeleted). Tests: e2e test_sweeps_flow +2 (17 / 17).
- 2026-10-31 · S02: sweeps/state.ts `history` per study (snapshot = roles by name, question, the view's UNDO_VIEW keys; same kind within 1 s or a second change within 50 ms = one step; merge / unmerge forget it; `patch(f, false)` for what the app does by itself); `/api/sweep/autosave` (common.read_autosave / write_autosave, now shared with Recordings' autosave - F29's set-aside kept) + `reopenLast` when the area first shows; `areaCommands.ts` (an area's keys and Ctrl+K commands; App.tsx asks it when the area is not Recordings); `sweeps/notify.ts` -> Toasts in the area (a view's own loading error stays in the view). Also a separate commit: mypy clean again (16 errors in the Sweeps backend). Tests: test_sweep +1, e2e +1 (and the message selectors), the e2e fixture removes sweep_autosave.json.
- 2026-10-31 · S03: ParallelPlot `.pp-scroll` (MIN_AXIS 110 px, a non-passive wheel listener that scrolls sideways and lets the page scroll at either end, `fit` = view.fitAxes, optional), the tooltip a grid of columns kept inside what is on screen; `ColumnPicker` = MultiSignalPicker (new `noun="columns"`) in a fixed popover, options by group (`axisOptions`, `groupLabel`, `presetChoices` in view.ts), in the results' bar and both raw views (ShowSelect and the two selects gone); StudyView: `usePanelWidth` swLeft / swDetail + `PanelResizer`, `leftHidden` (pref sv3.swLeftHidden), the grid's columns inline; SetsTable: re-run / rank / holds sticky (`.st-0..2`), holds moved next to the rank. Tests: e2e +1 (wide table: scroll by wheel, fit, typed choice, drag, hide), two adapted to the picker. Checked by eye in Hebrew (RTL).
- 2026-10-31 · S04: view.onlyHolding / tableColumns / tableSort (optional, undoable); sweeps/view.ts `tableRows` / `tableColumns` / `tableOptions` / `defaultTableColumns` - one answer for the table, its export and the report; SetsTable rewritten (bar, pages of 100, sortable headers); `/api/sweep/export-sets` (a row per set, the columns and labels given, holds 1 / 0; a set number out of range = 400 "export again"); the runs through `export-rows`; the report's `rows` (optional - without it the table is every set best first, as before) used by CSV / Word / PDF and the HTML's table; ColumnPicker opens upward when there is more room there. Tests: test_sweep +1 (export-sets, export-rows, the report's rows), e2e +1 (only holding, sort, a column, both exports, three undo steps), three adapted (two pickers now).
- 2026-11-01 · S01b (owner: "how does optimize min / max work, does it?"): one objective worked (worst case: min over the combinations when maximizing, max when minimizing); with 2+ the rank still came from the first only - evaluate.answer now ranks the holding sets by #score when there are 2+ objectives; variants return the best's score; GoalsStep: a sentence of what ranks now (`optimizeNow`), objective / goal named apart, the hint says what worst case means. Tests: test_sweep +1 (max / min / weights), e2e +1, `_optimize` helper renamed.
- 2026-11-01 · S05: view.maps [{x, y, rest}] / view.scatters (optional; older studies: mapX / mapY, scatterX / scatterY as the first); `mapList` / `nextMapPair` (view.ts); svcore `map_for` (one map for the page and the report: min goals negated around pair_map - the report's map had the largest as best when minimizing), `best_set`, `slice_mask`, pair_map(only=); /api/sweep/map `rest`; the report's `maps` and figures as an ordered list (key, title, png) in HTML / Word / PDF. MapView = MapsView of MapPanel (pair, the others, ×, the edge where holding begins, a click on a cell = filters on x, y and the slice's parameters + a toast to the lines); marks carry their parameters (each map places them); ScattersView of ScatterPanel. Tests: test_sweep +1 (slice, min, report maps), e2e +1.
- 2026-11-01 · S06: question.robust {param: {mode pct | abs | steps, value}} (optional, wired only when set); svcore grid `tolerance_levels` / `tolerance_band` / `robustness` -> #robustHolds / #robustGoal / #robustSeen, ranking among robust-holding sets (score with 2+ objectives); suggest(focus, score, rank, robust) + kind `robust` (the band's ends of the top 5); Grid.neighbours(only=). With an old request the answer is byte-identical to before (checked against the previous analysis.py). Frontend: RobustEditor (Goals), NextRunsView rewritten (view.next: focus / kinds / budget / result with its question key -> "the question changed" banner; kept, not undone), sweeps/next.ts (KINDS, MARK), FLAG_COLS, marks off a map's axes, the report's question and process lines. Tests: test_sweep +1, e2e +1.
- 2026-11-01 · S07: TemplatesDialog (save / replace-asks / apply / double-click / export / import / delete; the fit = this table's share of the template's columns); `/api/sweep/templates/export` and `/import` (a template = columns + question; a taken name gets (2)); saved templates get `kind` and `saved`; saveTemplate leaves out scope and next.result / exported; the Apply / Delete submenus gave way to *Templates…* (and Ctrl+K). The e2e `save_as` helper clicks the save dialog's own button (a dialog behind it took the click). Tests: test_sweep +1, e2e +1, one adapted.
- 2026-11-01 · S08: sweeps/journal.ts - `changes(a, b)` reads the journal lines off two states of a study in `patch` (tracked changes only, so undo and answers write nothing; `as` = the action's own line: template, reset), `withEntry` merges a run of one kind to one key within 2 min (max 400 lines), `journalLine` renders in the report's language (a goal without a name of its own = "Goal n", as its tab); explicit lines: open, merge / unmerge, suggest, export (every file written), report. Study.log / iterations (saved in .svsweep, optional); `withIteration` on each answer (n = 1 + merged tables). Report: sections journal + iterations, `iterations` -> fig_iterations (2 or more), `provenance(tid)` in the route (each table: size, time, SHA-256; a folder: its table count; the app's version), include journal / provenance. Report step: the journal and iterations on screen. Tests: test_sweep +1, e2e +1.
- 2026-11-01 · S09: index.css `.app` grid-template-columns minmax(0, 1fr) (the top row's min-content made the app 1047 px wide at 1024 - every area cut), the search trigger icon-only under 1100 px; sweeps.css: the plot's bar wraps (was nowrap + overflow-x), the step foot wraps, step buttons shrink (min 96 px, ellipsis), `.sw-wide` / `.sw-narrow` labels under 1180 px (follow, re-run), the maps' grid columns min(380 px, 100%). e2e +1 (1024 px: app width, the foot's buttons apart, the bar not scrolling).
- 2026-11-01 · S10: svcore map_for returns goal / direction / bestAt and no cell numbers without a goal; MapSpec.color (share | goal; default goal when the goal has no conditions); MapView: per-map key (MapKey), colour by the best goal (better = bright either direction, grey: none holds), ★ at bestAt; ResultsSide `BestSet` (rank 1: parameters, goal, score / robust goal, *Open it*); fig_map(color, labels) with a colour bar and the star; mapList keeps color. e2e +1.
- 2026-11-01 · S11 / S12 / S18: PlotStyle (view.style: cmap, size, opacity, grid, minor, numbers) + StyleMenu (maps, points, effects); colors.ts CMAPS / rampOf / rampCssOf; ScatterView: axes' titles, grid + minor, round points of the size and opacity chosen, `scatterList` (view.ts) shared with the report; EffectsView: titles, grid + minor, the share holding under the ticks; report: `style_of`, fig_scatter (points in the report), fig_effects titles + grid, fig_map cmap / numbers; ReportReq scatters / style / colorBy. Tests: test_sweep +1, e2e +1.
- 2026-11-01 · S19: evaluate adds #obj1.. (each further objective's worst case, group goal); state `optAxes` (goal, rank when not empty, score, objectives) in defaultAxes and `withNewOptAxes` (only those that just appeared - not those the user took off); colLabel #objN; the table's default columns take #objN; ScatterView: + Pareto (#goal x #obj1), the front ringed and joined, a dragged rectangle -> setFilter on its two columns (ranges by the scale's inv; categories by their codes), a click clears them, a toast to the lines. Tests: test_sweep (+#obj1), e2e +1.
- 2026-11-01 · S13: ParallelPlot's slider (a range under a plot wider than the screen, synced with scrollLeft; `sliderLabel` = axes a-b of n), in the results and the raw step. Checked on 59 columns in Hebrew, dark. e2e: many_columns + the slider (End / Home, the label, gone with Fit).
- 2026-11-01 · S14: report format plot takes `only` (set indices; out of range dropped) and cuts the answer to them; exportPlot(…, only); SetsTable's Export menu: the sets as an interactive plot. Tests: test_sweep +1, e2e +1.
- 2026-11-01 · S15: view.axesOff (newest first, 8 kept; not undone); state `setAxes` (remembers what left) used by toggleAxis and the picker; PlotToolbar's *Taken off* row (+ name, × forget); the picker's label *add / remove*. e2e +1.
- 2026-11-01 · S16: suggest() returns `taken` (per kind, of the suggestions) and `budget`; the round-robin was already a fair share - now said (swBudgetShare); NextRunsView: found / taken per kind, *up to N × M = R runs*, after: *N × M = R*, fewer than asked -> why. Tests: test_sweep +1 (sums, a budget of 3 = one each in order), e2e +1.
- 2026-11-01 · S17: svcore export `write_rows` (by the file's ending: .csv / .tsv / .json / .m struct array / .py list of dicts; numpy scalars as plain values, NaN -> NaN / None); /api/sweep/suggest/export `combos` (False: the sets alone); NextRunsView: same-in-all line + only the changing columns (toggle), an export menu (run list / sets alone x formats), copy as TSV. Tests: test_sweep +1, e2e +1.
- 2026-11-01 · S20: journal.ts `reportJournal(log, final, start)` - from the last reset / the start line; final: the last line of each key (found among hidden lines too: hiding the last version leaves the thing out, it does not bring back the one before), roles netted per column, keep / exclude replayed against scopeBack, goalAdd / goalRemove and a removed goal's lines out, things that ended as nothing out; opening a file writes no line; LogEntry.hidden + hideJournalLine; view.journalAll / journalStart; Report step `Journal` (final / everything, × ↺ ⤒), the iterations box apart (.sw-iterations); ReportDialog uses reportJournal. e2e +1, the S08 test adapted.
- 2026-11-01 · S22: BestSet.tsx (out of ResultsSide - GoalsStep imports it; ResultsSide imports GoalsStep, so no cycle); the Goals step's foot: how many hold + BestSet; *Open it* goes to the results with the set pinned. e2e +1.
- 2026-11-01 · S21: sweeps/explore.ts (Draft, draftOf, structureKey - the server answers once per structure, sliders applied here; with robustness the values too, 250 ms after a move; `explore` = funnel, each control's own cut, ranking (one objective by its worst case; several by a weighted score of each one's place among the survivors), the Pareto front on the first two; `goalOfDraft` - limits and thresholds as conditions; an "or" goal cannot take them: refused with a message); comparisons tolerant to Float32 (0.2 is 0.20000000298: a limit <= 0.2 had left out the sets at 0.2 the server keeps - found by the e2e checking that the saved goal holds for what Explore showed); ExploreView (funnel, sliders with a histogram strip, two-thumb limits, objectives with direction / weight / threshold, the best set, Pareto scaled to the sets left, candidates with margins), view.explore keeps the draft (not undone, not journalled: the save is the step); Center `explore`; ConditionRow offers parameters too. e2e +1.
- 2026-11-01 · S23: ExploreButton.tsx (Goals side under the goal's name, Results side under the best set); ExploreView: limits for every numeric parameter (`withLimit` / `isLimited`: back at the whole range = no limit), weight + threshold sliders always (`thresholdOf` / `thresholdOffEnd`: the far end is off), conditions editable / added / removed in the draft; `draftStudy` + `exploreAxes` + `limitMarks` in explore.ts; ParallelPlot `keep` + `data-shown`; SetsTable `draft`; Candidates gone (the table has the margins); swExploreMargin / swExploreLimitsPick removed. e2e +1 (the acceptance list), S21's adapted. Checked: the whole e2e suite (34 files, one per process; test_globe3d needs ~2.5 min) green - test_features once had one failure (test_compare_same_segment_across_runs, Recordings) that passed alone and on a rerun of the file in order: a flake, not this change; backend 898 passed, mypy clean, tsc, oxlint 51.
- 2026-11-01 · S24-S27 queued: what S23 left in Explore (a new condition's start, the table's sort / columns - owner's choice, the axes in Explore's lines, the Windows / macOS check).
- 2026-11-01 · Release 1.17.0 prepared: version in version.py, build.bat, CITATION.cff (+ date), the installer, version_info.txt, install.md; CHANGELOG 1.17.0 (the highlights now lead with Sweeps - the old line predated it); README review: README (highlights, a Sweeps section with docs/images/23_sweeps_explore.png, `sweep` in the CLI lines, the Hebrew part), GUIDE / GUIDE.he chapter 12 *Sweeps* (the guide is in the app, F1), features.md *Sweeps* (+ `sweep` in the CLI row), command-line.md `sweep` (it was not documented; its output from the example), index.md card, gallery, limitations (Explore's, S24 / S26 included), install.md ~280 browser tests (was ~195), validation regenerated (23 / 23); tools/make_readme_media.py copies the examples' folders (it stopped on examples/investigate/) and makes 23_sweeps_explore (`--only 23`; the other pictures not retaken). Here: backend 898 + 12 skipped, mypy clean, tsc, oxlint 51, build, mkdocs --strict (anchors checked), e2e: the whole suite on S23 (281; one flake in test_features, see S23's line), after the release changes test_file_help_menus, test_fresh_user, test_workflows, test_sweeps_flow; frontend/dist rebuilt.
- 2026-11-01 · Q124-Q126 queued from the owner's notes: a new signal (ƒ) in the investigation (the derived run is left out of *What changed first* and the others' file scopes); a signal slower than its recording (detect, its updates - by change or N Hz - as a part of the per-signal edit, operations over the updates); an update flag choosing a value's samples (the same mechanism, the flag read by previous sample). Two owner's choices marked.
- 2026-11-01 · Owner's answers: Q125 in place (+ tag; `phase` / `delay` in the rate mode); Q126 widened to an update clock (+ *like another signal*, set for a selection); the flag kind still open. Q127-Q129 queued (operations by the selection, the same formula for other indices, typed values in Explore). docs/dev/SWEEPS_MODEFRONTIER.md: modeFRONTIER's capabilities against Sweeps, MF01-MF10 and a design.
- 2026-11-01 · SWEEPS_MODEFRONTIER.md revised from web sources (findings marked verified / unverified, capability map corrected, licences of open replacements); decision: a group of designs is the central concept, three areas (Problem, Run, Explore) instead of five stages; MF00 and MF11 added; §6 is the brief for the implementing agent.
- 2026-11-01 · MF00 part 1: groups of parameter sets - set ids from parameter values, live rule (the axes' filters, compared as Float32 like the page) or frozen ids, automatic groups (all / holds / Pareto / fails = complete and not holding / error = an output missing / suggested), ∪ ∩ ∖, status per set, failed conditions per set; `view.groups` + `view.activeGroup` optional in .svsweep, in undo; pytest 904 passed, mypy clean, tsc + build clean (dist not committed). Left for part 2: Explore's groups panel (colour, name, count, eye, active, menu), *Save as group* (Shift: frozen) from the brush, the table's status stripe / failed cell / ≈ virtual / group chips / checkbox *marked* vs pinned, colour by group, i18n (he/en), an e2e that an old .svsweep opens with the automatic groups only. Note: "fails in k of n" needs the condition's `needed` sent with the answer (evaluate.py has it; not in the answer's columns yet).
- 2026-11-01 · MF00 part 2 (done): groups panel (results side), Save as group (Shift frozen), rename / freeze / ∪ ∩ ∖ with the active group / eye / delete, marked = the table's ticked sets, colour by group (`#group`), hidden groups through scopeMask; table status stripe, ≈ virtual, failing cells, "fails in k of n" (evaluate.py sends `needed` per condition), group chips; i18n en/he; CSS on theme variables (no --warn exists: amber for fails). pytest 905 passed, mypy clean, tsc + build clean. e2e test_sweeps_groups.py written, not run (no Chromium here) - first thing to run. Next: MF01.
- 2026-11-01 · MF01 + Q129 (done): NumField on every Explore value (typed, outside the results kept and marked, Esc, arrows); Explore *Sliders | Table* (`view.exploreAs`), ProblemTable on the same Draft; categorical parameters - `Draft.levels` → condition `in` (evaluate.py `_condition_in`, set_rows' why, label `p ∈ {…}`); ConditionRow / goal summary show it. pytest 906 passed, mypy clean, tsc + build clean. e2e test_sweeps_problem.py + test_sweeps_groups.py written, not run (no Chromium here) - run both. Next: MF02.
- 2026-11-01 · MF02 part 1: Charts tab (Desk.tsx): 1/2/4 panes - points, bubble, histogram (brush), box, scatter matrix (Pearson / Spearman), broken conditions (click = keep the failing sets); `view.desk` optional and undoable; stats.ts checked by hand in node (Pearson ±1, ties in ranks, quartiles). tsc + build clean, pytest unchanged (906). e2e test_sweeps_charts.py written, not run (no Chromium). Left: lines / map / history / Pareto / comparison as pane kinds, a group per pane, the three areas.
- 2026-11-01 · MF02 part 2 (done): pane kinds lines / map / history / Pareto / compare sets; a group per pane (DeskPane.group, view.ts groupRows; ScatterPanel takes it too). tsc + build clean. e2e test_sweeps_charts.py extended (every kind, a group per pane), not run (no Chromium). Next: the three areas.
- 2026-11-01 · MF02b three areas: StepNav = area bar (Problem | Run | Explore) + the area's steps (data-area / data-step); `Step` gains "run" (RunArea.tsx, quiet; outside Back / Next); `areaOf`, `AREA_STEPS` in model.ts; Explore tab → *Decide*. e2e: `_step` goes through the area; *Decide* in two tests; new test_three_areas_and_a_quiet_run. tsc + build clean. Not run here: e2e (no Chromium) - the default screen changed, so the whole suite. Note: the button *Explore this goal* (Results side) still says Explore; rename it with MF10 (Decide).
- 2026-11-01 · MF05 (done): sensitivity.py (correlations, ANOVA shares, Sobol first / total from data), /api/sweep/sensitivity, SensitivityTable in *Which parameter matters*; Ishigami test passes on a 12^3 grid. pytest 912 passed, mypy clean, tsc + build clean. e2e test_sweeps_sensitivity.py not run (no Chromium). No new dependency. Next: MF03.
- 2026-11-01 · MF03 (done): doe.py (scipy.stats.qmc; no new dependency), /api/sweep/doe, DoeSheet in the Run area (vary / hold, method, preview, export run list, group of ids). pytest 920 passed, mypy clean, tsc + build clean. e2e test_sweeps_doe.py not run (no Chromium). ROADMAP: Milestone 23's combined lines split, one task per line. Next: MF04.
- 2026-11-01 · CI opt-in on push (`[ci]` in the last commit's message or Run workflow; PRs always; docs site not rebuilt for docs/dev). Releasing: step 0 = run ci by hand.
- 2026-11-01 · MF04 (done): surrogate.py, /api/sweep/surrogate/{train,grid,optimise}, SurrogateView (*Model* tab); requirements-sweeps-opt.txt + extras.ALWAYS_OPTIONAL + make_pypi reads it; requirements-dev and ci install it. pytest 929+ passed, mypy clean, tsc + build clean. e2e test_sweeps_model.py not run (no Chromium). Owner's choice open: put scikit-learn in requirements.txt (the installer gets Kriging, ~+40 MB) or keep it optional.
- 2026-11-01 · MF06 + MF11 (done): runner.py (template split then filled - no shell; json / csv / stdout parsers; parallel, timeout, Stop kills; results CSV with run_status / run_seconds; resume), /api/sweep/run/{preview,start,<job>} on app/jobs.py, RunStepPanel (step form, preview, which sets, monitor: counts, histories, live Pareto, failures, auto-merge). pytest + mypy clean, tsc + build clean. e2e test_sweeps_run.py not run (no Chromium). Note: the merged results add run_status / run_seconds columns (roles guessed; set them to Not used if wanted). Next: MF07.
- 2026-11-01 · Q130-Q138 specified (investigating signals: clusters, likely first, plot beside each, less noise, chains, different from the other runs, consistent precursors, report) - Milestone 24, after Milestone 23.
- 2026-11-01 · MF07 (done): optimise.py (DE, NSGA-II, model-assisted, auto), /api/sweep/optimise/start through runner.run_all (Live: gen, best), OptimiserPanel + the run Monitor (onDone → group). pymoo rejected at the licence gate (moocore LGPL-2.1+). pytest + mypy clean, tsc + build clean. e2e test in test_sweeps_run.py not run (no Chromium). Next: MF10.
- 2026-11-01 · e2e, first browser run of the M23 files (whole suite, one file per process, on the build of this round): fixed in the tests - Decide is the tab's name (MF02b), 18 scenario combinations in the example (not 36: doe, run), the run template's placeholder is the column's name, wait for a pane's drawing and for a study to finish opening (charts, groups: end states), the robust row's first select. test_features::test_globe_without_webgl_falls_back failed once in the full file and passes alone (order-dependent, Recordings - not this round's change; watch it). Everything else green.
- 2026-11-01 · MF10 (done): svcore/sweep/mcdm.py, /api/sweep/mcdm, DecidePanel; tests by hand-worked tables + AHP; e2e test_decide_ranking_methods_pairwise_and_a_group. The table / best set still rank by the weighted sum; the panel's ranking is kept as a group.
- 2026-11-01 · MF08 (done): svcore/sweep/robust.py (extends question.robust with `dist`), /api/sweep/robust/{sample,model,stats}, RobustSheet (Run area); [U] sampling options verified on ESTECO's pages (§1 updated, D-optimal still [U]; polynomial chaos / FORM not done). pytest +7, e2e test_sweeps_robust.
- 2026-11-01 · Owner: scikit-learn into requirements.txt (licences re-read in the wheels, BSD-3); requirements-sweeps-opt.txt removed; ALWAYS_OPTIONAL = desktop only.
- 2026-11-01 · Refresh of a growing file (owner's report): csv_loader `_Bounded` / `_complete_part` (parsers and the text pass read the size seen at the start; a half-written last line waits while the file grows), store.open_file keeps the stat from before the read. tests/test_growing_file.py (fails on the old code: the read followed the writer, the refresh said unchanged).
- 2026-11-01 · MF09 (done): svcore/sweep/clusters.py, /api/sweep/clusters, ShapePane (Charts kinds pca / som); pytest +7, e2e +1. Milestone 23 done. Next: Q130.
- 2026-11-01 · Q130-Q133 (done): svcore/firstchange.py `uninformative`, `WEIGHTS` / `score_parts` / `score_of`, `clusters`; store.change_clusters (the reference runs, the event's signal - the page sends the plotted one most unusual in the span -, the shape by `lag` for the 30 likeliest with room on both sides); /api/firstchange gains `refs`, `event` -> `clusters`, `event`, `weights`, `skipped`; spark 120 points. WhatChanged: clusters (closed, the likeliest open), the order, the score and its parts, ClusterPlot, Open as a tab / Add to the investigation (journal "Changes together..."), names by message, the left-out list, keyboard. Tests: test_change_clusters (+4: two clusters by gaps, a leading step above a bigger blip after and a change the reference has, constant / counter / clock / heartbeat, the route), e2e test_what_changed (10: the old ones read the list By time with every cluster open; +2 new). On the Investigate demo: Wind's cluster first, then Motor3 / Battery_V / Motor1, Vibe_Z, Roll (the event) last.
- 2026-11-01 · Q134 (done): store._chain, Chain in WhatChanged; pytest +1 (A -> B -> Event, no edge to a lone blip), e2e +1 (Motor3 -> Roll 80-180 ms, a node opens its cluster).
- 2026-11-01 · Sweeps redesign (owner: "a mess - redo it simply, not more and more"; then "remove the old things"): StepNav four steps (normStep maps clean / report / run), CenterTabs five tabs (normCenter), GoalTable (at least / at most per column = conditions mode "all"; optimize per output), RolesStep with the clean tools (constant -> not used; removed columns shown as not used), undo / redo in the plot bar. Deleted: CleanStep, ExploreView, DecidePanel, ExploreButton, EffectsView, SensitivityTable, SurrogateView, HealthView, CompareView, RunArea, RunStepPanel, DoeSheet, OptimiserPanel, RobustSheet, NumField, sweeps/explore.ts; e2e test_sweeps_{run,model,sensitivity,robust,doe,problem} and the flow tests of removed tabs; e2e +1 (four steps, five tabs, the goal table).
- 2026-11-01 · Sweeps cleanup (owner: "delete everything old that is not used"): backend svcore/sweep/{doe,surrogate,sensitivity,runner,optimise,robust,mcdm,compare,quality}.py, 15 endpoints and their tests (test_sweep_{doe,mcdm,optimise,robust,runner,sensitivity,surrogate}; test_sweep's suspects / compare tests), scikit-learn out of requirements.txt and extras (sweeps-opt gone); frontend: the unused sweepApi calls and types, view.runStep / exploreAs / explore, ScattersView, idOfParams / paramsOfId, CENTERS, ROLES / SCALES, 307 strings, 175 style rules (the ones made from a value - sw-mark-<kind>, sw-th-<role> - kept); README, GUIDE / GUIDE.he 12, features, index, gallery, limitations on the four steps; docs/images/23_sweeps_goal.png (tools/make_readme_media.py --only 23) for 23_sweeps_explore.png; SWEEPS_MODEFRONTIER.md marked as history.
- 2026-11-02 · Checks after the redesign and the cleanup: backend 920 + 12 skipped, mypy clean, tsc, build, mkdocs --strict, the whole e2e suite one file per process (all green; test_sweeps_flow 31, test_sweeps_groups 2, test_sweeps_charts 4).
- 2026-11-02 · Owner's answers (commit "Live in the Recordings bar..."): TopBar's Live group (Live, its settings, the MAVLink pill) moved to RecordingsBar beside undo; the Sweeps report without *Which parameter matters* (sweep_report.fig_effects, svcore sweep.effects, swCenterEffects removed), Map / Points from the Charts' panes on screen and next runs' maps (reportFigures in ReportDialog, a count beside each box, disabled with none; scatterList removed, mapSpec to sweeps/view.ts); GUIDE / GUIDE.he / features.md; S24-S27 closed. Tests: backend +1 assertion, e2e test_file_help_menus (Live only in the area bar), test_sweeps_flow (the report's boxes and figures), the Live selectors of test_features and test_workflows (the CI smoke set).
- 2026-11-02 · Release 1.18.0 prepared: version in version.py, build.bat, CITATION.cff (+ date), the installer, version_info.txt, install.md (+ ~930 server tests); CHANGELOG 1.18.0 (highlights; Changed / Added / Fixed); README review: README, features.md, limitations, gallery already describe the four Sweeps steps (the redesign's commit) - Live, Templates and Clear now said to be in the Recordings bar; pictures not retaken (23_sweeps_goal.png is from the redesign); validation regenerated (23 / 23, the version). Here: backend 920 + 12 skipped, mypy clean, tsc, oxlint 54 (as before), build, mkdocs --strict; e2e: test_file_help_menus, test_sweeps_flow (31), test_sweeps_charts, test_features -k live / mav / follow (6), test_fresh_user, test_workflows; frontend/dist rebuilt.
- 2026-11-02 · The v1.18.0 tag's build failed on Windows only: test_a_half_written_last_line_waits_while_the_file_grows wrote with `write_text` (CRLF on Windows) and compared with a length in `\n`s - the code was right (it stopped after the last complete CRLF line). The test writes bytes now and checks both `\n` and `\r\n` on every platform. Nothing was published (pypi-publish and release need every build), so the version stays 1.18.0: the owner moves the tag to this commit. Backend 921 + 12 skipped.
- 2026-11-03 · Owner's spec, Data + Columns (patch sweeps-data-columns): backend sweep.combine / combine_preview / build / recipe_files (svcore/sweep/io.py), /api/sweep/combine, build, drop, values, formula-preview, export-table; summary with holdValues (rowsAll); reload / changed / provenance through a table's recipe; MAX_TABLES 12; the HTML plot starts from the view on screen and zooms. Frontend: Study.tables / use / shown / picked, RawStep and RolesStep rewritten, DerivedEditor (completion, preview, edit), ParallelPlot zoom (sweeps/zoom.ts), narrow window (sweeps/narrow.ts), FileBrowser "Save as type", template summary (sweeps/templates.ts). Checked: backend 926 + 12 skipped, mypy, tsc, build, oxlint 54; e2e test_sweeps_flow 26 / 31 with the updated tests - left: test_new_column... (fixed, not rerun), test_undo_redo_and_the_studies_open_again, test_many_columns_scroll_pick_and_panels, test_templates_dialog_save_replace_export_import_apply; new e2e for join / Continue with / condition cards / Template / narrow window still to write; the rest of the suite not run.
- 2026-11-03 · Release 1.19.0: version in version.py, build.bat, CITATION.cff (+ date), installer (iss, version_info), install.md; CHANGELOG 1.19.0; README, features, GUIDE / GUIDE.he, gallery; pictures 23_sweeps_goal (again), 25_sweeps_data, 26_sweeps_split (tools/make_readme_media.py --only 23_sweeps 25 26); validation regenerated (23 / 23); ROADMAP. Split by completed (groups per value, re-runs with their value, the report); Next runs' split; Charts' high-resolution PNG and HTML; derivative / integral on a signal's updates; plot images for a report and as HTML.
- 2026-11-04 · 1.20.0 the owner's notes (legend, made signals, groups, track colour, fleet example, Sweeps Pareto / Clear) · branch owner-notes-1.20 · backend 943 + e2e all files pass; new test_owner_notes_1_20.py.
- 2026-11-04 · 1.20.1 Borders over the offline map and the satellite photos · branch borders · test_offline_map (+1), map / settings / owner notes e2e pass.
- 2026-11-05 · 1.21.0 Filter review, Step response, Hardware, compare time tolerance; review fixes (sync confirmation and why, old STATUSTEXT scale, PreArm, ERR/EV, motors, battery limits and timer, units, CSV decimal comma / ISO dates / no time column, compare tolerance, file-dialog Esc, Copy, template fit) · backend 983 pass; e2e 303 pass (new test_release_1_21.py), 2 fail as before (test_one_place_for_each_control fails on main too; test_borders… passes alone - a canvas timing).
- 2026-11-07 · Patch 0: the owner's plan U1–U8, M1, A1–A3 in TASKS.md (spec, board) and ROADMAP.md (Milestone 25); CLAUDE.md e2e rule: relevant files per task, whole suite per group / at the end · docs only, no tests needed · next: U1.
- 2026-11-07 · U1 a template's default tabs, the rest in "+N more" (`defaultTabs`, `ws.moreTabs`, TabChoice dialog, Settings `tplTabChoice`) · backend all + mypy; e2e test_template_tabs, test_fresh_user, test_workflows, test_templates_recent_badfiles, test_settings, test_features -k template · next: U3.
- 2026-11-07 · U3 the tab's lanes once above its plots (TabBand.tsx, `tabBandLanes`, `xViews`, `plot.ownBand`), the cursors and hover on it and on the overview strip; U7 gets the flags-vs-events look (owner) · backend all; e2e test_tab_band, test_state_lanes, test_overview_strip, test_template_tabs, test_plot_menus, test_timeline, test_workflows, test_aligned_plots, test_globe3d, test_map_objects, test_conditions, test_what_changed, test_features -k lane/state/cursor/overview/mode · next: U2, then the whole e2e suite (end of group 1).
- 2026-11-07 · U2 the findings docked beside the timeline (FindingsDock), ◆ marks on it (`findingMarks`, plotFinding) · e2e test_workflows, test_features -k smart_start, test_fresh_user, test_findings_report, test_timeline · owner: one combined patch for the round, the whole e2e suite at the very end · next: M1.
- 2026-11-07 · M1 hero (img_00_hero, 3200 x 1800 dark), social preview cropped from it, README order; the tagline waits for the owner · next: A1.
- 2026-11-07 · A1 store.py 1,495 -> 850 (svcore/investigate.py, app/livewatch.py, app/filecheck.py, svcore/transforms.py) · pytest 978, test_investigate (5); Investigate / live e2e · next: U6.
- 2026-11-07 · U6 ghost on the map / 3D from `s.pointer` · e2e test_hover_ghost, test_globe3d, test_map_objects, test_tab_band, test_owner_notes_1_20, test_object_frames, test_features -k legend/hover/cursor/map/geo · next: U4.
- 2026-11-07 · U4 setpoints dashed and faded by themselves (desired.ts, `PlotSignal.dash`, Inspector ▸ Line) · e2e test_setpoint_style · next: U5.
- 2026-11-07 · U5 the difference view in Compare (`trace`, DiffChart.tsx, ✓ / ✗) · pytest 981; e2e test_compare_diff, test_workflows -k compare, test_features -k compare/tol · next: U7.
- 2026-11-07 · U7 less clutter (85 buttons / 59 controls in the ArduPilot example, from 107) · e2e test_less_clutter, test_features (all), test_workflows, test_template_tabs, test_object_templates, test_templates_recent_badfiles, test_overview_strip, test_fresh_user, test_plot_menus, test_tab_band, test_state_lanes · next: A2.
- 2026-11-07 · A2 i18n.ts -> i18n/ (11 area files + index, 1,785 keys, none over 600 lines) · tsc + build · next: A3.
- 2026-11-07 · A3 App.tsx 632 -> 434 (Welcome.tsx, rail.ts, PlotGrid.tsx, shortcuts.ts) · e2e as listed in A3 · next: U8.
- 2026-11-07 · U8 docs/dev/NAVIGATION.md (options A / B / C, A recommended, 3 questions) · next: the whole e2e suite, then the owner's answers (tagline, U7 measure, U8 option).
- 2026-11-07 · The whole e2e suite (one process, 16 min here): 313 passed, 1 failed - test_offline_map::test_borders_over_the_offline_map_and_the_satellite_photos, which fails the same way on origin/main in this environment (the canvas the same after toggling borders off and on) - to check on the owner's machine. Backend 981 passed; mypy: only the 4 known errors in routes/analysis.py (numpy 2.5 here, also on main). Sent as one patch (U3..U8) on d4c0f61.
- 2026-11-07 · Owner: tagline approved (applied), U8 option A approved (next: U9), U7 - keep the strip's mode row and its picking ("it marks the region of interest; more modes can be added there and the intersections highlighted"): the measure is the controls (< 70), done.
- 2026-11-07 · U9 navigation option A (areas switch with Fleet, views menu, fixed rail) · e2e test_navigation + the files that follow · next: release 1.22.0.
- 2026-11-07 · Release 1.22.0 prepared: version in build.bat, version.py, CITATION.cff (+ date), the installer (iss, version_info), install.md (+ ~980 server / ~320 browser tests); CHANGELOG 1.22.0 (highlights; Added / Changed / For developers); README (tagline, hero, compare / fleet bullets, the Hebrew part), features, limitations, GUIDE / GUIDE.he, fleet tutorials; validation.md regenerated; pictures and clips from tools/make_readme_media.py (all but 06 and the 02 clip, as before; its scenes follow U2 / U7 / U9: the findings dock, closed groups, the Fleet area; a MAVLink link stopped between scenes) and the social preview from the hero. frontend/dist not committed (build.yml builds it). `mkdocs build --strict` passes.
- 2026-11-07 · The whole e2e suite on 1.22.0 (16 min here): 312 passed, 3 failed - two were tests still expecting the old navigation (the Log button gone for a CSV, two areas), updated (test_features, test_sweeps_flow) and passing; test_offline_map's borders test fails on origin/main here too. Backend 981 passed.
- 2026-11-07 · ci failed on the 1.22.0 push: mypy, the 4 errors in routes/analysis.py (the course step `k` reused after an index array; numpy 2.5's stubs on the runner) - renamed `step`; mypy clean, backend 981 passed.
- 2026-11-07 · 1.22.0 re-release (owner, after the tag, before publishing): two MODE rows on top in the ArduPilot example (the strip's default row and the tab band) -> the band leaves out what the strip shows (`stripLanes`, published by OverviewStrip), the strip's rows name the mode under each cursor line (`.ov-cur-tag`, `.ov-phase.at`); the automatic map is OpenStreetMap in both themes (was dark grey in the dark theme); every README picture / clip in the dark theme (make_readme_media `page(dark=True)`); the hero with OSM and the 3D zoomed / tilted - but the sandbox has no internet for tiles, so 00 / 05 / 28 are to be retaken on the owner's machine (`--only 00 05 28`, then make_social_preview.py); the docs site's first picture is the hero. Tests: test_tab_band rewritten.
- 2026-11-08 · 1.22.0 re-release, the map pictures retaken with the internet (00 / 05 / 28, social-preview). The hero's 3D was empty: the wheel zooms toward the mouse, which was at the plot's middle, not on the track, so 3 steps went down into the ground beside it -> `img_00_hero` waits for the 3D tiles, points the wheel at the track's middle (projected from the scene's track lines) and takes 2 steps: the whole track, tilted (General camera, -35 deg). 05's 3D was shot before its tiles were refined (blurred) -> it waits for `globe.tilesLoaded`. Checked: one MODE.Mode row above the plots, the automatic map is OSM in the dark theme. Tests: backend pytest, mypy, tsc; e2e test_tab_band, test_template_tabs, test_overview_strip, test_map_objects, test_globe3d (22 passed).
- 2026-11-08 · Round of 2026-11-08 started (owner's audit: C, O, P, A, U, T, F); baseline at `77aaa4a`: backend 981 passed / 14 skipped, validate 23 / 23. C1 done: Compare judged on the union of both runs' samples (svcore/compare.py); tests: test_compare_fullres (new), test_checks (+1), compare / checks / sync / real logs files - 115 passed, 13 skipped; mypy compare.py clean. Next: C2.
- 2026-11-08 · C2 done: state signals held (`analysis.hold_to`) in formulas, operations and conditions; the copter example's mode condition is [46.41, 60.41], no formula value outside the mode's values; tests: test_state_hold (new) + 16 related files, 185 passed; validate 23 / 23; mypy clean on the changed modules. Next: C3.
- 2026-11-08 · Interim patch signalviewer-phase1-partial-2026-11-08.patch (C1, C2) checked with `git am` on a fresh clone (32 tests of the changed areas passed there). C3 done: `params.nan` (propagate / skip / legacy), restored recipes without it are "legacy"; tests: test_missing_policy (new) + 22 related files, 259 passed; validate 23 / 23; mypy clean. Next: C4.
- 2026-11-08 · C4 done: V24-V28 in validate (28 / 28), docs/validation.md regenerated; V29 moves to P1 (it would fail until the offset copy is gone). test_validation 32 passed. Phase 1 patch next.
- 2026-11-08 · Owner applied the Phase 1 patch (`3110e75`). O1 done: Automatic = offline map, Never use the network (setting + SV_OFFLINE=1, checked in tiles.py), the Online map sign; tests: test_offline_switch (new), test_basemap, test_app_folder; e2e test_offline_map (+2), test_settings, test_globe3d, test_map_objects; tsc + build; mkdocs --strict. Next: O2.
- 2026-11-08 · Owner answered the five questions (IDs approved; C2 old sessions keep their numbers - C2b; conditions change accepted; skip choice in Create signals - C3b; next version 1.23.0). Patch signalviewer-O1-2026-11-08.patch sent (O1 only, on `3110e75`). O2 started: only read (make_test_bin.py --corrupt exists; backend/tests/data/sample.ulg; routes/files.py turns unexpected errors into "Unexpected error while reading the file").
- 2026-11-08 · Owner applied the O1 patch (`4c3c52f`). C2b done: restored recipes without `hold` get false, new ones true (`HOLD_OPS`); tests: test_state_hold (+1) + 10 related files, 129 passed; validate 28 / 28; mypy clean. Next: C3b.
- 2026-11-08 · C3b done: *Missing values* in Create signals (sum / mean / min / max / norm / integral), the derived list marks skipped / bridged / unknown / infinite; tsc + build; e2e test_missing_choice (new, 2), test_update_rate, test_features + test_workflows (154 passed). Next: O2.
- 2026-11-08 · O2 done: .bin - the message before a damaged block and damage-only instances left out (0 phantom signals in 60 fuzz seeds, was 31); .ulg - damaged parameters / messages / time stamps left out, the log opens; unexpected loader errors say what to do; tests: test_damaged_files (+20) and 28 related files, 482 passed; validate; mypy; tsc + build; e2e test_damaged_note (new) + 3 files. Next: O3.
- 2026-11-08 · O3 done: `atomic_path` / `atomic_open` / `atomic_write` (app/atomic.py, from app/common.py) for sessions, autosave, templates, settings, readers / layouts, reports, Recordings' saves, Sweeps' study / templates / report; tests: test_atomic_write (new, 5) + 42 related files, 829 passed; mypy; e2e test_workflows, test_findings_report, test_template_tabs. Phase 2 done; patch next.
- 2026-11-08 · Owner applied the Phase 2 patch (`a39b8d5`). P1 done: `signal_parts` / `view_shifted`, the per-request routes shift the window (20M samples with an offset: 51 -> 3.7 ms, 160 -> 0.2 MB; stats 458 -> 2.6 ms); V29 in validate (29 / 29); tests: test_offset_nocopy (new, 7) + 14 files, 190 passed; mypy; e2e test_what_changed, test_aligned_plots, test_features -k offset (23). Next: P2.
- 2026-11-08 · P2 done: svcore/memcache.py (`ByteLRU`, SV_MEMCACHE_MB 1024) for transforms, derived, FFT, summaries, stats; the transform-cache race fixed; Settings ▸ Storage shows memory; 12 x 20M changed signals 1832 -> 916 MB; whole backend suite 1049 passed; validate; mypy; tsc + build; e2e test_settings, test_offline_map. Next: P3.
- 2026-11-08 · P3 done: AbortController in api.ts / TimeChart, binary /api/data (`pack_series` / `unpackSeries`), `y_reference` for /api/data (bin) and /api/xy (relative), joinTables.ts (30 signals 162 -> 77 ms); backend 123 related tests; mypy; tsc + build; e2e test_data_path (new) + 8 files; borders test fails on origin/main here too (network). Next: P4.
- 2026-11-08 · P4 done: app/openmany.py + common.open_paths (thread pool, memory budget SV_OPEN_BUDGET_MB, order / names / tags kept); 4 x 55 MB .bin 2.13 -> 1.42 s on 2 cores; tests: test_open_many (new, 5), whole backend suite 1056 passed; mypy; e2e 5 files + test_features -k open. Next: P5.
- 2026-11-09 · P5 done: `tools/benchmark.py --synthetic` (offset ratio, 30-signal zoom, pan burst, .bin + changed signals vs the memory cache, live wide append) with targets; the file mode fixed (403 since the localhost check); docs/performance.md. Phase 3 done.
- 2026-11-09 · O2 follow-up: log index version 3 (an index from before O2 kept phantom signals and broke live mode), `DataFlash.__setstate__`; test_big_files (+1, 15 passed).
- 2026-11-09 · Owner: Phase 3 patch not applied yet, continue and send one cumulative patch. 26.A1 done: DerivedSignal, SubplotConfig, subplot_from_dict, Tab, ViewState, SignalType (+ the unused field), the index keys removed; whole backend suite 1056 passed; mypy. Next: 26.A2.
- 2026-11-09 · 26.A2 done: app/subproc.py (shared with pyops), svcore/readerworker.py, readers isolated in the app; tests: test_readers (+2), test_pyops, whole backend suite 1059 passed; mypy; e2e test_user_reader (new). Next: 26.A3.
- 2026-11-09 · Owner: no patches until the release - carry on to the end of the tasks. 26.A3 done: `apply_filter(sampling)`, smooth / rms `seconds`, `smooth_s`, SAMPLING_OPS for old sessions; tests: test_sampling (new, 6), whole backend suite, validate; tsc + build; e2e test_features, test_missing_choice, test_update_rate (130). Next: 26.A4 (size assessment first).
- 2026-11-09 · 26.A4 assessed (39 call sites in 11 files, a sync layer, a session migration, undo moving from toasts to Ctrl+Z): larger than the task - not started, the owner decides. Next: 26.A5.
- 2026-11-09 · 26.A5 done: `ws.readAs` + /api/read_as (held / interpolated, by name, undoable), /api/discrete with why, `angle_units` with why in the object dialog; tests: test_heuristics (new, 3), whole backend suite 1068 passed; mypy; tsc + build; e2e test_heuristics (new, 2) + 5 files. Phase 4 done except 26.A4. Next: 26.U1.
- 2026-11-09 · Whole e2e suite at the end of Phase 4 (52 files, one per process): 4 files with a failure. Fixed: (1) test_one_per_plot "the same again" made 6 signals instead of reusing 3 - since C2b a stored recipe carries `hold` (and `nan` / `sampling`) the request did not, so peers.ts `opKey` did not match; it now completes a request with the defaults the backend writes (`withDefaults`); (2) test_data_path's burst test counted aborts by network events, and its route handler (a sleep) held the test's thread, so the wheel steps waited for it - now the steps come from the page and the aborts are counted in the page (passes twice). Not reproduced: test_features (1 failure in the suite run; 126 passed alone). Known: test_offline_map borders (the network; fails on origin/main here too).
- 2026-11-09 · 26.U1 done: type scale, radii, spacing, semantic colour tokens; literals 45 / 11 / 69 -> 0; test_design_tokens (new); tsc + build; e2e 8 files (19). Next: 26.U2.
- 2026-11-09 · 26.U2 done: colour-blind-safe palette + `ink()` (3:1 in both themes), hover rings, crosshair, the difference chart unstretched with band edges / bottom marks / hover readout, one palette everywhere; tsc + build; e2e 8 files (22). Next: 26.U3.
- 2026-11-09 · 26.U3 done: controls 58 -> 54 (Attitude) / 80 -> 71 (Flight): folded template strip, strip's + / hide on hover, map pickers hidden with an object, 3D image / remove in ⋯; tsc + build; e2e 11 files (see the task). Next: 26.U4.
- 2026-11-09 · 26.U5 done (before U4): per-signal tolerances in Compare, saved / opened as the CLI's --tolerances file; `svcore/tolerances.py` judges for both (outside_pct now in the app too); backend all + mypy; e2e test_compare_tolerances, test_compare_diff. Next: 26.U4.
- 2026-11-09 · 26.U4 done: golden runs (settings), the start card's *Judge it against …*, Compare's verdict per file, worst failure, *Report…* with the verdict section; tsc + build; e2e test_judge_a_run + 7 related files (51). Next: 26.U6.
- 2026-11-09 · 26.U6 done: trust badges (interpolated / filter by stretch / missing data, angle guess) on chips and the derived list, the network in the status bar; backend all + mypy; e2e test_trust_badges + 7 files. Next: 26.U7.
- 2026-11-09 · 26.U7 done: per-signal data quality on open (svcore/quality.py, /api/runs/{id}/quality, note + badge + marks + dialog); backend all + mypy; e2e test_data_quality + 5 files. Next: 26.U8.
- 2026-11-09 · 26.U8 done: one events list (Log panel, + findings / conditions / limits), ] / [ to step, the status bar names the event; tsc + build; e2e test_event_navigation + 3 files. Phase 5 done - the whole e2e suite next.
- 2026-11-09 · T1 done: Vitest (devDependency, reason in the task), 8 files / 24 tests of the frontend's logic, `npm test`; tsc. Next: T2.
- 2026-11-09 · Whole e2e suite (end of Phase 5, one file per process): 328 passed; failed under load, passed alone: test_error_details (setup), test_plot_menus (fixed in T2), test_features 1, test_object_templates 1, test_timeline 1 (T2's first autosave wait - fixed).
- 2026-11-09 · T2 done: 78 sleeps -> 30 (helpers settled / autosaved / until / frames / range_changed), test_quick_view and test_plot_menus fixed, the borders test passes; 14 files green. T3 done: CI npm test, 18 e2e files, benchmarks --check 3. Phase 6 done.
- 2026-11-09 · Final checks of the round: backend 1081 passed (14 skipped), mypy clean, `cli.py validate` 29/29, tsc + build, `npm test` 24, `benchmark.py --synthetic --check 3` all targets met, `mkdocs build --strict` clean. Whole e2e (one file per process): 332 passed; test_features 1 failed while the backend suite ran beside it, 126/126 alone. Cumulative patch: origin/main a39b8d5..HEAD (23 commits), applied on a fresh worktree and checked. Owner to decide: Phase 7 (F1-F4); 26.A4 (larger than the task); golden runs and Compare tolerances kept in the settings / a file, not the session (26.U4/U5); a "skip" choice for formulas' missing values (C3); live mode does not re-check data quality as a file grows (26.U7); the JSON form of /api/data kept beside the binary one (P3); the version number (not changed).
- 2026-11-09 · Release 1.23.0 prepared (Releasing steps 1-4, owner's request): version 1.23.0 in build.bat, app/version.py, CITATION.cff (2026-11-09), the installer (.iss, version_info four places), docs/install.md, docs/validation.md (made again by tools/make_validation_doc.py); CHANGELOG "Unreleased" -> "1.23.0 – 2026-11-09" with a highlights line, its sections merged (Added / Changed / Fixed / Performance / Tests and CI); README reviewed against it (the hero, a "Judge a run" section, Compare / Flight logs / Trust in the list, the Hebrew section), docs/index.md, gallery, limitations (readers in a process; golden runs and tolerances not in the session; formulas keep missing; data quality not re-checked live; the events list in the Log panel), GUIDE.he (tolerances per signal, judging, data quality, ≈, ] / [). Pictures: a new hero (00_hero: the model against the flight, the differences with the ±3° tolerance, the verdict - offline, no map tiles; make_readme_media.py img_00_hero), 1.22's hero kept as 31_flight_map_3d (needs the internet to remake), social-preview cropped again; every other picture and video remade except 05, 28 and 06 / the 02 video (map tiles or real-GPU 3D: owner's PC). frontend/dist built and committed. Left to the owner: Releasing step 0 (run ci by hand), the Windows build, tag v1.23.0 and push.
- 2026-11-09 · v1.23.0's build failed on every platform in backend/tests/test_offset_nocopy.py: `pytest.approx` of the limits result (a dict holding the list of stretches) - approx takes flat values only; here the two results were equal to the bit, so approx was never asked to compare. Fixed: the stretches compared apart, flattened. Checked the whole backend suite with a stricter approx (one that refuses any nested value): no other case.
- 2026-11-09 · Round of 2026-11-09 started (N0): the owner's prompt revised with him and kept as docs/dev/AGENT_PROMPT_2026-11-09.md; "Owner's plan (2026-11-09)" added (order, decisions 1-4, Q1-Q8 with defaults, board); Milestone 27 in ROADMAP. Baseline at `dafea49`: `npx tsc -b` clean, `npm test` 8 files / 24 tests. Fixture examples/three_objects.csv from tools/make_objects_fixture.py. Found while reading: `GPS.Lat [deg]`-style names (N1 must ignore a trailing unit) and ArduPilot names in CSV pair GPS + ATT today (Q8). Checks: tsc, Vitest. Next: N1.
- 2026-11-09 · N1 done: `signalGroups.nameTree` / `pathCuts` - "." and "/" nest at any depth whatever the count (identifier-like segments only; a trailing `[unit]` / `(unit)` ignored; a leading "/" skipped; single-child chains folded into one row; no group of one signal - while searching a single match shows its full name); the heuristics kept for "_" / ":" only; flight logs (bin, tlog, ulg, can) on the old path unchanged. DataPanel walks the tree (`Row.label`; the group's full path in its tooltip; indentation by logical padding, so RTL follows). A group with a plotted signal starts open. Reproduced first: the fixture listed flat at `dafea49`. Checked: copter_flight.bin's list identical before / after (dumped with both builds); uav_flight.csv now nests GPS / ATT. Checks: tsc, Vitest 9 files / 35 tests (signalGroups.test.ts new, 11), e2e test_name_tree (new, 3), test_features -k "S03 or multi_select or group" (2), test_map_objects (4), test_object_templates (4), test_workflows (28), test_owner_notes_1_20 (5) - all green. Owner's Q8 answered (decision 5). Next: N5.
- 2026-11-09 · N5 part 1-4. Detection (`objectDetect.ts`): an object is a prefix with lat + lon (or NED / ENU / ECEF x y z under a position or frame word) at any depth, with "." / "/" or "_"; roles only from its own prefix and its sub-groups (pos / position / lla / geo, att / attitude / euler / angles / ori / q); aliases and unit suffixes (`lat_deg`) and bracketed units read; classes by whole prefix segments, the deepest deciding (`CLASS_WORDS`, `ref` left out per Q2); `KNOWN_GROUPS` for ArduPilot / PX4 / MAVLink in any file (POS + ATT; GPS + ATT only without POS - decision 5); explanations and near misses (suffix `_cmd`, misspelling, glued `posLat`, x / y / z with no frame); `q[0]` is an index, not a unit (also fixed in signalGroups.pathCuts); cached per signal list, 5000 names well under 100 ms. Dialog: *Objects found in this recording* (checkbox, name, class, colour, signal chips, Why?, Advanced…, added), Add all (N) / Add selected in one commit (`actions.addObjects`), the naming note with a copyable example; Advanced… / by hand = the old form, prefilled from the candidate; NED / ENU candidates need an origin (Advanced…). Template: *Position on the map & 3D* adds every LLA candidate; its toast lists them and has Why? (`Toast.action2`) beside Undo. Docs: GUIDE.md, GUIDE.he.md, README, CHANGELOG. Not yet: guessRoles' other callers (frames.ts, PlaceOnMapDialog) still use the old guess. Checks: tsc, Vitest 10 files / 48 (objectDetect.test.ts new, 13), e2e test_map_objects (6, 2 new), test_object_templates (5, 1 new), test_object_frames (3), test_heuristics (2), test_globe3d (10), test_hover_ghost (1), test_features -k object_signals (1) - all green; the existing tests open the form through the new `object_form` helper. Next: N5's looks by class, attitude source, suggestion bar.
- 2026-11-09 · N5 done (the rest). Saved fields, all optional (old sessions unchanged): `MapObject.cls`, `track` ("line" / "dash" / "points"), `attitudeSource` ("own" / "motion" / `{ object }`), `minSpeed`. Backend: `/api/object_track` takes `attitude: "motion"` and `minSpeed` - `motion_attitude` (analysis.py): heading = course over ground, pitch = atan(climb / ground speed) over the course's ~1 s baseline, held below minSpeed (the first valid value before it), no roll; `derived: "motion"` in the reply. A borrowed attitude is the other object's angle signals sent as this object's (`mapObjects.trackRequest`; the server interpolates them the short way round onto its times); no chains, a missing source falls back to motion; an old object with neither stays "none" (its course, drawn filled, as before). Looks: GeoChart dashes / points (`ctx.setLineDash`, dots), Globe3D `PolylineDash`; a derived attitude is an outlined icon (`drawObjectIcon(..., outline)`), a see-through model with a silhouette in 3D, ≈ on the chip (`AttitudeSourceBadge`), a line in *Why?*. Found list: *Attitude* per position-only row (from motion / from another row, linked at Add by `objectAdd.linkAttitudes`); the form: *Attitude* (motion / another object with angles, the primary and truth first), *Hold the heading below (m/s)*, *Track*. Suggestion bar (`ObjectSuggestBar`, file panel above the templates): the newest file with objects not on any map - Add all (`actions.addObjectsToMaps`: every map / 3D of the tab, or a new map; one commit, toast with Undo), Choose…, Why?, × (hidden per file for this run, `objSuggestHidden`). `guessRoles` now takes the file's first LLA candidate of `detectObjects` (the old guess only when nothing is found), so the form's fill-in, frame suggestions (frames.ts) and *Place on map* never mix sources. Templates keep cls / track / "motion" (a borrowed source names a session object: kept as motion). Not done (follow-up): motion from the object's own velocity signals (vel.north/east/down) - the position is differentiated. Checks: tsc, Vitest 11 files / 55 (mapObjects.test.ts new, 7), backend `-k object_track` 7 (3 new: circle course + flight-path angle, hold while hovering, borrowed across 359/1) and `-k template` 230, e2e test_map_objects (8, 2 new: the bar, borrowing), test_heuristics, test_less_clutter, test_object_frames, test_object_templates, test_one_per_plot, test_owner_notes_1_20, test_template_tabs, test_templates_recent_badfiles, test_globe3d, test_hover_ghost, test_name_tree (49), test_workflows + test_offline_map (33), test_features (125 / 126: test_limits_pass_fail_in_the_inspector fails about one run in two - after a reload, also with the build before this change; not related, left for N9). Next: N6.
- 2026-11-10 · N6 measured first (tools/browser_benchmark.py --group smooth: the fixture's three objects added by the "objects found" line, and copter_flight.bin; frame intervals from requestAnimationFrame, React renders counted by `perf.ts` `countRender` - off unless `window.__svRenders` is set). Machine: Intel Xeon 2.1 GHz, 2 CPUs, headless Chromium, no GPU (3D in SwiftShader). Baseline (at c5bf95b): playback on the map 16.7 ms median / 0-1 dropped, but App, DataPanel, PlotView, StageBar, TemplateStrip, StatusBar, TabBand, Timeline, GeoChart each rendered 1.02 times per frame (3D: Globe3D 2.31); map drag p95 33 ms / 19 dropped (fixture), 117 ms / 471 dropped (copter); wheel zoom (30 steps) p95 183 / 317 ms, 145 / 315 dropped; 3D playback 183-192 ms median (software GL). Changes: the cursor values moved out of App into `CursorValues`; StageBar and PlotView read only `cursor.on`; GeoChart draws from a ref (`drawRef`) on a store subscription to the time (follow sets the view from the same subscription), sets the canvas size only when it changes; the base layer is drawn with a 25 % margin and moved / scaled while the view changes (and while tiles arrive), drawn again 200 ms after the movement pauses or when it no longer covers the screen; Globe3D moves on a subscription (its readout box still renders once a frame: it is what changes). After: panels 0.01 renders / frame during playback (StatusBar, TabBand, Timeline still 1: they show the time); drag p95 16.7 ms / 0 dropped on both; zoom p95 16.8-33 ms, 18 / 69 dropped; 3D 167-183 ms (software GL, unchanged - the owner checks a real GPU). Budgets added (`smooth_map_pan_p95_ms` ≤ 34, `smooth_map_zoom_dropped` ≤ 150, `smooth_play_panel_renders` ≤ 0.1), run in N9. Map: animated zoom (140 ms ease-out, around the pointer; none with reduced motion), a glide after a quick drag, controls in the start corner (+, −, Fit everything, Follow ▾, Back to following), a drag while following keeps an offset from the object, keys while the map has the focus (Q3's default: arrows, + / −, F, 0; Shift+←/→ left to the cursor), the one-line hint (pref `mapHintSeen`), *Camera following an object* smooth / exact in Settings (`smoothFollow`: eased ~120 ms while playing; 3D Chase eases its heading ~200 ms). Double-click still fits everything (kept as today; the hint says so). 3D: `Plot.camera` (optional: absent = as before) "chase" / "lookat"; *On the object* is the spec's Orbit (it already turned around the object and zoomed towards it); a change of mode / followed object / looked-at object flies for 700 ms (lerp of position, direction and up); a hint per mode. Not done: North up / Track up (rotating the 2D map; next), reverse playback (nice-to-have). Checks: tsc, Vitest 11 / 55, e2e test_map_smooth (new, 5), test_globe3d (11, 1 new: Chase / Look at), test_map_objects, test_offline_map, test_wheel, test_hover_ghost, test_name_tree, test_object_templates, test_object_frames, test_less_clutter, test_timeline, test_update_rate, test_trust_badges, test_damaged_note, test_owner_notes_1_20, test_release_1_21, test_heuristics, test_user_reader, test_settings, test_workflows, test_features (153 / 154: the known flaky test_limits_pass_fail_in_the_inspector). Next: Track up, then N7.
- 2026-11-10 · N6 done: Track up (`Plot.mapUp`, optional: absent = north up). The canvas becomes a square as wide as the view's diagonal, turned by CSS (`rotate(-heading)`) - the drawing and its base-layer reuse are unchanged, turning costs nothing per frame; the scale bar and attribution go on a level layer of their own (`.geo-top`); the pointer, drag, glide and arrow keys turn back into the map's frame (`toCanvas`). The heading: the followed object, else the primary, else the first (eased while playing when following is smooth; the last kept while it has none); the N on the button turns to show north. Labels on the map turn with it (accepted). Checks: tsc, e2e test_map_smooth (6, 1 new), test_offline_map, test_map_objects, test_wheel, test_hover_ghost, test_less_clutter, test_workflows (45). Next: N7.
- 2026-11-10 · N7 part 1. Backend: derived op `relate` (`svcore/relate.py`, definitions in its docstring): range, horiz, dalt, bearing, relbearing, closure, tca, hdgdiff, aspect; err_horiz / vert / 3d / hdg / roll / pitch (wrapped ±180); diff in ned / enu (the ECEF difference turned by the primary's latitude / longitude at each sample), ecef, lla (north / east metres by the meridian / prime-vertical radii, and Δalt), track (along / cross + right / up along the primary's heading - its yaw, else its course). On the primary's samples, the secondary interpolated (≈ badge via `_note_interpolated`), missing outside its span; no altitude: nothing vertical; a heading without angles is the course. Overlays reuse the `frame` op (lla → ned / enu with `ref: "signals"` = the primary's latitude / longitude / altitude: its first valid position is the one origin). Frontend: `relation.ts` (`defaultPair` by `MapObject.cls`, `pairOf` = `Plot.primaryObject` / the first of `Plot.relatedObjects` else the default - the existing saved fields, no new ones for the pair; the at-cursor maths, same WGS84 / NED as svcore), `actions.setObjectPair` (one commit; the tab's other maps / 3D views follow by latitude signal; a centred 3D camera moves with the primary), `actions.plotsInNewTab`. Map: rings (primary solid, secondary dashed), a dashed line with the range (`Plot.relLines`: pair / all / off), a click (no drag) picks the primary, Shift+click the secondary, Q / Shift+Q / X while focused (Q4's default); the chips: marked, a right-click menu (Set as primary / secondary, Error signals, Edit). The box (`RelationPanel`, its own render per frame; `Plot.relFolded`): the values, *Plot over time*, *Error signals*, a frame choice with *Differences* and *Overlay* (track: differences only). Error names `<s>_vs_<p>.err.*` (ASCII, nest by N1); a motion attitude's heading error is `hdg_cog`; an attitude borrowed from the primary gets no angle errors (a message says why) - Q5's default: Euler differences. 3D: the box's primary and lines follow `pairOf`; the primary select calls `setObjectPair`. A deviation: a click on a chip still opens the object's form (tests and habit) - the primary / secondary are in its menu. Checks: tsc, Vitest 12 / 61 (relation.test.ts new, 6), backend tests/test_relate.py (new, 5) and `-k derived or analysis or frame` (30), mypy on svcore/relate.py + analysis.py, e2e test_object_relations (new, 4), test_map_objects, test_map_smooth, test_globe3d, test_hover_ghost, test_less_clutter, test_object_templates, test_offline_map, test_workflows, test_heuristics (68). Next: N7's 3D side, the offer after Add all, velocities.
- 2026-11-10 · N7 done. 3D: rings (a PointPrimitiveCollection `rings`: the primary amber, the secondary fainter), models carry their object id (`Model.fromGltfAsync({ id })`) so a click (`scene.pick`) picks the primary, Shift+click the secondary; the view takes the focus on a pointer-down (`tabIndex -1`) and Q / Shift+Q / X work there; the box adds closure and aspect from `relation()` (one set of maths). The offer after objects are added (`ui.compareOffer`, set by `addObjects` / `addObjectsToMaps` with 2+ objects): *Compare the objects with <primary> · frame · Make plots* in the file panel; *Differences from the primary (NED)* in the chip's menu. Velocities: detection finds `<obj>.vel.north / east [/ down]` (`vn / ve / vd`, also `velocity`, `v_ned`), `MapObject.vel` (optional), `relate` `vdiff` (each velocity turned to ECEF from its own local frame, the difference into the primary's at each sample; no down: nothing vertical), a *Velocity difference* plot in *Differences* when both have it. Fixed (N5): the suggestion line's *Choose…* on a tab without a map used the new plot's id while `placePlot` kept the empty plot's - nothing opened (`test_suggestion_bar_choose_opens_the_list_on_a_new_map`). Not kept in templates: `vel` (the roles table has no velocity). Checks: tsc, Vitest 12 / 61, backend test_relate (6, 1 new: 200 km apart, side by side, no down), mypy relate.py, e2e test_object_relations (5), test_map_objects (9), test_globe3d (12, 1 new), test_hover_ghost, test_map_smooth, test_object_templates. Next: N2.
- 2026-11-10 · N2 done: `layoutActions.swapPlots(i, j)` (one commit; the active plot follows; rowSizes / colSizes untouched - they belong to the cells) and `moveActivePlot(dir)` (the neighbour by the grid, left / right as seen on the screen - mirrored in RTL); the ⠿ handle beside the title (only with 2+ plots) drags with `PLOT_MIME` (`application/x-sv-plot-move`, apart from SIGNAL_MIME / CHIP_MIME), the target outlined (`.move-target`); *Move to…* in the plot menu: a submenu of the tab's cells (row / column and title) rather than a drawn mini grid; Ctrl+Shift+arrows (Q1's default; in shortcuts.ts with the other Ctrl keys, not while typing) and four command-palette entries; Help lists the key. Checks: tsc, Vitest 13 / 63 (movePlots.test.ts new, 2), e2e test_move_plots (new, 2), test_plot_menus, test_one_per_plot, test_aligned_plots, test_less_clutter, test_owner_notes_1_20, test_workflows (41). Next: N3.
- 2026-11-10 · N3 done. Settings → *New lines*: `ui.lineWidth` (0.5-6, default 1.5) and `ui.lineStyle` (solid / dash / dot / dashdot), kept in the app folder with the other choices (settings.ts KEYS), not in the session; opacity left out (the spec's "if cheap": uPlot has no per-series opacity without a colour change, and fade() is the setpoint's). `styledSignal(sig, color, extra)` in store/selectors.ts is the one place a line is made (`newPlotSignal` uses it); the literals in CompareTable, ComparePanel (3), WhatChanged (3), segments, conditions and errors replaced (TimeChart's shared lanes are not saved lines: left). `PlotSignal.lineStyle` (optional) - precedence lineStyle > dash > automatic (`desired.lineLook` returns the style; `DASH` patterns: dash 6/4, dot 1.5/3, dash-dot 6/3/1.5/3, × dpr); drawn in TimeChart (its style keys include it), the legend swatch (`ls-dot` / `ls-dashdot`), and the report / image export (plotSpec sends `style`, report.py `LINE_STYLES` → matplotlib). The Inspector: Auto / Solid / Dashed / Dotted / Dash-dot - Solid and Dashed still write the old `dash` (1.23 reads it), Dotted / Dash-dot `lineStyle`. *Apply to all open plots* (`actions.applyLineDefaults`): every non-state line of every tab, one commit (none when nothing differs), a message with the count and Undo; solid clears a style set by hand. Checks: tsc, Vitest 14 / 66 (lineDefaults.test.ts new, 3), backend test_right_axis (2, 1 new) and `-k report` (34), e2e test_settings (2, 1 new), test_plot_style, test_setpoint_style, test_compare_diff, test_compare_tolerances, test_conditions, test_error_details, test_error_segments, test_what_changed, test_workflows (48), test_features (126 - the flaky one passed). Next: N4.
- 2026-11-10 · N4 done. `styleLines.ts`: `linesInScope(ws, sigs, "plot"|"tab"|"all")` (the active plot of the active tab / its every plot / every tab, in drawing order), `defaultScope` (the narrowest with a line), `restyle` (a field left out is kept; `color: "palette"` gives the i-th line `TRACE_COLORS[i]`; the style written as the Inspector writes it - Solid / Dashed the old `dash`, Dotted / Dash-dot `lineStyle`, Auto clears both; width clamped 0.5-6), `applyLook` (counts the lines that change). `actions.styleLines(targets, look)`: one commit (none when nothing changes), a toast with the count and Undo. `StyleLinesDialog` (`ui.styleDialog: {name, sigs, lines?}`): scope radios with each scope's count (hidden for a legend selection), colour Keep / Palette / 8 swatches, width (empty = keep), line style Keep / Auto / four styles, the count of lines, Apply. Entry points: *Style the lines…* in the file-group and the user-group menus of the signal list; the Inspector's batch section (legend Ctrl+click) gains colour (Palette + swatches) and line style through the same action, and *Style these lines…* opens the dialog on the selection. Checks: tsc, Vitest 15 / 71 (styleLines.test.ts new, 5), e2e test_plot_style (3, 2 new), test_setpoint_style, test_settings, test_one_per_plot, test_name_tree, test_plot_menus, test_owner_notes_1_20. Next: N9.
- 2026-11-10 · N8 done (the owner approved it: Q6 answered). The format checked against Tacview's published "ACMI flight recordings 2.2" page (raia-software-inc.gitbook.io/tacview/technical-documentation/acmi-telemetry-file-format), not from memory: the two header lines, object 0's ReferenceTime / ReferenceLongitude / ReferenceLatitude / DataSource / DataRecorder / RecordingTime / Title, `#seconds` frames, hex ids, `T=Lon|Lat|Alt|Roll|Pitch|Yaw` (degrees, metres MSL, roll right, pitch up, yaw clockwise from true north), `-id` removal, `Type` tags (Air+FixedWing, Air+Rotorcraft, Sea+Watercraft, Ground+Vehicle, Weapon+Missile - Tacview has no UAV tag), the seven `Color` names, `\,` for a comma in text (the page gives no escape for line breaks: replaced by a space). `svcore/acmi.py` (`write_acmi`: one grid at `rate` Hz, 10 by default, angles interpolated the short way round, roll / pitch written ±180, yaw 0-360; whole-degree reference point; an object appears at its first position and is removed when it ends; epoch times (> 1e9 s) become the ReferenceTime, else 2000-01-01T00:00:00Z; `acmi_color` by hue ranges, a light blue Cyan, grey Blue). Route `POST /api/export/acmi` (export.py `acmi_objects`: each object through `object_track` without decimation - the same position, quaternion / motion attitude and angle units as the 3D view; altitude MSL by `altRef` with the bundled elevation; no altitude: on the ground; roll unknown: 0; UTF-8 with BOM, LF). Frontend: *Export for Tacview (.acmi)…* in the plot menu of a map / 3D view with objects (objects through `trackRequest`, borrowed attitude resolved; mapObjects imported lazily). Checks: backend test_acmi (4: a known small file verbatim, epoch / wrap, colours / text, the export of three_objects.csv), mypy on the two files, tsc, e2e test_map_objects (the new case).
- 2026-11-10 · N9 done: release 1.24.0 prepared (not tagged). Version in version.py, build.bat, installer/SignalViewer.iss, installer/version_info.txt (4 places), CITATION.cff (date 2026-11-10), docs/install.md's file name; CHANGELOG `## 1.24.0 – 2026-11-10` with highlights; README review (the map section: primary / secondary, smooth map, Tacview; the Hebrew list: map and 3D, moving plots / line styles - no version numbers added), features.md (objects found, motion / borrowed attitude, primary / secondary, smooth motion, Tacview, line styles, moving plots), limitations.md (Tacview export, name-only guesses, 3D on software GL, no line opacity), validation.md regenerated (its version line). **Full checks:** backend pytest 1093 passed / 14 skipped after two fixes (test_design_tokens: N6's north arrow used `7px` and `#e5534b` - now `--fs-glyph` and `--danger`; test_validation: the page's version line); mypy (109 files) clean; `python cli.py validate` 29 / 29; `npx tsc -b`, `npm run build`, Vitest 15 files / 71 tests; **the whole e2e suite 361 passed** (first run: 2 failed - test_less_clutter read the status bar before the plot's "drawn for" count arrived, now waits for it; the known flaky test_limits_pass_fail_in_the_inspector read the workspace right after the reload, before the autosave was restored - now waits for the plot's chip; each passed 5 / 5 after, then the whole suite again: 361 / 361); `tools/benchmark.py --synthetic --samples 2000000 --check 3`: every target met; `tools/browser_benchmark.py --group smooth` (2 CPUs, no GPU): map pan p95 16.7 ms (≤ 34), wheel zoom 62 frames dropped (≤ 150), 0.01 panel renders per frame during playback (≤ 0.1); `mkdocs build --strict` passes. Defaults used for unanswered questions: Q1 Ctrl+Shift+arrows, Q2 `ref` = other, Q3 the map keys (arrows, + / −, F, 0), Q4 Q cycles the primary / X swaps, Q5 Euler differences wrapped to ±180°, Q7 1.24.0 (Q6 answered: yes). **Left open:** a motion attitude from the object's own velocity signals (N5), reverse playback (N6), `MapObject.vel` is not kept in templates, line opacity, ACMI of the plots' other signals / a chosen time span. **The owner checks by hand on Windows:** CI (run by hand), the build and the installer, the N6 smoothness on a real machine (60 fps targets: drag, zoom, playback with 3 objects), the Cesium 3D view on a real GPU (Chase / Look at, the flight between views), opening an exported .acmi in Tacview; then tag `v1.24.0`.
- 2026-11-10 · Round of 2026-11-10 started (L0): prompt kept as docs/dev/AGENT_PROMPT_2026-11-10.md, "Owner's plan (2026-11-10)" with board, decisions, Q1-Q14, notes; Milestone 28 in ROADMAP. Baseline at `d61ab6d`: backend 1095 passed / 14 skipped, mypy clean, tsc clean, Vitest 15 files / 71 tests. Fixtures from tools/make_local_objects_fixture.py (the backend's own WGS-84 maths).
- 2026-11-10 · L1-L5 done (code map in the plan): metric positions in every form, the frame decided per group, flat velocities, units flagged (Q6), XKF1 / NKF1 lanes / PX4 / MAVLink local positions, origins own → known → sibling, origin groups never objects, one chain walk and one "already on the map" rule (F8 fixed), rows say frame + origin, Advanced… fills / suggests the origin. Checks: tsc, Vitest 15 files / 87 tests (5000 metric names < 100 ms), pytest tests/test_local_objects.py.
- 2026-11-10 · L6 done - group A complete. Checked: N7 relation between two lanes (pytest: lane 1 - lane 0 = +1.5 m north, err_hdg +0.5°), lane 0 on POS within 0.05 m (pytest and e2e through /api/object_track), 3D / templates / relations / frames (e2e), old sessions (no saved field added or changed: the objects are LLA objects behind derived signals), Tacview export (same object_track path, e2e of N8 green). Live mode: not exercised. e2e that ran: test_local_objects (new, 3), test_map_objects, test_object_frames, test_object_templates, test_object_relations, test_globe3d (35 passed); then the **whole e2e suite** at the end of the group (result in the next line). Next: L7.
- 2026-11-10 · Whole e2e at the end of group A: the run was cut off by the session at ~74% (all green until then, no failure); the files of the group (test_local_objects, map_objects, object_frames, object_templates, object_relations, globe3d) passed; the full suite is run again at the end of group B.
- 2026-11-10 · L7 done: Reference ⇄ Compared with in the relation box's header (`RelationPicker`, also in the 3D bar instead of its Object / Second selects), ring icons in the header and on the chips, the ring tooltip on the map, Ctrl+K "Set reference object: …" / "Swap…", Help rows; words en Reference / Compared with, he בסיס / מושווה (decision 6). Checks: tsc, Vitest 15 / 87; e2e test_object_relations (6, one new), test_globe3d (12), test_file_help_menus + test_map_objects (12). Next: L8.
- 2026-11-10 · L8 done: Compare objects… (dialog, presets, one tab per quantity, statistics, CSV), err_speed, stats abs_max / t_abs_max / p95_abs, plotTabs never drops silently, reuse of relation / frame signals (decisions 9-12). Checks: backend 1100 passed / 14 skipped (test_design_tokens caught a radius fallback in the new CSS - fixed), mypy clean, tsc, Vitest 15 / 91; e2e test_local_objects (4), test_object_relations (6), test_map_objects (10). On ardupilot_lanes.csv: lane 1 north error +1.5 m, lane 0 ~0, yaw error +0.5°, RMS 1.5 in the table, speed error 0. Next: L9.
- 2026-11-10 · L9 done - group B complete (decisions 13-16). Checks: backend 1101 passed / 14 skipped, mypy clean, tsc, Vitest 16 files / 98; e2e test_compare_similar (2, new), test_error_segments + test_one_per_plot (5). Whole e2e suite at the end of group B: see the next line. Next: L10.
- 2026-11-10 · **Whole e2e suite at the end of group B (the debt of group A paid too): green.** First run: the first 192 tests passed, then the container's disk filled (8.5 GB of pytest temporary files in /tmp/pytest-of-root - not the app) and the rest errored at setup; one F just before (test_missing_choice::test_sum_propagate_then_skip_is_marked) passes alone and in the rerun. Rerun in two chunks with /tmp cleaned between: test_map_smooth … test_release_1_21 60 passed; test_runs_matrix … test_workflows 122 passed. Note for later runs: clean /tmp/pytest-of-root between big e2e runs in a small container. Next: L10.
- 2026-11-10 · L10 done (decisions 17-20): movePlotToTab / mergePlotInto (one Undo each), the handle onto a tab, Move to… → tab / New tab, Add its lines to…, Shift+drop merge, Ctrl+K. Checks: tsc, Vitest 16 / 102; e2e test_move_plots_tabs (3, new), test_move_plots (2), test_plot_menus + test_tab_band + test_template_tabs (6). Next: L11.
- 2026-11-10 · L11 done - group C complete (decisions 21-25). Checks: backend 1107 passed / 14 skipped, mypy clean (110 files), tsc, Vitest 102; e2e test_map_export (new), test_findings_report + test_map_objects + test_offline_map (17). Next: L12.
- 2026-11-10 · L12 done - group D complete (decisions 26-30): one table + shared vectors (10 cases, Vitest and pytest agree), the Python API, four CLI commands, three REST endpoints, docs/api.md. Checks: backend 1122 passed / 14 skipped (the parity test first left derived signals in the shared store and broke two order-dependent tests - cleaned up), mypy clean (114 files), tsc, Vitest 17 files / 112. Next: L13.
- 2026-11-11 · L13 done, with a human-factors review (`docs/dev/UX_REVIEW_2026-11-11.md`): L8-L12 applied on `e2a75a8` and reviewed on screen; added `flatLine.ts` (the right-axis / own-plot offer from the values), `soloPlot` (M), the start card's Quick look, `plotTabs` `look` (comparison lines named and coloured by object), statistics with units and a link to the time of the largest error, the ⋯ corner, wording and spacing fixes; guides en + he, features, limitations, README, version 1.25.0, CHANGELOG, dist. Checks: backend 1122 passed / 14 skipped, mypy clean, tsc, Vitest 119, mkdocs strict, e2e 381 passed + 1 (`test_sweeps_flow.py`, unstable in the container on every tree - see the review). Left to the owner: `[ci]`, README media, the Windows build, the tag. Proposals waiting: the review's "Proposed, not done".
- 2026-11-11 · Round of 2026-11-11 (1.26.0): one Map with 2D | 3D (the owner: one switch; "3D" is XYZ), `pagePlot` (a 3D view was dropped from reports without a word), `app/scene3d.py` + `report_assets/scene3d.html` (three.js r159 - the owner chose it), every HTML report live (`replay.compact / link`), `sv.scene_image / scene_html`, `cli map --3d`; the pre-existing token failure (`.tl-edge::after` 2px radius) fixed. Backend 1140 passed / 14 skipped, mypy clean, tsc clean, Vitest 21 files / 132 tests; e2e (relevant files only, 61) green - the whole suite is the owner's.
- 2026-11-11 · 1.26 after the owner's review: the offline pages share one toolbar (camera Free / Centre / Close, object, + − ⤢, Relation, theme) and the app's relation box (`relation.js`, `mappage.css`); 3D tracks as screen-width lines with the app's looks; the app's 3D view has the relation box (pair chosen there, `Plot.relHidden`, `RelationToggle` in both bars; a third object stays in the data box); `docs/validation.md` regenerated (the version). Backend 1135 passed / 14 skipped, mypy clean, Vitest 132; e2e: test_live_report, test_globe3d (3 adapted: the picker moved into the box), test_object_relations, test_map_export, test_replay, test_less_clutter, test_map_objects, test_object_templates, test_hover_ghost - green.
- 2026-11-11 · 1.26, the owner's "continue": `components/MapBar.tsx` - one bar for the map in 2D and 3D (camera General / On the object / Chase on a chosen object, + − fit, Relation; 2D Chase = close + track up via `trackUpOf`; 3D `zoom3d`); "Closest in" goes to the moment (app `RelationPanel`, pages `svSeek` → viewer.js `replay-seek`); pages: Trail (`svTrail`), attitude indicator (3D), the address keeps the view (`svHash`), the app's camera words. Backend 1135 passed / 14 skipped, mypy clean, Vitest 132; e2e green: test_live_report (3), test_globe3d, test_map_smooth, test_object_relations, test_less_clutter, test_map_objects, test_offline_map, test_hover_ghost, test_object_templates (one timeout in the long batch, green alone twice), test_map_export, test_replay, test_features / test_heuristics / test_object_frames / test_local_objects (-k map, mode, report, 3D).
