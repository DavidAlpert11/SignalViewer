# Install

Signal Viewer runs on Windows, Linux and macOS. **Nothing needs the internet at run time** – no account, no
telemetry; the map and the 3D terrain work offline too.

=== "Windows"

    From the [latest release](https://github.com/DavidAlpert11/SignalViewer/releases/latest):

    - **`SignalViewer-Setup-X.Y.Z.exe`** – installs for you only, no administrator rights; Start menu,
      *Open with* for data files, an uninstaller.
    - **`…-Windows-x64-portable.zip`** – to run without installing: extract, double-click *Signal Viewer.bat*.

=== "Linux / macOS"

    The **`-portable.7z`** for your system from the
    [latest release](https://github.com/DavidAlpert11/SignalViewer/releases/latest) (macOS: Apple silicon,
    M1 and later). Extract it and run `SignalViewer/SignalViewer`. Or install it with Python.

=== "Python (3.9 or newer)"

    ```bash
    pip install signalviewer                 # every reader and report
    signalviewer                             # the app (in the browser)
    pip install "signalviewer[desktop]"      # ... or in its own window
    ```

=== "From source"

    ```bash
    git clone https://github.com/DavidAlpert11/SignalViewer.git
    cd SignalViewer && pip install -r requirements.txt && python run.py
    ```

    The first start builds the UI (Node.js LTS needed, about half a minute) – [more below](#run-from-source).

## First start: Windows and macOS warnings

!!! warning "The packages are not code-signed yet, so the first start may be stopped once"

    - **Windows** (*Windows protected your PC*, SmartScreen): *More info* → *Run anyway*. Shown for the
      installer and for `SignalViewer.exe` from the portable package, once per version.
    - **macOS** (*"SignalViewer" cannot be opened* or *is damaged*): macOS marks files that came from
      the internet. Remove the mark from the extracted folder once, in Terminal:
      `xattr -dr com.apple.quarantine /path/to/SignalViewer`, then start `SignalViewer` in it (or
      right-click it → *Open* → *Open*).

## The light install

`pip install signalviewer-lite` (about 350 MB instead of 760) is the core – CSV, MATLAB v5, ArduPilot .bin,
CAN, binary layouts, every plot and analysis, HTML reports. The rest are extras; a file that needs one says which.

| Extra | Adds |
|---|---|
| `[parquet]` | Parquet (also a faster CSV reader) |
| `[hdf5]` | `.h5`, MATLAB v7.3 |
| `[mavlink]` | `.tlog`, live MAVLink |
| `[px4]` | `.ulg` |
| `[ros]` | `.mcap` |
| `[reports]` | PDF, Word, images |
| `[desktop]` | its own window instead of the browser |
| `[all]` | everything |

Both install the same `signalviewer` Python package: install one of them, not both.

The packages carry the examples without their recordings (1.30.0): the first time you open an example its files
are written to `~/.signalviewer/examples/<version>` - a second or two, once per version, the same recordings as before.

## From scripts

`signalviewer-cli` and `import signalviewer` read and export recordings from scripts. `rec.signal("ATT.Roll")`
finds *ATT.Roll [deg]* (the unit may be left out), and `signalviewer.show(t, {"alt": alt})` sends
arrays from a notebook into the open app. [Command line and Python](command-line.md).

## If the window does not open

**Windows window engine.** The app window uses Microsoft Edge WebView2 (built into Windows 11 and
updated Windows 10). If it is missing (e.g. an old offline Windows 10 LTSC), the app opens in the local
browser instead — still with no internet — says why in the page (and in the log), and stops by itself
5 minutes after its last tab was closed (or a minute after the tab says it is closing; never while a
file is still being read). The portable package unblocks its own DLLs that Windows marked as
downloaded, which used to send it to the browser every time.

The UI is built for Chromium 87 / Firefox 78 and newer (`frontend/vite.config.ts`, `MIN_CHROMIUM` in
`run.py`). An offline computer often keeps an older WebView2: the app then opens in a newer Edge or
Chrome as a window of its own (`--app`, with a profile of its own in `~/.signalviewer/browser-profile`),
else in Firefox, else it shows a message box with what to install (the *Evergreen Standalone
Installer* of the WebView2 runtime). If the page still does not start, the page itself says why
instead of staying blank. **Safe graphics** (`--safe-graphics`, the *Signal Viewer (safe graphics)*
shortcut) draws without the graphics card - for a white or black window on virtual machines, remote
desktop or old drivers; the 3D view still works, drawn by the processor.

## For developers

### Building the packages

**Nothing needs the internet at run time.** The installer, the portable folder and the single
file contain Python, every library, the UI with its fonts, the report assets and the icon.
Verified by running the built app with no network interface at all.

Build commands (Windows unless said):

- `build.bat installer` → `dist\SignalViewer-Setup-1.37.0.exe`  
  **Recommended.** One file; installs for the current user (no admin), Start-menu and desktop icons, *Open with* for data files, uninstaller
- `build.bat portable` → `dist\SignalViewer-portable.zip`  
  Unzip anywhere and run `SignalViewer.exe` (fast start)
- `build.bat onefile` → `dist\SignalViewer.exe`  
  A single file to copy; starts a few seconds slower (it unpacks itself each time)
- `build_windows_portable.bat` (**Windows**) / `python tools/make_windows_portable.py` → `dist\SignalViewer-Windows-portable.7z`  
  **Windows portable build on a Windows PC**: double-click the `.bat` (needs Python 3.8+ with pip and internet, once, only to build). Downloads the official embeddable Python + the Windows builds of the libraries; the result needs no Python and no internet. **7z** (about 80 MB instead of 126 MB as zip): made with 7-Zip when installed, else with the py7zr library fetched once; Windows 11 opens .7z in Explorer, Windows 10 needs 7-Zip. `--format zip` for a zip, `--keep-folder` keeps the assembled folder, `--clean` forces a fresh download, `--build-ui` rebuilds the web UI first (Node.js; done automatically when the UI sources are newer than the built UI)
- `tools/make_windows_portable.sh` (Linux/macOS) → `dist/SignalViewer-Windows-portable.7z`  
  Builds the same Windows package **without a Windows PC** (runs the same Python builder; options are passed on)
- `build.bat wheels` → `wheels\`, `frontend\dist`  
  On a connected PC: downloads the libraries and builds the UI once (Node.js needed), so the build itself can run on an offline PC

The installer needs Inno Setup 6 on the BUILD PC only (free).

**Ready-made packages** (no Python and no installation needed, except the Windows installer itself) are built by the GitHub
Actions workflow in `.github/workflows/build.yml` for Windows (x64: the installer, a portable `.zip` and `.7z`), Linux (x64) and macOS (Apple silicon):
run it manually (*Actions → build → Run workflow*) and download them from the run's artifacts, or push a
tag such as `v1.0.0` to also get a draft Release with every file and a "which file?" note. Windows: the embeddable-Python
package described above; Linux / macOS: the PyInstaller folder (`SignalViewer.spec`) - extract it and run
`SignalViewer/SignalViewer`.

Build it yourself: `build.bat` (Windows) or `./build.sh` (Linux / macOS) → `dist/SignalViewer[.exe]` - with Node.js
installed: the UI is not kept in git, so the script builds it first.

### Run from source

```bash
pip install -r requirements.txt
python run.py              # native window (pywebview), or the browser if pywebview is missing
python run.py --browser    # always use the browser
python run.py flight.bin   # open files (or a .svsession) - in the app that is already running, if there is one
```

The built UI (`frontend/dist`) is not kept in git - the installer, the portable package and
`pip install signalviewer` carry it. From the source folder, `run.py` builds it once by itself on the first
start - Node.js (LTS) needed - and again whenever the UI code is newer than that build (after a pull, a patch
or an edit); the next start sees it is current and starts at once. `python run.py --build` forces a build,
`--no-build` (or `SV_NO_BUILD=1`) never builds. Without Node.js it says so (and shows the last build, if
there is one). For working on the UI:

```bash
python run.py --port 8765 --no-open   # backend
cd frontend
npm install
npm run dev      # dev server with hot reload, proxies /api to port 8765
npm run build    # builds frontend/dist (not in git)
```

Tests:

```bash
python -m pytest backend/tests          # ~1,500 server tests (incl. damaged copies of every format)
pip install -r requirements-dev.txt && python -m playwright install chromium
python -m pytest tests/e2e              # ~540 browser tests, the whole suite in one run (~30 min)
python -m pytest tests/e2e/test_features.py    # or one file: one test per catalog feature
cd backend && mypy --config-file ../pyproject.toml app svcore signalviewer   # type check
python tools/benchmark.py big.csv       # performance against the targets (results in docs/)
python tools/benchmark.py --synthetic   # the plot / offset / memory / live benchmarks, on generated data
```
