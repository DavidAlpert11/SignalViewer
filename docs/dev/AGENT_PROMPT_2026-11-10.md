# Agent prompt – Signal Viewer, owner's round of 2026-11-10: local-position objects, comparisons, moving plots, map export, a scripting API

> ## Status – read this first (update at the end of every session)
>
> **Stage reached: group A done (L0-L6) and L7 done, 2026-11-10.** Next: **L8**. Work order: **L0 → L1 → L2 → L3 → L4 → L5 → L6 → L7 → L8 → L9 → L10 → L11 → L12 → L13.**
> Group A's and L7's code maps, decisions (1-8) and the new question Q14 (`ref` as origin vs trajectory) are in
> `TASKS.md` → "Owner's plan (2026-11-10)". In short: `objectDetect.ts` (`metricPosition`, per-group
> NED / ENU decision, `KNOWN_GROUPS` with `ned / vel / origin / order / lane / skip`, `originOf`,
> `isOriginGroup`, `Candidate.origin / badUnit / lane`), `objectAdd.ts` (`addable`, `objectSources`,
> `firstSource`, `isAdded(c, plot, derived)`, `candidateObject` with `ref: "signals"`, `whyLines`),
> `ObjectDialog.tsx` (`frameLabel`, `suggestedOrigin`), `ObjectSuggestBar.tsx`; tests
> `objectDetect.test.ts`, `mapObjects.test.ts`, `backend/tests/test_local_objects.py`,
> `tests/e2e/test_local_objects.py`; fixtures `tools/make_local_objects_fixture.py`.
> L7: `RelationPanel.tsx` (`RingIcon`, `RelationPicker` - also in `Globe3D.tsx`'s bar), the ring tooltip in
> `GeoChart.tsx`, chips in `PlotView.tsx`, Ctrl+K, Help; words Reference / Compared with (he בסיס / מושווה).
> The whole e2e of group A was cut off at ~74% (green until then) - run it in full at the end of group B.
> **Left for L13:** the naming convention in the guides (en + he), `docs/features.md`.
> The patch does not include `frontend/dist` (built in L13). Apply: `git am < signalviewer-2026-11-10.patch` on `d61ab6d`.
> Groups (whole e2e at the end of each): **A** = L0–L6 (local positions), **B** = L7–L9 (primary / secondary made clear, comparisons),
> **C** = L10–L11 (moving plots, map export), **D** = L12 (API), **E** = L13 (release). If time is short,
> finish a group and stop cleanly rather than start the next one.
>
> **Base and patch.** The owner applies each patch and pushes it to `main`. Make every session's patch
> against `main` as it is when the session starts (at the time of writing: `d61ab6d`, "Release 1.24.0").
> ```
> git clone https://github.com/DavidAlpert11/SignalViewer.git && cd SignalViewer
> git log --oneline -3          # the base: main's HEAD
> cd frontend && npm ci && npx tsc -b && npm test
> ```
> At the end: `git format-patch <base>..HEAD --stdout > signalviewer-<date>.patch`, check it with `git am`
> on a fresh clone of `main`, update this Status box and the board in `docs/dev/TASKS.md`
> ("Owner's plan (2026-11-10)"), and hand both files to the owner. Keep a copy of this prompt in the repo
> as `docs/dev/AGENT_PROMPT_2026-11-10.md` and keep the two copies equal.
>
> Milestone 28 in `ROADMAP.md`; board, decisions, open questions (Q1–Q13, each with a default) and the Log
> in `TASKS.md` → "Owner's plan (2026-11-10)".

---

## The goal

Today, when an open file has `lat / lon / alt` (+ attitude) under a prefix, Signal Viewer finds it as a
map object and offers it in the suggestion bar (*"3 objects found … Add all · Choose… · Why?"*). The owner
wants the same for objects whose position is given **in metres in a Cartesian frame – NED, ENU or ECEF**.
The motivating case: **ArduPilot logs every EKF lane's solution in NED** (`XKF1[0].PN / PE / PD`,
`XKF1[1].…`, older EKF2 logs `NKF1[n].…`), relative to the EKF origin (`ORGN`). Each lane should be found
as a navigation object with its own attitude, placed on the map through its origin, and offered in one
click – exactly like `POS` is today. The same for PX4 / MAVLink local positions and for generic names
such as `tgt.ned.x` or `ship.ecef_x`.

The owner then asked for more in the same round (groups B–D):
0. **The rings around objects explained, and one clear place to choose them** (L7): the solid amber ring
   (the primary – the reference) and the dashed one (the secondary) mean nothing to a user who has not
   read the guide, and changing them is hidden in a chip's context menu and keys.
1. **Comparing objects, discoverably** (L8): one easy place to compare objects – **positions, velocities
   and angles** – showing both **the values themselves** and **the errors relative to a reference object
   the user chooses**.
2. **Comparing similar nested signals** (L9): when nested names are similar (`nav1.att.roll`,
   `nav2.att.roll`, `truth.att.roll`; `XKF1[0].Roll`, `XKF1[1].Roll`), offer to compare them – the user
   picks from a list.
3. **Moving a plot beyond its tab** (L10): to a new tab, into another tab's grid, or into another plot
   (its lines join that plot).
4. **Exporting the map** (L11): an image of the map (PNG) and a standalone HTML file with the map, and the
   map inside reports.
5. **A clear API for the whole process** (L12): load → find objects → compare → statistics → export data,
   map and report, from Python, from the command line and over the local REST API – documented.

**Much of the machinery already exists – extend it, do not build a parallel one** (CLAUDE.md, "one way
to do a thing"). Read section 1 before writing anything.

---

## 0. Before you write any code

1. Read `/CLAUDE.md`, `docs/dev/TASKS.md` (Current state + the 2026-11-09 round), `docs/dev/ROADMAP.md`
   Milestone 27 and `docs/dev/AGENT_PROMPT_2026-11-09.md` §N5 / §N7 (the detection rules and the owner's
   decisions 1–5 still hold; this round extends them).
2. Read these files fully, and `grep` every caller of what you change across `frontend/src/` and
   `backend/`:
   - `frontend/src/objectDetect.ts` – names → candidates (`parseName`, `detectNow`, `KNOWN_GROUPS`,
     `ATT_GROUPS`, the frame tables `NED_WORDS / ENU_WORDS / XYZ / FRAME_WORDS / POS_SUB / VEL_SUB`).
   - `frontend/src/objectAdd.ts` – `addable`, `isAdded`, `candidateObject`, `whyLines`.
   - `frontend/src/components/ObjectSuggestBar.tsx`, `frontend/src/components/ObjectDialog.tsx`
     (`readSetup` walks the `vecsmooth` → `frame` derived chain; the form's `PosSetup`, `refMode`).
   - `frontend/src/frames.ts` – `createFrameGroup`, `suggestFrames`, `NED_VEL`, `NED_XYZ_GROUPS`.
   - `frontend/src/mapObjects.ts` (`guessRoles`), `frontend/src/relation.ts` (N7 comparisons).
   - `backend/svcore/analysis.py` – the `frame` op: `qty: "position"`, `_reference` with
     `ref: "first" | "manual" | "signals"` (signals = three more sources lat / lon / alt; their first valid
     sample is the origin). **This already converts NED / ENU / ECEF → LLA. No new backend op is needed.**
   - For L8–L12 also: `frontend/src/relation.ts` (`compareObjects`, `overlayObjects`, `errorSignals`,
     `plotRelation`), `components/RelationPanel.tsx`, `components/ObjectSuggestBar.tsx` (the compare offer),
     `backend/svcore/relate.py` (op `relate`, its docstring has the definitions), `frontend/src/errors.ts`
     (errors between the two lines of a plot), `pairing.ts` (`distinctParts`), `peers.ts`,
     `components/ComparePanel.tsx` (runs against a golden run), `store/actions/layout.ts` (`swapPlots`,
     `moveActivePlot`, `moveTab`), `store/actions/plots.ts` (`plotsInNewTab`: at most 6 plots × 10 lines),
     `components/TabBand.tsx`, `components/PlotView.tsx` (the ⋯ menu, drag MIME types),
     `components/GeoChart.tsx`, `backend/app/basemap.py`, `backend/app/report.py`,
     `backend/app/routes/export.py`, `backend/signalviewer/__init__.py` (Python API),
     `backend/signalviewer/cli.py`, `docs/command-line.md`.
   - Tests: `frontend/src/objectDetect.test.ts`, `frontend/src/mapObjects.test.ts`,
     `tests/e2e/test_map_objects.py`, `tests/e2e/test_object_frames.py`, `tests/e2e/test_object_templates.py`.
3. Run the baseline and write the numbers into the Log: `cd backend && python -m pytest -q`, mypy (command
   in CLAUDE.md), `cd frontend && npx tsc -b && npm test`. Note any failure that exists before you start.

---

## 1. Findings from the review (verified on `d61ab6d` by running `parseName` / `detectObjects`)

What already works:
- `Candidate.pos` is `"lla" | "ned" | "enu" | "ecef"`; roles `px / py / pz` carry a metric position.
- Found today: `tgt.pos.north / east / down` (NED under a position sub-group), `ship.ecef.x / y / z` and
  `ship.ecef_x` (ECEF by its word), `tgt.enu.east / north / up`.
- ECEF candidates are addable: `candidateObject` makes an `ecef → lla` frame group.
- NED / ENU candidates are listed but **not addable** (`addable()` returns false → "needs an origin –
  Advanced…"). The form (`ObjectDialog`, preset) then opens with `refMode: "manual"` and empty fields.

Gaps and bugs (each one is covered by a task below):

| # | Name / case | Today | Why |
|---|---|---|---|
| F1 | `XKF1[0].PN [m]`, `PE`, `PD` (ArduPilot EKF3 lanes), `NKF1[n].…` (EKF2) | not found | `PN/PE/PD` are in no table; `XKF1` / `NKF1` are in `ATT_GROUPS` (treated as attitude-only groups) |
| F2 | `vehicle_local_position.x / y / z` (PX4), `LOCAL_POSITION_NED.x / y / z` (MAVLink) | not found | x/y/z need a frame word; `frames.ts` already knows these groups are NED (`NED_XYZ_GROUPS`) but `objectDetect.ts` does not use it |
| F3 | `nav.ned.x`, `nav.x_ned`, `nav.pos_ned_x`, `tgt.enu.x` | not found | under a NED / ENU frame word, `x/y/z` are looked up in `NED_WORDS` / `ENU_WORDS` (north/east/down) and miss |
| F4 | `ship.ecefX`, `ship.X_ECEF`, `ecef_x` vs `x_ecef` | only `ecef_x` / `ecef.x` | glued and suffix forms not parsed |
| F5 | `tgt.pos.north / east / up` | **no candidate at all** | north/east under `pos` default to NED, `up` goes to ENU → neither frame is complete |
| F6 | `tgt.pos.n / e / d` | not found | single letters are accepted only for velocity |
| F7 | `ORGN[0].Lat / Lng / Alt`, `vehicle_local_position.ref_lat / ref_lon`, (and by the same rule `HOME_POSITION.*`, `GPS_GLOBAL_ORIGIN.*`, PX4 `home_position.*`) | **found as objects** (`ORGN[0]`, `vehicle_local_position.ref`, class *other*) | they are origins / home points, not moving objects – they belong to the object they are the origin of |
| F8 | An ECEF (or any converted) object, after *Add all* | **offered again** by the suggestion bar; *Add all* again adds duplicates | `isAdded` and the bar compare `c.picks.lat` with `o.lat`; a converted candidate has no `picks.lat` and the object's `lat` is a derived id. `isAdded`'s comment says "or ECEF x through its frame chain" – the code does not do it |
| F9 | `XKF1[n].VN / VE / VD` | velocity not picked | velocity roles are only read under a `vel` sub-group; `frames.ts` has the flat field table (`NED_VEL`: vn/ve/vd, veln…, vel_n…) |
| F10 | `ros: /odom.pose.pose.position.x` | near miss "noframe" | correct – the frame is unknown; keep it a near miss (see Q3) |

Things to be careful about (not bugs today, but this round touches them):
- **Do not auto-pair `XKQ[n].Q1..Q4`** (ArduPilot lane quaternions): in ArduPilot `Q1` is **w**, but the
  alias table maps `q1 → qx`. XKF1 lanes have their own Euler angles; use those. Log the XKQ issue as a
  follow-up, do not change the alias table in this round.
- `ORGN` has an instance field (`ORGN[0]` = EKF origin, `ORGN[1]` = AHRS home in current firmware).
  **Verify on a real log** (ask the owner for one with two EKF3 lanes) before relying on the instance
  meaning; if instances are absent, match the group without an instance.
- `ORGN.Alt` and `POS.Alt` are above mean sea level, while the `frame` op's reference altitude is described
  as height above the ellipsoid. Using `ORGN` keeps the lane track consistent with `POS` on the map (both
  AMSL); say so in *Why?* rather than "correcting" it.
- PX4's local origin can be reset during a flight (`ref_timestamp`, `xy_reset_counter`). The backend takes
  the first valid sample of the reference signals. Out of scope to support a moving origin – mention it
  in *Why?* for PX4 local positions (see Q5).
- Every object added from a local position is an LLA object after conversion (derived signals), so N7
  relations, Tacview export, sessions and live mode should need nothing new – L6 verifies that.

### Findings for L8–L12 (verified by reading the code on `d61ab6d`)

- **Comparisons exist but are scattered and partial.** The relation box on a map (`RelationPanel`, only
  when the map has ≥ 2 objects) has four actions: *Plot the relation*, *Error signals* (pair only:
  horiz / vert / 3D, heading, roll and pitch), *Differences* in a frame (`compareObjects`: Δ per axis +
  horiz / vert / 3D, velocity differences when both have `vel` – **no angles**), *Overlay* (`overlayObjects`:
  position values only – **no velocity or angle values**). The suggestion bar offers *Differences* once,
  right after objects were added, then it is gone. A user who did not add objects through the bar has
  to find the small box on the map.
- `plotsInNewTab` silently keeps at most 6 plots and 10 lines each – a comparison of many objects or of
  position + velocity + angles can lose plots without a word.
- **Similar signals:** there is pairing by the differing part of names (`pairing.ts` `distinctParts`,
  "One into each plot"), errors between the two lines of a plot (`errors.ts`), and Compare of the same
  signal across *files* (ComparePanel). There is no way to find *within one file* the signals that differ
  only by their owner (`nav1` / `nav2` / `truth`, `[0]` / `[1]`) and compare them.
- The `sub` op (used by `errors.ts` and ComparePanel) **does not wrap angles**: yaw 359° vs 1° gives 358°.
  `relate` does wrap (`err_hdg` etc.).
- **Moving plots (N2)** is swap-within-the-tab only (`swapPlots`, drag handle, *Move to…* mini grid,
  Ctrl+Shift+Arrow). No move to another tab, no move into another plot. `MAX_PLOTS = 9` per tab.
- **Map export:** the 2D map (`GeoChart`, canvas with tiles) has no image or HTML export; the report
  (`report.py`) has no `geo` mode, so maps are not in reports. The 3D view saves a PNG
  (`/api/save/image`, `Globe3D` `toDataURL`). The offline basemap tiles are drawn by the backend
  (`app/basemap.py`), so the backend can render a map image without a browser. Tacview export exists.
- **API:** Python `signalviewer.load()` → `Recording` (signals, `to_dataframe`), `sv.show()` (push into
  the open app); CLI `info / export / report (from a template) / check / compare (runs vs golden) / sweep /
  templates`; REST endpoints under `/api/*` with FastAPI docs at `/api/docs`. **Nothing for objects:**
  object detection exists only in TypeScript (`objectDetect.ts`), and the comparison orchestration only
  in `relation.ts`, so a script or CI cannot do what the UI does.

---

## 2. Testing policy for this round

CLAUDE.md applies. In addition:
- Every parsing rule in L1–L3 gets a Vitest case in `objectDetect.test.ts` (the table in §1 is the
  minimum list: each row must have a test that fails on `d61ab6d` and passes after your change).
- Keep the existing test "is fast on 5000 names and cached" green (< 100 ms); add 5000 names with
  metric-position signals to it.
- L8–L12: Vitest for every new pure function (grouping of similar names, move-plot actions + Undo,
  comparison layout); pytest for every backend change (angle-wrapped difference, comparison statistics,
  map rendering, the new endpoints, the Python API and CLI commands – run the CLI on the fixtures in the
  test); e2e for each new UI flow (new files `tests/e2e/test_compare_objects.py`,
  `test_compare_similar.py`, `test_move_plots_tabs.py`, `test_map_export.py`).
- After each task run only the relevant e2e files (`test_map_objects.py`, `test_object_frames.py`,
  `test_object_templates.py`, `test_object_relations.py` as they apply); the whole e2e suite at the end
  of L6 and in L8. Say in the Log which e2e ran.

---

## 3. The tasks, in order

### L0 – Baseline, fixtures and notes — S

- Baseline numbers into the Log (§0.3).
- Extend `tools/make_objects_fixture.py` (or add `tools/make_local_objects_fixture.py`) to write, from
  one known flight path (≈ 2 km, climbing and turning, 10 Hz, 5 min, origin at a fixed lat / lon / alt):
  - `examples/ardupilot_lanes.csv` – ArduPilot names as the .bin loader makes them:
    `POS.Lat [deg] / POS.Lng [deg] / POS.Alt [m]`, `ATT.Roll / Pitch / Yaw [deg]`,
    `XKF1[0].Roll / Pitch / Yaw [deg]`, `XKF1[0].VN / VE / VD [m/s]`, `XKF1[0].PN / PE / PD [m]`, the same
    for `XKF1[1]` with a small, known offset (e.g. +1.5 m north) so the two lanes are visibly different,
    `ORGN[0].Lat [deg] / Lng [deg] / Alt [m]` (constant), `GPS[0].Lat / Lng / Alt`.
    PN/PE/PD must be computed with the **exact** LLA → NED conversion (the same maths as
    `svcore/analysis.py`), so lane 0 converted back must land on POS within 0.05 m.
  - `examples/local_frames.csv` – generic names: `tgt.ned.x / y / z`, `ship.ecef_x / _y / _z`,
    `boat.pos.north / east / up`, `rov.pos.n / e / d`, `origin.lat / lon / alt`.
  - A PX4-style CSV is optional (names `vehicle_local_position.x / y / z / vx / vy / vz / ref_lat /
    ref_lon / ref_alt`, `vehicle_attitude.q[0..3]`).
- Write what you read in §0.2 that this round touches into the task notes (callers of `isAdded`,
  `addable`, `detectObjects`, `ATT_GROUPS`).

**Done when:** baseline logged, fixtures generated by a script (committed with the script), notes written.

### L1 – Parsing metric positions by name (generic rules) — M

In `objectDetect.ts`, extend `parseName` and its tables (keep them "one place, easy to extend"):
1. **x / y / z under a frame word, any form** (F3, F4): `ned.x`, `pos.ned.x`, `x_ned`, `ned_x`, `pos_ned_x`,
   `enu.x`, `x_enu`, `ecef.x`, `ecef_x`, `x_ecef`, `ecefX`, `X_ECEF`, `ecef_X`, and `[m]` / `_m` units.
   In NED, x/y/z mean north/east/down; in ENU east/north/up; in ECEF X/Y/Z. Glued forms (`ecefX`) only
   with a frame word, never bare `posX`.
2. **Frame decided by the whole group, not by each name** (F5): when a prefix has north / east plus
   `up` → ENU; north / east plus `down` → NED. Fix it where the frames are assembled in `detectNow`
   (collect the words per prefix, decide the frame once), not by special-casing `up` in `parseName`.
3. **Single letters `n / e / d`** (F6) only directly under a position or frame sub-group (`pos.n`,
   `ned.n`), never at the prefix level (`nav.n` is not a position).
4. **Units** (`[cm]`, `[mm]`, `[km]`, `_cm`…): a metric position whose unit is not metres is **not addable
   by *Add all*** and *Why?* says "position in cm – convert it to metres first (ƒ)". Do not add silent
   scaling in this round (Q6).
5. **Flat velocity fields** (F9): `vn / ve / vd`, `veln / vele / veld`, `vel_n / vel_e / vel_d` right under a
   prefix that already has a position. Take the field table from `frames.ts` (`NED_VEL`) – move it to one
   shared place that both files import; do not copy it.
6. Bare `x / y / z` with no frame word stay a near miss `noframe` (F10), with a clearer *Why?* line:
   "x / y / z with no frame – name it `ned.x` / `enu.x` / `ecef.x`, or choose the frame in Advanced…".

**Done when:** every L1 row of §1 has a passing test; the existing tests pass unchanged; the 5000-name
test is still < 100 ms.

### L2 – Known flight-log groups with local positions — M

Extend `KNOWN_GROUPS` (same table, new optional fields; e.g. `ned?: [string, string, string]` field
words for px/py/pz, `vel?`, `origin?: string[]` groups to take the origin from):
- **ArduPilot `XKF1` (EKF3) and `NKF1` (EKF2), every instance** (F1): class *navigation*, position NED from
  `PN / PE / PD`, velocity `VN / VE / VD`, **its own** `Roll / Pitch / Yaw`, origin from `ORGN` (L3).
  Remove `XKF1` / `NKF1` from `ATT_GROUPS`, but keep what that set protects: a top-level group name is a
  group, not an attitude sub-group (`XKF1[0].Roll` must not make `XKF1[0]`'s parent an object). Check
  every use of `ATT_GROUPS` before removing.
  - Name: the prefix (`XKF1[0]`, `XKF1[1]`) as the convention says; *Why?* adds "EKF3 lane 0".
  - Order in the list: after `POS` (POS is the EKF's chosen output; lanes after it, then AHR2, then GPS).
- **PX4 `vehicle_local_position`** (F2): NED from `x / y / z`, velocity `vx / vy / vz`, origin from its own
  `ref_lat / ref_lon / ref_alt` (L3), attitude from `vehicle_attitude` (the existing `attFrom` rule).
  Take the group list from `NED_XYZ_GROUPS` in `frames.ts` – one definition, imported.
- **MAVLink `LOCAL_POSITION_NED`**: NED from `x / y / z`, velocity `vx / vy / vz`, origin from
  `GPS_GLOBAL_ORIGIN`, else `HOME_POSITION` (L3), attitude from `ATTITUDE` / `ATTITUDE_QUATERNION`.
- Check the field names against the loaders (`backend/svcore/bin_loader.py`, `ulog_loader.py`,
  `tlog_loader.py`): the names in the table must be the names the loaders produce, including units in
  brackets and instance brackets. Write in the notes which ones you confirmed on real files and which
  only from the loaders' code.

**Done when:** on `examples/ardupilot_lanes.csv` the candidates are, in order,
`POS, XKF1[0], XKF1[1], GPS[0]` (lanes with `pos: "ned"`, `attitude: "angles"`, own roll/pitch/yaw,
`vn/ve/vd`); the existing copter / PX4 / CSV-with-ArduPilot-names tests pass unchanged.

### L3 – The origin: found, used, explained — M

A local (NED / ENU) candidate needs an origin. Add `origin?: { ids: [string, string, string]; via: string;
rule: "own" | "known" | "sibling" }` to `Candidate`, found in this order:
1. **own** – lat / lon / alt reference fields inside the object's own prefix: `ref_lat / ref_lon / ref_alt`,
   `origin.lat…`, `ref.lat…`, `home.lat…`, `datum.lat…` (PX4's `vehicle_local_position.ref_*` is this rule).
2. **known** – the known group's `origin` list (XKF1 / NKF1 → `ORGN` with the EKF-origin instance, then
   `ORGN` without instance; LOCAL_POSITION_NED → `GPS_GLOBAL_ORIGIN`, then `HOME_POSITION`).
3. **sibling** – a group named `origin`, `ref`, `home` or `datum` (optionally with a class word:
   `nav.origin`, `nav_ref`) beside or above the object's prefix that has lat, lon **and** alt.

Then:
- **Origin groups are not objects** (F7): a prefix used as an origin, or whose last segment is
  `origin / ref / home / datum` / a known origin group (`ORGN`, `HOME_POSITION`, `GPS_GLOBAL_ORIGIN`,
  `home_position`), is never a candidate and never "incomplete". `vehicle_local_position.ref_lat` must not
  produce `vehicle_local_position.ref`.
- `addable(c)` = `lla` or `ecef` or (`ned` / `enu` **with an origin**) and the unit check from L1.
- `candidateObject`: for a local position with an origin, `createFrameGroup([px, py, pz, oLat, oLon, oAlt],
  { qty: "position", src: c.pos, dst: "lla", ref: "signals" }, …)`. Without an origin it is not called
  (the row says "needs an origin", see L5).
- `whyLines`: one line for the origin – "origin: ORGN[0] (Lat / Lng / Alt), the EKF origin; heights are
  above sea level like POS" / "origin: its own ref_lat / ref_lon / ref_alt; PX4 may move it during the
  log – the first value is used" / "no origin found – choose one" – en **and** he.

**Done when:** on both fixtures every local candidate with an origin is addable, *Add all* puts it on the
map, and lane 0 converted lies on `POS` within 0.05 m (a test that reads the derived signals' values –
backend or e2e); `ORGN[0]` and `*.ref` are no longer candidates; *Why?* explains the origin.

### L4 – "Already on the map" for every kind of object — S

Fix F8 with one rule used everywhere:
- Move the chain walk of `ObjectDialog.readSetup` (`vecsmooth` → `frame` → sources) into a shared helper
  (e.g. `objectSources(o, derivedSignals)` in `objectAdd.ts` or `mapObjects.ts`) and use it from
  `readSetup` too, so there is one implementation.
- A candidate's identity is its first position source: `picks.lat.id` for LLA, `picks.px.id` for
  NED / ENU / ECEF. An object is "the same" when its first source after the chain walk is that id.
- `isAdded` and `ObjectSuggestBar` (`onMaps`) both use it; delete the lat-only checks.

**Done when:** after *Add all* on `local_frames.csv` and `ardupilot_lanes.csv` the suggestion bar
disappears and the dialog shows every row as added; a second *Add all* is impossible; reopening a saved
session keeps that state (Vitest for the helper, e2e for the bar).

### L5 – The found list and the form for local positions — S

In `ObjectDialog.tsx` (found list and form) – no new places for controls (CLAUDE.md §3):
- Each row shows its frame and origin: "NED · origin ORGN[0]", "ECEF", "NED · needs an origin".
- A local row **without** origin: the existing "needs an origin – Advanced…" opens the form preset with
  the frame already chosen and the origin **suggested**: if the same file has an LLA candidate (e.g.
  `GPS[0]`), preselect `refMode: "signals"` with its lat / lon / alt (its first valid sample becomes the
  origin – say so next to the field), otherwise `manual`. Today the preset always starts `manual` and
  empty.
- A local row **with** origin opened in *Advanced…*: the form shows `refMode: "signals"` with the found
  origin filled in (editable).
- Every new string through `frontend/src/i18n/mapsAnd3d.ts`, `en` and `he`; check RTL; CSS variables only.

**Done when:** e2e: open `local_frames.csv` with `origin.*` removed → the NED row says it needs an origin
→ *Advanced…* shows `signals` with the file's LLA object preselected → Save → the object is on the map.

### L6 – Everything downstream still works — S

Objects made from local positions are LLA objects behind derived signals; verify, and fix only what fails:
- N7: primary / secondary with a lane as secondary, the relation box at the cursor, *Make plots* in NED /
  ECEF (`relation.ts`, `svcore/relate.py`): lane 1 − lane 0 shows the +1.5 m north offset of the fixture.
- The "Position on the map & 3D" template, the 3D view, playback, *Export for Tacview (.acmi)*.
- Session save → reopen, autosave, and an **old** session (from 1.24.0) still opens (no saved field
  renamed or repurposed; any new field optional with a default).
- Live mode, if an ArduPilot live connection produces XKF1 (`mavlink.ts`) – note the result, do not
  extend live mode in this round.

**Done when:** each item checked and written in the Log; whole e2e suite green (state which ran).

### L7 – Primary and secondary: explained on the map, chosen in one clear place — S

**Today** (`GeoChart.tsx`, the end of the draw: `pairOf(plot)`; `Globe3D.tsx` `rings`): the primary has a
solid amber ring, the secondary a dashed amber ring, a dashed line with the distance joins them
(`plot.relLines`). The pair decides the relation box, the comparisons' reference, the error signals and
which object the map follows by default. **Nothing on screen says so.** Changing it: the chip's
right-click (*Set as primary / secondary*) and Q / Shift+Q / X with the map focused; the 3D view has a
*Primary* select among its camera controls; the 2D map has none – two views, two different ways.

The spec:
- **Explained where it is seen:**
  - Hovering a ring (or the object under it) shows a tooltip: "Primary – the reference: the relation box,
    comparisons and errors are measured from it" / "Secondary – compared with the primary in the relation
    box". Use the hit-test that already picks an object on click (`objAt`).
  - The relation box's header shows a small key drawn like the map: a solid ring + *Reference (primary)*,
    a dashed ring + *Compared (secondary)* – the header is the box's first line, so the key is visible
    even when the box is folded.
  - The object chips (legend) mark the two: a small solid / dashed ring icon before the name, with the
    same tooltip. The ring colour is the theme's amber token for both views; keep solid vs dashed as the
    difference and add the icon so it does not rely on dash alone (colour-blind / small screens).
  - Help (`Help.tsx` keys list) and the guides: one short paragraph "The rings".
- **One clear place to choose** (CLAUDE.md §3): the **relation box header** becomes the place – two
  selects, *Reference* and *Compared with*, and a ⇄ swap button – shown whenever the plot has ≥ 2 objects,
  folded or not. The same component in the 2D map and the 3D view: the 3D view's own *Primary* select moves
  into it (the camera buttons stay where they are and keep following the primary). The chip's context menu
  entries and Q / Shift+Q / X stay as the allowed second entries (shortcuts); add "Set reference object…"
  to the command palette.
- Everything through `actions.setObjectPair` (one commit, Undo), the saved fields stay
  `Plot.primaryObject` / `relatedObjects` – no new saved field.
- The L8 Compare dialog's *Reference* is the same value (choosing it there changes the rings, and the
  other way round).
- en + he, RTL (the ⇄ and the "→" in the header must read correctly in Hebrew), both themes.

**Done when:** e2e (extend `test_object_relations.py`): hovering the primary's ring shows the tooltip;
the header shows the key; choosing another reference in the header moves the solid ring, the distance
line and the relation values, and Undo restores them; the same in the 3D view; Q / X still work.

### L8 – Compare objects: one place, positions, velocities and angles, values and errors — L

**The user's need:** "I have truth, two EKF lanes and a GPS on the map – show me how each one differs from
the one I choose, in position, velocity and attitude, both the curves themselves and the errors, and let
me find this without hunting."

**One dialog, `Compare objects…`** (new `components/CompareObjectsDialog.tsx`; the logic in `relation.ts`
– extend it, do not start a second module):
- **Reference** (one object; default `pairOf(plot).primary`, i.e. truth first) and **objects to compare**
  (checkboxes, default all others). Choosing the reference here also sets the plot's primary (the existing
  `actions.setObjectPair`), so the relation box agrees.
- **Quantities** (checkboxes): *Position* (default on), *Velocity* (on when the objects have `vel`),
  *Attitude* roll / pitch / yaw (on when they have angles of their own). Disabled with a reason
  ("XKF1[1] has no velocity") when not available; an object whose attitude is borrowed from the reference
  or drawn from motion is left out of attitude errors with that reason (as `errorSignals` does today).
- **Show:** *Values* · *Errors vs the reference* · *Both* (default *Both*).
- **Frame** for position and velocity: NED (default) / ENU / ECEF / LLA / along-across track – the
  existing `CompareFrame`, with its hints.
- **Statistics** (on by default): a table per object and component – RMS, mean, max |error|, 95th
  percentile, time of the max – computed in the backend on full-resolution data (reuse
  `compute_signal_stats`; add percentile there if missing). Shown in the dialog after *Make*, copyable,
  *Save CSV*.

**What *Make* produces** (one commit, one Undo, one toast with Undo):
- One **tab per quantity**: "Position (NED) vs truth", "Velocity (NED) vs truth", "Attitude vs truth".
  Layout per tab: one row per component (N / E / D, or roll / pitch / yaw); with *Both*, the left column is
  the values of all objects (reference included, drawn first and thicker), the right column the errors of
  each object vs the reference; plus one row for horiz / vert / 3D error (position) or speed error
  (velocity). 3 components × 2 columns = 6 plots – within limits.
- Values: position in the frame from one shared origin (as `overlayObjects`); velocity in the frame
  (NED from `vel`, rotated for ENU / ECEF); attitude as recorded, yaw shown wrapped consistently (no 0/360
  jumps between objects – use the reference's wrap).
- Errors: `relate` (`diff`, `vdiff`, `err_horiz / vert / 3d`, `err_roll / err_pitch / err_hdg`). Add to
  `relate` only what is missing (e.g. a yaw error that uses yaw, not the heading, when both have yaw –
  check what `err_hdg` does today and say it in the notes), with the definitions in its docstring.
- Fix `plotsInNewTab`'s silent truncation: when a request exceeds the limit, split into more tabs or say
  in the toast what was left out – never drop silently. Make the change in `plotsInNewTab` itself so every
  caller benefits.
- Re-running with the same choices reuses the existing derived signals (`findDerived`), no duplicates.

**Where the user finds it** (CLAUDE.md: one place + command palette / shortcut):
- The relation box's four buttons become **one `Compare…` button** that opens the dialog; *Plot the
  relation*, *Error signals*, *Differences* and *Overlay* become **presets** at the top of the dialog
  (one click each, same result as today) – nothing the user had is lost (Q7).
- The suggestion bar's offer after adding objects opens the same dialog, prefilled.
- A map / 3D plot with ≥ 2 objects but the relation box folded or hidden: the plot's ⋯ menu has no second
  copy – the box is the place; make the folded box still show its `Compare…` button.
- Command palette: "Compare objects…" (acts on the active tab's map / 3D plot; if there are several, on
  the active one; if none, says how to add objects). Pick a shortcut only if it does not clash
  (`shortcuts.ts`) – Q7.
- en + he strings, RTL, CSS variables.

**Done when:** on `ardupilot_lanes.csv` with truth = POS (or a truth object from the fixture), one *Make*
with Position + Velocity + Attitude and *Both* gives three tabs with the layout above; lane 1's north error
is +1.5 m, lane 0's ≈ 0; the statistics table matches a numpy computation in a pytest; the old four actions
give the same signals as on `d61ab6d` (e2e `test_object_relations.py` still passes, adapted only for the
button now living in the dialog).

### L9 – Compare similar signals (nested names) — M

**The user's need:** "`nav1.att.roll`, `nav2.att.roll`, `truth.att.roll` – compare them" without dragging
each one and building differences by hand.

**Finding the families** (pure function, new `frontend/src/similar.ts`, Vitest; no data read, names only,
fast on 5000 names like `objectDetect`):
- Two signals of the **same file** are in one family when their names are equal except in **one segment**
  of the path (`pathCuts` / `nameTree` from `signalGroups.ts` – the list's own tree), and that segment
  differs by an instance (`GPS[0]` / `GPS[1]`), a number (`nav1` / `nav2`, `ekf_2`), or is a whole-word
  owner/class word (`truth` / `nav` / `gps`, `CLASS_WORDS` from `objectDetect.ts`). Units in brackets are
  ignored for matching but must agree for a difference (else a reason is shown).
- *More (looser) matches* (off by default, Q12): the differing segment within edit distance 1–2, or the
  leaves equal under different parents (`a.b.roll` / `c.roll`). Shown with why they matched.
- A family has a **leaf** (what is compared: `att.roll`) and **members** (`nav1`, `nav2`, `truth`).
- Group level: choosing a group (`nav1.att`) gives every leaf under it that has partners
  (`roll`, `pitch`, `yaw`) – one family per leaf.

**The UI:**
- Entry point: the signal list's group menu and a signal's context menu get *Compare with similar…*;
  plus the command palette "Compare similar signals…". (Exactly these places – CLAUDE.md §3.)
- Dialog `CompareSimilarDialog.tsx`: the list of families (leaf, members, how they matched) with
  checkboxes; a **reference** member (default: a truth-class member, else the first); *Values* /
  *Errors* / *Both*; optional statistics as in L8.
- *Make*: one tab, one row per leaf: values of all members on the left, member − reference on the right
  (same layout and the same `plotsInNewTab` as L8).
- **Angle-aware differences:** add an optional `wrap` parameter to the backend `sub` op (`360` or
  `"2pi"`; absent = today's behaviour, so old sessions are unchanged) that wraps the result to
  ±half-period. Use it when the signal's unit is deg / rad **and** the leaf is an angle role (roll / pitch /
  yaw / heading / phi / theta / psi, the `ALIASES` of `objectDetect.ts`). Also offer it in `errors.ts`
  (errors between two lines) for the same case – one rule, one helper.
- Across files (the same name in two files) stays ComparePanel's job – do not duplicate it; if the user
  picks *Compare with similar…* on a name that exists in other open files, the dialog points to Compare.

**Done when:** on `examples/three_objects.csv` and `ardupilot_lanes.csv` the families are found
(`*.att.roll` across phys / nav; `XKF1[0].Roll` / `XKF1[1].Roll`); the yaw difference across 0/360 is
small, not ≈ 360; e2e `test_compare_similar.py` makes the tab from the group menu.

### L10 – Move a plot to another tab, or into another plot — M

Extend N2 – same actions file, same menu, same drag handle (do not add a parallel mechanism):
- **Actions** in `store/actions/layout.ts`, each one `commit` (one Undo):
  - `movePlotToTab(plotId, tabId | "new", cell?)` – the plot (same id, so its axes, cursors, objects,
    primary / secondary and map state stay with it) leaves its tab and goes to the target tab: into the
    given empty cell, else the first empty cell, else the grid grows by a row or column while
    `≤ MAX_PLOTS`; if the target is full, refuse with a toast that says why. The source cell becomes empty
    (the grid does not reflow); the active tab and plot follow the moved plot. `"new"` makes a tab named
    after the plot.
  - `mergePlotInto(plotId, targetPlotId, keepSource = false)` – the plot's lines join the target plot
    (same mode only: time into time, objects of a map into a map / 3D, XY into XY; otherwise refuse with the
    reason); duplicates are not added twice; line styles and axes (left / right) kept; then the source
    plot is removed (or kept, for *Copy into*).
  - Copy variants (`copyPlotToTab`) only if Q8 says so; default: move only, Ctrl while dropping = copy.
- **UI:** the ⋯ menu's *Move to…* gets a target picker: *This tab* (today's mini grid) · each other tab
  (its mini grid) · *New tab*; and *Add its lines to…* (a list of the compatible plots, by tab). Dragging
  the ⋯ handle onto a tab in `TabBand` moves the plot there; onto another plot's body with a modifier
  (Shift) merges into it – highlight the target and show the action in a hint while dragging.
  Keep the existing drag MIME type; keep a click selecting the plot.
- Command palette: "Move plot to new tab", "Move plot to tab…".
- Linked X axes are per tab: a moved plot joins the target tab's link setting – say so in the notes.

**Done when:** Vitest for each action and its Undo (including a map plot keeping its objects and pair,
a full target tab refused, merge of incompatible modes refused); e2e `test_move_plots_tabs.py` (drag onto
a tab, *Move to → New tab*, *Add its lines to…*); `test_move_plots.py` still green.

### L11 – Export the map: PNG, standalone HTML, and maps in reports — M

- **One renderer in the backend** (`backend/app/mapimage.py` or inside `report.py` – choose and say why):
  given a map plot's state (bounds or the current view, objects, their `object_track`s, track colouring,
  the cursor time, base layer) it draws: the offline basemap tiles (`app/basemap.py`), each object's track
  in its colour (and its track look / colour-by-value as on screen where practical), the object's marker
  and name at the cursor, a legend, a scale bar, north arrow, and the attribution line. Output PNG or SVG.
  Online imagery (satellite / online map) is used only if the user has it on and its tiles are already in
  the app's tile cache; the attribution is then always written on the image (Q9).
- **The map's ⋯ menu:** *Save image (PNG)…* (the current view, or *Fit all tracks*) and *Save as HTML…*.
  Reuse `/api/export/image` (add the `geo` case) rather than a new endpoint where it fits.
- **Standalone HTML map** (offline, no CDN, like today's HTML report – `report_assets`): the tiles for the
  tracks' bounding box at a few zoom levels embedded as images (a size budget, e.g. ≤ 15 MB, the zoom
  levels chosen to fit it – say in the file what was embedded), the decimated tracks, pan / zoom, a time
  slider that moves the markers, hover for name / time / lat / lon / alt, light / dark. The 3D view keeps its
  PNG; HTML 3D is out of scope.
- **Reports:** a `geo` plot is drawn in reports (PDF / Word / PNG: the static image; HTML report: the
  interactive map above). Today a report skips it – check what it does now and record it.
- Templates and the CLI's `report` command get maps for free through the same report code.

**Done when:** pytest renders a PNG of the fixture's tracks with the offline basemap (size, non-blank,
tracks' pixels where expected); the HTML file opens with no network (e2e: open it with the network
blocked, move the slider, the markers move); a report of a tab with a map contains the map in HTML and PDF.

### L12 – A clear API for the whole process — L

**Goal:** everything L0–L11 does from the UI can be done from a script, a shell / CI, or another program,
with the same rules and the same numbers.

**First, one source of truth for detection** (Q10). Object detection (L1–L3) must be available in Python.
Default: move the **tables** (aliases, frame words, class words, known groups, origin groups) to one JSON
file, e.g. `backend/svcore/object_names.json`, read by both `objectDetect.ts` (imported at build time) and a
new `backend/svcore/objects.py` (the same algorithm); and one shared **test-vector file**
(`tests/data/object_detect_cases.json`: names in → candidates out) run by **both** Vitest and pytest, so the
two implementations cannot drift. The comparison maths stays in `svcore/relate.py` / `analysis.py`
(already backend); add `backend/svcore/objcompare.py` that orchestrates a comparison on arrays (no UI
derived signals) and returns values, errors and statistics – and have the dialog's statistics (L8) call it
through the endpoint below, so UI and API compute statistics in one place.

**Python** (`backend/signalviewer/__init__.py`, documented in its docstring and `docs/command-line.md`):
```python
import signalviewer as sv
rec = sv.load("flight.bin")
rec.objects()                                # found objects: name, class, frame, origin, why (list of dicts / dataclasses)
nav = rec.object("XKF1[0]")                  # t, lat, lon, alt (converted from NED via the origin), roll, pitch, yaw, vel
cmp = sv.compare_objects(rec, reference="POS", objects=["XKF1[0]", "XKF1[1]"],
                         what=("position", "velocity", "attitude"), frame="ned")
cmp.values()      # DataFrame: time + each object's components
cmp.errors()      # DataFrame: time + each object's errors vs the reference
cmp.stats()       # DataFrame: object × component → rms, mean, max_abs, p95, t_max
cmp.to_csv("errors.csv"); cmp.to_mat("errors.mat")
sv.similar(rec)                              # families of similar signals (L9)
sv.compare_signals(rec, ["nav1.att.roll", "nav2.att.roll"], reference="truth.att.roll")
sv.map_image(rec, objects=[...], path="map.png")      # L11
sv.map_html(rec, objects=[...], path="map.html")
sv.report(rec, compare=cmp, map=True, path="report.html")   # also .pdf / .docx, as the existing reports
```
Several files: `objects=` may name objects of other loaded recordings (`sv.compare_objects([rec_truth,
rec_flight], …)`), with the time alignment rules the app uses (state which).

**Command line** (`signalviewer/cli.py`, `--json` on every command, exit codes documented):
```bash
signalviewer-cli objects flight.bin [--json]                      # what was found, and why
signalviewer-cli compare-objects flight.bin --ref POS --objects "XKF1[0],XKF1[1]" \
    --what position,velocity,attitude --frame ned \
    --csv errors.csv --stats stats.csv --map map.png --map-html map.html --report report.html
signalviewer-cli compare-similar flight.bin [--leaf att.roll] [--ref truth] [--csv …] [--json]
signalviewer-cli map flight.bin --objects all --out map.png|map.html
```
Optional pass / fail: `--tolerance position=2m,attitude=1deg` with a non-zero exit code and JUnit XML,
reusing `svcore/tolerances.py` and the `check` / `compare` conventions (Q11).

**REST** (local, 127.0.0.1 only, as today; one router file `app/routes/objects.py`):
`POST /api/objects/detect` (runs → candidates with *why*), `POST /api/objects/compare` (the same request
as the Python call → values / errors decimated for display, statistics full-resolution, or a CSV),
`POST /api/objects/similar`, the map export from L11, the report with maps. Pydantic models with field
descriptions so `/api/docs` is the reference; one example request per endpoint in a new
`docs/api.md` (linked from `mkdocs.yml`) that walks the whole process end to end with `curl`.

**Done when:** a pytest runs the whole process on `ardupilot_lanes.csv` through Python, through the CLI
(subprocess) and through the REST client, and the three give the same statistics as the UI's dialog
(tolerance 1e-9); the shared test vectors pass in Vitest and pytest; `docs/api.md` and
`docs/command-line.md` describe every command with a working example; mypy clean.

### L13 – Docs, changelog, release notes, full checks — S

- `CHANGELOG.md` (user wording): "Objects whose position is in NED, ENU or ECEF metres are found and
  added like latitude / longitude ones – every ArduPilot EKF lane (XKF1 / NKF1) on the map with its own
  attitude, placed through the EKF origin (ORGN); PX4 / MAVLink local positions; an ECEF object is no
  longer offered again after it was added."
- The naming convention in the guides (English and Hebrew, the same place N5 documented it): add
  `<object>.ned.x / y / z`, `<object>.pos.north / east / down`, `<object>.ecef.x / y / z`, and
  `<object>.origin.lat / lon / alt` (or `ref_*`). Consider adding one NED object to `NAMING_EXAMPLE`
  in `objectAdd.ts` only if it stays short.
- `ROADMAP.md` Milestone 28 ticked with done-notes; `TASKS.md` current state, board, Log.
- Also for L7–L12: the guides' paragraph "The rings" (en + he); CHANGELOG lines (the rings explained and
  chosen in the relation box, Compare objects…, Compare with similar…, moving plots to other tabs /
  into plots, map PNG / HTML and maps in reports, the API and CLI commands); `docs/maps-and-3d.md` and the
  guides (en + he) for the new dialogs; `docs/api.md` and `docs/command-line.md`; `docs/features.md`.
- Full checks from CLAUDE.md, the whole e2e suite, `mkdocs build --strict`; the patch (Status box).

---

## 4. Invariants most at risk in this round (from CLAUDE.md)

- **One way to do a thing:** one frame table, one velocity table, one chain walk, one "already added"
  rule. `frames.ts` and `objectDetect.ts` must not drift apart again – import, do not copy.
- Detection works from **names only** and stays fast and cached; it never reads data.
- Signals by stable id `"<runId>/<name>"`; every workspace change through `commit` (one Undo for *Add
  all*, as today).
- Sessions / templates / autosave backward compatible; new `Candidate` fields are frontend-only and need
  no migration; new `MapObject` fields (if any) optional with defaults.
- Heavy work in the backend: the conversion is the existing `frame` op; the UI only receives decimated data.
- English + Hebrew for every string, RTL checked, CSS variables, no new dependencies.
- Nothing is added without a click; *Why?* explains every guess, including the origin.
- One place per control (CLAUDE.md §3): the compare dialogs open from the places named in L8 / L9 and the
  command palette only; moving plots extends N2's menu and handle.
- Detection rules live in one table file shared by TypeScript and Python (L12); the comparison maths
  lives in the backend (`relate.py`, `analysis.py`, `objcompare.py`) – the UI and the API never compute
  the same statistic two ways.
- New optional op parameters (`sub` `wrap`) default to today's behaviour; old sessions give the same
  signals.

---

## 5. Open questions for the owner (work with the default until answered; record the answer in TASKS.md)

- **Q1 – Lanes in *Add all*.** A copter log then offers POS, XKF1[0], XKF1[1], AHR2, GPS[0], GPS[1].
  *Default:* all are offered and checked (as N5 decided: every navigation solution); POS first.
  Alternative: lanes listed but unchecked when POS exists.
- **Q2 – Origin / home as a map marker.** *Default:* origin groups are never objects (L3). A static "home"
  marker could be a later task.
- **Q3 – x / y / z with no frame (ROS `pose.position.x`).** *Default:* stays a near miss with a better
  *Why?*; no guess (ROS's ENU convention is not guaranteed by the topic name).
- **Q4 – No ORGN in an ArduPilot log.** *Default:* the lane needs an origin (L5 suggests `GPS[0]`'s first
  fix). Alternative for later: derive the origin from POS − lane NED at a common time.
- **Q5 – PX4 origin resets during a flight.** *Default:* first value used, said in *Why?*. Supporting a
  time-varying origin in the `frame` op is a separate backend task.
- **Q6 – Positions in cm / mm (e.g. u-blox ECEF in cm).** *Default:* found but not addable by *Add all*,
  with a *Why?* line pointing to ƒ. Alternative: scale automatically from the unit.

- **Q7 – The relation box's buttons.** *Default:* the four buttons become one `Compare…` that opens the
  dialog, with the four as presets inside. Shortcut for *Compare objects…*: none unless a free one is
  agreed (propose one in the Log after checking `shortcuts.ts`).
- **Q8 – Move or copy.** *Default:* the menu moves; Ctrl while dropping copies; *Add its lines to…*
  moves (the source plot is removed) with *Copy into* beside it.
- **Q9 – Map export imagery.** *Default:* the offline basemap; online imagery only if on and already
  cached, with its attribution on the image / in the HTML; HTML size budget 15 MB.
- **Q10 – One source for detection.** *Default:* shared JSON tables + the same algorithm in TS and Python
  + shared test vectors. Alternative: detection only in the backend, the UI asks once per opened file
  (bigger change to the suggestion bar's instant response).
- **Q11 – Pass / fail in `compare-objects`.** *Default:* yes, optional `--tolerance`, the CLI's existing
  JUnit conventions.
- **Q12 – Loose matches in *Compare with similar…*.** *Default:* off, behind *More matches*.
- **Q13 – The 3D view's *Primary* select.** *Default:* it moves into the shared relation-box header (L7),
  so 2D and 3D choose the pair the same way.

---

## 6. Ideas for the next round – NOT part of this round

Do not implement these. They are here so the owner can choose the next round, and so the code written now
does not close the door on them. If something in L0–L13 makes one of them easier or harder, write one
line about it in the Log. Each has a size guess and why it matters to navigation / flight-test engineers.

**Correctness of comparisons (recommended first)**
- **I1 – Altitude datum per object — M.** Objects mix heights above sea level (ArduPilot POS / GPS Alt,
  ORGN) and above the ellipsoid (anything converted from ECEF, most GNSS receivers' "height"). The
  difference is the geoid height – about +18 to +20 m in Israel – and shows up as a constant vertical
  "error" in every comparison. Give each object an altitude reference (AMSL / ellipsoid / AGL, guessed
  from the name and the format, shown in *Why?*), convert with an offline geoid grid (EGM96 / EGM2008 at
  coarse resolution, a few MB) before comparing, and warn when a comparison mixes references.
- **I2 – Time lag between objects — S/M.** A navigation solution or a receiver lags the truth (GPS
  typically 100–200 ms). Estimate the lag per object from the velocity (cross-correlation), show it in
  the comparison's statistics, and offer *Compare with the lag removed*. Without it the along-track error
  is dominated by lag.
- **I3 – Antenna lever arm — S.** A receiver measures its antenna, not the vehicle's reference point.
  Offer an offset in body axes per object (ArduPilot: `GPS_POS1_X/Y/Z` from the log's parameters) applied
  with the object's attitude before comparing.

**Understanding the errors**
- **I4 – Uncertainty, not only error — M.** The EKFs log their own variances (ArduPilot `XKF4` SP / SH /
  SV, PX4 `eph` / `epv`). Plot the error with its ±3σ band, report the share of time outside it (a
  filter-consistency check), and draw the uncertainty ellipse around the object on the map.
- **I5 – Accuracy figures engineers quote — S.** CEP50 / CEP95, 2DRMS, horizontal / vertical 95 %, and a
  north-vs-east error scatter with the CEP circles – in the statistics table, the report and the API.
- **I6 – Errors by flight phase — S.** The statistics split by flight mode or by a condition the user
  already defines (`conditions.ts`): "lane 1 is fine in Loiter, 4 m off in Auto".
- **I7 – Error on the track — S.** Colour a compared object's track by its error against the reference
  (the track colouring by a value exists – feed it `err_3d`), so the map shows *where* it went wrong; and
  *Go to worst*: one click from the statistics table to the moment, on the map and every plot.

**Events on the map**
- **I8 – Navigation events — S.** EKF lane switches, GPS glitches / fix loss, EKF resets and failsafes
  (ArduPilot ERR / EV / XKF flags) as marks on the track and on the timeline, with the lane that became
  primary.
- **I9 – Mission and home — M.** The mission's waypoints, the geofence and home (ArduPilot CMD / FNCE,
  MAVLink mission items) drawn on the map; altitude above terrain (AGL) from the offline elevation data
  the basemap already has.

**Working faster**
- **I10 – Saved comparisons — S.** A comparison set-up (reference, objects by name, quantities, frame,
  tolerances) saved in a template, re-applied to the next log automatically – and run by the CLI over a
  folder of logs (one row per log in a summary table).
- **I11 – Sim vs flight across files — M.** Compare an object of one file with an object of another
  (a simulation's truth vs a flight's EKF) with the app's time-sync rules – the API in L12 should already
  allow two recordings; this is the UI side.
- **I12 – Map tools — S.** A measuring tool (distance / bearing between two clicks), and two maps or a
  map + 3D synchronised side by side (follow different objects at the same time).

---

## 7. When you stop

Update the Status box at the top (stage reached, code map of what you built – file / function names, what
is left), the board and Log in `TASKS.md`, and make the patch as described. If you stop in the middle of a
task, say exactly where (file, function, what is half-done) so the next agent can continue cold.
