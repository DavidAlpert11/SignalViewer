# Changelog

## 1.1.0 – unreleased

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
- Coordinate frames: Create signals > Frames converts between NED, ENU, body, ECEF and LLA, with
  separate maths for a vector (velocity, acceleration… - rotated only; body needs the attitude,
  ECEF the vehicle's lat / lon) and a position (also moves the origin; NED / ENU are metres from
  a reference point - the first sample or one you enter). Creates three signals, one per axis,
  that update with their files and are kept in sessions.
- XYZ plot: any three signals as a 3D plot (a trajectory in metres, three sensor axes…) - not
  tied to the map. Rotate, move and zoom with the mouse; equal scale and "Z down" for NED.
  "Place on map" puts a track in NED / ENU metres on a map or 3D plot from an origin (the GPS's
  first fix, or typed in). Reports draw it in 3D.
- 3D view on computers without WebGL (old or virtual machines, remote desktop; recent Chrome and
  Edge no longer emulate it): a simplified 3D view of the tracks instead of an error.
- `python run.py` from the source folder always shows the current UI: after a pull or patch it
  builds the UI once by itself (Node.js needed) into an ignored folder, without touching the
  tracked `frontend/dist`. `--build` / `--no-build` to force or skip.
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
- Fixed: a web page open in your browser could, in principle, reach Signal Viewer's local server (DNS rebinding) and read or write files. The server now answers only requests addressed to localhost / 127.0.0.1.

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
