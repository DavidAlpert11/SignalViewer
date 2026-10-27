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
* The interactive HTML report lists the notes under its summary; it does not draw them on its plots (the PDF and Word reports do).
* Columns with a time column of their own keep that column's unit unless it is changed: *Time axis…* gives them one scale of their own (a `time_boot_ms` column → ×0.001), the same for all of them - a file whose own time columns are in different units can put only one of those units in seconds.
* The strip's rows are kept in the session, not in templates; a selection on the strip is made in the strip's run (saved as a condition it applies to every open file).
* The strip's flags are deliberately few: a signal that is mostly flat (a set point, a counter, a switch) is never flagged as stuck or saturated, nor is anything in the first or last 5% of the run. Files with more than 300 signals are scanned on their first 300.
* Reports: "Stretches together" (occurrences) plots are not drawn in reports yet; a finding's plot is the time plots of the tab it was found in (up to two) at its view. The journal keeps the last 200 steps; it is saved with the session, not with templates.
* Runs × conditions works on the open files: a folder of runs is opened (up to 200 files at a time, each read into memory) rather than indexed like the Fleet's flight logs. Parameters come from signals that hold one value and from numbers in file names; a side file of parameters is not read yet.
* What changed first finds a change in level (beyond 4 times the usual noise, 3 samples in a row); a change only in how a signal oscillates (same level, more shaking) shows only when it pushes samples that far. It reads the usual level well before the span - an event that has been building for longer than that is measured against its own start.
* What differs inside the stretches compares means (in units of the spread outside) - a signal that only changes shape, not level, ranks low. The overlay draws the first 200 stretches.
* Conditions: kept in the session (no shared library yet). A selection is the two cursors - Shift+drag was planned for it, but Shift+drag already zooms the values (T19), so it stays that. Conditions are looked for file by file, on the first signal's samples (other signals: nearest sample).
* Vector smoothing is a plain centred moving average (no Kalman filter, no outlier rejection); angles and quaternions are not smoothed. The last half-window of a live file is averaged over fewer samples until more arrive.
* *Time axis…*: another column as the time for CSV / text, MAT and Parquet; a scale also for HDF5. Flight logs and ROS recordings keep their own clock (only the offset). Cursor, zoom and notes follow the same rows to the new axis only when one file is open and its rows were not re-sorted; with other files open they stay where they are.
* The window needs an engine from about late 2020 or newer: Microsoft Edge WebView2 / Edge / Chrome 87+, or Firefox 78+. On an older one the app says so instead of starting.
* CAN: candump logs, Vector ASC (classic CAN lines) and CAN tables in CSV are read; CAN FD lines in ASC files, `.blf` and MF4 are not. The same id on two buses is decoded as one message.
* Binary layouts (ICD): fixed fields, bit fields and value names; no checksums (a damaged packet with a good sync and length is read), no arrays or strings inside a payload, no packets whose layout depends on a field.
* Your own readers run inside the app: a reader that hangs holds the opening of that file (the rest of the app keeps working); files read by a reader are reloaded whole in live mode, not appended.
* A spectrum (FFT, Welch, spectrogram) of a signal with gaps bridges them with straight lines on an even time grid: the frequencies are right, but amplitudes are lower by about the share of time the gaps cover. For exact amplitudes put the two cursors on a stretch without gaps.
* Telemetry logs (.tlog): messages that carry the autopilot's clock are placed on it (one offset per boot, the median radio delay); messages without it are at their receive time, so they include each packet's radio delay. Live, a boot's offset is learned from its first data and then kept.
