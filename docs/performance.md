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
