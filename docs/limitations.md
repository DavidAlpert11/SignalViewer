# Known limitations

* Interactive HTML reports embed signals longer than 150,000 samples as three min/max levels, so very deep zoom inside the report shows less detail than the app.
* Copying an image to the clipboard depends on the window's clipboard support; Save image always works.
* A derived signal whose source file was closed stays in the list, marked, until you remove it.
* The macOS package is not signed or notarized: after extracting, run `xattr -dr com.apple.quarantine SignalViewer` (or right-click → Open) the first time.
* Without `pyarrow` the pandas parser keeps a malformed row that has too few fields (missing values become empty), while `pyarrow` skips it.
* The timeline's modes apply to time, X-Y, map and spectrogram plots, not to FFT.
* In a web browser (not the desktop window) Ctrl+PageUp / Ctrl+PageDown and Ctrl+Tab switch the browser's own tabs; use the *All tabs* list or *Go to tab* (Ctrl+K) there.
* The right value axis follows its data: zooming the values (Shift+drag), panning, the axis limits dialog and linked value axes act on the left axis.
* *Open with* (Explorer) is set up by the installer; with the portable packages, open files from the app or `SignalViewer file…`.
* Installed with pip it opens in the browser (with `signalviewer-lite`, only the core readers are there until their extras are added - the app says which); `pip install "signalviewer[desktop]"` gives it its own window (on Linux that needs GTK or Qt).
* With `signalviewer-lite` the *pump on a test bench* example (Parquet) is offered only once the `[parquet]` extra is installed: its recording is written on first use (1.30.0), which needs it.
* Heavy computations - an FFT, statistics, a spectrogram, a new signal - run a few at a time (2–4, `SV_HEAVY_JOBS`): with many such plots of long recordings on screen, some are drawn a moment after the others.
* The interactive HTML report lists the notes under its summary; it does not draw them on its plots (the PDF and Word reports do).
* Columns with a time column of their own keep that column's unit unless it is changed: *Time axis…* gives them one scale of their own (a `time_boot_ms` column → ×0.001), the same for all of them - a file whose own time columns are in different units can put only one of those units in seconds.
* The strip's rows are kept in the session, not in templates; a selection on the strip is made in the strip's run (saved as a condition it applies to every open file).
* The strip's flags are deliberately few: a signal that is mostly flat (a set point, a counter, a switch) is never flagged as stuck or saturated, nor is anything in the first or last 5% of the run. Files with more than 300 signals are scanned on their first 300.
* Written reports (1.31): the editor is plain text (Markdown) - a line that mixes Hebrew and English shows in the
  editor in the browser's bidi order (the preview and the files are laid out per paragraph); math is matplotlib's
  mathtext (no matrices or aligned equations); a template saved in the app carries the written report (1.32), but the
  command line's batch reports do not make it yet (they make the report of the template's tabs); one written report
  per session.
* Ready-made report parts (1.32): pairs, objects and states are found by the signals' names - a pair named
  otherwise is not found (write its plot with `[[plot A, B]]` and its values with `{{ }}`); `[[differences]]`
  compares the files on their recorded time (no automatic time alignment - align them first in Compare when their
  clocks differ); `[[navigation]]` compares objects with a latitude / longitude or a local position with its origin
  (as *Compare objects…*); `[[trajectory]]` reads a latitude / longitude track. The parts are not offered in Sweeps.
* Reports: "Stretches together" (occurrences) plots are not drawn in reports yet; a finding's plot is the time plots of the tab it was found in (up to two) at its view. The journal keeps the last 200 steps; it is saved with the session, not with templates.
* Runs × conditions works on the open files: a folder of runs is opened (up to 200 files at a time, each read into memory) - for a folder of hundreds, *Summarize a folder* reads one file at a time into a Sweeps table instead. Parameters come from signals that hold one value and from numbers in file names; a side file of parameters is not read yet.
* What changed first finds a change in level (beyond 4 times the usual noise, 3 samples in a row); a change only in how a signal oscillates (same level, more shaking) shows only when it pushes samples that far. It reads the usual level well before the span - an event that has been building for longer than that is measured against its own start. Near the start of the file it reads it from whatever is there before the span; with nothing before it, it says so instead of answering.
* What differs inside the stretches compares means (in units of the spread outside) - a signal that only changes shape, not level, ranks low. The overlay draws the first 200 stretches.
* Conditions: kept in the session (no shared library yet). A selection is the two cursors - Shift+drag was planned for it, but Shift+drag already zooms the values (T19), so it stays that. Conditions are looked for file by file, on the first signal's samples (other signals: nearest sample).
* Vector smoothing is a plain centred moving average (no Kalman filter, no outlier rejection); angles and quaternions are not smoothed. The last half-window of a live file is averaged over fewer samples until more arrive.
* *Time axis…*: another column as the time for CSV / text, MAT and Parquet; a scale also for HDF5. Flight logs and ROS recordings keep their own clock (only the offset). Cursor, zoom and notes follow the same rows to the new axis only when one file is open and its rows were not re-sorted; with other files open they stay where they are.
* The window needs an engine from about late 2020 or newer: Microsoft Edge WebView2 / Edge / Chrome 87+, or Firefox 78+. On an older one the app says so instead of starting.
* CAN: candump logs, Vector ASC (classic CAN lines) and CAN tables in CSV are read; CAN FD lines in ASC files, `.blf` and MF4 are not. The same id on two buses is decoded as one message.
* Messages in a byte stream (1.32): the framing found by itself needs a 2-byte header that recurs; one length or type
  byte (not two-byte lengths), fields at fixed offsets (no arrays, strings or layouts that depend on a field inside a
  payload); a proposed structure names its fields by place (`value_4`) - rename them; a payload that may hold the
  footer's bytes needs a length byte or a size per message (escaping is not undone). Request / reply pairing looks
  within 0.5 s. A recording made from messages has no file: the session keeps its definition and makes it again.
* The Messages panel (1.32): it looks for byte streams in the open files that are not logs (a `.tlog`, `.bin`, `.ulg`
  or `.mcap` is listed by its message types instead); a log's message types are its signals grouped by the name before
  the first dot, the count and rate those of its fields. An ICD layout used as a structure keeps its own time field as
  an ordinary field (a stream has its receive times).
* Listening to a link (1.32): one link at a time; serial ports need pyserial; nothing is sent (no handshake of our
  own); a growing `.svraw` is read again whole on each refresh - fine for hours of a serial link, slow for a very
  fast stream over a long time (stop and start a new recording).
* Binary layouts (ICD): fixed fields, bit fields and value names; no checksums (a damaged packet with a good sync and length is read), no arrays or strings inside a payload, no packets whose layout depends on a field.
* Your own readers run in a process of their own in the app (in Python and the command line they run in the calling process); a reader that never ends is stopped after `SV_READER_TIMEOUT` (600 s by default). Files read by a reader are reloaded whole in live mode, not appended.
* A spectrum (FFT, Welch, spectrogram) of a signal with gaps bridges them with straight lines on an even time grid: the frequencies are right, but amplitudes are lower by about the share of time the gaps cover. For exact amplitudes put the two cursors on a stretch without gaps.
* Telemetry logs (.tlog): messages that carry the autopilot's clock are placed on it (one offset per boot, the median radio delay); messages without it are at their receive time, so they include each packet's radio delay. Live, a boot's offset is learned from its first data and then kept.
* Sweeps: above *most lines to draw* (Settings, 200,000 by default) a parallel plot draws every run as density - a run in a crowded spot is part of a shade, not a line of its own (the rare runs are lines; hover and click reach the lines). A density picture is one colour when the colour is a number column. With no limit, a million runs of 12 columns take about 70 MB in the page and several seconds to draw on a PC without a graphics card.
* Sweeps, the goal's table: a limit is *at least* / *at most* on a numeric column; a category parameter, conditions in some scenarios only and *or* goals are set under *More options*.
* The legend beside the plot is chosen by an estimate of the names' widths; a plot whose names fit only just may stay above with a third row - *Legend ▸ Beside the plot* keeps it there. Above the plot, the header may grow once when the values first appear (then it stays until the pointer leaves the plot).
* Your groups of signals are kept in the session by signal id: a group's signals from a file that is closed are left out of it until the file is open again; templates do not carry groups yet.
* A made signal's *Change the formula…* is for formulas; the other operations (derivative, filter…) are made again in *Create signals*. A changed formula moves the signal to the end of the made signals' list.
* A coloured map track (by a state or a value) is drawn whole in 3D (not only the timeline's shown span); the value's colour scale runs from its lowest to its highest along that track.
* Sweeps: the Pareto levels are counted up to the tenth front; sets further back share level 11. With three or more objectives a Pareto chart shows two of them at a time (the front is the sets no other beats on all of them, so a front set can look beaten in one pair).
* The tab's band of state lanes (the flight mode, inside the top plot or - *Settings ▸ Look ▸ Mode band* - above the plots) is shown when the tab's time plots are in one column with X linked; with several columns each plot keeps its own lane.
* The faint copy of an object under the pointer on the map / in 3D follows time plots of the same tab only; the built-in *Flight* tab (map and 3D) has no time plot - add one to see it.
* A template keeps its default tabs; a line's dash chosen by hand (Inspector ▸ Line) is kept in the session, not in templates.
* In a segment comparison the difference view's times are since each segment's start: a click there does not move the cursor.
* Golden runs and Compare's tolerances are kept in the app's settings and in the tolerances file (*Save tolerances…*), not in a session or a template. The Compare panel pairs signals by name: a tolerances file's `"as"` (another name in the run) is used by `signalviewer-cli compare` and kept when the panel saves the file.
* Formulas keep a missing value missing (a sum, mean or norm in *Create signals* also offers to skip or bridge it; a formula does not yet).
* The data-quality summary is of a file as it was opened or read again; a file growing in live mode is not checked again as it grows. A state or event signal (a mode, a message) is checked for missing values only.
* The list of all events (modes, log events, findings, conditions, limits) is *Checks ▸ Events* of a flight log; for other files ] / [ and the command palette step through the conditions and limits.
* Tacview export (.acmi): the objects only (not the plots' other signals), 10 samples a second, the whole recording; a recording whose times are not Unix clock seconds starts at 2000-01-01 00:00 UTC in Tacview; an object without its own roll (drawn from its motion) is level. The file is plain text (Tacview also reads it zipped).
* Object guesses read names only: an object whose position signals do not share a prefix (`lat`, `lon` alone, or `gpsLat` with `navLon`) is offered through *Advanced…* rather than found; a motion attitude has no roll.
* Local positions (NED / ENU): the origin is one point - the first valid sample of the origin signals. A PX4 origin that is reset during the flight (`ref_timestamp`) is not followed. A position in cm or mm is found but not added until it is converted to metres (ƒ); bare `x / y / z` with no frame word are not guessed (ROS `pose.position`). ArduPilot's lane quaternions (`XKQ`) are not paired with the lanes - their own roll / pitch / yaw are used.
* Altitudes are compared as recorded: ArduPilot's POS / GPS / ORGN heights are above sea level, a position converted from ECEF is above the ellipsoid - comparing the two shows the geoid height (about 18 - 20 m in Israel) as a constant vertical error.
* A map saved as HTML embeds the offline basemap for the tracks' area within about 15 MB (the file says which zoom levels it holds); online imagery is used only if it was on and already in the app's cache. The 3D view saves a PNG only.
* *Compare with similar…* reads names of one file; the same signal across files is the Compare panel. *One plot at a time* is a way to look, not part of a session or a report.
* The 3D camera On the object and the map's smoothness depend on the graphics: on software rendering (no GPU) the 3D view uses lighter settings.
* Line styles: opacity is not a line setting (a setpoint's faded look is automatic).
* The Map's flat drawing (where 3D cannot draw, or *Always flat*) has no terrain relief, sky, shadows, cockpit camera or error surface; the error is shown by colouring the compared track instead.
* The offline 3D page draws the ground as a flat local plane (no earth curvature) - right for a flight of tens of kilometres, increasingly off beyond ~100 km.
* MGRS covers 80° S to 84° N; near the poles (the UPS grid) positions are shown in decimal degrees.
* Places: KML styles, folders and time spans are not imported (the shapes and names are); a polygon's holes are left out. Lines and areas are drawn 2 m over the ground in the light mode.
* Statistics of the shown window and the at-a-glance mean are plain means of the samples, not weighted by time: where a signal's rate changes, its faster part counts more. *The run at a glance* holds at most four numbers per run.
* *Parameters ▸ Compare with* compares two files at a time; a parameter changed during the run is compared by its first and last value.
* My maps take raster tiles only (PNG / JPEG / WebP MBTiles, XYZ / TMS servers); vector (pbf) MBTiles and WMS are not read. *Keep this area offline…* is offered only where the map's terms allow bulk downloads (the ground heights and your own servers), not for OpenStreetMap, Esri or OpenTopoMap.
* The height profile's ground is as fine as the heights the app has there (the bundled grids, `.hgt` files, kept areas); where it is coarse the profile says so.
* Story mode picks at most 12 moments; the reference object's track gives the computed ones (the other objects only through the pair).
