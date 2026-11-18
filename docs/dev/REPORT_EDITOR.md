# RE1 - the report as a document you write (plan, waiting for the owner)

The owner (2026-11-18, Hebrew): *"a screen or a whole area where a report can be edited in an orderly way, like
markdown or LaTeX; and from there you can always refer to variable values, plots from a tab, a whole tab, etc."*

Status: **plan only - no code until the owner answers the questions at the end.** Task ids RE1.1 ... RE1.6 below.

---

## 1. What exists today (studied 2026-11-18, 1.30.0)

| Part | Where | What it does | What RE1 does with it |
|---|---|---|---|
| Report panel | `components/ReportPanel.tsx` (side panel, rail button *Report*, Ctrl+K *Report*) | A form: title, intro, summary, language, theme, scope (this tab / all tabs), *include the investigation*, Compare's verdict, a checkbox + caption per plot; Preview, HTML (the one live page), PDF, Word | **Absorbed**: its form becomes the *default document* (2.3); the side panel goes away - one way to make a report |
| `ReportMeta` | `store/model.ts`, saved as `ws.report` | title, intro, summary, lang, theme, scope, investigation, verdict, includeVerdict | Kept, read as before; one new optional field `doc` (2.4). Nothing renamed or repurposed |
| Per-plot `excludeFromReport`, `caption` | `Plot` | which plots the panel's report takes, and their caption | Read by the default document only (`tab()` field honours them) |
| Generated sections | `reportProcess.ts processSection`, `investigation.ts investigationSections`, `meta.verdict` | the process in brief, findings / steps / conditions, Compare's verdict | Become fields: `{{ process() }}`, `{{ investigation() }}`, `{{ verdict() }}` |
| What a page may draw | `plotSpec.ts pagePlot / pagePlots / plotSpec` | one rule for report, replay, clip; the server request for one plot | Reused as is by the `plot()` / `tab()` fields - **the only way a plot goes out** |
| Builders | `backend/app/report.py`: `plot_data` (full-resolution statistics, min/max levels, `full` = every sample), `_stats_table`, `_notes_html`, `_sections_html`, `build_html` (uPlot page, replay / story), `build_pdf` (matplotlib pages, `_bidi`), `build_docx` (python-docx, RTL paragraphs), `build_plot_html`, `build_image` | three emitters of one request (`tabs` + `sections` + `notes` + text) | Kept as the emitters' building blocks; a document becomes an ordered list of the same blocks (3.2) |
| Copy for Confluence (CP1) | `clip.ts`, `build_clip_page / _macro / _static`, `/api/export/clip` | the page with every sample as an attachment + the macro's lines; a static picture + table + notes | The document gets the same copy (RE1.5), by the same three functions |
| Preview | `components/ReportPreview.tsx` | the HTML report in a sandboxed iframe (dialog) | Replaced by the live preview pane (4) |
| Jobs | `/api/jobs` kind `report` (`routes/jobs.py`) | long exports with progress, atomic write | Same job, the body carries the document |
| Batch reports | `app/batch.py`, `cli.py report --template ... logs/*.bin`, `signalviewer.report()` | one report per file from a template, same builders | A template that carries a document makes that document for every file (RE1.4) - this is "re-run on a new recording" |
| Sessions | `/api/session/restore` keeps the **original run ids**; *Open session with new files* (`RetargetDialog`, `neededNames`) keeps ids too | a saved layout stays valid | A document's `"<runId>/<name>"` references survive both; `neededNames` must also walk the document |
| Templates | `templates.ts` capture / apply, `svcore/templates.py`; signals by **slot + name**; conditions and places travel by name | | The document travels in the template with slot references (RE1.4) |
| Statistics | `svcore/ops.compute_signal_stats` (time-weighted mean / RMS / std, NaN-safe, cached, range or mask), `check_limits`, `/api/stats/window`, glance stats (`min max mean first final range`), Runs-matrix measures | | The `stat()` field calls `compute_signal_stats` on **all** the data, in the backend |
| Conditions | `ws.conditions` (id, name, text, exit, minDur, mergeGap, combine), `store.evaluate_condition`, `occurrence_rows` | stretches where an expression holds | `when=cond(...)` masks a statistic; `{{ cond(...) }}` prints its result |
| Formulas | `svcore/formula.py` (AST whitelist), `formulaRefs.ts` (`{Speed}`, `{file:RPM}`, `param("X")`), derived signals `derived/<name>` | | A field may compute on a formula; the field language itself is parsed by an AST whitelist, never `eval` |
| Areas | `areas.ts` (Recordings, Sweeps), `App.tsx` AREA_VIEWS, TopBar | an area = a whole activity with its own state slice, never in `ws` | Decides where the editor lives (2.1) |
| i18n / RTL | report words in `i18n/live.ts`; `STRINGS` in report.py; `_bidi` (PDF), `rtlize` (Word), `dir` on the page | | Per paragraph direction (5.4) |

What it touches besides itself (for the task notes): `ReportPanel.tsx` (removed), `ReportPreview.tsx` (replaced),
`rail.ts` + `App.tsx` (the Report button opens the screen), `CommandPalette.tsx` (entries), `PlotView.tsx` ⋯ menu and
`TopBar.tsx` tab menu (*Add to report*), `RetargetDialog.neededNames`, `templates.ts` capture / apply,
`svcore/templates.py`, `app/batch.py`, `signalviewer.report()`, `routes/jobs.py`, `app/report.py`, `study.schema.json`
(not touched - the study is Sweeps'), the docs (`docs/features.md`, `docs/limitations.md`, a new `docs/reports.md` page).

---

## 2. Decisions proposed

### 2.1 Where it lives - **a screen of the Recordings area** (recommended)

| Option | For | Against |
|---|---|---|
| A. Keep the side panel, add a big text box | small change | no room for source + preview; the owner asked for "a screen or a whole area" |
| **B. A full screen inside Recordings** (the stage becomes *editor \| preview* when Report is chosen) | the document **belongs to the session** (it points at its tabs, plots, notes, conditions); saved, undone and carried by templates with it - no new state outside `ws`; the rail, Ctrl+K, the cursors, the files stay where they are; one click back to the plots | the plots are not on screen while writing (answered by the insert library, 3.3, and *Add to report* from the plots) |
| C. A third top-level area "Reports" beside Recordings and Sweeps | looks like the owner's words "a whole area" | `areas.ts` rule 3: an area's state never goes into `ws`, yet the document must refer to `ws` and travel with sessions / templates; two places for one session's work; switching areas hides the files' context |

**Recommended: B.** The rail's *Report* button (and Ctrl+K *Report*, and Ctrl+Shift+R - free today) switches the
stage from the plot grid to the report screen; the same button, Esc in the outline, or a click on a plot tab goes back.
The side panel `ReportPanel` is removed: its settings (language, theme) move to the screen's own head row; its plot
checkboxes and captions become the default document's fields (2.3). The plots keep their ⋯ *Add to report* (one
entry point, beside *Copy for Confluence*), which inserts a field at the editor's caret (or the end).

Sweeps keeps its own report (its tables live outside the session). The document cites Sweeps results through a field
made **in Sweeps** (RE1.6), not a second Sweeps report.

### 2.2 The document model - **Markdown (CommonMark) + three small extensions** (recommended)

| | Markdown | LaTeX-like | Block editor (Notion-like) |
|---|---|---|---|
| Engineers know it | yes (README, Confluence, Jira, GitHub) | some; heavy for text | yes, but its file is JSON, not readable |
| Hebrew + English + math mixed | plain text, direction per paragraph | `\begin{RTL}`... - hard | good |
| Diff / review / copy into a mail | plain text | plain text | no |
| Dependencies | a small parser | a real TeX is out of the question offline | a big editor framework |
| Same source in session, template, CLI | yes | yes | yes (JSON) |

**Recommended: Markdown** - CommonMark + GFM tables, with exactly these extensions:

1. **Fields** `{{ ... }}` - a live value / plot / table (section 3). Chosen because `{...}` already means a signal in
   formulas and `{{ }}` is what Jinja, Confluence and Mustache users read as "filled in".
2. **Math** `$...$` inline, `$$...$$` display - the LaTeX math everyone writes.
3. **Callouts** `> [!NOTE]` / `> [!WARNING]` / `> [!FINDING]` (GitHub's syntax) - findings and limits stand out.
   Plus a page break line `\newpage` (LaTeX's word, ignored by HTML, honoured by PDF / Word).

Nothing else (no raw HTML - it is escaped: the page stays safe and the PDF / Word emitters can draw everything).

**Parser:** one parser, in the backend (Python), because PDF, Word, the CLI batch and the values all live there:
`markdown-it-py` (MIT, pure Python, CommonMark-compliant, used by Jupyter / MyST, ~150 kB) with its `dollarmath`
plugin from `mdit-py-plugins` (MIT). New dependencies - the reason (for the task notes): a correct CommonMark
parser is ~2,000 lines to write and test; these are small, pure Python, offline and maintained. Alternative if the
owner refuses new dependencies: a subset parser of our own (headings, paragraphs, lists, tables, emphasis, code,
quotes, links) - ~400 lines, documented as "Markdown subset". The frontend does not parse Markdown: the outline
(headings) and the field autocomplete need only line-level patterns.

**Math rendering:** recommended **matplotlib mathtext** (already a dependency): the backend turns each formula into
SVG (preview, HTML) or PNG (PDF, Word) - one renderer, identical in every output, nothing added to the UI bundle.
It covers fractions, sub/superscripts, roots, sums, integrals, Greek, accents, most symbols; **not** matrices or
`align`. If the owner needs those: KaTeX (MIT, ~280 kB JS + fonts) bundled offline and lazy-loaded only on the report
screen for preview and HTML, with mathtext still for PDF / Word (two renderers - question 4).

### 2.3 The default document - how today's report is absorbed

When `ws.report.doc` is absent (every session saved until now), the report screen shows a document **generated
from `ws.report`** exactly as the panel's report is built today:

```markdown
# {title}
{intro}

{{ process() }}
{{ verdict() }}            <- only when meta.verdict and includeVerdict
{{ investigation() }}      <- only when there is one and meta.investigation !== false
{{ tab("<tabId>") }}       <- one per tab in scope (this tab / all), plots with excludeFromReport left out, captions kept

## Summary
{summary}

{{ notes() }}
```

It is not written into the session until the user changes it (the first edit commits `report.doc`), so opening and
saving an old session without touching the report changes nothing. A test checks that the default document of an
old session renders the same content (same plots, statistics, sections, notes) as `build_html` did from the panel's body.
*Reset to the default* (the screen's ⋯) regenerates it.

### 2.4 Where it is saved

```ts
// store/model.ts - ReportMeta gains ONE optional field; nothing else changes
export interface ReportDoc {
  v: 1;                       // the document format's version
  text: string;               // the Markdown source, fields with stable ids
  /** last values shown, by field text - shown greyed "not current" when the source is not open (question 7) */
  last?: Record<string, string>;
}
export interface ReportMeta { ...as today...; doc?: ReportDoc }
```

- **Undo**: the editor keeps its own fine-grained undo while typing; the workspace gets **one `commit` per pause**
  (1 s without typing) or when the editor loses focus - so Ctrl+Z outside the editor undoes a sentence, not a letter.
  Inserting a field (menu, drag, *Add to report*) is its own commit.
- **Autosave / session / template**: the field is optional; an older app opening a newer session ignores it and
  still makes its panel report from title, intro and summary, which keep the values they had (they are not synced
  from the document - one source of truth, no guessing which heading is the "title").
- **Several documents per session** (e.g. "flight report" and "one page for the manager") - question 2. If yes:
  `ws.reports?: ReportDoc[]` + `activeReport`, the default document still being the first; the model above stays.

---

## 3. References ("live fields")

### 3.1 The syntax

A field is `{{ name(args) }}` - a call with literal arguments and keyword arguments, **parsed with Python's `ast`
and a whitelist** (the field names below, string / number / tuple / list / True / False literals, nested field
calls) - the same rule as `svcore/formula.py`, never `eval`. Every reference is by stable id:

| Field | Shows | Notes |
|---|---|---|
| `stat("<runId>/<name>", "max")` | a number with its unit | statistics: `min max mean rms std range first final samples duration`, `tmax` / `tmin` (when the extreme happened). Optional: `range=(t0, t1)` (seconds, the file's time), `range=note("<noteId>")` (a note's span), `when=cond("<condId>")` (only while a condition holds - a mask, as `compute_signal_stats(mask=)`), `fmt=".3g"`, `unit=False` |
| `stat(formula("{<runId>/Roll} - {<runId>/RollDes}"), "rms", when=cond("<condId>"))` | a value of a formula | the formula through `svcore/formula.py` on the full data; `derived/<name>` signals are referenced like any signal |
| `table(["<runId>/a", "<runId>/b"], stats=["min","max","rms"], range=..., when=...)` | a statistics table | the same table cells and limits column as `_stats_table` |
| `plot("<tabId>/<plotId>")` | the plot | through `plotSpec` + `plot_data`; optional `range=`, `caption=`, `label="fig:roll"`, `width="half"` |
| `tab("<tabId>")` | every plot of the tab | `pagePlots` rule (maps / 3D included, occurrence / video plots listed with their reason) |
| `note("<noteId>")`, `notes()`, `findings()` | a note / all notes / the findings | findings with their status words |
| `cond("<condId>")`, `cond("<condId>", "count" \| "time" \| "first" \| "table")` | where a condition holds | default: "N stretches, total T s, first at t"; `table` = `occurrence_rows` |
| `meta("<runId>", "name" \| "file" \| "start" \| "duration" \| "format" \| "samples")`, `param("<runId>", "NAME")` | the recording's facts | `param` as in formulas: the value at the end of the log |
| `process()`, `investigation()`, `verdict()` | today's generated sections | so the default document is fields only |
| `ref("fig:roll")` | "Figure 3" | numbering of labelled plots / tables (RE1.5) |
| `sweep(...)` | a Sweeps result | RE1.6, made in Sweeps (2.1) |

Fields inside a Hebrew sentence are isolated (`<bdi>` / Unicode isolates) so `-12.3 m/s` reads left to right.

### 3.2 Values always on all the data, in the backend

`POST /api/report/render` (`routes/report.py`, new; `app/report.py` gains `render_doc`):
1. parse the Markdown (markdown-it-py) into blocks; parse each field (ast whitelist);
2. **resolve** each field: statistics with `compute_signal_stats` on the whole signal (or the range / mask) - never on
   decimated data; plots with `plot_data` (min/max levels; `full=True` for the HTML file: every sample, as CP1);
   conditions with `store.evaluate_condition`; formulas with `svcore/formula.evaluate`;
3. return the blocks for the preview (HTML fragments + plot payloads), or hand the same resolved blocks to the HTML /
   PDF / Word / Markdown emitter.
Each field's result is cached by (field text, the signals' `store.version`) - the preview re-renders only changed
fields; `compute_signal_stats` is already cached per data identity. Heavy fields go through `app.common.heavy`.

### 3.3 How a reference is picked (the user never types an id)

- **Autocomplete** after `{{`: field names, then signals (the same fuzzy search as the signal picker, by *name* and
  file), tabs, plots, notes, conditions - each shown by its name, written as its id.
- **Insert menu** (the screen's toolbar *Insert*): Value..., Table..., Plot..., Tab, Note / findings, Condition,
  Recording facts, Math, Callout, Page break. *Value...* is a small dialog: signal, statistic, range (all / between
  the cursors now / a note / shown window), when (a condition) - with the value shown live before it is inserted.
  "Between the cursors" is **frozen to numbers** on insert (cursors are UI state and move; a report must not).
- **The library** (left pane): tabs with their plots, notes, conditions, the open files - drag any into the text.
- **From the plots**: ⋯ *Add to report* on a plot, the tab's right-click *Add to report*, a signal chip's
  *Add value to report* (statistic menu). Ctrl+K: *Insert into report...*.
- **In the editor** a field reads as a chip with names (`max · Roll · flight_12.bin`), the raw text shown when the
  caret enters it - so ids never get in the way.

### 3.4 Renames and closed sources - never a silent wrong value

- A signal renamed in the app (derived signals' rename, `/api/derived/rename`), a tab or plot renamed: ids do not
  change, so nothing to do; a derived signal's id changes with its name - the rename action rewrites the document's
  references in the same `commit`.
- A file closed, a plot / tab / note / condition deleted: the field renders as a **broken reference** - a red chip
  "⚠ Roll · flight_12.bin - file not open" in the editor and the preview, with *Point to...* (choose another file
  / plot, rewriting the ids). Exports list the broken fields first ("3 fields cannot be filled: ... Export anyway?")
  and print them as "[not available: Roll · flight_12.bin]", never as an empty cell or a stale number.
- Deleting a plot / tab / note that a document uses asks first ("used by the report - delete anyway?").
- Sessions reopen files with their original ids; *Open session with new files* keeps ids too - the document follows
  the new files by itself (`neededNames` also walks `report.doc` so the dialog checks the document's signals).

---

## 4. Editing UX

- **Layout:** head row (document name, language, theme, Export ▾, Copy for Confluence, ⋯) / three columns:
  *library + outline* (collapsible) | **source** | **live preview** (resizable split; `Ctrl+\` toggles source /
  preview / both). Not WYSIWYG: the source is the truth (copy, diff, templates), the preview is what goes out.
- **Editor component:** CodeMirror 6 (MIT, lazy-loaded with the report screen - not in the main bundle; ~150 kB
  gz). Reason (task notes): chips over field text, autocomplete at the caret, Markdown highlighting, **direction per
  line** (`perLineTextDirection`), search, its own undo, accessible. A plain `<textarea>` cannot show chips or keep
  Hebrew and English lines each in its own direction. Question 5.
- **Toolbar (Insert):** heading, bold, italic, list, table, math, callout, page break, and the field menu (3.3).
- **Keyboard:** Ctrl+B / Ctrl+I, Ctrl+K stays the command palette (with *Insert into report...*), Ctrl+Space
  autocomplete, Alt+↑/↓ move a line, Ctrl+S saves the session, Ctrl+E export (last format), F2 on a chip *Point to...*.
- **Outline:** the headings; click to jump (source and preview scroll together).
- **Preview:** the report page itself (`build_html`'s CSS and `viewer.js` with uPlot) in a sandboxed iframe, updated by
  `postMessage` block by block (no flash, scroll kept); plots interactive as in the HTML file.
- **Light / dark:** the screen uses `index.css` variables; the preview follows the report's own theme choice.
- **Hebrew / RTL:** each paragraph's direction from its first strong letter (`dir="auto"`), in the editor and in every
  output (HTML `dir=auto`, Word `rtlize` per paragraph, PDF `_bidi` per line); numbers and fields isolated. Every new
  string through `i18n/` (a new `i18n/report.ts`, moving the report words out of `live.ts`).

---

## 5. Output - one path

`parse -> resolve (fields) -> emit`. The preview and every export share parse and resolve; only the emitter differs:

| Output | Emitter | Plots | Math | Notes |
|---|---|---|---|---|
| Live preview | HTML fragments | uPlot, interactive | mathtext SVG | block by block |
| HTML file | `build_html` page around the blocks | interactive, **every sample** (`full=True`, as CP1) | SVG | replay / story bar kept when the document has a time plot |
| PDF | the matplotlib page builder, extended to flow blocks (headings, paragraphs, lists, tables, figures, callouts, `\newpage`) | `render_figure` | PNG | the weakest emitter today - question 10 |
| Word | `build_docx` extended the same way | PNG | PNG | Heading styles, real tables, RTL per paragraph |
| Markdown | the source with fields replaced by text / tables and `![...](images/fig_3.png)` | PNG files beside it | kept as `$...$` | a folder: `report.md` + `images/` |
| Copy for Confluence | `build_clip_page` (the document as the attachment page) + `build_clip_macro` + `build_clip_static` (inline styles) | as CP1 | PNG in the static copy | same three functions, no new copy path |
| CLI / Python | `app/batch.py`, `signalviewer.report()` | as the file format | | the document from the template (RE1.4) |

---

## 6. Phases (each a commit series with its own "Done when")

**RE1.1 - MVP: write a report with values and plots.**
The report screen (2.1) with source | preview (plain `<textarea>` allowed here if CodeMirror is not yet agreed),
Markdown core, fields `stat` (range numbers / note / all), `table`, `plot`, `tab`, `notes`, `meta`; autocomplete
after `{{` and the *Insert* menu with *Value...*; broken references; `ws.report.doc` with commit per pause; the
default document (2.3) and the side panel removed; exports HTML (every sample), PDF, Word through the shared path.
*Done when:* an old session's report (default document) has the same plots, statistics, sections and notes as
before (backend test against `build_html`'s body); a needle test - `{{ stat(..., "max") }}` on a 5,000,000-sample
signal with one spike prints the spike, in preview, HTML, PDF and Word (backend + e2e `test_report_doc.py`); undo /
redo of an edit and of an insert; a closed file shows the broken chip and the export asks; a Hebrew paragraph with an
English field reads correctly (RTL checked by eye and by `dir`); quick_check green; e2e: the new file +
`test_report*.py`, `test_confluence_copy.py`, `test_templates*.py`.

**RE1.2 - the investigation in the text.** `when=cond(...)`, `cond(...)`, `formula(...)`, `findings()`, `process()`,
`investigation()`, `verdict()`; the library pane with drag; *Add to report* on plots, tabs and chips; chips in the
editor (CodeMirror). *Done when:* a statistic while a condition holds equals `compute_signal_stats(mask=)` on all
the data (test); a renamed derived signal keeps its fields (one undo step); each entry point inserts the same field.

**RE1.3 - the report as a template for the next recording.** Capture: the document goes into the template with
`"<runId>/<name>"` rewritten to `"@<slot>/<name>"`, tab / plot ids to the template's own keys, conditions and notes by
name; apply: rewritten back to the new ids. `cli.py report --template` and `signalviewer.report()` make the document
when the template has one. *Done when:* a template made from session A, applied to file B, gives the document with
B's values (e2e + backend), and the CLI gives the same numbers for B; *Open session with new files* checks the
document's signals.

**RE1.4 - math, outline, numbering.** `$...$` / `$$...$$` (mathtext, or KaTeX per question 4), `label=` / `ref()`
numbering of figures and tables, the outline pane, callouts, `\newpage`. *Done when:* the same formula appears in
preview, HTML, PDF and Word; numbering follows reordering.

**RE1.5 - more outputs.** Markdown + images folder; *Copy for Confluence* of the whole document (CP1's functions).
*Done when:* the e2e stand-in Confluence page shows the document's attachment page with every sample.

**RE1.6 - Sweeps results.** In Sweeps, *Copy as report field* on the answer / the best set / a plot: a `sweep()`
field naming the study file, the question and the result kind, with a **snapshot** of the result saved in the field
(Sweeps' tables are outside the session) and *Refresh* when the study is open. *Done when:* the number in the report
equals the one in Sweeps; the report opens without the study (snapshot shown, marked with its date).

## 7. Risks

- **Preview speed** on long documents with many plots: mitigated by per-field cache and block-by-block updates;
  measured in RE1.1 (target: a value edit visible < 300 ms, a plot < 1 s on the 4-core sandbox).
- **The PDF emitter** (matplotlib pages) is the hardest to make flow text, tables and figures well; Hebrew wrapping
  in particular. Alternative: *Print to PDF* from the HTML page (best typography, uses the system's print dialog).
- **Two kinds of undo** (the editor's and the workspace's) can surprise; the commit-per-pause rule must be tested.
- **New dependencies** (markdown-it-py + mdit-py-plugins, CodeMirror 6) - each needs the owner's yes; the light
  install (`lite`) must still work: the Markdown parser goes into the base requirements, not an extra.
- **Template rewrite of ids** must handle plots that the template drops (no signal in the new file): fields become
  broken references, never wrong ones.
- **mathtext coverage** - matrices / aligned equations not supported (question 4).

## 8. Questions for the owner (in Hebrew, as sent)

1. מיקום: מסך מלא בתוך אזור ההקלטות (כפתור "דוח" בסרגל מחליף את הגרפים בעורך) - מומלץ; או אזור שלישי בשורה העליונה ליד Sweeps?
2. מסמך אחד לכל סשן, או כמה מסמכים (למשל "דוח טיסה" ו"עמוד למנהל")?
3. הפאנל הצדדי הנוכחי של הדוח יוסר והטופס שלו יהפוך ל"מסמך ברירת המחדל" - מאשר?
4. נוסחאות מתמטיות: matplotlib (בלי תלות חדשה, זהה בכל הפורמטים, בלי מטריצות) או KaTeX (LaTeX מלא, ~300KB בטעינה עצלה, רק ב-HTML/תצוגה)?
5. עורך: CodeMirror 6 (תלות חדשה, נטען רק במסך הדוח; צ'יפים, השלמה אוטומטית, כיוון לכל שורה) - מאשר?
6. מפענח Markdown: ספריית markdown-it-py (קטנה, Python טהור) - מאשר, או מפענח חלקי משלנו?
7. כשהקובץ סגור: להציג את הערך האחרון באפור עם "לא עדכני", או רק סימון "הפניה שבורה"?
8. סדר השלבים: התבנית (אותו דוח על הקלטה חדשה + שורת פקודה) לפני הנוסחאות המתמטיות?
9. Sweeps: אילו תוצאות תרצה לצטט (התשובה, הסט הטוב, טבלה, גרף)? צילום מצב קפוא עם "רענן" - בסדר?
10. PDF: להמשיך עם matplotlib (פשוט, בלי תלות) או "הדפס ל-PDF" מהדף (מראה טוב יותר, דרך חלון ההדפסה)?
