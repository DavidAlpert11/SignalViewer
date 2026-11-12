# Changelog

## 1.27.0 – unreleased

<!-- lane W0 -->
- The study file (`.svstudy.json`, version 1, `docs/dev/study.schema.json`): one definition of a "one parameter
  set for many systems" study, read by the Sweeps panel, the API and the `study` command line.

<!-- lane L1 -->

<!-- lane L2 -->

<!-- lane L3 -->

<!-- lane L4 -->

<!-- lane L5 -->

<!-- lane L6 -->

<!-- lane L7 -->

<!-- lane L8 -->

## 1.26.0 – 2026-11-11

Highlights: **an HTML report is one live page** - one time bar for every plot, the map and the 3D view,
with Play and the log's marks; **the 3D view goes into reports and the replay page** - live in HTML (offline,
turn, zoom, follow), a picture in PDF, Word and PNG; **one Map with a 2D | 3D switch**, and "3D" alone now
means three signals on plain axes (XYZ).

### Added
- **The 3D view in reports, in the replay page and as its own file.** In an HTML report or a replay page the
  3D view is live: the offline map draped on the terrain, each track with a curtain to the ground and the
  flown part brighter, the models with their heading, pitch and roll; turn, zoom, *Follow* an object,
  heights ×1 / ×2 / ×5, hover for time, position, altitude and height above ground. It moves with the page's
  time like the map. In PDF, Word and PNG it is a picture. Its ⋯ menu also saves it as its own offline HTML
  page or as the picture reports use. Nothing comes from the internet (three.js is inside the file); a
  browser without 3D graphics shows the picture.
- **Every HTML report is live**: the time bar of the replay page at the bottom of the report - a click on
  any plot or the bar, or Play, moves every plot's cursor, the map and the 3D view; the log's errors,
  warnings, findings and notes are marks on it. The report keeps its layout, its statistics tables and a
  zoom per plot. PDF and Word show each plot, the map and the 3D view as an image.
- **One bar for the map in 2D and in 3D**, in the app and in the offline pages: the camera *General · On the
  object · Chase* on the object chosen beside it (the reference first), + / − / fit, *Relation*; each view's
  own extras after it. The camera stays when you switch between 2D and 3D. *Chase* in 3D sits behind the
  object looking where it goes; in 2D it is on the object, close, with its direction of travel up.
- **Closest in → go there**: in the relation box (the app and the pages) a click on *Closest in* moves the
  time to the moment the two objects are closest.
- **The offline pages**: a *Trail* (the whole track or its last 60 / 20 s), an attitude indicator for the
  object the 3D camera is on, and an address that keeps the view (`#t=…&cam=…&obj=…` - a link to the same
  moment, camera and object).
- **The 2D map's page and the 3D view's page work the same way**: one toolbar in both and the app's relation
  box in both: choose the reference
  and the compared object, swap them, fold it, or hide it with its button. The tracks look as in the app
  (a line, a navigation solution dashed, a receiver as points; a fixed width on screen in 3D); the pair has
  its rings and a dashed line with the distance.
- **The relation box in the app's 3D view**, as on the 2D map (the pair is chosen there); a third object
  stays in the 3D data box. A *Relation* button in both views' bars shows / hides it, and the box has its
  own ×.
- Python and the command line: `sv.scene_image(rec, …)`, `sv.scene_html(rec, …)`, `signalviewer-cli map
  flight.bin --3d --out view.png|view.html`.
- **Hide an object on the map**: the eye on its chip (Alt+click: only this one, again: all) - it is not
  drawn and not fitted, and keeps its place in the list, struck through; the relation box says "— hidden —".
  The offline pages' legend works the same way; pictures leave it out; a session keeps it.
- **A ground with relief anywhere**: when the network is allowed the 3D ground uses world elevation tiles
  (~30 m, kept in the tile cache), and your own SRTM `.hgt` files (`~/.signalviewer/terrain/`) work offline.
  The offline 3D page's ground reaches the horizon (fog, a sky, the sun from the north-west), has Heights
  ×10, says "flat here" when it is, says when only coarse heights are there, and names its grid in the
  footer. The PDF / Word picture shows the ground around the tracks too.
- **Export the flight** - one submenu in a map's ⋯ menu with three ways out: *Tacview (.acmi)*, **Tacview
  CSV files** (one per object, named as Tacview's CSV import wants; File → Open, then File → Merge) and
  **Google Earth (.kml)** (a track per object that plays with Google Earth's time slider when the log has
  dates). In Python: `sv.tacview_csv(rec, …)`, `sv.kml(rec, …)`.
- **Places, as in Google Earth**: the airfield, the range, the target, the ground station - named points
  (with an icon), lines and areas that are on every Map. Right-click on the Map → *Add a place here…*, type a
  position (`32.687, 35.39` or `32°41'13"N 35°23'24"E`), *Mark this spot* on an object's chip, or import
  `.kml`, `.kmz`, `.geojson` or `.csv`. The **Places** panel (the Map's ⋯ → *Places…*, or Ctrl+K "Go to a
  place…") lists *Places of this session* (saved with it and its template) and *My places* (yours, in
  every session); click one and the camera flies there; *Save this view* keeps a camera position by name.
  The mouse readout says "1.2 km from Runway 27"; the relation box can compare the reference with a place.
  Places go into the HTML pages, the pictures, the KML file and the ACMI file (as stationary waypoints).
- **Settings > Map and objects**: the icon a new object gets by its class (truth, navigation, receiver,
  other - no longer always an aircraft), the camera of a new Map, *Always flat* (the light drawing), the
  relation box and names shown or hidden, the track's width, the model size, distances and heights in
  m / km or ft / NM, coordinates as decimal degrees, degrees-minutes-seconds or MGRS, the folder of your
  elevation files, the export rate for Tacview / KML, and the Story. They apply to new things only - an open
  session or an object already made is not changed; *Reset this group* brings the defaults back.
- **The Map, worth stopping to look at**: a sky and the sun where it was over the flight (the recording's
  date when it has one, else mid-morning), soft shadows of the models when the camera is near them; a drop
  line and a dark disc under each object; its last 10 s brighter over the whole track; every camera change
  flies there; a **Cockpit** camera (looking where the object points, rolling with it); a **flight display**
  (attitude, ground speed and altitude tapes, heading) for the object the camera is on; a **mini-map** of the
  whole flight while the camera is close (a click flies there); and **the error, drawn** - when the pair
  in the relation box is one vehicle (truth and a navigation solution) a surface between their tracks
  coloured by the distance shows where the solution left the truth and by how much (the flat drawing
  colours the compared track). The same in the offline 3D page. On a computer without graphics
  acceleration (the light mode) the effects stay off.
- **Story mode - the flight tells itself**: *▶ Story* beside Play in a live HTML page (and on the Map's bar
  in the app) plays the flight as a short guided film: the time runs, slows at each moment that matters,
  the camera flies to the object, and a card says what happened in one sentence with its number - "nav is
  6.1 m north of truth", "Closest: 41 m", the log's errors and warnings, your notes, takeoff and landing,
  the highest and fastest points, the steepest bank, passing a place. The moments are diamonds on the
  timeline; ◀ ▶ step through them, Esc ends it, a click on the card stays there; a link with `#story=1`
  starts it. PDF and Word reports get "The flight in N moments": the table and the 3D picture at the first
  four. Settings > Map and objects: Story on / off and about 90 s · 45 s · 3 min.

### Changed
- **The Map is 3D**: no more 2D | 3D switch - the Map is the earth with its terrain, and "2D" is its camera
  **From above** (straight down, north up, the whole flight framed; *Track up* beside it). The mouse's
  position (latitude, longitude, ground height, distance / bearing from the reference) is shown in a corner.
  Maps saved before open From above; reports draw a From above map as the clear flat picture. Where the
  computer cannot draw 3D, the Map is drawn flat and says so.


### Fixed
- **The command line on Windows writes UTF-8**: `signalviewer-cli … --json` printed nothing (and failed) when
  a name held a character outside the Windows code page (`Δnorth`, Hebrew); its output is now UTF-8 on any
  console or pipe.
- **Tacview shows the aircraft, not triangles, and the file opens cleanly**: each object's `Name` is now a
  model Tacview has a 3D shape for (C172, MQ-9, DJI300, AIM-9M, Zodiac, Pickup by its kind) and its own
  name is the call sign; an object with no attitude is written without one (it no longer flies sideways
  with a frozen nose); a missing altitude or angle keeps the last value (no empty fields); an object that
  is gone for more than 2 s is removed and comes back as a new object; a long recording is written at a
  lower rate so Tacview stays responsive. Every file is checked against the ACMI 2.2 rules by the tests.
- **An object with no position is no object**: latitude and longitude 0, 0 (ArduPilot's EAHR without an
  external AHRS, a GPS before its fix) are a gap, not a point at 0° N 0° E. *Add all* leaves such an object
  out and says so; it is not drawn, not fitted and not exported.
- **A log with one faulty message type loads**: when the firmware writes one message type with a length
  other than its format says, that type is left out (the message says which, with both lengths) and
  everything else is read; before, a long log was refused as too damaged. The same when a message's
  format lists more (or fewer) column names than it has values - a Write() call in the firmware that got
  three more labels than values: which name is which value cannot be known, so that message alone is left
  out and the message says so. A message type with no format at all is skipped the same way. A log that is mostly damage is
  still refused, and a damaged one says how much of it was readable.
- `docs/validation.md` says the current version again (the release check failed on it).
- A 3D view was left out of reports and replay pages without a word; it is in now. A plot that still
  cannot go into a report (a video, occurrences) is listed greyed in the Report panel with the reason, and
  a replay page says what it left out.

## 1.25.0 – 2026-11-11

Highlights: **replay pages** - the tab as one HTML page to send, that opens in any browser on the moment
you were looking at, its plots and map moving together, with Play; **a timeline that maps the
recording** (the active line along it, what the plots show as a window to drag); **Δ between two cursors
in the legend**; **objects whose position is in metres** - NED, ENU or ECEF - found and added like
latitude / longitude ones, so every ArduPilot EKF lane is on the map beside POS; **the rings explained**
and the pair chosen in one place; **Compare objects…** - position, velocity and attitude of every object
against a reference, values and errors side by side with their statistics, and one click to the moment
of the largest error; **Compare with similar…** for signals whose names differ in one part; **plots move
to other tabs and into other plots**; **a map saves as a PNG or as one offline HTML file** and goes into
reports; **the whole process from Python, the command line and REST** with the same numbers; and a
human-factors pass - a flat line is offered the right axis or its own plot, one plot at a time (M), a
plain file opens with a suggestion instead of an empty plot.

### Added
- **Send it as a replay** (Report panel, first; Ctrl+K *Send this view as a replay page*): the tab on
  screen saved as one HTML page that opens in any browser with no install and no network, on the moment
  you were looking at (the cursor, else the middle of what is shown). One time for the whole page: a click
  on any plot, the timeline under the plots or **Play** (Space; ×0.5 - ×30) moves the cursor in every plot
  and the markers on every map, and the plots follow while playing; a drag zooms every time plot. The log's
  errors and warnings, the health check's findings and your notes are marks on its timeline - a click
  goes there. The address keeps the moment (`#t=…`), so a link can point at a time. The page says where it
  came from (*Made with Signal Viewer*, with the link to get it). After saving, *Open it* shows it in your
  browser. It is the HTML report in one more form - the same numbers, the same offline map.
- **The timeline maps the recording**: the active plot's first line is drawn faintly along it - where the
  action is, at a glance - and what the plots show is a window on it: drag it to move along the recording,
  pull an edge to zoom, double-click it to show everything; one Backspace undoes the move.
- **Δ in the legend**: with two cursors each line's chip shows how much it changed between them
  (cursor 2 − cursor 1, in its unit), beside its value - read at a glance, as on a scope.
- **Objects whose position is in metres - NED, ENU or ECEF - are found and added like latitude /
  longitude ones.** Every ArduPilot EKF lane (`XKF1[n]`, older logs `NKF1[n]`) is offered after POS with
  its own attitude and velocity and placed on the map through the EKF origin (`ORGN`); PX4
  (`vehicle_local_position`, through its own `ref_lat / ref_lon / ref_alt`) and MAVLink
  (`LOCAL_POSITION_NED`, through `GPS_GLOBAL_ORIGIN`) local positions too. Generic names work in any
  form: `tgt.ned.x`, `nav.x_ned`, `ship.ecefX`, `boat.pos.north / east / up` (ENU), `rov.pos.n / e / d`,
  with an `origin.lat / lon / alt` (or `ref_*`) group as the origin. *Why?* says where the origin came
  from; the found list shows each object's frame and origin ("NED · origin ORGN[0]").
- A local position with no origin in the file: *Advanced…* fills in the file's GPS (its first fix
  becomes the origin) and says so.
- **The rings on the map are explained.** Hovering an object says what its ring means (solid: the
  reference, dashed: compared with it); the relation box's header shows the two rings and chooses the
  pair - *Reference* ⇄ *Compared with*, with a swap button - and the 3D view uses the same header
  instead of its own selects. The object chips carry the same ring icons; Ctrl+K can set the reference.

- **Compare objects…** - one dialog for comparing the objects of a map or 3D view against a
  reference: position, velocity and attitude; their values, their errors or both; in NED, ENU, ECEF,
  LLA or along / across track. *Make* adds one tab per quantity (values left, errors right, plus the
  horizontal / vertical / 3D or speed error) - one Undo - and a statistics table of the errors (RMS,
  mean, max |error| and when, 95th percentile) to copy or save as CSV. Open it from the relation box's
  *Compare…*, the offer after adding objects, or Ctrl+K "Compare objects…".

- **Compare with similar…** - in a signal's menu and a group's menu in the signal list (and Ctrl+K):
  the signals of the same file whose names differ in one part only (`nav1` / `nav2`, `XKF1[0]` /
  `XKF1[1]`, `truth` / `nav`), one family per quantity (a group gives roll, pitch and yaw at once), in
  one tab: their values beside each one minus the reference, with the errors' statistics.

- **Move a plot to another tab** - drag its ⠿ handle onto a tab (Ctrl: a copy), or ⋯ → *Move to…* →
  a tab or *New tab*; the plot keeps everything (axes, cursors, a map's objects and pair). ⋯ → *Add its
  lines to…* (or Shift+drop onto another plot) puts its lines into a plot of the same kind. One Undo each.

- **Maps leave the app.** A map's ⋯ menu saves its picture (this view, or every track fitted) with the
  offline map, the tracks, the objects at the cursor, a legend, a scale bar and a north arrow - and
  *Save as HTML* makes a page that opens anywhere with no network: pan, zoom, a time slider that moves
  the objects, light / dark. Online imagery is used only from tiles already seen, always credited.
- **Reports include maps** - as a picture in PDF / Word, as the interactive offline map in HTML.

- **The whole process from a script, a shell or another program** - with the app's rules and numbers:
  Python (`rec.objects()`, `rec.object("XKF1[0]")`, `sv.compare_objects(...)` with `values()` / `errors()` /
  `stats()` / `to_csv` / `to_mat`, `sv.similar`, `sv.compare_signals`, `sv.map_image`, `sv.map_html`,
  `sv.report`), the command line (`objects`, `compare-objects` with `--tolerance` and JUnit for CI,
  `compare-similar`, `map`) and local REST (`/api/objects/detect`, `/compare`, `/similar`). Walk-through:
  [API](docs/api.md).
- **A line that looks flat beside larger ones is offered a way out - also in files with no units.**
  Adding a current of 12 A to a plot of 3000 rpm says so and offers *To the right axis* or *To its own
  plot* (nothing moves by itself; one Undo). Until now the offer was made only when the units differed.
- **A plain file no longer opens on an empty plot with no word on what to do.** When no template fits
  the file, the start card offers *Quick look* (every signal in a plot of its own); it leaves by itself
  with the first signal you plot.
- **One plot at a time** (`M`, or the layout button): the active plot fills the tab, `1 - 9` flip through
  the others, `Esc` returns to all of them. The layout is not changed. For small screens and for showing
  one plot to a room.

### Changed
- Differences of angles are wrapped: 359° − 1° is −2°, not 358° - in Compare with similar…, *Errors
  between two lines* and the error-segments table (degrees or radians, from the unit or the values).
- The relation box's four buttons are now one *Compare…*; *Plot the relation*, *Error signals*,
  *Differences* and *Overlay* are one-click presets at the top of the dialog, with the same results.
- Making the same relation or comparison again reuses the signals already made instead of adding copies.
- *Compare objects…*: in the tabs it makes, every line is named by its object (`XKF1[0]`, not
  `XKF1_0_vs_POS.dned.north`) and has the object's colour - the one on the map - in every plot (an
  object used to be one colour among the values and another among the errors). The statistics table
  says its units, names an object once per block and lines its numbers up; the dialog's contents no
  longer touch its edges, and the one-click presets look like buttons.
- The start card's suggested view leaves once you have two tabs of your own (it used to stay floating
  over a comparison's tabs).
- *Compare objects…*: the **time of the largest error** in the statistics is a way there - a click puts
  the cursor at that moment in every plot and on the map.
- A plot's ⋯ button is always in the head's far corner (it used to drop to a row of its own under a full
  row of chips - 30 px of a small plot's height, and a different place from plot to plot).
- The lines select beside *Compare…* in the relation box says what it chooses ("Lines: the pair"); it read
  as "Compare… the pair".
- Command palette: a command with no icon keeps the icons' column, so the labels line up.
- The overview strip explains its clicks only when it has something to click (a plain file with no flags
  and no state rows no longer opens under a line of instructions).
- Help ▸ Keyboard shortcuts: the mouse column is readable (long gestures wrap; the dialog is wider).
- A message with two buttons keeps its text readable (the buttons go under it when they do not fit).
- "Primary / secondary" is now "Reference / Compared with" (Hebrew: בסיס / מושווה) everywhere - the
  box, the chips, their menu, Help.

### Fixed
- A map of objects was left out of reports: it is now drawn.
- A request for more plots than a tab holds (or more signals than a plot shows) no longer drops the
  rest silently: it goes on in another tab, and a message says what was left out.
- An ECEF (or any converted) object is no longer offered again by the suggestion bar after it was added,
  and *Add all* can no longer add it twice.
- Origins and home points (`ORGN`, `HOME_POSITION`, `vehicle_local_position.ref_*`, `origin.*`) are no
  longer offered as objects of their own.
- A position in metres written in cm / mm / km is no longer added as if it were metres: *Why?* asks to
  convert it first.

## 1.24.0 – 2026-11-10

Highlights: **every object of a recording on the map and in 3D at once** - truth, each navigation
solution and each receiver found by their names, with *Why?* for every guess, each drawn as what it is
and given an attitude from its motion when it has none; **primary and secondary objects** with range,
bearing, closure and the angle off at the cursor, and their errors or differences plotted in NED, ENU,
ECEF or along the track in one click; **a map and 3D view that move smoothly** (drag, glide, follow,
track up, Chase and Look at); **export for Tacview** (.acmi); plots that change places, defaults for
new lines with dotted and dash-dot styles, and a whole group of lines styled at once.

### Added
- **Every map object in a recording, found and added at once.** *Add object* lists the objects found
  by their names - every prefix with a latitude and a longitude (`phys.*`, `nav.*`, `gps.*`, `ins2_*`,
  `sim.nav.pos.*`), classified as truth, navigation or receiver - with **Add all** (one Undo), **Add
  selected**, and **Why?**: which signals, by which rule, what is missing, what almost matched. Each
  object takes its signals from its own prefix only (no more GPS position with the navigation's
  attitude). Several navigation solutions and receivers are all proposed. NED / ENU / ECEF positions
  are found too. *Position on the map & 3D* adds every object of the file and says which, with *Why?*.
  A note in the dialog, the guide and the README gives the naming convention. Flight logs and CSVs with
  their names keep their pairing (POS with ATT); *Advanced…* opens the full form as before.
- **Objects found as soon as a file opens.** A slim line in the file panel says *"3 objects found:
  phys, nav, gps"* with **Add all** (onto the tab's map and 3D view, or a new map), *Choose…*, *Why?*
  and × to hide it for that file. Nothing is added without a click.
- **Each kind of object looks like what it is.** Truth is a solid line, a navigation solution dashed, a
  receiver's fixes are points (*Track* in the object's form changes it).
- **An attitude for an object that has none.** A GPS receiver (position only) is drawn by its motion -
  heading along the course over ground, pitch from the climb, roll unknown, the heading held while it
  hovers or stands (below 1 m/s, editable) - or with the angles borrowed from another object on the
  same vehicle (*Attitude* in its row or its form). Such an icon is drawn as an outline, its chip shows
  ≈ and says where the angles come from.

- **A map that is easy to move (Tacview-like).** Dragging follows the pointer and glides on after a
  quick drag; the wheel, **+ / −** and the keys zoom smoothly around the pointer; **Fit everything** and
  **Follow ▾** are buttons in the corner. Dragging while following moves the map around the object
  (*Back to following* puts it in the middle again). When the map has the focus: arrows move it, + / −
  zoom, F follows, 0 fits everything (Shift+←/→ still step the cursor). A one-line hint shows until the
  map is first moved. *Camera following an object* in Settings: smooth (default) or exact. **Track up**
  (the N button in the corner) turns the map so the followed object's heading points up.
- **3D camera: Chase and Look at.** *Chase* stays behind and above the object, turning with it; *Look at*
  looks from it towards the second object. Changing mode or object flies there instead of jumping, and a
  short hint says what the mouse does in each mode.

- **Primary and secondary objects, and what is between them (Tacview-like).** On a map with several
  objects one is the *primary* (a ring) and one the *secondary* (a dashed ring) - by default the truth
  and the first navigation solution (in a flight log the EKF and a GPS). Click an object (Shift+click:
  the secondary), use the chip's menu, or Q / Shift+Q and X on the map. A box at the cursor shows the
  range, horizontal distance, Δalt, bearing, relative bearing, closure rate, time to closest approach,
  heading difference and aspect; a dashed line with the range joins them (or the primary to every
  object, or none). From the box: *Plot over time* (range, Δalt, bearing, closure in a new tab), *Error
  signals* (horizontal / vertical / 3D, heading, roll, pitch errors against the primary - `nav_vs_phys.err.*`),
  and *Differences* / *Overlay* in NED, ENU, ECEF, LLA or the track frame - differences in NED / ENU are
  in the primary's local frame at each sample, overlays share one origin. All computed in the backend.
  When both objects have velocities (`<object>.vel.north / east / down`) their difference is plotted
  too. Right after objects are added, a line offers *Compare the objects with <primary> · frame · Make
  plots*. In 3D the primary and secondary have rings, a click picks them and the box adds closure and aspect.

- **Plots can change places.** Drag a plot by the ⠿ beside its title onto another plot, use *Move to…*
  in its menu, or Ctrl+Shift+arrows: the two swap (one Undo); the cells keep their sizes.

- **Defaults for new lines, and more line styles.** *Settings → New lines*: the width and style
  (solid, dashed, dotted, dash-dot) every new line gets; *Apply to all open plots* gives them to the
  lines already drawn (one Undo). The Inspector offers dotted and dash-dot too, and reports and saved
  pictures draw the styles as the plots do.
- **Export for Tacview.** *Export for Tacview (.acmi)…* in a map's or a 3D view's menu saves its
  objects as a Tacview ACMI 2.2 file: position, altitude above sea level and attitude as the 3D view
  draws them, the kind, name and colour of each object.
- **Style a whole group of lines at once.** *Style the lines…* in a group's menu in the signal list
  (a file's group or your own) gives every line of its signals one colour - or a different one each
  from the palette - a width and a line style, in this plot, this tab or every tab (the count of lines
  is shown). With several lines picked in the legend (Ctrl+click), the Inspector sets their colour and
  line style too, or opens the same dialog. One Undo takes it back.

### Performance
- **Smoother playback and map.** While playing, only what moves is drawn again: the panels, the file
  list and the plots' heads no longer re-render every frame. Dragging and zooming the map move the map
  already drawn and draw it properly once movement pauses: on the copter log a drag went from 471
  dropped frames to none, a wheel zoom from 315 to about 70 (headless, no GPU).

### Fixed
- *Choose…* on the "objects found" line opened nothing when the tab had no map yet.
- **Signal names with dots nest again, at any depth.** `phys.att.roll`, `nav.vel.north` and a MATLAB
  struct's `sim.nav.pos.x` are listed as a tree (phys › att › roll) whatever the number of signals -
  before, a file needed 40 signals to be grouped at all, and only two levels were shown. A chain of
  single levels is one row (`truth.pos`), a group of one signal is not made, and inside a group only the
  rest of the name shows (the full name stays in the tooltip and in search). A unit in brackets
  (`GPS.Lat [deg]`) does not split a name, nor does a number (`bus_1.5V`). Flight logs list as before.

## 1.23.0 – 2026-11-09

Highlights: **judge a run, from opening it to the report** - a golden run is remembered with its
tolerances, a new recording with its signals is offered to be judged against it, Compare opens on a
verdict per file, the worst failure and a report that starts with the verdict; **tolerances per signal**
in the same file `signalviewer-cli compare` reads, so the app and CI give the same verdict. **The numbers
are right in the hard cases**: every sample is judged, a flight mode is the mode in force, a missing
value is never dropped or made 0, filters follow time across gaps. **Results say what they rest on**
(trust badges, a data-quality summary of every file as it opens), one list of events with ] / [, less
on screen, plots that read better in both themes - and a faster, exact plot data path.

### Added
- **Judge a run, from opening it to the report.** Mark a file in Compare as a **★ Golden run** (its tolerances are remembered with it); a recording opened later that has its signals is offered *Judge it against <golden run>* on the start card, and one click opens the golden run beside it with its tolerances and Compare. Compare now starts with a **verdict** per file - ✓ all within, or ✗ how many signals are outside - with *Show the worst failure* (the signal with the largest share outside and its difference over time) and *Report…*: a tab of the failing signals and a report whose first section is the verdict table (each signal's tolerance and each file's pass / fail, share outside, largest difference). Without a golden run, Compare starts on a file named as the reference (golden, reference, baseline…) instead of simply the first.
- **Tolerances per signal in Compare, in the command line's file.** A tolerance was one for every signal in the app, while `signalviewer-cli compare --tolerances` read one per signal. Now the selected signal has *This signal's tolerance* under its comparison (± / % / time / the share allowed outside - empty fields show every signal's, greyed) and *Leave out of pass / fail*; signals with their own are marked ± in the list. *Save tolerances…* writes the file the command line reads and *Open tolerances…* reads one, and both judge a signal by the same rule (the share allowed outside included), so the app and CI give the same verdict.
- **What to know about a file's data, when it opens.** Each file is checked in the background, signal by signal: values missing, gaps (time with no data - the same rule as spectra, statistics and filters), repeated or backwards time stamps, and the logging rate changing (100 Hz, then 10 Hz). A file with something to say gets one note (*messy.csv: 2 of 3 signals need a look - missing values (1), gaps (2)… · Show*), a **!** badge beside its name, and its signals a mark with the details on hover; **Data quality…** (the file's right-click, or the badge) lists every signal and what was found - click one to plot it. A state or event signal (a mode, a message) is logged when it changes, so its pauses and repeated times are not counted. A clean file says nothing.
- **One list of what happened, and ] / [ to step through it.** The Log panel's *Events* now also lists the health check's findings, the named conditions' stretches and where plotted signals are outside their limits, with the log's modes, events, errors and messages - one list in time order, each kind a chip to show or hide; a click goes there (a stretch is shown whole). **]** and **[** move the cursor to the next / previous event of any kind (messages left out) from the cursor, in any file; the status bar says which (*◆ 3/24 · Mode · ALT_HOLD*). With a condition in focus, ] / [ still step through its stretches. Also in the command palette (*Next event*, *Previous event*).
- **Results say what they rest on.** A derived signal whose values were read between another signal's samples (a sum of a 100 Hz and a 33 Hz signal), whose filter ran on each stretch between gaps or on an even grid, or whose missing values were skipped or bridged, has a small badge - **≈** on its legend chip, a word in the list of derived signals (*interpolated*, *filtered by stretch*, *skipped missing*…) - and its tooltip says exactly what was done. Amber when missing data was handled, quiet for how values were read. A map or 3D object whose angle unit is *Automatic* has **≈** on its chip with the guess and why (*degrees - one of the angles goes beyond 2π*). The status bar says what leaves the PC: **● Online map** while an online map layer is on screen, **Network off** when *Never use the network* is on (nothing is said in the default, when nothing is sent).
- **The app's guesses are shown and can be corrected.** Whether a numeric signal is a state (held between its samples - a flight mode number, a gear) or a value (interpolated) was decided by the app alone; a counter of a few whole numbers was held, a mode logged as a float was interpolated. Now the signal list's right-click has *Read between samples as ▸* with what was detected and the choice - by signal name, in every open file, kept in the session and undone with Ctrl+Z; cursor values, formulas, conditions and operations follow it. The map / 3D object dialog's *Automatic* angle unit now says what it takes the angles to be and why (*automatic - degrees (one of the angles goes beyond 2π)*).
- **One design system** (26.U1): every text size, corner, spacing and colour of the interface comes from one set of tokens - a type scale of nine steps instead of about thirty sizes, five corner radii, a spacing scale, and semantic colours. Pass / fail greens and reds now follow the theme (they were fixed colours: green text on white was hard to read), and a few labels that ignored *Settings ▸ Text size* follow it now.
- **Plots that read better** (26.U2). New lines get a colour-blind-safe palette (Okabe & Ito's eight first), and every line is drawn at a contrast of at least 3:1 against the plot in either theme - a yellow on the light plot or a dark blue on the dark one is lifted just enough (the colour saved in a session is not changed). The hover points are rings in each line's colour, the crosshair a quiet dashed line in the theme's axis colour. Compare's difference chart is drawn at its real width (its numbers were stretched), on the plot's background with a frame; the tolerance band has its edges drawn, stretches outside it are a faint shade with a solid red mark along the bottom (the lines stay readable), and hovering shows each run's difference at that moment. One palette everywhere (What changed, conditions' plots and the fallbacks used their own).
- **Benchmarks of this version's changes** (P5): `python tools/benchmark.py --synthetic` measures, on generated data, a plot request with and without a time offset, a zoom step of 30 signals, a pan burst, the memory of a large log with changed signals and a live append on a wide CSV, each against a target (*Performance* page); `--json` for CI. `tools/benchmark.py FILE` works again (its requests were refused by the localhost-only check since 1.19).
- **Six new validation cases** (`signalviewer-cli validate`, the *Validation* page; 29 in all): a 5 ms violation in 2 million samples fails Compare (V24), a violation between two samples of a 10 Hz golden run fails (V25), a condition on a mode starts when the mode was entered (V26), a formula of a mode makes only values the mode has (V27), a sum and a norm with a missing input are missing (V28); and a plot request on a run with a time offset is not more than 2 times slower than without (V29).

### Changed
- **The map is offline unless you choose otherwise** (O1). The map's *Automatic* layer is the offline map the app draws from its own data again (1.22.0 had made it OpenStreetMap, which downloaded the tiles of the flight's area). The online layers are grouped in the layer menu as *Online – downloads map tiles*, and while one is used the plot shows an amber **Online map** sign. New: **Settings ▸ Never use the network** - the online layers are turned off and the app downloads nothing; `SV_OFFLINE=1` in the environment turns it on for a whole installation (shown locked in Settings). A session that chose an online layer opens with it, unless the network is off. README, SECURITY and the docs now say exactly what an online layer sends.
- **Less on screen** - only what applies. With something plotted, the file panel's template list is one line (click to unfold; the library and *Save as template* are also in *Templates ▾*); the mode strip's *+* and *hide* show when the pointer is over it; a map whose object already draws the track has no *Lon / Lat* pickers or alignment (*⋯ ▸ Lat / lon track* brings them back); the 3D view's *Save image* and *Remove* moved into its **⋯** menu. Visible controls in the ArduPilot example: 58 -> 54 on the Attitude tab, 80 -> 71 on the Flight tab (map + 3D).

### Fixed
- **Compare judges every sample, in both directions** (C1). Pass / fail, the share within tolerance and the largest difference were computed on the baseline's samples thinned to 200,000 (the command line) or 20,000-50,000 (the Compare list), and the run was only looked at the baseline's times - so a 5 ms excursion in a long recording, or a violation between two samples of a 10 Hz golden run against a 1 kHz run, could pass. Now they are judged on all the samples of both runs inside the overlap; only the drawn difference curve is thinned (its peaks kept). The command line and the app give the same numbers. For runs at different rates the share within tolerance is now counted over both runs' samples.
- **A flight mode (or any state signal) in a formula or a condition is the mode in force** (C2). A formula with a state signal interpolated between two modes - values the signal never had (between mode 2 and mode 5 there is no 3.7) - and a condition such as `{MODE.Mode} == 5` started halfway to the previous change (40.45 s instead of 46.41 s in the ArduPilot example). Now a state signal - text values, or a few whole numbers - is read as its last value at or before each moment, as the plots and the cursor already showed it; also in the two-signal and several-signal operations. Sessions saved before this version keep their numbers: their derived signals are restored with the old alignment (`"hold": false`); a derived signal made now is saved with `"hold": true`, so a session saved now opens with the mode held.
- **A missing value is never silently dropped or turned into 0** (C3). A sum or norm of several signals ignored a missing input (1 + missing + 3 gave 4), an integral counted a gap as 0 and went on, `!=` in a formula was true on a missing value, and an infinite result (1/0) quietly became a gap. Now a missing input makes that sample missing, an integral is unknown from a gap on, a comparison with a missing value is missing, and the number of infinite values is reported with the signal. In **Create signals**, a sum, mean, min, max, norm or integral has a *Missing values* choice: keep missing (the default), or use the signals that have a value / bridge the gap with a straight line (`"nan": "skip"`); the new signal is then marked in the list of derived signals (*skipped missing*, *gaps bridged* - hover for how many and where). **Sessions saved before this version keep their numbers**: their derived signals are restored with the old rules (`"nan": "legacy"`); changes on signals (*Edit* formulas) keep the old rules too.
- **A damaged flight log no longer invents signals, and a damaged PX4 log opens** (O2). A damaged block in an ArduPilot .bin could be read as a message of a real type - in the example log it added `IMU[149].*` (six signals that are not in the log); now the message just before a damaged block and an instance only damage made are left out, and the note after opening says so. A PX4 .ulg with a damaged parameter failed entirely ("could not convert string to float"); now it opens with that parameter left out, and samples whose time stamp only damage can make (a topic logged without time gaining one) are left out too, counted. A reader failing in a way nobody foresaw says what happened and what to do (another copy; *Help ▸ Copy error details*) instead of "Unexpected error".
- **A save that fails never leaves a broken file** (O3). Sessions, templates, the settings, reports (HTML / PDF / Word), plot images, exported CSV and the files Sweeps saves were written in place: a crash, a full disk or a power loss in the middle left a cut file where the good one was - and an HTML report was emptied before it was built, so a report that failed (a signal closed meanwhile) left an empty file. Now each is written to a temporary file next to it and replaces the old one only when complete.
- **Your own file reader cannot take the app down** (26.A2). A reader in the readers folder ran inside the app: one that crashed Python closed the whole app, and one that never ended held the file's opening forever. Now it runs in a process of its own, like the Python operations: a crash or a reading longer than 10 minutes (`SV_READER_TIMEOUT`) is stopped with a message naming the reader's file, and the next file opens as ever. (The Python API and the command line still run readers in your own script.)
- **Filters and smoothing follow time, not the sample count** (26.A3). A low- or high-pass filtered across a pause in the log as if the samples on both sides were neighbours, and after a change of logging rate (100 Hz, then 10 Hz) it cut a slow tone in the slower part; a smooth or RMS window was a number of samples, so it meant something else on every signal. Now a filter runs on each stretch between gaps, an uneven stretch on an even grid of its usual step (as the spectra do), and smooth / RMS windows are in seconds (*Window (s)*, about 10 samples of the chosen signal to start with) - also in *Change this signal* (`smooth_s(x, seconds)` in formulas). Derived signals in sessions saved before this version keep their numbers (`"sampling": "samples"`); a change on a signal saved before keeps its old filter too.
- **Large values are drawn exactly** (P3). Values were sent to the plots as 32-bit floats: a Unix time or a counter near 1.7e9 was drawn in steps of 128 (a +-3 wave on it disappeared), and a latitude on the map was off by up to 0.2 m (an RTK track looked jagged; the map's objects were rounded the same way). Now each signal is sent relative to the middle of its values, so only its own variation is rounded (~1e-7 of it).

### Performance
- **A run moved in time (a time offset) is as fast as one that is not** (P1). Every plot redraw, cursor value, step to the next sample, statistics and spectrogram of a shifted run copied its whole time vector: with 20 million samples about 50 ms and 160 MB per signal per request (statistics 460 ms - their cache never hit). Now the window is shifted instead: about 3 ms and no copy, the same as without an offset.
- **One memory budget for results kept to be fast** (P2). Changed signals were kept by count (32 of them - at 20 million samples 5 GB), derived signals without any limit, spectra by their own 256 MB; now changed and derived signals, spectra, plot summaries and statistics share one budget in bytes (1 GB, `SV_MEMCACHE_MB`), the least recently used going first (12 changed signals of 20 million samples: 1.8 GB kept before, 0.9 GB now). Two requests at once could make a changed signal look missing for a moment; no longer. *Settings ▸ Storage* shows the memory used (*120 MB of 1 GB*, by kind on hover) and clears it.
- **Several files open at once** (P4). Files chosen together were read one after the other; now they are read side by side on the computer's cores, within a memory budget (half the computer's memory, at most 8 GB - `SV_OPEN_BUDGET_MB`; a file bigger than that is read alone). They are listed in the order chosen, and two files with the same name in different folders are named by their folders. Four 55 MB ArduPilot logs: 2.1 -> 1.4 s on two cores.
- **Faster, exact plot data** (P3). A zoom or pan made a request per step and every one was waited for; now the older ones are cancelled. The points come as raw binary arrays (a quarter smaller, decoded three times faster than before), and a time plot of many signals is put together twice as fast (30 signals: 160 -> 77 ms per redraw).

### Tests and CI
- The frontend's logic has unit tests (`cd frontend && npm test`, Vitest): undo / redo, opening old sessions, pairing, colours, the verdict, trust badges. The end-to-end tests wait for what they check instead of fixed pauses (78 pauses -> 30, each left for a reason). CI runs the unit tests, 18 end-to-end files instead of 3, and the benchmarks against their targets (`tools/benchmark.py --synthetic --check 3`).

## 1.22.0 – 2026-11-07

Highlights: **a flight log opens on what matters, and nothing covers it** - a template opens its
default tabs (the ArduPilot review: Attitude and Flight; the rest a click away), the flight mode is
one band over all the plots of a tab **with the cursor and the pointer on it**, the health check's
findings wait beside the timeline instead of over a plot, and a setpoint is dashed beside its
measured value. **Compare shows where and why a signal fails** (the difference over time with the
tolerance band, pass / fail per signal, as the Simulink Data Inspector). The pointer over a plot
moves a ghost on the map and in 3D. **Fleet is a work area** beside Recordings and Sweeps, and the
screen is calmer (107 -> 85 buttons in the ArduPilot example). A new name line: *Signal Viewer –
offline flight log & test data analysis*. Sessions and templates open as before.

### Added
- **Compare shows where and why a signal fails** (as the Simulink Data Inspector): with a tolerance every signal in the list has ✓ or ✗; picking one shows, under its numbers, each run's difference from the baseline over time with the tolerance band shaded and the stretches outside it in red (stretches a hair apart are one), listed below - a click on one puts the cursors on it and zooms there; a click on the chart moves the cursor.
- **Setpoint against measured value at a glance**: a setpoint beside its measured value in one plot - ArduPilot's DesRoll / Roll and RATE.RDes / RATE.R, PX4's roll_sp / roll and `<topic>_setpoint.x` / `<topic>.x` - is drawn dashed and a little faded by itself, and its legend swatch is dashed. Inspector ▸ *Line*: Auto / Solid / Dashed; a choice by hand wins (saved with the session).
- **The pointer over a time plot shows on the map and in 3D**: a faint copy of each object (the map) or a faint point (3D) where it was at the moment under the pointer - also while the cursors are on; it goes when the pointer leaves the plot and never moves the cursor or adds an Undo step.
- **A template opens its default tabs, the rest a click away**: a template can name the tabs it opens by default (*Opened by default* in the template editor; saved as the optional `defaultTabs`). Right after a file loads (and for the examples) only those open, with no question - the built-in *ArduPilot · Full review* and *MAVLink · Full review* open **Attitude** and **Flight** - and the other tabs wait in the views menu **▾** beside the tab bar's + (their number on it): open one, *Open all*, or *Don't offer these*; Undo puts an opened tab back on offer. A template chip with several tabs asks which tabs (All / None, the default ones checked); *Settings ▸ Opening a template ▸ Default tabs* skips the question. The library pre-checks the default tabs and has All / None. Templates and sessions without `defaultTabs` open every tab, as before.

### Changed
- **Navigation**: the work areas are a switch in the top row - **Recordings · Sweeps · Fleet** - and **Fleet is an area** of its own (it was a panel of the rail): the folders, search and trend beside the flights, the whole width; opening a flight goes to Recordings with its Log. Beside the tabs, **+** makes a tab and **▾** is the one menu for views: a new tab, a template or collection, and the tabs a template left out (their number on it). The rail keeps its tools in place - Log is greyed while no flight log is open. *Templates ▾* keeps saving a template and new collections.
- **The flight mode once per tab, with the cursor on it**: a tab whose time plots share the time axis no longer draws its shared lanes (the flight mode on the ArduPilot views) at the bottom of every plot - the plots get the height back. The mode is shown once: in the overview strip above the plots (its default row), or - when the strip does not show it - in a band right above the plots, lined up and zoomed with them. Cursors 1 / 2 and the pointer over a plot are lines on that row, with the mode under each named (*1 · AUTO*). A plot's ⋯ menu shows the lanes in that plot again (*State lanes in this plot too*). Tabs with one plot, several columns or unlinked X keep their lanes in each plot, as before.
- **Health findings no longer cover the plots**: once a flight log's view is open, the start card's findings fold into **N findings** beside the timeline (click: the list as before, with *Plot* and *All findings, events and parameters*; ×: put them away - the Log panel keeps them all), and every finding is a ◆ mark on the timeline: a click plots its signals in a new tab (findings close together are one mark with a list).
- **Less on the screen** (the ArduPilot example: 107 visible buttons -> 85, of which 59 controls - the rest are its data: signal rows, flight modes, flags, event marks): a flight log's signal groups start closed except those plotted (more than 40 signals); the template suggestions fold away once something is plotted (*▸ Templates (3)*); the plot type shows on the plot in use (or a non-time plot); the stage bar's two icon-only buttons (zoom back, clear the plots) are one ⋯ menu; the overview strip's how-to line shows until the strip is first used (then as its tooltip); its automatic flags are rings, named *Auto flags* and "Automatic flag (found in the data)" - the log's own events stay the ▼ marks on the plots. Words: "1 file" (not "1 files"), "2 tabs, 1 plot opened", and "3,840 points drawn for 12,300 samples" (with why) instead of "Showing 3,840 of 12,300 points".
- README: a new first picture (an ArduPilot flight on the map by flight mode, in 3D, Roll desired against actual and the vibration at the moment the health check found), then the map / 3D, health check and compare clips; the social preview is cut from it.
- The name line in the README, the docs site and PyPI: *Signal Viewer – offline flight log & test data analysis*; the site's first picture is the new one.
- The map's *automatic* layer is OpenStreetMap in the dark theme too (it was the dark grey map); the dark one stays in the list.
- The README's pictures and clips are in the dark theme.

### For developers
- `frontend/src/App.tsx` 632 -> 434 lines: the welcome screen, the tool rail, the plot grid and the keyboard shortcuts in their own files.
- The texts (`frontend/src/i18n.ts`, 3,610 lines) are split by area into `frontend/src/i18n/`: eleven files, each with English and Hebrew, merged by `i18n/index.ts`; imports are unchanged.
- `backend/app/store.py` split (1,495 -> 850 lines; no change to routes, API, sessions or behaviour): the Investigate computations are pure functions over a signal getter in `svcore/investigate.py` (unit-tested without a Store), live polling is `app/livewatch.py` (`LiveWatcher`), the file checks `app/filecheck.py`, the changes on signals `svcore/transforms.py`; `app.store` still exports the names it did.

## 1.21.0 – 2026-11-05

Highlights: tools from ArduPilot's own web tools, inside the app and offline - **Filter review**
(the IMU batch sampler, the harmonic notches and the gyro low-pass on the spectrum, with the
spectrum after the filters estimated), a **Step response** plot (as PID Review), a **Hardware**
summary of the log (as Hardware Report) - and a **time tolerance** in comparisons (as the Simulink
Data Inspector). With them, a review before the ArduPilot forum: **unrelated logs are no longer
called "the same flight"**, **tolerances the larger of abs / pct**, a **health check that reads the
log's own motor outputs, limits and battery timer**, **ERR / EV by name**, **old ArduPilot telemetry
no longer all errors**, **CSV with a decimal comma, ISO date-times or no time column**, Esc / Copy in
dialogs. Sessions, templates and studies open as before (old ArduPilot unit names are mapped).

### Added
- **Filter review** (ArduPilot): the IMU batch sampler (`ISBH` / `ISBD`) is read - `ISBD[0].GyrX` … at the sensor's rate (2 kHz and more), and `…Post` for the samples after the filters (`INS_LOG_BAT_OPT` 4 or 2). An FFT plot's **Filters** button draws the harmonic notches at the centre frequencies the log recorded (`FTN` / `FTNS` / `FCN`, else `INS_HNTCH_FREQ`) times their harmonics (`INS_HNTCH_HMNCS`, and `INS_HNTC2_*`), the gyro low-pass (`INS_GYRO_FILTER`), and for a gyro before the filters a dashed line: its spectrum after them, estimated with ArduPilot's own filter coefficients. On a real Pixhawk 6X log the estimate is within a factor of 2 of the measured `…Post` spectrum. New template *ArduPilot · Filter review*.
- **Spectra of signals recorded in bursts** (the batch sampler: 1024 samples every second or so) are averaged per burst ("averaged over N bursts") - bridging the pauses smeared the peaks.
- **Step response** plot type: signals in pairs (setpoint, measured), the loop's response to a step estimated from the flight (Wiener deconvolution over 2-second windows, averaged - as ArduPilot's PID Review and PID-Analyzer), with rise time, overshoot and settling; over the cursors' region when they are on; it says when the log is too slow (under 40 Hz) or the setpoint barely moves. A *Step response* tab in *ArduPilot · Rates (PID)*; in reports too.
- **Log panel ▸ Hardware**: board and firmware from the boot messages, frame, ESC protocol, loop rate, every IMU / compass / barometer from its device id (chip, bus, address - ArduPilot's own tables), GPS and battery monitor; *Copy* for a forum post.
- **Time tolerance in comparisons** (as the Simulink Data Inspector): the Compare panel's *Time tolerance (s)* and `signalviewer-cli compare --tol-time` / `"time"` in a tolerances file - a run may be that much early or late (the golden value's band is its lowest / highest within ± that time, then widened by `abs` / `pct`).

### Changed
- **Comparison tolerance: the larger of `abs` and `pct`** of the golden value, as the Simulink Data Inspector (it was the smaller). With a percentage the band closed to 0 wherever the golden value crossed 0, so a roll angle compared with `--tol-pct` failed at every zero crossing, and adding `pct` to `abs` made a check stricter. `signalviewer-cli compare` and the Compare panel alike; give `abs` too for a signal that crosses 0.
- **Health check, battery: below a limit for `BATT_LOW_TIMER` seconds** (10 by default), as ArduPilot judges it - a dip under a burst of throttle no longer makes a flight's battery "low". With `BATT_FS_VOLTSRC = 1` the resting voltage (`BAT.VoltR`) is the one judged.
- **ArduPilot units:** a heading is `[deg]` (was `[degheading]`) and a field of unknown unit has none (was `[UNKNOWN]`): `ATT.Yaw [deg]`, `CTRL.RMSRollP`. A session saved before opens with the new names; templates and check files match either.

### Fixed
- **A spectrum with very small values on a log axis no longer breaks the plot** ("Invalid array length": the axis' tick search never ended below about 1e-15 - a quiet signal, or a spectrum after deep filters). Values far below the largest are drawn at a floor (12 decades), in the app and in HTML reports.
- **A CSV whose first column is not a time** (no column named *time*, and the first one has text or goes down) uses the row number as its time, and the first column is a signal. It became the time anyway and **every row was sorted by it**, scrambling the file; a file whose first column is a name did not open. Live mode goes on counting.
- **The automatic signal alignment checks itself**: two altitudes or voltages that only climb or fall line up at some shift by chance (correlation 1.0 between two unrelated flights) - the pair must also change together there, else the way is *uncertain*, and the dialog says why.
- **CSV with a decimal comma (`1,5`, columns separated by `;`)** - from Excel or a logger in a European locale - is read as numbers. Each such column became a state signal whose "states" were its numbers. Also in Sweeps and in live mode.
- **ISO 8601 date-times in a CSV's time column** (`2026-01-01T10:00:00.5`) are seconds since 1970; they were read as nanoseconds (a time axis in the 10^18).
- **Health check, motors:** when the log has `SERVOn_FUNCTION`, only the motor outputs are checked (a gimbal, a gripper or landing gear on another output counted as a motor), and the finding names the motor (*Motor 3*), not its output. `MOT_PWM_MIN / MAX` of 0 mean the throttle channel's range (`RC3_MIN / MAX`), as in ArduPilot - not the highest output seen, which called a motor saturated.
- **Health check, battery:** the first battery is held to its own limits - with `BATT_LOW_VOLT` at 0 (no limit) battery 2's `BATT2_LOW_VOLT` was used for it.
- **ArduPilot errors (ERR) and events (EV) by name**: *Error: Radio failsafe*, *EKF_YAW_RESET*... (they were *subsystem 5* and *Event 62*). An error marked resolved (code 0) is no longer counted as an error, a refused mode change is a warning, and a lost GPS, a failed autotune, a helicopter rotor below its critical speed and a released parachute are flagged in the health check.
- **Esc in a file dialog opened over another dialog closes only the file dialog.** Esc in *Export CSV*'s save dialog also closed the table of all signals behind it (and the same over any dialog). And after a click on a part of the path (the folder became the current one) Esc did nothing.
- **Copying text works in the desktop window, with the right message when it cannot.** *Copy* in the Log panel's parameters, the Inspector's statistics table, the runs matrix, Investigate's moments and Sweeps' next runs used the browser's clipboard API only (a webview may refuse it) and said "Copying images isn't available" when it failed - now the same fallback as Copy error details, and a message about the clipboard.
- **A template is no longer suggested when it would open nothing.** *Flight on the map & 3D* was offered for a log with attitude and no GPS (the simulation example): its map objects need a position, and the click said "Nothing to open".
- **"Looks like the same flight" no longer offered for unrelated logs.** A .tlog's boot clock says how to put it on an autopilot log's time, not that the two are one flight: opening any .bin and any .tlog together offered to align them. The boot / events alignment is now confirmed by a pair of the same quantity (attitude, altitude, battery...) changing together, and never offered for two different vehicle types.
- **The Align dialog says why.** Under the boot clock and the matching events: "Confirmed: ATT.Roll and ATTITUDE.roll change together at this offset (r = 0.85)", or in red "Probably not the same flight" with the pair and its r, or that the vehicle types differ. Such a candidate can still be applied (two flights on one time axis on purpose). The "same flight" notice names the signal that confirmed it.
- **Old ArduPilot telemetry (before 3.4): boot messages are no longer errors.** Those versions sent STATUSTEXT on their own severity scale (LOW = 1); read as MAVLink's (1 = ALERT) the version banner, "Initialising APM..." and "Frame: QUAD" were errors and the health check said so. The scale is recognised from the banner; the firmware (`APM:Copter V3.x`) is shown again.
- **A failed arming check is a warning, not an error** (`PreArm: Motors Emergency Stopped` made a clean flight's health check red), in .bin, .tlog and .ulg alike.

## 1.20.1 – 2026-11-04

Highlights: **country borders on the satellite photos and clearer on the offline map** - with no
internet too.

### Added
- **Borders** beside the map's layer (offline map and satellite): country borders, with a halo so they read on any land and dashed so they are not taken for roads, and the country names (and on the satellite photos the places) in the UI language. On by default, kept with the session; the street maps keep their own borders.

### Changed
- The offline map's borders are stronger (they were thin and faint).

## 1.20.0 – 2026-11-04

Highlights: the owner's review notes. A **legend that neither jumps nor fills the plot** (beside the
plot when there are many signals), **made signals deleted and renamed from the signal list**,
**named, nested groups** of signals, a **map track coloured by the flight mode** or by a value, an
**example fleet** that shows what the Fleet is for, and in Sweeps **several objectives** ranked by
the Pareto front with a **Pareto chart** that is one click away, and **Clear** as in Recordings.
Sessions, studies and templates open as before.

### Added
- **The legend beside the plot.** A plot's menu has *Legend ▸ Automatic / Above the plot / Beside the plot / Hidden*. Automatic keeps it above while it fits in two rows and puts it in a column beside the plot otherwise (40 signals took a third of the plot): a row per signal, the values in one aligned column, a filter above 8 signals, the width dragged (double-click: as it was). Hidden says how many signals and shows it again in one click.
- **The line under the pointer in front.** The pointer on a legend entry (above or beside) draws that line in front and the plot's others faint.
- **Made signals managed in the signal list.** A signal made in *Create signals* has *Rename…*, *Change the formula…* and *Delete* on its right-click menu (and the Delete key, also for several selected). Deleting asks first when other made signals were made from it and deletes them too; one *Undo* puts all of it back, in every plot. A rename keeps its place: the plots, the groups and the signals made from it (their formulas' `{name}` too) follow. *Create signals*' own delete is the same one.
- **Your own groups of signals.** Select signals, right-click ▸ *Group these* / *Add to a group* ▸ *New group…* and name it; `/` in the name nests it (`Nav/IMU` inside `Nav`). *My groups* is above the files: drag signals onto a group, rename it, take a signal out, remove the group (the signals stay), add the whole group to a plot. Any open file's signals and made signals; saved with the session, undone with Ctrl+Z.
- **A map track coloured by a state or a value.** An object's dialog has *Track colour*: the object's colour, *By a state* (the flight mode is chosen by itself; the colours are the mode lane's) or *By a value* (altitude, speed - a colour scale). A key in the map's corner says what each colour is; the same in 3D. The plain track of the same position takes the object's colour.
- **The Fleet's example.** `examples/fleet`: ten ArduPilot flights of two copters over six weeks - one's vibration grows flight after flight until a flight crosses the limit with clipping; the other has a flight with poor GPS and one on a worn battery. The Fleet panel says what it is for and has *Try the example fleet*, which opens on the vibration trend. Made by `tools/make_fleet_example.py`; see the [Fleet tutorial](docs/fleet-tutorial.md).
- **Sweeps: several objectives, ranked together.** With two or more columns to optimize, the Goal step chooses how the sets that hold are ranked - *the weighted score* (the weights in the table) or *the Pareto front, then the closest to the ideal* - and has *Show the Pareto front* (the Results' charts, a Pareto chart added when there is none). With one, a line says how to add another.
- **Sweeps: a better Pareto chart.** Any two of the objectives on its axes (three or more: a chart per pair), the *balanced* choice starred (the front's set closest to the ideal, every objective counted the same), the Pareto level of each set in the table (*Pareto level*: 1 = the front, 2 = the next...).
- **Sweeps: Clear ▾** beside *Study ▾* - groups, charts, filters and the re-run list; the goal and the results (the columns stay); start the study over; or everything (every study closed, after asking - the notice's *Undo* opens them again).

### Changed
- **The legend's values no longer move it.** Each value keeps a place as wide as the widest it had, and the header never gets lower while the pointer is in the plot (it grew and shrank by a row as the numbers changed length). The time under the pointer moved into the plot's corner. A name that already says its unit (`Roll [deg]`) does not repeat it after the value.
- **20 colours** for new lines (10 before - an investigation with 30 signals repeated them every tenth line).
- **Big automatic groups nest again by the name** (`IMU[0]` ▸ `Acc` ▸ ...) - a group of 12 or more signals whose names go on with one more separator.
- **Sweeps: the tabs say how many lines they draw** - *Parameter sets · 45*, *All runs · 810*; when every set ran once a line says why the two look the same.
- **Sweeps: the Pareto front is found much faster** (10 000 sets and three objectives: 1.5 s instead of 46 s); levels past the tenth are counted together.
- The Fleet's trend follows the typed search (a vehicle's name: its flights alone), not the number's limit (that is the line on it).

### Fixed
- **Sweeps: *All runs* showed the parameter sets** while the runs were still being read - it now says *Reading every run…* until they are there.

## 1.19.0 – 2026-11-03

Highlights: **Sweeps, as the owner specified** - each table apart and merging into a new table
(by rows or on key columns), clearer Columns (conditions, identifiers, templates as files), several
goal rows edited at once, *Show: Holds ▾*, as many charts as wanted, the re-run list in Next runs with
the budget shared by mode, and **Split by** a condition to find the best set for each of its values.
In Recordings, a **derivative or integral of a signal's real updates** (a value computed slower than
it is logged), and plot **images for a report** (twice the pixels) or as an **interactive page**.
Saved studies and templates open as before.

### Changed
- **Sweeps / Data: each table apart, merging as a step of its own** (owner's spec). Every table you load is listed separately in *Tables in this study* - tick, show, export (CSV or HTML with the parallel plot, straight to the save dialog), close. *Merge* makes a NEW table from the ticked ones - rows added, or side by side on key columns (join); optionally a source column (its name editable) and duplicate rows removed; a preview says how many rows and which columns some tables lack (empty there). *Continue with* chooses the table - one, or a merged one - the next steps work on. *Add a table (merge)*, "keep the added table's" and *Close this table* are gone (close a study with its tab's ×). Saved studies keep every table and open as before.
- **Sweeps / Columns** (owner's spec): the roles are *Parameters, Outputs, Conditions, Identifiers* (a run id or a recording) and *Not used*, each explained in its header's tooltip. Above the table: undo / redo, *Reset to guessed roles*, *Template ▾* (Save to a JSON file to share, Load - with a summary of what matched, which new columns need a role - marked in the table - and which formulas were skipped), and the study's numbers in one row (the runs as *640 of 1,922* when conditions are filtered). The side panel: one sentence, each condition as a folding card (many values: a search, *+N more* with each value's runs, All / None on what is found, a min-max range), the new columns as a list (change, delete; the form opens on *+ Add*). The formula completes column names and functions (Tab / Enter) and shows its value in the first run, or what is wrong.

- **Sweeps / Goal**: a column is chosen by typing part of its name ("roll err" finds roll_error_deg; its role and range beside it) in *Must meet* and *Robust to*; Ctrl / Shift-click choose several rows of the goal's table and one bar sets their *at least* / *at most* (a value, or a % of each column's own range) and what to optimize; a new column says *new* until touched; a limit on a column deleted or *Not used* is said.
- **Sweeps / Results: Show: Holds ▾** (All / Holds / Fail / a group) replaces *Only sets that hold* - the table, the lines and the export show the same sets, those that hold first.
- **Sweeps: the re-run list lives in Next runs** (its count in the tab's name; each set with ×, Export, Clear); the button in the top row is gone, and adding a set says so with a link there.
- **Sweeps / Charts: as many as wanted** - *Add chart*, 1 / 2 / 4 in a row, each with *Duplicate*, *Remove*, export (PNG, a high-resolution PNG for a report, or the chart as a page of its own - HTML, the drawing itself) and *In report* (the report has the charts ticked; the others are dimmed).
- **Sweeps / Next runs: how the budget is shared** among the kinds - *Equal* (in turns, as before), *Proportional* (to what each kind found, at least one of each) or *Manual* (a number per kind; together they are the sets to suggest). Kept in templates.

### Added
- **Sweeps: Split by a condition.** A condition's card in Columns has *Split results by this*: the results then show *All together* or one value at a time (a set must hold in every combination of the other conditions with that value - the same goal), and *Best set per value* puts the values side by side (sets that hold, the best value, the best set); a click shows that value. *A group of each value* makes the sets that hold for each value a group of its own colour - for the lines, Show and every chart. A set added to the re-run list while a value is shown is kept with that value, and runs with the combinations of that value only. The report has the best set per value. Kept in templates (skipped, and said, for a table without that condition).
- **Derivative and integral of a signal's real updates.** A value computed slower than it is logged repeats itself - its derivative was zero, then a spike. In *Create signals*, a derivative or an integral now takes *Updates of the signal*: every sample, *at its own, slower rate* (Hz), or *where another signal is 1* (a 0 / 1 flag that marks each update); it is computed on those samples and put back on every sample. In formulas too: `deriv(x, 10)`, `deriv(x, {Flag})`, `integ(...)`.
- **Images for a report, and as a page.** A plot's menu adds *Save image for a report* (a PNG with twice the pixels) and *Save as an interactive page (HTML)* - the plot alone, as in the HTML report (zoom, lines on and off, values under the pointer). The 3D view's *Image* saves at the screen's size or at twice it.
- **Sweeps: zoom in the parallel plots** - the mouse wheel (Ctrl + wheel when the plot is wider than the screen: the wheel still moves it sideways) and + / − / *Reset zoom*, a drag pans while zoomed - to pick one line where they are dense. In Data, a click on a line shows that run's values and marks its row in the Table tab; a click on a column's name colours by it (its menu: right-click); the plot stays as left across tabs.
- **Sweeps in a small window**: the side panel is 220-320 px wide (drag), folds into a panel opened with its button below 900 px; wide tables keep their name column in place; long names are cut with … (whole in a tooltip); the step's button stays at the foot of the side panel.

### Fixed
- **Sweeps / Goal: a limit typed while a new answer arrived** could be lost (the box was made again); the box now keeps what is typed.

## 1.18.0 – 2026-11-02

Highlights: **Sweeps, redone simply** - four steps (Data, Columns, Goal, Results), the goal as one
table of *at least* / *at most* and what to optimize, and the results as parameter sets, all runs,
linked **Charts** (points, histograms, boxes, a correlation matrix, maps, Pareto, clusters, a
self-organising map), **groups** of sets, next runs and the report; the older tools are gone and
scikit-learn is no longer installed. **What changed first** now shows the changes in clusters, the
likeliest cause first, and who leads whom. **Live** moved to the Recordings bar. Fixed: refreshing
a file that is **still being written**. Sessions and templates you already have open as before.

### Changed
- **Sweeps, redone simply.** Four steps: *Data* (load, merge, the table and its lines), *Columns* (what each column is - parameter, output, scenario, run id, not used), *Goal* (one table: at least / at most on any column, what to optimize; the count and the best set follow each change) and *Results* (parameter sets and all runs as lines - Keep, Exclude, undo, redo, export -, charts, next runs, report). The older tools (Explore / ranking methods, which parameter matters, the model, maps and points tabs - both still chart kinds -, data health, running sets from the app, comparing studies) are gone, and scikit-learn is no longer installed.
- **Sweeps report: the maps and point plots on screen.** The *Map* and *Points* parts now draw the Charts' map and point panes (and next runs' maps), with how many beside each box; *Which parameter matters* is no longer in the report.
- **Live is in the Recordings bar**, beside undo - it follows the open files and MAVLink, so it belongs to that area; the top row keeps only what every area shares.
- **CI runs on a push only when asked** (`[ci]` in the last commit's message, or *Run workflow*); pull requests always.

### Added
- **What changed first: clusters, the likeliest first.** The changes that happen together are one line each (when, how many, the likeliest names), ordered by how likely a cause - strength, how early before the event, whether it stays changed, whether the other open runs have it too, whether its shape leads the event's signal, whether others follow it; hover a number for its parts (or order by time). An opened cluster has its own plot right there (every signal on its usual level and noise, the span shaded, a tick at each change), *Open as a tab* and *Add to the investigation*. Constant signals, clocks and counters and heartbeats are left out and counted; a log's names are grouped by message (ATT.*); the arrow keys walk the clusters. Above them, *who leads whom*: the likeliest of each cluster in time order, an arrow where the next clearly follows it (by how long, how well it matches).
- **Sweeps: Charts.** A desktop of 1, 2 or 4 linked charts - points, bubble, histogram, box, scatter matrix with Pearson or Spearman correlations, history, Pareto, the lines, a map, a comparison of the marked sets, and which conditions fail how often - each for all the sets or one group. All show the same sets in the same colours; a range dragged on a histogram (or a rectangle on the points, a click on a broken condition) filters every chart, the lines and the table.
- **Sweeps / Charts: the shape of the sets.** Two new chart kinds: *Principal components / clusters* - the sets on their first two principal components (or a map that keeps their distances), coloured by k-means or hierarchical clusters, the clusters kept as groups in one click - and a *Self-organising map*, a grid of nodes with how many sets each holds, darker at the borders between clusters; a click on a node keeps its sets as a group.
- **Sweeps: groups of parameter sets.** Filter on the axes and *Save as group* (a rule that follows new results; Shift keeps just the sets of now). The groups panel lists the automatic groups (all, hold every condition, Pareto front, fail, error, marked) and yours: colour, count, show / hide in every plot and the table, rename, freeze, union / intersection / difference. Colour the plot by group.
- **Sweeps: each set's status in the table** - a stripe for the sets that fail (amber) or miss an output (red), the failing condition's cells marked, and a tooltip *fails in k of n*; a column with each set's groups.

### Fixed
- **Refreshing a file that is still being written.** The read used to follow the writer to the end of the file - the progress stood at 100 % until the writing stopped - and the refresh after it could report the file as unchanged. Now a refresh reads the file as it was when the refresh began (a row still being written waits for the next read), the next refresh or live mode reads the rest once, and a file's text columns are no longer lost when it grew in between.

## 1.17.0 – 2026-11-01

Highlights: **Sweeps**, a second work area for the results of a run envelope - a table with a row
per run, and the question *which parameters hold in every scenario, and which of them is best?*
answered step by step: the columns' roles, goals with conditions and objectives (several, compared),
a parallel plot filtered as in HiPlot, maps, robustness, what to run next and a report of the whole
process; **Explore** tries a goal's limits, ranges and objectives as sliders, live in the lines and
the table. Also **work areas**, **names on the tool rail**, **a welcome screen that shows what the
app does** and **one place for messages**. Fixes: a **line width** you choose is drawn, and
**limits** show as soon as they are set. Nothing changes in results, sessions or templates you
already have.

### Added
- **Sweeps: Explore** - a new tab of the results, a draft of the active goal where everything works
  together: the goal's conditions dragged as *what if*, limits on the parameters (a range each),
  and the objectives - added and removed by typing, each with its direction, weight and an optional
  *good enough* threshold. At every move: a funnel (all sets → meet the conditions → within the
  limits → good enough), what each slider alone takes out, a strip under each slider of where the
  sets are (those left in green), the best set (and a note when a move changed it), the leading
  candidates with their margins, and with two objectives the Pareto plot (the front ringed, the best
  by the weights starred). Nothing is the goal until **Save as a goal** - a new goal or replacing
  the one it came from: the limits and thresholds become conditions, so the saved goal holds for
  exactly the sets Explore left. *Back to the goal* drops the draft. A condition can now be on a
  parameter too.
- **Sweeps: Explore, live in the lines and the table** - *Explore this goal →* in the Goals step
  (and beside the answer in the results) opens it with a draft of the goal. Every control is on
  screen from the start: a two-thumb range for each parameter (the whole range = no limit;
  *limited: N* says how many are narrowed, a box finds a parameter when there are many), and for each
  objective its weight (shown with one objective too - it counts from two) and a *good enough*
  slider whose far end is *no threshold*; conditions can be added in Explore itself. Beside the
  controls, the parallel plot and the table of sets show the draft at every move - what is left in
  colour, the rest greyed, the best set drawn thick, the table in the draft's order - with *N of M
  parameter sets left*. Dragging on a parameter's axis sets its limit. The table's Export writes what
  is left: the sets (CSV, in the table's order), their runs, or the interactive plot. *Back to the
  goal* shows the goal's own lines again; nothing changes the goal but *Save as a goal*.
- **Sweeps: the best set while a goal is edited**: the foot of the Goals step says how many sets
  hold and shows the best set with its goal - a condition, a direction or a weight changed there
  shows its effect at once, without going to the results (*Open it* goes there, with the set open).
- **Sweeps: the journal tells the final story**: the report's journal shows, by default, what the
  study ended up as - each goal's last version, the roles as their net change, the keep / exclude
  steps still standing; trials that were undone or overwritten (a tolerance added and taken away,
  a limit tried three ways) are not in it, nor is opening a file (*Where it comes from* names the
  tables). *Everything* shows the whole journal. In the Report step × leaves a line out of the
  report (↺ brings it back), and ⤒ on a line says *the analysis starts here*: what came before stays
  out. The report follows what the Report step shows.
- **Sweeps, next runs - compact, and more than CSV**: a parameter with one value in every
  suggestion is said once above the table, which shows only what changes (*show every column*
  brings the rest back); the value a suggestion moves is in bold. *Export the next runs ▾* writes the
  run list (each set × each combination) or the sets alone as CSV, TSV, JSON, a MATLAB struct
  array (.m) or a Python list of dicts (.py) - for a simulation script to read as it is - and
  *Copy the sets* puts them on the clipboard for a spreadsheet.
- **Sweeps, next runs - numbers that add up**: each kind says what it **found** and what it
  **took**, and the takes add up to the sets suggested; under the number asked: *up to N sets × M
  combinations = up to R runs*, and after suggesting, what came out (*N sets × M = R runs*) and,
  when fewer than asked, that the kinds ticked found only that many. How the number is shared is
  said: in turns, one of each kind ticked, then a second of each - a small number gives the first
  kinds one each, and what a kind cannot fill goes to the others.
- **Sweeps: an axis taken off comes back**: the axes taken off the lines lately - from an axis's
  menu or the column picker - are listed under the bar (*Taken off: + ki_roll*), one click each to
  bring one back; the picker's button says it adds as well as removes (*Columns: 8 of 22 (add /
  remove)*).
- **Sweeps: the sets shown as an interactive plot**: the table's *Export* also writes its sets -
  only those that hold, those a rectangle or a filter kept - as an interactive parallel plot (HTML,
  like HiPlot: drag on an axis to filter, click a line), besides CSV.
- **Sweeps, many columns**: when the lines are wider than the screen, a **slider** under them says
  which axes are on screen (*axes 5–13 of 42*) and moves along them - dragged, clicked, or with the
  keys (Home / End) - besides the mouse wheel; *Fit to width* puts every axis in and the slider goes.
- **Sweeps: the optimization in the plots, and choosing on a Pareto plot**: when a goal is set the
  lines get its axes - the goal, the **rank**, each further objective's worst case and the weighted
  **score** - so dragging on *rank* keeps the best few and the parameters' axes show what they
  have. In Points, **+ Pareto** plots the first objective against the second with the Pareto
  front's sets ringed and joined. **A rectangle dragged on any point plot keeps what is in it**: it
  becomes the filters of its two columns, so the lines, the table of sets, its Export (CSV and
  the interactive plot) and the report follow; a click on the plot clears it.
- **Sweeps: how the plots look, and the points in the report**: a **Style ▾** next to the maps, the
  point plots and *Which parameter matters* - the colour map (viridis, plasma, cividis, turbo,
  greys), a point's size and opacity, the grid and its minor lines, the numbers on a map's cells -
  kept with the study and used by the report. The point plots have their axes' titles and a grid,
  and go into the report; *Which parameter matters* has its axes' titles (the parameter, the goal)
  and a grid, on screen and in the report.
- **Sweeps: where the optimization shows**: the answer's panel shows **the best set** - its
  parameters and its goal (its score with several objectives, its worst case within the tolerance
  when robust) - and opens it. A map can be coloured by **the best goal** of each cell instead of
  the share that holds (*Colour*; with only something to optimize every set holds, so this is the
  default then), the best set has a ★, and each map says what its colour and its numbers are. With
  conditions but nothing to optimize the cells have no number any more - it was the share, *1*.
  The report's maps are drawn the same way, with a colour bar.
- **Sweeps: the whole process in the report**: each study keeps a **journal** - opened, roles
  changed, each goal as it ended up, robustness, columns taken out, keep / exclude, tables merged
  in, templates applied, suggestions made, files written, reports made - with the time of each
  (a run of edits to one thing is one line; undo is not a step of its own). Each table merged in
  starts an **iteration**: how many sets hold and the best goal after each, as a table and a plot
  of how the study converged. The report has both, and **Where it comes from**: each table read,
  its size, time and SHA-256 (to find the very same file again), and the app's version. The Report
  step shows the journal and the iterations on screen; they are saved with the study.
- **Sweeps templates**: *Study ▾ → Templates…* opens one dialog for them - save the study as a
  template (it asks before replacing one of the same name), see how many of each template's columns
  this table has and its goals, apply one (or double-click it), **export one to a file** for a
  colleague and **import** one (a taken name becomes *name (2)*), delete one. A template now keeps
  the maps, the table's columns, robustness and next runs' choices too - but not what belongs to one
  table's runs (keep / exclude steps, next runs' answer). *Save as a template…* stays in the menu,
  and also asks before replacing.
- **Sweeps: robust to a parameter, and next runs on the parameters you choose**: in Goals, **Robust
  to** takes the parameters a good set must not be fragile to (typed, as everywhere), each with how
  far it may move - ± a percentage, ± a value or ± grid steps. A set then *holds robustly* when every
  set within the tolerance holds too; the table gets *holds robustly*, the goal's worst case within
  the tolerance and how many sets that was, and only the sets that hold robustly are ranked. When
  the grid is coarser than the tolerance, the step says so. **Next runs** explores the parameters
  you choose - all, those on the maps, or typed - and the others stay at the values of the set each
  suggestion starts from; **Is it robust?** proposes the runs at the ends of the tolerance of the
  best sets. With several objectives *near the best* follows the weighted score. A suggestion that
  moves a parameter a map does not draw is marked apart on it; the suggestions and their choices
  stay with the study (after a restart too), say when the question has changed since, and go into
  the report's process with the run list written.
- **Sweeps: several maps and point plots**: **+ map** adds a map of two other parameters (each map
  has its own pair, × takes it away); with three parameters or more, *The others* chooses between
  every value (the colour is the share holding over all of them) and **a slice at the best set**
  (the others held at its values, which the map names). A line marks where holding begins. A click
  on a cell keeps its sets on the lines' axes (*Show the lines* goes there). **+ points** does the
  same for the point plots. Every map on screen goes into the report, each with its title (and the
  values of a slice); they are kept with the study and undone with Ctrl+Z.
- **Sweeps: the sets that hold, to take elsewhere**: the table of sets has its own bar -
  **Only sets that hold (n of m)**, its **Columns** (any column of the answer: outputs per set, new
  columns, scores...), pages instead of stopping at 300 rows, and **Export**: the sets as shown (a
  row each, the columns shown, in the table's order, holds as 1 / 0) or all their runs, as CSV. A
  click on a header sorts by it (again: the other way; *best first* goes back). The report's table
  (HTML, Word, PDF, CSV) is now the table on screen - its sets, order and columns - and the report's
  process says when only the sets that hold were shown and how the table was sorted. These choices
  are kept with the study and undone with Ctrl+Z.
- **Sweeps with many columns**: each axis of the parallel plot keeps room to be read, and the plot
  scrolls sideways - with the mouse wheel, as there is nothing to scroll up or down - instead of
  squeezing forty axes into the screen; *Fit to width* squeezes them in when wanted. The tooltip
  of a line lays its values out in columns. **Columns (n of m)** chooses what is shown, in the plot
  and the raw table, from one list: type part of a name, take every match in one go, or a group
  (parameters, outputs...) - it replaced *Show columns* and *+ axis*. In the table of sets the
  re-run box, the rank and holds / fails stay in view when it scrolls sideways. The steps' panel
  and the set's panel are dragged wider or narrower (double-click: back to the default) as in
  Recordings, and the steps' panel can be hidden (‹ at the start of the steps) for more room.
- **Sweeps: undo / redo, and the studies kept**: every change to a study - the columns' roles, the
  goals and conditions, what is shown (filters, keep / exclude, axes, *Start the study over*) - is
  undone with **Ctrl+Z** or the ↶ button in the area's bar, and redone with **Ctrl+Y** (a drag on an
  axis or typing a limit is one step; merging a table starts the history again). The open studies
  are kept as you work and open again, where they were, the next time the app starts (a table that
  cannot be read any more is named in a message). The area's messages - saved, exported, merged, or
  why something failed - appear in the app's one place for messages, and **Ctrl+K** offers the
  area's own commands (open, save the study, report, undo / redo, go to a step).
- **Sweeps, easier to undo and to read**: a merged table is taken out again with the × on its
  name (Raw results); *Close this table* is a button there too. A goal is deleted with the × on its
  tab or in the comparison table (the last one is cleared). *Show columns* sets the plot's axes - or
  the raw table's columns - to all of them, or to the parameters, scenarios, outputs, or the
  parameters and the goal. The plot says what one line is: a parameter set (all its scenarios
  together: outputs as their mean, the goal and conditions as their worst case) or a run (one
  parameter set in one scenario - one row of the table).
- **Sweeps, step by step**: the area is now a path through six steps, each with its own panel and
  a line saying where it stands - **1 Raw results** (the table page by page and sortable, or every
  run as a parallel plot; a second sweep is added here), **2 Clean columns** (take out the columns
  with one value or none, add columns made from others), **3 Scenarios & parameters** (a table of
  the columns with a choice for each: scenario, parameter, output...; the shape of the study
  follows), **4 Goals** (conditions met together - *and* - or any of them - *or* - and what to
  optimize; several goals kept and compared side by side: how many sets hold, the best, how
  robust), **5 Results** (the parallel plot filtered as in HiPlot, keep / exclude, the sets, why one
  fails, which parameter matters, the map, next runs, data health) and **6 Report** (the whole
  process). *Export the plot* writes the parallel plot alone as an interactive page, from the raw
  results or from the results. *Study > Start the study over* and *Close this table* say how to
  begin again. The example is new: a drone's roll controller - parameters kp_roll, ki_roll,
  filter_hz; scenarios wind, payload, gusts; outputs roll error, overshoot, energy... - with a
  second, finer sweep to merge.
- **Sweeps**, a second work area, for the results of a run envelope: a table with a row per run -
  parameters and scenario columns first, the outputs last (CSV, Parquet or Excel) - and the question
  *which parameters hold in every scenario, and which of them is best?*
  - **Columns**: each column's role is guessed - *Parameters* (what we choose), *Must hold across*
    (scenario, wind, seed: what we don't), *Outputs*, *Run id* or *Not used* - and so is its scale
    (linear, log, category, ordinal). Any of them can be changed; the changes are remembered for the
    next table with the same columns, and *Back to the guessed roles* undoes them. The shape of the
    study shows at once: parameter sets, combinations to hold in, sets missing one, runs with no result.
  - **The question**: which values of each must-hold-across column count; a goal (maximize or
    minimize an output, by its worst case over the combinations); conditions met in every
    combination, in at least *k*, or in every combination of chosen values. A set that misses a
    combination, or has a run with no result, does not hold.
  - **New columns**: a formula per run (`range_m / payload_kg`), or one value per parameter set - min,
    max, mean, median, P10, P90, spread... of a column, over all its runs or only some scenarios.
  - **Parallel plot**: a line per parameter set or per run; axes added, removed and dragged into
    order; each axis linear, log, category or ordinal, and reversible; lines coloured by any column;
    several ranges kept on one axis (drag, Shift-drag) or typed exactly; a histogram on each axis;
    hover shows a line's values, a click opens its set. What tells nothing can be hidden.
  - **The table** ranks the sets, best first, with each condition's worst case and margin; a set
    opens on the right with *why it fails* (which condition, in which combination, by how much)
    and all its runs, the breaking values marked.
  - **Re-run list**: chosen sets x their combinations (or only those missing or with no result) to a
    CSV the run envelope can read.
  - **Always opens**: whatever the guess, the table opens; with no parameter column yet, the columns
    come first and say what to choose. A folder of statistics files (one per run) opens as one table.
  - **Follow the file**: when the table's file changes, the study says so and reads it again (or
    by itself, with *Follow the file*), keeping the question, the view and the roles.
  - **Templates**: a study's roles, question and view saved by name, offered when a table with the
    same columns opens, applied in one click (what the new table cannot answer is left out).
  - **Several goals**: the Pareto front of the holding sets and a weighted score.
  - **Which parameter matters**: each parameter's effect on the goal (and on holding), in order of
    importance; **Map**: two parameters, the share of sets that hold and the best goal per cell;
    **Points**: any two columns.
  - **Next runs**: new parameter sets to run, each with its reason - the edge between holding and
    failing, near the best, where scenarios disagree, the emptiest corners, what is missing - shown
    on the map and written as a run list.
  - **Data health**: missing combinations, runs with no result, and runs that look wrong (an output
    far from its neighbours' in the same combination); any of them can be left out.
  - **Stability**: per set, the share of its neighbours that hold and how many steps it can move.
  - **Recordings**: a column of the runs' files opens a set's runs - or one run - in Recordings;
    *Runs x conditions* opens its table here.
  - **Merge** a second sweep into a study - finer somewhere, other areas - as rows of the same table
    (a `_source` column says where each run came from); where both ran the same run, keep the newer,
    the older or both. A saved study merges them again when it opens; the example has a second sweep.
  - **Keep / Exclude / Restore**, as in HiPlot: narrow what is shown to the lines the filters keep
    (the axes fit them) or to the rest, step by step; *Step back* and *Restore all* undo it.
  - **Export shown**: the runs on screen after the filters, every column, as a CSV.
  - **One place for each control**: the colour is chosen in an axis's menu (*Colour the lines by
    this*) - the bar above the plot only says what the colours mean, and offers holds / the Pareto
    front / one colour; axes move by dragging their names on the plot (the row of axis chips is
    gone, so the bar is one line and the plot no longer jumps); a column's scale is in its axis's
    menu, Columns only says what each column is. The area's bar: *Open* (a table, a folder, a saved
    study), *Study* (save, templates, report), *Export re-run list* (every combination, or only
    what is missing or failed).
  - **Report** (*Study > Report…*) of the answer and of how it was reached - the question, the
    process (tables merged, runs left out, each filter, each keep / exclude step, the re-run list),
    the parallel plot, which parameter matters, the map and the best sets - as **interactive HTML**
    (one file that opens in any browser, offline: drag on an axis to keep a range, click an axis's
    name to colour by it, the table follows), **Word**, **PDF**, or the answer table as **CSV**. A
    title and notes go at the top; the dialog shows the process as it will be written.
  - **Compare** two studies of the same sets (before and after a change), **save / open a study**
    (`.svsweep`).
  - **CLI**: `signalviewer sweep TABLE --question q.json` - exit 0 when enough sets hold, for CI.
  A million-row table opens in about a second; reopening it reads a compressed copy kept in the
  cache. An example table and the script that makes it (also in a big size) are in `examples/sweeps`.
- **Work areas** (the way Mission Planner has its screens): the top row now holds what is the same
  everywhere - the name, the area, search, live, settings, theme, language, help - and the row under
  it is the area's own: its session, plot tabs, templates, undo / redo, Clear and the Inspector. Today
  there is one area, **Recordings** (everything the app did so far), so only its name shows; areas for
  other kinds of work can be added beside it without moving anything in this one.
- **The tool rail has names**: Files, Create, Compare, Investigate, Report, Fleet under their icons -
  Investigate and Fleet were hard to find behind an icon alone.
- **The welcome screen**: a line on what the app is for, and the examples as cards - each with what it
  shows (a drone flight: map, 3D and attitude; an ArduPilot log: the automatic health check; find out
  what went wrong: Investigate…). They used to be one line of links that did not wrap: below 1920 px
  the last one (the Investigate example) ran off the screen.
- **One place for messages**: the start card and the messages are together at the lower corner of
  the plots, above the timeline. At most three messages show; older ones still up wait behind
  *+N*. **Esc** takes one step back: the selection, then the newest message, then the start card
  (it used to stay over the plots until its × was clicked).

### Fixed
- **A narrow window** (1024 px): the app was wider than the window - the top row could not get
  narrower, so the right edge of every area was cut; it fits now (the search keeps its icon). In
  Sweeps the step's *← back* and *next →* buttons went over each other in a narrow side panel and
  the plot's bar scrolled under its own scrollbar: they wrap. The steps, *Follow the file* and the
  re-run button get shorter in a narrow window; a map fits a narrow column.
- **Sweeps, the report's map** showed the largest goal of each cell as its best when the goal was to
  minimize; it shows the smallest now, as the map on screen does (one function makes both).
- **Sweeps, optimize**: with two or more objectives the sets that hold are now ranked by the
  weighted score - the weights decide the order (the first objective alone ranked them, the weights
  only moved the score column). The step says, in a sentence, by what the sets are ranked now; an
  objective is called *objective* (*+ objective*), not *goal* like the goal it is part of, and its
  column says *worst case (maximize)* / *(minimize)*: the smallest value over the scenarios when
  maximizing, the largest when minimizing. *Compare goals* shows the best set's score too.
- **Sweeps**: a parameter taken out in *Clean columns* is no longer offered by the map, next runs
  or the report's map (the map said *Choose two different parameters*); the marks of next runs are
  drawn on the axes the map shows; a goal's weight shows that goal's number after switching goals;
  saving or deleting a template says so (and says why when it fails).
- **Line width** had no effect on most recordings: a line with about a point per pixel or more was
  always drawn 1 pixel wide, whatever the width - in practice every long recording, even zoomed in.
  A width you set is now drawn; only lines at the default width keep the fast thin drawing.
- **Limits** (Inspector → Limits) were checked but their dashed line did not appear on the plot
  until something else about the signal changed (its colour, say). They show at once now.
- **Open files** was cut to "Open fil" (in Hebrew too) once files were open and the panel's head
  had its other buttons; it is the + alone then, its name in the tooltip.
- The messages no longer cover the timeline's speed and cursor controls.

## 1.16.0 – 2026-10-29

Highlights: **when the file on screen was saved, and whether a newer one is on the disk** - its time
on each file, amber when another program saved it again, a click (or F5) reads it; and fixes to
**Investigate** - above all *What changed first*, which on a span early in the file or a long one
said that nothing changed. Nothing changes in results, sessions or templates you already have.

### Added
- **When the file on screen was saved, and whether there is a newer one**: each file in the list shows the time its version on screen was saved to the disk (the date for another day); hovering adds when the app read it. When another program saves the file again, the time turns amber with ↻ - only the file's date is checked, every few seconds, nothing is read - and a click (or F5) reads the new version. The message after a refresh says, per file, *read again - saved at 21:24:07* or *not changed on the disk*, stays 10 s, and a new refresh replaces it instead of stacking up. (It used to say only "2 files refreshed", for 4 s - with small changes in the data it was not clear whether the file had been read at all.) In live mode the green dot stays as it was.

### Fixed
- **What changed first** on a span early in the file, or a long one, read the usual level from before the first sample: every signal had "no data" and the panel said *No signal left its usual range* - a wrong "nothing changed". The usual level is now read inside the data (the time before the span shrinks first, then the baseline), and a span with nothing before it says so: *pick a span later in the file*. *Find similar* reads it the same way.
- **Numbers with an exponent** in a condition or a new signal's formula (`Speed > 1e3`, `2.5E-3`, `1_000`) were read as a signal called `e3` / `E` ("missing in every file").
- **What changed first**: a state signal that went to a lower value was shown as rising (↑).
- **Hebrew** in *What changed first*: "no change" came before the other file's name, the file in the scope list was cut in the middle of its name, and times said "s" instead of ש׳.
- "1 stretches" → "1 stretch" (the condition count, the strip, the stretches table, the steps list).

## 1.15.0 – 2026-10-28

Highlights: **Investigate** - from "something went wrong in this flight" to an answer you can show:
name the moments that matter (conditions), see what left its usual range first and how long after,
check it against the other runs, and write it up with findings and a report. Also: **the error per
axis in one click**, a **file's time axis changed while working**, and **no more silent blank window**
on offline computers with an old Edge WebView2. Nothing changes in results, sessions or templates you
already have.

### Added

**Investigate** (the magnifier on the left; an example with a known answer on the welcome screen):
- **Conditions**: name the moments that matter (`Speed > 30`, `abs(Vz) > 5 and Mode == "AUTO"`, with hysteresis and minimum length) and see them in every open file - counted while you type, stepped through with `]` / `[`, shaded on the plots, combined, hidden, deleted with undo. With both cursors on, **Find similar** on the bar above them writes the condition for you, on the signal most unusual inside the selection (of all the tab's plots, not only the active one).
- **The run at a glance**: a strip above the plots, under their time axis, with the run's phases in the plots' own colours and a few automatic flags - a frozen or saturated signal, a gap in the recording, a glitch - and where the plots are zoomed; click to go there. Its rows are yours (any state signal or condition, added, replaced, moved, removed) and a click picks stretches (Ctrl / Shift+click: *or* in a row, *and* across rows), shaded on the plots, saved as a condition in one click.
- **The stretches of a condition, together**: a table of them (sort, click to go there, copy), all of them on top of each other in a new tab (lined up at start, end or peak, their mean bold), and **What differs inside** - the signals most different inside the stretches than outside.
- **What changed first?** On the selection bar: every signal of the event's file - also the ones on no plot - in the order it left its usual range around the span, with a small picture each and dashed lines on the plots; under each, the same signal in the other open runs at the same time (a run without the event that has the same change shows that change alone does not explain it). The ones the sample rates cannot order are grouped; a signal that was already drifting steadily (a used-energy counter, a clock) is judged against its own trend. For long logs: a filter, rows and whole groups taken out, groups that close. The **lag** between any two ("Roll follows Motor3 by 120 ms"), shown aligned on the plot. A click on a candidate opens it in a plot of its own (Ctrl+click: into the active plot). Candidates, with the warning that earlier is not cause.
- **Runs × conditions**: every open run against every condition - counts or total time, the parameters that tell the runs apart (constant signals, numbers in file names), the odd run marked, a click to its stretch, two columns against each other with a fitted line - and *Open a folder of runs…* for a whole Monte-Carlo set.
- **Findings and an investigation report**: a note can be a finding (open, explained, fault, rejected hypothesis) that keeps the view it was found in; **Steps so far** records what you do, grouped by kind (a group goes into the report, closes or is removed at once; a filter); the report can include the investigation - findings with their plots, rejected hypotheses, the analysis steps, conditions per run and how to reproduce it (HTML, PDF, Word).
- **Templates take the investigation along**: a template saved while investigating keeps the conditions (they are written by signal name); opening it on the next flight's file adds the ones not there yet, counted on that file at once.
- **An example with a known answer** (welcome screen → *find out what went wrong*) and a tutorial that walks through every tool on it (docs/investigate-tutorial.md, in Hebrew too).

**Plots and signals:**
- **One into each plot**: select several signals - a flight computer's X, Y, Z - and put one into each plot of the tab, beside the true X, Y, Z already there one per plot. They are paired by the part of their names that differs (X / Y / Z, [0] / [1] / [2], Roll / Pitch / Yaw), else by order; ones with no plot left get new plots. The added set has one colour in every plot, a message says what went where, and one Undo takes it back. In the ▾ beside *Plot them*, with *Each in a new plot* (and in the right-click menu of a selection or a group).
- **The error per axis in one click**: ⋯ on a plot with two lines - *Error: NavPos_X − TruePos_X*, or *Error in every plot with two lines* - opens the errors (second line − first, where both have data) in a new tab, a plot per axis titled with its RMS, mean and largest error and when it happened; the flight mode where it is worst is named when it stands out (1.5 × the next). The cursor goes to the largest error.
- **Time axis…** (right-click a file; it replaces *Time offset…*): another column as the file's time (CSV / text, MAT, Parquet), the unit of its time - ready conversions (ms → s, µs → s, s → min…) or any scale - and its offset, in one place. Before anything changes it says what the new axis looks like (only goes up / goes up and down / repeated values / missing values / long gaps, the unit its name says) and what will mean something else: the column leaves the plots it is in, new signals and edits computed against time (derivative, integral, filters, a shift in t) are computed again on the new axis, signals made from the column itself will fail, other open files keep their axis. A column that goes up and down needs a tick first, and offers an X-Y plot instead. With *Link plots* / *Link operations* on, the same change can be made on the other files. Cursor, zoom and notes follow the same rows; one Undo puts the file and the work back. Kept in sessions, refresh and live mode; in Python: `sv.load(path, {"time_scale": 0.001})`.
- **Columns with a time column of their own** (a `time_boot_ms` beside a time in seconds) can now be put in seconds: a scale of their own in *Time axis…*.
- **State lanes, where you want them**: right-click a lane (or its chip, or the signal in the list) → *this plot only*, *every plot of this tab*, *every time plot, all tabs*, or *Remove this lane*. **Always as a state**: by the signal's name, in every plot and every file, without setting it in each plot again.
- **Map objects from ECEF / NED / ENU**: *Position from* in the object dialog - the three components in metres, and for NED / ENU the reference point (the first sample of a latitude / longitude / altitude, or typed numbers). Made with the existing frame conversion when the object is saved; editing reads it back.
- **Smoothing a noisy position or vector**: *Smooth position (s)* on a map object, and *Create signals → Several → Smooth a vector* for any 2-3 components (a velocity, say): a centred average over a window in seconds, never across a gap, latitude / longitude handled across ±180. New signals; the recorded ones stay as they are.
- The object dialog says that the attitude can be a quaternion and that its angle unit only changes the drawing.
- **Safe graphics** (`--safe-graphics`, a *Signal Viewer (safe graphics)* shortcut in the portable package and the Start menu): draws without the graphics card, for a white or black window on virtual machines, remote desktop or old drivers. The 3D view keeps working.
- *Help → About* says which engine draws the app (WebView2 / Edge / Chrome / Firefox and its version) and whether in its own window or a browser.

### Fixed
- A long plot title no longer runs under the plot's buttons: it is cut with "…" (the whole of it on hover).
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
