# Benchmark — wide5k.csv

262 MB · 5,000 rows · 5000 signals · 1 CPU · Python 3.12.3

| Measurement | Target | Result | |
|---|---|---|---|
| Open, first time (incl. building the cache) | < 3.1 s (5 s per 40 M values) | 3.59 s | MISS |
| Open again (from cache) | < 1 s | 0.44 s | pass |
| Memory for the data after reopening / binary data size | ≤ 1.2× | 24 MB / 191 MB = 0.12× (+ 120 MB runtime) | pass |
| Redraw after zoom, 4 signals (server) | < 300 ms | 4 ms | pass |
| Redraw, full range (server) | < 300 ms | 6 ms | pass |
| Redraw, deep zoom to raw samples (server) | < 300 ms | 4 ms | pass |
| Data sent per redraw | ≤ 1 MB per plot | 39 KB per signal | pass |
| Cursor values (server) | < 50 ms | 2 ms | pass |
| Statistics for a region (server) | — | 2 ms |  |
| Live mode: read 1,000 appended rows | < 1 s end to end | 741 ms (1000 rows) | pass |

Server times exclude browser rendering (measured separately in the browser tests).
Opening speed scales with CPU cores: Arrow parses each 64 MB part in parallel.
