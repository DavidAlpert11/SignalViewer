# Prompt – polish before the 1.28.0 release (films, pictures, small fixes)

Give this file to a new agent session on a clone of this repository: *"Read `docs/dev/AGENT_PROMPT_2026-11-15.md` and do it."*

## 1. Who you work for, and how

- The owner is **David Alpert**. He writes and reads **Hebrew**: every report to him is in Hebrew, plain, the outcome
  first. Code, comments, documentation and commit messages stay in **English**.
- He gave **push rights to `main`**: commit with `git -c user.name="David Alpert" -c user.email="davidalpert11@gmail.com"`
  (or `git config` once per clone), `--author="Claude <noreply@anthropic.com>"`, one coherent change per commit, then
  `git fetch origin main && git rebase origin/main && git push origin HEAD:main`. Never force-push. Tags and GitHub
  releases are **his** – never create them.
- **Ask before** anything outward-facing that is not a push to `main` (GitHub settings, releases, deleting files he made).
- Before you stop, everything is committed and pushed (a hook checks the working tree).

## 2. What Signal Viewer is (owner-approved positioning)

A local, offline **engineering data analysis & validation workbench** for any time-series data: flight, vehicle and
bench tests, simulation output (MATLAB .mat, Python), ROS 2 (.mcap), CAN + DBC, CSV, Parquet, HDF5, ArduPilot .bin,
MAVLink .tlog, PX4 .ulg. Python FastAPI backend (`backend/`) + React/TypeScript UI (`frontend/`), shown in pywebview or a
browser, English and Hebrew (RTL), light and dark. **ArduPilot logs are convenient sample data, not the product's
identity** – generic chrome; domain content only in profiles / templates.

The workflow it serves: Import → Explore → Visualize → Compare → Investigate → Validate → Report.
Three pillars (README): compare and understand · investigate and validate · reproduce and report. Plus Sweeps
(parameter studies up to a million runs, a loop that runs the user's simulation) and the Fleet.

## 3. Where things stand (2026-11-15)

- **1.28.0 is finished on `main`, not tagged** (the owner tags when he is happy). The redesign round of 2026-11-14 is
  done: five lanes (L1 look, L2 Sweeps, L3 plots and frame, L4 map, L5 analysis) and the Final lane – see
  `docs/dev/TASKS.md` (lane board at the top of "Current state", the Log at the bottom), `docs/dev/PLAN_2026-11-14.md`
  (the approved plan; §8 the owner's decisions), `CHANGELOG.md` (1.28.0 by theme).
- Checks at the release state: full e2e 460 / 461 (the one: a 3D click under load, since made robust), quick_check
  (tsc, Vitest 247, pytest 1347, mypy) green, `mkdocs build --strict` green, `test_perf_budget` green, the 1M-run
  Sweeps measure 1.8–1.9 s. After that: one-map flight templates (owner's request) with their e2e green.
- Media made from the app itself (all scripts in `tools/`):
  - `make_readme_media.py` – `docs/images/00…31`, `38_welcome_cards`, the welcome cards' pictures
    (`frontend/public/examples`, `--only examples`), the README clips `docs/media/0x_*.mp4/.gif` (`--only vid`).
    `--only 00 05` etc. picks scenes. Map scenes need the internet (OpenStreetMap tiles).
  - `make_demo_video.py` – `docs/media/demo_simulation.mp4` (87 s): a .mat model vs its flight, Align time finds the
    offset, Compare's verdict, the worst moment, three smart-sweep rounds, one gain set for three drones.
  - `make_training_video.py` – `docs/media/training.mp4` (3 min 23 s): a slide per chapter then the app live, nine
    chapters, captions + a click ring. Reuses `make_demo_video.Film` / `cut_and_encode` / `fresh`.
  - `make_social_preview.py` – `docs/images/social-preview.png` (from scene 31).
  - `make_bench_example.py` – `examples/bench/pump_run_07.parquet` (the test-bench example, with `checks.json`).

## 4. The owner's next wishes (start here – ask him which first if unclear)

He wants to keep working on the **films** and **polish a few things** before releasing. Known open items:

1. **Films:** the captions are in English – he may want a Hebrew version (the app has a full Hebrew UI: set
   `language: 'he'` via `window.__sv.setState`); pacing, music-free; maybe a narrated voice-over script (text he can
   record). GitHub does not play repo MP4s inline: offer the drag-into-README upload route (he does it himself).
2. **Pictures without a scene** in `make_readme_media.py`: `20–24` (sim vs flight), `32–37` (live / report pages, from
   `make_live_report_media.py`), `39–43` (smart-sweep demo, common gains, all runs, report, what changed) – old look;
   the README no longer uses them except `42_report_process`. Add scenes or drop the files no page links to (grep
   `docs/` first).
3. **The offline 3D page** (`backend/app/report_assets/scene3d.html` / `relation.js`, picture `36_map_wow`) still shows
   the old camera names (General / On the object / Chase / Cockpit) and amber buttons – M6 renamed the app's cameras
   (Free · From above · Around it · Behind it · Cockpit); make the page match.
4. **The map's camera help line** (`.g3-cam-hint` / `.map-cam-line`) is always on and covers part of the map – consider
   showing it briefly on a camera change or on hover (a UI change: e2e `test_map_smooth`, `test_globe3d`).
5. **Command palette** has no *Align time* command (it is only in a file's right-click menu) – add one (CLAUDE.md
   allows the palette as the second entry point).
6. **GitHub About** (description, topics, social preview) – the session cannot change repo settings; the texts to
   paste are in the last report of 2026-11-15 (also: README's opening paragraph).
7. `test_globe3d.py::test_primary_secondary_in_3d` – flaky under heavy load only (now retries its click).

## 5. Rules (binding – `CLAUDE.md` has the full list and overrides this file)

- One way to do a thing; a control in exactly one place (palette and shortcuts are the only second entries).
- Every workspace change through `commit` (Undo); UI-only state separate. Saved files backward compatible (new fields
  optional; never rename a saved field). Offline; 127.0.0.1 only; formulas only via the AST whitelist; no new
  dependencies without a written reason.
- Every user-visible string in `frontend/src/i18n/` (en + he); CSS tokens only (a test forbids literal colours).
- Engineering correctness over polish; never claim a test passed that did not run; never weaken an e2e assertion.
- Tests per change: only the relevant ones (`tsc`, the Vitest / pytest files touched, the e2e files of
  `docs/dev/E2E_MAP.md`); `python tools/quick_check.py` before pushing; the whole e2e suite only before the owner tags.
- `npm run build` (the committed `frontend/dist`) after frontend changes, in its own commit, at the end of a batch.
- Keep `docs/dev/TASKS.md` (Current state + a Log line), `CHANGELOG.md` (user-facing, under 1.28.0 while untagged)
  and `ROADMAP.md` current.

## 6. Sandbox quirks (cloud container)

- Setup: `pip install -r requirements.txt` without pywebview (`grep -vi pywebview requirements.txt > /tmp/r.txt`),
  `pip install -r requirements-dev.txt`, `cd frontend && npm ci`.
- Chromium: `export SV_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` (the e2e files and media tools
  read it). Videos need Playwright's own ffmpeg build: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python -m playwright
  install ffmpeg` (plus the system `ffmpeg` for encoding).
- After a frontend change the app rebuilds the UI on start (~1 min): warm it before e2e with
  `python run.py --port 8777 --no-open --browser` (stop it after "running at"), or the first e2e times out.
- For a clean probe of the app use an empty home: `HOME=<tmp> python run.py --port <p> --no-open --browser` (else the
  autosave restores the last session and the welcome screen does not show).
- Clean `/tmp/pytest-of-*` between big e2e runs (small disk).
- The account's usage limit is shared by every session: prefer one session working in order over many in parallel;
  commit and push after each task so a stop loses nothing.

## 7. Report

In Hebrew, outcome first: what changed (with the picture / film paths), what ran and passed, what did not run, and what
the owner must do himself (tag, GitHub settings, Windows-only checks: the Portable, the pywebview window, 3D speed on a
real graphics card).
