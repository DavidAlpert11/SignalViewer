# Agent prompt – Signal Viewer, owner's round of 2026-11-13: a welcome that shows, the first minute with your own file, one gain set for many systems, smart sweeps on the farm, a calmer screen, a "wow" pass, and a release

> **This prompt is self-contained.** You have not seen the earlier conversations. Everything you need is here and in
> the repository files named below. Keep a copy in the repo as `docs/dev/AGENT_PROMPT_2026-11-13.md`.

> ## Status – read this first
>
> **Default: one session runs the whole round (`SESSION: ALL`, section A5).** The owner pastes this whole prompt into a
> session in Claude Code on the web; **the first line he sends says which session you are**: `SESSION: ALL` (the
> whole round, in sequence), or – only if he chooses the parallel way – `SESSION: W0`, `SESSION: L1` … `SESSION: L8`,
> `SESSION: FINAL` (section A4). **No line = `ALL`.**
>
> **Order:** W0 → L3 → L4 → L6 → L1 → L5 → L2 → L7 → L8 → FINAL. In `ALL` mode one session does them one after
> another; in the parallel way L1…L8 run at once between W0 and FINAL. Tests are written in every task and run once,
> in FINAL.
>
> **Base commit (main):** `950b0a9` · W0 commit on `sv1113/base`: `efa88b2` · mode: `SESSION: ALL` · release 1.27.0
>
> | Session | Tasks | Branch | State (not started / running / pushed / merged) | Note |
> |---|---|---|---|---|
> | W0 – plan, contracts, W11 fix | P0, contracts, W11 | `sv1113/base` | merged to main (owner) | backend 1226 passed; W11 runs are FINAL's |
> | L1 Welcome | W1, W2 | `sv1113/l1` | merged to main (owner) | W1 + W2; study-card pictures in FINAL |
> | L2 First minute | W3, W4, W6, W5, W13.5 | `sv1113/l2` | merged to main (owner) | W3–W6, W13.5; e2e in FINAL |
> | L3 Sweeps engine | W14 core, W15 core, CLI, drone example | `sv1113/l3` | merged to main (owner) | W14/W15 core, CLI, drone example; own pytest green |
> | L4 Farm + demo engine | W17, W18 engine | `sv1113/l4` | merged to main (owner) | launcher, demo engine, CLI; own pytest green; Portable not verified |
> | L5 Sweeps panel | W14, W15, W17, W18 UI | `sv1113/l5` | merged to main (owner) | panel + demo view; e2e in FINAL |
> | L6 Robustness + palette | W10, W8 | `sv1113/l6` | merged to main (owner) | W10 + W8; pywebview close: manual check |
> | L7 Plot polish + motion | W7, W9, W13.2/3/4/6/9 | `sv1113/l7` | merged to main (owner) | W7, W9, W13.2/4/6/9; W13.3 not shipped |
> | L8 Calm screen | W16 (its share), W13.7, W13.8 | `sv1113/l8` | merged to main (owner) | W16 counts 44→42, 118→116, 59→58, 14→12 |
> | FINAL – merge, all tests, W12, release prep | W12, all checks | `sv1113/release` | done (patch; push refused) | + the owner's notes after the round, on `sv1113/continue`; see docs/dev/lanes/final.md |
>
> Per-task state lives in each lane's file `docs/dev/lanes/<lane>.md` (task / state / verification / note). Only W0
> and FINAL edit this box – in `ALL` mode, the running session, after each lane.
>
> **Decisions already made by the owner (do not ask again):**
> - W5: build the setting *Click places the cursor*, **default OFF**. Nothing existing changes.
> - Release: you **prepare** it (version files, CHANGELOG, `frontend/dist` build, patch). You do **not** create or push
>   a tag, and never push to `main`. Pushing `sv1113/*` branches to `origin` is approved.
> - The optimisation setup lives in a **study file** the user builds in the app and saves; the API and the CLI read
>   the same file (W14, W15, W17, W18).
> - The farm is used through the owner's **existing launcher application** (W17); Signal Viewer is never installed on
>   compute nodes.
>
> **Revision 2 (2026-11-13), before W0 runs:** batch size defined in candidate values; `demo` / `demo-sim` in the CLI
> contract; per-lane blocks in every shared file, made by W0; who may edit e2e files and the Settings registry; what
> "the CI machine" means; the two new welcome cards stay hidden until FINAL merges; W0's priority order if time runs
> short.
>
> **Revision 3 (2026-11-13):** the whole round can run in one session, and that is now the default (`SESSION: ALL`,
> section A5). The parallel way stays available unchanged.
>
> **Version:** check `CHANGELOG.md`. If `## 1.26.0` is still unreleased (no tag `v1.26.0`), the release is 1.26.0;
> otherwise `1.27.0`. FINAL bumps the version files.

---

## 0. Run mode

**Finish your session's whole share without stopping and without asking.** The open decisions are above. If something
is genuinely ambiguous, take the most conservative reading, write it in your lane file, and continue.

**Checkpoints.** After each task: commit (identity in section A), one line in your lane file. At ~75 % of your
context (or when the tool warns you): finish the current task to a stable state (`npx tsc -b` clean, no half-edited
files – otherwise revert the half task and mark it `todo`), commit, `git push -u origin <your branch>`, write the next
step in your lane file, and end with the line the owner should paste to continue:
`SESSION: <lane> (continue from sv1113/<lane>)` – in `ALL` mode: `SESSION: ALL (continue from sv1113/<lane>)`.
A continuing session reads the Status box and its lane file first, not the whole Log.

---

## A. Who the owner is and how he wants the work done

- **The product.** Signal Viewer (`github.com/DavidAlpert11/SignalViewer`): a desktop app (local FastAPI backend in
  `backend/`, React + TypeScript UI in `frontend/`) for flight-test and simulation engineers. Fully offline. English
  and Hebrew.
- **The owner** applies patches himself and pushes to `main`. He reads Hebrew; write reports to him in Hebrew,
  plainly, outcome first. Code, comments, docs and commit messages stay in English.
- **Commit identity (binding).** The history was cleaned so only two identities appear. Every commit must use exactly:
  ```
  git -c user.name="David Alpert" -c user.email="davidalpert11@gmail.com" \
      commit --author="Claude <noreply@anthropic.com>" ...
  ```
  Author `Claude <noreply@anthropic.com>`, committer `David Alpert <davidalpert11@gmail.com>`. No other name or
  e-mail. Check with `git log --format='%an <%ae> | %cn <%ce>' <start>..HEAD | sort -u` before pushing.
- **Setup.**
  ```
  git clone https://github.com/DavidAlpert11/SignalViewer.git && cd SignalViewer
  pip install -r requirements.txt -r requirements-dev.txt
  cd frontend && npm ci && cd ..
  ```
  W0 starts from `main`; lanes start from `sv1113/base` (`git fetch origin sv1113/base && git checkout -b
  sv1113/<lane> origin/sv1113/base`). The history was rewritten on 2026-11-13; hashes in older prompts and in
  TASKS.md's Log no longer exist – do not look for them.
- **Read first:** `/CLAUDE.md` (binding rules: one way to do a thing, one place per control, en + he for every
  string, CSS variables only, sessions backward compatible, heavy work in the backend, always offline-capable, every
  workspace change through `commit` with Undo), `docs/dev/TASKS.md` ("Current state"), `docs/dev/PLAN_2026-11-13.md`
  (written by W0), and for L2/L7/L8 `docs/dev/UX_REVIEW_2026-11-11.md`. Do not rewrite the README.

## A2. Speed rules

- **Tests are written in every task and run in FINAL.** During a lane run only `npx tsc -b` after each task (seconds;
  a type error breaks the merge for everyone). Exceptions: **L3 and L4** may run **their own new** pytest files
  (seconds), because there correctness is the product.
- **Never run the whole e2e suite** (~9 min, the owner's).
- **Build `frontend/dist` once**, in FINAL.
- Every task lists in `docs/dev/E2E_MAP.md` (add lines only) the e2e files it wrote or whose selectors it changed,
  so FINAL runs exactly those.
- New tests wait on state (`expect(...).to_have_*`, a `data-*` attribute or a `__sv*` hook), never on `sleep`.
- Each lane writes its own **user docs** (guide pages en + he for its features) and its **CHANGELOG lines** (inside
  the `<!-- lane Lx -->` block W0 created), so FINAL only merges and edits wording.
- **"The CI machine"** in this prompt means the machine FINAL runs on. Every timing is recorded together with that
  machine's CPU count and the measured number. A lane does not tune thresholds on its own machine.

## A3. Quality rules (fast must not mean sloppy)

- **Honest verification.** Each task's lane file says **verified** (its checks ran and passed), **partially verified**
  (name what did not run and why) or **not verified**. Lane tasks are **not verified** until FINAL runs their tests.
  Never write that a check passed if it did not run.
- **`done` means "Done when" is fully met.** Otherwise **partial**, with what is missing. A workaround, a skipped
  test or a hard-coded value is not `done`.
- **Scope is fixed.** Build only what the tasks describe: no new features, no architecture changes, no refactors
  outside the files a task needs, no new dependencies unless a task requires one (say why). Above all for W13.
- **Look at it as a new user** – in FINAL, once, on the merged tree (section A4).

## A4. The execution plan – one parallel wave (already made; do not re-plan)

### Why this shape
Every task is assigned to exactly one lane by **area of the code**, so lanes edit different files and the merge is
mechanical. Anything that would make lanes wait for each other – shared types, routes, CLI commands, the study file,
motion tokens, i18n and CSS modules – is fixed **before** the wave, by W0, as a **contract**. Lanes build against the
contract, not against each other; there is no integration session.

### W0 – one session, as short as possible (target ≤ 60 minutes)
1. **P0 – `docs/dev/PLAN_2026-11-13.md`, one page:** per lane, the real files it owns (confirm or correct the "Owns"
   column below against the code); per task, the e2e files that cover it; risks this prompt did not know. If the
   code contradicts this prompt, the code wins – write the difference. **Split T49 and T50** (TASKS.md Q48, Q49) item
   by item to the lane that owns the item's file; the rest go to L8.
2. **Contracts** (types, stubs, fixtures – no real logic):
   - **Study file:** `docs/dev/study.schema.json` (JSON Schema, `version: 1`) covering W14, W15, W17 (`launcher`
     block) and W18 (`demo` block); Python dataclasses in `svcore` with load / save / defaults; TS types in the
     frontend. Loading is backward-compatible (unknown keys kept, missing keys defaulted).
   - **Routes** with their final request / response shapes, returning a fixture:
     `POST /api/sweeps/common` (W14 ranking), `POST /api/sweeps/next-runs` (W15 proposal),
     `POST /api/sweeps/launcher/submit` and `GET /api/sweeps/launcher/status` (W17),
     `POST /api/sweeps/demo/step` and `GET /api/sweeps/demo/progress` (W18).
     The response shapes are written as JSON fixtures in `tests/fixtures/sweeps/` **and** validated by one pytest, so
     L3/L4 must return exactly that shape and L5 can build against it.
   - **CLI skeleton:** `python -m signalviewer.study <next|rank|status|submit|wait|loop|demo> <study file>` and
     `python -m signalviewer.study demo-sim <params.json>`, with their arguments (at least `loop --max-rounds N`,
     `loop --local`) and exit codes (0 ok, 3 nothing left to propose, 4 some runs failed, 5 timed out), each command
     printing "not implemented". Meaning, fixed now so L4 does not invent it: `demo <study>` = `loop <study> --local`
     plus the gap to the full-grid optimum per round and the final sentence (W18); `demo-sim <params.json>` = one run
     of the demo simulator (W18), taking a parameters file, not a study file. The Portable's entry point routes the
     same arguments (find how the portable build is made).
   - **Fixture data:** three tiny hand-written drone tables + a study file + the expected ranking, in
     `tests/fixtures/drones/`.
   - **Per-lane modules, registered with one line each:** an i18n module per lane (`i18n/l1Welcome.ts`, …), a
     stylesheet per lane (`styles/l1.css`, …), an empty lane file `docs/dev/lanes/<lane>.md`.
   - **Per-lane blocks in every shared file.** Two branches that add lines at the same spot conflict in git even when
     both only add, so W0 puts an empty, marked block per lane (comment `--- lane Lx ---` / `<!-- lane Lx -->` in the
     file's own syntax, in lane order, one blank line between blocks) in: `EXAMPLE_SETS`, the Settings registry,
     `docs/dev/E2E_MAP.md`, `CHANGELOG.md` (under the unreleased version) and `ROADMAP.md` (Milestone 31). Only the
     lanes that can touch a file need a block there; when unsure, add it.
   - **`EXAMPLE_SETS` entries for `commonGains` and `smartSweepDemo`**, with their final file paths (tables, study
     file), in W0's own block. L3 and L4 create the files at those paths; L1 makes the cards. Because
     `/api/examples` returns only sets whose files exist, the two cards stay hidden on every lane branch until FINAL
     merges L3 and L4 – expected, not a bug; no lane creates placeholder data files to make them appear.
   - **e2e file owners:** in the plan, each e2e file has one owning lane (the lane that owns the feature it tests).
   - **W13.1 motion tokens** (`--motion-fast`, `--motion-base`, `--ease-out`, and their `prefers-reduced-motion`
     zeroes) in the global stylesheet, so every lane uses them.
   - **`data-tour` anchors:** a short list (open a file, signal tree, compare, command palette) with the attribute
     names fixed in the plan; the lane owning each element adds its attribute.
3. **W11** – the code fix of the two flaky e2e files (no runs now), `tools/quick_check.py`, `docs/dev/E2E_MAP.md`.
4. `npx tsc -b` and `cd backend && python -m pytest -q -x` once – the base must be green. Commit, push
   `sv1113/base`, fill in the Status box, report in Hebrew: **"open L1–L8 now"**.

**If W0 runs short of time or context,** the order is: the plan and every contract in step 2 (they block the wave),
then `docs/dev/E2E_MAP.md` (lanes add lines to it), then step 4. W11's flaky-test fix and `tools/quick_check.py` may
move to FINAL: write that in the plan and in the Status box, and FINAL does them first.

### The wave – eight sessions at once, each from `sv1113/base`

| Lane | Tasks, in order | Owns (may edit) | Must not edit |
|---|---|---|---|
| **L1 Welcome** | W1 → W2 (+ cards for `commonGains` and `smartSweepDemo`, with a neutral placeholder picture until FINAL runs the tool) | `Welcome.tsx`, `EXAMPLE_SETS` (its block only), `frontend/public/examples/`, the thumbnail tool, its i18n / CSS module | plot, Sweeps, settings |
| **L2 First minute** | W3 → W4 → W6 → W5 → W13.5 (empty states) + its T49/T50 share | empty plot, template strip, start card, status bar, the cursor setting | plot head, palette, Sweeps |
| **L3 Sweeps engine** (Python) | W14 core → `tools/make_drone_sweeps.py` → W15 core → CLI `rank / next / status` → routes filled in | `svcore` sweeps modules, the two sweeps routes, `examples/drones/`, its pytest files | any frontend file, launcher / demo modules |
| **L4 Farm + demo engine** (Python) | W17 → W18 engine → CLI `submit / wait / loop / demo` | `svcore` launcher / demo modules, their routes, `tools/launcher_mock.py`, `tools/hpc/`, `examples/smart_sweep_demo/`, the Portable entry point, its pytest files | any frontend file, W14/W15 core (calls them through the contract) |
| **L5 Sweeps panel** (UI) | W14 panel → W15 *Suggest next runs* + study editor → W17 *Send to launcher* + run states → W18 demo view | the new Sweeps panel and its components, its i18n / CSS module | backend (builds against the W0 fixtures) |
| **L6 Robustness + palette** | W10 → W8 + their T49/T50 share | workspace revision counter, close prompt, its setting, command palette | plot, Welcome, Sweeps |
| **L7 Plot polish + motion** | W7 → W9 → W13.2 / .3 / .4 / .6 / .9 + their T49/T50 share | plot head, cursor bar and readout, plot rendering, loaders, tab bar badge, flight-log rows, 3D labels, the performance test | empty plot (L2), palette (L6) |
| **L8 Calm screen** | W16 (the T49/T50 items left to it + the audit) → W13.7 focus / pressed states → W13.8 tour | panel headers and toolbars not owned above, the Settings component's layout (how entries are grouped and shown – it does not move, rename or reorder entries in the Settings registry, where L2 and L6 add theirs), button classes, the tour | anything another lane owns – a needed change there goes to its lane file as a request |

**Rules for every lane:**
- Work on `sv1113/<lane>`, commit per task, push at the end (and at a checkpoint).
- Edit only what you **own**. Shared files (`EXAMPLE_SETS`, the i18n and stylesheet indexes, the Settings registry,
  `E2E_MAP.md`, `CHANGELOG.md`, `ROADMAP.md`): **add lines only, inside the block W0 made for your lane**, never
  outside it, never reorder or reformat. Adding a `data-tour` / `data-testid` attribute to another lane's element is
  allowed.
- **e2e files owned by another lane:** when your change moves or renames one of **your** elements, you may change the
  selector lines that reach it in any e2e file – those lines only, nothing else in the file, never weaker
  assertions. Add a line in your `E2E_MAP.md` block: `<file> – selector change by Lx`. Anything more in another
  lane's e2e file is a Request. If two lanes changed the same line, FINAL keeps both changes.
- Need a change outside your area? Write it in your lane file under "Requests"; FINAL does it.
- End with a short Hebrew report: done, partial, not verified, requests.
- If pushing is refused in the sandbox: `git format-patch --binary origin/sv1113/base..HEAD --stdout >
  signalviewer-1113-<lane>.patch`, and say so.

### FINAL – one session, after all eight pushed
1. Create `sv1113/release` from `sv1113/base`; merge lanes in the order **L3 → L4 → L6 → L1 → L5 → L2 → L7 → L8**
   (fewest shared files first). On a conflict in a shared file keep both sides' added lines. `npx tsc -b` after each.
2. Do the lane files' **Requests**; replace any fixture still returned by a route with the real call.
3. **Run everything once:** `python tools/quick_check.py`, then the e2e files of `E2E_MAP.md` (and W11's two files
   10 times each), the W15 / W17 / W18 convergence tests. Fix failures – the code or the test, never by deleting or
   weakening a test. You may use sub-agents to fix failures in parallel by area.
4. Run the W2 thumbnail tool (all cards, including the two new ones).
5. **Look at it as a new user:** screenshots of every area the round changed (light / dark, en / he); look for broken
   layout, clipped Hebrew, wrong RTL, poor contrast, jumpy loading; fix.
6. **W12** – merge the lanes' CHANGELOG lines and guides, version files, single `frontend/dist` build, `python run.py`
   starts against it.
7. `git format-patch --binary <main base>..HEAD --stdout > signalviewer-1113.patch`, `git am` on a fresh clone,
   identity check, update the Status box and `docs/dev/TASKS.md`, push `sv1113/release`, final report (section F).

**If Playwright's browser cannot be installed in the sandbox** (network allowlist), FINAL marks every e2e and the
screenshots **not verified**, lists the exact files and screens, and the owner runs them locally. Do not work around
the block.

## A5. Single-session mode – `SESSION: ALL` (the default)

One session runs the whole round in the order of section A4's merge, so each lane builds on the real code of the
lanes before it. Everything in A4 still applies – the same tasks, the same ownership per lane, the same lane files,
the same rules for shared files – with these differences:

1. **Order:** W0 (all of it, including W11 and `tools/quick_check.py` – no deferring to FINAL) → **L3 → L4 → L6 → L1
   → L5 → L2 → L7 → L8** → FINAL.
2. **Stacked branches:** `sv1113/base` from `main`; each lane's branch is created from the **previous lane's tip**
   (`sv1113/l3` from `sv1113/base`, `sv1113/l4` from `sv1113/l3`, …, `sv1113/l8` from `sv1113/l7`), and
   `sv1113/release` from `sv1113/l8`. FINAL's step 1 is then a fast-forward, not a merge; FINAL still runs
   `npx tsc -b` once on the result. Push each branch when its lane ends.
3. **Real code instead of fixtures:** L5 builds on the real routes L3 and L4 already filled in; the W0 fixtures and
   their pytest stay as the contract test. A Request a later lane can do itself (because the owning lane is already
   finished, and the change is in its own area or a small one in the earlier lane's) it does, in its own commit, and
   notes it in both lane files; anything larger stays a Request for FINAL.
4. **Between lanes:** `npx tsc -b` clean, lane file complete, Status box updated (that lane: *pushed*), a two-line
   Hebrew progress note, then straight on to the next lane – **without waiting for the owner**.
5. **Context:** the whole round does not fit one context. At ~75 % use the checkpoint in section 0: finish the current
   task to a stable state, commit, push, write the next step in the Status box and the lane file, and end with
   `SESSION: ALL (continue from sv1113/<lane>)`. The owner opens a new session, pastes this prompt plus that line,
   and the new session continues from the Status box – it does not redo finished lanes.
6. **One final report** (section F) at the end of FINAL; the progress notes in between stay short.

### Kick-off lines for the owner
**The usual way – one session:**

| Step | Open | First line |
|---|---|---|
| 1 | one session | `SESSION: ALL` |
| it stopped at a checkpoint | a new session, same prompt | the line it printed: `SESSION: ALL (continue from sv1113/<lane>)` |

**The parallel way (faster in wall-clock time, more sessions):**

| Step | Open | First line |
|---|---|---|
| 1 | one session | `SESSION: W0` |
| 2 – after W0 says "open L1–L8 now" | eight sessions at once | `SESSION: L1` … `SESSION: L8` |
| 3 – after all eight pushed | one session | `SESSION: FINAL` |
| any session stopped early | one session | the line it printed: `SESSION: <lane> (continue from sv1113/<lane>)` |

If eight at once is more than the account allows, open them in two batches – **L3, L4, L5, L2** first (longest),
then **L1, L6, L7, L8** – nothing else changes.

---

## B. The owner's words (2026-11-13) and what each becomes

| He said | Task |
|---|---|
| "Pictures instead of the text on the examples' buttons." | W1, W2 |
| "More design ideas and improvements – what should be checked and improved?" | W3–W11 |
| "I want the app to be WOW." | W13 |
| "Choose one parameter set that works for N different tables, each with its own scenarios, constraints and optimisation – with an example the user can try." | W14 |
| "An API: give it a table or a set of tables, and it outputs the next set of runs to tune the optimisation." | W15 |
| "Maybe the app is too crowded? Simpler human engineering." | W16 |
| "A small Windows HPC farm; we already run it through a launcher app that takes the simulation exe and an XML (really JSON) parameters file. Add a mode that talks to that app." | W17 |
| "A light demo I can run on my PC: code with input and output, the app builds the next generation, I see it converge and see the benefit over running the whole grid." | W18 |

---

## C. Findings (read in the code on the base; nothing here was run)

- **The examples today** (`frontend/src/components/Welcome.tsx`, CSS `.examples-line` / `.ex-card` in `index.css`
  ~l.465): six cards in a `minmax(210px, 1fr)` grid, each an `Icon.*` (18 px) + title + one-line description. Sets are
  in `backend/app/routes/fs.py` `EXAMPLE_SETS` (`flight`, `twoFlights`, `car`, `ardupilot`, `simVsFlight`,
  `investigate`); `/api/examples` returns only sets whose files exist.
- **e2e depends on the cards' text**: `tests/e2e/test_compare_diff.py`, `test_compare_tolerances.py` click
  `.examples-line button` by `has_text`; `test_fresh_user.py` waits for `.examples-line`. Keep the title as real text
  inside the button.
- **Pictures already made by a tool**: `tools/make_readme_media.py` starts the app with an empty home, drives it with
  Playwright, writes `docs/images/*.png` (dark theme, 1600 × 900). Reuse its start-the-app code.
- **UX review 2026-11-11, "Proposed, not done"** – none of the ten items appears in CHANGELOG since. The status bar
  already says "every sample" (`allPoints`) when nothing is reduced; only the reduced case still reads "{n} points
  drawn for {total} samples" (`i18n/plots.ts` `shownPoints`, `StatusBar.tsx`).
- **Open in ROADMAP**: T49 duplicate and unclear controls (13 items, spec TASKS.md Q48), T50 small windows and
  crowded headers (Q49), *Ask before closing with unsaved changes* (P8 note), default theme / language of an exported
  page.
- **Flaky e2e**: `test_sweeps_flow.py` (fails 1–2 of 31 in ~3 of 5 runs) and
  `test_settings.py::test_line_defaults_and_apply_to_all` (assertion right after a state change with no wait).
- **Repository size**: pack ~230 MB for 371 commits; `frontend/dist` (~11 MB) is committed at every release,
  `docs/media` 27 MB, `docs/images` 16 MB, `examples` 10 MB. Owner decision (W12 writes a proposal; move nothing).

---

## D. Tasks

Each: **What**, **Done when**. Prefix W. Add Milestone 31 to ROADMAP for this round (L-lanes add their lines).

### W11. The two flaky e2e files + the quick-check tool (W0)
What: find the cause, not a longer timeout: wait on the state the assertion reads. Add `tools/quick_check.py`
(cross-platform; runs `tsc -b`, `vitest run`, backend `pytest -q -x`, `mypy`, stops at the first failure; one line in
CLAUDE.md's "After every change") and start `docs/dev/E2E_MAP.md`.
Done when (measured in FINAL): each file passes 10 of 10 runs; the Log says how it was measured.

### Group A – the welcome screen shows (L1)

**W1. Example cards with a picture.**
What: each card gets a thumbnail on top (16:9, card's full width, rounded top corners), title and one-line
description under it; the icon goes. Pictures in the folder the built UI serves offline (check `vite.config` and
`run.py`), e.g. `frontend/public/examples/<id>.webp`, ~480 × 270, each ≤ 40 kB. **Language-neutral**: crop to the
plot / map area only, no UI text. Both themes: `<id>.dark.webp` and `<id>.light.webp`, picked by the app's theme
variable. `alt` from i18n (en + he). A missing picture falls back to today's icon card. Responsive: 3 columns at
1440 px, 2 at 1280, 1 on a narrow window; RTL mirrored. Hover: existing amber border + slight lift of the picture
(motion tokens; off for reduced motion). Lazy-load; reserve the space (no layout jump).
Done when: the cards show pictures in light, dark, en, he, at 1280 × 720 and 1920 × 1080; the three e2e files above
pass unchanged; pictures are files, not inlined base64.

**W2. The pictures are made by the tool, not by hand.**
What: `tools/make_readme_media.py --only examples` (or a sibling reusing its start-the-app code – do not copy it)
opens each example set as a new user would, waits on a state hook for plots / map to settle, screenshots the plot
area at 2× and writes the WebP files. Map examples use the built-in offline basemap.
Done when: running the tool on a clean checkout remakes all the files close to the committed ones; the docstring
says when to run it (before a release, with the README pictures).

### Group B – the first minute with your own file (L2)

**W3. Suggestions inside the empty plot.** When the tab is empty, the template strip's chips (*Quick look* and the
views that fit) show inside the empty plot under its sentence; the side-panel strip appears only once something is
plotted. One place at a time (CLAUDE.md §3). Update the e2e references to `.tpl-strip` (~23). If the H6 commit ("the
start card offers Quick look when nothing fits") is in the base, remove the duplicate entry point.
Done when: a plain CSV with no template opens with the chips in the middle of the screen; Quick look works from
there; Undo returns to the empty plot.

**W4. The next step for this file.** The start card's second line names the next step: 2+ files → *Compare*; a
flight log with findings → *N findings*; a golden run exists → *Judge it*; otherwise nothing. One sentence, a link to
the panel. Shown once per session per reason.
Done when: each case shows its line in en and he; e2e covers one.

**W5. The cursor from the first click.** Setting *Click places the cursor*, **default OFF**. When ON: the first
click on a plot places the cursor; `Space` still toggles it. List in the lane file the e2e tests that would change if
the default were flipped (count + names).
Done when: works in both states, en + he, persisted in prefs, tests for both states, no existing e2e changes.

**W6. The status bar in the user's language.** Reduced case reads "Shown reduced (min–max) – zoom in for every
sample"; the numbers move to the tooltip. en + he.
Done when: both cases read as sentences; the trust information is one hover away.

### Group C – polish (L7, L6)

**W7 (L7). Two cursors: the floating bar gets a fixed place** – in the plot's head, right of the legend, while two
cursors are on; labels no longer collide with event texts.

**W8 (L6). Command palette, empty query:** recent commands first (last 5 in prefs), then groups with headers; keys
in the keys column; every row has an icon.

**W9 (L7). Small things:** the tab bar's badge reads "+8 views"; in flight logs the repeated group part of a row is
dimmed; the 3D view's labels declutter by priority – object name > mode > events, as the 2D timeline already does.

### Group D – robustness (L6)

**W10. Ask before closing with unsaved changes.** A workspace revision counter bumped by `commit`, the revision at
the last save / autosave-to-session; closing the window (pywebview) or the tab (`beforeunload`) with unsaved changes
asks *Save / Don't save / Cancel*. A setting turns it off. Autosave stays.
Done when: Vitest for the counter (commit bumps, undo / redo, save resets, UI-only state does not bump); e2e for the
browser prompt; the pywebview close path marked "needs manual check" if it cannot be run.

### Group W – the "wow" pass (split across lanes)

**W13. Premium, offline, fast.** Small, consistent, tasteful – not a redesign. Everything respects
`prefers-reduced-motion`, both themes, en + he / RTL, and CLAUDE.md.
1. **Motion tokens** (W0) – used by every transition this round touches.
2. **First plot draw-in** (L7): traces draw in left to right over ~400 ms, once per tab, never on zoom / pan / refresh,
   off for reduced motion and above a size threshold.
3. **Smooth zoom / pan easing** (L7) only if it keeps 60 fps on a 1M-sample signal, measured in FINAL on the CI
   machine. If 60 fps cannot be measured reliably there (headless browsers do not report real frame rates), do not
   ship it – note it.
4. **Skeleton loaders** (L7) instead of spinners for the signal tree and the plot while a file loads.
5. **Empty states** (L2): empty plot, empty tree, empty findings – one clear sentence plus one action (reuse W3's
   chips); no dead ends.
6. **Cursor readout** (L7): tabular numbers, aligned units, a subtle fade, no width jitter.
7. **Pressed / focus-visible states** (L8) on every button class (focus ring visible in both themes); consistent
   hover lift on cards.
8. **First-launch 30-second tour** (L8; skippable, once): 3–4 coach marks on the W0 `data-tour` anchors, en + he,
   stored in prefs, reachable again from the Help menu.
9. **Performance budget as a test** (L7): opening the largest bundled example plots in a sane time on the CI machine
   (L7 writes the test with a generous placeholder threshold; FINAL records the number and sets the threshold).
Done when: each item is shipped with a test, or skipped with a one-line reason.

### Group S – sweeps: one parameter set for many systems

**W14. Common parameters across sweeps** (engine L3, panel L5).

*The problem (the owner's example: several different drones that must fly with the same gains).*
Input: **N sweep tables** T₁…T_N (N ≥ 2). Each row is one run. Every column of every table has one role:

| Role | Meaning | Example |
|---|---|---|
| **Shared parameter (S)** | Exists in every table (after name mapping). **Its value is what we choose – one value for all tables.** | Kp, Ki, Kd |
| **Scenario (E_t)** | Table t only. The choice must work for every active value of it. | wind, mass, temperature |
| **Local choice (L_t)** – optional | Table t only. Each table picks its own best value for it. | a local filter |
| **Output (Y_t)** | Result of the run. Some outputs may be shared (after name mapping). | overshoot, settling time |

- **Name mapping:** similar names in different tables are paired to one name; the app proposes (normalised names,
  then similarity), the user confirms. Default roles: a column in all tables is shared, any other input is a
  scenario; the user can change any role.
- **Value matching:** exact by default; optional tolerance per shared parameter.
- **Per table t:** active scenarios (default all; values can be dropped), constraints C_t (boolean expressions over the
  row's columns, the app's existing expression syntax), an objective J_t (expression + min/max), aggregation over
  scenarios (default **worst case**, option **mean**).

*The computation,* for every candidate value s of S:
1. **Feasible in t** iff some local choice l makes **every** active scenario run (s, l, e) exist and satisfy C_t.
   A missing run = failure with the reason "not run".
2. **score_t(s)** = aggregation over scenarios of J_t for the best local choice l*_t(s).
3. **Feasible for all** iff feasible in every table; a value present in only some tables is listed as "not run in
   table k".
4. **Ranking:** a shared objective → minimise the worst table; different objectives → **Pareto front** over
   (score_1…score_N), optional weights on min-max-normalised scores.
- Only values that were run are chosen. No interpolation (that is W15's job).

*The output:* one ranked table – per value of S and per table: pass / fail, score, chosen local value, the deciding
(worst) scenario; for a rejected value: which table, scenario and constraint failed and by how much. Clicking a row
opens those runs in the plots. CSV export; the settings are the study file.

*Where:* backend (`svcore`, vectorised pandas group-by), the panel inside Sweeps, reached from one place; Pareto as a
scatter for 2 tables, parallel coordinates for 3+ (reuse an existing plot type if one fits). en + he.

*The example:* `tools/make_drone_sweeps.py` generates three tables from a small **closed-form toy model** of a drone
attitude loop (second-order plant; PID gains; formulas in the docstring):
- **Drone A – light quad:** wind 0/3/6/10 m/s; `overshoot < 8`; min settling time.
- **Drone B – heavy hexa:** mass 2/3.5/5 kg × wind 0/5 m/s; extra output `motor_sat`; `overshoot < 12 and
  motor_sat < 0.9`; min energy.
- **Drone C – VTOL:** columns `P_gain`, `I_gain`, `D_gain` (tests the mapping); local choice `filter_hz`;
  `phase_margin > 45`; min settling time; a few runs deliberately missing.
- ~6 × 5 × 5 gain values. Files in `examples/drones/` at the paths of the `commonGains` entry W0 put in `EXAMPLE_SETS`, so the
  card opens the tables **and** the filled-in panel with the answer visible.

*Done when:* pytest: a brute-force reference (plain loops) equals the vectorised result – feasible set, ranking,
Pareto front; `P_gain`↔`Kp` proposed; "not run" reported; dropping a scenario changes the feasible set as expected.
e2e: card → panel shows the known best value → click → runs open. 3 tables × 1 000 rows in < 1 s (record it).

**The study file – one definition of the whole optimisation (`<name>.svstudy.json`).** Built and saved in the panel;
the same file drives the panel, the API and the CLI. JSON, `version: 1`, schema `docs/dev/study.schema.json`. Holds:
- **Tables:** paths or globs per table (relative to the study file) – new result files in the folder are picked up on
  the next open; this is how results *accumulate*.
- **Mapping and roles**, tolerances; **per table:** active scenarios, constraints, objective, aggregation;
  **combining:** min-worst or Pareto, weights.
- **Search space for new runs:** per shared parameter – min, max, smallest step or allowed values, integer, log scale;
  constraints on S itself (e.g. `Kp * Ki < 3`).
- **Next-run settings:** batch size (default 20), **counted in candidate values of S** – each candidate expands to
  its runs in every table (scenarios × local values), so a batch of 20 is typically a few hundred runs; mix of reasons (refine / boundary / gaps, default 50 / 30 / 20 %);
  output folder per round (`next/round_<k>/`); output columns (default the table's own input columns + `run_id`,
  `reason`, `round`); CSV or XLSX.
- **`launcher` block** (W17) and **`demo` block** (W18).
- **History (written by the app):** each round – date, proposals, reasons, and per proposal *pending / submitted /
  done / failed / partly done*. Pending proposals are not proposed again.
Panel: *New / Open / Save study* (save through `commit`, with Undo); the study's state at the top (*12 pending runs
from round 3*). A session may reference a study file; it does not copy it.

**W15. Next runs to try** (engine L3, button L5).
What: given a study file, propose the **next batch** (batch size candidate values of S, each expanded to its runs) that most improves the choice, within the search
space. Deterministic and explainable – numpy / pandas only. Every proposed run is labelled with its reason:
1. **Refine:** around and between the best feasible values (halve the step locally).
2. **Boundary:** between neighbouring feasible and infeasible values, where the constraint margin changes sign.
3. **Gaps:** values run in some tables but not others.
For each proposed s, the runs for **each** table are s × that table's active scenarios (× local values). Every run
gets a **stable `run_id`** (short hash of study name + round + table + values).
Interfaces, one implementation: `next_runs(study) -> Proposal`; `POST /api/sweeps/next-runs`; CLI `study next`
(writes the round, updates history), `study rank`, `study status`; exit 3 = nothing left at the smallest step.
Panel: *Suggest next runs* – a table + the candidates on the ranking / Pareto view in a different marker, each with
its reason – and writes the round's files.
Done when: with the toy model as the simulator, a test loop through the CLI finds the brute-force optimum of a fine
grid within ≤ 4 rounds of 20 candidate values from a coarse grid; every row has a reason; proposals respect the search space and the
constraints on S; nothing pending is proposed twice; a study saved by the panel gives the same proposal in the CLI.

**W17. Run the loop on the farm through the owner's launcher – Launcher mode** (engine L4, button L5).
The owner's farm (Windows HPC) is driven by an **existing launcher application** that takes the simulation `.exe`
and a **parameters file** (XML in the simple case; JSON in his real setup – details not known yet). **Signal Viewer
does not replace it, does not talk to HPC Pack in this mode, and is never installed on compute nodes.** It runs in
one place (laptop with the Portable, or one management machine) and speaks the launcher's language:

```
study ──► parameter files in the launcher's format ──► the launcher (sim.exe + params) ──► the farm
  ▲                                                                                         │
  └──────────────── results read from where the runs already write them ◄──────────────────┘
```

Everything launcher-specific is in the study's **`launcher` block** – no launcher-specific code:
- **`params_template`** (per table allowed): a text template for one run's parameters file (XML, JSON, INI…).
  `{{name}}` takes a column value by the table's own column name; also `{{run_id}}`, `{{table}}`, `{{round}}`. Values
  are escaped for the format (XML for `.xml`, JSON rules for `.json`, raw otherwise). One small tested placeholder
  engine – no Jinja, no new dependency; an unknown placeholder is an error that names it.
- **`params_name`:** file name pattern, default `{{table}}/{{run_id}}.xml` (or `.json`).
- **`submit`:** the launcher's command line, with `{{round_dir}}`, `{{params_files}}` (a list file), `{{sim_exe}}`
  (per table), `{{run_id}}`; `submit_mode` per round or per run. Run as an argument list (no shell), cwd = the
  round folder, output to `round_<k>/submit.log`, exit code recorded.
- **`results`:** a glob with `{{run_id}}` / `{{table}}` (default `results/{{table}}/{{run_id}}*`), a format (CSV
  row, CSV time series reduced by expressions, JSON with a key path per output, or the app's loaders), and an
  optional **converter command** (gets the path, prints one CSV row). Found by `run_id`, else by input values;
  duplicates counted once and reported.
- **`status`:** done = result present; optional failure-marker glob; optional per-round timeout.
- **One result file per run**; the loader handles thousands of small files fast (measure 5 000, record it).
- **`local_workers`:** when set, the "launcher" is a local process pool of that size (default cores − 1) running the
  command per run on this PC – the same code path, used by W18 and for trying things without a farm.
Panel: *Send to launcher* (shows the exact command, asks once per session, runs it); per-run *submitted / done /
failed / missing*. CLI: `study submit`, `study wait` (exit 0 / 4 / 5), `study loop --max-rounds N` (next → submit →
wait → repeat until exit 3). `SignalViewer.exe study …` runs headless in the Portable (no Python needed); if the
Portable cannot be built in the sandbox, mark that **not verified** and document the build step.
`tools/launcher_mock.py` reads parameter files (XML or JSON), runs the toy model or a given `.exe`, writes results
where `results` says, fails on purpose with `--fail-rate`.
Safety: the command comes only from the study file the user saved (shown before the first run of a session, never
from a table or result); no shell; the backend is not exposed to the network.
*Direct HPC Pack example (lowest priority; skip and say so if time runs out):* `study next` can also write
`round_<k>/runs.csv` with `index` 1…N for a parametric sweep; `tools/hpc/run_one.ps1` and a `launcher` block whose
`submit` creates one HPC Pack job with a parametric task. **Not verified** (no cluster).
Done when: pytest covers the placeholder engine (XML / JSON escaping, unknown placeholder, per-table template), the
submit runner, result discovery by `run_id` and by values, failure markers, timeout, `local_workers`; the drone
example converges through the mock launcher with `study loop`; the guide has the owner's checklist: take one real
parameters file, replace values with `{{…}}`, set `submit` to the launcher's command line, run a round of 3, check
the results are found.

**W18. The smart-sweep demo – see it converge on your own PC** (engine L4, view L5, card L1).
Purpose: let a user see, in under a minute on an ordinary laptop, the loop of W15 + W17 working, and **what it saves
compared with running the whole grid**. Everything offline, nothing heavy.
- **The "simulation" is a real program with a real input and output**, so the demo shows the actual mechanism:
  `examples/smart_sweep_demo/sim.py` (stdlib only), also reachable as `SignalViewer.exe study demo-sim <params.json>`
  so the Portable needs no Python. It reads one JSON parameters file (written from the demo's `params_template`),
  computes the drone toy model for one run (~10 ms, plus an optional `sleep_ms` in the study to make the farm visible,
  default 30 ms), and writes one CSV result row named by `run_id`. A small seeded noise term (default on) shows that
  the method copes with noisy results.
- **The study** `examples/smart_sweep_demo/demo.svstudy.json`: the three drones of W14; a **coarse start grid**
  (e.g. 4 × 4 × 4 shared values × each drone's scenarios); a **fine search space** (e.g. 21 × 21 × 21); batch 20 candidate values;
  `launcher` block = the demo sim with `local_workers`; a `demo` block with the reference settings below.
- **The reference ("run everything"):** the full fine grid computed once in-process with the closed-form model
  (vectorised – the whole grid, ~10⁴ values × scenarios, in about a second), cached next to the study. It is used
  only to *measure*: never by the proposer.
- **The demo view** (in the Sweeps panel, opened by the `smartSweepDemo` welcome card):
  - buttons **Next round** and **Run until converged** (stops at exit 3, at convergence, or at a round limit) and
    **Reset**;
  - a live strip: round, runs done / running / failed (the local workers visibly fill and empty);
  - the shared-parameter space (2 of the 3 gains on the axes, the third as a slider or small multiples): tried values
    coloured by round, feasible vs infeasible, the current best, the true optimum of the full grid as a ring;
  - a **convergence chart**: x = runs executed, y = best objective found so far (worst drone), with a dashed line at
    the full-grid optimum and a marker where the full grid would finish (its run count);
  - a **one-sentence result**, computed, never hard-coded, e.g. *"Found the full-grid optimum within 0.5 % after 1 488
    runs – the full grid needs 9 261 × 12 = 111 132 runs (≈ 75× fewer)."* en + he. (Illustrative numbers: 64 coarse
    values + 3 rounds × 20, each × 12 runs.)
- **CLI equivalent:** `study demo examples/smart_sweep_demo/demo.svstudy.json` (= `study loop … --local` plus the
  demo's measurements, as fixed in the W0 contract) prints one line per round
  (round, runs, best, gap to the full-grid optimum) and the same final sentence – the same demo without the UI.
- **Guide (en + he), short:** what the demo shows, how to read the convergence chart, how to swap `sim.py` for your
  own program (same input / output contract), and that the same study runs on the farm by changing the `launcher`
  block (W17).
Done when: from a clean checkout, the card opens the demo and *Run until converged* reaches the full-grid optimum
(within the tolerance in the `demo` block) in ≤ 60 s on the CI machine with the default settings, and the sentence
reports a saving of at least 10× (record the actual numbers); the CLI gives the same rounds as the panel
(determinism); pytest checks the sim's input / output contract, the reference grid, and the convergence metric;
e2e: open the card → *Next round* twice → the convergence chart has two points and the run counter is right.

### Group H – a calmer screen (all lanes, audit by L8)

**W16. Fewer things on screen, one place for each.**
What: carry out ROADMAP **T49** (13 duplicate and unclear controls, spec TASKS.md Q48) and **T50** (small windows and
crowded headers, spec Q49) exactly as specified – each item by the lane W0 assigned it to. L8 does the rest and the
audit: on four screens (welcome, one plotted tab, Sweeps, Settings) count the controls visible without opening
anything, before (on the base) and after (FINAL re-counts on the merged tree). Rules: one primary action per area;
rarely used controls go behind the existing *More* menu (no new pattern); nothing removed without a way to reach it
(command palette at least); labels say what happens.
Done when: T49 and T50 are ticked; the count drops on all four screens; a list of every moved control and where it
is now; e2e for moved controls updated by selector, not by weakening the assertion.

### Group E – docs and release prep (FINAL)

**W12.**
- CHANGELOG from the lanes' lines, in user wording, grouped: Welcome / First minute / Sweeps and the farm / Polish /
  Safety / Wow.
- Guides en + he from the lanes, checked for consistency: W1, W3–W6, W10, W13 (tour, motion), W14, W15, W16, W17,
  W18.
- ROADMAP Milestone 31 ticked; `docs/dev/TASKS.md` current; `docs/gallery.md` with the new welcome screen and the
  demo's convergence view.
- **Release prep:** version files bumped, `frontend/dist` built **once**, `python run.py` starts against it. No tag.
- A short **proposal for the repository's size** in TASKS.md (no change made): measure what `frontend/dist`,
  `docs/media`, `docs/images`, `examples` add to the history (`git rev-list --objects --all | git cat-file
  --batch-check`); compare (a) building `frontend/dist` in the release workflow, (b) Git LFS for media, (c) docs media
  on `gh-pages` only – for each, what breaks (offline `pip install`, the Portable, `run.py`'s rebuild) and the clone
  size.

---

## E. Checks (FINAL, once, on the merged tree)

- `python tools/quick_check.py` (tsc, vitest, backend pytest, mypy) – all green; any environment-only failure noted
  with its cause.
- `cd frontend && npm run build` – clean (the single build).
- e2e: exactly the files in `docs/dev/E2E_MAP.md`, plus W11's two files 10 times each. Never the whole suite.
- The W15, W17 and W18 convergence tests.
- `git log --format='%an <%ae> | %cn <%ce>' <main base>..HEAD | sort -u` prints exactly one line:
  `Claude <noreply@anthropic.com> | David Alpert <davidalpert11@gmail.com>`.
- `git am` of the final patch on a fresh clone succeeds.

## F. Report to the owner (Hebrew)

Outcome first. A table of every task with its state and verification; a separate list of everything **not verified**
or **partial** and what the owner should check by hand (at least: e2e if the browser was blocked, the Portable's CLI,
the pywebview close prompt, the real launcher). What waits for him: tagging and pushing the release, the
repository-size proposal, the optional flip of W5's default. The demo's measured numbers (runs, time, saving).
Screenshots of the new welcome screen and the demo, light and dark.
