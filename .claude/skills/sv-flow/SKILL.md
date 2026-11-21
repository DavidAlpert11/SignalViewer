---
name: sv-flow
description: The loop for one Signal Viewer task from the owner's words to main - read the queue, find every caller, build, run only the checks the change touches, commit small, push at once (a session with push access), verify after the push and fix forward; the whole suite once at the end of the round. Use at the start of every task; for a session without push access finish with sv-patch.
---

# One task, start to main (Signal Viewer)

The rules are in `/CLAUDE.md`; this is the order to do them in, fast. The owner's rule (2026-11-21): **a session with
push access pushes each finished task to main at once, then checks and fixes forward** - only the checks the change
touches while working, the whole suite once at the end of the round. A session without push access ends with one
patch (skill `sv-patch`).

## 0. Start (2 min)

```bash
git fetch origin && git status -sb               # on main, clean, up to date (git pull --rebase origin main)
git config user.name "David Alpert" && git config user.email davidalpert11@gmail.com
```
Read `docs/dev/TASKS.md` (Current state, Open specs) and the task's lines in `ROADMAP.md`. The owner writes in
Hebrew: answer in Hebrew; code, commits and docs in English. A spec marked "waiting for the owner" is not built.

## 1. Before writing (the 10 minutes that save an hour)

- `grep -rn "<symbol>" backend frontend/src tests` for **every** symbol you will change - callers, tests, docs.
- Find the existing mechanism first: `store.ts` actions, `api.ts`, `files.ts`, `svcore/*`, `app/routes/<area>.py`.
  One way to do a thing (CLAUDE.md "Before changing anything").
- Where a control goes: skill `sv-ui`. A report part: `sv-report-part`. Messages / links: `sv-messages`.
- Write the plan in 3-6 lines into the task's Status in TASKS.md (what, where, what else it touches).

## 2. Build in small steps, each one checked

Fast checks while working (seconds, not minutes) - only what the change touches:

| Changed | Fast check |
|---|---|
| a `backend/svcore` / `backend/app` module | `cd backend && python -m pytest -q tests/test_<area>*.py -x` (grep the module name in `backend/tests`) |
| typing of Python | `cd backend && mypy --config-file ../pyproject.toml app svcore signalviewer` (~40 s) |
| `frontend/src` | `cd frontend && npx tsc -b` (~30 s); a logic file with a `*.test.ts`: `npx vitest run src/<file>.test.ts` |
| strings | both `en` and `he` in the area's `i18n/*.ts` (tsc enforces it) |
| a UI flow | the e2e files of that area (skill `sv-checks` §3), after `npm run build` |

Never run the whole e2e suite per task (~30 min).

## 3. Close the task (the same commit)

- A test for the behaviour (backend pytest; e2e for a UI flow when possible).
- `CHANGELOG.md` `## Next – unreleased`: one user-facing line. `ROADMAP.md`: tick / notes. `TASKS.md`: Current
  state row, Status, a Log line (date, what, which checks ran).
- `python tools/quick_check.py` (tsc, Vitest, pytest, mypy - ~4 min; start it in the background, read the log).
- Commit small: one task, or one coherent part of it. The message says what and why, in English.

## 4. Push, then verify (owner, 2026-11-21)

```bash
git pull --rebase origin main && git push origin HEAD:main
```
Then, while the next task starts: the relevant e2e files (`sv-checks` §3) on the pushed commit. A failure is fixed
**forward** in a new small commit (never a force-push, never a rewrite of main); say it in the TASKS log. CI runs only
when asked: `[ci]` in the last commit message of the round.

## 5. End of the round

The whole e2e suite one file at a time (`sv-checks` §4), `mkdocs build --strict` when docs changed, fixes forward,
then a short summary to the owner in Hebrew: what changed, why, how to see it, what is left open.

## Without push access

Commit locally exactly as above, then skill `sv-patch`: ONE file with all the commits since origin/main, checked with
`git am` on a fresh clone, sent to the owner with the commands to apply it.
