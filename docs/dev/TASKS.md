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

- **2026-11-16 · PLAN_2026-11-17 (the owner approved it) - in progress.** Order R, S1, S2, E1, M1, M3, M2 (plan §6).
  R done: the unreleased 1.27.0 and 1.28.0 are one release, **1.27.0** (CHANGELOG merged under `1.27.0 – unreleased`,
  the version files at 1.27.0, the docs' "1.28" -> "1.27"; history not rewritten). The owner tags v1.27.0 once the
  round is stable. Next: S1 (formula: if / compare / text / bins).
- **2026-11-16 · Sweeps as one flow (PLAN_2026-11-16 §7a) - done.** Done: one stepper for every study (Data ·
  Columns · Goal · Results · Next runs; `sweeps/flow.ts`, `FlowNav.tsx`); the tables' column (Navigator) only in Data,
  resizable, a labelled *Remove from the study* with Undo; Next runs = the proposal + *Run from the app* (`NextStep.tsx`,
  `RunPanel.tsx` - the Run column is gone, *How to run* moved there from Set up); the systems together = a tab of
  Results. §7b file dialog done: New folder, Rename (F2), Delete (Del, to the recycle bin - `app/trash.py`, no new
  dependency), only in the user's own folders. The 404 on /api/object_track fixed (a map asked for a closed file's
  track). Stability round done: quick_check green; the whole e2e suite (4 workers, xdist) - 2 timing failures under
  load, both green alone (one wait made state-based); UI built. (Released as 1.27.0 - see R above.)
- **2026-11-16 · main is not stable (owner): Out of Memory, the 3D map's "Fragment shader failed to compile", slow
  maps.** Findings, numbers and plan: `docs/dev/PLAN_2026-11-16.md`. Found: every closed 3D map kept its WebGL
  context alive (Cesium's static index-buffer cache) up to 16 - fixed in `Globe3D.tsx` (contexts released, render
  error -> light mode -> flat map). Guard `tests/e2e/test_map_memory.py`; measuring `tools/measure_maps.py`,
  `tools/measure_e2e_memory.py`. Waiting for: the owner's numbers on Windows with a GPU (`measure_maps.py --gpu`);
  the e2e suite's memory; the whole suite before the tag.
- **1.28.0 is finished on `main`, not tagged** (the owner tags). Round 2026-11-15: polish before the tag –
  repository cleanup, code reliability, the films and the pictures (marketing).
- Done 2026-11-15 (see the Log): repository cleanup, history rewritten to the owner's identity, e2e speed-up and two
  outdated tests, Align time in the palette, the camera line fades, the offline 3D page's cameras, the pictures
  retaken, the training film remade.
- Open: a Hebrew version of the films and a narration script (offered); GitHub About texts (the owner pastes them);
  the full e2e suite before the tag.
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
- 2026-11-15 · Cleanup (c3e7391→20ed5b5 after the rewrite): agent prompts, lane notes, plans, mock-ups, unused clips 01-08 and
  images 34-37 removed; TASKS.md trimmed; lane markers out of code comments.
- 2026-11-15 · History rewritten (owner's request): every commit and tag by David Alpert <davidalpert11@gmail.com>, the
  Co-Authored-By / Claude-Session lines removed; file trees identical (checked per tag). main force-pushed; tags not
  (proxy) - the owner runs the script from the report.
- 2026-11-15 · e2e: tests/e2e/conftest.py - one Chromium per run, a context per test; big.csv / wide.csv made once. Full
  run 22.6 min (was ~30), 459 passed, 2 failed - test_less_clutter (expected map + 3D: one map since 1.28) and
  test_settings (an external session leaked into the next test) - both fixed and green.
- 2026-11-15 · Align time in the palette (e2e test_calm_screen +1); the camera line fades 5 s after a change (test_map_smooth,
  test_globe3d, test_live_report green); the offline 3D page: five cameras in the app's order, neutral selection
  (test_live_report, test_round_1112, test_map_export, test_scene3d green).
- 2026-11-15 · Pictures: the welcome cards (one map), 20-24 / 32-33 / 39-43 with new scenes, the README and gallery set,
  the social preview. Dead code removed (vulture): 4 functions, 1 parameter; quick_check green.
- 2026-11-15 · Training film remade (each demo once, real actions, the map loaded behind its slide, the 3D relief
  tilted; the recording reports a hardware renderer so the 3D view is drawn as with a graphics card).
- 2026-11-15 · The owner moved the 28 release tags onto the rewritten history from his computer and deleted the old
  branches (the session's proxy refuses tag and branch-delete pushes); checked here: every tag equals the rewrite, every
  commit and tag by David Alpert, only `main` left. GitHub's API counts one contributor (its sidebar is a cache).
- 2026-11-16 · Out of Memory / render error (PLAN_2026-11-16.md): measured v1.26.0, 08f7fbd and main, light and full
  mode, 20 openings each; fixed the leaked WebGL contexts (0 alive after closing, browser memory flat at ~1.23 GB
  instead of 2.05-2.2 GB), the render-error fallback, the W9 listener and the click handler. e2e: test_map_memory (new,
  3 green); the map files - see the next line.
- 2026-11-16 · Owner's GPU run (Windows): 0 contexts after closing, browser 240-280 MB, draw 1.4 s - the fix holds. The
  start page over open files (brand / Ctrl+K, Back); e2e test_welcome_cards + test_first_minute green (13).
- 2026-11-16 · Sweeps as one flow (§7a): FlowNav (five steps for a table and a study file), Navigator only in Data
  (resizable), NextStep (proposal + Run from the app), Together a tab of Results, Remove from the study (Undo). Saved
  files unchanged (a table's Next runs is its saved `view.center = "next"`, as before). Vitest flow.test.ts; e2e
  test_sweeps_workspace / flow / data_columns / charts / groups, test_study_common / loop / demo, test_welcome_cards,
  test_owner_notes_1_20, test_tour, test_error_details, test_release_1_21 - green (updated for the new places).
- 2026-11-16 · File dialog (§7b): New folder / Rename / Delete inline in the dialog; /api/fs/mkdir, rename, delete
  (to the recycle bin: Windows shell with undo, ~/.Trash, freedesktop trash - app/trash.py; send2trash not needed).
  Refused outside home / data drives, in hidden folders, on a drive or main folder itself, on a file open in the app.
  pytest test_fs_edit (7); e2e test_file_browser_edit (new, 2) + the file-dialog tests of test_features,
  test_first_minute, test_fresh_user, test_templates_recent_badfiles, test_user_reader - 45 green.
- 2026-11-16 · The 404 on /api/object_track (owner's GPU run): a map still on screen while its file closes asked for
  that file's track (the runs changed before the plot unmounted). `positionOpen` skips objects whose position is not
  in an open file (GeoChart, Globe3D). measure_maps --cycles 1: 6 console messages (the 404s) before, 0 after. Vitest
  mapObjects; e2e test_map_memory, test_map_objects, test_globe3d - 26 green.
- 2026-11-16 · Stability round: quick_check green (a radius token fixed). The whole e2e suite with pytest-xdist
  (`-n 4 --dist loadfile`, added to requirements-dev) under measure_e2e_memory: all green except two timing failures
  under the 4-worker load (test_flat_line_solo::test_comparison_lines_wear_their_object, test_round_1112::
  test_the_wow_in_the_3d_page) - both green alone; the 3D one now waits on the state, not 300 ms. Memory: pytest
  123 MB, servers peak 2.5 GB, browsers peak 7.0 GB (4 workers at once), back to 1.7 GB at the end - no steady
  climb. Lesson: warm the UI build first (`python run.py --build`) - after a UI edit each worker built it at once
  and the machine ran out of memory. frontend/dist rebuilt.
- 2026-11-16 · R (PLAN_2026-11-17 §1): 1.27.0 and 1.28.0 merged into one release 1.27.0 - CHANGELOG (one section, the
  highlights written once), build.bat, app/version.py, CITATION.cff, the installer's two files, docs' "(1.28)" -> 1.27.
  pytest test_crashlog (the versions equal) green; mkdocs build --strict green.
