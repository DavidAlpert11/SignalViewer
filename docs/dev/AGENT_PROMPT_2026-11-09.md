# Agent prompt – Signal Viewer, owner's round of 2026-11-09

> ## Status – read this first (updated at the end of every session)
>
> **Stage reached:** N0, N1, N5, N6, N7, N2, **N3** and **N4 done**. **Next: N9** (release 1.24.0 - Q7's
> default; full checks; commit `frontend/dist`; no tag). N8 (ACMI export) only if the owner approves it
> (Q6 - default: not started); if approved, do it before N9.
> - N3's code map: `styledSignal(sig, color, extra)` in `store/selectors.ts` is the one place a line is
>   made (Settings' `ui.lineWidth` / `ui.lineStyle`); `PlotSignal.lineStyle` - precedence lineStyle >
>   dash > automatic (`desired.lineLook`, `DASH`); `actions.applyLineDefaults`; report.py `LINE_STYLES`.
> - N4's code map: `frontend/src/styleLines.ts` (`linesInScope` plot / tab / all, `defaultScope`,
>   `restyle`, `applyLook`), `actions.styleLines(targets, look)` (one commit, a toast with Undo),
>   `components/StyleLinesDialog.tsx` opened by `ui.styleDialog` - from both group menus in the signal
>   list (*Style the lines…*) and from the Inspector's batch section (*Style these lines…*, colour and
>   line style there too).
> - N7's code map: backend `svcore/relate.py` (op `relate`, definitions in its docstring); frontend
>   `relation.ts` (pair defaults, at-cursor maths, the over-time actions), `RelationPanel.tsx`,
>   `actions.setObjectPair` / `plotsInNewTab`, `ui.compareOffer`; the pair lives in the existing
>   `Plot.primaryObject` / `relatedObjects`.
> - Measuring: `python tools/browser_benchmark.py --data <dir> --results r.json --group smooth`;
>   `window.__svRenders = {}` turns on the render counter (`frontend/src/perf.ts`).
> - Left (small): a motion attitude from the object's own velocity signals (N5); reverse playback (N6,
>   nice-to-have); `MapObject.vel` is not kept in templates.
> - Known flaky e2e: `test_features.py::test_limits_pass_fail_in_the_inspector` (after a reload; also
>   before this round) - look at it in N9.
>
> e2e: open the object form through `object_form(pg, row)` in test_features.py (the dialog opens on the
> found list). e2e needs `npm run build` first; do not commit `frontend/dist` before N9.
>
> **Base and patch.** The owner applies each patch and pushes it to `main`, so every session's patch is
> made **against the repository's `main` as it is when the session starts** (it was `c5bf95b` for the
> N6 / N7 / N2 sessions; the round began at `dafea49`, 1.23.0). To continue:
> ```
> git clone https://github.com/DavidAlpert11/SignalViewer.git && cd SignalViewer
> git log --oneline -3          # the base: main's HEAD
> cd frontend && npm ci && npx tsc -b && npm test
> ```
> At the end of your session make the patch from that base to HEAD
> (`git format-patch <base>..HEAD --stdout > signalviewer-<date>.patch`), check it with `git am` on a
> fresh clone of `main`, update this Status box and the board in `docs/dev/TASKS.md`
> ("Owner's plan (2026-11-09)"), and hand both files to the owner. This prompt also lives in the repo
> as `docs/dev/AGENT_PROMPT_2026-11-09.md`; keep the two copies equal.
>
> **Where things are:** board, owner's decisions 1-5, open questions Q1-Q7 with their defaults (Q8 answered), notes
> from the code and the Log: `docs/dev/TASKS.md` → "Owner's plan (2026-11-09)". Milestone 27 in
> `ROADMAP.md`. Fixture: `examples/three_objects.csv` (`tools/make_objects_fixture.py`).
>
> **Baseline at `dafea49`:** `npx tsc -b` clean; `npm test` 8 files / 24 tests.
>
> **Found while reading the code (now part of the spec below):** names like `GPS.Lat [deg]` carry a
> trailing unit (N1); CSVs with ArduPilot message names pair `GPS.*` position with `ATT.*` attitude
> today, which N5's own-prefix rule would break (Q8, **approved by the owner**: the known-groups table
> applies to any file).
>
> **Code map from N1 / N5:** `signalGroups.pathCuts` / `nameTree` (the list's tree); `objectDetect.ts`
> (candidates, classes, known log groups, explanations); `objectAdd.ts` (candidate → MapObject, *Why?*
> words, `linkAttitudes`); `mapObjects.ts` (`attitudeOf`, `trackRequest`, `trackKey`, `guessRoles` via
> detection); `ObjectSuggestBar.tsx`; backend `motion_attitude` in `app/routes/analysis.py`.

You are a senior engineer working on **Signal Viewer** (repo `DavidAlpert11/SignalViewer`, base commit
`dafea49`, version 1.23.0). It is an offline desktop app: Python FastAPI backend plus React/TypeScript frontend.
Its users are flight-test, drone and simulation engineers. This round comes from a hands-on review by
the owner and by a friend who normally uses **Tacview**. The friend found map objects tedious and the
map hard to move around.

**Priority from the owner:** the friend's Tacview-like wishes come first among the map work. They are
smooth motion, an easy-to-move map (N6), and a primary / secondary object with the relations between
them (N7). **Work order: N1 → N5 → N6 → N7 → N2 → N3 → N4 → (N8, only if approved) → N9.** The task
numbers are IDs, not the order. If time is short, N2, N3 and N4 are the ones that slip.

## 0. Before you write any code

1. Read `/CLAUDE.md` (the rules), `docs/dev/TASKS.md` (the work queue) and `docs/dev/ROADMAP.md`. Every
   rule there applies unless this prompt overrides it explicitly (see §2, testing).
2. Add a section **"Owner's plan (2026-11-09)"** to `TASKS.md` with the tasks below (IDs `N1`–`N8`), a
   progress board and a Log. Add the IDs to `ROADMAP.md`. Keep both current after every task, as
   CLAUDE.md requires.
3. Record the baseline before you change anything. Run `cd frontend && npx tsc -b && npm test`, and write
   the result in the Log. A full baseline is not needed (see §2).
4. Work one task at a time, in the work order above (not the numbering of §3). Make one small commit per task, or per coherent part of a task.
5. **Stop and ask the owner** before any decision that is not settled here. Typical cases: a new
   dependency, a change to a saved field, a task that grows well beyond its spec, or N8 (ACMI export) at all.
   Write the question in TASKS.md and in your reply. Keep working on the next independent task while you wait.
   If no answer has come by the time the work depends on it, use the **default** written next to that
   question in this prompt (marked *Default if unanswered*), record in the Log that you did, and keep it
   easy to change. Never block the round on an unanswered question.
6. **Sessions and hand-off.** The work may span several sessions, and the working copy may not survive
   between them. End every session with a clean, committed state and a hand-off: a `git bundle` (or
   `git format-patch` series) from `dafea49` to HEAD, plus the updated TASKS.md board showing what is
   done, what is in progress and what is next. Start every session by restoring that bundle and reading
   the board. Do not leave uncommitted work at the end of a session.

## 1. Findings from the review (verified on `dafea49`)

Reproduce each finding before you fix it. A CSV with these 19 columns shows all of them:
`time, phys.lat, phys.lon, phys.alt, phys.att.roll/pitch/yaw, phys.vel.north/east, nav.lat, nav.lon, nav.alt, nav.att.roll/pitch/yaw, nav.vel.north/east, gps.lat, gps.lon, gps.alt`.
Commit this file as a test fixture (`tests/fixtures/` or wherever the e2e fixtures live). Generate it
from a small script so it stays small.

- **F1 – the dot nesting "disappeared".** `frontend/src/signalGroups.ts` groups by prefix only when
  the file has at least `GROUP_MIN = 40` signals. Sub-groups need `SUBGROUP_MIN = 12` signals. The number
  of groups must be at most a third of the number of signals. There are only two levels. As a result,
  the 19-signal file above is listed flat, and a third level (`sim.nav.pos.x` from a `.mat` struct) is
  never shown. The caller is `DataPanel.tsx`, in the `rows` useMemo, at about lines 290–350.
- **F2 – one object per file, with mixed sources.** `guessRoles` in `frontend/src/mapObjects.ts` picks
  each role independently. On the file above it gives position from `gps.*` and attitude from
  `nav.att.*`. The template "Position on the map & 3D" adds a single object named after the file.
  `ObjectDialog.tsx` asks for six signals per object, one object at a time.
- **F3 – line style.** Batch editing exists only inside the Inspector (`multi.length > 1`: scale /
  offset / time offset / width / line-or-states). It has no colour and no line style, it works only
  within the active tab, and the Inspector starts closed. `PlotSignal.dash` is a boolean. The default
  width `1.5` is a literal repeated across the code (`conditions.ts`, `errors.ts`, `segments.ts`,
  `store/actions/plots.ts`…). There is no setting for it.
- **F4 – plots cannot be moved.** `Tab.plots` is a flat row-major array. There is no move or swap action in
  `store/actions/layout.ts`.
- **F5 – map navigation is hidden.** `GeoChart.tsx` supports wheel zoom, drag to pan, double-click to fit,
  and `plot.followObject`. None of this is visible: there are no zoom buttons, no fit button, and
  follow is a tiny ⌖ in the object chip. The 3D view uses Cesium's default camera controls with no hint.
  There is no live relation between objects (distance, bearing, Δalt). "Measure" only measures two
  clicked points.
- **F6 – smoothness is at risk.** Playback (`App.tsx`) writes the cursor to the global store on every
  frame, so it may re-render far more than the map and 3D. During a pan, `GeoChart` rebuilds its base
  layer (tiles) on every mouse move, because the cache key is the view. Measure both before changing anything (N6).

## 2. Testing policy for this round (owner's instruction – overrides CLAUDE.md's per-group rule)

**During the work, run partial checks only.** After each task:
- `cd frontend && npx tsc -b` and `npm test` (Vitest is fast; always run all of it).
- Add a Vitest unit test for every piece of logic that has no screen: grouping, object detection,
  defaults, swap, error maths in the frontend.
- When the backend is touched, run `cd backend && python -m pytest -q -k <area>` on the touched modules,
  and add or extend their tests.
- Run **only the relevant e2e files**. The list is given per task in §3. Also run the files of views that
  gain or lose screen space because of the change (CLAUDE.md, T08 lesson). Add new e2e tests for the new flows.
- Write in the Log which checks ran and their result.

**Do not run the whole e2e suite, the full backend suite, mypy over everything, the benchmarks or
mkdocs between tasks.** All of them run once, in N9 (release preparation). A failure found there is
fixed, and only the affected checks are rerun after the fix. Write this policy in the round's section of TASKS.md.

## 3. The tasks, in order

### N1 – Dot nesting, always and at any depth (bug)

The spec:
- Treat `.` and `/` as **explicit** separators. When a file's names use them, build the tree always,
  whatever the number of signals, and recursively to any depth. `.mat` struct names arrive as `a.b.c`
  through `mat_loader.py`, so the same rule covers them.
- A separator only splits between **identifier-like segments** (letter or `_` first, then letters,
  digits, `_`, optionally an index like `[0]`). So `vel (m/s)`, `bus_1.5V` and `fw v2.1` are not split:
  units in parentheses and numbers with a decimal point stay whole. Add these to the Vitest suite.
  A trailing unit in brackets or parentheses (`GPS.Lat [deg]`, `vel (m/s)`) is ignored for this test
  and kept in the label, so `GPS.Lat [deg]` (examples/uav_flight.csv) still nests under `GPS`.
- Flight-log names (`GPS[0].Lat`, `ATT.DesRoll`, `XKF4[0].SV`) already contain `.`. They keep **exactly**
  today's grouping (`IMU[0] > Acc > X`). Find where that grouping happens today and make sure the new
  rule does not run on top of it or change it.
- Keep the current heuristics (thresholds, the 0.6 share, the `/3` rule) **only** for `_` and `:`. This
  way ArduPilot names such as `MOT_1_PWM` do not shatter. Do not regress the existing flight-log
  grouping (`IMU[0] > Acc > X`).
- Fold a chain of single-child levels into one row. For example, `phys.att` with only `att` inside shows
  as one group `phys.att`. Do not create a group of one signal.
- Inside a group, show only the remaining part of the name. Keep the full name in the tooltip, in search,
  and in drag/drop.
- Keep today's open/closed defaults: big files start collapsed, and groups with plotted signals start open.
  Searching opens matching groups. Indentation must work for any depth, in LTR and in RTL.
- The rows are virtualised. Keep `Row` heights and the `offsets` logic correct.

Done when: the 19-signal fixture shows `phys > att / vel`, `nav > att / vel` and `gps`; a 3-level `.mat`
shows all levels; an ArduPilot `.bin` (`examples/copter_flight.bin`) lists exactly as before.

Tests: a new Vitest suite for `signalGroups.ts`. E2E: `test_features.py -k group` (or the matching
tests – grep `grp-head`), `test_map_objects.py`, `test_object_templates.py`, `test_workflows.py`.

### N2 – Move plots: swap places in the grid

The spec:
- Add a drag handle (⠿) beside the plot title. Dropping it on another cell **swaps** the two plots.
  Highlight the target cell while dragging. Use a new drag MIME type that cannot collide with the
  `SIGNAL_MIME` and `CHIP_MIME` already used in `PlotView.tsx`. A click on the plot must still select it.
  The drag handle is the main way; the shortcut below is secondary.
- The plot's ⋯ menu gets **Move to…** with a mini grid of the tab's layout. Click a cell to swap with it.
- Add a shortcut that swaps the active plot with its neighbour, and add it to the command palette. Do
  **not** use Ctrl+Alt+Arrow (on many Windows machines with Intel graphics it rotates the screen; on
  GNOME it switches workspaces) and do not use Alt+Shift (it switches the keyboard language on Windows,
  which Hebrew users press constantly). Proposed: **Ctrl+Shift+Arrow**. Check `shortcuts.ts` for clashes
  (bare arrows step the cursor; Alt+← is zoom back). *Owner question – Default if unanswered: Ctrl+Shift+Arrow.*
- Add `layoutActions.swapPlots(i, j)` through `commit` (one undo). `tab.active` follows the moved plot.
  Row and column sizes stay with the cells, not with the plots. Linked axes, cursors and map/3D state
  move with the plot, since they are keyed by plot id.

Tests: Vitest for `swapPlots` and undo. E2E: new `test_move_plots.py`, plus `test_plot_menus.py`,
`test_one_per_plot.py`, `test_aligned_plots.py`.

### N3 – Line defaults in Settings, and one place that makes a PlotSignal

The spec:
- Settings gets a **Lines** section with three choices: default width (0.5–6), default line style
  (solid / dashed / dotted / dash-dot) and, if cheap, default opacity. These are saved like the other
  Settings choices; find the existing mechanism in `settings.ts` / `prefs.ts`. They are not saved in the session.
- Replace every literal `PlotSignal` construction with one helper (for example `newPlotSignal(sig, color)`
  in the store) that applies the defaults. Grep for `width: 1.5` and `width: 1,` across `frontend/src`.
- Add a button **Apply to all open plots**. It is one `commit` and one undo, and it states how many lines
  it changed. Defaults do **not** silently restyle existing lines.
- Add the data model field `PlotSignal.lineStyle?: "solid" | "dash" | "dot" | "dashdot"`, optional.
  Precedence is `lineStyle` > the old `dash` boolean > automatic (setpoint dashed, `desired.ts`). Old
  sessions must open unchanged. Draw the styles in every chart that honours `dash` today (grep `dash` in
  `components/`) and in the report export, if it draws lines.

Tests: Vitest for the helper and the precedence. E2E: `test_settings.py`, `test_plot_style.py`,
`test_setpoint_style.py`.

### N4 – Style a whole group of signals at once

The spec:
- In the signal list, right-click a group (file groups from N1 and the user's own groups) and choose
  **Style the group's lines…**. A small dialog offers colour (one colour or a palette), width, line style,
  opacity and markers if supported. It also offers a scope: *this plot / this tab / all tabs*. It applies
  to every plotted signal of the group, and the dialog states how many lines that is. It is one commit.
- In the legend, Shift/Ctrl-click selects several lines and opens the same panel.
- Extend the Inspector's batch section with colour and line style, so all three entry points share one
  implementation. CLAUDE.md requires one way to do a thing.

Tests: Vitest for "which lines does a scope hit". E2E: `test_plot_style.py`, and a new case for the group menu.

### N5 – Map objects: a naming convention, all objects at once, and why each guess was made

This is the biggest task. Split it into commits: detection → dialog → template → docs.

**Detection** (new module, for example `frontend/src/objectDetect.ts`, replacing the role logic in `guessRoles`):
- An **object is a prefix** (owner's rule): **every nested prefix, at any depth, that holds the set of
  object signals is proposed.** The set is position (lat, lon, alt) and attitude (roll, pitch, yaw, or
  phi, theta, psi). Prefixes may be multi-level (`sim.truth.lat` → `sim.truth`) and may use `_`
  (`nav_lat`, `ins2_lat`).
- **Which prefix is the object.** The object is the prefix whose own signals, or whose position and attitude
  sub-groups, hold the set. A position sub-group is named pos / position / lla / geo; an attitude sub-group
  is named att / attitude / euler / angles / ori (one table, easy to extend). So `sim.nav.pos.lat` +
  `sim.nav.att.roll` gives the object `sim.nav`. A prefix that only *contains* objects is not itself an
  object: `sim` with `sim.truth.*` and `sim.nav.*` gives two candidates, `sim.truth` and `sim.nav`, and not `sim`.
- **What is required.** lat + lon are required. alt and attitude are not: a prefix with lat/lon but no
  attitude (a typical GPS receiver) is still proposed, and its row says what is missing. A prefix with
  attitude but no position is not a map object and is not proposed. **Owner's decision: position-only
  prefixes are proposed.** The full set (position + attitude) ranks first.
- **Roles come only from the object's own prefix and its sub-groups** (`nav.att.roll`, `nav.euler.phi`,
  `nav.pos.lat`). Never take a role from another object's prefix **during detection**. A position-only
  object still gets an attitude for display, from a source the user chooses (next point).
- **Attitude source of a position-only object (owner's decision).** Each object gets an optional saved
  field `attitudeSource`: `"own"` (its own signals; the only value for objects that have them), `"motion"`,
  or `{ object: <id> }`. Old sessions have no field and behave as today.
  - **From motion** (the default for position-only objects): heading = course over ground; pitch = the
    flight-path angle (climb over ground speed); roll = 0, shown as unknown. Use the object's own velocity
    signals when it has them (`vel.north/east/down`), else differentiate the position with light
    smoothing. Below a speed threshold (default 1 m/s, editable in Advanced) hold the last valid heading,
    so a hovering or parked object does not spin on noise.
  - **From another object**: borrow the attitude of an object the user picks in the row (a dropdown of
    the objects that have their own attitude; the primary is listed first). It is interpolated onto the
    object's time base, the short way round. Use it when the receiver rides on the same vehicle; do not
    pick it by default, because a position-only object may be another vehicle.
  - A derived attitude is always marked as such: a ≈ badge on the chip, an outlined (not filled) icon on
    the map and in 3D, and a line in **Why?** (*"Attitude: from motion (course over ground), roll
    unknown"* or *"Attitude: borrowed from nav"*). Changing the source is one commit and one undo.
- Accept aliases for the roles: lat/latitude, lon/lng/long/longitude, alt/altitude/height/alt_msl/hgt,
  roll/phi, pitch/theta, yaw/heading/hdg/psi, quaternions as today, and the NED/ECEF/ENU positions that
  `ObjectDialog` already converts. Keep the unit guess (deg/rad) as today, with its reason.
- **Classify** each object by keywords in its prefix (case-insensitive, list in one table, easy to extend).
  Keywords match **whole segments** of the prefix only, never substrings: `est` matches `est` and `est2`,
  but not `test` or `estimate`. A segment may carry a number (`nav1`, `ekf3`, `gps_2`). When several
  segments of a multi-level prefix match different classes, the **deepest matching segment wins**:
  `sim.nav` is *navigation*, `sim.truth` is *truth*, `sim` alone is *truth*.
  - *truth*: phys, truth, true, sim, model, plant, dyn. (`ref` is left out on purpose: it often means a
    commanded or reference trajectory, which is not truth. *Owner question – Default if unanswered:
    `ref` is "other".*)
  - *navigation*: nav, ins, ekf, ahrs, est, kf, filter, fusion, numbered variants such as nav1, nav2, ekf3.
  - *receiver*: gps, gnss, rcv, rx, pvt, ublox, novatel.
  - Anything else is *other*.
- **There can be several navigation solutions (and several receivers): propose all of them.** Give each
  one a distinct colour and a name that keeps its prefix.
- **Flight logs** must not regress. Keep a table of well-known message groups: ArduPilot `POS` (EKF
  output), `GPS[n]` (receivers), `AHR2` (backup AHRS), `XKF1[n]` (EKF cores, attitude), and the SITL
  simulation truth message if the loader exposes it (check `bin_loader.py` / `flightlog.py`), plus
  PX4 `vehicle_global_position`, `vehicle_gps_position`, `vehicle_attitude`. Pair attitude to position as
  today for these known groups. The known-groups table applies to **any** file, not only `.bin` / `.ulg`: a CSV
  with ArduPilot message names (`GPS.Lat`, `ATT.Yaw` – examples/uav_flight.csv and test_map_objects'
  `obj_aircraft.csv`) stays one aircraft, GPS position with ATT attitude, as today. *(Q8 – approved by
  the owner.)* A copter `.bin` must still give a sensible main object.
- Each candidate carries an **explanation**, as data: for each role, the signal chosen and the rule that
  chose it (exact name / alias / known log group / sub-group), the class and the keyword that decided
  it, what is missing, and the **near misses**. A near miss is a signal that almost matched, together
  with why it did not (for example `nav2.lattitude`: a misspelling one edit away from an alias; or
  `nav2.lat_cmd`: the role word is followed by a suffix that marks a command, not a measurement).
- **Unit suffixes are accepted**, not near misses: `lat_deg`, `lat_rad`, `alt_m`, `alt_ft`, `yaw_deg`.
  The suffix also feeds the unit guess and is named in the explanation as the reason for the unit.
- Keep it fast: test names once per signal list, cached, like `guessRoles` today (a 5000-signal file
  must stay within a few ms).

**Dialog** (`ObjectDialog.tsx` becomes two levels):
- The first screen is **Objects found in this recording**. It shows one row per candidate across the open
  files. Each row has a checkbox, an editable name, a class badge (truth / navigation / receiver), a
  kind icon, a colour, the signals it found as small chips, and **Why?**. Candidates already on the plot
  are shown as added.
- The primary button is **Add all (N)**. It appears whenever two or more candidates are found. The
  secondary button is **Add selected**, with **Select all / none** above the list. All rows start
  checked except those already on the plot. Both buttons are one commit and one undo.
- **The suggestion comes to the user.** When a file with at least one new candidate is opened, a
  non-blocking suggestion appears (a slim bar in the signal list, not a modal):
  *"3 objects found: phys, nav, gps · Add all · Choose… · Why?"*. **Add all** adds them to the map/3D
  plot (it creates one if the tab has none). **Choose…** opens the dialog above. Nothing is added without
  a click. Dismissing it hides it for that file; it stays reachable from the dialog and the template.
  The bar has its own e2e case.
- **Why?** expands the explanation in plain words, for example: *"Position: nav.lat / nav.lon / nav.alt
  (names under the prefix nav). Attitude: nav.att.roll/pitch/yaw (sub-group att of nav). Class: navigation
  (the word 'nav')."* It also lists the missing roles and the near misses.
- A short, always-visible **"How to name your signals"** note gives the convention
  `<object>.lat / lon / alt / roll / pitch / yaw` (sub-groups allowed: `<object>.att.roll`), a copyable
  example with three objects, and a link to the Help section. This is what lets the user arrange the
  recording so the guess just works.
- **Advanced…** on a row opens today's detailed form for that object, with frames, smoothing, units,
  altitude reference and track colour. Nothing that exists today may be lost.
- Default look by class: truth is a solid line with the object's icon; navigation is dashed; a receiver
  is drawn as points, with an outlined icon oriented by its derived attitude (see "Attitude source").
  Everything stays editable.

**Template:** "Position on the map & 3D" adds **all** candidates of the file, not one. Its toast says
what was added and offers *Why?* (opens the explanation) and *Undo*. Example: *"3 objects: phys (truth),
nav (navigation), gps (receiver) · Why? · Undo"*.

**Docs:** the naming convention goes in Help, in the user guide (`docs/`, including the Hebrew guide
GUIDE.he) and in the README's map section.

Done when the 19-signal fixture gives three correctly classified objects with no mixed sources and one
click adds them all; a file with `nav1.*` and `nav2.*` proposes both; every explanation names its rule;
and the copter `.bin` still works.

Tests: Vitest for detection (fixture names, multi-nav, `_` prefixes, the known log groups, near misses,
performance on 5000 names), and the attitude sources: course and flight-path angle from motion on a
known track, heading held below the speed threshold, a borrowed attitude interpolated across 359°/1°). E2E: `test_map_objects.py`, `test_object_templates.py`,
`test_object_frames.py`, `test_globe3d.py`, `test_hover_ghost.py`, plus new cases for Add all and Why?.

### N6 – Smooth motion and an easy map (Tacview-like) – the friend's top priority

The friend compares the app with **Tacview**. What matters most to him is that **motion is smooth** and
that **the map is easy to move**. Treat smoothness as a requirement with numbers, not as polish.

**First, measure.** Use the 19-signal fixture with three objects, and also the copter `.bin`. Record the
frame time during playback at ×1 and ×10, during a map pan, and during a wheel zoom, on the map and in
3D. **Method:** a small timing hook, enabled only in tests/benchmarks, that records the intervals between
`requestAnimationFrame` callbacks and the React render count per frame; drive it from Playwright so the
same script runs later in `tools/browser_benchmark.py`. Report median and 95th-percentile frame time and
the number of dropped frames. Write the numbers, and the machine (CPU, GPU or software rendering,
headless or not), in the Log. Places to check first:
- Playback (`App.tsx`, the `playing` effect) writes `cursor.t1` to the global store on every animation
  frame. Check how much of the app re-renders per frame (all plots, the signal list, the Inspector). The
  map and 3D should redraw their moving parts from a ref or subscription, not through a full React render.
- In `GeoChart.tsx`, the cached base layer (`baseRef`, keyed by the view) is rebuilt on every
  `mousemove` of a pan and every wheel step. Every pan frame redraws tiles, including the offline map
  that the app draws itself.

**Targets.** The absolute targets are for the owner's laptop; the agent's machine may be headless with
software rendering, where they cannot be reached. So:
- **Relative targets (checked by the agent and by the benchmark):** the per-frame React render count
  during playback drops to the moving parts only (plots, signal list and Inspector do not re-render per
  frame); pan frame time improves on the baseline by a clear margin; nothing gets slower than the
  baseline. The benchmark threshold is set from the measured baseline, not as an absolute fps.
- **Absolute targets (checked by the owner on Windows, listed in the N9 summary as "to verify"):**
  playback at 60 fps on the map and 3D with three objects, and no worse than today on a 1 GB `.bin`.
- Pan and zoom follow the pointer within one frame. There is no blank or flashing tile area while
  moving: show the previous tiles stretched or shifted until the new ones are ready.

**Smooth motion:**
- Objects are drawn at the **interpolated** position and attitude for the exact frame time (`objectAt`
  already lerps; check that 3D does the same, including attitude, the short way round). There must be no
  stepping at the logging rate, even for a 5 Hz GPS.
- The camera in **Follow** and **Chase** moves smoothly. Add light damping so it does not jitter with
  noisy positions, and add an option to turn it off.
- The playback speeds (×0.25 … ×64) stay smooth. Reverse playback is a nice-to-have.

**Easy map movement** (2D map):
- **Pan by transform.** During a drag or a zoom, move the already-drawn base image (translate / scale)
  and redraw tiles only when movement pauses, or in the background. Add **inertia** after a quick drag
  (a short glide, off in reduced-motion mode).
- **Zoom** is smooth (animated, not stepped) around the pointer, with the wheel, a trackpad pinch,
  **+ / −** buttons and double-click (zoom in) / **Fit all** button (today double-click fits – keep it
  discoverable via the button and the hint).
- Add floating controls in a corner: **+ / −**, **Fit all**, **Follow ▾** (choose an object; this uses
  `followObject`), and **North up / Track up**. Respect RTL and both themes.
- A drag while following does not fight the user. Following keeps the object centred but lets the user
  offset it (as Tacview's camera does around the selected object). **Back to following** recentres.
- Add keys that work only when the map plot is focused: arrows pan, `+` / `−` zoom, `F` follows, `0`
  fits all. Today, bare ←/→ step the cursor and Home/End jump to the start/end of the recording
  (`shortcuts.ts`), so: while the map is focused the arrows pan (Shift+←/→ still steps the cursor there),
  and Home/End keep their timeline meaning everywhere. `0` is free (digits 1–9 pick a plot; Ctrl+0 is UI
  scale). Do not clash with `]` / `[`, `P`, `R`, `Z`, `D`, `N` or Space. *Owner question (ask the friend
  about Tacview's keys) – Default if unanswered: the keys above.*
- Show a one-line hint on first use: *"drag to move · wheel to zoom · double-click to fit"*. Once the user
  dismisses it, the dismissal is remembered.

**3D camera** (Globe3D):
- Camera modes: General (today); **Chase** (behind and above the primary object, following its heading);
  **Orbit** (around the primary object, mouse drag rotates around it, wheel changes the distance, the
  object always stays in the centre); **Look at** (from the primary towards the secondary object, see N7);
  **On the object** (today).
- Switching mode or object flies the camera there in a short animation, not a jump.
- Show a short hint of the mouse controls for the current mode.

Do not claim Tacview behaviour from memory. Where a detail matters (key bindings, exact camera
behaviour), write the question for the owner, who can check with the friend.

Tests: a new `test_map_smooth.py` (the buttons, follow pause/resume, keys, the hint), plus
`test_offline_map.py`, `test_map_objects.py`, `test_globe3d.py`, `test_wheel.py`, `test_hover_ghost.py`. Add
a frame-time check to the benchmarks (`tools/browser_benchmark.py`) with a threshold, so smoothness does
not regress later. It runs only in N9, like the other benchmarks.

### N7 – Primary and secondary objects, and the relations between them (Tacview-like), plus navigation error signals

As in Tacview, the user picks a **primary object** and a **secondary object**, and sees the relation
between them live.

**Choosing them:**
- On the map, in 3D and in the object row: a click selects the **primary** object, and Shift+click (or a
  right-click menu *Set as secondary*) selects the **secondary** object. Both are clearly marked (for
  example a ring for the primary and a dashed ring for the secondary), in both views and in the object chips.
- Add a key to cycle the primary object and one to swap primary and secondary, both active only when
  the map or 3D is focused. Do **not** use Tab: it would trap keyboard focus inside the map (Ctrl+Tab
  already cycles tabs). Proposed: `Q` / Shift+`Q` cycles the primary, `X` swaps primary and secondary.
  *Owner question – Default if unanswered: Q / Shift+Q / X.*
- The defaults come from N5's classes: the primary is the *truth* object, and the secondary is the first
  *navigation* object. When there is no truth object (a typical flight log), the primary is the first
  *navigation* object (for ArduPilot, the EKF `POS` group), and the secondary is the first *receiver*.
  With a single object, there is no secondary and the relation panel stays hidden. The choice is saved in the plot (optional fields, old sessions unchanged). The map
  and 3D of the same tab share it.

**The relation panel** (a small overlay box in the map and in 3D, collapsible), at the cursor time:
- horizontal distance, slant range (3D), Δalt;
- bearing from primary to secondary, and the relative bearing from the primary's heading;
- **closure rate** (the rate of change of the range; positive when closing) and the time to closest
  approach when they are closing;
- the angle between the two headings (0–180°), and the aspect angle of the secondary: the angle at the
  secondary between its tail and the line to the primary, 0–180°, with L/R. 0° means the primary is
  directly behind the secondary; 180° means head-on. Put these definitions in the Help text and in the
  backend docstrings, and test them;
- the units follow the app's unit settings.

On the map and in 3D, a line connects the two objects, labelled with the range. A toggle sets it to show
for the pair only, for the primary to every object, or off.

**Over time:**
- *Plot the relation*: make derived signals for range, Δalt, bearing and closure rate between the
  pair, and open a time tab linked to the map cursor in one click.
- **Navigation errors.** Add *Make error signals vs. primary* on an object, and for all objects at once.
  It creates derived signals: horizontal error (m), vertical error (m), 3D error (m), and heading error
  (deg, wrapped to ±180). With attitude, it also creates roll and pitch errors. Group them so N1 nests
  them, e.g. `nav_vs_phys.err.horiz` (ASCII only, so users can type it in search).
- **Comparison and difference plots, in a chosen frame (owner's request).** Once objects are defined,
  offer the comparison plots instead of waiting for the user to build them:
  - **Where it is offered:** in the suggestion bar right after objects are added (*"Compare objects ·
    frame: NED ▾ · Make plots"*), in the object row's menu, and in the relation panel. Nothing is created
    without a click; the result is one commit and one undo.
  - **Pairs:** by default every object against the primary (normally truth). The user can pick one pair
    instead. One click makes one time tab, linked to the map cursor, with one plot per component.
  - **Two kinds of plot:** *Compare* overlays the same quantity of every object on one plot (north of
    phys, nav and gps together). *Differences* plots secondary − primary per component, and also
    horizontal, vertical and 3D error.
  - **Frames to choose from:** NED (default), ENU, ECEF, LLA, and track frame (along-track /
    cross-track / vertical, aligned with the primary's heading). Each choice states its meaning in its
    tooltip.
  - **The frame maths must be right, not just convenient:**
    - *Differences* in NED / ENU are expressed in the local frame **at the primary's position at each
      sample**: ECEF difference, rotated by the primary's lat/lon at time t. A fixed-origin NED would
      tilt the error over a long flight.
    - *Compare* overlays in NED / ENU use **one shared origin** for all objects (default: the primary's
      first valid position; the existing `ref` choices first / manual / signals also apply), or the
      curves are not comparable.
    - ECEF differences need no origin. LLA differences show Δlat / Δlon converted to metres (north /
      east), with Δalt; raw degrees only on request.
    - Velocities, when every object in the pair has them (`vel.north/east/down` or ECEF velocities), get
      the same treatment: compare and differences, in the same frame.
    - Attitude differences are per-angle and wrapped to ±180°. A derived attitude is labelled as such
      in the signal name and tooltip. When an object's attitude is borrowed from the very object it is
      compared with, skip its attitude differences (they would be zero by construction) and say so. *Owner question – Default if unanswered:
      Euler-angle differences; the rotation-based error (small-angle vector from the relative rotation)
      is offered later if wanted.*
  - **Reuse, don't duplicate:** `svcore/analysis.py` already has `lla_to_ecef`, `_ecef_to_ned`,
    `_reference` and the frame ops (LLA / ECEF / NED / ENU / body). Build the new op on top of them; do
    not write a second set of frame conversions. Units follow the app's unit settings.
- All of these are computed in the **backend** as a derived-signal op in `svcore`, alongside the existing
  frame ops. Use the existing derived-signal mechanism; do not add a parallel one. The rules:
  - Interpolate the secondary onto the primary's time base.
  - Missing stays missing (C3).
  - Interpolation gets its ≈ trust badge (26.U6).
  - Large files stay fast (decimated data to the UI).
- The live panel may compute the values at the cursor in the frontend for speed. Test that they equal
  the backend's numbers.
- The existing "Measure" (two clicked points) stays as it is.

Tests: backend pytest for the new ops, with known geometry: a fixed offset of N metres in a direction,
two objects closing head-on at known speeds (closure rate, time to closest approach), and a heading wrap
across 359°/1°. For the frame plots: a known offset of N metres north gives N in the north difference
and zero in east/down, in NED at the primary for an object far from the origin (e.g. 200 km away), and
the same vector rotated correctly in ENU, ECEF and the track frame; compare overlays share one origin.
Vitest for the frontend maths and for primary/secondary selection and defaults. E2E: a new
`test_object_relations.py` (select primary/secondary, panel values at a known time, swap, plot the
relation, make comparison and difference plots in NED and ECEF), plus `test_map_objects.py` and
`test_globe3d.py`.

### N8 – (Optional – ask the owner first) Export to Tacview `.acmi`

Export the objects of a map/3D plot to a text ACMI file, so users who know Tacview can open the same
flight there. Verify the format, header and the field order of `T=` against Tacview's published ACMI 2.x
specification (ask the owner for it if you are offline); do not rely on memory. The backend writes the
file, and the UI offers it through the existing save mechanism. Backend tests cover a known small file.

### N9 – Release preparation (the only full verification)

1. Bump the version as `backend/app/version.py` and TASKS.md "Releasing" describe (build.bat,
   installer; a test keeps them equal).
2. Update the user-facing material: `CHANGELOG.md` (user-facing wording), README (the map section, the
   naming convention, new pictures if `tools/make_readme_media.py` allows), and the English and Hebrew guides.
3. Run the **full** checks, all of them, and record each result in the Log:
   - `cd backend && python -m pytest -q`
   - `mypy --config-file ../pyproject.toml app svcore signalviewer`
   - `python cli.py validate`
   - `cd frontend && npx tsc -b && npm run build && npm test`
   - the **whole** e2e suite (`python -m pytest -q tests/e2e`)
   - `tools/benchmark.py --synthetic --check`
   - `mkdocs build --strict`
4. Fix failures, rerun what failed, then rebuild and commit `frontend/dist`. **Do not tag or publish.**
   The owner runs CI, builds on Windows and tags. End with a short summary for the owner: what changed,
   what was decided (including every *Default if unanswered* that was used), what is left open, and what
   the owner must verify by hand on Windows (the absolute smoothness targets of N6, the installer, the
   Cesium 3D view on a real GPU).
5. **Deliver** the release candidate as a `git bundle` from `dafea49` to the final commit, plus the
   patch series, so the owner can apply it to the repository and push it himself.

## 4. Invariants to watch in this round (from CLAUDE.md – the ones most at risk)

- Signal ids stay `"<runId>/<n>"`. Every workspace change goes through `commit`.
- Sessions, templates and autosave stay backward compatible. New fields are optional with defaults
  (`lineStyle`, the reference object, object class). An old session with `dash` and single objects opens unchanged.
- Every new string goes through `frontend/src/i18n/` in **English and Hebrew**, in the right area file.
  Check every new control in RTL and in both themes.
- Each control lives in one place: Settings for defaults, the plot's row or menu for plot things, the
  signal list for list things. Shortcuts and the command palette are the only second entry points.
- Heavy maths (error signals) stays in the backend. Cesium and map data stay lazy-loaded.
- Fully offline. Nothing new talks to the network.
