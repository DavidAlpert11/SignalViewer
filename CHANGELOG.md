# Changelog

## 1.6.1 – unreleased

### Fixed
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
