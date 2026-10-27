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
* Conditions: kept in the session (no shared library yet). A selection is the two cursors - Shift+drag was planned for it, but Shift+drag already zooms the values (T19), so it stays that. Conditions are looked for file by file, on the first signal's samples (other signals: nearest sample).
* Vector smoothing is a plain centred moving average (no Kalman filter, no outlier rejection); angles and quaternions are not smoothed. The last half-window of a live file is averaged over fewer samples until more arrive.
* *Time axis…*: another column as the time for CSV / text, MAT and Parquet; a scale also for HDF5. Flight logs and ROS recordings keep their own clock (only the offset). Cursor, zoom and notes follow the same rows to the new axis only when one file is open and its rows were not re-sorted; with other files open they stay where they are.
* The window needs an engine from about late 2020 or newer: Microsoft Edge WebView2 / Edge / Chrome 87+, or Firefox 78+. On an older one the app says so instead of starting.
* CAN: candump logs, Vector ASC (classic CAN lines) and CAN tables in CSV are read; CAN FD lines in ASC files, `.blf` and MF4 are not. The same id on two buses is decoded as one message.
* Binary layouts (ICD): fixed fields, bit fields and value names; no checksums (a damaged packet with a good sync and length is read), no arrays or strings inside a payload, no packets whose layout depends on a field.
* Your own readers run inside the app: a reader that hangs holds the opening of that file (the rest of the app keeps working); files read by a reader are reloaded whole in live mode, not appended.
* A spectrum (FFT, Welch, spectrogram) of a signal with gaps bridges them with straight lines on an even time grid: the frequencies are right, but amplitudes are lower by about the share of time the gaps cover. For exact amplitudes put the two cursors on a stretch without gaps.
* Telemetry logs (.tlog): messages that carry the autopilot's clock are placed on it (one offset per boot, the median radio delay); messages without it are at their receive time, so they include each packet's radio delay. Live, a boot's offset is learned from its first data and then kept.
