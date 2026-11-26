---
name: sv-checks
description: Run Signal Viewer's checks after a change - set up the cloud sandbox, quick_check, the e2e files that touch the change (a map from area to test files), the whole suite at the end of a round. Use after every task, before handing work over or merging.
---

# Checks after a change (Signal Viewer)

The rules are in `/CLAUDE.md` ("After every change"); this is the practical sequence.

## 1. Set up (a fresh cloud container)

```bash
grep -vi pywebview requirements.txt > /tmp/r.txt && pip install -q -r /tmp/r.txt -r requirements-dev.txt
cd frontend && npm ci --no-audit --no-fund && cd ..
export SV_CHROMIUM=/opt/pw-browsers/chromium        # the pre-installed Chromium (never `playwright install`)
```

## 2. Always

```bash
python tools/quick_check.py          # tsc, oxlint baseline, Vitest, backend pytest, mypy - stops at the first failure (~4 min)
```
It runs long: start it in the background and read its log; mypy must say `Success`.

## 3. The e2e files that touch the change

While working, only these (owner, 2026-11-21: push first, then check, fix forward - skill `sv-flow`); the whole
suite once at the end of the round (§4).

Build the UI first (`cd frontend && npm run build`) and **do not edit `frontend/src` while e2e runs** - `run.py`
rebuilds on a changed source and the fixture times out (*Connection refused*). One file per process:

```bash
for f in test_report_parts test_report_doc; do python -m pytest -q tests/e2e/$f.py; done
```

| Changed | Run (tests/e2e/) |
|---|---|
| Report screen, parts, reportdoc.py, report.py (report_office.py PDF / Word, report_clip.py Confluence) | test_report_parts, test_report_doc, test_live_report, test_findings_report, test_confluence_copy |
| LaTeX (reportlatex.py, svcore/latex.py, the built-in Tectonic) | backend test_report_latex (the built-in tests run after `python tools/get_tectonic.py` and `python tools/make_tex_bundle.py --check`); e2e test_report_doc -k latex |
| The HTML page's plots (report_assets/viewer.js) | e2e test_report_xy_zoom, test_report_doc, test_confluence_copy, test_live_report |
| Messages panel, structures, byte streams, links | backend test_bytestream test_protocol test_msginspect test_messages_library test_rawlink; e2e test_messages |
| Templates, profiles | test_template_tabs, test_object_templates, test_templates_recent_badfiles |
| Examples, welcome, Help menu | test_welcome_cards, test_fresh_user |
| Sweeps | test_sweeps_*.py, test_needle, test_settings |
| Maps / 3D | test_globe3d, test_map_objects, test_needle |
| Plots, cursors, legend | test_features (-k), test_plot_*, test_cursor_labels, test_needle |
| What changed / Investigate | test_what_changed, test_features -k investigate |
| Anything that changes what is on screen by default | also the views that gain or lose room (CLAUDE.md, the T08 story) |

`grep -ln "<a selector or word you changed>" tests/e2e/*.py` finds the rest.

## 4. End of a round (before a version) - the whole suite, one file at a time (~35 min)

```bash
rm -rf /tmp/pytest-of-*
for f in tests/e2e/test_*.py; do echo "$(basename $f): $(python -m pytest -q "$f" 2>&1 | tail -1)"; done > /tmp/e2e_full.log
```
Run in the background. A file that fails under load is re-run alone before it is called a failure; say both in the
TASKS.md log.

## 5. Docs

```bash
pip install -q mkdocs==1.6.1 mkdocs-material==9.7.7 && mkdocs build --strict -d /tmp/site
```
