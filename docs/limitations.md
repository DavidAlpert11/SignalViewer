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
* Installed with pip, only the core readers are there until their extras are added (the app says which, see Download); it opens in the browser; `pip install "signalviewer[desktop]"` gives it its own window (on Linux that needs GTK or Qt).
* The interactive HTML report lists the notes under its summary; it does not draw them on its plots (the PDF and Word reports do).
* Columns with a time column of their own keep that column's unit: a `time_boot_ms` column stays in milliseconds (as the main time column always has), so it does not line up with a time in seconds.
