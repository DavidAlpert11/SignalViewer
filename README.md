<p align="center">
  <img src="assets/png/icon-128.png" width="96" alt="Signal Viewer icon">
</p>

<h1 align="center">Signal Viewer</h1>

<p align="center">
  <b>A fast, offline desktop app for exploring, comparing and reporting on time-series data</b><br>
  CSV · Parquet · MATLAB .mat · ArduPilot .bin · MAVLink .tlog · PX4 .ulg · ROS 2 .mcap · HDF5 · CAN + .dbc
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/UI-React%20%2B%20TypeScript-61DAFB?logo=react&logoColor=black">
  <img alt="Platforms" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey">
  <img alt="Offline" src="https://img.shields.io/badge/runs-100%25%20offline-2ea44f">
  <img alt="Languages" src="https://img.shields.io/badge/UI-English%20%7C%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA-orange">
  <a href="https://davidalpert11.github.io/SignalViewer/"><img alt="Docs" src="https://img.shields.io/badge/docs-site-0A7BBB"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
</p>

<p align="center">
  <img src="docs/images/01_overview.png" alt="Signal Viewer: four linked plots, two cursors and statistics between them" width="100%">
</p>

Signal Viewer is a Python computation core (FastAPI + NumPy) with a React/TypeScript UI, in one
native desktop window. It opens multi-gigabyte recordings in seconds, keeps every sample available
at full resolution, and works with **no internet connection at all** – including the map and the
3D globe.

- **Plot anything quickly** – up to 9 linked plots per tab, Time / X-Y / FFT / Spectrogram / Map / 3D modes, two cursors with Δ and statistics, zoom history, notes.
- **Compare runs** – every shared signal ranked by similarity, automatic time alignment, a full comparison table, CSV export – over the whole runs or **the same segment of each** (the 2nd AUTO of every flight).
- **Understand flight logs** – ArduPilot, MAVLink and PX4 logs read directly: flight modes, events, parameters and an automatic **health check**; the first log you open gets a suggested view and its three worst findings.
- **Watch it live** – MAVLink from a vehicle or a simulator over UDP, TCP or a serial radio, recorded to a `.tlog` as it arrives and followed like any growing file.
- **See where it happened** – an offline map and a 3D terrain view with the vehicle model, its attitude and its track, synchronised with the timeline.
- **Do the math** – formulas such as `2*Speed - RPM/95` with autocomplete, filters, derivatives and integrals that update when the data changes; **coordinate frames** (NED / ENU / body / ECEF / LLA, suggested from the signal names); motor orders on spectra.
- **Share the result** – interactive offline HTML, PDF and Word reports – also **one per file from the command line**; sessions and reusable templates.
- **Into the test process** – `signalviewer-cli check` (limits as pass / fail, per flight mode) and `compare` (against a golden run) with exit codes and JUnit XML for CI.
- **Any recording** – CAN logs with a `.dbc`, raw binary packets described by a layout (ICD), and your own formats as a short Python reader.

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
git clone https://github.com/DavidAlpert11/SignalViewer.git
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
- **Python 3.9+:** `pip install "signalviewer[all]"`, then `signalviewer`. A plain `pip install signalviewer` is the core (about 350 MB instead of 760); the extras `[parquet] [hdf5] [mavlink] [px4] [ros] [reports] [desktop]` add the rest, and a file that needs one says which.
- **From source:** `pip install -r requirements.txt` and `python run.py`.

**Nothing needs the internet at run time** - the packages carry Python, every library, the UI, the
map and the 3D terrain. Building the installer and the portable packages yourself, and running from
source: [Install](https://davidalpert11.github.io/SignalViewer/install/).

## Command line and CI

```bash
signalviewer-cli export flight.bin --signals "ATT.Roll,ATT.Pitch" --out roll.csv
signalviewer-cli report --template "ArduPilot · Full review" --out reports/ logs/*.bin
signalviewer-cli check  runs/*.csv --checks checks.json --junit results.xml     # exit 1 on a broken limit
signalviewer-cli compare golden.csv new/*.csv --tol-pct 2                        # against a golden run
```

```python
import signalviewer as sv
t, roll = sv.load("flight.bin").signal("ATT.Roll")
sv.show(t, {"roll x2": 2 * roll})          # into the open app
```

More - the checks and tolerances files, your own readers, binary layouts, CAN: [Command line, Python and formats](https://davidalpert11.github.io/SignalViewer/command-line/).

## Where it fits

Signal Viewer is for the engineer who has **recordings to judge**: several runs of the same test, a
flight log after a flight, a simulation next to the real thing - and often a closed network. What it
brings together, in one offline window and on the command line:

- **comparing runs** first-class: every shared signal ranked by how different it is, automatic time
  alignment, the same segment of each run (the 2nd AUTO of every flight), differences per flight mode;
- **from data to a verdict**: limits and golden-run tolerances as pass / fail, a report per file -
  the same in the app and in CI;
- **many sources, one view**: CSV, MATLAB, ArduPilot / PX4 / MAVLink logs, ROS 2, HDF5, Parquet, CAN
  with a `.dbc`, your own binary packets and formats;
- **offline and local**: nothing leaves the PC, no account, no telemetry; English and Hebrew.

If you mostly stream ROS topics live, a robotics tool such as PlotJuggler or Foxglove fits that
better; if your work lives inside MATLAB, its Simulation Data Inspector is next to your models. Signal
Viewer reads what those tools record (`.mcap`, `.ulg`, `.mat`) when you need to compare and report.

## Documentation

[The documentation site](https://davidalpert11.github.io/SignalViewer/) - the [user guide](docs/GUIDE.md) ([עברית](docs/GUIDE.he.md)), [what works](docs/features.md)
(every feature and the keyboard), [command line and formats](docs/command-line.md), [install and
build](docs/install.md), [offline map and 3D](docs/maps-and-3d.md), [performance](docs/performance.md),
[known limitations](docs/limitations.md), [gallery](docs/gallery.md), [development](docs/development.md).
The same guide is in the app: *Help → User guide* (F1). Changes: [CHANGELOG](CHANGELOG.md).

## בעברית בקצרה

הפעלה: `pip install -r requirements.txt` ואז `python run.py`.
כשקוד הממשק חדש יותר מהבנייה הקיימת (אחרי pull או patch), ‏`run.py` בונה אותו פעם אחת לבד (נדרש Node.js) לתיקייה `frontend/.local-dist` שגיט מתעלם ממנה.
האפליקציה נפתחת בחלון משלה (או בדפדפן), והקבצים לא יוצאים מהמחשב.
גררו קבצי CSV, MAT או לוגים של ArduPilot (‎.bin) לחלון, לחצו על סיגנל כדי להוסיף אותו לגרף, ורווח מפעיל את הסמן.
זום: X / Y / XY בתפריט הזום בסרגל (המקש Z מחליף). לגרירה אחת: Shift = ערכים בלבד, Ctrl = מלבן, ‏Alt = הזזה (pan).
גלגלת מעל ציר עושה זום רק בו; Shift+גלגלת בערכים בלבד, Ctrl+גלגלת בשניהם. כפתור פריסה אחד, וגרירת סיגנל לקצה של גרף מפצלת אותו.
רענון כל הקבצים: הכפתור ⟳ בפאנל הקבצים או F5. "חי" מרענן הכל ואז עוקב אחרי הקבצים שממשיכים לגדול;
בחץ שליד הכפתור: עצירה אוטומטית אחרי זמן ללא נתונים, ומה לעשות עם קבצים חדשים באותה תיקייה.
עמודות טקסט (מצבים) ומצבי טיסה מוצגים כרצועות צבעוניות עם שם המצב.
לוג של ArduPilot: כפתור "לוג טיסה" מופיע בסרגל הצד רק כשפתוח קובץ ‎.bin – אירועים והודעות (לחיצה מזיזה את הסמן לרגע),
סימון אזהרות ושגיאות על הגרפים, ופרמטרים: חיפוש, שונו בטיסה, לא ברירת מחדל, השוואה מול לוג אחר ושמירה כ־‎.param.
לוגים: ‎.bin (ArduPilot), ‎.tlog (טלמטריית MAVLink) ו־‎.ulg (PX4); הקלטות ROS 2 / Foxglove ‏(‎.mcap, בלי התקנת ROS) וקובצי HDF5. לוג של הבקר וטלמטריה של אותה טיסה מזוהים ומיושרים בזמן –
הודעות שנושאות את שעון הבקר ממוקמות בזמן המדויק שלהן. בפאנל הלוג: תקינות, אירועים, פרמטרים ותצוגות מוכנות. ספקטרוגרם כמצב גרף,
הערות (N), סטטיסטיקה "רק בזמן ש…", ו־param("NAME") בנוסחאות.
מפה: רחובות, לוויין, טופוגרפית ואפורה בהירה/כהה – נשמרות בדיסק לעבודה בלי אינטרנט; בלי אינטרנט: גבולות ושמות מדינות.
מצב הטיסה יכול להופיע בכל הגרפים בלשונית (קליק ימני על המצב). תצוגות השוואה של לוג הבקר מול הטלמטריה.
תבניות: תבנית היא אוסף לשוניות, ואוסף יכול לכלול תבניות אחרות. כל סיגנל שייך ל"משבצת קובץ", וכשפותחים תבנית
בוחרים קובץ לכל משבצת (עם הצעה אוטומטית). כל תבנית היא קובץ JSON בתיקייה ~/.signalviewer/templates –
עריכה, ייצוא וייבוא מתוך ספריית התבניות. "מבט מהיר" ו"השוואת קבצים פתוחים" מתאימות לכל קובץ.
יישור זמן בין כל שני קבצים (CSV, ‏MAT, לוגים): אוטומטית לפי סיגנלים באותו שם, לפי שני סיגנלים לבחירה, לפי רגע בסיגנל
(עלייה דרך רמה, קפיצה, שינוי מצב…) או לפי שני הסמנים – קליק ימני על הקובץ ← יישור זמן מול קובץ אחר.
בנייה לחלונות: הפעילו `build_windows_portable.bat` – נוצר `dist\SignalViewer-Windows-portable.7z` שלא צריך התקנה
(Windows 11 פותח 7z ישירות; ב־Windows 10 צריך 7-Zip. לקובץ zip: ‎`--format zip`).
בנוסחאות: השלמה אוטומטית של פונקציות (עם הסבר), משתנים וסיגנלים, והצגת הארגומנטים של הפונקציה שבה נמצא הסמן.
Ctrl+K פותח חיפוש של כל הפקודות והסיגנלים. בורר השפה נמצא בסרגל העליון.
חדש ב־1.3: MAVLink חי (UDP / TCP / פורט טורי, מוקלט ל־‎.tlog תוך כדי), השוואת אותו מקטע בכל הריצות (למשל ה־AUTO השני של כל טיסה),
דוח לכל קובץ משורת הפקודה (`python cli.py report --template … --out … קבצים`), המרת מערכות צירים (NED / ENU / גוף / ECEF / LLA, מוצעת לפי
שמות הסיגנלים), גרף XYZ, סדרי מנוע בספקטרום, כרטיס פתיחה חכם לקובץ הראשון, וברשימת הקבצים יחידה, קצב דגימה ותמונה קטנה לכל סיגנל.
חדש ב־1.4: מסנני Low-pass / High-pass אמיתיים (Butterworth בלי השהיה; הגרסאות הקודמות השתמשו בממוצע נע, ולכן ערכים מסוננים בסשנים ישנים ישתנו מעט),
קבצים פגומים (קטועים, בתים פגומים, בלוק אפסים) נפתחים עם מה שאפשר לקרוא, Help ← "העתקת פרטי שגיאה" לדיווח על תקלות
(הלוג נשמר רק במחשב, ב־‎~/.signalviewer/logs), ורישיון MIT.
חדש ב־1.5: וידאו מסונכרן עם הנתונים (מצב גרף Video), פעולות Python משלכם ושליחת נתונים מ־Python, תצוגת Fleet על כל לוגי הטיסה
(חיפוש לפי ממצא או מספר, מגמה לאורך הטיסות), וקבצי ROS 2 ‏(‎.mcap), ‏HDF5 ו־Parquet.
חדש ב־1.6: שתי דוגמאות חדשות במסך הפתיחה – אותה משימה בשתי טיסות (רגילה וברוח צד) ולוג טיסה של ArduPilot עם ממצא לחפש,
"יצירת סיגנל ▸" אחד בתפריטי הסיגנל, ותיקונים ל־1.5: הדוגמאות חזרו לחבילת Windows, מספר הגרסה ב־Help, תאריך הטיסה ב־Fleet
ללוגים של ArduPilot, ו־Undo של "מחיקת כל הנגזרים" שכבר לא מוחק עבודה שנעשתה אחריו.
חדש ב־1.7: לכל קובץ צבע ותג קצר (A, B, C…) במקרא, בסטטיסטיקה ובבוחרי הסיגנלים - סיגנלים באותו שם משני קבצים
נצבעים לפי קובץ; מועדפים ותיקיות אחרונות בדיאלוג הקבצים ו־Ctrl+P לפתיחה מהירה; ציר ערכים שני (ימני) לסיגנל
ביחידות אחרות; דוגמאות ותבניות שנפתחות מוכנות בלחיצה אחת; עמודות עם עמודת זמן משלהן (Speed + Speed_time,
msg.time_boot_ms) נקראות כך; מצב Live עוקב גם אחרי קובץ MATLAB שנשמר שוב ושוב; תבניות מובנות בעברית.
חדש ב־1.8: מתקין ל־Windows ו־zip בכל שחרור, "פתח באמצעות" מהסייר (לחלון שכבר פתוח), ‏`pip install signalviewer`, ומדריך
למשתמש בעברית ובאנגלית (F1); תפריטי קובץ ועזרה, כפתור אחד לסוג הגרף והמקרא לידו (יותר מקום לעקומות), תפריט קליק ימני
בכל גרף, והגדרות שנשמרות בין הפעלות; הערות על טווח זמן, וכמה רחוקים שני סיגנלים לכל קטע של מצב טיסה; ותיקונים:
סטטיסטיקה שיכלה להציג מספרים של סיגנל אחר, גרפים בעמודה שלא היו מיושרים, וזום בטאצ'פד.
חדש ב־1.6.1 (ליטוש): כל הטאבים נגישים גם כשיש הרבה (רשימת "כל הטאבים", Ctrl+PageUp/PageDown), לכל קובץ צבע משלו
ב־Compare open files, השוואת ריצות מחשבת זוויות (Yaw / Heading) סביב המעגל, Shift+קליק ו־Ctrl+A בדיאלוג הקבצים,
תיקייה אחרונה נפרדת לכל שימוש, קובץ שכבר פתוח נקרא מחדש במקום להיפתח פעמיים, ודיאלוגים ותפריטים שנסגרים ב־Esc.

## License

Signal Viewer is released under the [MIT License](LICENSE): free to use, change and ship, also
commercially, as long as the copyright notice stays with it.

It ships with third-party parts under their own licences: uPlot (MIT,
`backend/app/report_assets/uPlot.LICENSE`), the report fonts (SIL Open Font License,
`backend/app/report_assets/fonts/OFL-LICENSE.txt`), CesiumJS (Apache-2.0), and map data from
OpenStreetMap (© OpenStreetMap contributors, ODbL), Natural Earth (public domain) and the AWS
Terrain Tiles (see [Offline map data](docs/maps-and-3d.md#offline-map-data)). Python and JavaScript libraries keep
their own licences (`requirements.txt`, `frontend/package.json`).
