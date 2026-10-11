# Browser benchmark

1 CPU · 3.9 GB RAM · headless Chromium (no GPU) · Python 3.12.3

Measured in the real UI. Without a GPU, frame rates are a conservative floor.

| Measurement | Budget | Result | |
|---|---|---|---|
| Start-up: page to ready app (median of 5) | ≤ 1500 ms | 339 ms | pass |
| Start-up: JavaScript loaded | ≤ 800 KB | 540 KB | pass |
| Start-up: JS heap | ≤ 40 MB | 3.9 MB | pass |
| Add a signal of a 5M-row file -> drawn (median of 4) | ≤ 300 ms | 206 ms | pass |
| Zoom (wheel) -> redrawn, 4 signals, p95 of 10 | ≤ 300 ms | 175 ms | pass |
| Cursor scrubbing, 4 signals: frames per second | ≥ 50 fps | 60.0 fps | pass |
| Cursor scrubbing: p95 frame time | ≤ 33 ms | 16.7 ms | pass |
| Cursor scrubbing: long tasks (> 50 ms) | ≤ 0  | 0  | pass |
| Playback (draw mode): frames per second | ≥ 50 fps | 60.0 fps | pass |
| Playback (cursor mode): frames per second | ≥ 50 fps | 60.0 fps | pass |
| Dragging the timeline (draw mode), 4 signals: fps | ≥ 50 fps | 54.3 fps | pass |
| Dragging the timeline (draw mode): long tasks (> 50 ms) | ≤ 5  | 3  | pass |
| 3x3 grid, 36 series: zoom -> redrawn, p95 | ≤ 500 ms | 259 ms | pass |
| 3x3 grid: cursor scrubbing fps | ≥ 30 fps | 56.1 fps | pass |
| 5000-signal file: file panel shown | ≤ 300 ms | 286 ms | pass |
| 5000-signal file: search, last key -> results | ≤ 150 ms | 38 ms | pass |
| 5000-signal file: scrolling the file panel fps | ≥ 50 fps | 60.0 fps | pass |
| 200 templates: open the library | ≤ 300 ms | 203 ms | pass |
| 200 templates + 5000 signals: file opened -> panel updated | ≤ 200 ms | 188 ms | pass |
| Offline map, first view of an area (tiles drawn by the server, empty cache) | ≤ 8000 ms | 7048 ms | pass |
| Offline map, the same view again (cached tiles) | ≤ 1500 ms | 513 ms | pass |
| Offline map: dragging (panning) fps | ≥ 30 fps | 53.9 fps | pass |
| Offline map with a moving object: playback fps | ≥ 30 fps | 57.0 fps | pass |
| 3D view: shown with an object (CesiumJS loaded on first use), software WebGL | ≤ 20000 ms | 9675 ms | pass |
| 3D view: playback with an object, software WebGL on 1 CPU (floor) | ≥ 0.5 fps | 0.8 fps | pass |
| Memory: heap growth per open/plot/close cycle, cycles 10-30 | ≤ 30 KB | 19.5 KB | pass |

Details:

- `grid_scrub_long_tasks`: 0
- `grid_scrub_p95_frame_ms`: 33.3
- `grid_series`: 36
- `map_cached_tiles`: 16
- `map_first_tiles`: 16
- `mem_heap_10_mb`: 5.25
- `mem_heap_30_mb`: 5.63
- `plot_add_all_ms`: [200, 213, 194, 228]
- `scrub_cursor_requests`: 155
- `tpl_runs_change_longest_task_ms`: 0
- `zoom_median_ms`: 145

Note: "5000-signal file: file panel shown" varies between ~260 and ~400 ms from run to run on this
machine, around its 300 ms budget; the same version measured twice gave 374 and 260 ms (phase 4) and
390 and 260 ms (phase 5) - noise of this machine, not a change. The offline map's first view went
from ~6.0 to ~7.1 s between phases 5 and 6; rendering the same tiles with the phase 5 and phase 6
code in one process gave the same times (204 / 212 ms vs 214 / 200 ms per tile): the machine was
slower, not the code.
