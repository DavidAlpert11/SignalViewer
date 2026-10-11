# Benchmark — big.csv

696 MB · 5,000,003 rows · 7 signals · 1 CPU · Python 3.12.3

| Measurement | Target | Result | |
|---|---|---|---|
| Open, first time (incl. building the cache) | < 5.0 s (5 s per 40 M values) | 4.79 s | pass |
| Open again (from cache) | < 1 s | 0.07 s | pass |
| Memory for the data after reopening / binary data size | ≤ 1.2× | 326 MB / 305 MB = 1.07× (+ 120 MB runtime) | pass |
| Redraw after zoom, 4 signals (server) | < 300 ms | 9 ms | pass |
| Redraw, full range (server) | < 300 ms | 6 ms | pass |
| Redraw, deep zoom to raw samples (server) | < 300 ms | 5 ms | pass |
| Data sent per redraw | ≤ 1 MB per plot | 38 KB per signal | pass |
| Cursor values (server) | < 50 ms | 1 ms | pass |
| Statistics for a region (server) | — | 2 ms |  |
| Live mode: read 1,000 appended rows | < 1 s end to end | 149 ms (1000 rows) | pass |

Server times exclude browser rendering (measured separately in the browser tests).
Opening speed scales with CPU cores: Arrow parses each 64 MB part in parallel.
