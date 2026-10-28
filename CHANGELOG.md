# Changelog

## Unreleased

Highlights: **change a file's time axis while working** - another column as its time, its unit,
its offset; and **no more silent blank window** on offline computers with an old Edge WebView2.
Nothing changes in results, sessions or templates you already have.

### Added
- **Time axis…** (right-click a file; it replaces *Time offset…*): another column as the file's time (CSV / text, MAT, Parquet), the unit of its time - ready conversions (ms → s, µs → s, s → min…) or any scale - and its offset, in one place. Before anything changes it says what the new axis looks like (only goes up / goes up and down / repeated values / missing values / long gaps, the unit its name says) and what will mean something else: the column leaves the plots it is in, new signals and edits computed against time (derivative, integral, filters, a shift in t) are computed again on the new axis, signals made from the column itself will fail, other open files keep their axis. A column that goes up and down needs a tick first, and offers an X-Y plot instead. With *Link plots* / *Link operations* on, the same change can be made on the other files. Cursor, zoom and notes follow the same rows; one Undo puts the file and the work back. Kept in sessions, refresh and live mode; in Python: `sv.load(path, {"time_scale": 0.001})`.
- **Columns with a time column of their own** (a `time_boot_ms` beside a time in seconds) can now be put in seconds: a scale of their own in *Time axis…*.
- **Investigate → Conditions**: name the moments that matter (`Speed > 30`, `abs(Vz) > 5 and Mode == "AUTO"`, with hysteresis and minimum length) and see them in every open file - counted while you type, stepped through with `]` / `[`, shaded on the plots, combined, hidden, deleted with undo. With both cursors on, **Find similar** on the bar above them writes the condition for you.
- **One into each plot**: select several signals - a flight computer's X, Y, Z - and put one into each plot of the tab, beside the true X, Y, Z already there one per plot. They are paired by the part of their names that differs (X / Y / Z, [0] / [1] / [2], Roll / Pitch / Yaw), else by order; ones with no plot left get new plots. The added set has one colour in every plot, a message says what went where, and one Undo takes it back. With *Each in a new plot*, in the menu of the ▾ beside *Plot them* (and in the right-click menu of a selection or a group).
- **The error per axis in one click**: ⋯ on a plot with two lines - *Error: NavPos_X − TruePos_X*, or *Error in every plot with two lines* - opens the errors (second line − first, where both have data) in a new tab, a plot per axis titled with its RMS, mean and largest error and when it happened; the flight mode where it is worst is named when it stands out (1.5 × the next). The cursor goes to the largest error; the step is recorded for the report.
- **Templates take the investigation along**: a template saved while investigating keeps the conditions (they are written by signal name); opening it on the next flight's file adds the ones not there yet, counted on that file at once.
- **Pick moments on the strip**: its rows are yours - any state signal or condition, added, replaced, moved, removed - and a click picks stretches (Ctrl+click: *or* in a row, *and* across rows), shaded on the plots, saved as a condition in one click.
- **The run at a glance**: a strip above the plots with the run's phases and a few automatic flags - a frozen or saturated signal, a gap in the recording, a glitch - and where the plots are zoomed; click to go there.
- **Findings and an investigation report**: a note can be a finding (open, explained, fault, rejected hypothesis) that keeps the view it was found in; the Investigate panel records the steps you take; the report can include the investigation - findings with their plots, rejected hypotheses, the analysis steps, conditions per run and how to reproduce it (HTML, PDF, Word).
- **Runs × conditions**: every open run against every condition - counts or total time, the parameters that tell the runs apart (constant signals, numbers in file names), the odd run marked, a click to its stretch, two columns against each other with a fitted line - and *Open a folder of runs…* for a whole Monte-Carlo set.
- **What changed first?** On the selection bar: every signal of the tab (or of its files) in the order it left its usual range around the span, with a small picture each, dashed lines on the plots, the ones the sample rates cannot order grouped - candidates, with the warning that earlier is not cause - and the **lag** between any two ("Roll follows Motor3 by 120 ms"), shown aligned on the plot.
- **An example with a known answer** (welcome screen → *find out what went wrong*) and a tutorial that walks through every Investigate tool on it (docs/investigate-tutorial.md, in Hebrew too).
- **The stretches of a condition, together**: a table of them (sort, click to go there, copy), all of them on top of each other in a new tab (lined up at start, end or peak, their mean bold), and **What differs inside** - the signals most different inside the stretches than outside.
- **State lanes, where you want them**: right-click a lane (or its chip, or the signal in the list) → *this plot only*, *every plot of this tab*, *every time plot, all tabs*, or *Remove this lane*. **Always as a state**: by the signal's name, in every plot and every file, without setting it in each plot again.
- **Map objects from ECEF / NED / ENU**: *Position from* in the object dialog - the three components in metres, and for NED / ENU the reference point (the first sample of a latitude / longitude / altitude, or typed numbers). Made with the existing frame conversion when the object is saved; editing reads it back.
- **Smoothing a noisy position or vector**: *Smooth position (s)* on a map object, and *Create signals → Several → Smooth a vector* for any 2-3 components (a velocity, say): a centred average over a window in seconds, never across a gap, latitude / longitude handled across ±180. New signals; the recorded ones stay as they are.
- The object dialog says that the attitude can be a quaternion and that its angle unit only changes the drawing.
- **Safe graphics** (`--safe-graphics`, a *Signal Viewer (safe graphics)* shortcut in the portable package and the Start menu): draws without the graphics card, for a white or black window on virtual machines, remote desktop or old drivers. The 3D view keeps working.
- *Help → About* says which engine draws the app (WebView2 / Edge / Chrome / Firefox and its version) and whether in its own window or a browser.

### Fixed
- **What changed first** on a span early in the file, or a long one, read the usual level from before the first sample: every signal had "no data" and the panel said *No signal left its usual range* - a wrong "nothing changed". The usual level is now read inside the data (the time before the span shrinks first, then the baseline), and a span with nothing before it says so: *pick a span later in the file*. *Find similar* reads it the same way.
- **Numbers with an exponent** in a condition or a new signal's formula (`Speed > 1e3`, `2.5E-3`, `1_000`) were read as a signal called `e3` / `E` ("missing in every file").
- **What changed first**: a state signal that went to a lower value was shown as rising (↑).
- **Hebrew** in *What changed first*: "no change" came before the other file's name, the file in the scope list was cut in the middle of its name, and times said "s" instead of ש׳.
- "1 stretches" → "1 stretch" (the condition count, the strip, the stretches table, the steps list).
- **Find similar** writes the condition on the signal most unusual inside the selection, of all the tab's plots - not on the first line of the active plot (a flag on Motor3 with the Alt plot active gave `Alt < 29.73`, 768 stretches; now `Roll > 9.86`, 3).
- **What changed first** looks at every signal of the event's file by default, not only the plotted ones (Wind, the start of the demo's chain, is on no plot); under each signal, the same signal in the other open files at the same time - a run without the event that has the same change shows that change alone does not explain it.
- **The overview strip** sits under the plots' time axis: a flag at 38.5 s is above 38.5 s on the plots (it was ~70 px off).
- **Hebrew**: in *What changed first* the signal's name was cut off (only the file showed); in *What differs inside* the before → after values read backwards.
- The bar above a selection (Note / Find similar / What changed?) did not appear on a plot made active after the plots were built.
- A click on a name in *What changed first* or *What differs inside* opens it in a plot of its own (Ctrl+click: into the active plot) - a motor at 2000 no longer squeezes a roll of 2° flat.
- **Steps so far** is grouped by kind (conditions, what changed first, lags, findings, errors…): a group goes into the report, closes or is removed at once; a filter for a long list; "4 of 6 in the report".
- A long plot title no longer runs under the plot's buttons: it is cut with "…" (the whole of it on hover).
- **What changed first** on a long log: a filter by name, a × to take a row or a whole group out of the list (its dashed lines leave the plots too; one click brings them back), groups that close, and long groups shown 5 at a time. Groups are measured from their first row - one slow signal (2.5 Hz) no longer chains a whole log into a single "together" group. The name has its own line.
- **What changed first** no longer lists signals that were only going on as before: a counter or a clock that was already climbing steadily (used energy, GPS time) is judged against its own trend. On the ArduPilot example: 17 candidates instead of 21, vibration first.
- Range notes kept only their start time in reports; they now show "from – to".
- **State lanes**: the end of a lane no longer looks like one more state with an unclear text - the lane's name was drawn over its last stretch; it is now in the margin left of the lane, and hovering a lane says what it is.
- **A blank white window** on computers with an old Microsoft Edge WebView2 (common offline): the UI was built for engines from 2023 on and did not even start there. It is now built for Chromium 87 / Firefox 78 and newer, with the few newer functions it uses added where missing. The launcher checks the WebView2 version; when it is too old it opens the app in a newer Edge or Chrome as a window of its own, else Firefox, else says in a message box what to install. If the page still does not start, it says why (engine, what to do, the log) instead of staying blank.

## 1.14.0 – 2026-10-26

Highlights: **very large flight logs** - a 1.2 GB ArduPilot .bin opens in seconds instead of not at
all, and reopens in a moment; **live mode keeps the map and 3D objects at the newest data**; the app
no longer stops under a browser tab left in the background; the disk space it uses for speed is kept
small, shown and clearable; and **signals are typed by name** wherever one is chosen, with its unit
and **unit conversions** (rad → deg, m/s → km/h, m → ft...) one click away. Nothing changes in
results, sessions or templates you already have.

### Fixed
- **Big ArduPilot logs (.bin) froze while opening**: the reader made several temporary arrays the size of the file, one of them 8 bytes per byte (about 13 GB of memory for a 1.2 GB log), and a log with many small damaged blocks was walked again from every break. A 1.2 GB log now opens in about 7 s with under 0.5 GB of memory; the progress bar moves, and Cancel works.
- **"Failed to fetch", then nothing works** (browser mode): the server stopped itself 30 s after the last ping of the page, but a browser slows the timers of a tab in the background to about one a minute - often in the middle of a long load. Now any request of the page counts, the page says goodbye when it closes, the limit is 5 minutes otherwise, and the server never stops while a file is still being read. If the server is gone anyway, the message says so and what to do.
- **Refresh and live mode did not move the object on the map / in 3D**: the data was read again, but the object stays at the time (cursor), and the time stayed where it was. A time at the end of the recording now moves on with new data (live mode puts it there when it starts); a time moved back stays where it is, and End brings it to the newest data again. In live mode an object whose track ends a moment before the newest data (GPS at 5 Hz, IMU at 400 Hz) shows its last state instead of disappearing.
- **Opens in the browser instead of its own window** (Windows portable): the window's .NET parts were blocked by Windows' "downloaded from the internet" mark, and the reason was never shown (the launcher has no console). The app now unblocks its own DLLs, finds the WebView2 runtime by its folders too, and when it still opens in the browser it says why (and writes it to the log).
- Refreshing one file is a background job with progress (a big file was one long request).
- Live mode: every update re-tested every signal of a file for "state signal" (up to 200 k samples each) and kept the answers forever - a slow memory leak and up to a second of work per update. Two timers of the page no longer send a request while the previous one is still unanswered (with a busy server, the same pushed data could be handled twice).
- The FFT cache could hold gigabytes (33 full spectra of long, fast signals); it now keeps up to 256 MB, and only the newest version of each signal.

### Added
- **`tools/live_demo.py`**: two objects that move - an aircraft flying circles and a ship sailing a zig-zag, written to two CSV files that keep growing - to see live mode on the map and in 3D without a logger. Open both, add an object from each (they fill themselves in), press Live.
- **Signals are typed, not scrolled for**, wherever one signal is chosen for a role - a map object's position and attitude, *Place on the map*, the state signal of error segments: type part of the name (as in the file list's search), arrows + Enter, from every open file (the main file's first, each marked with its file). Beside the field: the **unit the signal is in now**, and **ƒ** - change that signal right there (a unit conversion, a scale, a formula), e.g. angles that turn out to be in radians. Esc closes only the dialog on top.
- **Unit conversions** in *Change this signal…*: rad ↔ deg, rad/s ↔ deg/s, m/s ↔ km/h ↔ kn ↔ mph ↔ ft/min, m ↔ ft ↔ km ↔ NM, cm / mm → m, m/s² ↔ g, °C ↔ °F ↔ K, Pa ↔ hPa ↔ psi, ms / µs → s, deg·1e7 → deg. The conversions from the signal's unit are offered first (all of them when its name does not say). It is an in-place change like any other - composed with one already there, undoable, kept in the session - and the **unit shown** changes with it: on the axis, in the file list, in the legend ("Yaw [rad]" converted shows deg). The unit shown can also be typed.
- **Big .bin logs are read when used**: values stay in the file until a signal is plotted (a 16 M-sample signal is read in about 0.3 s), within a memory budget (`SV_LAZY_MB`, default 1536 MB); fields the log stores as float32 / small integers stay float32 (the same values, half the memory); several cores share the work.
- **A big .bin opens again in a moment**: its index (time vectors and message positions, about a third of the log's size) is kept in the cache folder and memory-mapped - 0.03 s and almost no memory for a 1.2 GB log. Used only when the log's size, time and contents match; not written for a log still being written.
- **Settings > Disk space used by the app**: the CSV cache and log indexes, copies of files dropped into a browser window, and map tiles - each with its size and *Clear*; *Clear all but the map tiles*. Nothing an open file needs is removed. Also `signalviewer-cli cache` (`--clear cache|uploads|tiles|all`).
- The cache keeps itself small: when a file changes, its old copy is removed (a big CSV that grows used to leave a full copy behind on every change); entries unused for 30 days go, and the cache stays under 5 GB (`SV_CACHE_MAX_GB`, `SV_CACHE_DAYS`). Copies of dropped files older than 7 days are removed at start.

## 1.13.0 – 2026-10-24

Highlights: **the work of one file, part by part, for another** - copy only the changes, only the
new signals, only the plots, or any mix, to a file that is already open (or one to open); and clear
one file's work only. And **other signals in an expression of x**: `sin(x) + Speed` on one signal or
a group. Nothing changes in results, sessions or templates you already have.

### Added
- **Copy the work to another file…** (a file's right-click; it was *Add a run with the same work…*): the target can be **a file that is already open** as well as a new one, and each part is chosen on its own - its changes (ƒ), the signals made from it, and its signals in the plots: on the same plots (to compare), in a plot of its own beside each plot in the same tab (side by side when every plot of the tab gets one; a tab without room for them - 9 plots at most - is copied as a new tab instead), in a copy of each tab, or not in the plots. *Link plots* and *Link operations* for what comes next are two separate boxes, off unless ticked.
- **Other signals in an expression of x**: `sin(x) + Speed` - wherever an expression of `x` is written (*Change this signal…*, the change of several selected signals, *Create signals → Expression in x*), another signal is written by its name (suggested while typing; `{Two words}` for names with spaces). It is the signal of the same file as `x` - for a group, each one's own file - as read from the file, so a group that includes Speed itself sees the same Speed in every one of them. Copied or linked to another file, the change reads that file's Speed. A name some file lacks is named, with those files. **`{run_b.csv:Speed}`** takes that one file's Speed instead, for every signal changed (the file as the file list shows it); it is kept by the file itself, so it stays right after saving and reopening the session and after *Replace the input files*. A name with spaces or brackets typed without braces is answered with the braced name (`{Speed [km/h]}`).
- **New signals made from two files belong to one of them**: a signal knows which of its sources are fixed - `{run_b.csv:Speed}` in an expression of x or a Formula, the baseline of a *Compare runs* difference - and belongs to the file of the others. So *Copy the work to another file*, *Link operations* and *Clear this file* treat it like any signal of that file: copied to a new run, `x - {run_b.csv:Speed}` reads the new run's x and still run_b's Speed, and the difference of each new run is against the same baseline. Signals of two files whose intent is not known (made before, or a formula whose names fell in two files) are listed in the copy dialog, each with a box: ticked, the new file takes the place of the copied one and the other file stays.
- **Clear this file ▸** (a file's right-click): its signals out of every plot (signals made from it too), undo its changes (ƒ), delete the signals made from it (and what was made from those) - one at a time or all of them; the file stays open, the other files keep their own work, and one Undo puts it back.

## 1.12.0 – 2026-10-22

Highlights: **one piece of work for many runs** - *Add a run with the same work* gives a new file
the changes, new signals and plots made for another (on the same plots, or in new tabs), and *Link
plots* / *Link operations* keep the files together from then on. **And several signals at once**:
select signals in the file list (Shift + click or Shift + drag for a range, and ranges add up: 1-3,
then 7-11; or Ctrl+click chips in a legend), right-click any of them and change all of them
together: `x*8` or `sin(x)` is applied to each one. *Create signals* takes your own expression in x
too. A new selection starts with one click after an action, a whole group is selected with its
checkbox, and the groups of search results can be closed. Nothing changes in results, sessions or
templates you already have.

### Added
- **The same change on several signals, from wherever they are selected**: right-click any of the selected signals in the file list (or of the Ctrl+clicked chips in a legend) for *Change the N selected…*, *Plot the N selected* and *New signals from the N selected ▸* (derivative and integral at once, one new signal for each). In the change dialog **x is each signal in turn** - `x*8` or `sin(x)` changes every one of them; the signals are listed and any can be taken out.
- **Your own expression in x** in *Create signals → One signal* (`x*8`, `sin(x)`, `deriv(x)/9.81`): on one signal or on each of several, as a new signal or changing the signal itself.
- **Ranges with Shift, as many as you need**: hold Shift and click signals 1 and 3 - or press on 1 and drag to 3 - and 1 to 3 are selected; let go of Shift, hold it again on 7 and click 11, and 7 to 11 are added (1 to 3 stay). Dragging near the edge of the list scrolls it.
- **A new run with the same work - next to the old one**: right-click the file you worked on → *Add a run with the same work…* and choose the new file (the newest one with the same name pattern is suggested). It gets the same changes (ƒ), the same new signals (signals made from signals too) and the same place in the plots - on the same plots to compare, or in a copy of each tab - and the first run stays. Again for a third and a fourth run. (*Replace the input files* still swaps files instead.)
- **Link plots and Link operations, each on its own**: two buttons at the top of the file list. *Link plots* (the former *Link files*): adding or removing a signal does it in every file - now for signals made from it too. *Link operations*: a change on a signal, or a new signal made from it, is made on the same signal of every file. Both are kept in the session.
- **Selecting a whole group**: while signals are selected each group has a checkbox (all / some / none of its signals); Ctrl+click on a group, or *Select these N* on its right-click, does the same.

### Changed
- **Starting a new selection takes one click**: after an action on the selected signals (change, plot, new signals) they stay selected for the next action, and the next Ctrl / Shift + click starts a new selection instead of adding to it. *Clear selection* is a button with its name, and Esc clears it (in the file list and its search box).

### Fixed
- While searching, a file or a group of the results could not be closed - a click on it did nothing until the search was cleared. It now closes and opens as without a search, and *Collapse all* / *Expand all* do all of them.
- *Change this signal…* on the right-click of a signal that was part of a selection changed only that signal (*Apply to 1 variables*); it now offers the change for all the selected signals.
- A second Shift+click range in the file list started from where the first one started (1 to 11 instead of 1 to 3 and 7 to 11), and Shift + drag dragged the signal toward a plot instead of selecting.
- In the legend, *New signals from these…* opened *Create signals* without the selected signals; they are now chosen there.

## 1.11.0 – 2026-10-21

Highlights: **easier to trust, report and contribute to** - every change is now tested on GitHub
(Python 3.9 and 3.12, the UI and a short run in a browser), *Help → Report a problem…* takes you
from an error to a filled-in report in two clicks, and `compare` can allow a few samples outside a
tolerance so one spike does not fail a matching run. Nothing changes in results you already have:
without the new option every sample must still be inside.

### Added
- **Every change is checked on GitHub**: the tests, the type checks, the numerical validation and a short run of the app in a browser on every push and pull request (the *CI* badge on the README).
- **`signalviewer-cli compare`: a few samples may be outside** - `"outside_pct": 0.5` in the tolerances (per signal or for all) or `--allow-outside 0.5` passes a signal when at most 0.5 % of its samples are outside the tolerance, so a spike at a step does not fail a run that otherwise matches. Without it every sample must be inside, as before.
- **Help → Report a problem…** copies the error details and opens the bug report form on GitHub in your browser: paste and send. Nothing is sent by the app; without internet it says the address to open on another computer.
- **Ways in for others:** a guide to contributing (`CONTRIBUTING.md`), forms for bug reports and ideas that ask what helps to fix it, a private way to report a security problem (`SECURITY.md`), and *Cite this repository* on GitHub (`CITATION.cff`).

### Fixed
- `signalviewer-cli compare` wrote "0.0 % of samples outside" for a signal that failed on a few samples; the share is now written exactly (*0.089 %*).
- `signalviewer.load()` in a script or a notebook printed a progress line (*[OK] Loaded …*) into your own output; it now goes to stderr, as on the command line.
- The PyPI page's *Documentation* link opens the documentation site.
- The README says what `pip install signalviewer` gives (the app in your browser; `[desktop]` for its own window) and what to do when Windows or macOS stops the first start of the unsigned packages (a new section in *Install*).

## 1.10.0 – 2026-10-21

Highlights: **numbers you can trust** - every computation checked against a reference
(`signalviewer-cli validate`, the new *Validation* page) and the readers checked against logs from
real vehicles; that work found and fixed wrong frequencies in spectra of logs with gaps, filters
cutting at −6 dB, time statistics of uneven sampling and samples moved by seconds in slow telemetry.
And **a simulation against its flight, start to finish**: a new example, a walkthrough, and
`compare --align` for CI. A new documentation site.

**Results that change from 1.9.0** (the old ones were wrong - see *Fixed*): FFT / Welch of signals
with gaps or lost samples; low- and high-pass filters (the cut-off is now the −3 dB point, as in a
derived signal or `lowpass(...)` in a formula, recomputed when a session opens); mean, RMS and std
of unevenly sampled signals (evenly sampled: the same numbers); the time of telemetry (.tlog)
samples when the radio delay varied; signals matched across files by name without the unit in
Compare and on the command line (more rows than before).

### Added
- **A simulation against its flight, start to finish** - a new example (welcome screen and `examples/sim_vs_flight/`): the same attitude test flown in a model (.mat, from 0 s) and on the vehicle (ArduPilot .bin, from boot), and a documentation page that walks through it - align in time, look closer, rank every signal, and the same check as pass / fail in CI. Made for this: `signalviewer-cli compare --align auto` (or `--align SECONDS`, `--align-on NAME`) lines the runs up first, and `{"as": "name"}` in the tolerances pairs signals named differently.
- **A new documentation site**: a front page that says what the app is for, with the download, the four things people do with it and why the numbers can be trusted; search; light and dark (following your system); the pages grouped into *Get started*, *Features*, *Quality* and *Development*; the Hebrew guide right to left.
- ***What works*, readable**: the one big table (cells a paragraph long, bold everywhere) is now a page with a section per area - opening files, file formats, plots, reading values, math and analysis, comparing runs, flight logs, map and 3D, reports, the command line - each with a picture, a list per feature and a jump list on top. Nothing was dropped: every item of the table is there, word for word.
- **Tested on logs from real vehicles**: public ArduPilot (.bin, .tlog) and PX4 (.ulg) logs, read by Signal Viewer and by their projects' own readers (pymavlink, pyulog) and compared field by field; and a way to run the same checks on your own logs (see *Development*). This found the .tlog timing fault below.
- **Validation: every computation checked against a reference** - FFT and Welch, low- and high-pass filters, derivative and integral, statistics, decimation, Compare (RMS difference, correlation, angles, time alignment) and coordinate frames (WGS84, body to NED): 23 cases, each against a closed-form result or a definition, never against the app itself. They run with the tests on every change; `signalviewer-cli validate` runs them on your own machine and installation (exit code, `--json`, `--junit` for a qualification record); the documentation's new *Validation* page lists them with the expected and measured values and the conventions (FFT amplitude, Welch units, filter cut-off, std). On 1.9.0 four of them fail - the three fixes below.

### Fixed
- **A simulation and its flight log would not compare or align by themselves**: Compare, *Align* and `signalviewer-cli compare` paired signals only by their exact name, and a simulation's `ATT.Roll` is the log's `ATT.Roll [deg]`. Names now match with or without their unit (when that is one signal in each file).
- **Align by signal could lock onto nothing**: where the two signals barely move (a command that is 0 before and after a test), a near-empty overlap could score higher than the real match - aligning the example above landed 70 s off. Overlaps where a side does not move are no longer counted.
- **Spectra of logs with gaps showed the wrong frequencies.** The FFT and Welch spectra took the samples to be evenly spaced at the record's *mean* interval, so one logger pause moved every frequency: a 37 Hz vibration in a 20 s record with a 2 s pause was shown at 33.3 Hz (dropped packets and NaN samples did the same). Now a signal with a gap, NaN samples or repeated time stamps is put on an even grid of its *median* interval, in time, before the spectrum - the spectrogram, which already resampled, uses the same grid. The frequencies are right; amplitudes are lower by about the share of time the gaps cover, and the plot says so: *⚠ 1 gap(s), 2 s bridged* (hover for the details). Evenly sampled signals and small timestamp jitter are used as before, unchanged.
- **Low-pass and high-pass filters cut at the frequency you enter.** The filters run forward and backward (no delay), which squares their response: a 4th-order Butterworth designed at the cut-off was at -6 dB there, not -3 dB - a "10 Hz" low-pass halved a 10 Hz signal. The filter is now designed for the two passes, so the filtered signal is at -3 dB (half power) at the cut-off, in *Create signals*, *Change this signal* and formulas (`lowpass(Roll, 5)`). Derived signals with a filter are recomputed with it when a session is opened, so their values change slightly near the cut-off. To reproduce a result in MATLAB or SciPy: `filtfilt(butter(4, fd/(fs/2)), x)` with `fd` ≈ 1.12 × the cut-off for a low-pass, 0.90 × for a high-pass (exactly: `svcore.ops.zero_phase_design_cutoff`).
- **Telemetry logs (.tlog): samples moved by seconds when the radio was slow.** Messages that carry the autopilot's clock are placed on it, but the reader told the autopilot's boots apart by assuming the radio delay varies by well under a second. A real log (ArduPilot's own vtol.tlog, delays from 0 to 4 s) became five "boots", and about one sample in ten was moved by 1 to 3 s and ended up out of order. A boot is now a stretch in which the autopilot's clock runs on (a reboot restarts it), with one offset for the whole boot: every sample keeps its exact place and order, also live. Checked against pymavlink on two real logs, one of them with five reboots.
- `python -m signalviewer.cli …` did nothing and exited 0 without a word; it now runs the command line like `signalviewer-cli`.
- **Mean, RMS and standard deviation of unevenly sampled signals counted samples, not time.** A simulation with a variable-step solver (1000 small steps in the first second, then 99 one-second steps) had a mean of 9.1 where the signal was 10 for 1 s and 0 for 99 s; now it is 0.1. When the samples are not evenly spaced each one counts for the time it stands for (half the interval to each neighbour) - in the Inspector (marked ⏱, hover for why), *only while* a state holds, Compare and the reports. A dropout (a step five times longer than the steps around it) is time with no data: it is not given to the two samples beside it. Evenly sampled signals, and small timestamp jitter, give exactly the numbers they gave before.

## 1.9.0 – 2026-10-20

Highlights: **into the test process** - `signalviewer-cli check` (limits as pass / fail, per flight mode) and `compare` (against a golden run) with exit codes and JUnit XML for CI; **any recording** - CAN logs with a .dbc, raw binary packets from a layout (ICD), and your own formats as a short Python reader; **a simpler top bar** - session, Clear ▾ (what to clear), settings and day / night as buttons; **never old numbers** after the data changed; a documentation site, and `pip install signalviewer-lite` next to the full package.

### Added
- **One Clear button with a choice of what to clear** (the top bar, also Ctrl+K; the eraser above the plots still empties this tab): this tab's plots, the other tabs, all tabs, or all the work on the data - tabs, notes, derived signals and edits - while the files stay open; each one is undone with one click. *Everything* (also closing the files) is still there, and still asks first.
- **CAN bus logs with a .dbc:** candump logs (`.log`), Vector ASC (`.asc`) and CAN frame tables (`.csv` with time, id and data columns) open as signals named *Engine.RPM [rpm]* - each message at its own rate - decoded with every `.dbc` next to the log or in your readers folder: Intel and Motorola byte order, signed, scale and offset, value names, float signals, multiplexed signals, 29-bit ids, CAN FD payloads. Frames whose id is in no .dbc are counted in the load report; without a .dbc the message says where to put one. Our own reader (MIT): nothing LGPL is installed.
- **Raw binary recordings from a layout (ICD):** a `<name>.icd.json` in the readers folder describes the packets - sync word, packet id and length in the header, and for each field its offset, type (u8 … f64), byte order, scale and offset, unit, bit field or value names - and Signal Viewer opens such recordings as signals named *NAV.alt [m]*, each packet type at its own rate. Time from a packet's field or from the header. Noise on the line, unknown packet ids and a cut-off end are skipped to the next sync and counted in the load report. A wrong layout says which packet and field. `signalviewer-cli readers --example-icd run.tlm` writes an example layout and a recording to try it on. (YAML layouts too when PyYAML is installed.)
- **Your own file formats:** a Python file in `~/.signalviewer/readers` with a function marked `@reader(extensions=[".kv"])` that returns the time and the signals makes Signal Viewer open those files - in the file dialog, by drag & drop, in Python (`sv.load`) and on the command line - like any built-in type: plots, cursors, compare, reports, checks. Text values (a mode as words) come with their names; each signal may have its own time. `signalviewer-cli readers --example` writes a reader to start from; saving a reader is enough, no restart. A reader that fails says the line in your file.
- **Pass / fail from the command line, for test benches and CI:** `signalviewer-cli check runs/*.csv --checks checks.json --junit results.xml` checks every file against limits - a whole run, a time window, or only while a state holds (*Speed below 76 km/h while DriveMode = CRUISE*, every stretch or the 2nd one) - and prints one line per check with where it first went outside and how far. `--template "My limits"` uses the limits you already set on signals in the app and saved in a template. Exit code 0 = all passed, 1 = a check failed, 2 = a check could not be made (a missing file or signal is never a silent pass); `--junit` writes results that CI systems show as test results. Example: `examples/checks.json` on the three car runs.
- **A run against a golden run, from the command line:** `signalviewer-cli compare golden.csv new/*.csv --tol-pct 2` - every signal both runs have, with the Compare panel's numbers (RMS and largest difference, correlation; headings wrap at 360°), the most different first. With a tolerance - one for all (`--tol-abs`, `--tol-pct`) or per signal in a `--tolerances` file, where a signal can also be skipped - a signal outside it fails the step (exit code 1); `--junit` for CI. Without one it only lists the differences.

### Changed
- **No File menu: its few entries are buttons in the top bar again** - open and save session, **Clear ▾**, settings, and a **day / night** button (one click instead of Settings). Opening files stays in the file list (Ctrl+O), recent files Ctrl+P.
- **A documentation site** (GitHub Pages, built from `docs/`): the user guide in English and Hebrew, every feature, the command line and file formats, install and build, map and 3D, performance and known limitations. The README is now a short front page that links to it.
- **A light install next to the full one:** `pip install signalviewer` still installs everything; `pip install signalviewer-lite` (about 350 MB instead of 760) is the core - CSV, MATLAB v5, ArduPilot .bin, CAN, binary layouts, every plot and analysis, HTML reports - with Parquet, HDF5 / MATLAB v7.3, MAVLink .tlog and live MAVLink, PX4 .ulg, ROS 2 .mcap, PDF / Word reports and the desktop window as extras (`signalviewer-lite[all]` for everything). A file or a report that needs a missing part says what to install, instead of failing or calling the file damaged. The installer and the portable packages have everything.
- **Python and the command line take signal names the way people write them:** `rec.signal("ATT.Roll")` finds *ATT.Roll [deg]* - the unit may be left out and the case does not matter, as long as the name means one signal (two signals with the same name and different units ask for the full name, never a guess). A name that is not there says which names are closest (*Did you mean 'ATT.Roll [deg]'?*). The same in `signalviewer-cli export --signals`.
- **`signalviewer.show(...)`:** with `pip install signalviewer`, sending data from a notebook to the open app is `import signalviewer as sv; sv.show(t, {"altitude": alt})` - no file to copy (the one-file client from *Save the Python client…* still works).

### Fixed
- **Never old numbers after the data changed:** a derived signal recreated under the same name (another cut-off, a re-opened session) showed the old spectrum; signals made with a Python operation kept their values after the operation's file was edited and *Reload* pressed; a plot or the small picture in the file list could stay as it was when a file was reloaded with the same number of samples; a large CSV copied over with the same size and time stamp was read from the cache; in live mode a value fixed early in a file (re-saved with the same size) was not read. Every one of these now reads the new data.
- A MATLAB v7.3 file opened without the `hdf5` extra said "not a valid MATLAB file"; it now says which extra to install.
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
