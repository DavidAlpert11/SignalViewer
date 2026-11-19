# RE2 - the report area: ready reports made of ready-made parts (1.32.0; the rest phased)

The owner (2026-11-19, Hebrew, translated): *"An area where the report can be edited as a complete report editor:
import tables from outside (e.g. from Word) and external pictures. How to generate things automatically in the
report, for example: put in all the checks of commands vs. execution (cmd, desired, etc.); detect all the objects and
examine navigation errors between them - in position, velocity and angle; detect a trajectory and state transitions;
and create an automatic report that can fit anything. The automatic report must allow comparing files: when several
files are loaded it shows, in some smart way, the main differences between them - both the main signals that differ
and a focus on the central region of the change. Also other smart ideas of what this area needs and how we can help
make it automatic. And saving a template, etc."*

Status: **RE2.1 + RE2.2 + RE2.3 + RE2.4 + most of RE2.5 built in 1.32.0** (owner, 2026-11-19: "propose a nice idea and
build it; I liked that on the side you click a template and it is added to the report - templates with sub-templates
by category: all the commands vs execution, the navigation comparisons with the reference guessed and changeable,
comparisons when several files... a ready report made of parts that the user edits; decide the open questions;
prepare a new version, pictures, documentation; not only ArduPilot"; and "also code that makes a recording showing
every template: navigation, commands vs execution, the scenario, special moments, comparison to another file").

## 0. Decided (2026-11-19, the owner left the questions to the agent)

| # | Question | Decided | Why |
|---|---|---|---|
| 1 | Source of truth | Markdown stays; a part is a `[[name args \| options]]` line in it | old sessions open; diffs; one parser for the three outputs |
| 2 | Editor | The plain textarea stays this round; the block editor (§2.2 B) is RE2.6, later | the owner's ask was the parts library - built first |
| 3 | Where parts are made | The server writes each part as ordinary Markdown + plot items **in place of its marker before parsing** (`app/reportparts.py expand_all`) | the page, PDF and Word draw it with the code that draws everything; *Expand to text* later is the same Markdown |
| 4 | The library | The Report screen's *Insert* list starts with **Ready reports** (auto / control / navigation / compare, offered when they fit), the user's own report templates, then **Ready-made parts by category** (commanded vs actual · navigation, reference guessed + a select · the scenario · comparing files, baseline guessed + a select · what to look at) - built from `/api/report/parts` (scan) | the owner: "click a template on the side and it is added; sub-templates by category" |
| 5 | A ready report on a written report | Replaces a report nobody wrote yet; else goes in at the caret without its title | no dialog, nothing lost (Undo) |
| 6 | Pictures | In the session (`ws.report.assets`, downscaled to 2000 px, 5 MB each / 20 MB all), `![name](asset:<id>)`; a template carries the ones its text uses; PDF now draws pictures | one file travels |
| 7 | Paste | HTML (Word / web) and TSV (Excel) -> Markdown tables in the browser, merged cells repeated; Ctrl+Shift+V plain | no dependency |
| 8 | The comparison measure | RMS(d) / S, S = the baseline's 1st-99th percentile span; **overall** and **in its region** (the largest RMS in 1 % slices); region above 1/4 of the peak; first divergence = |d|/S above max(2 %, 5 x its median) for 0.2 % of the samples; levels same < 2 % < small < 10 % < large (by the larger of the two) | the owner's "mostly the same, a central region different" must stand out |
| 9 | Baseline / reference guess | Baseline: the file named ref / baseline / golden / nominal..., else the first; reference: truth, else receiver, else navigation; with several files and no `ref`, each file against its own | what an engineer would pick; always shown and changeable |
| 10 | My report templates | The app's settings (`sv.reportTemplates`), any session; a session template (library *Save*) also carries `report` (optional field) and brings it to a session with no report | the user's, not one session's |
| 11 | CLI batch with the written report (RE1.3's rest) | Not this round - the name resolver of `{{ }}` and `[[tab.plot]]` is in the browser; the parts themselves are server-side already | next |
| 12 | Demo | `examples/report_demo` (generic names, deterministic; `tools/make_report_demo.py`) | shows every part, not a flight log |

Built: `backend/svcore/reportparts.py` (pairs - the Python twin of desired.ts with shared cases
`backend/tests/data/setpoint_cases.json` -, tracking with steps, difference, region, timeline, path facts),
`backend/app/reportparts.py` (the parts, en / he, `scan`, `expand_all`, `WithExtra`), `/api/report/parts`,
`frontend/src/reportReady.ts` + `components/ReportParts.tsx` (the library), `reportPaste.ts`, `reportDoc.ts`
(`[[part]]`, `[[plot …]]`), `templates.ts` (`report`). Tests: `backend/tests/test_report_parts.py`,
`frontend/src/reportReady.test.ts`, `reportDoc.test.ts`, `desired.test.ts`, `tests/e2e/test_report_parts.py`.
Pictures 48 / 49 / 50. Open: RE2.6 (block editor), *Expand to text*, report checks before export, numbering / toc,
the CLI making the written report, Sweeps parts.

The proposal as first written follows (§0 above supersedes it where they differ).

## 1. What exists (studied 2026-11-19, main = 1.31.0)

The building blocks are almost all there, but each lives in its own panel. RE2 mostly **connects** them to the
report. Nothing below is rewritten.

| Need | What exists | Where | Gap for the report |
|---|---|---|---|
| Commanded / measured pairs | the one name detector (`des`, `cmd`, `target`, `setpoint`, `sp`, `dem`, PX4 `_setpoint` topics); *Plot the commanded / measured pairs*; dashed setpoint | `desired.ts actualNames / setpointPairs`, `store/actions/plots.ts:649` | TS only (the CLI cannot find pairs); no metrics per pair |
| Tracking metrics | step response (Wiener deconvolution) | `svcore/stepresp.py`, `/api/stepresp`, `StepChart` | no tracking error / delay / overshoot / settling / time out of tolerance per pair |
| Lag between two signals | cross-correlation | `svcore/firstchange.lag`, `investigate.lag_between` | reuse for the delay |
| Limits, pass / fail | `check_limits`, checks files, JUnit | `svcore/limits.py`, `app/checks.py`, `ChecksView.tsx` | not a report block |
| Tolerances | one rule for GUI and CLI (abs / pct / time / outside_pct, per signal) | `svcore/tolerances.py` | reuse as is for "pass" |
| Objects | detection by names (lat/lon, NED, ENU, ECEF; classes truth / nav / gps) - TS and Python agree | `objectDetect.ts` <-> `svcore/objects.py` + `object_names.json` | - |
| Navigation errors between objects | position / velocity / attitude errors + statistics, one maths for app, API, CLI | `svcore/objcompare.py`, `relate.py`, `/api/objects/compare`, `cli compare-objects` | not a report block |
| Similar families | nav1 / nav2, XKF1[0] / [1] | `similar.ts` <-> `svcore/similar.py`, `cli compare-similar` | - |
| States and phases | read-as-state, lanes, `transitions()`, `overview.phases` (the run's mode signal), flags (stuck, saturated, gap, spike) | `readAs.ts`, `svcore/analysis.transitions`, `svcore/overview.py` | no timeline table |
| Trajectory moments | takeoff / landing / highest / farthest / events, each a sentence | `svcore/story.py` (Story mode) | not in the document |
| Health / quality | flight-log health findings; data quality per signal | `svcore/health.py`, `svcore/quality.py` | not in the document |
| Many files | compare all signals vs a baseline: `worstRmsPct`, `minCorrelation`, `pass`, a 40-slice difference **profile** | `svcore/compare.py`, `/api/compare/all`, `ComparePanel` | ranking for a report, the "central region" |
| What changed first | first change, uninformative signals (constant, counter), clusters, lag chain | `svcore/firstchange.py`, `WhatChanged.tsx` | reuse for the first divergence |
| What differs in occurrences | effect size inside vs outside stretches | `svcore/occurrences.differ` | - |
| Parameters that differ | flight-log parameters across runs | `/api/runs/parameters/compare` | a strong "why" for a difference |
| Templates | slots + names, conditions, places, profile (glance, searches), generators quicklook / compare / objects | `templates.ts`, `svcore/templates.py`, `builtin_templates.json` | no document in a template (RE1.3) |
| Batch | `cli.py report --template`, `app/batch.py` | | makes the old plot report, not the document |
| The document | Markdown + `[[tab.plot]]` + `{{ max(Roll) }}`; names resolved **in the browser** (`formulaRefs.resolveFormula`) | `reportDoc.ts`, `ReportScreen.tsx`, `app/reportdoc.py`, `svcore/docfields.py` | resolution in TS only - the CLI cannot make a document |
| Pictures | `![alt](C:/path.png)` embedded at export | `reportdoc._img_src` | a path on one PC: lost when the session moves |
| Heavy work | `app.common.heavy` (2-4 at once), jobs with progress | `app/common.py`, `routes/jobs.py` | - |

**Two findings that shape the design:**
1. **Names are resolved in the browser** (`reportDoc.resolveValue` -> `resolveFormula`). A template run by the CLI
   has no browser. For the automatic report to run in batch (the owner's "save a template... re-run"), the
   resolution of `{{ }}` names and of the new blocks must also exist in Python. There is a precedent for this: L12
   ported `objectDetect` and `similar` to Python, with tests that check the two agree. The same pattern applies here.
2. **Pairs are detected in TS only** (`desired.ts`). The rules move to a JSON file read by both (as
   `object_names.json`) and get a Python twin, with a test that checks the two agree.

---

## 2. The editor

### 2.1 Source of truth: keep Markdown

The plain text stays the saved form (`ws.report.doc.text`). It diffs, travels in templates, is read by the CLI, and
old sessions keep opening. A WYSIWYG model (ProseMirror / Tiptap JSON) would make the text a second format, and
`[[...]]` / `{{...}}` / math round-trip badly through it.

### 2.2 The editing surface - options

| Option | RTL per paragraph | Offline / bundle | Effort | Risk |
|---|---|---|---|---|
| A. Today's textarea + preview | no (one direction for the whole box; mixed lines in bidi order) | 0 KB | - | the owner's "full editor" is not met |
| **B. Our own block editor over the same Markdown** (recommended) | **yes**: each block is its own auto-growing textarea with `dir="auto"` | 0 KB, no dependency | medium (~600 lines) | selecting across blocks: handled by "select blocks" mode, not free text selection |
| C. CodeMirror 6, lazy-loaded on the Report screen only | yes (`perLineTextDirection`) | ~150 KB gz, lazy, offline | small to wire, chips need widgets | a new dependency (CLAUDE.md asks for a reason); per-line direction, not per paragraph |
| D. WYSIWYG (Tiptap / ProseMirror) | yes | ~250 KB+ | large | Markdown round-trip loses our syntax; two formats |

**Recommended: B.** The document is split into blocks at blank lines, the same split the parser makes. Each block
is one of these:
- **text** (a paragraph, heading, list, quote): an auto-growing textarea with `dir="auto"`, so a Hebrew paragraph
  reads right to left while you type. A small rendered preview of the block appears beside it, or under it in narrow
  mode.
- **table**: edited as a grid (cells are inputs; Tab moves; + row / + column; paste cells from Excel), saved as a
  Markdown table. A "source" toggle shows the pipes.
- **live block** (`[[...]]`): a card that shows what it draws (a thumbnail of the plot / the first rows of the
  table), its options as a small form (window, table yes / no), *Expand to text* and *Refresh*. "Edit source"
  shows the raw `[[...]]`.
- **picture**: a card with the picture, its caption and its width.

The block list gives drag-to-reorder, an outline (headings), "insert here" between blocks, and a per-block menu
(move, duplicate, delete, convert). It also gives undo per pause, as today: one commit per pause, and a drag is
one commit. The whole-document source view stays one click away (today's textarea), so nothing is ever hidden.
The preview stays as today: the same page the export makes.

If the owner prefers a ready editor, C is the fallback. The reason to write down: per-line RTL and chips, lazy-loaded,
kept out of the main bundle.

### 2.3 Paste and import

All conversion happens in the browser with `DOMParser`, so no dependency is added.

| From | The clipboard has | Becomes |
|---|---|---|
| Word / web table | `text/html` with `<table>` | a Markdown table. Merged cells are repeated (rowspan) or left empty (colspan) and said once in a toast; line breaks in a cell become `<br>`; bold / italic kept; colours dropped. Text direction is kept as written: a Hebrew cell stays Hebrew, and the paragraph reads RTL by its first letter, as today |
| Excel / LibreOffice | `text/plain` TSV (+ html) | a Markdown table from the TSV (exact numbers, no Word formatting) |
| Word paragraphs | `text/html` | headings (h1-h3 / Word's "Heading" styles), bold, italic, lists, links -> Markdown; everything else plain text |
| A picture (screenshot, copied image) | `image/*` | a stored picture (2.4) + `![caption](asset:<id>)` |
| A file dropped / *Insert > Picture...* | png / jpg / gif / svg / webp | the same |
| *Insert > Word document...* (later) | a .docx | its headings, paragraphs, tables and pictures as Markdown + stored pictures (python-docx is already a dependency, in the backend) |
| A CSV file dropped | | a Markdown table (asks first when it has more than 50 rows: "a table of 50 rows, or a plot?") |

Paste with Shift (Ctrl+Shift+V) always pastes plain text.

### 2.4 Where pictures live

| Option | For | Against |
|---|---|---|
| A path, as today | nothing to store | broken on another PC, in a template, in autosave after a move |
| A folder beside the session (`flight12.svs.assets/`) | small session file | two things to copy; autosave and templates have no "beside" |
| **Inside the session / template, downscaled and capped** (recommended) | one file travels; works in autosave, templates, the CLI | the session file grows |

**Recommended:** `ws.report.assets?: { [id]: { name, mime, data /* base64 */, w, h } }` (optional, new, so old
files still open). The id is a content hash, so the same picture is stored once. On paste the picture is
downscaled to at most 2000 px on its long side and re-encoded (PNG, or JPEG at 85 for photos; in the browser,
through a canvas). Cap: 5 MB per picture after downscaling and 20 MB for all of them; above the cap the screen
says so and offers "link to the file instead" (today's path form, which keeps working). Unused assets are dropped
when the session is saved. A template carries the assets its document uses. Outputs: the page and Word embed them
(as today); PDF draws them.

---

## 3. Automatic sections

### 3.1 Live block or editable text? Both

- **Live block** `[[tracking]]`: recomputed on whatever is open. This is what a template and the CLI need, and the
  same document works on the next recording.
- **Expand to text** (on the block's card): replaces the block with ordinary Markdown that the user can edit. Its
  numbers become `{{ }}` values (still computed on all the data, so they are live), its plots `[[plot ...]]`
  (3.2), and its table rows a Markdown table whose cells are `{{ }}`. The words are the user's to change. It is
  one undo step, and it can be undone.

Default: insert as a live block. A section the user wants to comment on line by line gets expanded.

### 3.2 A plot defined in the document

Automatic sections need plots that are not in any tab. A new form, by signal names as in `{{ }}`:

    [[plot Roll, DesRoll | 10..60]]          one plot, two lines, a time window
    [[plot Roll, DesRoll | around 42.3]]     a window centred on a moment (the block chooses its width)
    [[plot xy Lat, Lon]]                     an X-Y / track plot
    [[plot Roll | files: all]]               the same signal in every open file (comparisons)

The plot is drawn by the same plot spec (`plotSpec`) as a tab's plot, so "no point left out" holds (min/max
levels). It is resolved by name: in a template it is rewritten to the slot, as `{{ }}` is.

### 3.3 The blocks

Each block: what it finds, what it computes (always on **all** the samples, in the backend, through
`app.common.heavy`), what it shows, and its options (after `|`). Every number has the time where it happened,
and in the HTML page a click on it moves the cursor there.

**`[[tracking]]` - commanded vs actual.**
- Finds every setpoint / measured pair in the open files (the `desired.ts` rules, now shared with Python), plus
  pairs the user added by hand (`[[tracking DesAlt -> Alt]]`).
- Computes per pair: tracking error e = measured - setpoint (angles wrapped, as `compare.angle_period` does):
  RMS, max |e| and when, bias (mean e); **delay** (`firstchange.lag`, cross-correlation); time outside the
  tolerance (% and the longest stretch) with the tolerance from the tolerances file (`svcore/tolerances`) or
  `| tol 2`. For **steps** in the setpoint (a change larger than 10 % of its range within 1 s, then held for at
  least 2 s), each step's overshoot %, rise time 10-90 %, settling time to 5 %, and steady-state error, plus the
  worst step. Optional `| step response`: `stepresp` for rate loops.
- Shows a table with one row per pair (pass / fail when a tolerance is given), sorted worst first, and a plot for
  each of the worst N pairs (the setpoint dashed, as on screen) with the worst moment marked. Options: `| top 5`,
  `| tol 2`, `| when="Auto"`, `| 10..60`.

**`[[objects]]` - objects and their navigation errors.**
- Finds the objects (`objectDetect` / `svcore/objects`). The reference is the object of class *truth*, else the
  one the user marked, else asked: `| ref GPS`.
- Computes `objcompare.compare` (the same numbers as *Compare objects...* and the CLI): position error N / E / D and
  horizontal / 3D, velocity error, attitude error roll / pitch / yaw (wrapped); per object RMS, max and when, p95,
  bias. Optional similar families (`similar.families`: nav1 / nav2).
- Shows a statistics table (object x quantity), the error plots over time for the worst object, a map picture of
  the tracks with the worst moment marked (`cli map` already draws one), and "the worst 3 moments" as sentences.

**`[[states]]` - trajectory and state transitions.**
- Finds the state signals: the run's mode / phase signal (`overview.phase_signal`), every signal read as a state
  (`readAs`), and the flight log's mode changes.
- Computes a timeline per state signal (`overview.phases`): each stretch's value, start, end and duration; where it
  was (the reference object's position at the start; the nearest *place* by name; the height); transition counts
  and a from -> to table; and the story's moments (`story.moments`: takeoff, landing, highest, farthest, the log's
  errors) on the same time line.
- Shows a timeline table, a lane picture (the states over time, as the lanes draw them), the track on the map
  coloured by state, and the moments as sentences. Options: `| signal Mode`, `| min 2s` (drop stretches shorter
  than 2 s, said).

**`[[differences]]` - several files (section 4).**

**`[[health]]` / `[[quality]]`** - the flight-log health findings and the data-quality summary, as tables with
their times. Small, and already computed.

**`[[summary]]` - what to look at (5).**

### 3.4 Where the code goes

`backend/svcore/autoreport/` holds pure functions over arrays, testable without a Store, the same way
`objcompare` is: `tracking.py`, `states.py`, `differences.py`, `summary.py`, plus `pairs.py` (the Python twin
of `desired.ts`, reading `setpoint_words.json`). `app/reportdoc.py` resolves the blocks: the app sends the block
text and the open runs; the server finds, computes and returns rows + plot specs. Results are cached per
(block text, run ids, file mtimes), so the preview does not recompute a block while the user types elsewhere.

---

## 4. Comparing several files: `[[differences]]`

**Baseline:** the golden run when one is marked (`judge.ts`), else the first file, else `| base <file>`. Each other
file is compared with it. With three or more files the ranking takes the worst file, and a signal x file table
shows them all.

**Alignment:** the Compare panel's own (time since start, the files' clocks, or the sync it suggested). The block
says which one it used.

**Which signals:** those in both files, by name (Compare's C13 rule: names that differ only by unit are the same
signal). Left out with a count: uninformative signals (`firstchange.uninformative`: constant, counter, time
itself), and signals with fewer than 10 samples in the overlap. Signals that exist in one file only are listed
apart. They are often the answer ("file B has no GPS2").

**The measure (robust, explained):** for each signal

- **D = RMS(other - base) / S**, where S = the baseline's 1st-to-99th percentile span (not the max-min range, which
  one spike would set). Angles are wrapped. D is "the typical difference as a share of how much the signal
  moves": 0.01 = 1 %, invisible on a plot; 0.2 = clearly different.
- plus **shape**: 1 - correlation (catches a delay or a sign error that a small D can hide);
- plus, for **state** signals: whether the sequences of states differ (edit distance between the sequences) and
  the time in each state.
- A signal's rank is D (shape breaks ties). Levels: same (D < 2 %), small (2-10 %), large (>= 10 %). The
  thresholds are options.

**Not drowning the reader:**
- Signals are grouped by family / message (`IMU.AccX/Y/Z` is one row, showing its worst axis), so the top list is
  not one sensor's three axes.
- **Top N** (default 6) groups get a plot each. The rest are in a closing table (signal, D, shape, the window,
  the files), and above it one line: "412 signals compared: 371 the same, 29 small, 12 large".
- A fast first pass: per-signal statistics (`compute_signal_stats`, cached) find signals that are identical
  (same samples, same mean / std / min / max), and those skip the alignment.

**The central region of the change:**
1. The difference profile of each top signal (`diff_profile`, normalised by S) on a common time axis.
2. **The largest-difference window:** the sliding window (default 10 % of the overlap, at least 2 s) where the sum
   over the top signals of the normalised |difference| is largest.
3. **The first divergence:** the first time where the difference of a top signal leaves its own early noise and
   stays out (the `first_change` rule applied to the difference signal, k x noise, persisting). The earliest such
   signal is named: "first to diverge: ATT.Roll at 41.8 s; the largest difference 44-52 s".
4. The plots of the top signals are drawn **zoomed on that window** (with a margin), with a small full-length strip
   above each where the window is shaded. `| full` draws them full length.

**Also, because they explain differences:**
- states that differ (mode sequence A: Auto -> RTL; B: Auto -> Land at 51 s);
- objects whose errors differ (the `[[objects]]` statistics of each file side by side);
- **parameters that differ** (`/api/runs/parameters/compare`): "PSC_POSXY_P 1.0 -> 1.4". This is often the cause,
  and it is listed first when a top signal belongs to the system the parameter tunes. That last link is by name
  prefix only, and the block says so.

The output is computed by the backend as a job with progress (many signals x files), and the page shows a "N of M
signals" bar while it runs.

---

## 5. The automatic report that fits anything

### 5.1 *Make a report for me* (a button on the Report screen; Ctrl+K)

A short dialog **built from what was found**, with nothing hidden. Each line is a checkbox with what it will add
and a count:

    Found in the open files                          will add
    [x] 3 files (flight12, flight13, flight14)       Differences vs flight12 (golden)
    [x] 14 commanded / measured pairs                Commanded vs actual, top 5 plotted
    [x] 3 objects (truth, EKF, GPS)                   Navigation errors vs truth
    [x] Mode signal (6 states, 23 changes)            States and trajectory
    [x] Health check: 2 warnings                     Health
    [ ] Data quality: 1 file with gaps               Quality
    [x] 4 findings, 2 notes                           Findings / Notes
    [x] Template "ArduPilot · Full review" (5 tabs)  its tabs as plot sections
    Title [Flight 12-14 review]   Language [Hebrew]   Detail ( ) short  (o) normal  ( ) full

What it writes: an ordinary document of live blocks, so the user can edit, delete and expand any part.

    # Flight 12-14 review
    [[summary]]
    ## Differences between the files
    [[differences | base flight12]]
    ## Commanded vs actual
    [[tracking | top 5]]
    ...
    ## Notes
    [[notes]]

Rules: a section with nothing found is not added and is listed in the dialog as "not found". *Short* = top 3 and
no appendix tables. *Full* = every pair and object plotted. The dialog is rules, not a prompt or an AI. The same
open files give the same report.

### 5.2 `[[summary]]` - what to look at

At the top: the 3-7 most important things the other blocks found, each one line with a pass / fail / warning mark,
its number, its time and a link to its section. For example: "Roll did not track its command during 44-52 s (max
error 11.2 deg at 47.1 s) - fail at tol 5"; "flight13 differs most from flight12 at 44-52 s, first in ATT.Roll";
"EKF position error 3D p95 2.1 m (max 6.3 m at 120.4 s)". The order is fails first, then the largest normalised
values. It is computed after the other blocks, from their results, so it adds nothing new to compute.

### 5.3 Templates and batch (RE1.3 folded in)

- **Save as template** (the template library's *Save*, now with "include the report"): the template gets
  `report?: { v: 1, text, options?, assets? }`, which is optional, so old templates still open. `{{ }}` and
  `[[plot ...]]` names are rewritten to the slot (`@<slot>/<name>`), and tab / plot references to the template's
  own tabs. Live blocks need no rewrite: they detect again on the new files.
- **Apply** (open the template on new recordings): the document comes with it; references to signals the new file
  does not have become red ⚠ ("RollDes is not in flight15"), never a wrong number.
- **Batch:** `cli.py report --template "Nav review" --out reports/ logs/*.bin` makes the **document** when the
  template has one (HTML / PDF / Word, `--format`). For this the Python side needs (1) the name resolver for
  `{{ }}` (`svcore/docrefs.py`, ported from `formulaRefs.resolveFormula`, with a test that checks both give the
  same ids for the same names), and (2) the blocks, which are already in Python (3.4). `--compare` gives
  `[[differences]]` over the listed files (the first, or `--base`, is the baseline).
- **Built-in templates:** the generators (quicklook, compare, objects) each get a default document, so *Quick look*
  also makes a sensible report.

---

## 6. More ideas, by priority

Must have (with the first phases):
1. **Report checks before export** - extending today's ⚠ count: broken references, empty blocks ("no pairs
   found"), missing pictures, values that are "-", a section heading with nothing under it, files of the report
   that are no longer open. One list, each with a click to the block.
2. **Every automatic number links to its moment** (in the app and the HTML page: a click moves the cursor / opens
   the tab).
3. **Outline + figure / table numbering + `[[toc]]`** (RE1.4's open part): captions "Figure 3", `ref("fig:roll")`.
   This is needed once automatic sections add many plots.

Should have:
4. **Confluence copy of the whole document** and **Markdown + pictures export** (RE1.5; CP1's functions).
5. **A company look for Word:** a reference .docx (styles, logo, header / footer) chosen once in Settings and
   used by python-docx. A sign-off table block `[[signoff]]` (name / role / date).
6. **Frozen versions:** *Freeze this report* saves the HTML with its date and the files' names into the session's
   versions list, so you can see what was sent last week. A version stores its output and is not recomputed.

Later:
7. Sweeps results as blocks (RE1.6).
8. Several documents per session ("flight report" and "one page for the manager"), as a list on the Report screen.
9. A side-by-side "difference of two report versions" (numbers that moved).

Not proposed: an AI writing the text. It is offline and has no model, and the owner asked for rules that fit
anything.

---

## 7. Phases (each its own commits, checks, e2e and CHANGELOG line)

| Phase | What | Done when |
|---|---|---|
| **RE2.1 Import** | paste HTML / TSV tables, Word paragraphs, pictures (paste, drop, *Insert > Picture*) stored in `ws.report.assets` with the cap; `asset:` in page, PDF and Word | a table copied from Word (with Hebrew, a merged cell) and from Excel arrives as the same Markdown table (Vitest on saved clipboard HTML); a pasted picture survives save -> reopen on a clean HOME and appears in HTML / PDF / Word (backend + e2e); an old session opens unchanged |
| **RE2.2 Commanded vs actual** | `setpoint_words.json` + `svcore/autoreport/pairs.py` (twin of `desired.ts`), `tracking.py`, `[[tracking]]`, `[[plot ...]]`, *Expand to text* | the pairs found in TS and Python agree on the examples' names (test); on a synthetic step with known overshoot / delay / settling the block gives them within tolerance (backend); a needle spike in the error is the reported max (needle test); expanding gives text whose values equal the block's |
| **RE2.3 Differences** | `differences.py`, `[[differences]]` as a job, the window, the zoomed plots | on two synthetic runs that differ only in one signal during 40-50 s, that signal ranks first, the window is 40-50 s +- 1 s, the first divergence is ~40 s; 1,000 signals x 3 files in < 30 s on the 4-core sandbox; identical signals skipped |
| **RE2.4 States and objects** | `states.py`, `[[states]]`, `[[objects]]` (objcompare) | the timeline equals the lane's stretches; the object block's numbers equal `cli compare-objects` on the same files |
| **RE2.5 The automatic report + template + CLI** | the dialog, `[[summary]]`, `report` in templates, `svcore/docrefs.py`, `cli report` makes the document | a template made from session A, applied to file B, gives B's numbers in the app and the same numbers from the CLI (backend + e2e) |
| **RE2.6 The block editor** | 2.2 B: per-paragraph RTL, table grid, cards, drag, outline | a mixed Hebrew / English document types correctly per paragraph (e2e with RTL); each block edit is one undo step; the source view round-trips byte for byte |
| RE2.7 Checks, numbering, toc, Confluence | section 6, items 1-4 | as each item says |

Order alternative: RE2.6 (the editor) first if the owner feels the textarea is the main pain. It is independent
of the blocks.

## 8. Risks

- **Too much on the page:** automatic sections can produce 40 plots. Mitigated by top-N, the levels, the summary,
  and "the rest in a table". The dialog's *Detail* sets the defaults.
- **False pairs / objects:** name rules guess. Every block lists what it found and why ("DesRoll -> Roll: prefix
  *Des*"), and a pair can be removed (`| skip DesYaw`) or added by hand.
- **Alignment of different files:** a wrong time alignment makes every signal "differ". The block checks for it:
  when most signals differ with a constant lag, it says "the files seem shifted by 2.3 s - align first?"
  (`compare.auto_shift`).
- **Speed:** differences over thousands of signals. Mitigated by the identical-signal fast path, `heavy`, a job
  with progress, and the cache. The UI gets only plot levels.
- **Two resolvers (TS and Python):** a test runs the same names through both, as L12 did.
- **Session size with pictures:** downscaling, the caps, and the "link instead" fallback.
- **The block editor** is the largest UI piece. It is phased last, so the blocks are useful first in the textarea.

## 9. Questions for the owner (Hebrew, as sent)

1. עורך: עורך-בלוקים משלנו (כל פסקה בכיוון שלה, טבלה כרשת, כרטיס לכל גרף, בלי ספרייה חדשה) - או CodeMirror (ספרייה מוכנה, ~150KB, נטענת רק במסך הדוח)?
2. תמונות: לשמור בתוך קובץ הסשן/התבנית (מוקטנות, עד ~20MB סה"כ) - מתאים, או שאתה מעדיף תיקייה ליד הסשן?
3. חלקים אוטומטיים: "בלוק חי" שמתעדכן לכל הקלטה + כפתור "הפוך לטקסט לעריכה" - מתאים?
4. פקודה מול ביצוע: אילו מדדים חשובים לך הכי הרבה (שגיאת עקיבה, השהיה, overshoot, זמן התייצבות, זמן מחוץ לסבולת)? יש לכם סבולות קבועות (קובץ) או לפי בדיקה?
5. אובייקטים: האם תמיד יש אובייקט "אמת" (truth) לייחוס? ואילו שגיאות - מיקום/מהירות/זווית בכל הצירים, או אופקי/אנכי בלבד?
6. השוואת קבצים: הקובץ הראשון/הזהוב כבסיס - נכון? כמה קבצים בדרך כלל (2? 10?) ובערך כמה סיגנלים בכל קובץ?
7. "האזור המרכזי של השינוי": חלון ההפרש הגדול + נקודת הסטייה הראשונה, עם הגרפים מוגדלים עליו - זה מה שהתכוונת?
8. דוח אוטומטי: חלון עם תיבות סימון לפי מה שנמצא (בלי AI) - מספיק? ושמירה כתבנית שרצה גם משורת הפקודה על תיקייה - חשוב כבר בשלב הראשון?
9. סדר: להתחיל ב-RE2.1 (הדבקת טבלאות ותמונות) + RE2.2 (פקודה מול ביצוע), או קודם השוואת קבצים (RE2.3)?
10. מהרעיונות הנוספים (בדיקת דוח לפני ייצוא, תוכן עניינים ומספור, תבנית Word של החברה, גרסאות מוקפאות, העתקה לקונפלואנס) - מה חשוב לך?
