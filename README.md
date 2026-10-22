<p align="center">
  <img src="assets/png/icon-128.png" width="96" alt="Signal Viewer icon">
</p>

<h1 align="center">Signal Viewer</h1>

<p align="center">
  <b>A fast, offline desktop app for exploring, comparing and reporting on time-series data</b><br>
  CSV · Parquet · MATLAB .mat · ArduPilot .bin · MAVLink .tlog · PX4 .ulg · ROS 2 .mcap · HDF5 · CAN + .dbc
</p>

<p align="center">
  <a href="https://github.com/DavidAlpert11/SignalViewer/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/DavidAlpert11/SignalViewer/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/UI-React%20%2B%20TypeScript-61DAFB?logo=react&logoColor=black">
  <img alt="Platforms" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey">
  <img alt="Offline" src="https://img.shields.io/badge/runs-100%25%20offline-2ea44f">
  <img alt="Languages" src="https://img.shields.io/badge/UI-English%20%7C%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA-orange">
  <a href="https://davidalpert11.github.io/SignalViewer/"><img alt="Docs" src="https://img.shields.io/badge/docs-site-0A7BBB"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
</p>

<p align="center">
  <a href="https://github.com/DavidAlpert11/SignalViewer/releases/latest"><b>⬇ Download for Windows</b></a>
  &nbsp;·&nbsp; <code>pip install signalviewer</code>
  &nbsp;·&nbsp; <a href="https://davidalpert11.github.io/SignalViewer/"><b>Documentation</b></a>
  &nbsp;·&nbsp; <a href="https://davidalpert11.github.io/SignalViewer/GUIDE.he/"><b>מדריך בעברית</b></a>
</p>

<p align="center">
  <img src="docs/images/01_overview.png" alt="Signal Viewer: four linked plots, two cursors and statistics between them" width="100%">
</p>

**For flight-test, drone and simulation engineers** who have recordings to judge: several runs of
the same test, a flight log after a flight, a simulation next to the real thing – often on a closed
network. Open the files, see what is wrong, compare, report; then make the same check pass / fail in CI.

- **Plot** – up to 9 linked plots per tab: Time, X-Y, FFT, spectrogram, map, 3D; two cursors with Δ and statistics.
- **Compare runs** – every shared signal ranked by how different it is, time-aligned, also per segment (the 2nd AUTO of every flight).
- **Flight logs** – ArduPilot, PX4 and MAVLink read directly: flight modes, events, parameters and an automatic health check.
- **Live** – MAVLink over UDP, TCP or a serial radio, recorded to a `.tlog` as it arrives.
- **Map and 3D** – the vehicle, its attitude and its track on an offline map and terrain, in step with the timeline.
- **Math** – formulas (`2*Speed - RPM/95`), filters, derivatives, integrals, coordinate frames (NED / ENU / body / ECEF / LLA); the same change on many signals at once (`x*8` or `sin(x)` on each one selected).
- **Reports** – offline HTML, PDF and Word; one per file from the command line.
- **CI** – `signalviewer-cli check` (limits) and `compare` (against a golden run) with exit codes and JUnit XML.
- **Any recording** – CAN with a `.dbc`, raw binary packets from a layout (ICD), or your own format as a short Python reader.

Under the hood: a Python core (FastAPI + NumPy) and a React / TypeScript UI in one native window.
Multi-gigabyte recordings open in seconds, every sample stays available at full resolution, and
**nothing needs the internet** – not even the map and the 3D globe.

---

## See it in action

### Open a file and build a view

Open a file, choose a layout, click signals into plots, then zoom and read values with two cursors.

<p align="center"><img src="docs/media/01_quickstart.gif" alt="Opening a CSV, plotting four signals, zooming and placing two cursors" width="100%"></p>

### A flight on the map and in 3D

One template turns latitude / longitude / altitude / attitude signals into a map and a 3D view. Press
play and both follow the timeline; *Up to the time* draws the track as it is flown.

<p align="center"><img src="docs/media/02_flight_map_3d.gif" alt="A UAV flight over the Sea of Galilee played back on the offline map and in 3D" width="100%"></p>

### Compare runs

Pick several files: every shared signal is ranked from least to most similar. Click a row to overlay
it, align the runs in time automatically, or open the table of all signals.

<p align="center"><img src="docs/media/03_compare_runs.gif" alt="Comparing three runs: similarity list, overlay and comparison table" width="100%"></p>

### Flight-log health check

Open an ArduPilot `.bin` and the **Log** panel finds vibration, clipping, battery, EKF and motor
problems. Click a finding to jump to it; click an event to move the cursor there.

<p align="center"><img src="docs/media/04_flight_log_health.gif" alt="ArduPilot log: vibration template, health findings, events and parameters" width="100%"></p>

### Live from the vehicle

*Live ▸ MAVLink*: connect to a vehicle, a simulator or a ground station that forwards (UDP, TCP or
a serial radio). The link is recorded to a `.tlog` that opens like any file and grows in live mode;
*Follow* keeps the last seconds in view.

<p align="center"><img src="docs/media/05_live_mavlink.gif" alt="Live MAVLink: attitude and altitude growing as the vehicle sends them" width="100%"></p>

> Higher-quality MP4 versions of these clips are in [`docs/media/`](docs/media).

---

## Quick start

```bash
git clone --depth 1 https://github.com/DavidAlpert11/SignalViewer.git   # without the history: much smaller
cd SignalViewer
pip install -r requirements.txt
python run.py                      # opens the desktop window (or the browser)
```

The welcome screen opens each example in one click (*a drone flight · the same mission flown twice ·
three car runs to compare · an ArduPilot flight log*), or press **Ctrl+O** and open the files in
[`examples/`](examples):

| File | Try |
|---|---|
| `examples/run_012.csv` | click *Speed*, *RPM*, *Throttle*, *DriveMode* into a 2 × 2 layout; press **Space** and **D** for two cursors |
| `examples/run_012.csv` + `run_013.csv` + `run_014.csv` | open all three, then **Compare** in the side rail |
| `examples/uav_flight.csv` | **Templates ▾ → Position on the map & 3D**, then press **P** to play |
| `examples/uav_flight.csv` + `uav_flight_windy.csv` | the same mission flown twice, the second in a cross-wind: both tracks on the map, **Compare** shows where they differ (roll, ground speed, battery) |
| `examples/copter_flight.bin` | an ArduPilot quad-copter flight: the start card suggests *ArduPilot · Full review* and points at the vibration burst it found; the **Log** button has the events, parameters and the whole health check |
| a report per file | `python cli.py report --template "ArduPilot · Full review" --out reports/ logs/*.bin` (HTML, `--format pdf` or `docx`; `python cli.py templates` lists them) |
| pass / fail in CI | `python cli.py check examples/run_01*.csv --checks examples/checks.json --junit results.xml` - exit code 1 when a limit is broken, 2 when a file or signal is missing; `--template NAME` uses the limits saved in a template |
| against a golden run | `python cli.py compare examples/run_012.csv examples/run_014.csv --tol-abs 15` - every shared signal, the most different first; outside the tolerance = exit code 1 |
| your own format | `python cli.py readers --example` writes `~/.signalviewer/readers/example_kv_reader.py`: a function marked `@reader(extensions=[".kv"])` that returns the time and the signals; files of that type then open like the built-in ones |
| raw binary packets | `python cli.py readers --example-icd examples_run.tlm` writes a layout (`example_bench.icd.json`: sync, ids, fields with type / scale / unit / bits / names) and a recording; open the `.tlm` like any file |
| live data | ArduPilot SITL or MAVProxy on UDP 14550, then **Live ▾ → MAVLink → Connect and record** |

The demo files are synthetic and are regenerated by `python tools/make_demo_data.py` (the .bin by
`tools/make_example_bin.py`, a real DataFlash log; `tools/make_test_bin.py` makes test logs of any length).

---

## Install

- **Windows:** `SignalViewer-Setup-X.Y.Z.exe` from the [latest release](https://github.com/DavidAlpert11/SignalViewer/releases/latest) (installs for you only, no administrator rights), or the portable `.zip`. **Linux / macOS:** the `-portable.7z` for your system.
- **Python 3.9+:** `pip install signalviewer`, then `signalviewer` - every reader and report; it opens in your browser, `pip install "signalviewer[desktop]"` gives it its own window. Short of disk space? `pip install signalviewer-lite` is the core (about 350 MB instead of 760) with the rest as extras (`signalviewer-lite[ros]`, `[parquet]`, `[all]`…); a file that needs one says which. Install one of the two, not both.
- **From source:** `pip install -r requirements.txt` and `python run.py`.

**Nothing needs the internet at run time** - the packages carry Python, every library, the UI, the
map and the 3D terrain. The packages are not code-signed yet: on the first start Windows may say
*Windows protected your PC* (*More info → Run anyway*) and macOS may refuse to open the app
([what to do](https://davidalpert11.github.io/SignalViewer/install/#first-start-windows-and-macos-warnings)). Building the installer and the portable packages yourself, and running from
source: [Install](https://davidalpert11.github.io/SignalViewer/install/).

## Command line and CI

```bash
signalviewer-cli export flight.bin --signals "ATT.Roll,ATT.Pitch" --out roll.csv
signalviewer-cli report --template "ArduPilot · Full review" --out reports/ logs/*.bin
signalviewer-cli check  runs/*.csv --checks checks.json --junit results.xml     # exit 1 on a broken limit
signalviewer-cli compare golden.csv new/*.csv --tol-pct 2 --allow-outside 0.5   # against a golden run
signalviewer-cli validate                                                       # the numerical validation, here
```

```python
import signalviewer as sv
t, roll = sv.load("flight.bin").signal("ATT.Roll")
sv.show(t, {"roll x2": 2 * roll})          # into the open app
```

More - the checks and tolerances files, your own readers, binary layouts, CAN: [Command line, Python and formats](https://davidalpert11.github.io/SignalViewer/command-line/).

## Where it fits

| You mostly… | A good fit | Where Signal Viewer adds |
|---|---|---|
| judge test runs, flight logs and simulation output, often offline | **Signal Viewer** | – |
| stream ROS topics live | PlotJuggler, Foxglove | comparing recorded runs, pass / fail, reports (it reads their `.mcap`, `.ulg`) |
| work inside MATLAB / Simulink | Simulation Data Inspector | no MATLAB licence, flight logs and CAN next to the `.mat` ([a worked example](docs/sim-vs-flight.md)) |
| review one ArduPilot / PX4 flight online | UAV Log Viewer, PX4 Flight Review | offline, several flights side by side, your own limits in CI |
| write the final analysis as a script | Python / MATLAB | a quick look first; `sv.load()` / `sv.show()` go both ways |

Nothing leaves the PC: no account, no telemetry; English and Hebrew.

## Documentation

[The documentation site](https://davidalpert11.github.io/SignalViewer/) - the [user guide](docs/GUIDE.md) ([עברית](docs/GUIDE.he.md)), [what works](docs/features.md)
(every feature and the keyboard), [command line and formats](docs/command-line.md), [install and
build](docs/install.md), [offline map and 3D](docs/maps-and-3d.md), [performance](docs/performance.md),
[known limitations](docs/limitations.md), [**validation**](docs/validation.md) (every computation checked against a reference), [gallery](docs/gallery.md), [development](docs/development.md).
The same guide is in the app: *Help → User guide* (F1). Changes: [CHANGELOG](CHANGELOG.md).
Found a problem or want to help? *Help → Report a problem…* in the app, or [CONTRIBUTING](CONTRIBUTING.md).

## בעברית בקצרה

<div dir="rtl">

**Signal Viewer** – אפליקציה לצפייה, השוואה ודוחות על נתוני זמן: ריצות ניסוי, לוגים של טיסה, תוצאות סימולציה,
לוגים של CAN והקלטות בינאריות. עובדת כולה בלי אינטרנט, והקבצים לא יוצאים מהמחשב.

**התקנה**

- **Windows:** קובץ ההתקנה `SignalViewer-Setup-X.Y.Z.exe` מ־[השחרור האחרון](https://github.com/DavidAlpert11/SignalViewer/releases/latest) (בלי הרשאות מנהל), או ה־zip הנייד.
- **Python:** <code dir="ltr">pip install signalviewer</code> ואז <code dir="ltr">signalviewer</code> (נפתח בדפדפן; חלון משלו: <code dir="ltr">pip install "signalviewer[desktop]"</code>).
- **מקוד המקור:** <code dir="ltr">pip install -r requirements.txt</code> ואז <code dir="ltr">python run.py</code>.

**מה אפשר לעשות**

- לגרור קבצים לחלון: CSV, ‏MATLAB, לוגים של ArduPilot ו־PX4, ‏MAVLink, ‏ROS 2, ‏HDF5, ‏Parquet, ‏CAN עם קובץ ‎.dbc.
- לבנות תצוגה: עד 9 גרפים מקושרים בטאב, שני סמנים עם הפרש וסטטיסטיקה, FFT, ספקטרוגרם, מפה ותלת־ממד.
- להשוות ריצות: כל הסיגנלים המשותפים מדורגים לפי מידת השוני, יישור זמן אוטומטי, אותו מקטע בכל ריצה – גם סימולציה מול הטיסה שלה.
- לחשב: נוסחאות, מסננים, נגזרות ואינטגרלים – גם על סיגנלים רבים בבת אחת – ופעולות Python משלכם.
- לשתף: דוחות HTML, ‏PDF ו־Word, סשנים ותבניות.
- לבדוק אוטומטית ב־CI: הפקודות <code dir="ltr">signalviewer-cli check</code> ו־<code dir="ltr">compare</code> מחזירות עבר/נכשל ו־JUnit XML.
- לסמוך על המספרים: כל חישוב נבדק מול ערך ייחוס (<code dir="ltr">signalviewer-cli validate</code>), והקוראים נבדקו על לוגים של כלי טיס אמיתיים.

**מדריך מלא בעברית:** [docs/GUIDE.he.md](docs/GUIDE.he.md), וגם בתוך האפליקציה: עזרה ← מדריך למשתמש (F1).
מה חדש בכל גרסה: [CHANGELOG](CHANGELOG.md).
מצאתם בעיה? עזרה ← דיווח על בעיה… באפליקציה. רוצים לתרום? [CONTRIBUTING](CONTRIBUTING.md).

</div>

## License

Signal Viewer is released under the [MIT License](LICENSE): free to use, change and ship, also
commercially, as long as the copyright notice stays with it.

It ships with third-party parts under their own licences: uPlot (MIT,
`backend/app/report_assets/uPlot.LICENSE`), the report fonts (SIL Open Font License,
`backend/app/report_assets/fonts/OFL-LICENSE.txt`), CesiumJS (Apache-2.0), and map data from
OpenStreetMap (© OpenStreetMap contributors, ODbL), Natural Earth (public domain) and the AWS
Terrain Tiles (see [Offline map data](docs/maps-and-3d.md#offline-map-data)). Python and JavaScript libraries keep
their own licences (`requirements.txt`, `frontend/package.json`).
