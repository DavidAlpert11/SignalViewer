# Development

The rules for every change are in [`CLAUDE.md`](https://github.com/DavidAlpert11/SignalViewer/blob/main/CLAUDE.md); the work queue and the catalogue of tasks in [`docs/dev/`](https://github.com/DavidAlpert11/SignalViewer/tree/main/docs/dev).

## Structure

```
run.py                 launcher (server + window)
SignalViewer.spec     PyInstaller build definition (build.bat / build.sh)
tools/benchmark.py     performance benchmark
tests/e2e/             end-to-end browser tests
backend/app/main.py    local API, 127.0.0.1 only (wires the routes, local-only guard, UI files)
backend/app/routes/    the API endpoints, one module per area (files, data, analysis, compare...)
backend/app/store.py   loaded files with stable ids
backend/svcore/        computation core: loaders, decimation, analysis, compare, sync
backend/tests/         pytest suite
frontend/src/          React + TypeScript UI (uPlot, zustand)
frontend/dist/         built UI served by the backend
examples/              demo files (tools/make_demo_data.py)
docs/images, docs/media  screenshots and clips used in this README
```

Environment variables: `SV_FLOAT32`, `SV_CACHE`, `SV_CACHE_MIN_MB`, `SV_MAX_POINTS`.
Workspace autosave and the binary cache live in `~/.signalviewer/`; the error log in
`~/.signalviewer/logs/` (Help > Copy error details puts its end on the clipboard; `SV_LOG_DIR` moves it).

## Tests: numbers and real logs

`cd backend && python -m pytest -q` runs everything that needs no network, including the
[numerical validation](validation.md) (`tests/test_validation.py`; after changing a case, rewrite the
page with `python tools/make_validation_doc.py`).

**Real flight logs** (`tests/test_real_logs.py`): logs recorded by real vehicles, not only the ones our
own tools write, checked against their projects' own readers - ArduPilot DataFlash against pymavlink's
DFReader (every numeric field), `.tlog` against pymavlink (every sample, on the autopilot's clock),
PX4 `.ulg` against pyulog (every field of every topic) - and for invariants (finite, non-decreasing
time; the health check runs). The public logs are pinned to a commit and a SHA-256 and kept outside
the repository (their licences differ from ours):

```bash
python tools/fetch_real_logs.py                          # once: ~/.cache/signalviewer-test-logs
cd backend && python -m pytest -q tests/test_real_logs.py
SV_REAL_LOGS=/path/to/your/logs python -m pytest -q tests/test_real_logs.py   # your own logs too
```

Without the download those tests are skipped; the regression test for radio delay always runs.

---

## Icon

`assets/icon.svg` (full) and `assets/icon-small.svg` (simplified for 16–32 px), rendered to
`assets/png/`, `assets/icon.ico` (Windows) and `assets/icon.icns` (macOS). Used for the executable,
the window and the browser tab. A signal trace read by the amber measurement cursor, the same
visual language as the app.
