# Work queue and handoff

This file is the **active work queue**: what is open, the current state and a short log, so any developer or agent
can pick up cold. `ROADMAP.md` is the catalogue (every task ID, ticked `[x]` when done) and `/CLAUDE.md` holds the
rules. The full history of the earlier rounds (plans, lane boards, the long log up to 1.28.0) was trimmed on
2026-11-15 and is in git: `git show 6477fd8:docs/dev/TASKS.md` (also the agent prompts, lane notes and mock-ups of
those rounds).

**Keep this file current.** After every finished task (or when you stop in the middle): update "Current state",
tick the task in `ROADMAP.md`, add the user-facing line to `CHANGELOG.md`, and add a line to the "Log".

---

## Current state

- **1.28.0 is finished on `main`, not tagged** (the owner tags). Round 2026-11-15: polish before the tag –
  repository cleanup, code reliability, the films and the pictures (marketing).
- Open (owner's list, 2026-11-15):
  - Films: a Hebrew version, a narration script, the training film's title (it is not ten minutes), fewer repeated
    examples, the map loaded before it is shown.
  - Pictures without a scene in `make_readme_media.py` (20–24, 32–33, 39–43): retake in the new look.
  - The offline 3D page (`backend/app/report_assets/scene3d.html`): the old camera names and amber buttons.
  - The map's camera help line always on (`.g3-cam-hint` / `.map-cam-line`): show it briefly.
  - The command palette has no *Align time*.
  - GitHub About (description, topics, social preview): the owner pastes the texts.
- Media made from the app itself (all in `tools/`): `make_readme_media.py` (pictures, the welcome cards'),
  `make_demo_video.py` (`docs/media/demo_simulation.mp4`), `make_training_video.py` (`docs/media/training.mp4`),
  `make_social_preview.py`, `make_bench_example.py`.

## Releasing

0. Run **ci** by hand first (Actions -> ci -> Run workflow, or `gh workflow run ci`; or put `[ci]` in
   the last commit's message): since 2026-11-01 a push to main runs it only when asked.
1. `python tools/make_readme_media.py` (needs Playwright) refreshes `docs/images` and the welcome cards' pictures
   (`frontend/public/examples`, `--only examples`) from the app itself; it does not make `06_3d_terrain.png`
   (headless, the 3D view runs on software WebGL) - keep or retake it by hand. The films: `tools/make_demo_video.py`
   and `tools/make_training_video.py` (need ffmpeg); `tools/make_social_preview.py` after scene 31.
2. Version in `build.bat` (`VERSION`), `backend/app/version.py` (a test keeps the two equal),
   `CITATION.cff` (`version` and `date-released`; a test checks the version),
   `installer/SignalViewer.iss` (`AppVersion`),
   `installer/version_info.txt` (four places); the workflow takes it from the tag, and a manual
   run (Actions -> build -> Run workflow) with the version left empty takes it from build.bat.
3. CHANGELOG: rename the open section to `## X.Y.Z – date` with a highlights line.
   **README review (owner's rule: before EVERY official release):** go through the CHANGELOG
   section and check each item against the README and the docs site (since Q73 the long parts
   live in `docs/`) - `docs/features.md` (a new or changed feature in its row; the test counts),
   `docs/limitations.md` (remove what was fixed, add what is new), `docs/install.md` (the file
   names with the version, the test commands), `docs/command-line.md`, the README's format list
   and highlights at the top, its Hebrew section (short and structured since Q74: install lines
   and what it does - no version history, the CHANGELOG has it; no `~` outside code, GitHub strikes
   text between two of them), and the pictures (step 1).
   `mkdocs build --strict` must pass (the docs workflow runs it on every push).
   Tests that compare byte lengths of a file they wrote: `write_bytes`, not `write_text` - on Windows
   `write_text` writes `\r\n` (the 1.18.0 tag failed there only).
4. `cd frontend && npm run build` and commit `frontend/dist`; tag `vX.Y.Z` and push the tag.

## How to work here (practical notes)

- **Patches to the owner (owner's rule, 2026-10-19):** every patch sent is ONE file with ALL the
  commits since what is on GitHub now (`git fetch origin` first; `git rebase origin/main` drops what
  the owner already applied; then `git format-patch --stdout origin/main..HEAD`), checked with
  `git am` on a fresh clone. The owner sometimes applies at once and sometimes later - a patch must
  never depend on an earlier patch having been applied.

- Setup: `pip install -r requirements.txt -r requirements-dev.txt`, `cd frontend && npm ci`.
- Run: `python run.py` (builds the UI once by itself when the sources changed, T17e).
- Checks after every change (CLAUDE.md): `cd backend && python -m pytest -q`;
  `cd frontend && npx tsc -b && npm run build`.
- e2e: Playwright, **one file per process**:
  `for f in tests/e2e/test_*.py; do python -m pytest -q "$f"; done`. A custom Chromium can be
  given with `SV_CHROMIUM=/path/to/chrome`. The full set takes several minutes; when time is
  short run the files / `-k` filters that touch what you changed, and say so in the log.
- CI: `.github/workflows/ci.yml` (T64) on every pull request, and on a push to main only when asked (`[ci]` in the last commit message, or Run workflow) - backend tests on
  Python 3.9 and 3.12, mypy, `validate`, tsc + build, and an e2e smoke run (test_fresh_user,
  test_workflows, test_file_help_menus) on the UI built from that commit; a few minutes. `build.yml`
  (tag / by hand) runs the backend tests on Linux, macOS and Windows: compare
  computed floats with a tolerance (`abs(x) < 1e-6`, `pytest.approx`, `np.allclose`), never `==` -
  the platforms' math libraries round differently (T17b's test failed on macOS / Windows at 1e-13).
  Waits in tests: wait for the END state (all the data in), not for "something changed", and allow
  for slow runners (seconds, not tenths).
- Tests reach the app state through `window.__sv.state()` / `window.__sv.setState(...)`
  (`frontend/src/main.tsx`).
- `frontend/dist` is committed. Patches between developers may leave it out (run.py rebuilds);
  rebuild and commit it before a release tag.
- **e2e: build first, then do not touch `frontend/src` while the suite runs.** `run.py` rebuilds the UI
  when the sources are newer than `frontend/dist`; the build takes longer than the fixture's 20 s wait
  for the server, so every file after an edit fails with *Connection refused* (2026-11-01).
- Sandbox gotchas seen so far: a background server or test run started inside a tool call may
  die when the call ends - start it with `setsid nohup ... &`. Never `pkill -f <pattern>` in the
  same shell command line that contains the pattern (it kills its own shell).

- Cloud sandbox: `pip install -r requirements.txt` without pywebview (`grep -vi pywebview requirements.txt > r.txt`),
  `pip install -r requirements-dev.txt`, `cd frontend && npm ci`. Chromium:
  `export SV_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` (the e2e files and media tools read it).
  Videos need Playwright's ffmpeg (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python -m playwright install ffmpeg`)
  plus the system `ffmpeg`. After a frontend change warm the UI build before e2e (`python run.py --port 8777
  --no-open --browser`, stop it after "running at"). A clean probe: `HOME=<tmp> python run.py ...` (no autosave).
  Clean `/tmp/pytest-of-*` between big e2e runs (small disk).

---

## Log

- Up to 2026-11-15: see `git show 6477fd8:docs/dev/TASKS.md`.
