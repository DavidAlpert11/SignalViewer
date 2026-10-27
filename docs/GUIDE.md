# Signal Viewer – user guide

Signal Viewer shows recorded signals – test runs, flight logs, simulation output – as plots you can
zoom, measure and compare. Everything runs on your computer; nothing is sent anywhere.

## 1. Start

- **Windows:** install `SignalViewer-Setup-X.Y.Z.exe` (for you only, no administrator rights), or
  extract the portable `.zip` and double-click *Signal Viewer.bat*.
- **Linux / macOS:** extract the `-portable.7z` and run `SignalViewer/SignalViewer`.
- The first screen offers **examples** (a drone flight, the same mission flown twice, three car runs,
  an ArduPilot log). One click opens one ready to look at – the quickest way to learn the app.

## 2. Open your files

- **+ Open files** in the file list (Ctrl+O), or drop files on the window. CSV and text tables, MATLAB `.mat`,
  ArduPilot `.bin`, PX4 `.ulg`, MAVLink `.tlog`, ROS 2 `.mcap`, HDF5 and Parquet are read directly.
- From Windows Explorer: right-click a file → **Open with → Signal Viewer**. If the app is already
  open, the file opens in it.
- **Ctrl+P** (recent and favourites) lists the files and folders you used lately.
- A CSV with an unusual layout: tick *Show import options before opening* in the open dialog to choose the delimiter,
  the time column and the header row, with a live preview.
- **The time axis of an open file** (right-click the file → *Time axis…*): another column as its time
  (CSV, MAT, Parquet), its unit (*ms → s*, *s → min*… or any scale), and its offset. The dialog says
  first what changes: a column that goes up and down, repeated or missing values, new signals computed
  against time (derivative, integral, filters), plots that show the column. One Undo puts it all back.

Each file gets a **colour and a short tag** (A, B, C…). Signals of the same name from several files
are told apart by them.

## 3. The screen

- **Left:** the panels – *Data* (the open files and their signals), *Create signals*, *Compare runs*,
  *Report*, and for flight logs *Flight log* and *Fleet*.
- **Middle:** the plots of the current tab. Tabs are at the top; the layout button (1 × 1) splits a
  tab into rows and columns.
- **Bottom:** the timeline – play, the time shown, the cursor. Time is written in seconds as
  recorded, like the axes; *Settings* (the gear, Ctrl+,) can show a clock from the start instead,
  and holds the theme and the text size.
- **Right:** the Inspector – values at the cursor, statistics, the selected signal's settings.

## 4. Plot

- Click a signal in the list to add it to the **active plot** (the one with the coloured frame), or
  drag it onto any plot. Drop on a plot's right or bottom edge to make a new plot there.
- The button next to the plot's title (**Time ▾**) changes the plot's type: Time, X-Y, XYZ, Map, 3D,
  FFT, Spectrogram, Envelope (many runs of one quantity), Video.
- **Right-click a legend chip** for its options: second value axis, show as states, move, remove…
- **Right-click in the plot** for: cursor here, note here, previous zoom, show everything, export
  the data, save or copy the image, axis limits.
- **Conditions** (rail → *Investigate*): the moments where something holds - `Speed > 30`,
  `abs(Vz) > 5 and Mode == "AUTO"` - in every open file that has those signals. Put both cursors
  around something odd and press **Find similar** on the bar above them: the condition is written
  for you, with the count as you change it. Click a condition's name (or press `]` / `[`) to step
  through its stretches; the one in focus is shaded, the others are thin strips along the top.
- **The stretches of a condition** (click its name): a table of them under the list (sort, click to go
  there), **Together in a new tab** - all of them on top of each other from their start, end or peak -
  and **What differs inside**: the signals that are most different inside the stretches than outside.
- **What changed first?** On the selection bar: the signals in the order they left their usual
  range around the span - candidates, not causes - and the lag between any two of them.
  Try it all on the example *find out what went wrong*: [the tutorial](investigate-tutorial.md).
- **Runs × conditions** (button under the conditions): every open run against every condition, with
  what tells the runs apart (a payload, a gain, the number in the file name). The odd run is marked; a
  click opens it at the stretch. *Open a folder of runs…* brings in a whole Monte-Carlo set.
- **Findings and the report**: give a note a status in the Inspector (open, explained, fault,
  rejected hypothesis) - it keeps the view it was found in. The Investigate panel keeps the steps you
  took; tick the ones for the report. *Include the investigation* in the Report panel puts the
  findings (with their plots), the rejected hypotheses, the steps, the conditions and how to
  reproduce it before the plots.
- **State lanes** (flight mode, gear…): right-click the lane, its chip or the signal in the list to show
  it on this plot only, on every plot of the tab, or on every time plot of every tab - or remove it.
  *Always as a state* makes a signal a lane wherever it is added, in every file.
- **Map and 3D objects:** *Add object* on a Map or 3D plot. Its position and attitude are filled in
  from the signals' names; to choose another, type part of its name in the field. Beside each field
  you see the unit the signal is in, and **ƒ** changes that signal on the spot – e.g. angles that
  turn out to be in radians: ƒ → *Convert units* → rad → deg. Or leave the signal as it is and set
  the object's *Angle unit* to radians: that only changes how it is drawn. The attitude can be three
  angles or a quaternion (*Attitude from*).
- **A position in ECEF, NED or ENU** (metres): *Position from* in the object dialog, then the three
  components; NED / ENU also need the reference point - the first sample of a latitude / longitude /
  altitude, or numbers typed in (a launch point). **Smooth position (s)** averages a noisy position
  over that many seconds (centred, never across a gap). Both make new signals when you save (they are
  in *Create signals* and the session); the recorded ones do not change. Any vector (a velocity, say)
  can be smoothed the same way: *Create signals → Several → Smooth a vector*.

## 5. Zoom and move

| Do | To |
|---|---|
| Drag on a plot | zoom into that time range |
| Mouse wheel | zoom around the pointer (Shift: values only, Ctrl: both, Alt: time only) |
| Wheel over an axis | zoom only that axis |
| Alt + drag, or middle-drag | move along the time axis |
| Double-click, or R | show everything |
| Backspace | the previous zoom |

With **Link X** on (the default) every plot of the tab shows the same time; **Link Y** does the same
for the values.

## 6. Measure

- **Space** turns the cursor on; click to place it; ← → step sample by sample.
- **D** adds a second cursor: the Inspector then shows the difference and the statistics between
  the two (min, max, mean, RMS…).
- Put the cursor on a moment and press **N** to write a note there; with two cursors the note covers
  the time between them (shaded). Notes show on every time plot and in the report.

## 7. Compare runs

- Open the runs together; plots show each signal once per file, in the file's colour.
- **Compare runs** (left) compares each signal with a baseline run (or the mean of the runs): RMS and
  largest difference, correlation, a tolerance; its table lists every signal found in two or more
  files, the worst first.
- Runs recorded with a time shift: right-click a file → **Align time with another file**.
- **The work you did on one file, for another:** right-click the file you worked on → **Copy the work
  to another file…**, choose a file that is open already or one to open, and what to copy: its
  changes (ƒ), the signals made from it, its signals in the plots (on the same plots to compare,
  beside each plot in the same tab, or in a copy of each tab) - any of them. Again for a third file, and a fourth.
- **Undo one file's work only:** right-click it → **Clear this file**: its signals out of the plots,
  its changes undone, the signals made from it deleted - one of them or all. The other files keep
  theirs.
- **Keep the files together** with the two link buttons at the top of the file list: **Link plots**
  (a signal added or removed in one file is added or removed in all of them) and **Link operations**
  (a change on a signal, or a new signal made from it, is made on the same signal of every file).
  Each one is on or off by itself.

## 8. Create signals

**Create signals** (left) makes new signals from existing ones: a formula with the signals' names
(`Speed * 3.6`, `deriv(Altitude)`, `lowpass(Roll, 5)`…), filters, unit changes, frame conversions,
a Python function of your own. They
behave like recorded signals and are kept with the session. With *Two signals* and A − B the panel
also tells how far apart A and B are – overall and for each stretch of a state such as the flight
mode (a simulation against the flight, a model against the test).

**An expression of x with other signals:** wherever you write an expression of `x` (*Change this
signal…*, or *One signal → Expression in x* here), another signal is written by its name:
`sin(x) + Speed`. It is the signal of the **same file** as `x` - for several selected signals, each
one's own file - as read from the file, so on a group that includes Speed itself, every one sees the
same Speed. Copied or linked to another file, it reads that file's Speed. To take it from **one
particular file** for all of them, name the file: `x + {run_b.csv:Speed}`. Names with spaces or
brackets go in braces: `{Speed [km/h]}`.

A new signal made from two files belongs to the file of `x` (or, in a Formula, of the names written
without a file); a source written with its file - and the baseline of a *Compare runs* difference -
is kept. So when the work is copied to a new run, the new run gets its own signal against the same
fixed source.

**Convert units:** right-click a signal → *Change this signal…* → *Convert units* (rad → deg,
m/s → km/h, m → ft, °C → °F…; the ones from the signal's unit first). The values and the unit
shown change together – on the axis, in the list, in the legend – and it can be undone like any change.

## 9. Keep and share your work

- **Save session** (the disk icon at the top left, Ctrl+S; opening one: the folder icon next to it, Ctrl+Shift+O) keeps everything – files, tabs, plots, zoom, notes. The app also
  restores your last work by itself when it starts.
- **Templates** (top bar): save a tab or a whole set of tabs as a template, and open it later on
  other files with the same signals.
- **Report** (left): a report of the plots, statistics and notes – previewed in the app, saved as
  interactive HTML, PDF or Word.
- A plot's **⋯** menu: export the data (CSV), save the image (PNG, SVG), copy the image.
- **Clear ▾** (the top bar): this tab's plots, the other tabs, all
  tabs, or all the work on the data - tabs, notes, derived signals and edits - while the files stay
  open. Each is undone with **Undo** in the message or Ctrl+Z. *Everything* also closes the files
  (it asks first).

## 10. Flight logs

ArduPilot and PX4 logs open with ready views (attitude, rates, vibration, battery, GPS, the map and
the flight modes as coloured lanes) and a **health check** that points at what is worth a look. The
*Flight log* panel lists the messages, events and parameters.

## 11. Live data

**Live** (top bar) follows files that are still being written – a CSV growing, a MATLAB file saved
again and again – and can connect to a MAVLink stream. From Python, `signalviewer_push.show(...)`
sends arrays straight into the running app.

While live, the time (cursor) stays at the newest data, so the values read at it and the objects on
the map and in 3D move with each update; move it back to look at a moment, press **End** to follow
again. To try it without a logger: `python tools/live_demo.py` writes an aircraft and a ship that
keep moving – open both files, add an object from each, press Live.

## 12. When something goes wrong

- **Help → Copy error details** copies the version, the system and the end of the log; paste it
  into your report. Nothing is sent automatically.
- **Help → Report a problem…** copies the same details and opens the bug report form on GitHub in
  your browser - paste them there.
- **Help → Keyboard shortcuts** (?) lists every key and mouse gesture.
- **A blank window**: an offline computer may have a Microsoft Edge WebView2 too old for the app (it
  needs version 87 or newer). The app then opens in a newer Edge or Chrome as a window of its own, or
  says what to install. A white or black window on a virtual machine / remote desktop / old graphics
  driver: start **Signal Viewer (safe graphics)**. *Help → About* shows which engine draws the app.
- Windows warns about an unknown publisher on the first start: *More info → Run anyway*.
- macOS refuses to open it the first time: right-click → *Open*, or run
  `xattr -dr com.apple.quarantine SignalViewer` once.
