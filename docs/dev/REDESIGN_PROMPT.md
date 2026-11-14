# Prompt – continue the redesign (any stage, any AI agent)

Give this file to any AI coding agent – one agent, or one per lane (*"… You are lane L2."*) – (Claude Code, Codex, Cursor, Copilot, Gemini, …) on a clone of this repository
(`git clone https://github.com/DavidAlpert11/SignalViewer`):
*"Read `docs/dev/REDESIGN_PROMPT.md` and do it."* It is written so the agent finds by itself where the work stopped and
continues from there, one task at a time, the same way at every stage. Nothing in it depends on one agent's tools.
**By default the agent has no GitHub write access: it hands each step over as a patch made against the repository's
current `main` (§5, step 7a), which the owner applies. It watches its token / context budget and stops in time with a
patch and a hand-over note for the next agent (§7).**

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
3. `docs/dev/TASKS.md` – **"Current state"** at the top (a **HAND-OVER** block there, if any, comes first: start from its
   *Next step*) and the **last lines of "Log"** at the bottom: what is done, where
   the last session stopped, what is next.
4. `docs/dev/ROADMAP.md` – the last milestone (32): which phases are ticked.
5. `git log --oneline -15` – the last commits (each task is one commit, its title names the task: `A1 …`, `C4 …`).
6. `docs/dev/E2E_MAP.md` – which e2e files cover which change. Mock-ups: `docs/dev/mockups/index.html` (open it in a
   browser; each page switches dark / light, EN / HE). The app before the redesign: `docs/dev/mockups/before/`.
7. If you are Claude Code: also load the skill `.claude/skills/signalviewer-continue/SKILL.md` (paths, sandbox quirks).

## 3. Find where you are – your lane, your next task

The work is split into **five lanes that run in parallel**, each one agent, each **owning its files**, plus a **Final**
lane after them (plan §7.0 – read it: the lanes table, the sync point S1, the shared files' lane blocks, the test policy).

- **If the owner named a lane** ("You are lane L3"): do only that lane's tasks, in its order, and edit **only the files
  it owns** – plus your own lane block in the shared files (`TASKS.md`, `ROADMAP.md`, `E2E_MAP.md`, `CHANGELOG.md`,
  `settings.ts`, `i18n/index.ts`, `store/state.ts`). Need a file another lane owns? Do not edit it: write the request
  under that lane in `TASKS.md` and go on. Need a new design token? Ask L1 the same way; meanwhile use the nearest token
  with a `TODO(L1 token)` comment.
- **If no lane was named**: you are the only agent – take the next task in the one-agent order **A → C → B → M → D → E →
  F** (F: F3, F1, F2, F5, then F4, F6; F7 / F8 only if the owner asks).
- **The Final lane** starts only when every lane's board line says *done* and its patches are on `main`.
- **Sync point S1** (A3 + A4 on `main`): until it is there, lanes L2–L5 do only their tasks without UI (backend, logic,
  tests) – the lanes table says which. Check `git log origin/main` for A3 / A4.
- Your **next task** = the first task of your lane (or of the order) not done. Done = its line in `TASKS.md` says *done*
  and a commit with its id is on `main` or in your unapplied patch. A **HAND-OVER** block for your lane comes first: start
  from its *Next step*. Check `git status` for unfinished work.
- If `TASKS.md` and the commits disagree, trust the code: check the task's *Done when*.
- The owner's message overrides all of this.

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
4. **Check – only what is relevant** (the owner: the full checks take time; they run once, at the end, before the
   version update):
   - `cd frontend && npx tsc -b`; the Vitest files of what changed (`npx vitest run src/<path>`).
   - The backend tests of the modules you changed (`cd backend && python -m pytest -q tests/test_<x>.py`) and
     `mypy --config-file ../pyproject.toml <the changed modules>`.
   - Add or update tests: a backend test for backend behaviour, Vitest for frontend logic without a screen, e2e for UI
     flows. e2e tests wait on state (`window.__sv.state()`, `window.__svSweeps`, `data-*` attributes), **never on a sleep**.
   - **Only the e2e files of the task** (plan §7 tables, `E2E_MAP.md`) – and, if what is on screen by default changes, also
     the files of the views that gain or lose space: `python -m pytest -q tests/e2e/test_<x>.py`. Update a selector when a
     control moved; **never weaken an assertion**.
   - Where speed matters (Sweeps on a million runs, the plots' `test_perf_budget`), measure before and after.
   - **Not** the whole backend suite, **not** the whole e2e suite. Before each patch / push only: `python
     tools/quick_check.py` (~5 min).
5. **Pictures after** (`.../<task>/after`), dark / light, en / he for anything visible; `python tools/count_controls.py`
   when controls moved (no screen may end with more controls than before).
6. **Write it down** (same commit): `TASKS.md` (the task's status, "Current state", one Log line: date, task, what ran
   and passed, what is next), tick it in `ROADMAP.md`, a user-facing line in `CHANGELOG.md` under the next version
   (`## 1.28.0 – unreleased`; create the heading if missing), a line in `E2E_MAP.md` for each e2e file written or changed.
7. **Commit, then hand the work over** – one task per commit, its title starting with the task id (`C4 One store, one
   Undo for a study`), its body saying what and why:
   ```bash
   git -c user.name="<your agent's name>" -c user.email="<its email>" commit -m "C4 One store, one Undo for a study" -m "<what and why>"
   ```
   Then **one of the two**, by what you were given:

   **(a) The default – no GitHub write access: a patch.** The owner applies it himself. Every time you export, export it
   **against the repository as it is now**, not against where you started:
   ```bash
   git fetch origin main                       # the current state of the repository (it is public: no rights needed)
   git rebase origin/main                      # your commits on top of it; resolve conflicts, re-run quick_check
   git format-patch origin/main --stdout > <out>/signalviewer_$(date +%Y-%m-%d_%H%M)_<lane>_<task-ids>.patch
   git worktree add ../sv-check origin/main
git -C ../sv-check -c user.name=check -c user.email=check@localhost am < <that patch>   # must apply cleanly
git worktree remove --force ../sv-check
   ```
   - The last three lines prove the patch applies to the current `main`. If it does not, fix it before you hand it over.
   - The patch holds **every commit not yet on `main`** – also those of earlier patches the owner has not applied yet. So
     the newest patch is always the only one he needs; say so, and never ask him to apply two on top of each other.
   - `<out>`: the folder the owner named; otherwise a folder **outside** the repository (e.g. `../signalviewer_patches/`).
     Never commit a patch file into the repository. Never commit `frontend/dist` from a lane (only the Final builds it).
   - If the network is closed and `git fetch` fails: ask the owner for the current `main` commit (or a fresh copy of the
     repository) before exporting; until then export against the last `main` you know and write its commit id in the
     file name and in your report (`…_base-1a2b3c4.patch`).
   - Tell him in Hebrew: the file's path, the tasks in it, the base commit, and the one command:
     `git am < <the patch>` (in his clone, on an up-to-date `main`; then `git push`).

   **(b) Only if you were given push rights to `main`** (the owner says so): the owner is the committer, you the author –
   `git -c user.name="David Alpert" -c user.email="davidalpert11@gmail.com" commit --author="<agent> <email>" …`, then
   `git pull --rebase origin main && git push origin HEAD:main`. Never force-push. If the push is refused, fall back to (a).

## 6. The end of a lane – and the Final

- **End of a lane:** run the union of the lane's e2e files once (not the whole suite), `quick_check`, export the lane's
  patch, set the lane's board line in `TASKS.md` to *done*, and **report to the owner in Hebrew**: what changed (the
  outcome first), before / after pictures, what was checked and passed, what was not.
- **The Final lane (one agent, after every lane is on `main`)** – the only time the full checks run, **before the version
  is updated**: E1 pictures, E2 guides / features / CHANGELOG, E4 the test-bench example; then the **whole e2e suite**
  (`python -m pytest -q tests/e2e`, ~30 min, in the background; clean `/tmp/pytest-of-*` between big runs on a small disk),
  `quick_check`, the 1M-run Sweeps measure, `test_perf_budget`, `mkdocs build --strict`; fix what they find; then E3 – the
  version (`backend/app/version.py`, `requirements.txt` per `pyproject.toml`'s note), `python tools/make_validation_doc.py`,
  `cd frontend && npm run build` (the committed `frontend/dist`). Report in Hebrew. The owner tags.

## 7. Stop in time – before the tokens or the context run out

You will not always see how much of your quota or context is left, so **work so that running out loses nothing**, and
stop on purpose before it happens.

**Always (cheap insurance):**
- Small steps: one task = one commit; a long task is split into parts, each its own commit (`C4a`, `C4b` …). Never hold
  more than one task's work uncommitted.
- After every task the hand-over of §5 step 7 (a patch against the current `main`, or a push). So at any moment the
  owner has everything up to the last finished task.
- Before a long step (the whole e2e suite ~30 min, a big refactor, many pictures), ask yourself whether what is left
  covers it **and** the hand-over after it. If not, hand over first.

**The signs that it is time to stop** – any one of them:
- your tool shows a usage / context meter at **about 75 %** or more, or says the context was compacted / summarised;
- a warning about a rate limit, a usage cap, a budget, or "approaching the limit";
- the owner gave you a budget (tokens, money, time, a number of tasks) and you are near **80 %** of it;
- you notice you are re-reading files you already read, or losing track of earlier decisions (the context is full).

**How to stop (keep about a fifth of your budget for this – it takes a few thousand tokens):**
1. Start nothing new. Bring the tree to a state that builds: finish the small piece in hand, or put the unfinished
   part away (`git stash`, or leave it out) – never hand over a broken `main`.
2. Run what you can afford of the checks (`python tools/quick_check.py` at least); write down what you did not run.
3. Commit (a finished task as usual; unfinished work as `WIP <task>: <what is done, what is not>`).
4. Update **`docs/dev/TASKS.md` → "Current state"** with a hand-over block (template below) and a Log line. If you learned
   something that changes *how* the work is done (a command that fails, a new quirk, a better order), fix
   **this file (`REDESIGN_PROMPT.md`)** too, so the next agent gets it – both in the same commit.
5. Export the patch against the current `main` (§5 step 7a) – or push if you have the rights.
6. Tell the owner in Hebrew: what is finished, what is half-done, the patch's path, and the one line for the next agent:
   *"Read `docs/dev/REDESIGN_PROMPT.md` and do it."* (The next agent needs nothing else: this file sends it to the
   hand-over block.)

**The hand-over block** (in your lane's block of the lane board in `TASKS.md`, or at the top of "Current state" when
working alone; the next agent reads it first):
```
- HAND-OVER <date time> (<agent>, lane <Lx or one agent>): stopped because <budget / context / error / done>.
  Last finished task: <id> (commit <sha>, in patch <file> / on main).
  In progress: <id> – done: <…>; not done: <…>; uncommitted / stashed: <none | what>.
  Next step, exactly: <the first thing to do>.
  Checks: quick_check <green / not run>; e2e run: <files> <green / failed: …>; not run: <…>.
  Watch out: <anything surprising – a flaky test, a decision to ask the owner, a file that must not be touched>.
```

## 8. When you are simply done for now

Same as §7 steps 3–6: commit, the hand-over block, the patch / push, the report in Hebrew.

## 9. Honest reporting

- Say *verified* only for what ran and passed; *partially verified* with what did not run; *not verified* otherwise.
- **Never claim** what cannot be checked without Windows or a GPU: the Portable (`SignalViewer.exe study …`), the
  pywebview close prompt, a real farm launcher, frame rates on a real graphics card – these are the owner's to check.
- Releases and tags are the owner's: never create a tag or a release.
- If a decision is truly not in the plan (a new trade-off), stop that part, ask the owner in Hebrew with a
  recommendation, and continue with another task meanwhile.

## 10. Decisions already made (do not ask again)

Layout A for Sweeps (navigator: Set up · Tables with rounds · Together; the middle; the Run column) · both flows in one
study: *I have results* / *Start from nothing*, continue later · `.svstudy.json` with an optional `workspace` block is the
study file; `.svsweep` keeps opening and saving for one table without set-up · the Goal step writes the study's goal ·
amber only for the cursor and time; selection / active / primary a neutral ink ring; the 2nd trace colour moved off the
cursor's hue · one top row, plot tabs in the stage bar · IBM Plex Mono for numbers · *at a glance* (extending the
existing strip), a mode echo in each plot card, help behind `?` – each can be turned off · every idea format-neutral,
profiles are templates, one *Checks* view (limits + data quality + a log's health check) · the map: Offline stays the
default; online layers opt-in, through the app, cached, blocked by *Never use the network*; no bulk download from
OpenStreetMap; the cameras renamed by what they do (Free · From above · Around it · Behind it · Cockpit in 3D only, M6) ·
handing over: a patch against the current `main` unless push rights were given · order A → C → B → M → D → E → F.
