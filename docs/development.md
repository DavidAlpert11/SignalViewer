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

---

## Icon

`assets/icon.svg` (full) and `assets/icon-small.svg` (simplified for 16–32 px), rendered to
`assets/png/`, `assets/icon.ico` (Windows) and `assets/icon.icns` (macOS). Used for the executable,
the window and the browser tab. A signal trace read by the amber measurement cursor, the same
visual language as the app.
