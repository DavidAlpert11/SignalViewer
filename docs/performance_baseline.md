# Performance baseline (phase 0) and fixes

Measured before the time slider, offline map and 3D work, so their cost can be compared later.
Machine: 1 CPU, 4 GB RAM, headless Chromium **without a GPU** (worst case: virtual machines,
remote desktop, blocked GPU drivers). Tools: `tools/benchmark.py` (server) and
`tools/browser_benchmark.py` (real UI). Reports: `docs/benchmark_browser.md`, server tables below.

## Server: healthy

| File | First open | Reopen (cache) | Redraw | Cursor | Live append |
|---|---|---|---|---|---|
| 5M rows × 7 signals (612 MB) | 3.63 s (target 5.0) | 0.06 s | 4–7 ms | 1 ms | 113 ms |
| 5000 rows × 5000 signals (468 MB) | **4.57 s (target 3.1, MISS)** | 0.28 s | 3–4 ms | 2 ms | – |

The 5000-column miss existed before (3.59 s on a 262 MB file earlier); per MB it is not slower.
Profile of that first open: Arrow parsing 70 % (native, one core), then two avoidable costs:

| Cost | Measured | Fix | Risk |
|---|---|---|---|
| Header line split with pandas' Python engine | 189 ms for 5000 columns | `csv.reader` on the one line: 0.3 ms, identical result | none (pandas' engine uses the csv module for one-char delimiters; keep `split()` for whitespace) |
| `data.strip()` only to test a 64 MB part for emptiness – copies the part | 33 ms per part (≈ 0.85 s on the 1.7 GB file) | `not data or data.isspace()`: 0.003 ms, same result incl. edge cases | none |

Together ≈ 0.45 s on the wide file and ≈ 0.85 s on the 1.7 GB file (would bring the earlier
12.16 s 20M-row result under its 11.5 s target).

## Browser: three real problems

### 1. Thick lines make every full redraw slow without a GPU (biggest)
Adding a signal 529 ms, zoom 1.1 s, dragging the cursor 6.7 fps, cursor-mode playback 4.2 fps.

- JavaScript (incl. React) is only ~70 ms of a 2.3 s playback window; ~1.5 s is
  `CanvasResourceProviderSharedImage::ProduceCanvasResource` – Chromium rasterising the canvas.
- One canvas of 0.55 Mpix, 1,400 points per series: a bare canvas drawing the same points takes
  26 ms per frame. Switching features off one at a time in the app: dashes, clip, text, line
  joins – no change; **line width forced to 1 px: 231 ms → 33 ms per cursor move (7×)**.
- Series default to 1.5 px. A 1-px line uses Skia's fast "hairline" path; wider lines are
  stroked geometrically, which is very expensive for the dense min/max zig-zag of decimated data.
  With GPU canvas this is cheap, without it (VMs, remote desktop) it is what users feel.
- Same result with GPU emulation or CPU canvas: not an artefact of the test machine.

### 2. The cursor redraws the whole plot – twice per move
The cursor line, its flag and the values are drawn on the series canvas, so every cursor move
redraws every series. While dragging, the 25 ms debounce of cursor values never holds (each step
takes longer), so 154 value requests were sent for one drag, and each answer triggers another full
redraw. Draw-mode playback is fast only because it redraws the part up to the cursor.

### 3. Template matching blocks the UI with many templates
With 200 templates and a 5000-signal file, opening a file froze the UI for **3.8 s in one task**;
opening the library took 454 ms. `matchSignal` compares every wanted name with all 5000 names and
recomputes a regex "bare" name for each, for every template, slot, file and call.

### Also
- **Memory leak**: ~100 KB per open → plot → new tab → close cycle, linear (97 KB, then 113 KB
  per cycle over 40 cycles; undo history excluded; store fields grew < 1 KB). Not found yet:
  needs a heap-snapshot comparison.
- 5000-signal file panel: 466 ms to show (budget 300) – grouping by prefix; minor.
- Fine: start-up 347 ms, 529 KB JS, 3.8 MB heap; search 41 ms; scrolling 60 fps; 3×3 grid
  (small canvases, short lines) zoom 379 ms and dragging 35 fps.

## Proposed fixes, by value

| # | Fix | Expected | Visible change |
|---|---|---|---|
| 1 | Draw the cursor, its flag and values on their own overlay canvas; a cursor move redraws only that | dragging / cursor playback from 4–7 fps to ~60 fps, on any machine | none |
| 2 | Cursor values while dragging: at most one request in flight, the latest wins (instead of a debounce that never fires) | 154 → ~a few requests per drag, no extra redraws | values follow the drag instead of appearing at the end |
| 3 | Where a series is decimated (≥ ~1 point per pixel) stroke it at 1 px; the chosen width when zoomed in to raw samples | redraw / zoom / add signal ~5–7× faster without a GPU | dense parts look slightly thinner (they are a solid band anyway) |
| 4 | Template matching: build per file, once, a set of names and a map of bare names; reuse it | 3.8 s → ~tens of ms | none |
| 5 | Header split with `csv.reader`; empty-part test without copying | −0.45 s wide file, −0.85 s on 1.7 GB | none |
| 6 | Find the ~100 KB/cycle leak with heap snapshots and fix it | flat memory in long sessions | none |
| 7 | Count redraws per zoom step and remove redundant ones (a full redraw before the data arrives, another after) | zoom further down | none |

After each fix: the browser benchmark, the server benchmark and all tests again; a fix that does
not show a measured gain is dropped. Item 3 is the only one with a (small) visual effect; item 1
alone removes most of the cursor cost even with thick lines.


## After the fixes

All 18 browser measurements now meet their budgets (`docs/benchmark_browser.md`); same machine,
no GPU. All 109 UI tests and 70 server tests pass.

| Measurement | Before | After | Budget |
|---|---|---|---|
| Add a signal (5M rows) -> drawn | 529 ms | 220 ms | 300 |
| Zoom -> redrawn, p95 | 1,148 ms | 170 ms | 300 |
| Dragging the cursor | 6.7 fps, 156 long tasks | 60 fps, 0 | 50 |
| Cursor-mode playback | 4.2 fps | 59.7 fps | 50 |
| 3×3 grid: zoom p95 / dragging | 379 ms / 35 fps | 241 ms / 53 fps | 500 / 30 |
| File opened with 200 templates + 5000 signals | 3,908 ms (one frozen task) | 171 ms, no long task | 200 |
| Open the template library | 420 ms | 60 ms | 300 |
| 5000-signal file panel shown | 466 ms | 265 ms | 300 |
| First open, 5000 columns (server) | 4.57 s | 4.15 s | 3.1 (still over: Arrow parsing on one core is ~90 %) |
| Start-up | 347 ms | 291 ms | 1500 |

What was done:

1. **Cursor layer** (`TimeChart`): the cursor, its flag and the values are drawn on their own
   canvas over the plot; a cursor move clears and redraws only that (except in draw-mode playback,
   where the series are cut at the cursor).
2. **Cursor values** (`App`): one request in flight; when it returns and the cursor has moved, one
   more for where it is now. Values now follow dragging and playback.
3. **Dense series at 1 device pixel**: a series with about a point per pixel or more (decimated
   min/max) is stroked at `1 / devicePixelRatio`, the canvas's fast hairline path; zoomed in to raw
   samples it keeps the chosen width.
4. **No rebuild per data update**: the plot is rebuilt only when its series or their styles change;
   new data for the same series goes into the existing plot (`setData`). The time window is read
   when drawing (a value captured at build time had frozen zooming once rebuilds stopped).
5. **Template matching**: each file's names are indexed once (exact set + bare names, cached per
   signal list) instead of comparing every name with every name, with a regex per name, each time.
6. **Server**: header line split with `csv.reader` (same result as pandas' engine for
   one-character delimiters; `split()` for whitespace), empty-part test without copying the part.
7. **Panels and dialogs preloaded**: React shows a lazily loaded component only after a ~300 ms
   throttle; their code is now fetched in the background once the app is idle, and each renders
   directly afterwards (an instance keeps the component it started with, so nothing remounts).

Found on the way:

- **The "leak" was the benchmark's**: Playwright keeps handles to elements it touched. Driven from
  inside the page, growth per cycle falls (29 KB, then 15 KB over 40 cycles) – warm-up, not a
  leak. The memory scenario now works from inside the page and reports growth per cycle after
  warm-up: 19.6 KB.
- **File dialog**: Enter could navigate to the previous path / save under the previous name when
  pressed right after typing (it read React state that had not caught up); and on opening, the
  previous folder showed for a moment and its loading could overwrite a path typed meanwhile (the
  open logic ran after paint). Both fixed; this was the intermittently failing session test.

Not done: the 5000-column first open stays over its target on one core – the remaining time is
Arrow's native parser, which uses all cores on a multi-core machine.
