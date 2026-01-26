# Signal Viewer Pro - Next Tasks Implementation Plan

## Priority Order

Based on impact and effort analysis:

| # | Feature | Impact | Effort | Priority |
|---|---------|--------|--------|----------|
| 1 | FFT Analysis | High | Medium | ⭐⭐⭐⭐⭐ |
| 2 | Region Selection + Stats | High | Medium | ⭐⭐⭐⭐⭐ |
| 3 | Measurement Cursors | Medium | Low | ⭐⭐⭐⭐ |
| 4 | Statistical Panel | Medium | Low | ⭐⭐⭐⭐ |
| 5 | Click-to-Select Subplot | Medium | Low | ⭐⭐⭐ |
| 6 | Keyboard Shortcuts | Low | Low | ⭐⭐⭐ |
| 7 | Signal Filtering | Medium | Medium | ⭐⭐⭐ |
| 8 | PDF Export | Low | Low | ⭐⭐ |

---

## Task 1: FFT/Spectrum Analysis

### Goal
Add frequency domain analysis capability for any signal.

### UI Changes

**Option A: New plot mode (recommended)**
```
Toolbar: Time | X-Y | FFT
When FFT selected:
- Shows magnitude vs frequency plot
- Uses assigned signals from current subplot
```

**Option B: Separate FFT window**
```
Right-click signal → "Show FFT"
Opens modal with FFT plot
```

### Implementation Steps

1. **Add FFT computation in ops/engine.py**
```python
class FFTOp(Enum):
    MAGNITUDE = "magnitude"
    PHASE = "phase"
    PSD = "psd"  # Power Spectral Density

def compute_fft(time: np.ndarray, data: np.ndarray, 
                window: str = "hanning") -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute FFT of signal.
    Returns: (frequencies, magnitudes)
    """
    dt = np.mean(np.diff(time))
    fs = 1.0 / dt  # Sampling frequency
    
    # Apply window
    if window == "hanning":
        windowed = data * np.hanning(len(data))
    else:
        windowed = data
    
    # Compute FFT
    fft_result = np.fft.rfft(windowed)
    freqs = np.fft.rfftfreq(len(data), dt)
    magnitudes = np.abs(fft_result) * 2 / len(data)
    
    return freqs, magnitudes
```

2. **Add FFT mode to SubplotConfig in core/models.py**
```python
@dataclass
class SubplotConfig:
    mode: str = "time"  # "time", "xy", "fft"
    fft_window: str = "hanning"
    fft_log_scale: bool = True
```

3. **Add FFT button to toolbar in ui/layout.py**
```python
dbc.Button("📊 FFT", id="btn-mode-fft", size="sm", color="secondary", outline=True),
```

4. **Add FFT trace rendering in viz/figure_factory.py**
```python
def _add_fft_traces(fig, runs, derived, sp_config, row, col, ...):
    for sig_key in sp_config.assigned_signals:
        time, data = get_signal_data(...)
        freqs, mags = compute_fft(time, data, sp_config.fft_window)
        fig.add_trace(go.Scattergl(x=freqs, y=mags, ...))
    
    # Update axes labels
    fig.update_xaxes(title_text="Frequency (Hz)", row=row, col=col)
    fig.update_yaxes(title_text="Magnitude", type="log" if log_scale else "linear")
```

5. **Add callback for FFT mode toggle in app.py**

### Files to Modify
- `ops/engine.py` - Add FFT computation
- `core/models.py` - Add FFT config to SubplotConfig
- `ui/layout.py` - Add FFT button
- `viz/figure_factory.py` - Add FFT rendering
- `app.py` - Add callback for mode toggle

---

## Task 2: Region Selection + Statistics

### Goal
Allow user to select a time region and see statistics for that region.

### UI Changes

```
Toolbar: [📏 Select Region] button
When active:
- Click-drag on plot to select region
- Shaded rectangle shows selection
- Floating stats panel shows: min, max, mean, std, RMS
```

### Implementation Steps

1. **Add region state to ViewState in core/models.py**
```python
@dataclass
class ViewState:
    # ... existing ...
    region_start: Optional[float] = None
    region_end: Optional[float] = None
    region_enabled: bool = False
```

2. **Add Select Region button to toolbar**
```python
dbc.Button("📏 Region", id="btn-region-select", size="sm", ...)
```

3. **Add click event handling in app.py**
```python
@app.callback(
    Output("store-view-state", "data"),
    Input("main-graph", "clickData"),
    Input("main-graph", "relayoutData"),  # For drag selection
    State("btn-region-select", "active"),
)
def handle_region_selection(...):
    # Parse click/drag to set region_start and region_end
```

4. **Add region rectangle in figure_factory.py**
```python
if view_state.region_enabled and view_state.region_start and view_state.region_end:
    fig.add_vrect(
        x0=view_state.region_start,
        x1=view_state.region_end,
        fillcolor="rgba(100, 100, 255, 0.2)",
        line_width=0,
    )
```

5. **Add statistics computation**
```python
def compute_region_stats(time, data, t_start, t_end) -> dict:
    mask = (time >= t_start) & (time <= t_end)
    region_data = data[mask]
    return {
        "min": np.min(region_data),
        "max": np.max(region_data),
        "mean": np.mean(region_data),
        "std": np.std(region_data),
        "rms": np.sqrt(np.mean(region_data**2)),
        "peak_to_peak": np.max(region_data) - np.min(region_data),
        "samples": len(region_data),
    }
```

6. **Add stats panel in right sidebar**
```python
dbc.Card([
    dbc.CardHeader("📊 Region Statistics"),
    dbc.CardBody(id="region-stats-panel"),
], id="region-stats-card", style={"display": "none"})
```

### Files to Modify
- `core/models.py` - Add region fields
- `ui/layout.py` - Add button and stats panel
- `viz/figure_factory.py` - Add region rectangle
- `app.py` - Add selection handling and stats display

---

## Task 3: Measurement Cursors (Two-Cursor Mode)

### Goal
Add a second cursor for delta measurements between two time points.

### UI Changes

```
When cursor is enabled:
- [1-Cursor | 2-Cursor] toggle
- In 2-cursor mode: show two vertical lines
- Display: ΔT, ΔY for each signal
```

### Implementation Steps

1. **Add second cursor time to ViewState**
```python
cursor_time: Optional[float] = None
cursor2_time: Optional[float] = None
cursor_mode: str = "single"  # "single" or "dual"
```

2. **Add second slider or click-to-set**

3. **Display delta values in inspector**
```python
if cursor_mode == "dual":
    delta_t = cursor2_time - cursor_time
    delta_y = value2 - value1
    # Show: ΔT = 0.5s, ΔY = 12.3
```

---

## Task 4: Statistical Panel (Always Visible)

### Goal
Show live statistics for assigned signals in right panel.

### UI Changes

```
Right Panel:
┌─────────────────────┐
│ 📊 Statistics       │
├─────────────────────┤
│ Signal 1            │
│   Min: 0.0          │
│   Max: 100.0        │
│   Mean: 50.2        │
│   RMS: 52.1         │
├─────────────────────┤
│ Signal 2            │
│   ...               │
└─────────────────────┘
```

### Implementation Steps

1. **Add stats section to layout.py**
2. **Compute stats in update_plot callback**
3. **Display as table or list**

---

## Task 5: Click-to-Select Subplot

### Goal
Click on a subplot to make it active (instead of using dropdown).

### Implementation Steps

1. **Add clickData callback**
```python
@app.callback(
    Output("select-subplot", "value"),
    Input("main-graph", "clickData"),
)
def select_subplot_by_click(click_data):
    if click_data:
        curve_number = click_data["points"][0]["curveNumber"]
        # Map curve to subplot index
        return subplot_idx
```

2. **Visual feedback already exists** (blue border on active)

---

## Task 6: Keyboard Shortcuts

### Goal
Add keyboard navigation and shortcuts.

### Shortcuts to Add

| Key | Action |
|-----|--------|
| `←` `→` | Move cursor (when enabled) |
| `+` `-` | Zoom in/out |
| `1-9` | Select subplot |
| `Ctrl+S` | Save session |
| `Ctrl+O` | Load session |
| `Ctrl+I` | Import CSV |
| `Space` | Toggle cursor |
| `Tab` | Next subplot |
| `Shift+Tab` | Previous subplot |

### Implementation

```python
# In layout.py - add keyboard listener
html.Div(id="keyboard-listener", tabIndex=0, style={"outline": "none"}),
dcc.Store(id="store-keypress"),

# JavaScript callback for key events
app.clientside_callback(
    """
    function(n) {
        document.addEventListener('keydown', function(e) {
            // Store key press
        });
    }
    """,
    Output("store-keypress", "data"),
    Input("keyboard-listener", "n_clicks"),
)
```

---

## Task 7: Signal Filtering

### Goal
Add basic signal filtering (low-pass, high-pass, moving average).

### UI

```
Operations Panel:
- Filter Type: [Low-pass | High-pass | Band-pass | Moving Avg]
- Cutoff Frequency: [____] Hz
- [Apply Filter]
```

### Implementation

```python
from scipy import signal

def apply_lowpass(data, fs, cutoff):
    nyq = fs / 2
    b, a = signal.butter(4, cutoff / nyq, btype='low')
    return signal.filtfilt(b, a, data)
```

**Note:** Requires scipy dependency.

---

## Task 8: PDF Export

### Goal
Add direct PDF export (in addition to HTML and DOCX).

### Implementation

Option A: Use reportlab
Option B: Convert HTML to PDF with weasyprint
Option C: Use plotly's kaleido for images, then PDF

---

# Implementation Order

## Phase 1 (Immediate)
1. ✅ Click-to-select subplot
2. ✅ Statistical panel
3. ✅ Keyboard shortcuts (basic)

## Phase 2 (Next)
4. ✅ Measurement cursors
5. ✅ Region selection

## Phase 3 (Future)
6. ✅ FFT analysis
7. ✅ Signal filtering
8. ✅ PDF export

---

# Estimated Effort

| Task | Hours | Complexity |
|------|-------|------------|
| Click-to-select | 2 | Low |
| Statistical panel | 3 | Low |
| Keyboard shortcuts | 4 | Medium |
| Measurement cursors | 4 | Medium |
| Region selection | 6 | Medium |
| FFT analysis | 8 | Medium |
| Signal filtering | 6 | Medium |
| PDF export | 4 | Low |

**Total:** ~37 hours for all features

---

# Design Improvements (Parallel Work)

## Quick Wins
- [ ] Add loading spinner during imports
- [ ] Improve signal list colors (color dots)
- [ ] Add signal count to subplot badge
- [ ] Improve empty state messages

## Medium Effort
- [ ] Virtual scrolling for signal list
- [ ] Collapsible toolbar sections
- [ ] Better color palette

## Future
- [ ] Drag-and-drop signals
- [ ] Undo/redo system
- [ ] Plugin architecture
