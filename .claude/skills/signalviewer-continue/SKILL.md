---
name: signalviewer-continue
description: Continue work on Signal Viewer (this repository) as the previous agents did - where everything is, the rules that must not break, how to verify a change (the exact commands, the sandbox's quirks), how to commit / hand over, and what is open next (the owner's UI review of every area and button). Use at the start of any session on this repo, before changing code.
---

# Continuing Signal Viewer

Signal Viewer is a local, offline desktop app for flight-test and simulation engineers: a Python FastAPI
backend (`backend/`) and a React + TypeScript UI (`frontend/`), shown in a pywebview window or a browser,
English and Hebrew (RTL). The owner (David Alpert) reads Hebrew: **report to him in Hebrew, plainly, outcome
first**; code, comments, docs and commit messages stay in English.

## 1. Read first (in this order)

1. `CLAUDE.md` – the binding rules (one way to do a thing, one place per control, en + he for every string,
   CSS variables only, sessions backward compatible, heavy work in the backend, offline, every workspace change
   through `commit` with Undo). They override anything here.
2. `docs/dev/TASKS.md` → "Current state" (top) and the last lines of "Log" (bottom): what is done, what is open.
3. `docs/dev/ROADMAP.md` – the catalogue; the newest milestone is at the end.
4. The latest round's spec / status box: `docs/dev/AGENT_PROMPT_<date>.md`, its plan `docs/dev/PLAN_<date>.md`,
   per-lane notes `docs/dev/lanes/*.md`, and `docs/dev/E2E_MAP.md` (which e2e files cover which change).

## 2. Where things are

| Area | Backend | Frontend |
|---|---|---|
| Recordings (files, plots, cursors) | `backend/app/routes/{files,data,analysis,...}.py`, `backend/svcore/*` readers | `frontend/src/components/{PlotView,TimeChart,DataPanel,StageBar,TopBar}.tsx`, state in `frontend/src/store/` (`slices/`, `actions/`) |
| Investigate / What changed | `svcore/firstchange.py`, `svcore/investigate.py` | `components/InvestigatePanel.tsx`, `WhatChanged.tsx` |
| Map / 3D / story | `app/mapimage.py`, `app/scene3d.py`, `svcore/story.py` | `components/GeoChart.tsx`, `Globe3D.tsx` (Cesium, lazy), `MapBar.tsx`, `MapStory.tsx` |
| Fleet | `app/fleet.py`, `routes/fleet.py` | `components/FleetPanel.tsx` |
| Sweeps (one table) | `svcore/sweep/*`, `routes/sweep.py` | `components/sweeps/*`, `frontend/src/sweeps/state.ts` |
| Sweeps → Common parameters (many tables), next runs, launcher, the loop, the demo | `svcore/study.py` (the `.svstudy.json` file, schema `docs/dev/study.schema.json`), `sweeps_common.py` (W14 ranking), `sweeps_next.py` (W15 proposals), `launcher.py` + `placeholders.py` (W17), `loop.py` (the loop for any study), `demo.py` (W18: the loop + a full-grid reference), `drone_model.py`; routes `sweeps_common.py`, `sweeps_farm.py`; CLI `backend/signalviewer/study.py` (`python -m signalviewer.study ...`, also `SignalViewer.exe study ...` via `run.py`) | `components/sweeps/StudyPanel.tsx`, `LoopSection.tsx`, `DemoView.tsx`, `SpaceView.tsx`, `ConvergenceChart.tsx`; state `frontend/src/sweeps/studyStore.ts`; types `studyTypes.ts`; opening from outside `studyOpen.ts` |
| Welcome screen, examples | `routes/fs.py` `EXAMPLE_SETS` (`/api/examples`), `examples/` | `components/Welcome.tsx`, pictures `frontend/public/examples/<id>.<theme>.webp` (made by `tools/make_readme_media.py --only examples`) |
| Settings | `routes/system.py` (`/api/settings`) | registry `frontend/src/settings.ts`, dialog `components/SettingsDialog.tsx` |
| i18n | – | `frontend/src/i18n/<area>.ts` (welcome, study = Sweeps → Common parameters, app, plots, ...), `en` and `he: typeof en` |
| Styles | – | `frontend/src/index.css` (tokens incl. motion `--motion-fast/base`, `--ease-out`), by area `frontend/src/styles/{welcome,study,app,plots,review}.css` (loaded in that order after index.css) |

## 3. Verify a change (exact commands)

```bash
python tools/quick_check.py            # tsc -b, vitest, backend pytest -x, mypy - stops at the first failure (~5 min)
```
- e2e: only the files that touch the change (`docs/dev/E2E_MAP.md` lists them); never the whole suite while
  developing (~9 min+). `python -m pytest -q tests/e2e/test_<x>.py`.
- New tests wait on state (`window.__sv.state()`, `window.__svSweeps.idle()/.saved()`, `window.__svStudy`,
  `data-*` attributes), never on a sleep.
- After a version bump: `python tools/make_validation_doc.py` (a test compares `docs/validation.md`).
- Build the UI once at the end of a round: `cd frontend && npm run build` (updates the committed `frontend/dist`);
  check `python run.py --no-build --browser --no-open --port 8771` serves it.
- UI audit: `python tools/count_controls.py [--root <other checkout>]` counts the controls a new user sees on
  four screens (compare a `git worktree` of `main` with the branch).

### Cloud sandbox quirks (seen 2026-11-13)
- `pip install -r requirements.txt` fails on `pywebview` (proxy_tools wheel): install the rest without it.
- `pip install -r requirements-dev.txt` upgrades Playwright past the pre-installed browsers. Use
  `export SV_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` (the e2e fixture and the media tool
  read it); for fixtures that ignore it (`test_globe3d.py`), link the expected headless-shell folder to the
  installed one (`ln -s /opt/pw-browsers/chromium_headless_shell-1243 /opt/pw-browsers/chromium_headless_shell-<new>`).
- After any frontend change the first app start rebuilds the UI (`run.py` → `frontend/.local-dist`, ~1 min); an e2e
  module's server can time out on it ("Connection refused" / URLError in every test of the file). Warm it first:
  `timeout 120 python run.py --port 8777 --no-open --browser` (wait for "running at", then stop it), then run the e2e.
- Never symlink `frontend/node_modules` into another worktree: its start-up runs `npm ci` and empties yours.
- No Windows: the Portable (`SignalViewer.exe study …`) and the pywebview close prompt cannot be checked here -
  say so ("not verified"), never claim it.

## 4. Commit, push, hand over

- Identity (binding): `git -c user.name="David Alpert" -c user.email="davidalpert11@gmail.com" commit --author="Claude <noreply@anthropic.com>" ...`
  and check `git log --format='%an <%ae> | %cn <%ce>' <base>..HEAD | sort -u` shows exactly that one pair.
- The owner (2026-11-13): **push straight to `main`, no pull request** (he can always go back a version). Keep each
  commit one coherent step; rebase on `origin/main` before pushing; never force-push. Set the identity once per
  clone (`git config user.name "David Alpert"; git config user.email "davidalpert11@gmail.com"`) so a cherry-pick or
  rebase keeps the committer right, and commit with `--author="Claude <noreply@anthropic.com>"`. If pushing is refused, hand over
  `git format-patch --binary <base>..HEAD --stdout > <file>.patch` (the owner applies it with `git am`).
- After every task: a line in `docs/dev/TASKS.md` (Current state + Log), the task ticked in `ROADMAP.md`,
  a user-facing line in `CHANGELOG.md` (under the unreleased version).
- Honest states: *verified* (the check ran and passed), *partially verified* (say what did not run), *not
  verified*. `done` means the task's "Done when" is fully met.

## 5. Open next (the owner, 2026-11-13)

**A review of every area and every button** – fix bugs, remove what is not needed or move it to its right
place, give each area a better visualization; the most modern and practical app. Suggested method:
1. For each area (Welcome, Recordings: file panel / stage bar / plot head / timeline / Inspector / each side
   panel, Map & 3D, Investigate, Compare, Report, Log, Sweeps single table, Sweeps → Common parameters + loop,
   Fleet, Settings, the command palette) take screenshots light / dark, en / he, at 1280×720 and 1920×1080
   (`tools/make_readme_media.py` has the start-the-app helpers: `App`, `page`, `open_api`).
2. List every control there (`tools/count_controls.py` as a start), and for each: what it does, how often it is
   needed, whether another control does the same (CLAUDE.md: one place per control; the palette and shortcuts are
   the only second entries). Write the list into `docs/dev/TASKS.md` as a round with one task per area.
3. Change one area at a time, with its e2e files (update selectors, never weaken assertions) and a recount.
4. Report to the owner in Hebrew with before / after screenshots.

Done so far (2026-11-13, R1-R13 and the owner's notes - see TASKS.md Log): every area reviewed once; a demo per
area on the welcome screen (grouped Recordings / Sweeps / Fleet; `areaExample.ts` hands a card to its lazy area;
`examples/sweeps/drone_tuning.svsweep` = a table with its question); every report opens with *The process in
brief* (`reportProcess.ts`); Sweeps fast on 1M runs (the answer reused across Parameter sets / All runs, a
50k sample keeping every set, mark arrays instead of np.unique); All runs shows the scenario axes; the plot
menu's *Save / export* submenu; README + site home rewritten. Measure speed with a big table (a 1M-row CSV
made with numpy, the sweep card pointed at it - see the Log) before and after a change.

Next: the Compare panel and the Create-signals panel at 1280 in Hebrew; the Sweeps single table's left column
(long); the welcome's Fleet picture (cropped by 16:9); `test_less_clutter::test_what_does_not_apply_is_hidden`
(fails on main in the sandbox: the 3D view).

Known rough edges to look at first: the Sweeps single-table area and Common parameters are two panels with
related ideas (consider one entry with two modes); `Ctrl+Z` in Common parameters does not reach the study's own
Undo; the 3D view's frame rate on a real GPU is unmeasured; W13.3 (smooth zoom easing) was not shipped.
