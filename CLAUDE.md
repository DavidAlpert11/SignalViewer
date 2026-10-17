# Working on Signal Viewer — rules for every change

You are working on Signal Viewer: a local, offline desktop app (Python FastAPI backend +
React/TypeScript frontend, shown in a pywebview window or a browser) for analysing time
signals. Primary users: **flight-test and drone engineers** (ArduPilot .bin, MAVLink .tlog,
PX4 .ulg, CSV) and **simulation engineers** (MATLAB/Simulink .mat and Python pipelines).

The work queue is `docs/dev/TASKS.md` (what to do next, in order, with full specs, current
state and a log - written so another developer or agent can take over). `docs/dev/ROADMAP.md`
is the catalogue of every task. Work one task at a time; when its "Done when" is met, tick it in
ROADMAP.md and update TASKS.md (current state, the task's status, the log). Update TASKS.md also
when you stop in the middle of a task.

## Before changing anything
1. Read the code you are about to change **and every caller of it** (`grep` the symbol across
   `backend/` and `frontend/src/`). Write down, in the task's notes, what else it touches.
2. Prefer extending an existing mechanism over adding a parallel one (one way to do a thing).
   Check `store.ts` actions, `api.ts`, `files.ts`, `svcore/*` first. Backend endpoints live in
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
- Heavy work stays in the backend; the UI receives decimated data only.
- The app works fully offline and listens only on 127.0.0.1.
- Formulas are evaluated with the AST whitelist in `svcore/formula.py` — never `eval`.
- English and Hebrew (RTL): every user-visible string goes through `i18n.ts`
  (`he` is typed as `typeof en`, so tsc enforces both). Check RTL layout of anything new.
- Light and dark themes: use the CSS variables in `index.css`, no hard-coded colours.
- Lazy-loaded heavy parts (Cesium 3D, map data) must stay out of the main bundle.

## After every change
- `cd backend && python -m pytest -q` — all green.
- `cd frontend && npx tsc -b && npm run build` — no errors (the build updates `frontend/dist`).
- Add or update a test for any backend behaviour you change; e2e (`tests/e2e`, Playwright)
  for UI flows when possible.
- A change to what is on screen by default (a panel open / closed, a new toolbar control, a
  toast) changes the space other views get: run **every** e2e file, one file per process
  (`for f in tests/e2e/test_*.py; do python -m pytest -q "$f"; done`), not only the ones that
  look related. (T08 - the Inspector starting closed - made the 3D view wider; a 3D test that
  clicked two fixed places on the globe broke and was only found three tasks later.)
- Update `CHANGELOG.md` (user-facing wording) and the task notes in `ROADMAP.md`.
- Keep commits small: one task (or one coherent part of it) per commit.

## Style
- Match the existing code: short comments that explain *why*, no dead code, no new
  dependencies without a reason written in the task notes.
- Error messages are for engineers in the field: say what happened and what to do.
