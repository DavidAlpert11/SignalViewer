# Performance

Measured with `tools/benchmark.py` on a 1-CPU, 4 GB test machine (full results in `docs/`).
The first-open target is scaled by the number of values (5 s per 40 M values, the reference file).

| | 5 M rows × 7 (730 MB) | 20 M rows × 4 (1.7 GB) | 5,000 rows × 5,000 columns (262 MB) |
|---|---|---|---|
| Open, first time | 4.2 – 4.8 s (target 5.0) | 12.2 s (target 12.5) | 3.6 s (target 3.1) |
| Open again (cache) | 0.07 s | 0.06 s | 0.44 s |
| Memory for the data | 1.07× binary size | 1.03× | 0.12× (only shown columns are read) |
| Redraw full / zoom / deep zoom | 6 / 9 / 5 ms | 6 / 11 / 6 ms | 5 / 4 / 4 ms |
| Cursor values | 1 ms | 1 ms | 1 ms |
| Live mode, 1,000 new rows | 149 ms | 295 ms | 741 ms |

Parsing runs at about 8.5 M values per second per CPU core for both long and wide files and scales
with cores (64 MB parts are parsed in parallel). Redraw time does not grow with file size: min/max
summaries per 1,024-sample block are computed once per signal. Wide files: the cache is one
column-major matrix (not one file per column), discrete-signal detection runs on demand, the signal
list is virtualized, and signal choosers are searchable instead of long dropdowns.

## The round of 2026-11-08 (`tools/benchmark.py --synthetic`)

Generated data, no file needed (`--samples`, default 5 million per signal; `--json` writes the numbers for
CI). Measured on a 2-CPU test machine:

| Measurement | Target | Result |
|---|---|---|
| Plot request with a run time offset / without (one signal, zoomed) | ≤ 2× | 0.97× (3.2 / 3.3 ms; was ~15× before 1.23) |
| Zoom step, 30 signals (server, binary answer) | < 500 ms | 17 ms |
| Data sent for that step | ≤ 2 MB | 1.4 MB (JSON before 1.23: a third more) |
| Pan burst of 10 steps: the last answer (older ones cancelled) | < 300 ms | 19 ms (186 ms when every step was waited for) |
| Large .bin (52 MB) with 10 changed signals: memory cache / its budget | ≤ 1 | 59 / 1024 MB |
| Live append, 300-column CSV: 1,000 rows readable | < 1 s | 35 ms |

Opening several files at once (1.23): four 55 MB ArduPilot logs in 1.4 s instead of 2.1 s on two cores.
