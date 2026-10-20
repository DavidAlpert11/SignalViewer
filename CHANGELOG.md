# Changelog

## 1.9.0 – unreleased

### Changed
- **Python and the command line take signal names the way people write them:** `rec.signal("ATT.Roll")` finds *ATT.Roll [deg]* - the unit may be left out and the case does not matter, as long as the name means one signal (two signals with the same name and different units ask for the full name, never a guess). A name that is not there says which names are closest (*Did you mean 'ATT.Roll [deg]'?*). The same in `signalviewer-cli export --signals`.
- **`signalviewer.show(...)`:** with `pip install signalviewer`, sending data from a notebook to the open app is `import signalviewer as sv; sv.show(t, {"altitude": alt})` - no file to copy (the one-file client from *Save the Python client…* still works).

### Fixed
- **The PyPI page shows the pictures:** the README's screenshots, clips and links pointed into the repository and were broken on pypi.org; the package's copy now points at the release on GitHub. The page also links the changelog, the issues and the releases. The README badge says Python 3.9+, as the package requires.

## 1.8.0 – 2026-10-20

Highlights: **easier to get and to start** - a Windows installer and a .zip on every release, *Open with* from Explorer (into the window that is already open), `pip install signalviewer`, and a user guide in English and Hebrew (F1); **a cleaner screen** - File and Help menus, one plot-type button and the legend beside it (more room for the curves), a right-click menu in every plot, Settings that are kept between starts; **new**: notes over a time range and how far apart two signals are per flight-mode stretch; **fixes** that matter for measuring: statistics that could show another signal's numbers, plots in a column that did not line up, trackpad zoom.

### Added
- **How far apart are two signals - simulation and flight, model and test:** *Create signals → Two signals* (A − B) shows the RMS, mean and largest difference over the time both have, and the same for each stretch of a state such as the flight mode; the stretch where they part ways is marked, a click shows it in the plots, a click on the largest difference puts the cursor there.
- **Notes over a time range:** with two cursors on, *N* (or *Note here…* on a right-click) writes a note that covers the time between them - shaded on every time plot, listed as "8 – 22 s" in the Inspector and in the report (HTML, PDF, Word).
- **Settings** (the gear in the top bar, *File → Settings…*, Ctrl+,): theme, text size, and how the timeline writes time. Kept on this computer between starts; opening a session (a colleague's, an old one) no longer changes your theme or text size.
- **`pip install signalviewer`:** the app as a Python package - `signalviewer` starts it, `signalviewer-cli` is the command line, `import signalviewer` reads recordings in scripts and notebooks. Built and checked (installed in a fresh environment and started) on every build; published to PyPI with the releases.
- **A user guide**, in English and Hebrew: twelve short sections from the first start to flight logs and live data. In the app: *Help → User guide* (F1); on GitHub: `docs/GUIDE.md`, `docs/GUIDE.he.md`.
- **Open files from outside:** *Open with* in Windows Explorer (offered by the installer for .bin, .tlog, .ulg, .mcap, .mat, .csv, .parquet and .h5 files; a saved session, .svsession, opens with a double-click) and `SignalViewer file.bin` on the command line. When Signal Viewer is already running the files open **in that window**, which comes to the front – several files chosen together open in one app, not one app each. `--new-window` starts a separate app. Your default programs for those file types are not changed.

### Changed
- **One way to change a signal itself, with one name:** *Change this signal…* (right-click a signal; it is now after Add / New plot) and *Create signals → Change this signal* are the same change (marked ƒ) and are called the same. A file's menu no longer has *Reload from disk* - the ↻ next to the file reloads it, F5 or the panel's ↻ reloads every file.
- **File and Help menus in the top bar.** *File*: open files, recent and favourites, refresh all files, open / save session, clear everything, each with its shortcut (they were three unlabeled icons). *Help*: keyboard shortcuts, the examples, copy error details, about (help was only a small "?" in the status bar).
- **The plot header is one line:** the plot's type is one button with its name (*Time ▾*) instead of nine buttons on every plot, and the legend sits next to it when there is room. In a small window each plot has about half again as much height for the curves.
- **Right-click in a plot** opens its menu: cursor here, second cursor here, note here, previous zoom, show everything, and the plot's options (export, images, axis limits, clear).
- **Downloads:** every release now has the **Windows installer** (`SignalViewer-Setup-X.Y.Z.exe`, for the current user, no administrator rights) and the Windows portable package also as a **.zip** (Windows 10 opens it without 7-Zip), next to the .7z packages, with a short "which file?" note on the release page. The installer is installed and started by the build before it is published.

### Fixed
- **A damaged autosave is kept:** when the last work cannot be read (the computer went off while it was being saved), the app starts empty as before, but now keeps the file as `autosave.damaged.json` and says where - the next autosave no longer overwrites the only copy.
- **Sending data from Python behind a company proxy:** the Python client no longer sends its data to the proxy (the app is on the same computer).
- The Inspector shows a value with as many digits as the legend chip.
- **Choices were forgotten at every start:** the panels' widths, the Inspector open or closed, the file dialog's sort and last folders, the MAVLink address. The app starts on a new port each time and the browser keeps such things per address; they are kept in the app folder now (what the browser still had is taken over once).
- **The timeline wrote time differently from everything else** (2:03.0 where the axes, the cursor and the Inspector said 123.4). It writes seconds as recorded now; the clock from the start is a choice in Settings.
- **Trackpads zoomed far too fast:** every wheel event zoomed by 25 %, and a trackpad sends dozens per gesture. The zoom now follows the size of the scroll (a mouse notch is still about 25 %), one gesture is one step back with Backspace, and a sideways swipe moves along the time axis instead of zooming out. The same in the spectrogram, X-Y, XYZ and map plots.
- **The keyboard-shortcuts list described the mouse wheel wrongly:** Shift + wheel zooms the values, Ctrl + wheel both, Alt + wheel the time; double-click shows everything (time and values).
- Hebrew: the theme button is called "ערכת נושא"; the Inspector button has a translated name.
- **The plot menu (⋯) was cut off in short plots** (several plots in a small window): *Axis limits* and *Clear plot* could not be reached. Menus are now drawn above everything.
- **Plots in a column line up.** With linked time, a plot whose value axis was wider (a unit label, larger numbers, text values) started further right, so the same moment was at a different place in each plot. The plots of a column now share one axis width; a spectrogram spans its signal's whole time like the signal's own plot (it covered only the part where its window fits).
- **An Envelope plot zooms with the tab's time plots** (drag, double-click, Backspace and R as in a time plot); before, its zoom was its own.
- **Statistics could show another signal's numbers.** With *only while* a state has a value, two signals of one file could show the same min / max / mean (one signal's numbers under the other's name); a report with scaled signals and a file reloaded with the same length could do the same. The statistics are now always computed from the signal they are shown for.

## 1.7.0 – 2026-10-19

Highlights: **every file has a colour and a short tag** (A, B, C…) - signals of the same name from
several files are told apart at a glance; **places in the file dialog** (favourite and recent
folders) and **Ctrl+P** quick open; a **second value axis** for signals in other units; examples
and template chips open **ready to look at**; telemetry exports where **each value has its own
time column** are read as such; **live mode** follows a MATLAB file that is saved again and again.

### Added
- **Places in the file dialog** (owner's request): a side column with the folders of the open files, **favourite folders** (pin the folder shown with ★ next to the path; × to unpin; drag to reorder; kept between sessions), **recent folders**, and this computer's home, Desktop, Documents, Downloads and drives. One click goes back to a folder you work in.
- **Ctrl+P – quick open:** type part of a name to open a recent file, or a favourite / recent folder in the file dialog.
- A folder with nothing to open says so, and how many files of other types it holds.
- **Every file has a colour and a short tag** (A, B, C…) (owner's request): with several files open the legend shows the tag in the file's colour instead of a long, cut-off file name, and so do the cursor values, the statistics and the signal pickers. The same signal from two files in one plot is coloured by file automatically; *Colour by file* in the plot's ⋯ menu does it for every signal. Click the tag in the file list to change the colour; *File options ▸ Short tag…* to rename it. Compare runs uses the same colours (unchecking a run no longer recolours the others). Saved in sessions.
- **A second value axis:** a signal in other units (speed and battery voltage) can go on the **right axis** with its own scale and unit - right-click its chip ▸ *To the right axis*; when you add a signal in other units than the plot's, a message offers it. Reports and saved images draw both axes.

- **Examples open ready to look at:** a welcome-screen example opens with its view already applied (the car runs and the two flights compared, the drone flight and the ArduPilot log in their views); Undo goes back to an empty plot.
- **Template chips open in one click** when it is clear which file goes where (right-click a chip for the library with its choices); with a choice to make, the library opens as before.
- **Columns with a time column of their own** (a user's request): in telemetry exports where each value has its own time column - told by the name (*Speed* + *Speed_time*, *ATTITUDE.roll* + *ATTITUDE.time_boot_ms*, or alternating *time, Speed, time, RPM*) - each value is drawn against its own time; no more X-Y plots of value against time. Works for CSV / text and MATLAB files, and for a *.tlog* that is a text table; it can be turned off in *Import options*.

### Changed
- Small windows: the file panel's header fits with several files (the link toggle is an icon); short plots show more value labels.
- In Hebrew, the built-in templates and the tabs they make are named in Hebrew.
- Clearer controls: the file list's signal menu offers **Add to / Remove from the active plot** (and *Scale, offset or function…* instead of *Change the variable…*); the zoom button always says *Zoom: X* (it was a second bare "X" next to *Link X*); *Clear everything* asks with a red *Clear everything* button; Compare runs shows one number per signal (the match %); Create signals: *This signal / Each of several*; *Templates…* left the tab menus (top bar, file panel and Ctrl+K have it).
- After a suggested view is opened, the start card keeps the flight log's findings (each a click from its moment) instead of closing.

### Fixed
- **Live mode with a MATLAB (or ULog / MCAP / HDF5 / Parquet) file that a program saves again and again:** it was shown only once the saving stopped (and live mode could stop itself as "idle" meanwhile); now it is read at least every 2 seconds while it changes. A slow read of a big file is no longer overtaken by the next poll.
- A click on **Create signal ▸** sometimes opened and closed its submenu at once.
- File dialog: **Tab** in the path box completes only what you typed; on a path left as it is, Tab moves to the next control (a keyboard user could not leave the path box).

## 1.6.1 – 2026-10-19

Highlights: a polish release after a review of every button. **Many tabs** are all reachable again
(an *All tabs* list, Ctrl+PageUp / PageDown); **Compare open files** gives every file its own
colour; **Compare runs** handles yaw / heading across north; the file dialog gets **Shift+click
ranges**, **Ctrl+A** and a last folder per use; dialogs and menus close with **Esc**.

### Fixed
- File dialog: a file clicked while the same folder was still being listed (or listed again) stays picked; *Open* no longer stays disabled.
- File dialog: **Shift+click selects a range** and **Ctrl+A** every file shown; saving a session, report or image no longer changes the folder *Open files* starts in, and a first save starts where your data is.
- Opening **several files at once** suggests *Compare open files* for all of them (it suggested a view for the first file only, or nothing), and the reading notes come as one message instead of one per file ("text read as states: DriveMode").
- Opening a file that is **already open** reads it again from the disk instead of adding a second copy without a word; *Open another copy* is offered in the message.
- **Dialogs take the keyboard:** Esc closes the file dialog (and Templates, confirmations) right after it opens, typing filters the list at once, and Tab stays inside the dialog. The layout and zoom pop-ups close with Esc.
- The plot's **⋯ menu** closes with Esc or a click anywhere else (it stayed open until the mouse passed over it).
- **Compare runs** treats yaw / heading / course as angles: 359° and 1° are 2° apart (the yaw of the two example flights showed an RMS of 75.8° instead of 21.8°, and came first as "least similar").
- First run: the template library no longer says *The templates folder is not available*.
- **Many tabs:** every tab can be reached again - an *All tabs* list next to +, the active tab is always scrolled into view, the mouse wheel scrolls the tabs, **Ctrl+PageUp / Ctrl+PageDown** go to the previous / next tab, and the command palette (Ctrl+K) has *Go to tab*. Many tabs no longer squeeze the search box.
- **Compare open files** (and Quick look) drew every signal in the same colour; now each file has its own colour, the same in every plot.

### Inside
- Running the tests no longer fills the developer's own recent files, autosave and uploads.

## 1.6.0 – 2026-10-18

Highlights: **two new examples** on the welcome screen - the same mission flown twice, and an
ArduPilot flight log with something to find - a single **Create signal ▸** in the signal menus, and
fixes for 1.5.0: the examples missing from the Windows package, the version shown in Help, the
flight date in Fleet and an Undo that could throw work away.

### New
- Example: **the same mission flown twice** - a calm flight and the same waypoints in a cross-wind
  (drift off the track, nose into the wind, gusts, more battery drain), for the map with two tracks
  and Compare runs.
- Example: **an ArduPilot flight log** (.bin) - a 4-minute quad-copter flight with every mode from
  STABILIZE to LAND, a mission, and one problem to find: the health check shows a vibration burst
  with clipping, the smart start offers "ArduPilot · Full review".
- Signal menus (file list and plot legend): one **Create signal ▸** with Derivative, Integral and
  *Other operations…*, which opens Create signals with that signal already chosen.
- The welcome screen names all the formats it opens (it still said "CSV or MAT").

### Fixed
- **Examples on the welcome screen are back** in the Windows portable package (the package left the
  example files out, so the "Try an example" line was hidden). An example is offered only when all
  its files are there.
- Help and *Copy error details* show the right version (1.5.0 showed "1.4.0").
- Fleet: flights from current ArduPilot firmware are dated by the GPS time in the log again (they
  got the file's date, wrong once the log had been copied). Folders already in Fleet: *Update* them.
- *Delete all derived signals*: its Undo now disappears with your next change instead of staying -
  clicking it later used to throw away what you had done since.

### Inside
- The app's state code is split by area (no change in behaviour); the backend's type check has no
  exceptions left.

## 1.5.0 – 2026-10-18

Highlights: **video synchronised with the data**, **your own Python operations** and **sending data
from Python**, the **Fleet** view over all your flight logs, and **ROS 2 (.mcap), HDF5 and Parquet**
files. (The 1.5.0 packages show "1.4.0" in Help - the version files were not updated for the tag.)

- **Video with the data**: a plot can now show a video of the test (plot mode *Video*: mp4, webm,
  mov…). It follows the cursor and the timeline (play plays it too), and playing or seeking in the
  video moves the cursor. *Line up…* lets the video and the cursor be put on the same moment
  (take-off, a step) separately, *Lock here* keeps them together from then on; the offset is saved
  with the session and can be typed.
- **Your own Python operations** (*Create signals > Python*): every function marked `@operation`
  in a `.py` file in your operations folder is listed, with its description and parameters, and
  makes a signal like any other (preview, live updates, sessions). *Make an example* writes a file
  with three to start from. The code runs in a process of its own: an error names the line in your
  file, an endless loop is stopped, a crash does not take the app down. Only your folder runs - a
  session or template keeps just the operation's name.
- **Send data from Python** (Jupyter, a simulation, a script): `show(t, {"altitude": alt})` with the
  one-file client (*Create signals > Python > Save the Python client…*; numpy only) puts the data
  in the open app - a new name lands in the active plot, sending the same name again updates it in
  place (plots and signals made from it follow). A pandas DataFrame works too (index = time). Only
  programs that can read your `~/.signalviewer/push.json` can send - it holds a token made fresh
  at every start.

- **Fleet** (the new rail button): add folders of flight logs (.bin / .tlog / .ulg, sub-folders
  too) and search every flight at once - by a finding (errors, warnings, vibration, GPS…), by a
  number ("vibration above 30"), by name / vehicle / firmware - and see a number's **trend** over
  the flights' dates (the limit drawn, flights over it in red, click one to open it). *Open here*
  opens a flight at its finding. *Update* reads only new and changed logs. Kept on this computer
  (`~/.signalviewer/fleet.sqlite`).
- **ROS 2 recordings (.mcap)** open directly - no ROS installation needed: every numeric field of
  every topic, each topic on its own time; images and point clouds are left out (listed), a
  recording cut off by a crash keeps everything before the cut. Foxglove JSON channels too.
- **Parquet files (.parquet)**: numeric, true / false and text columns, with the pandas index or a
  time column as the time.
- **HDF5 files (.h5 / .hdf5)**: every numeric dataset, matrix column and table field, with each
  group's own time.
- A file saved with the wrong extension that is really an MCAP or HDF5 file is named as such.

## 1.4.0 – 2026-10-18

Highlights: **real Butterworth filters** (the old Low-pass / High-pass were a moving average and
could silently show the raw signal - filtered signals in saved sessions now get correct, slightly
different values), **damaged files open** with what is still readable, **Help > Copy error
details** for bug reports, and an explicit **MIT licence**.

- Licence: Signal Viewer is now explicitly MIT licensed (`LICENSE`); the installer shows it and the
  README lists the licences of the bundled parts.
- Damaged files: a CSV with a few bad bytes (a flaky SD card, a bad copy) or a block of zeros (a
  file cut by a power loss) no longer fails as a whole - the damaged lines are skipped and the
  rest opens, with a note. A MATLAB .mat that ends in the middle (MATLAB stopped while saving)
  opens with every variable that was complete before the cut. Every format is now tested
  against hundreds of damaged copies of itself.
- Filters: **Low-pass / High-pass are now real Butterworth filters** (4th order, run forward and
  backward so nothing is delayed), in Create signals and in formulas (`lowpass(v0, 5)`). Before,
  they were a moving average - and when a filter could not be applied (a cut-off above half the
  sample rate, a time that does not increase) the raw signal was shown under the filter's name.
  Now the reason is shown instead. Filtered signals in saved sessions open as before but with the
  correct (slightly different) values.
- Help > **Copy error details**: the version, the system and the end of the app's own log, to paste
  into a bug report. Errors are now kept in `~/.signalviewer/logs` (nothing is sent anywhere), and
  an unexpected server error shows a readable message instead of "Internal Server Error".
- Running from the source folder: after `git checkout`, `pull` or `clone`, `run.py` could show an
  OLD build of the interface (it judged by file times, which git resets); it now asks git whether
  the interface changed since its last build, and builds it when needed.
- A damaged settings file (after a crash) or a template file that holds no templates is now
  handled with a clear message instead of an error.

## 1.3.0 – 2026-10-17

Highlights: **live MAVLink** (UDP / TCP / serial, recorded as you go), **the same segment
across runs** (e.g. the 2nd AUTO of every flight), **batch reports** from the command line,
**coordinate frames** (NED / ENU / body / ECEF / LLA) and a plain **3D plot**, a **smart start**
for the first file, a calmer plot toolbar, and a file list with units, rates and a small picture
of every signal. Note: pan is now **Alt + drag** (Shift + drag zooms the values).

- Coordinate frames: Create signals > Frames converts between NED, ENU, body, ECEF and LLA, with
  separate maths for a vector (velocity, acceleration… - rotated only; body needs the attitude,
  ECEF the vehicle's lat / lon) and a position (also moves the origin; NED / ENU are metres from
  a reference point - the first sample or one you enter). Creates three signals, one per axis,
  that update with their files and are kept in sessions.
- XYZ plot: any three signals as a 3D plot (a trajectory in metres, three sensor axes…) - not
  tied to the map. Rotate, move and zoom with the mouse; equal scale and "Z down" for NED.
  "Place on map" puts a track in NED / ENU metres on a map or 3D plot from an origin (the GPS's
  first fix, or typed in). Reports draw it in 3D.
- File list: every signal shows its unit apart from the name (it is no longer cut off at the
  end of a long name), its sample rate (in a wider panel, and in the tooltip with the number of
  samples) and a small picture of the whole signal - spikes included. Only the rows on screen
  fetch pictures; scrolling a file with hundreds of signals stays smooth.
- Calmer plot toolbar: ONE layout button (it shows the current layout; its popover has the common
  layouts and any rows × columns) instead of seven icons, and the zoom mode in a small menu.
  For one drag, Shift zooms the values and Ctrl a box, whatever the zoom mode (the wheel uses
  the same keys). **Pan is now Alt + drag** (or the middle button); Shift + drag zooms the values.
- Split a plot by dragging a signal (or a legend chip) to its right or bottom edge: a new plot
  opens there, the grid grows when it is full.
- Fixed: middle click on a tab did not close it on Windows (the browser's autoscroll took the click).
- The file list's selection is clearer: checkboxes appear only once signals are selected (not
  just for searching), and the bar says "N signals selected" with "Plot them" (one undo step),
  "Change them…" and "New signals from them…" and how to add or remove (Ctrl / Shift + click).
- FFT: motor orders - pick an RPM / ESC / motor-speed signal in an FFT plot and the spectrum is
  marked at 1×, 2× and 3× its mean rotation rate over the same window (between the cursors, or
  the whole signal), plus the blade-pass frequency for 2–5 blades. Saved with the plot.
- Frames: the conversion is suggested from the names - a GPS position to NED, a NED velocity into
  the body frame, an IMU acceleration into NED with the log's attitude (and its angle unit). The
  first suggestion is filled in when the tab opens; chips switch between them.
- Fixed: a flight log (.bin / .tlog) or .mat in a folder with remembered CSV import settings
  opened but showed "Unexpected error while reading the file".
- Fixed: opening a template right after choosing it could open it with no files (the files for
  its slots were still being worked out); "Open" now waits for them.
- Smart start: the first file opened into an empty workspace gets a small card with the template
  that fits it best ("Open it" - nothing is applied by itself) and, for a flight log, the three
  findings of the health check most worth a look, each with a jump to its time. The library and
  the card rank templates the same way.
- Batch reports: `python cli.py report --template "ArduPilot · Full review" --out reports/ logs/*.bin`
  makes one report per file (HTML, PDF or Word; `--lang he`), with the same template matching and
  drawing as the app. A file that cannot be read or has none of the template's signals is
  skipped and named. `python cli.py templates` lists the templates it can use (built-in and
  yours); `--template` also takes a template .json file.
- Compare runs over a segment: "Compare over: A segment" picks a state signal (flight mode, gear,
  any text column), a value and which occurrence (1st, 2nd… or last) - e.g. the 2nd AUTO of every
  flight. Each file is compared from the start of its own segment; the list shows where the
  segment is in each file (or that it is missing). Clicking a signal opens the files over that
  segment, aligned at 0, in a tab named after the segment; the comparison table names it too.
- Live MAVLink: Live ▸ MAVLink connects to a vehicle or simulator over UDP, TCP or a serial port
  and records the link to a .tlog (in ~/.signalviewer/recordings). The recording opens like any
  file and live mode follows it, so live and recorded data behave the same; Disconnect keeps it.
  Only listens by default; "Ask the vehicle to send data" acts as a minimal ground station
  when no other program asks for the data. A pill next to Live shows messages per second and
  turns red when the link goes quiet. Also in Ctrl+K.
- Frames: the three signals of a conversion are kept together as one group, e.g.
  `ned_Pos_lla` with `ned_Pos_lla.N` / `.E` / `.D` (the name you type replaces the default).
  The file list and Create signals show it nested; add all to the active plot or each to a new
  plot (right-click), remove the whole group at once. Older sessions open as before.
- Frames: Preview works - the three axes dashed in the active plot (with a key), or a plot per
  axis under the plots when their sizes differ (lat / lon vs alt); the preview plots are not
  saved and go away on Create or Clear. With a map, XY or XYZ plot active, the preview goes to
  the tab's first time plot (or plots of its own).
- Frames: choose where the three new signals go - the active plot, a new plot each, or none.
- 3D view on computers without WebGL (old or virtual machines, remote desktop; recent Chrome and
  Edge no longer emulate it): a simplified 3D view of the tracks instead of an error.
- `python run.py` from the source folder always shows the current UI: after a pull or patch it
  builds the UI once by itself (Node.js needed) into an ignored folder, without touching the
  tracked `frontend/dist`. `--build` / `--no-build` to force or skip.

## 1.2.0 – 2026-10-14

- Fixed: a web page open in your browser could, in principle, reach Signal Viewer's local server (DNS rebinding) and read or write files. The server now answers only requests addressed to localhost / 127.0.0.1.

## 1.1.0 – 2026-10-13

- File browser: type part of a path and pick from suggestions; Tab completes, ↑ ↓ choose,
  Enter opens. Clickable folder path (breadcrumbs). Type letters on the list to filter it.
- Folder listing no longer stalls on a disconnected network drive, and is faster on
  network folders. `~` works in typed paths.
- Envelope plot (Monte-Carlo, repeated tests): plot the same signal from many runs and switch
  the plot to Envelope - median, 5–95 % band and min–max; runs far from the rest are named.
  Reports (HTML, PDF, Word) show the envelope too.
- Limits: give a signal a lower and/or upper limit in the Inspector. The plot shows them as
  dashed lines; the Inspector says pass or fail, how often and how long the signal was outside,
  and lists each violation (click to zoom). Kept in sessions and templates; reports get a
  pass / fail column.
- Clearer panel names: "Create signals" (was Analysis) and "Compare runs" (was Compare).
- Spectrum plots: choose FFT or Welch PSD (averaged power spectral density - the usual view for
  vibration). Kept in sessions, templates and reports.
- Segments: show a mode signal (flight mode, gear, any text column) as states, and the
  Inspector lists its segments and the total time in each state. Click a segment to zoom to it
  and put the cursors on its edges - the statistics then cover that segment.
- Formulas: `deg`, `rad`, `wrap180`, `wrap360`, and roll / pitch / yaw from a quaternion
  (`q2roll(qw, qx, qy, qz)` …, in degrees).
- Command line and Python: `python cli.py info FILE`, `python cli.py export FILE --out x.mat`
  (or .csv; choose signals and a time window), and `import signalviewer as sv; sv.load(path)`
  for numpy / pandas. From MATLAB: `system('python cli.py export f.bin --out f.mat')`.
- Welcome screen: open a ready example in one click (a drone flight, or three car runs to compare).
- The Inspector starts closed and opens by itself when you select a signal or turn on the
  cursor. If you close it with its button, it stays closed until you open it again.
- "Clear all plots" has its own icon and offers Undo; it is also in the command palette (Ctrl+K).
  The live "Follow" choice is in one place: the plot bar while live mode runs.
- Fixed: an Undo button on an older message could undo a later, unrelated change.
- Fixed: a blank window on Linux systems whose locale is set to POSIX / C.

## 1.0.0 – first release

- Open CSV, MATLAB .mat (v5 / v7.3), ArduPilot .bin, MAVLink .tlog and PX4 .ulg files.
- Up to 9 linked plots per tab: Time, X-Y, FFT, Spectrogram, Map and 3D modes; two cursors,
  statistics, notes, zoom history and a timeline with playback.
- Compare runs: similarity list, automatic time alignment and a comparison table.
- Flight logs: flight modes, events, parameters and an automatic health check.
- Offline map and 3D terrain view with vehicle models, synchronised with the timeline.
- Formulas and analysis (filters, derivatives, integrals) that update with their sources.
- Templates and collections, sessions with autosave, live mode.
- Interactive HTML, PDF and Word reports.
- English and Hebrew (right to left), light and dark themes; runs fully offline.
