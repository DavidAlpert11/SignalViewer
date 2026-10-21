# Contributing to Signal Viewer

Thank you for helping. The most useful things, roughly in order:

1. **A bug report with a file that shows it.** *Help → Report a problem…* in the app copies the
   version, the system and the end of the log and opens the form. A short or anonymised piece of
   the recording is enough; a log that opens wrongly is fixed fastest when we can open it too.
2. **A reader for your format.** A Python file in `~/.signalviewer/readers` with a function marked
   `@reader(extensions=[".xyz"])` makes Signal Viewer open your files
   (`signalviewer-cli readers --example` writes one to start from). If others record the same
   format, open a pull request that adds it - see
   [Command line, Python and formats](https://davidalpert11.github.io/SignalViewer/command-line/).
3. **A pull request** for a fix or a feature. For anything larger than a fix, open an issue first,
   so we agree on where it belongs before you write it.

## Set up and run

```bash
git clone --depth 1 https://github.com/DavidAlpert11/SignalViewer.git
cd SignalViewer
pip install -r requirements.txt -r requirements-dev.txt
cd frontend && npm ci && cd ..          # only for UI changes (Node.js 22)
python run.py                            # rebuilds the UI by itself when its sources changed
```

## Before you open the pull request

```bash
cd backend && python -m pytest -q                                          # all green
cd backend && mypy --config-file ../pyproject.toml app svcore signalviewer  # clean
cd frontend && npx tsc -b && npm run build                                 # UI changes
python -m pytest -q tests/e2e/test_workflows.py                            # UI flows (python -m playwright install chromium, once)
```

CI runs these on every pull request. You do not need to commit `frontend/dist`: a release rebuilds it.

## The few rules that matter

The full list is in [`CLAUDE.md`](CLAUDE.md) (written for people and coding agents alike). In short:

- **Offline, local only.** The app works with no network and listens only on 127.0.0.1. No new
  network calls, no telemetry.
- **Old files keep opening.** Sessions, templates and autosave are backward compatible: new fields
  are optional with a default; a saved field is never renamed or repurposed.
- **English and Hebrew.** Every text on screen goes through `frontend/src/i18n.ts` in both
  languages (TypeScript enforces it); check right-to-left. Colours come from the CSS variables
  (light and dark).
- **Heavy work in the backend**, on full-resolution data; the UI receives decimated data only.
  Formulas go through the AST whitelist in `svcore/formula.py` - never `eval`.
- **A test for what you change** (`backend/tests`; `tests/e2e` for UI flows), a line in
  `CHANGELOG.md` for what users will notice, and one change per commit.
- **Numbers are checked against references.** A change to a computation keeps
  `signalviewer-cli validate` green; a new computation brings a case for it (`svcore/validation.py`).

## Where things are

[Development](https://davidalpert11.github.io/SignalViewer/development/) has the structure, the
build, the tests and the benchmarks. The work queue and the plans are in `docs/dev/`.

By contributing you agree that your contribution is released under the [MIT License](LICENSE).
