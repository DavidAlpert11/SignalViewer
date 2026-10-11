# Benchmark — big20.csv

1675 MB · 20,000,000 rows · 4 signals · 1 CPU · Python 3.12.3

| Measurement | Target | Result | |
|---|---|---|---|
| Open, first time (incl. building the cache) | < 11.5 s (5 s per 730 MB) | 12.16 s | MISS |
| Open again (from cache) | < 1 s | 0.06 s | pass |
| Memory for the data after reopening / binary data size | ≤ 1.2× | 783 MB / 763 MB = 1.03× (+ 120 MB runtime) | pass |
| Redraw after zoom, 4 signals (server) | < 300 ms | 11 ms | pass |
| Redraw, full range (server) | < 300 ms | 6 ms | pass |
| Redraw, deep zoom to raw samples (server) | < 300 ms | 6 ms | pass |
| Data sent per redraw | ≤ 1 MB per plot | 47 KB per signal | pass |
| Cursor values (server) | < 50 ms | 1 ms | pass |
| Statistics for a region (server) | — | 1 ms |  |
| Live mode: read 1,000 appended rows | < 1 s end to end | 295 ms (1000 rows) | pass |

Server times exclude browser rendering (measured separately in the browser tests).
Opening speed scales with CPU cores: Arrow parses each 64 MB part in parallel.
