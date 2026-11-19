# Reports - how they work, what was decided, what is open

The report is a document the user writes (RE1, 1.31.0) with ready-made parts the app writes for them (RE2, 1.32.0).
User docs: `docs/reports.md`. The full plans as first written are in git: `git show 4f514f27:docs/dev/REPORT_EDITOR.md`
(RE1) and `git show 4f514f27:docs/dev/REPORT_AUTO.md` (RE2, with the study of what existed and the 10 questions).

## How it works (read this before changing a report)

1. **The text** (`ws.report.doc.text`, Markdown) is the one source - saved in the session, in a template (`report`),
   in the user's report templates (prefs `sv.reportTemplates`) and parts (`sv.reportMyParts`). Pictures pasted into
   it are kept in `ws.report.assets` and written `![name](asset:<id>)`.
2. **The app resolves** what only it knows (`frontend/src/reportDoc.ts prepareDoc`): each `[[…]]` / `{…}` becomes a
   marker ⟦n⟧ and `items[n]` - `[[tab.plot]]` plot specs (`plotSpec.ts`, the one rule for every page),
   `[[plot A, B]]` plots from names, `{ max(Roll) }` a formula with signal ids (`formulaRefs.resolveFormula`),
   `[[notes]]`-like specials, and **parts** `[[tracking | tol 2]]` -> `{kind: "part", part, arg, opts, runs, mapBase}`.
3. **The server** (`backend/app/reportdoc.py resolve`): pictures `asset:` -> data URLs; **parts expanded first**
   (`app/reportparts.py expand_all`: each part writes Markdown + plot items in place of its marker; `[[summary]]`
   after the others from their highlights, `[[toc]]` last from the headings); then the CommonMark subset is parsed,
   values computed on every sample (`svcore/docfields.py`), plots' data made (`report.plot_data`; a part's computed
   series through `WithExtra`, nothing added to the Store); then **one of three emitters** - the live page
   (`build_doc_html`, also the preview), PDF (matplotlib, flowing pages), Word (python-docx).
4. **The parts' numbers** are pure functions in `backend/svcore/reportparts.py` (pairs - the Python twin of
   `desired.ts`, shared cases `backend/tests/data/setpoint_cases.json`; tracking with steps; difference / region;
   timeline; path facts) and existing modules (`objcompare`, `overview`, `quality`, `firstchange.lag`, `ops`).
5. **The library** beside the text: `/api/report/parts` (`scan`) -> `frontend/src/reportReady.ts` (categories,
   ready reports, the user's templates and parts) -> `components/ReportParts.tsx`. Paste / pictures:
   `reportPaste.ts`. The demo: `examples/report_demo` (`svcore/example_data/make_report_demo.py`), Help -> Examples.

**Adding a part:** see the `sv-report-part` skill (`.claude/skills/sv-report-part/SKILL.md`).

## RE1 decisions (2026-11-18)

| # | Question | Decided | Why |
|---|---|---|---|
| 1 | Where | A screen of the Recordings area: the rail's *Report* shows it in place of the plots | the report belongs to the session |
| 2 | One or several documents | One per session (`ws.report.doc`) | simple; several can come later as a list |
| 3 | The old panel | Removed; an old report opens as the document its form made (`reportDoc.defaultDocText`) | one way to make a report |
| 4 | Math | matplotlib mathtext (SVG in the page, PNG in Word, native in PDF) | no dependency, the same everywhere |
| 5 | Editor | A plain textarea + toolbar + Insert list + suggestions strip (no CodeMirror) | no dependency; enough for Markdown |
| 6 | Markdown parser | Our own CommonMark subset (`app/reportdoc.py`, ~250 lines, tested) | no dependency |
| 7 | A closed file | A red ⚠ with the reason (no stale value kept) | never a wrong number |
| 8 | Order | Templates / CLI batch with the written text: next round (RE1.3) | the editor first |
| 9 | Sweeps | Later (RE1.6) | |
| 10 | PDF | matplotlib, now flowing (headings, lists, tables, math, plots); Hebrew fixed (libraqm) | no dependency |

## RE2 decisions (2026-11-19)

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

Later (round 2, 2026-11-19, owner): the trajectory as a map (`mode: geo`, `app/mapimage.py`); a second value axis
titled with its lines' names, the right one in its colour (viewer.js, `report.draw_axes`); `[[toc]]`; My parts;
navigation errors one plot per axis, every object of every file a line, the noisiest underneath; `[[overview]]` - a
review of any recording (signals, rate, quality, statistics, plots), first in the automatic report.

## Open

- The command line makes the written report (`cli.py report --template`): the `{ }` / `[[tab.plot]]` resolver is
  in the browser only - port it to Python (as L12 ported objectDetect, with shared cases).
- RE2.6 a block editor (per-paragraph RTL while typing, a table grid, cards, drag, outline).
- RE2.7 *Expand to text* (a part -> its Markdown, editable); report checks before export; figure / table numbering;
  Copy for Confluence of the whole document; Markdown + images export; Sweeps results as parts / fields.
- One written report per session.
