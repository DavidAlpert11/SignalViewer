# Command line, Python and file formats

Everything here works without the window, on a PC without a screen and in CI. `signalviewer-cli`
is installed by `pip install signalviewer`; from the source folder it is `python cli.py`.

## Read and export

```bash
signalviewer-cli info flight.bin                       # the signals, their samples and time span
signalviewer-cli export flight.bin --signals "ATT.Roll,ATT.Pitch" --out roll.csv --t0 10 --t1 60
signalviewer-cli export run.csv --out run.mat           # one MATLAB variable per signal + Time
```

Signal names may be written without their unit and in any case (`ATT.Roll` for *ATT.Roll [deg]*)
when that is one signal; a name that is not there gets the closest names.

## Reports

```bash
signalviewer-cli report --template "ArduPilot · Full review" --out reports/ logs/*.bin --format pdf
signalviewer-cli templates                              # what --template can name
```

## Pass / fail in CI: `check`

```bash
signalviewer-cli check runs/*.csv --checks checks.json --junit results.xml
signalviewer-cli check flight.bin --template "My limits"   # the limits saved on signals in the app
```

A checks file ([example](https://github.com/DavidAlpert11/SignalViewer/blob/main/examples/checks.json)):

```json
{"checks": [
  {"name": "Engine temperature below 88 °C", "signal": "EngineTemp", "hi": 88},
  {"name": "Speed while cruising", "signal": "Speed", "lo": 20, "hi": 76,
   "during": {"state": "DriveMode", "value": "CRUISE", "occurrence": "all"}},
  {"signal": "RPM", "lo": 1000, "hi": 3000, "t0": 5, "t1": 50, "scale": 1, "offset": 0}
]}
```

`during.occurrence`: 1 = the first stretch of the state, 2 = the second…, -1 = the last, left out = all.
Each failure says how many times the signal left its limits, when first, and the worst point.
Exit code **0** all passed, **1** a check failed, **2** a check could not be made (a missing file,
signal or state value - never a silent pass). `--junit` writes results CI systems show as tests.

## Against a golden run: `compare`

```bash
signalviewer-cli compare golden.csv new/*.csv --tol-pct 2
signalviewer-cli compare golden.bin today.bin --tolerances tol.json --junit compare.xml
```

```json
{"default": {"abs": 0.5}, "signals": {"Speed": {"abs": 1.0}, "RPM": {"pct": 3, "outside_pct": 1}, "Gear": {"skip": true}}}
```

Every signal both runs have, with the Compare panel's numbers (RMS and largest difference,
correlation; headings wrap at 360°), the most different first. A signal passes when every sample is
within min(abs, pct of the golden value) - or, with `"outside_pct"` (`--allow-outside PCT` for every
signal), when no more than that share of its samples is outside. Without any tolerance the
differences are only listed.

### A simulation against a flight

Two loggers, two clocks, two naming habits: `--align auto` lines the run up with the golden run by
cross-correlation (`--align-on NAME` to choose the signal, `--align SECONDS` to give the shift),
names match with or without their unit, and `{"as": "name in the run"}` in the tolerances pairs
signals named differently. A worked example: [Simulation against flight](sim-vs-flight.md).

## Numerical validation: `validate`

```bash
signalviewer-cli validate                   # one line per case, then "23 passed, 0 failed"
signalviewer-cli validate --json            # every case with expected, measured, error, tolerance
signalviewer-cli validate --junit v.xml     # JUnit XML, e.g. as a record that this installation computes correctly
```

Spectra, filters, derivative and integral, statistics, decimation, Compare and coordinate frames,
each against a reference that does not come from the app. Exit code 0 = every case within its
tolerance, 1 = one is not. The cases and the conventions behind them: [Validation](validation.md).

## Python

```python
import signalviewer as sv
rec = sv.load("flight.bin")
t, roll = rec.signal("ATT.Roll")
df = rec.to_dataframe(["ATT.Roll", "ATT.Pitch"], t0=10, t1=60)     # one time base
sv.show(t, {"roll x2": 2 * roll}, name="from my notebook")         # into the open app
```

## Your own formats

`signalviewer-cli readers` shows the readers folder (`~/.signalviewer/readers`) and what is in it;
`readers --example` writes a Python reader to start from:

```python
@reader(extensions=[".kv"], name="key=value lines")
def read_kv(path):
    ...
    return {"time": t, "signals": {"speed": speed, "mode": codes}, "labels": {"mode": {0: "IDLE", 1: "RUN"}}}
```

Return one time for all signals, or a tuple `(time, values)` for a signal with its own time, or
`None` for "not my file". Saving the file is enough - no restart.

## Raw binary packets (ICD layouts)

A `<name>.icd.json` in the readers folder describes packets as they come off the wire; files with
its extensions then open as signals `<packet>.<field> [unit]`. Try it with
`signalviewer-cli readers --example-icd run.tlm` (a layout and a recording).

```json
{"name": "Bench telemetry", "extensions": [".tlm"], "byte_order": "little",
 "header": {"sync": "0xA55A", "size": 4, "id": {"offset": 2, "type": "u8"}, "length": {"offset": 3, "type": "u8"}},
 "packets": [{"id": 1, "name": "NAV", "size": 14, "time": "t_us", "time_scale": 1e-6, "fields": [
   {"name": "t_us", "offset": 0, "type": "u32"},
   {"name": "alt", "offset": 4, "type": "i32", "scale": 0.01, "unit": "m"},
   {"name": "mode", "offset": 10, "type": "u8", "enum": {"0": "IDLE", "1": "CLIMB", "2": "CRUISE"}},
   {"name": "armed", "offset": 11, "type": "u8", "bits": [0, 1]},
   {"name": "volt", "offset": 12, "type": "u16", "scale": 0.001, "unit": "V", "byte_order": "big"}]}]}
```

Types `u8 i8 u16 i16 u32 i32 u64 i64 f32 f64`; value = raw × scale + `offset_value`. Time from a
packet's field, else from the header (`"time": {"offset", "type", "scale"}`), else the packets are
numbered. Noise, unknown ids and a cut-off end are skipped to the next sync and counted in the load
report. YAML layouts (`.icd.yaml`) work when PyYAML is installed.

## CAN bus logs

candump logs (`.log`), Vector ASC (`.asc`) and CAN frame tables (`.csv` with time, id and data
columns) open with every `.dbc` next to the log or in the readers folder. Signals are named
`<Message>.<Signal> [unit]`, each message at its own rate; value names become text values.
Multiplexed signals, float signals, 29-bit ids and CAN FD payloads are decoded; frames whose id is
in no `.dbc` are counted in the load report.

## With pip: full or light

`pip install signalviewer` has everything. `pip install signalviewer-lite` is the core (CSV, MATLAB
v5, ArduPilot .bin, CAN, binary layouts, every plot and analysis, HTML reports); its extras:
`[parquet]` `[hdf5]` (.h5, MATLAB v7.3) `[mavlink]` (.tlog, live) `[px4]` (.ulg) `[ros]` (.mcap)
`[reports]` (PDF, Word, images) `[desktop]` - or `[all]`. A file that needs a missing extra says which.
Install one of the two packages, not both (they install the same `signalviewer` module).
