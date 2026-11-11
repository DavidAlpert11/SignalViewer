# API: objects, comparisons, maps

Everything the app does with map objects - find them, place a local position on Earth, compare them against
a reference, find similar signals, draw the map, make a report - can be done from Python, from a shell or CI,
or from another program over local REST, **with the same rules and the same numbers**:

- detection reads one table, `backend/svcore/object_names.json`, in the app and in Python, and the shared
  test vectors (`tests/data/object_detect_cases.json`) are run by both;
- the comparison is the app's own operations (`frame`, `relate`) and statistics (`compute_signal_stats`),
  in the same order; a test runs the whole process through Python, the command line, REST and the app's
  dialog path and requires the same statistics to 1e-9 (`backend/tests/test_api_parity.py`).

The examples use `examples/ardupilot_lanes.csv`: an ArduPilot flight with POS, two EKF3 lanes (`XKF1[0]`,
`XKF1[1]`, positions in metres from the EKF origin `ORGN[0]`), and a GPS. Lane 1 is 1.5 m north of lane 0 and
its yaw is 0.5° more - so those are the errors you should see.

## 1. Find the objects

=== "Python"

    ```python
    import signalviewer as sv
    rec = sv.load("examples/ardupilot_lanes.csv")
    for o in rec.objects():
        print(o["name"], o["cls"], o["frame"], o["origin"])
    # POS navigation lla None
    # XKF1[0] navigation ned {'via': 'ORGN[0]', 'rule': 'known'}
    # XKF1[1] navigation ned {'via': 'ORGN[0]', 'rule': 'known'}
    # GPS[0] receiver lla None
    ```

=== "Command line"

    ```bash
    signalviewer-cli objects examples/ardupilot_lanes.csv
    signalviewer-cli objects examples/ardupilot_lanes.csv --all --json    # the reasons as data
    ```

=== "REST"

    ```bash
    # the app (or `python run.py --no-open`) listens on 127.0.0.1; open the file first
    curl -s localhost:8765/api/files/open -H 'Content-Type: application/json' -d '{"paths": ["examples/ardupilot_lanes.csv"]}'
    curl -s localhost:8765/api/objects/detect -H 'Content-Type: application/json' -d '{}'
    ```

Each object carries *why*: the rule that chose each signal (`prefix`, `subgroup`, `known`), the word as written,
the sub-group or paired group, the origin's rule (`own`: its own `ref_lat…`; `known`: the log's origin, as
`XKF1` → `ORGN[0]`; `sibling`: an `origin.*` group beside or above it), a unit that is not metres, near misses.

## 2. One object's arrays

```python
nav = rec.object("XKF1[1]")       # t, lat, lon, alt - the NED position placed on Earth through ORGN[0] -
                                  # and roll, pitch, yaw, vn, ve, vd, all on the position's time
```

## 3. Compare against a reference

=== "Python"

    ```python
    cmp = sv.compare_objects(rec, reference="POS", objects=["XKF1[0]", "XKF1[1]", "GPS[0]"],
                             what=("position", "velocity", "attitude"), frame="ned")
    cmp.reasons      # {'velocity': 'POS has no velocity'}
    cmp.left_out     # {'attitude': [{'object': 'GPS[0]', 'why': 'GPS[0] has no attitude of its own in angles'}]}
    st = cmp.stats() # XKF1[1] Δnorth rms 1.500 ... Δyaw rms 0.500
    cmp.errors()     # Time + "XKF1[1].Δnorth", ... (one time base: the first column's)
    cmp.to_csv("errors.csv"); cmp.to_csv("stats.csv", "stats"); cmp.to_mat("errors.mat")
    ```

=== "Command line"

    ```bash
    signalviewer-cli compare-objects examples/ardupilot_lanes.csv --ref POS --objects "XKF1[0],XKF1[1],GPS[0]" \
        --what position,attitude --csv errors.csv --stats stats.csv --json
    # pass / fail for CI: exit 1 here (lane 1 is 1.5 m off), JUnit XML for the CI's test view
    signalviewer-cli compare-objects examples/ardupilot_lanes.csv --ref POS --tolerance position=1m --junit r.xml
    ```

=== "REST"

    ```bash
    curl -s localhost:8765/api/objects/compare -H 'Content-Type: application/json' \
      -d '{"reference": "POS", "objects": ["XKF1[0]", "XKF1[1]"], "what": ["position", "attitude"], "frame": "ned", "points": 500}'
    # -> stats (full resolution), values / errors decimated to ~500 points for display, reasons, left_out;
    #    "csv": "/path/errors.csv" also writes the errors at full resolution
    ```

What is compared, per object: the differences per component in the chosen frame (`ned`, `enu`, `ecef`, `lla`
as north / east / up, `track` as along / cross / up), the horizontal, vertical and 3D error; the velocity
differences and the speed error (both need velocities); the roll, pitch and yaw errors (each object's own
angles; yaw wrapped to ±180°). Statistics: RMS and mean (time-weighted on uneven sampling), largest |error| and
its time, 95th percentile of |error|, samples.

Two files (a simulation's truth and a flight): `sv.compare_objects([truth, flight], reference="truth:phys", …)`
- an object is named `file:name` where both files have the name; each keeps its recorded time.

## 4. Similar signals

```python
sv.similar(rec)        # [{'leaf': 'XKF1[*].Yaw', 'how': 'instance', 'members': [...]}, ...]
df = sv.compare_signals(rec, ["XKF1[1].Yaw [deg]"], reference="XKF1[0].Yaw [deg]")
df.attrs["stats"]      # rms 0.5 - the yaw passes 359 -> 0 and the difference stays 0.5, never ~360
```

```bash
signalviewer-cli compare-similar examples/three_objects.csv --leaf att.yaw --json
curl -s localhost:8765/api/objects/similar -H 'Content-Type: application/json' -d '{"run": "<run id>"}'
```

## 5. The map and a report

```python
sv.map_image(rec, path="map.png")      # offline basemap, tracks, legend, scale bar, north arrow, attribution
sv.map_html(rec, path="map.html")      # opens with no network: pan, zoom, time slider, light / dark
sv.report(rec, "report.pdf", compare=cmp)   # .html / .pdf / .docx: the map, the error plots, the statistics
```

```bash
signalviewer-cli map examples/ardupilot_lanes.csv --out map.html
signalviewer-cli compare-objects examples/ardupilot_lanes.csv --ref POS --map map.png --map-html map.html --report report.html
```

Over REST the map is the image export of a map plot (`POST /api/export/image` with `"plot": {"mode": "geo",
"geo": {"objects": [{"name", "color", "lat", "lon", "alt"}], "base": "offline"}}`, `format` png / svg / html) and
reports include such a plot (`POST /api/report`). The full reference with every field: `/api/docs` in the app.

## Naming your signals so objects are found

A prefix with `lat` / `lon` (and `alt`), or a position in metres with its frame in the name: `tgt.ned.x`,
`nav.x_ned`, `ship.ecefX`, `boat.pos.north / east / up` (ENU, decided by the whole group), `rov.pos.n / e / d`;
an origin as `origin.lat / lon / alt` beside it or `ref_lat / ref_lon / ref_alt` under it; angles `roll / pitch /
yaw` (or `phi / theta / psi`, a quaternion `qw…qz`) under the prefix or an `att` sub-group; velocities `vel.north`,
`vel_n`, `VN`. Positions in metres must be in metres (`[m]`); `[cm]` is found but not added until converted.
