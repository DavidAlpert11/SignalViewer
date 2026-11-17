# Signal Viewer – user guide

Signal Viewer is a workbench for analysing and validating any time-series data – flight, vehicle and
bench tests, simulation output, ROS 2 and CAN recordings – as plots you can zoom, measure, check and
compare. Everything runs on your computer; nothing is sent anywhere.

## 1. Start

- **Windows:** install `SignalViewer-Setup-X.Y.Z.exe` (for you only, no administrator rights), or
  extract the portable `.zip` and double-click *Signal Viewer.bat*.
- **Linux / macOS:** extract the `-portable.7z` and run `SignalViewer/SignalViewer`.
- The first screen offers **examples** (a drone flight, the same mission flown twice, three car runs,
  an ArduPilot log, a pump on a test bench…). One click opens one ready to look at – the quickest way to learn the app.

## 2. Open your files

- **+ Open files** in the file list (Ctrl+O), or drop files on the window. CSV and text tables, MATLAB `.mat`,
  ArduPilot `.bin`, PX4 `.ulg`, MAVLink `.tlog`, ROS 2 `.mcap`, HDF5 and Parquet are read directly.
- From Windows Explorer: right-click a file → **Open with → Signal Viewer**. If the app is already
  open, the file opens in it.
- **Ctrl+P** (recent and favourites) lists the files and folders you used lately.
- Beside each file: the time the version on screen was saved. When another program saves the file
  again, the time turns amber - click it (or press **F5**, which refreshes every open file) to read it.
- A CSV with an unusual layout: tick *Show import options before opening* in the open dialog to choose the delimiter,
  the time column and the header row, with a live preview.
- **The time axis of an open file** (right-click the file → *Time axis…*): another column as its time
  (CSV, MAT, Parquet), its unit (*ms → s*, *s → min*… or any scale), and its offset. The dialog says
  first what changes: a column that goes up and down, repeated or missing values, new signals computed
  against time (derivative, integral, filters), plots that show the column. One Undo puts it all back.

Each file gets a **colour and a short tag** (A, B, C…). Signals of the same name from several files
are told apart by them.

## 3. The screen

- **Top:** one row - the work areas as one switch (*Recordings* - your files and plots, *Sweeps* - a run
  envelope's results table), then the Recordings tools (open /
  save, templates, live, undo / redo, clear, Inspector), Ctrl+K, Settings, the theme, the language and Help.
- **Left:** the panels – *Data* (the open files and their signals), *Create signals*, *Compare runs*,
  *Investigate*, *Report* and *Checks* (the verdict, structure and parameters of any file - section 10).
- **Middle:** the plots of the current tab. The plot tabs are in the bar above the plots: **+** makes one, **▾** opens a
  template or collection - and a template's other tabs: a template may open only its default ones
  (the ArduPilot full review: Attitude and Flight) and keep the rest there, their number on the ▾.
  The layout button (1 × 1) splits a tab into rows and columns. When a tab's plots share the time,
  its flight-mode lane (or any state signal) is a thin coloured band inside the top plot, lined up with its
  time axis (*Settings → Look → Mode band* puts it above the plots instead). The timeline shows the same
  modes as colour along its track.
- **Bottom:** the timeline – play, the time shown, the cursor. Time is written in seconds as
  recorded, like the axes; *Settings* (the gear, Ctrl+,) can show a clock from the start instead,
  and holds the theme and the text size.
- **Right:** the Inspector – values at the cursor, statistics, the selected signal's settings.

## 4. Plot

- Click a signal in the list to add it to the **active plot** (the one with the coloured frame), or
  drag it onto any plot. Drop on a plot's right or bottom edge to make a new plot there.
- The button next to the plot's title (**Time ▾**) changes the plot's type: Time, X-Y, 3D (XYZ - any
  three signals on plain axes), Map, FFT, Spectrogram, Envelope (many runs of one quantity), Video. The **Map**
  is the earth with its terrain; its bar has the camera *Free · On the object* (the object chosen beside it),
  + / − / fit, *Relation* (the relation box shown or hidden), and its extras (a third object, data,
  events, measure, its own time). The mouse's position is shown in a corner: latitude, longitude, the ground
  height there and the distance / bearing from the reference. Where the computer cannot draw 3D (remote desktops, some virtual machines) the Map is drawn flat
  and says so in one quiet line.
- **Right-click a legend chip** for its options: second value axis, show as states, move, remove…
- **Many signals in one plot?** The legend moves into a column beside the plot by itself (a row per
  signal, the values aligned, a filter); the plot's menu ▸ *Legend* puts it above, beside or hides it.
  Point at a name to bring its line to the front. Each line shows its value at the cursor (and the change
  Δ between the two cursors) in a monospaced number with its unit.
- **Statistics of what is on screen:** the plot's ⋯ menu ▸ *Legend* ▸ *Statistics of the shown window*
  shows beside each line its lowest, mean and highest value over the time on screen, recomputed as you pan
  and zoom - fast on signals of tens of millions of samples. The mean is the plain mean of the samples in
  the window, not weighted by time: where the rate changes, the faster part counts more.
- **Your own groups:** select signals, right-click ▸ *Group these* ▸ *New group…* and give it a name;
  `/` in the name puts a group inside another (`Nav/IMU`). *My groups* is at the top of the list.
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
- **What changed first?** On the selection bar: every signal of the event's file in the order it left
  its usual range around the span - candidates, not causes - and the lag between any two of them.
  Under each, the same signal in the other runs: a change that a run without the problem has too
  does not explain it alone. On a long log, filter the list or take rows and groups out with ×.
  Try it all on the example *find out what went wrong*: [the tutorial](investigate-tutorial.md).
- **Runs × conditions** (button under the conditions): every open run against every condition, with
  what tells the runs apart (a payload, a gain, the number in the file name). The odd run is marked; a
  click opens it at the stretch. *Open a folder of runs…* brings in a whole Monte-Carlo set.
- **The run at a glance**: the strip above the plots - flags (a frozen or saturated signal, a gap, a
  glitch) and rows of state signals or conditions (**+** adds one; click a row's name to replace,
  move or remove it). Click a stretch to pick it, Ctrl or Shift+click to add one (same row: *or*, another
  row: *and*); **Save as a condition** keeps the selection. Double-click zooms; × hides the strip.
- **Findings and the report**: give a note a status in the Inspector (open, explained, fault,
  rejected hypothesis) - it keeps the view it was found in. The Investigate panel keeps the steps you
  took; tick the ones for the report. *Include the investigation* in the Report panel puts the
  findings (with their plots), the rejected hypotheses, the steps, the conditions and how to
  reproduce it before the plots. Save a template while investigating: it keeps the conditions for
  the next flight.
- **One into each plot, and the error per axis**: select the true X, Y, Z and choose *Each in a new
  plot* (▾ beside *Plot them*); then select the flight computer's X, Y, Z and choose *One into each
  plot* - X goes with X by name. ⋯ on any of those plots → *Error in every plot with two lines*: the
  errors in a new tab, with RMS, the largest error and when.
- **State lanes** (flight mode, gear…): right-click the lane, its chip or the signal in the list to show
  it on this plot only, on every plot of the tab, or on every time plot of every tab - or remove it.
  *Always as a state* makes a signal a lane wherever it is added, in every file.
- **Map and 3D objects:** *Add object* on a Map or 3D plot lists the **objects found in the
  recording** - every prefix with a latitude and a longitude under it (`phys.lat`, `nav.att.roll`,
  `ins2_lat`), classified as *truth*, *navigation* or *receiver* by the words in the prefix.
  **Add all** adds them in one step (one Undo); untick a row and **Add selected** for some. **Why?**
  says which signals were taken and by which rule, what is missing and what almost matched (`yaw_cmd`,
  a misspelt `lattitude`). Each object takes its signals from its own prefix only - a GPS's position is
  never mixed with the navigation's attitude.
  The *Position on the map* template adds every object of the file the same way, and when a file
  with objects opens, a line in the file panel offers them (*Add all*, *Choose…*, *Why?*, × to hide it).
  Truth is drawn as a line, a navigation solution dashed, a receiver as points (*Track* changes it).
- **Lines:** *Settings → New lines* sets the width and style (solid, dashed, dotted, dash-dot) of every
  line added from now on - the lines already drawn keep theirs until *Apply to all open plots*. A line's
  own style is in the Inspector; *Auto* dashes a setpoint beside its measured value by itself.
  To style many lines at once, right-click a group in the signal list → *Style the lines…*: one colour
  (or the palette, a colour each), a width and a style for its lines in this plot, this tab or every
  tab; a field left on *Keep* stays as each line has it. Lines picked in the legend with Ctrl+click get
  the same from the Inspector (*Style these lines…*). One Undo takes it back.
- **Moving plots:** drag a plot by the ⠿ beside its title onto another plot, or *Move to…* in the plot's
  menu, or Ctrl+Shift+arrows on the active plot: the two plots change places (Undo puts them back); the
  sizes of the cells stay. *Move to…* also lists the other tabs and *New tab* - the plot goes there as it
  is (its lines, axes, cursors, a map's objects); dropping it on a tab's name does the same (Ctrl: a
  copy). *Add its lines to…* joins a plot's lines to another plot of the same kind (Shift+drop on that
  plot); the source plot is then removed.
- **One plot at a time:** **M** (or the layout button ▸ *One plot at a time*) fills the tab with the
  active plot - for a small screen, or to show one plot to a room. 1 - 9 show the others; M or Esc brings
  all of them back. The layout itself is not changed.
- **A line that looks flat:** adding a small signal to a plot of large ones (a current of 12 A beside
  3000 rpm) brings a message with *To the right axis* and *To its own plot*. Nothing moves until you
  choose; it is said once per plot and signal.
- **Hiding an object:** the eye before an object's name in the chips above the map hides it (Alt+click: only
  this one; again: all). It is not drawn and *Fit* ignores it; its chip stays, struck through, for one click
  back. In the offline pages a click on the legend does the same.
- **Export the flight** (a map's or a 3D view's ⋯ menu ▸ *Save / export*) has three ways out, all from the same samples:
  - *Tacview (.acmi)…* - a Tacview ACMI 2.2 file: each object's position (altitude above sea level, by
    its altitude reference) and attitude as the 3D view draws it, 10 samples a second (fewer for a very
    long recording - the message says so). Each object gets a model Tacview has a 3D shape for (C172,
    MQ-9, DJI300, AIM-9M, Zodiac, Pickup by its kind) and its own name as the call sign, so Tacview no
    longer draws it as its plain triangle. An object with no attitude of its own is written without one.
  - *Tacview CSV files (a folder)…* - one CSV per object, named as Tacview's CSV import wants
    (`C172 (POS) [Blue].csv`). In Tacview: File → Open the first, File → Merge the others (Tacview
    Standard).
  - *Google Earth (.kml)…* - a track per object; with real dates in the log Google Earth plays it with
    its time slider.

  Times that are Unix clock seconds become the file's reference time; otherwise the flight starts at
  2000-01-01 00:00 UTC in Tacview. An object with no position in the file (latitude and longitude 0, 0
  in every sample - ArduPilot's EAHR without an external AHRS) is left out, and the message names it.
  The shown places go too: the ACMI file has the points as stationary waypoints, the KML every shape.
- **Places** (the Map's ⋯ → *Places…*, or Ctrl+K *Go to a place…*): named points, lines and areas on every
  Map - the airfield, the range, the ground station. Right-click on the Map → *Add a place here…*; *Add a
  place…* takes a typed position (`32.687, 35.39` or `32°41'13"N 35°23'24"E`); *Mark this spot* on an
  object's chip puts one where it is at the cursor; *Import…* reads `.kml`, `.kmz`, `.geojson` and `.csv`
  (`name, lat, lon[, alt]`). The panel has two lists: *Places of this session* (saved with it and its
  template) and *My places* (yours, in every session - ★ moves a place there). A click flies the camera there;
  the search box also takes a position; *Save this view* keeps the camera by name. The mouse readout says
  how far the nearest place is, and the relation box can compare the reference with a place.
- **The Map's camera** is *Free* (move it yourself) or *On the object*: the camera stays on the object as the
  replay moves it; drag to turn around it, the wheel (or + / −) goes nearer or further - always towards the
  object itself, all the way in to sitting on it (its own model is hidden there) and looking where you turned.
  Every change flies there; a session saved with one of the earlier cameras (From above, Around it, Behind
  it, Cockpit, Look at) opens Free, or On the object when it followed one. A **double-click on an object** puts the
  camera on it (elsewhere: Fit everything, Free); Ctrl+K has *Map camera: on …* / *Free*. With the 3D view clicked,
  the keys: **F** on the object / Free, **arrows** look around the object (Free: move over the ground), **+ / −**
  zoom, **0** fits everything. *Display* shows the flight display of the
  object the camera is on (attitude, ground speed, altitude, heading; shown by default while sitting on it - the
  wheel and drags go through it);
  a mini-map shows the whole flight while the camera is near an object (a click flies there). When the
  reference and the compared object are one vehicle (truth and a navigation solution), an **error
  surface** between their tracks shows where the solution left the truth (its scale and toggle are in the
  relation box). On a computer without graphics acceleration the sky, shadows and surfaces stay off.
- **▶ Story** (the Map's bar, and beside Play in a live HTML page): the flight tells itself - the time runs
  and stops at each moment that matters, the camera flies to the object, a card says what happened. ◀ ▶ step
  through the moments, Esc ends it, a click on the card stays there.
- **Settings → Map and objects** (for new things only - a session already open does not change): the icon
  a new object gets by its class (truth, navigation, receiver, other), the camera of a new Map, *Always
  flat* (the light drawing), the relation box and names shown or hidden, the track's width, the model size,
  m / km or ft / NM, coordinates as decimal degrees, degrees-minutes-seconds or MGRS, the folder of your
  elevation files, the export rate for Tacview / KML and the Story's length. *Reset this group* restores them.
- **Moving the map:** drag it (a quick drag glides on), zoom with the wheel or **+ / −** in its corner,
  **Fit everything** (or a double-click) shows every track, **Follow ▾** keeps an object in the middle -
  dragging while following moves the map around it, *Back to following* centres it again. Click the map
  and the keys work on it: arrows move it, + / − zoom, F follows, 0 fits everything (Shift+←/→ still
  step the cursor). *Settings → Camera following an object*: *Smooth* (default) eases after the object,
  so a noisy position does not shake the view; *Exact* stays right on it.
  Drawn flat, On the object has the **N** button: the map turns with the object (its heading up) and back
  north again. A line at the bottom says what the
  mouse does.
- **The map's background:** the *Map* button in the corner of every map (2D and 3D) shows each background
  as a picture of the place on screen - *Offline* (the default, shipped with the app), the online maps
  marked ☁ (*Satellite*, *Satellite + roads*, the street and topographic maps; greyed out with the reason
  when *Settings → Never use the network* is on), *Borders* (country borders and names over the map, with
  no internet too) and **My maps**. Opening the picker downloads nothing.
  - **Add a map…** takes a raster **MBTiles** file (fully offline) or your organisation's tile server
    (XYZ / TMS, for example on the local network); it is used like any background in 2D, 3D and exports.
    *Never use the network* blocks a server on the internet, not one on this PC or a private address.
  - **Keep this area offline…** downloads an area's tiles at the zooms you choose before going to the
    field - the size is estimated first, with progress, Stop, and the kept areas listed with their size and
    Delete. Only where the map's terms allow it (the ground heights and your own servers); OpenStreetMap,
    Esri and OpenTopoMap forbid bulk downloads and the dialog says so - places you look at are still kept.
- **Height profile:** *Profile* under the map bar's ⋯ shows, under the map, the object's height and the ground
  under it along the distance, for any recording with positions. The cursor's moment is marked; a click in
  the profile moves the cursor. Where the ground data is coarse it says so and how to get finer ground
  (`.hgt` files, or *Keep this area offline…*).
- **Arrows along the path:** any two signals that are north and east components - a wind, a velocity, a
  force - drawn as arrows along an object's track, on the map and in 3D (the object's settings ›
  *Arrows along the path*). The file's own pair is offered by itself (an ArduPilot log's estimated wind, a
  CSV's velocity).
- **The rings - the reference and the compared object:** with two objects or more on a map, one is the
  *reference* (a solid ring; also called the primary) and one is *compared with* it (a dashed ring; the
  secondary) - by default the truth and the first navigation solution. The relation box, the
  comparisons and the errors are measured from the reference. Point at a ring to read this; the chips
  above the map carry the same ring marks. **Choose them in the box's first line**: *Reference*,
  *Compared with*, and ⇄ to swap - the same in the 3D view. Shortcuts: click an object (Shift+click for
  the compared one), the chip's right-click menu, Q / Shift+Q and X while the map has the focus.
  The box in the map's corner shows, at the cursor: the **range** (straight line), the **horizontal**
  distance, **Δalt**, the **bearing** from the reference, the **relative bearing** (from its heading, +
  = right), the **closure** rate (+ while they close) and the time to the **closest approach**, the
  **heading difference** (0-180°) and the compared object's **aspect**: the angle at it between its
  tail and the line to the reference - 0° the reference right behind it, 180° nose to nose, with L / R.
- **Compare objects…** (the **Compare…** button of the relation box; Ctrl+K ▸ *Compare objects…*): one
  dialog for "how does each object differ from the one I trust". Choose the *Reference*, tick the
  objects to compare and the quantities - *Position*, *Velocity*, *Attitude* (one that an object does
  not have is greyed with the reason) - then *Values*, *Errors vs the reference* or *Both*, and the
  frame: NED / ENU in the reference's local frame at each moment, ECEF, LLA (in metres) or the track
  frame (along / across its heading). **Make** opens a tab per quantity: a row per component, the values
  of every object on the left and each object's error on the right, and a row of horizontal / vertical
  / 3D error. Every line is named by its object and has the object's colour from the map. The dialog
  then shows the **statistics** of each error on the full data - RMS, mean, largest |error|, 95 %, and
  the time of the largest: click that time and the cursor goes there in every plot and on the map.
  *Copy* and *Save CSV…* take the table out. *One click* at the top keeps the four earlier actions:
  *Plot over time* (the box's values as signals), *Error signals* (`nav_vs_phys.err.*`), *Differences*
  and *Overlay*. One Undo takes a comparison back.
- **Compare with similar…** (right-click a signal or a group in the list; Ctrl+K): finds the signals of
  the same file whose names differ in one part only - `nav1.att.roll`, `nav2.att.roll`,
  `truth.att.roll`; `XKF1[0].Roll`, `XKF1[1].Roll` - and lists them as families. Tick the families,
  choose the reference member (a *truth* one is suggested) and *Values* / *Errors* / *Both*; **Make**
  opens one tab, a row per family. Angle differences are wrapped (359° − 1° = −2°, not 358°). *More
  matches* also offers names one or two letters apart, each with why it matched. The same signal across
  *files* is the Compare panel's job.
- **A map out of the app:** a map's menu ▸ *Save / export* has *Save image (PNG)* - this view, or fitted to all the tracks
  - and *Save as HTML (opens offline)*: one file with the map, the tracks, a time slider that moves the
  objects and their values on hover; it needs no network and no Signal Viewer. Reports (PDF, Word,
  HTML) now include the tab's maps.
- **From a script:** everything above - finding the objects, comparing them, the statistics, the map and
  the report - is also a Python call, a command (`signalviewer-cli objects | compare-objects |
  compare-similar | map`) and a local REST request, with the same numbers. See *Scripting API* and
  *Command line* in the documentation.
- **An attitude for a position-only object** (*Attitude* in its row or its form): *from motion* points it
  along its course over ground and pitches it by its climb (roll unknown; below *Hold the heading below*,
  1 m/s by default, the heading stays as it was, so a hovering drone does not spin); *from <object>*
  borrows the angles of another object - use it when the receiver rides on that vehicle. Either way the
  icon is drawn as an outline and its chip shows ≈.
- **How to name your signals** so the guess just works: one prefix per object,
  `<object>.lat / lon / alt / roll / pitch / yaw`, sub-groups allowed (`<object>.att.roll`,
  `<object>.pos.lat`); aliases work too (latitude, lng, altitude, phi / theta / psi, heading). The words
  truth / phys / sim, nav / ins / ekf / ahrs and gps / gnss in the prefix set the class. Example with
  three objects: `truth.lat, truth.lon, truth.alt, truth.att.roll, …, nav.lat, nav.lon, …, gps.lat,
  gps.lon, gps.alt`. Flight logs (ArduPilot, PX4, MAVLink) are paired as before (POS with ATT).
  **A position in metres** is found the same way: `<object>.ned.x / y / z` (or `<object>.pos.north /
  east / down`; `… / up` makes it ENU), `<object>.ecef.x / y / z`; the forms `x_ned`, `ned_x`, `ecefX`
  work too. NED and ENU need an origin: `<object>.origin.lat / lon / alt` (or `ref_lat / ref_lon /
  ref_alt` inside the object, or a group named `origin`, `ref`, `home` or `datum` beside it) - an origin
  is never offered as an object. Every ArduPilot EKF lane (`XKF1[n]`, `NKF1[n]`) is found with its own
  attitude and placed through `ORGN`; PX4 and MAVLink local positions through their own origin. A row
  that says *needs an origin* opens *Advanced…* with a suggestion; a position in cm or mm is listed but
  not added until it is converted to metres (ƒ). Bare `x / y / z` with no frame word are not guessed.
- **One object by hand:** *Advanced…* on a found row (or *Add one by hand…*) opens the full form. Its
  position and attitude are filled in from the signals' names; to choose another, type part of its
  name in the field. Beside each field
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

The **timeline** under the plots maps the whole recording: the active plot's first line is drawn faintly
along it, and what the plots show is a window on it - drag the window to move along the recording, pull
one of its edges to zoom, double-click it to show everything (Backspace undoes a move).

## 6. Measure

- **Space** turns the cursor on; click to place it; ← → step sample by sample.
- **D** adds a second cursor: each line's chip shows how much it changed between the two (**Δ**,
  cursor 2 − cursor 1), and the Inspector shows the difference and the statistics between them (min,
  max, mean, RMS…).
- Put the cursor on a moment and press **N** to write a note there; with two cursors the note covers
  the time between them (shaded). Notes show on every time plot and in the report.

## 7. Compare runs

- Open the runs together; plots show each signal once per file, in the file's colour.
- **Compare runs** (left) compares each signal with a baseline run (or the mean of the runs): RMS and
  largest difference, correlation, a tolerance; its table lists every signal found in two or more
  files, the worst first. With a tolerance every signal shows ✓ or ✗, and the one you pick shows its
  difference from the baseline over time: the tolerance band shaded, the stretches outside it in red
  and listed - a click takes you there. Under the picked signal, **This signal's tolerance** gives it a
  tolerance of its own or leaves it out; **Save tolerances…** writes them in the file
  `signalviewer-cli compare --tolerances` reads, so a CI job judges the next run the same way.
- **] and [** jump to the next / previous event - a mode change, a log event or error, a health
  finding, a condition, a signal outside its limits; the status bar says which. *Checks › Events*
  (for a flight log) lists them all.
- **! beside a file's name** (and on some of its signals): its data has something to know - values
  missing, time with no data, repeated or backwards time stamps, a rate that changes. Click it (or
  right-click the file → **Data quality…**) for each signal's details.
- **≈ on a legend chip** (and a word in *Create signals*' list): the signal rests on an assumption -
  values read between another signal's samples, a filter run stretch by stretch, missing values left
  out or bridged; hover it for exactly what. The status bar says **● Online map** whenever map tiles
  are being downloaded.
- **Judging a run against a golden run**: in Compare, with the golden file as *Compare against* and a
  tolerance, the **verdict** says per file ✓ or ✗ and how many signals are outside; **Show the worst
  failure** opens that signal's difference over time, **Report…** makes a tab of the failing signals and
  a report that starts with the verdict. Tick **★ Golden run**: the next recording you open with its
  signals is offered *Judge it against …* on the start card - the golden run, its tolerances and the
  verdict in one click.
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

**A signal that updates slower than it is logged.** A value computed at 10 Hz but written at 100 Hz
repeats itself; its plain derivative is zero, then a spike. For a *Derivative* or an *Integral*,
choose **Updates of the signal**: *at its own, slower rate* (give it in Hz), or *where another signal
is 1* (a 0 / 1 flag the logger writes when the value updates). The derivative or integral is taken
on those samples alone and put back on every sample. In a formula: `deriv(Altitude, 10)`,
`deriv(Altitude, {Alt_updated})`, `integ(...)` the same way.

**Convert units:** right-click a signal → *Change this signal…* → *Convert units* (rad → deg,
m/s → km/h, m → ft, °C → °F…; the ones from the signal's unit first). The values and the unit
shown change together – on the axis, in the list, in the legend – and it can be undone like any change.

## 9. Keep and share your work

- **Save session** (the disk icon at the top left, Ctrl+S; opening one: the folder icon next to it, Ctrl+Shift+O) keeps everything – files, tabs, plots, zoom, notes. The app also
  restores your last work by itself when it starts.
- **Templates** (the top bar): save a tab or a whole set of tabs as a template, and open it later on
  other files with the same signals.
- **Send it as one page** (Report, at the top: *Save the page (HTML)…*; Ctrl+K: *Send this view as a replay
  page* for the tab alone): one HTML page for a colleague, with the report's title, notes and conclusion below
  when written. It
  opens in any browser with no install and no network, on the moment you were looking at; a click on
  any plot or on its timeline moves the cursor in every plot and on the map, **Play** (Space, or P as in the app) plays
  it, a drag zooms every plot, and the log's errors, warnings, findings and your notes are marks to jump
  to. The page's address keeps the moment (`…replay.html#t=125.4`), so a link can point at a time.
  *Open it* in the message shows it in your browser before you send it.
- **Report** (left): a report of the plots, statistics and notes – previewed in the app, saved as
  interactive HTML, PDF or Word. Every report opens with **The process in brief**: the data, what was
  checked (the log's own check, Compare's verdict, the investigation), what it shows and the conclusion –
  write the conclusion in *Summary* (the panel reminds you when it is empty). **The HTML report is one live page**: a time bar at the bottom moves every
  plot's cursor, the map and the 3D view together, with Play and the log's marks, while each plot keeps its
  own zoom and statistics. The 3D view is in it live (turn, zoom, the camera *Free · On the object* on an
  object; *Closest in* goes to that moment; a *Trail* of the last seconds; an attitude indicator; where the browser has no 3D graphics, its picture), and the map and the 3D
  view have the same buttons and the same relation box as in the app (hide it with *Relation*); in PDF and Word every plot, the map and the 3D view are pictures. A plot that
  cannot go into a report (a video, occurrences) is listed greyed with the reason.
- A plot's **⋯** menu ▸ **Save / export**: export the data (CSV), save the image (PNG, SVG), **save an image for a
  report** (a PNG with twice the pixels), **save as an interactive page** (HTML: the plot alone - zoom,
  lines on and off, values under the pointer). *Copy image* is a line of its own in the menu. The 3D view's **⋯** saves its image at
  the screen's size or at twice it, and removes the 3D view. A map whose object already draws the track
  shows no Lon / Lat pickers; **⋯ ▸ Lat / lon track** brings them back.
- **Clear ▾** (the top bar): this tab's plots, the other tabs, all
  tabs, or all the work on the data - tabs, notes, derived signals and edits - while the files stay
  open. Each is undone with **Undo** in the message or Ctrl+Z. *Everything* also closes the files
  (it asks first).

## 10. Checks: any file's verdict, structure and parameters

**Checks** (the left rail) works with every recording, not only flight logs. Its tabs:

- **Checks** – one verdict first, then tinted cards (green / yellow / red edge): your limits, the data
  quality (gaps, repeated or backwards time, missing values) and, for a flight log, the log's own health
  check. A card's signals plot with one click.
- **Events** (flight logs) – the modes, log events, errors, messages, findings, conditions and limit
  violations in one list, in time order.
- **Parameters** – the parameters of the run, for every format, in one list: a flight log's parameters, a
  MATLAB file's scalars, texts and struct fields, signals that hold one value the whole run, numbers in the
  file name; each says where it came from. **Compare with** another open file shows only what differs
  (a parameter changed during the run counts by its value at the start and at the end). *Compare runs ›
  Runs × conditions* shows the same settings when they differ between the runs.
- **The file** – the structure of any recording: a log's message types, a ROS bag's topics, a MATLAB
  file's structs, a table's column groups - each with its rate, samples, units and gaps, the time base and
  the values at the cursor; a live file as it grows. Click a column to plot it.
- **Instruments** – big readouts of each chosen signal's latest value at the time, and the attitude
  indicator with heading, altitude and ground speed. While live (a MAVLink link, data sent from Python, a
  file being written) they show the newest data; a reading that stopped arriving says how old it is.
  *Add an instrument…* adds a tile, ✕ removes one (Undo works); a template brings its own.
- **Hardware** (flight logs) – the board, firmware and sensors decoded from the log.

**The run at a glance** (above the plots) names each run with up to four numbers – max altitude, battery
used, lowest voltage… – in mono beside its name: a click goes to its time, ⋯ unpins it, and a number the
file does not have is said, not hidden. Pin one from the Inspector (the ☆ beside a statistic) or let a
template bring them: a template is also a **profile** - its at-a-glance numbers (the maximum, minimum,
mean, first or last value of a signal over the whole run), its instruments and its pinned searches for the
signal list (☆ beside the search box). The built-in ArduPilot, MAVLink and PX4 templates bring theirs; a
template you save keeps yours, so a test bench or a simulation gets its own. A *Checks: n failed · m to
look at* chip opens Checks on that run.

**A test bench, pass / fail in CI.** *A pump on a test bench* (Help → Examples; `examples/bench`) is a
run recorded as Parquet - phases as a state, units, a 0.2 s pressure spike, a 2 s gap and a motor
temperature that creeps over its limit. Its `checks.json` holds the same limits for the command line:

```bash
signalviewer-cli check examples/bench/pump_run_07.parquet --checks examples/bench/checks.json
```

2 of its 4 checks fail, on purpose; the exit code (1) fails a CI job. See [Command line](command-line.md).

## 11. Flight logs

ArduPilot and PX4 logs open with ready views (attitude, rates, vibration, battery, GPS, the map and
the flight modes as coloured lanes; a setpoint such as DesRoll is drawn dashed beside its measured
value) and a **health check** that points at what is worth a look - its findings wait beside the
timeline (*3 to look at*) and are ◆ marks on it; a click plots the signals behind one. *Checks* lists
the log's events, parameters and hardware too. On the map, an object's *Track colour* can follow the
flight mode (or a value such as the altitude), with a key, and *Arrows along the path* can show the
log's estimated wind.

### A folder of recordings { #folder }

Many recordings of the same kind - every flight of two copters, a test run a day - are summed up one row per
recording: **Sweeps ▸ Data ▸ *From a folder of recordings…*** (also under Sweeps' *Open ▾*; or *Investigate ▸ Runs matrix ▸ Summarize a
folder*). Each recording gets the same **measures** (the highest `VIBE[0].VibeZ`, the lowest `BAT[0].Volt`,
the last `BAT[0].CurrTot`…) and parameters read from its name (`{vehicle}_{date}` reads `X8-A_2026-09-02.bin`
as vehicle X8-A, date 2026-09-02). The folder is read one file at a time, so hundreds of files of any format
are fine. A `measures.json` beside the recordings (the Runs matrix's *Save measures*) is used at once;
without one, the folder's first recording opens with the Runs matrix to define them on it.

In Sweeps each row keeps a link to its recording (the *recording* column): tick the rows that need a look and
*Open in Recordings* opens them together, their signals side by side. The welcome card *A folder of
recordings* shows it on ten flights of two copters: X8-A's vibration grows flight after flight (18 → 67),
X8-B's battery drops on its last flight.

## 12. Live data

**Live** (the top bar, beside undo) follows files that are still being written – a CSV growing, a MATLAB file saved
again and again – and can connect to a MAVLink stream. From Python, `signalviewer_push.show(...)`
sends arrays straight into the running app.

While live, the time (cursor) stays at the newest data, so the values read at it and the objects on
the map and in 3D move with each update; move it back to look at a moment, press **End** to follow
again. To try it without a logger: `python tools/live_demo.py` writes an aircraft and a ship that
keep moving – open both files, add an object from each, press Live. *Checks › Instruments* shows the
newest values as big readouts while live.

## 13. Sweeps: which parameters hold

**Sweeps** (the top bar, next to *Recordings*) is for the results of a run envelope: a table with a
row per run – the parameters you choose, the scenarios you don't (wind, payload, seed), and the
outputs. It answers *which parameter sets hold in every scenario, and which of them is best?* Try
*Try an example* on its first screen: a drone's roll controller swept over wind, payload and gusts.

Four steps, left to right:

1. **Data** – every table you load is listed apart in *Tables in this study*: tick, show (as rows or
   as lines - the wheel zooms, a click on a line shows that run), export (CSV, or HTML with its
   parallel plot as you left it) or close. **Merge** makes a new table from the ticked ones - the
   rows one under the other, or side by side on key columns (join) - with a source column if you
   want it; the tables merged stay. The tables' column on the left (only in Data; drag its edge to
   widen it) chooses the table the next steps work on, and *Remove from the study* (×, with Undo) takes
   one out (see *Studies* below).
2. **Columns** – check each column's role: parameter, output, condition (what you don't choose:
   wind, payload), identifier (a run id or a recording), not used. Above the table: undo, redo,
   *Reset to guessed roles*, *Template ▾* (save to a JSON file to share, load - it says what matched)
   and the study's numbers. In the side panel each condition's values (search, *+N more*, a range),
   and new columns made from others (the formula completes names and shows the first run's value).
   *Split results by this* on a condition studies its values apart (below).
3. **Goal** – one table: *at least* / *at most* on any column (`roll_error_deg` at most 5 - an output
   in every condition, judged by the worst case) and what to optimize (the least `energy_wh`).
   Optimize two or more (the least energy *and* the least roll error): choose how they are ranked -
   the weighted score or the Pareto front - and **Show the Pareto front** for the trade-off, the
   balanced set starred.
   Ctrl / Shift-click choose several rows and set them together (a value, or a % of each one's
   range). The count and the best set follow each change.
4. **Results** – *Show: Holds ▾* (all, those that hold, those that fail, a group) for the table, the
   lines and the export; the parameter sets and every run as lines (*All runs* adds each scenario as an
   axis, after the parameters - how the runs spread over every scenario; drag on an axis to keep a range,
   as in HiPlot; Keep, Exclude, undo; zoom), *Why it fails* for any set, **Charts** (as many as you
   like, each exported as PNG or HTML, in the report or not), **Next runs** (where to run more, the
   budget shared equally, in proportion or by hand; and the re-run list you collect) and the
   **Report** (HTML, Word or PDF with the whole process). *Clear ▾* empties the charts and lists, the
   goal, the whole study, or closes every study.

   **A big table.** The plot draws every run up to *Settings → Sweeps: most lines to draw* (200,000
   unless you change it); above that it draws a sample of the runs your filters keep and says so under
   the plot. The count, *Keep*, *Exclude*, a group saved from the brush and *Export shown* always use
   every run.

**Split by a condition.** With *Split results by this* on, say, payload, the results show *All
together* or one payload at a time: for one value a set must hold in every combination of the other
conditions with it (the same goal). *Best set per value* puts them side by side; *A group of each
value* colours the sets that hold for each. A set added to the re-run list then runs with that
value only.

Ctrl+Z undoes any step, the study is kept when the app closes, and *Study ▾* saves it or makes a
template for the next table. In CI: `signalviewer-cli sweep results.csv --question study.svsweep`.

**Studies: many tables, the next runs, the loop.** *Open ▾* holds *New study…*, a table, a folder and
*Open a saved study* (a table's `.svsweep` or a study file, `.svstudy.json`). *New study…* asks how to
begin:

- **I have results** – load a table of runs; the roles are guessed from its columns and fill the study's
  set-up (parameters and their ranges, scenarios, outputs), and the answer shows at once.
- **Start from nothing** – *Send runs*: only what varies (values or ranges, steps, how many values in the
  first round), the scenarios and how to run (the command for one run on this PC, a wrapper, or your farm's
  launcher). No outputs and no goal: **Send round 1** runs that grid, and its results – even one row – open
  as a regular table in Data; Columns (already filled: what varies, the scenarios, every other number an
  output), Goal and Results follow as for any table. Each next round is aimed by the results.

Every study goes through the same five steps: **1 Data · 2 Columns · 3 Goal · 4 Results · 5 Next runs**.
**Data** holds the runs: on the left *Send runs* (what varies, the scenarios, how to run; how many of the
three are filled) and the study's tables – the layers of runs: each table, the tables merged into it and
each round the loop has run (new ones marked); a click shows its data. *About this study*
explains a demo. When the study has two systems (tables) or more, **Results** has a tab *All systems
together* – the values that hold for all of them. **Next runs** is the one place for the next parameter
sets: the sets proposed from the results so far (export them to run outside the app) and *Run from the
app* – what the next round will run or what is still missing, **The goal of the loop** (the loop ranks the
sets, so it asks for a goal here, not before: the table's Goal step, or what to rank by), **Run them**, *Only
write the files* (for a launcher of your own), the loop's *Next round*, *Run until converged* and *Stop*, its
progress and how it converges. *Clear ▾ › Everything* closes the tables and the study file (the notice's Undo
opens them again).
Finished rounds come back as new tables in Data. *Study ▾* saves, undoes and closes the study, and
*Report of the study…* writes one HTML page of the whole study. One Ctrl+Z undoes the last change anywhere
in Sweeps.

The open tables are pills in the top row, beside the area names (a click shows one, its × closes it). A round
stays marked *new* until you open it. A study table opened from Data *is* that table: change its goal in
its Goal step and the study's table changes too – the systems together rank with it, and one Ctrl+Z takes
both back. A single table opened with *I have results* is saved as its own `.svsweep`.

## 14. When something goes wrong

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

## Start from an example

The welcome screen shows six examples as cards with a picture of what each opens - an ArduPilot log, *Find out
what went wrong*, a simulation against its flight, the same mission flown twice, a folder of recordings and the
smart-sweep demo; **Help → Examples** lists every example (also a drone flight, three car runs, a pump on a test
bench, a sweep's results table and *One gain set, three drones*). The Sweeps ones open in the Sweeps area (see
*One parameter set for many systems* and *The smart-sweep demo*); the others open their recordings with the view
that suits them.

## The first minute

Open a file and the empty plot offers the views that fit it – *Quick look* (every signal in a plot of its own)
and the templates that match its signals; click one, or click signals in the list. Once something is plotted the
suggestions move to the file panel's *Views for these files*. The start card says what to do next: compare
the files you opened together, look at a log's findings, or judge the run against a golden one.
*Settings → Click places the cursor* makes the first click on a plot put the cursor there (Space turns it on
and off either way). The status bar says when a plot is drawn reduced (lowest and highest per pixel) – hover
for the numbers.

## One parameter set for many systems, the next runs, the farm, the demo

*Sweeps → Open ▾ → New study…*: a study of one or several sweep tables, saved as a `.svstudy.json`
(section 13). The values ranked together, why a value fails, the next runs and *Run them*
(in Next runs) are explained in
[One parameter set for many systems](common-gains.md) and [Launcher mode](launcher.md); the welcome screen's
*Smart sweep demo* in [The smart-sweep demo](smart-sweep-demo.md).

## Closing with unsaved work

When the window closes and your plots changed since the session was last saved, Signal Viewer asks
*Save / Don't save / Cancel* (in a browser tab the browser asks in its own words). The work is kept for the
next start either way (autosave); this is about a session file. Undo back to what was saved counts as saved.
*Settings → Ask before closing with unsaved changes* turns it off.

**The command palette** (Ctrl+K): with nothing typed it lists your last 5 commands, then every command by group,
each with its shortcut.

## Where things are

The plot bar keeps what you use with the plots: layout, link the time axes, zoom, the cursors; rarer things
(zoom back, link the value axes, clear the plots) are in its ⋯ menu. The keyboard shortcuts are in Help and on
the ? key. Every command is in the command search (Ctrl+K). Help → *Tour* shows the 30-second tour again.
