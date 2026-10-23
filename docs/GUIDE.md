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
- **A new run with the work you did on another:** right-click the file you worked on → **Add a run
  with the same work…**, choose the new file. It gets the same changes (ƒ), the same new signals and
  the same place in the plots - on the same plots, to compare, or in a copy of each tab. Do it again
  for a third run, and a fourth.
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

## 12. When something goes wrong

- **Help → Copy error details** copies the version, the system and the end of the log; paste it
  into your report. Nothing is sent automatically.
- **Help → Report a problem…** copies the same details and opens the bug report form on GitHub in
  your browser - paste them there.
- **Help → Keyboard shortcuts** (?) lists every key and mouse gesture.
- Windows warns about an unknown publisher on the first start: *More info → Run anyway*.
- macOS refuses to open it the first time: right-click → *Open*, or run
  `xattr -dr com.apple.quarantine SignalViewer` once.
