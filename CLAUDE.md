# Working on Signal Viewer — the one guide for every developer and AI agent

You are working on Signal Viewer: a local, offline desktop app (Python FastAPI backend +
React/TypeScript frontend, shown in a pywebview window or a browser) for analysing time
signals: an engineering data analysis and validation workbench for **any** time-series or measurement
data - test engineers (flight, vehicle, bench: .bin, .tlog, .ulg, CAN + DBC, CSV, Parquet, HDF5, .mcap) and
simulation engineers (MATLAB/Simulink .mat, Python). ArduPilot logs are convenient sample data, not the
product's identity: generic chrome and models; domain content only in profiles / templates.
The owner writes in Hebrew - answer him in Hebrew; code, commits and docs stay in English.

This file holds every rule and practice (it is loaded by itself in a Claude Code session; the last section is
the prompt to start one). The work queue is `docs/dev/TASKS.md` (what is open, the specs waiting for the owner,
a log - written so another developer or agent can take over). `docs/dev/ROADMAP.md` is the catalogue of every
task; `docs/dev/study.schema.json` is the study file's contract (code and tests read it). Work one task at a time; when its "Done when" is met, tick it in
ROADMAP.md and update TASKS.md (current state, the task's status, the log). Update TASKS.md also
when you stop in the middle of a task.

## Before changing anything
1. Read the code you are about to change **and every caller of it** (`grep` the symbol across
   `backend/` and `frontend/src/`). Write down, in the task's notes, what else it touches.
2. Prefer extending an existing mechanism over adding a parallel one (one way to do a thing).
   Check `store.ts` actions, `api.ts`, `files.ts`, `svcore/*` first. `store.ts` is the one place to
   import state from; its parts live in `frontend/src/store/` (T42): `model.ts` (workspace types),
   `slices/` (state by area: workspace + undo, data, view, live, ui), `state.ts` (`useApp`),
   `selectors.ts`, `actions/` (plots, layout, view, notes). New state goes into its area's slice;
   a new action into its area's file (it then appears as `actions.x` by itself). Backend endpoints live in
   `backend/app/routes/<area>.py` (shared helpers: `app/common.py`); `app/main.py` only wires them.
3. Decide **where** a control belongs before writing it:
   - TopBar: workspace / file actions only. StageBar: things about the plots on screen.
   - Side panels: tools that need room. Inspector: properties of the selection.
   - Settings dialog: choices made once (language, theme, defaults).
   - A control appears in exactly one place; shortcuts and the command palette (Ctrl+K)
     are the only allowed second entry points.

## Invariants that must never break
- Signals are addressed by stable ids `"<runId>/<name>"`, never by index.
- Every workspace change goes through `commit` (undo/redo). UI-only state does not.
- Sessions, templates and autosave stay **backward compatible**: old files must still open.
  New fields are optional with defaults; never rename or repurpose a saved field.
- Heavy work stays in the backend; the UI receives decimated data only. One exception (owner, 2026-11-17, M35):
  a Sweeps table goes to the page whole up to *Most lines to draw* (Settings) and is filtered and drawn there;
  anything that turns a brush into a result (Keep, Exclude, groups, exports, counts) is resolved by the server on
  the whole table (`svcore/sweep/select.py`), never from the rows drawn.
- **No point is ever left out of a picture (owner, 2026-11-17).** Numbers (counts, statistics, conditions, exports)
  are always computed on all the data. What is drawn may be reduced only so that every point still counts: min/max
  per pixel (time plots), extreme-keeping thinning along a path (X-Y, 3D), or density per pixel with the sparse
  points drawn one by one (parallel plots, scatters). Never a random sample or a plain stride. Where a sample is
  unavoidable (or chosen in Settings) the screen says so. The "needle" e2e tests (`tests/e2e/test_needle.py`) put
  one extreme point / short spike into a big table or recording and check it is drawn in every view.
- The app works fully offline and listens only on 127.0.0.1.
- Formulas are evaluated with the AST whitelist in `svcore/formula.py` — never `eval`.
- English and Hebrew (RTL): every user-visible string goes through `frontend/src/i18n/` - one file per
  area (templates, flightlog, investigate, compare, mapsAnd3d, files, live, app, signals, plots,
  common, welcome, study; the Sweeps area's own in `sweeps/i18n.ts`), each with `en` and `he: typeof en` (tsc enforces both); `i18n/index.ts` merges them and
  holds `translate` / `useT`. A new key goes into its area's file. Check RTL layout of anything new.
- Light and dark themes: use the CSS variables in `index.css`, no hard-coded colours.
- Lazy-loaded heavy parts (Cesium 3D, map data) must stay out of the main bundle.

## After every change
- `python tools/quick_check.py` — tsc, oxlint (no NEW warning: `tools/lint_baseline.py`, CC18), Vitest, backend pytest,
  mypy in one go, stopping at the first failure (W11). Fixed some old warnings? `python tools/lint_baseline.py --update`.
- `cd backend && python -m pytest -q` — all green.
- `cd backend && mypy --config-file ../pyproject.toml app svcore signalviewer` — clean (T36; no per-module
  overrides since T36b - narrow the Optional, do not silence the module).
- `cd frontend && npx tsc -b` — no errors. `frontend/dist` and `site/` are not in git (FR10, owner 2026-11-16): `run.py`
  builds the UI from the sources when they changed, the release job builds it for the packages (`build.yml`), the docs
  workflow builds the site. Build the UI whenever you need it (`npm run build`); nothing of it is committed.
- `cd frontend && npm test` — the frontend's unit tests (Vitest, `src/**/*.test.ts`: store / undo, session
  migration, pairing, colours...) - all green; add one when you change frontend logic that has no screen.
- Add or update a test for any backend behaviour you change; e2e (`tests/e2e`, Playwright)
  for UI flows when possible.
- e2e while developing (owner, 2026-11-07): after each task run **only the e2e files relevant to the
  change** (the files / `-k` filters that touch what you changed - and when the change alters what is on
  screen by default, also the files of the views that lose or gain space). Run the **whole** suite
  (`python -m pytest -q tests/e2e`, ~30 min) **once, at the end of a round, before the version is updated** (owner,
  2026-11-14: the full checks take time - per task only the relevant tests; `tools/quick_check.py` before handing work
  over), and say in the Log which e2e ran. (Why the space rule: T08 - the
  Inspector starting closed - made the 3D view wider; a 3D test that clicked two fixed places on the
  globe broke and was only found three tasks later.) CI is unchanged: manual (`[ci]`), full run before a release.
- Update `CHANGELOG.md` (user-facing wording) and the task notes in `ROADMAP.md`.
- Keep `docs/dev/TASKS.md` current after EVERY task (owner's standing request): the progress
  board, the task's **Status**, the "Current state" lines and a Log line - so anyone can see what
  is done without asking.
- Keep commits small: one task (or one coherent part of it) per commit.

## Style
- Match the existing code: short comments that explain *why*, no dead code, no new
  dependencies without a reason written in the task notes.
- Error messages are for engineers in the field: say what happened and what to do.

## How to work here (practical notes)
- Setup: `pip install -r requirements.txt -r requirements-dev.txt`, `cd frontend && npm ci`. Run: `python run.py`
  (builds the UI by itself when its sources changed).
- Publishing (owner, 2026-11-17): only main remains. Show the owner the result first (on a branch if he wants to
  look), or push straight to main when he says so; no pull request unless he asks. **Owner, 2026-11-21: a session
  with push access pushes each finished task to main at once, then runs the checks that touch it and fixes forward
  (a new small commit, never a rewrite of main); the whole e2e suite once at the end of the round** (skill `sv-flow`).
  Commits are authored as the owner: `David Alpert <davidalpert11@gmail.com>`. A remote branch cannot be deleted
  from a cloud session - ask him. Without push access, patches (owner, 2026-10-19): ONE file with ALL commits since
  GitHub's main (`git fetch origin`, `git rebase origin/main`, `git format-patch --stdout origin/main..HEAD`),
  checked with `git am` on a fresh clone - never depending on an earlier patch.
- e2e: Playwright, one file per process (`for f in tests/e2e/test_*.py; do python -m pytest -q "$f"; done`); a
  Chromium of your own via `SV_CHROMIUM=/path/to/chrome`. Build the UI first and do not touch `frontend/src` while
  the suite runs (`run.py` would rebuild, longer than the fixture's 20 s wait: *Connection refused*). Tests reach
  the app through `window.__sv.state()` / `window.__sv.setState(...)` (`frontend/src/main.tsx`) and Sweeps through
  `window.__svSweeps` (`idle()`, `filter()`...). Wait for the END state, never "something changed"; allow seconds.
- CI (`.github/workflows/ci.yml`): every pull request, and a push to main only when asked (`[ci]` in the last
  commit message, or Run workflow). `build.yml` (tag / by hand) runs the backend tests on Linux, macOS and Windows:
  compare floats with a tolerance (`pytest.approx`, `np.allclose`), never `==`. Tests that compare byte lengths of a
  file they wrote: `write_bytes`, not `write_text` (Windows writes `\r\n`). `docs.yml` builds the site on every push
  that touches `docs/`, `mkdocs.yml`, `overrides/` (`mkdocs build --strict` must pass).
- Cloud sandbox: `grep -vi pywebview requirements.txt > r.txt && pip install -r r.txt`; Chromium at
  `/opt/pw-browsers/chromium` (`SV_CHROMIUM`); a background server started inside a tool call may die when the call
  ends (`setsid nohup ... &`); never `pkill -f <pattern>` in a command line that contains the pattern; a clean probe:
  `HOME=<tmp> python run.py ...` (no autosave); clean `/tmp/pytest-of-*` between big e2e runs (small disk).
- Pictures and films for the README and the docs come from the app itself: `python tools/make_readme_media.py
  [--only 44 45 ...]` (Playwright; the films need ffmpeg; the map scenes 05 28 31 44 46 need the internet; it does
  not make `06_3d_terrain.png`). The welcome cards' pictures: `--only examples`. Long films:
  `tools/make_demo_video.py`, `tools/make_training_video.py`; `tools/make_social_preview.py` after scene 31.

## Skills (`.claude/skills/`, loaded in a Claude Code session in this repository)
`sv-flow` (one task from the owner's words to main: plan, fast checks, push, verify, fix forward), `sv-patch` (one
patch for the owner when the session cannot push), `sv-checks` (the checks and which e2e files to run), `sv-ui` (a
control or a string: where it goes, Undo, en + he, RTL, themes, test hooks), `sv-messages` (byte streams, structures,
the guided Messages panel, links), `sv-release` (preparing a version, the owner's commands), `sv-report-part` (the
report's ready-made parts; LaTeX in `docs/dev/REPORTS.md`), `sv-media` (pictures and films), `sv-example` (a new example).
They are the practical steps; this file stays the rules. Keep them current when a procedure changes.

## Releasing (the owner tags; an agent prepares)
0. Run **ci** by hand first (Actions -> ci -> Run workflow, or `[ci]` in the last commit message).
1. Refresh the pictures (above) when the interface changed.
2. The version in `build.bat` (`VERSION`), `backend/app/version.py` (a test keeps the two equal), `CITATION.cff`
   (`version`, `date-released`; a test checks it), `installer/SignalViewer.iss` (`AppVersion`),
   `installer/version_info.txt` (four places). The workflow takes it from the tag.
3. CHANGELOG: rename the open section to `## X.Y.Z – date` with a highlights line. **README review before EVERY
   release (owner's rule):** check each CHANGELOG item against the README and the docs site - `docs/features.md`,
   `docs/limitations.md` (remove what was fixed, add what is new), `docs/install.md` (file names with the version,
   test counts), `docs/command-line.md`, the README's formats and highlights, its Hebrew section (short and
   structured, in line with the English; no `~` outside code - GitHub strikes text between two), the pictures.
4. Tag `vX.Y.Z` and push the tag - the build workflow builds the UI and every package (nothing built is committed).

## Starting a new session (the prompt)
Paste this, with the task in the last line:

> You are working on Signal Viewer (repo davidalpert11/signalviewer, branch main). Read CLAUDE.md and follow it,
> then `docs/dev/TASKS.md` (Current state, Open specs). The owner writes in Hebrew - answer him in Hebrew. Do not
> change the version unless he asks for a release. Work one task at a time; after each, run the checks and the
> relevant e2e, update CHANGELOG (user-facing), ROADMAP and TASKS, and commit small. Show him the result (a short
> summary in Hebrew of what changed and why, and how to see it) before anything is merged into main.
> Task: …
