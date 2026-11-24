---
name: sv-report-part
description: Add or change a ready-made part of Signal Viewer's report ([[tracking]], [[navigation]], [[states]], [[trajectory]], [[moments]], [[differences]], [[overview]], [[summary]], [[toc]]) - where its numbers, its Markdown, its library entry, its strings, tests and docs go. Use for any work on the report's automatic parts or ready reports.
---

# A ready-made report part

How the report works end to end: `docs/dev/REPORTS.md` ("How it works") - read it first. A part is written in the
text as `[[name arg | opt, opt]]`; the server writes its Markdown in place of the marker **before** the document is
parsed, so the page, the PDF and Word draw it with no new emitter code.

## Where each piece goes

1. **Numbers** - a pure function over arrays in `backend/svcore/reportparts.py` (or an existing svcore module:
   `objcompare`, `overview`, `quality`, `firstchange`, `ops.compute_signal_stats`). Every number on **all** the
   samples (CLAUDE.md: no point left out); return plain dicts.
2. **The part** - a function `def name(p: Part, rids, arg, o)` in `backend/app/reportparts.py`, registered in `RUN` (its words in `S` and options in `KNOWN`: `app/reportparts_base.py`)
   and `PARTS`, its options in `KNOWN`. Write with `p.say(markdown)`, `table(head, rows)`, `p.plot(title,
   [sig_line(id, label, k, ...)], rng=, caption=)` (a computed series: `p.series(label, t, y)`), `p.map(title,
   objects)`; findings for `[[summary]]` with `p.hl(level, score, text)` (fail / warn / info). Nothing found: one
   italic line, never an empty section. Bad option: `options()` raises `PartError` -> a red ⚠ listing `KNOWN`.
   Strings in `S["en"]` and `S["he"]` (both, same keys). With several files: one plot per quantity with every
   file's line, not a plot per file.
3. **The app** - the name in `PARTS` (`frontend/src/reportDoc.ts`); the library entry in
   `frontend/src/reportReady.ts partCategories` (and `readyText` if a ready report should include it); what the
   library needs to know in `scan()` (`app/reportparts.py`) and `ReportScan` (`api.ts`). Labels in
   `frontend/src/i18n/live.ts` (`rp…`, en + he). The `?` help text (`rdHelpText`) lists the parts.
4. **Tests** - `backend/tests/test_report_parts.py`: the numbers on a signal whose answer is known (and a needle);
   the demo end to end (`examples/report_demo`); a part that finds nothing. Vitest `src/reportReady.test.ts`,
   `src/reportDoc.test.ts`. e2e `tests/e2e/test_report_parts.py` when the library or the screen changes.
5. **Demo data** - if the part needs signals the demo lacks, extend `backend/svcore/example_data/make_report_demo.py`
   (deterministic), run `python tools/make_report_demo.py`, commit the CSVs (`test_example_data` compares).
6. **Docs** - `docs/reports.md` (the parts table), CHANGELOG, `docs/dev/REPORTS.md` if a decision was made;
   pictures `python tools/make_readme_media.py --only 48 49 50 51`.

Check with skill `sv-checks` (mypy is strict on Optional - narrow it).
