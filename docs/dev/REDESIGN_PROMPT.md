# Prompt – continue the redesign (any stage, any AI agent)

Give this file to any AI coding agent (Claude Code, Codex, Cursor, Copilot, Gemini, …) on a clone of this repository:
*"Read `docs/dev/REDESIGN_PROMPT.md` and do it."* It is written so the agent finds by itself where the work stopped and
continues from there, one task at a time, the same way at every stage. Nothing in it depends on one agent's tools.

---

## 1. Who you work for, and how

- The owner is **David Alpert**. He reads **Hebrew**: every report to him is in Hebrew, plain, the outcome first. Code,
  comments, documentation and commit messages stay in **English**.
- The product is **Signal Viewer**: a local, offline desktop app for analysing time signals – a Python FastAPI backend
  (`backend/`) and a React + TypeScript UI (`frontend/`), English and Hebrew (RTL), light and dark. Users: flight-test and
  drone engineers (ArduPilot `.bin`, MAVLink `.tlog`, PX4 `.ulg`), simulation engineers (MATLAB `.mat`, Python), test
  benches (CSV, Parquet, HDF5), ROS 2 (`.mcap`). **It is an analysis tool for any time signals, not an ArduPilot tool.**
- The work: **the redesign of 2026-11-14** – Sweeps as one study for both flows, a design system ("a quiet frame, the data
  speaks"), plots, the map, every area, then new capabilities. The plan is approved: **`docs/dev/PLAN_2026-11-14.md`**.

## 2. Read first (in this order, every time you start)

1. `CLAUDE.md` – the binding rules (they override this file). In short: one way to do a thing; a control in exactly one
   place (the command palette and shortcuts are the only second entries); every user-visible string in
   `frontend/src/i18n/` in `en` and `he`; CSS variables only (no literal colours / sizes / radii – a test enforces it);
   saved files backward compatible (new fields optional, never rename a saved field); heavy work in the backend; offline,
   127.0.0.1 only; every workspace change through `commit` (Undo); formulas only through the AST whitelist.
2. `docs/dev/PLAN_2026-11-14.md` – what to build and why: §0 the summary, §2.2 the feature checklist that must survive,
   §3.4 the design rules, §3.6 *any data, not only ArduPilot*, §3.7 the map, §4 Sweeps, §5 the design system, §6 what moves
   where, **§7 the tasks (each with *Done when* and its e2e files)**, §8 the owner's decisions (all answered).
3. `docs/dev/TASKS.md` – **"Current state"** at the top and the **last lines of "Log"** at the bottom: what is done, where
   the last session stopped, what is next.
4. `docs/dev/ROADMAP.md` – the last milestone (32): which phases are ticked.
5. `git log --oneline -15` – the last commits (each task is one commit, its title names the task: `A1 …`, `C4 …`).
6. `docs/dev/E2E_MAP.md` – which e2e files cover which change. Mock-ups: `docs/dev/mockups/index.html` (open it in a
   browser; each page switches dark / light, EN / HE). The app before the redesign: `docs/dev/mockups/before/`.
7. If you are Claude Code: also load the skill `.claude/skills/signalviewer-continue/SKILL.md` (paths, sandbox quirks).

## 3. Find where you are

- The **order of phases** is fixed: **A → C → B → M → D → E → F** (§7 of the plan; F: F3, F1, F2, F5 first, then F4, F6;
  F7 and F8 only if the owner asks).
- The **next task** is the first task of that order that is not done. A task is done when its line in `TASKS.md` says
  *done* and a commit with its id exists. If `TASKS.md` says a task was **stopped in the middle**, continue it from the
  note it left (do not start it over); check the working tree (`git status`) for unfinished changes first.
- If `TASKS.md` and the commits disagree, trust the code: read the task's *Done when* and check it.
- If the owner gave you a different instruction in his message, it overrides this order.

## 4. Set up (once per machine)

```bash
pip install -r requirements.txt            # if pywebview fails to build (no GUI): install the rest without it
pip install -r requirements-dev.txt
cd frontend && npm ci && cd ..
python tools/quick_check.py                # the baseline must be green before you change anything
```
- e2e and pictures need Playwright with Chromium. If a Chromium is installed elsewhere, point the tools at it:
  `export SV_CHROMIUM=/path/to/chrome`.
- After a frontend change the app's first start rebuilds the UI (~1 min): warm it before e2e with
  `python run.py --port 8777 --no-open --browser` (stop it after "running at").

## 5. One task – the loop

1. **Read** the task in the plan (§7: *Done when*, e2e files) and the section it refers to. Read the code you will
   change **and every caller of it** (`grep` the symbol in `backend/` and `frontend/src/`). Prefer extending an existing
   mechanism over adding a parallel one.
2. **Pictures before** (if the screen changes): `python tools/plan_screens.py --out docs/dev/mockups/<task>/before`.
3. **Change** the code – only what the task needs. New strings in both languages. New CSS uses tokens. Saved files stay
   readable by the previous version and old files open.
4. **Check**:
   - `python tools/quick_check.py` – tsc, Vitest, backend pytest, mypy – all green.
   - Add or update tests: a backend test for backend behaviour, Vitest for frontend logic without a screen, e2e for UI
     flows. e2e tests wait on state (`window.__sv.state()`, `window.__svSweeps`, `data-*` attributes), **never on a sleep**.
   - Run **only the e2e files of the task** (plan §7, `E2E_MAP.md`) – and, if the change alters what is on screen by
     default, also the files of the views that gain or lose space: `python -m pytest -q tests/e2e/test_<x>.py`.
     Update a selector when a control moved; **never weaken an assertion**.
   - Where speed matters (Sweeps on a million runs, the plots' `test_perf_budget`), measure before and after.
5. **Pictures after** (`.../<task>/after`), dark / light, en / he for anything visible; `python tools/count_controls.py`
   when controls moved (no screen may end with more controls than before).
6. **Write it down** (same commit): `TASKS.md` (the task's status, "Current state", one Log line: date, task, what ran
   and passed, what is next), tick it in `ROADMAP.md`, a user-facing line in `CHANGELOG.md` under the next version
   (`## 1.28.0 – unreleased`; create the heading if missing), a line in `E2E_MAP.md` for each e2e file written or changed.
7. **Commit and push** – one task per commit, straight to `main`, no pull request:
   ```bash
   git -c user.name="David Alpert" -c user.email="davidalpert11@gmail.com" commit --author="<Your agent's name> <its email>" -m "C4 One store, one Undo for a study" -m "<what and why>"
   git pull --rebase origin main && git push origin HEAD:main
   ```
   (The committer is the owner; the author is the agent. Never force-push. If pushing is refused, make a patch:
   `git format-patch <base>..HEAD --stdout > redesign_<task>.patch` and say where it is.)

## 6. The end of a phase

- Run the **whole e2e suite** (`python -m pytest -q tests/e2e`, ~30 min; in the background; clean `/tmp/pytest-of-*`
  between big runs on a small disk). Fix what it finds.
- Build the UI once: `cd frontend && npm run build` (updates the committed `frontend/dist`).
- **Report to the owner in Hebrew**: what changed (the outcome first), before / after pictures, what was checked and
  passed, what was not checked, what is next. Then continue with the next phase unless he said to wait.

## 7. Before you stop (any reason – done, out of context, an error you cannot fix)

Update `TASKS.md` "Current state" with: the task, how far it got, the files changed and not committed, the exact next
step, anything you found that the next agent must know. Commit (even a work-in-progress commit titled `WIP <task>: …`)
and push. The next agent starts from §2 of this file and must be able to continue without asking.

## 8. Honest reporting

- Say *verified* only for what ran and passed; *partially verified* with what did not run; *not verified* otherwise.
- **Never claim** what cannot be checked without Windows or a GPU: the Portable (`SignalViewer.exe study …`), the
  pywebview close prompt, a real farm launcher, frame rates on a real graphics card – these are the owner's to check.
- Releases and tags are the owner's: never create a tag or a release.
- If a decision is truly not in the plan (a new trade-off), stop that part, ask the owner in Hebrew with a
  recommendation, and continue with another task meanwhile.

## 9. Decisions already made (do not ask again)

Layout A for Sweeps (navigator: Set up · Tables with rounds · Together; the middle; the Run column) · both flows in one
study: *I have results* / *Start from nothing*, continue later · `.svstudy.json` with an optional `workspace` block is the
study file; `.svsweep` keeps opening and saving for one table without set-up · the Goal step writes the study's goal ·
amber only for the cursor and time; selection / active / primary a neutral ink ring; the 2nd trace colour moved off the
cursor's hue · one top row, plot tabs in the stage bar · IBM Plex Mono for numbers · *at a glance* (extending the
existing strip), a mode echo in each plot card, help behind `?` – each can be turned off · every idea format-neutral,
profiles are templates, one *Checks* view (limits + data quality + a log's health check) · the map: Offline stays the
default; online layers opt-in, through the app, cached, blocked by *Never use the network*; no bulk download from
OpenStreetMap · order A → C → B → M → D → E → F.
