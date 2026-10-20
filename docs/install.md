# Install, build and run from source

**Download:** the [latest release](https://github.com/DavidAlpert11/SignalViewer/releases/latest).
On Windows take **`SignalViewer-Setup-X.Y.Z.exe`** (installs for you only, no administrator rights);
to run without installing, the **`…-Windows-x64-portable.zip`** (extract, double-click *Signal
Viewer.bat*). Linux and macOS: the `-portable.7z` for your system.

**With Python (3.9 or newer):** `pip install "signalviewer[all]"`, then `signalviewer` starts the app.
A plain `pip install signalviewer` is the core (about 350 MB instead of 760): CSV, MATLAB v5, ArduPilot
.bin, every plot and analysis, HTML reports. The rest are extras - `[parquet]` (also a faster CSV
reader), `[hdf5]` (.h5, MATLAB v7.3), `[mavlink]` (.tlog, live MAVLink), `[px4]` (.ulg), `[ros]`
(.mcap), `[reports]` (PDF, Word, images), `[desktop]` (its own window instead of the browser); a
file that needs one says which.
`signalviewer-cli` and `import signalviewer` read and export recordings from scripts. `rec.signal("ATT.Roll")`
finds *ATT.Roll [deg]* (the unit may be left out), and `signalviewer.show(t, {"alt": alt})` sends
arrays from a notebook into the open app.

**Nothing needs the internet at run time.** The installer, the portable folder and the single
file contain Python, every library, the UI with its fonts, the report assets and the icon.
Verified by running the built app with no network interface at all.

| Build command (Windows) | Result | When |
|---|---|---|
| `build.bat installer` | `dist\SignalViewer-Setup-1.8.0.exe` | **Recommended.** One file; installs for the current user (no admin), Start-menu and desktop icons, *Open with* for data files, uninstaller |
| `build.bat portable` | `dist\SignalViewer-portable.zip` | Unzip anywhere and run `SignalViewer.exe` (fast start) |
| `build.bat onefile` | `dist\SignalViewer.exe` | A single file to copy; starts a few seconds slower (it unpacks itself each time) |
| `build_windows_portable.bat` (**Windows**) / `python tools/make_windows_portable.py` | `dist\SignalViewer-Windows-portable.7z` | **Windows portable build on a Windows PC**: double-click the `.bat` (needs Python 3.8+ with pip and internet, once, only to build). Downloads the official embeddable Python + the Windows builds of the libraries; the result needs no Python and no internet. **7z** (about 80 MB instead of 126 MB as zip): made with 7-Zip when installed, else with the py7zr library fetched once; Windows 11 opens .7z in Explorer, Windows 10 needs 7-Zip. `--format zip` for a zip, `--keep-folder` keeps the assembled folder, `--clean` forces a fresh download, `--build-ui` rebuilds the web UI first (Node.js; done automatically when the UI sources are newer than the built UI) |
| `tools/make_windows_portable.sh` (Linux/macOS) | `dist/SignalViewer-Windows-portable.7z` | Builds the same Windows package **without a Windows PC** (runs the same Python builder; options are passed on) |
| `build.bat wheels` | `wheels\` | On a connected PC: downloads the libraries once, so the build itself can run on an offline PC |

The installer needs Inno Setup 6 on the BUILD PC only (free).

**Windows window engine.** The app window uses Microsoft Edge WebView2 (built into Windows 11 and
updated Windows 10). If it is missing (e.g. an old offline Windows 10 LTSC), the app opens in the local
browser instead — still with no internet — and stops by itself when no tab has been open for 30 s.


**Ready-made packages** (no Python and no installation needed, except the Windows installer itself) are built by the GitHub
Actions workflow in `.github/workflows/build.yml` for Windows (x64: the installer, a portable `.zip` and `.7z`), Linux (x64) and macOS (Apple silicon):
run it manually (*Actions → build → Run workflow*) and download them from the run's artifacts, or push a
tag such as `v1.0.0` to also get a draft Release with every file and a "which file?" note. Windows: the embeddable-Python
package described above; Linux / macOS: the PyInstaller folder (`SignalViewer.spec`) - extract it and run
`SignalViewer/SignalViewer`.

Build it yourself: `build.bat` (Windows) or `./build.sh` (Linux / macOS) → `dist/SignalViewer[.exe]`.

## Run from source

```bash
pip install -r requirements.txt
python run.py              # native window (pywebview), or the browser if pywebview is missing
python run.py --browser    # always use the browser
python run.py flight.bin   # open files (or a .svsession) - in the app that is already running, if there is one
```

The UI is already built (`frontend/dist`). When the UI code is newer than that build (after a
pull, a patch or an edit), `run.py` builds it once by itself - Node.js needed - into
`frontend/.local-dist` (ignored by git; the tracked `frontend/dist` is not touched) and serves
that; the next start sees it is current and starts at once. `python run.py --build` forces a
build, `--no-build` (or `SV_NO_BUILD=1`) never builds. Without Node.js it says so and shows the
last build. For working on the UI:

```bash
python run.py --port 8765 --no-open   # backend
cd frontend
npm install
npm run dev      # dev server with hot reload, proxies /api to port 8765
npm run build    # rebuilds frontend/dist
```

Tests:

```bash
python -m pytest backend/tests          # ~670 server tests (incl. damaged copies of every format)
pip install -r requirements-dev.txt && python -m playwright install chromium
python -m pytest tests/e2e              # ~190 browser tests, the whole suite in one run (~10 min)
python -m pytest tests/e2e/test_features.py    # or one file: one test per catalog feature
cd backend && mypy --config-file ../pyproject.toml app svcore signalviewer   # type check
python tools/benchmark.py big.csv       # performance against the targets (results in docs/)
```
