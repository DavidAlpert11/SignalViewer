# SDI Feature Map — Signal Viewer Pro

This document maps MathWorks Simulation Data Inspector (SDI) features to Signal Viewer Pro implementations.

## Feature Mapping Table

| SDI Feature | SDI Capability | Signal Viewer Pro Equivalent | Status | Module |
|-------------|---------------|------------------------------|--------|--------|
| **Inspect Signals** | View signal layout, zoom, pan, multiple subplots | Subplot grid (1×1 to 4×4), WebGL rendering, zoom/pan | ✅ Done | `viz/figure_factory.py` |
| **Signal Appearance** | Line color, width, style per signal | Per-signal settings: color, line_width, display_name | ✅ Done | `core/models.py`, UI |
| **Replay Mode** | Cursor sweeps across time, shows values | Cursor slider, play/pause, step controls | ✅ Done | `app.py`, cursor callbacks |
| **Replay Speed** | Adjustable playback speed | Speed control (interval adjustment) | ✅ Done | UI controls |
| **Streaming Display** | Time span, freeze, update modes | Time span config, freeze toggle, append mode | ✅ Done | `stream/engine.py` |
| **File Watching** | Detect file changes, append new data | File mtime/size monitoring, incremental reads | ✅ Done | `stream/engine.py` |
| **Compare Runs** | Overlay signals from different runs | Compare panel: baseline vs compare-to | ✅ Done | `compare/engine.py` |
| **Alignment** | Time base alignment for comparison | Sync methods: baseline, union, intersection | ✅ Done | `compare/engine.py` |
| **Interpolation** | Linear, nearest for different sample rates | Linear, nearest interpolation options | ✅ Done | `compare/engine.py` |
| **Delta/Difference** | Compute A−B between signals | Delta computation with metrics | ✅ Done | `compare/engine.py` |
| **Tolerances** | Absolute, relative tolerance checking | Tolerance spec: absolute, relative | ✅ Done | `compare/engine.py` |
| **Signal Operations** | Derivative, integral, FFT, etc. | Unary ops: derivative, integral, abs, rms, normalize | ✅ Done | `ops/engine.py` |
| **Binary Operations** | A+B, A−B, A×B, A÷B | Binary ops: +, −, ×, ÷, |A−B| | ✅ Done | `ops/engine.py` |
| **Multi-Signal Ops** | Norm, mean, envelope | Multi ops: norm, mean, min, max, sum | ✅ Done | `ops/engine.py` |
| **Derived Signals** | Computed signals as first-class | DerivedSignal model, appears in tree | ✅ Done | `core/models.py` |
| **Reports** | Inspect report, compare report | Report builder: intro, sections, export | ✅ Done | `report/builder.py` |
| **HTML Export** | Report export | Offline HTML export with embedded plots | ✅ Done | `report/builder.py` |
| **Save Views** | Save layout, assignments | Session save/load (JSON) | ✅ Done | `core/session.py` |
| **State Signals** | Discrete state visualization | State signal type: transition lines | ✅ Done | `core/models.py`, `viz/` |

## SDI Reference Links

1. [Inspect and Compare Signals](https://www.mathworks.com/help/simulink/ug/inspect-signals-using-the-simulation-data-inspector.html)
2. [Replay Simulation Data](https://www.mathworks.com/help/simulink/ug/replay-simulation-data-in-the-simulation-data-inspector.html)
3. [Streaming Display Controls](https://www.mathworks.com/help/simulink/ug/streaming-display-controls.html)
4. [Compare Runs](https://www.mathworks.com/help/simulink/ug/compare-runs-in-the-simulation-data-inspector.html)
5. [Generate Reports](https://www.mathworks.com/help/simulink/ug/generate-a-simulation-data-inspector-report.html)
6. [Save Views and Layouts](https://www.mathworks.com/help/simulink/ug/save-and-load-simulation-data-inspector-views.html)

## Non-Negotiable Constraints Compliance

| Constraint | Requirement | Status |
|------------|-------------|--------|
| C1 — Lossless | No downsampling/decimation | ✅ All points plotted |
| C2 — Offline | No CDNs, bundled assets | ✅ Local assets only |
| C3 — Canonical Naming | `signal — csv_display_name` | ✅ Implemented in `core/naming.py` |

## Architecture Overview

```
SignalViewer_Python/
├── app.py              # Main Dash app (~600 lines)
├── core/
│   ├── models.py       # Run, Signal, DerivedSignal, ViewState
│   ├── naming.py       # Canonical naming (single source of truth)
│   └── session.py      # Save/load sessions
├── loaders/
│   └── csv_loader.py   # Flexible CSV import
├── viz/
│   └── figure_factory.py  # Plotly figure creation
├── ops/
│   └── engine.py       # Unary/binary/multi operations
├── compare/
│   └── engine.py       # Run comparison with alignment
├── stream/
│   └── engine.py       # File watching, streaming
├── report/
│   └── builder.py      # Report generation, HTML export
└── ui/
    └── layout.py       # Dash UI layout
```

## Key Design Decisions

### 1. Data Flow
- **Runs**: Loaded from CSV into `Run` objects with `Signal` children
- **Derived**: Created by operations, stored as `DerivedSignal`
- **Assignments**: Signal keys (`run_idx:signal_name`) assigned to subplots
- **ViewState**: Layout, assignments, cursor state — serialized to sessions

### 2. Time Base Handling
- Operations on different time bases require explicit alignment selection
- Options: linear interpolation, nearest neighbor
- Compare: sync to baseline, union, or intersection

### 3. Naming Convention
All signal labels use: `signal_name — csv_display_name`
- Same filename from different folders: `parent/filename.csv`
- Derived signals: `signal_name — Derived`

---

*Last updated: Following task.md Phase 0-9 specifications*

