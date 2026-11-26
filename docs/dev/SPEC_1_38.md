# 1.38.0 spec - calm, clear, any data (Phase 1 of the plan in TASKS.md "Open specs")

Made 2026-11-26 from the app itself (1.37.0 + the judge's two fixes): 19 screens, dark / light, English / Hebrew,
taken by `/home/claude/audit/audit.py` (Playwright on make_readme_media's App) with a count of what is on screen.
Each item: what is there now -> what it becomes, and why. IDs are the ROADMAP "CC" task IDs.

## The numbers now (dark, English, 1600 x 900)

| Screen | Controls | TopBar | Prose blocks / words | Boxed elements |
|---|---|---|---|---|
| Welcome | 42 | 17 | 7 / 100 | 31 |
| 4 plots + Inspector | 97 | 18 | 3 / 62 | 69 |
| Create | 72 | 18 | 5 / 71 | 45 |
| Compare | 80 | 18 | 4 / 53 | 53 |
| Investigate | 59 | 18 | 4 / 78 | 41 |
| Report | 66 | 18 | 4 / 37 | 46 |
| Checks (flight log) | 113 | 18 | 8 / 102 | 61 |
| Checks (bench, not a log) | 65 | 18 | 9 / 126 | 47 |
| Sweeps - Goal / Results / Next runs | 56 / 62 / 35 | 8 | 5-10 / 78-142 | 27-54 |
| Settings | 64 | 17 | 14 / 223 | 44 |

**Targets for 1.38.0** (measured again in Phase 3 with the same script): TopBar <= 10; always-on prose <= 40 words
per working screen (Settings and Help excepted); no action in two places (beyond the palette / a shortcut);
boxed elements down by a third.

## A - calm and clear

- **CC1 TopBar 18 -> 10.** Now: Start page, Recordings, Sweeps, Commands, Open ▾, Save session (icon), Export
  recording (icon), Templates ▾, Live, Live settings ▾, Undo, Redo, Clear ▾, Inspector, Settings, Theme, Language,
  Help. After: [logo = start page] [Recordings | Sweeps] [Commands and signals] [File ▾: Open files…, Open session…,
  Recent ▸, Save session, Export recording…, Clear ▸] [Templates ▾] [Live ▾] … [Undo] [Redo] [⚙ Settings] [Help].
  Theme and language: in Settings (first section) + the palette + their shortcuts - choices made once
  (CLAUDE.md: "Settings dialog: choices made once"). The Inspector toggle moves to the StageBar's right end (it is
  about the plots). The same TopBar in Sweeps: *File ▾* opens / clears the study there.
- **CC2 One way through Sweeps.** Now three layers: a toolbar row (undo, redo, Open ▾, Study ▾, Clear ▾, reload,
  Follow the file), the 5 step cards, the side panel's "← back / next →" - and a second "See the results →" in
  the Goal page. After: the toolbar row goes (Open / Study / Clear -> TopBar *File ▾*; undo / redo -> TopBar's;
  reload and *Follow the file* -> the Data step); the step cards are the way; one "next →" (the side panel's).
- **CC3 Words on screen.** The always-on hint line above the plots ("Click: pick · Ctrl or Shift+click…") -> a "?"
  beside the band with the same text as its tooltip, and Help. Every long empty state -> one line + "how?"
  (tooltip / Help): the Inspector's Notes and Signal, Investigate's Conditions, Create's Derived signals, Checks'
  Limits, the Report's My parts, Sweeps' groups / Shown now / goal hints, Settings' descriptions (under each
  choice's "?"). Words kept where the user acts on them (a verdict, an error).
- **CC4 The plot's own actions in one place.** The floating bar over a selected plot (Note / Find similar /
  ? What changed?) -> the plot's ⋯ menu and its right-click menu (the same list); the keys (N, What changed? from
  the palette) stay.
- **CC5 The Inspector when it has something to show.** Closed by default; opens when a signal is selected or the
  cursors are placed (remembered when the user closes it); empty sections are one line. The cursor values: on the
  axes and in the Inspector - the status bar's "T1 18 T2 34 ΔT 16" goes (a third copy). C2 (panel widths, the
  Inspector on the first cursors) is answered here.
- **CC6 Create: what to make, then its fields.** Now a 6-way switch (One signal / Two / Several / Formula / Frames /
  Python) + a 2-way + a 2-way + paragraphs. After: one "What to make" list with a one-line description per item;
  the fields of the chosen one; explanations as tooltips.
- **CC7 Checks: the verdict first, in two parts.** Now up to six sub-tabs (Checks, Events, Parameters, The file,
  Instruments, Hardware). After: *Verdict* (the line "2 failed · 6 to look at · 2 fine", then the requirements
  file, limits, the profile's findings, the automatic flags, data quality - in that order) and *File* (the file,
  and for a log: events, parameters, instruments, hardware as sections). Findings in plain words: "MotorTemp above
  85 °C - 30 samples, first at 545.98 s" instead of "outside −∞ … 85 – 30×, first at 545.98".
- **CC8 The Report's head.** Now Write / Both / Preview + three selects + five export buttons + reload. After:
  Write / Both / Preview, one *Export ▾* (HTML, PDF, Word, PDF via LaTeX, LaTeX .zip), the report's options
  (language, written in, theme) under its ⚙.
- **CC9 Welcome.** One *Open files* (the centre; the empty Files panel says one line); examples grouped by task,
  generic first (see B1).
- **CC10 Visual weight.** One spacing scale and radius, fewer outlines (cards only where something is a unit),
  one primary button per screen, muted secondary text (index.css variables), the phase band once at the top and
  muted on the timeline; targets at least 24 px for ×, close tab, drag handle (RW8's leftover). Light and dark.

## B - any data, not ArduPilot

What the audit found: 22 of the 25 built-in templates are ArduPilot / MAVLink / PX4 (`bi-ap-*`, `bi-mav-*`,
`bi-px4-*`, `bi-pair-*`); the welcome's featured examples start with the ArduPilot log and 4 of 6 are flights;
examples/ is mostly UAV (copter_flight.bin, uav_flight*.csv, folder_of_flights, drones, sweeps/drone_tuning);
the automatic health check (svcore/health.py) is ArduPilot rules only - for any other file only the four generic
flags (svcore/overview.py: stuck, saturated, gap, spike) and data quality; checks.json knows only lo / hi (+ during
a state). Strong already, kept: MAT (v4-v7.3, struct-with-time multi-rate), HDF5 groups with their own time,
Parquet, CSV; Compare with Simulink-Data-Inspector tolerances; the Monte-Carlo envelope (svcore/envelope.py); the
CLI (check, compare, report, summarize, sweep - exit codes, JUnit); the Python API (signalviewer.Recording).

- **CC11 Requirements, not only limits.** checks.json (backward compatible: a check without `kind` is a range)
  gains: `range` (lo / hi, `during`, `from` / `to` time), `settle` (signal reaches its target / a reference within
  a band by a time), `overshoot` (max %), `rise` (10-90 % within a time), `sserror` (steady-state error), `rate`
  (|dy/dt| at most), `track` (signal within abs / pct of a reference signal), `order` (event A before B). One
  evaluator (svcore/requirements.py) used by Checks, `signalviewer-cli check`, the report and the runs table.
- **CC12 Automatic research for any file (profiles).** The ArduPilot rules become the *ArduPilot* profile (chosen
  for .bin / .tlog / .ulg, as now); a *generic* profile runs on every file: the four flags + oscillation (a limit
  cycle), drift, NaN / Inf, and - when a command / measured pair is recognised (svcore pairing: ref/cmd/setpoint/des
  vs meas/act) - tracking error and the step metrics (rise, overshoot, settle). A profile is a JSON file a user can
  write (Settings -> Profiles folder).
- **CC13 Many runs.** A folder of simulation runs (Monte-Carlo / a grid) -> the runs table (today's "folder of
  recordings", named generically) with a requirement-verdict column per requirement and the envelope one click away.
- **CC14 Simulink names and objects.** A struct-with-time's signal named by its `label` / `blockName`
  ("ctrl.signals.values" -> "u"); `Simulink.SimulationData.Dataset` / `timeseries` objects (MATLAB's opaque class
  data, unreadable outside MATLAB): a clear message on load + `tools/matlab/sv_export.m` that writes them as a
  plain struct .mat; docs/limitations.md says so.
- **CC15 Templates and the report.** Generic templates first: Step response and tracking, Actuator effort and
  saturation, Simulation against test, Monte-Carlo envelope, Frequency content; the flight ones grouped under
  *Flight logs*. A generic *Verification report* (requirements table, pass / fail per run, the plot of each failure,
  how to reproduce), en + he, every export format.
- **CC16 Examples (made by tools/, small).** `servo_step.mat` (a Simulink-style control loop, multi-rate, with its
  requirements), `process_plant.h5` (a thermal process simulation), `montecarlo/` (50 runs + requirements.json), a
  vehicle simulation against its test (non-flight). The welcome groups examples by task: Look at a recording ·
  Simulation against test · Verify against requirements · Find what went wrong · Many runs · Byte streams ·
  Flight logs (ArduPilot, PX4, MAVLink).
- **CC17 Words.** The generic UI says run / recording / signal / state; flight words only in the flight profile,
  templates and examples (welcome.ts 39, templates.ts 32, mapsAnd3d.ts 17 flight words today). README and the
  docs site: generic first, *Flight logs* as one section.

## C - technical (from the advocate / judge round)
- CC18 oxlint baseline in tools/quick_check.py + ci.yml (171 warnings today: only new ones fail); fix now
  no-loss-of-precision (chartUtil.test.ts:49), globals (mapLayers.ts:38).
- CC19 Sweeps: singular "1 limit" (swStLimits / swStGoal); the "neighbours hold" column "–" with no limit; Hebrew
  time ranges in Checks' findings (bidi isolation).
- CC20 Compare: the unit on the difference plot; a short noise note. A new derived signal's name shortened (the
  formula in its tooltip; old names unchanged). The loaders' 21 print() -> logging.
- C7, C9, C12-C19 of the 1.36.0 review: their text is outside the repo (/home/claude/review) - skipped unless the
  owner supplies it.

## D - refactoring (behaviour unchanged, after the UI work on each file)
- CC21 the csv_loader <-> bin_loader cycle (svcore/load_common.py, re-exports kept); bin_loader.py split.
- CC22 Globe3D.tsx (1379), TimeChart.tsx (1122), GeoChart.tsx (1100) -> hooks + helpers per component.
- CC23 bundle: index 698 kB (react-dom, uplot), api 578 kB (the i18n tables) -> vendor chunks, lazy GeoChart and
  rare panels; no chunk over 500 kB.

## Order
CC18 (the lint gate first, so the rest is checked) -> CC1-CC10 (screen by screen) -> CC11-CC17 -> CC19-CC20 ->
CC21-CC23 -> Phase 3 (the same count, a fresh agent's "where would you click") -> Phase 4 (release).
Not in scope: N5 (under 930 px, documented). Owner's call: I5 (ci on every push to main).
