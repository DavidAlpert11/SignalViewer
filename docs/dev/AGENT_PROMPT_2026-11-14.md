# Agent prompt – 2026-11-14: a planned redesign (Sweeps as one workspace, modern plots and look)

> Paste this into a new session (or say: "read `docs/dev/AGENT_PROMPT_2026-11-14.md` and do it").
> **This session starts with planning only.** No product code is changed until the owner approves the plan.

## 0. Who you are working for, and how

- The owner, David Alpert, reads Hebrew: **every report to him in Hebrew, plainly, outcome first**. Code,
  comments, docs and commit messages stay in English.
- First load the skill `.claude/skills/signalviewer-continue/SKILL.md` and read what it lists (`CLAUDE.md`,
  `docs/dev/TASKS.md` – Current state and the last Log lines, `docs/dev/ROADMAP.md`). `CLAUDE.md` binds.
- Identity and pushing: as in the skill (§4) – commit with `--author="Claude <noreply@anthropic.com>"`, the
  committer David Alpert; **push straight to `main`, no pull request**. A plan is committed like code.
- State of the product: 1.27.0 is final on `main` (the owner tags it). Everything here is for the next version.

## 1. What the owner asked (2026-11-14, his words, translated)

1. **Sweeps feels like separate apps.** "If you open the example of the runs, you cannot open the ready tables
   on the same screen and set the settings. It is as if each one is in something different." Example: open the
   smart-sweep demo (the loop run until it converges) – its result tables cannot be opened and examined with the
   single-table tools (roles, goal, results, charts) on the same screen.
2. **The plots.** Not reviewed in depth yet, but he saw **ArduDeck**, which "does beautiful things", and wants to
   take inspiration from it.
3. **A planned, orderly redesign** that keeps every capability of Signal Viewer ("my features") with a modern
   look and feel.
4. Start with planning.

## 2. What is true in the code today (verify, do not trust this blindly)

- `frontend/src/components/sweeps/SweepsArea.tsx`: the area shows **either** `StudyPanel` (Common parameters –
  several tables, the loop, the demo view) **or** `StudyView` (one table: Data → Columns → Goal → Results) **or**
  the welcome: `common ? <StudyPanel /> : study ? <StudyView /> : <SweepsWelcome />`. Two stores:
  `sweeps/state.ts` (`useSweeps`, the single-table studies, `.svsweep`) and `sweeps/studyStore.ts`
  (`useStudyPanel`, the `.svstudy.json` study). Two file formats, two undo stacks, two sets of charts
  (`ParallelPlot` / `Desk` vs `SpaceView` / `ConvergenceChart`).
- The demo and the loop write each round's results under the study's folder (the demo: a work copy in
  `~/.signalviewer/smart_sweep_demo/<key>/`, `results/…`, collected per table as `collected_<table>.csv` –
  `backend/svcore/launcher.py`, `loop.py`, `demo.py`). Those tables are never offered to the single-table flow.
- The examples: `examples/drones/` (three tables + `drones.svstudy.json`), `examples/smart_sweep_demo/`
  (`sim.py`, `demo.svstudy.json`), `examples/sweeps/` (one table + `drone_tuning.svsweep`, its question).
- Recordings plots: `TimeChart.tsx` (uPlot), `PlotView.tsx`, `GeoChart.tsx`, `Globe3D.tsx`, `MapBar.tsx`;
  tokens in `frontend/src/index.css`, styles by area in `frontend/src/styles/`.

## 3. Phase 1 – planning (this session's whole first part)

Produce **`docs/dev/PLAN_2026-11-14.md`** plus pictures, commit and push them, then **stop and ask the owner to
approve** (in Hebrew, a short summary with the pictures). Do not change product code before that.

### 3.1 Inventory (what exists, so nothing is lost)
- Every screen and mode: Recordings (welcome, files, plots, Map / 3D, each side panel, Inspector, timeline,
  Report, Log, Live), Sweeps (welcome, single table's four steps, Common parameters, the loop, the demo), Fleet,
  Settings, the command palette. Screenshots light / dark, en / he, 1440×900 (`tools/make_readme_media.py` has
  `App`, `page`; set `SV_CHROMIUM` as the skill says).
- A **feature list** ("the owner's features" – what must survive): per area, every capability and where it is
  today. `tools/count_controls.py` gives the control counts. This list is the acceptance checklist of the redesign.

### 3.2 Research ArduDeck (inspiration, not a copy)
- Find ArduDeck's public material (its site / repository / screenshots / videos – web search). Write down
  **what makes it look good**, as principles: layout, density, typography, colour use, how plots and telemetry
  are presented, motion, empty states, dark theme. Cite the sources (links) in the plan.
- **Do not copy** its branding, names, icons, assets or exact screens – take principles and turn them into
  Signal Viewer's own design. If something cannot be found or confirmed, say so in the plan; never invent what
  ArduDeck does.
- Also look at 2–3 other well-regarded tools in the space only as far as useful (e.g. PlotJuggler, Foxglove,
  UAV Log Viewer) – what each does well that Signal Viewer lacks.

### 3.3 Sweeps as one workspace (the main problem)
Write the target **information architecture**: one Sweeps workspace where a study holds tables, and any table
(an opened file, a demo / loop round's collected results, a merged table) opens in the same tools on the same
screen. Answer at least:
- What is "a study" (one model for `.svsweep` and `.svstudy.json`? one store? one undo?) and how **old files keep
  opening** (CLAUDE.md: backward compatible – both formats must still load, with a migration if needed).
- The layout: e.g. a left list of the study's tables and runs (files, rounds, merged), the centre the chosen
  table's steps / results, a side for the shared parameters, the loop and convergence – so the demo's tables
  are one click from the single-table tools. Give **2–3 options** with pros / cons and **one recommendation**.
- The demo walkthrough as the acceptance test: open the smart-sweep demo → run 2 rounds → open round 2's
  collected table in the same screen → set its goal → see its results and charts → back to the convergence –
  without leaving the screen.
- The engine stays (W14 ranking, W15 proposals, W17 launcher, the loop): the plan is about the UI and the
  study model, not new maths.

### 3.4 Plots and the look (the redesign)
- A **design system** section: tokens (colour, type scale, spacing, radii, elevation, motion), components
  (buttons, segmented controls, menus, panels, cards, tables, chips, toasts), plot styling (axes, grid, legend,
  cursor readout, markers, the active plot), map / 3D chrome. Light and dark. Hebrew RTL.
- **Mock-ups** of the key screens before code: static HTML pages (in `docs/dev/mockups/`, using the real
  tokens) or annotated screenshots – at least: the Recordings main screen with plots, a Map / 3D view, the
  unified Sweeps workspace (with the demo's table open), and one panel (What changed or Compare).
- Keep every feature of 3.1; say for each screen what moves where (CLAUDE.md: one control in one place).

### 3.5 The plan's last part: the work, in order
- Phases (e.g. A: design tokens and components; B: plots; C: Sweeps unification – model, then UI; D: each
  area adopts the new look; E: docs, pictures, release), each with tasks small enough for one commit, a
  "Done when" per task, the e2e files it touches (`docs/dev/E2E_MAP.md`), and the risks (selectors in e2e,
  saved files, performance – Sweeps must stay fast on a million runs).
- Put the tasks into `docs/dev/TASKS.md` (Current state + a new round) and `ROADMAP.md` (a new milestone).

**Stop here.** Report to the owner in Hebrew: the recommendation for Sweeps, the design direction with the
mock-ups, the phases, and what you need him to decide. Wait for approval.

## 4. Phase 2 – after approval: build it

- One phase at a time, one task per commit, push to `main` after each task.
- After every task: `python tools/quick_check.py`; the e2e files of what changed (update selectors, never
  weaken assertions; tests wait on state, never on sleeps); screenshots before / after.
- End of each phase: the whole e2e suite (~30 min, run it in the background) and a short Hebrew report with
  pictures.
- Keep it fast: measure before / after where it matters (the skill's Log shows how the 1M-run Sweeps table was
  measured).
- Docs follow the product: README / site pictures, the guides (en + he), CHANGELOG under the next version.
- If the context runs low: update TASKS.md (where you stopped, what is next) and the skill, commit, push – so a
  new session continues from the same point.

## 5. Not verified in the cloud (say so, never claim it)

No Windows here: the Portable (`SignalViewer.exe study …`), the pywebview close prompt, a real farm launcher, and
GPU frame rates are the owner's to check. Creating tags / releases is refused for these sessions – the owner tags.
