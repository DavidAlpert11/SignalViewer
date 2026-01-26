# Signal Viewer Pro - Complete Feature Analysis

## Current Version: v2.5

---

## 1. DATA MANAGEMENT

### 1.1 CSV Import
- ✅ Multi-file import (select multiple CSVs at once)
- ✅ Delimiter auto-detection (comma, semicolon, tab)
- ✅ Header row detection
- ✅ Time column selection
- ✅ Preview before import
- ✅ Skip rows option

### 1.2 Run Management
- ✅ Display canonical names (disambiguated)
- ✅ Rename CSV display names
- ✅ Replace CSV path (keep signal assignments)
- ✅ Remove individual runs
- ✅ Collapsible signal lists per run
- ✅ Run count badge

### 1.3 Session Management
- ✅ Save session to JSON
- ✅ Load session from file
- ✅ Preserves: runs, view state, derived signals, signal settings
- ✅ Preserves: tabs, tab view states, axis linking

---

## 2. VISUALIZATION

### 2.1 Multi-Subplot Layout
- ✅ Configurable rows × columns (1-4 each)
- ✅ Up to 16 subplots per tab
- ✅ Active subplot highlighting
- ✅ Custom subplot titles
- ✅ Subplot selector in toolbar

### 2.2 Multi-Tab System
- ✅ Chrome-like tabs (× close button inside)
- ✅ Add/remove tabs
- ✅ Rename tabs
- ✅ Close all / Close others options
- ✅ Independent view states per tab
- ✅ Tab switching preserves state

### 2.3 Plot Modes
- ✅ **Time Mode**: Signal vs Time
- ✅ **X-Y Mode**: Signal vs Signal
- ✅ X-Y alignment: Linear interpolation or Nearest

### 2.4 Axis Controls
- ✅ Manual X/Y limits (popover dialog)
- ✅ Reset to auto-range
- ✅ Scope: Active subplot or All subplots
- ✅ X-axis linking across all subplots in tab

### 2.5 Themes
- ✅ Dark theme (default)
- ✅ Light theme
- ✅ Toggle button in header

### 2.6 Performance
- ✅ WebGL rendering (Scattergl)
- ✅ Figure caching (skip re-render if unchanged)
- ✅ Lossless (no downsampling)

---

## 3. SIGNAL OPERATIONS

### 3.1 Signal Properties
- ✅ Custom display name
- ✅ Line width adjustment
- ✅ Custom color
- ✅ Scale factor (multiply)
- ✅ Offset (add)
- ✅ Time offset
- ✅ State signal mode (vertical transition lines)

### 3.2 Derived Signals - Unary Operations
- ✅ Derivative (d/dt)
- ✅ Integral
- ✅ Absolute value
- ✅ RMS (rolling window)
- ✅ Normalize (0-1)
- ✅ Negate
- ✅ Square root
- ✅ **Batch mode**: Apply to multiple signals at once

### 3.3 Derived Signals - Binary Operations
- ✅ Add (A + B)
- ✅ Subtract (A - B)
- ✅ Multiply (A × B)
- ✅ Divide (A ÷ B)
- ✅ Absolute difference |A - B|

### 3.4 Derived Signals - Multi-Signal Operations
- ✅ L2 Norm (sqrt of sum of squares)
- ✅ Mean
- ✅ Min
- ✅ Max
- ✅ Sum

### 3.5 Signal Linking
- ✅ Link multiple CSVs together
- ✅ Assign signal from all linked CSVs simultaneously
- ✅ Link All / Unlink All buttons

---

## 4. CURSOR & INSPECTION

### 4.1 Interactive Cursor
- ✅ Enable/disable toggle
- ✅ Click to position
- ✅ Slider for fine control
- ✅ Jump-to-time input
- ✅ Dashed vertical line on plots

### 4.2 Cursor Values Panel
- ✅ Show values at cursor time
- ✅ Grouped by subplot
- ✅ Color-coded by signal
- ✅ Scope: Active subplot only / All subplots
- ✅ Time display

### 4.3 X-Y Mode Cursor
- ✅ Cursor shows X and Y values at same time
- ✅ Vertical line at X-value

---

## 5. COMPARISON

### 5.1 Single Signal Compare
- ✅ Select 2+ runs to compare
- ✅ Baseline method: Mean or Specific run
- ✅ Time alignment options
- ✅ RMS difference, correlation, percent deviation

### 5.2 Compare All Common Signals
- ✅ Auto-detect common signals across runs
- ✅ Rank by difference (largest first)
- ✅ Color-coded results (red/yellow/green)
- ✅ Sort options: by difference or name
- ✅ **Signal selection checkboxes**
- ✅ Create subplots for selected signals
- ✅ Export results as CSV

### 5.3 Delta Signal Generation
- ✅ Generate difference signals for all common
- ✅ Auto-named derived signals

---

## 6. REPORTING

### 6.1 Report Configuration
- ✅ Report title
- ✅ Introduction text (multi-line)
- ✅ Conclusion text (multi-line)
- ✅ RTL support (Hebrew/Arabic)
- ✅ Tab scope: Current tab or All tabs
- ✅ Per-subplot: title, caption, description

### 6.2 Export Formats
- ✅ HTML (offline, embedded Plotly)
- ✅ DOCX (Word document with images)

---

## 7. STREAMING

### 7.1 Live Data Mode
- ✅ Auto-refresh at configurable interval (0.5s-5s)
- ✅ Detect file changes
- ✅ Smart incremental refresh (append-only)
- ✅ Toggle on/off

---

## 8. UI/UX

### 8.1 Layout
- ✅ 3-column layout: Left sidebar, Center plot, Right panel
- ✅ Responsive to window resize
- ✅ Dark Bootstrap theme (Cyborg)

### 8.2 Header Toolbar
- ✅ Import, Refresh, Stream, Save, Load buttons
- ✅ Clear All button
- ✅ Report button
- ✅ Theme toggle

### 8.3 Plot Toolbar
- ✅ Row/Column selectors
- ✅ Subplot selector
- ✅ Subplot title input
- ✅ Time/X-Y mode toggle
- ✅ Cursor toggle
- ✅ Cursor scope (Active/All)
- ✅ Link Tab axes button
- ✅ Axis limits popover
- ✅ Clear dropdown (Current/All subplots)

### 8.4 Right Panel
- ✅ Cursor Values section
- ✅ Operations section (collapsible)
- ✅ Compare section (collapsible)

---

## 9. STATE SIGNALS

### 9.1 Visualization
- ✅ Vertical lines at state transitions (like MATLAB xline)
- ✅ Lines span full Y-axis
- ✅ State value annotations at top
- ✅ Warning for >100 transitions

---

## 10. TECHNICAL

### 10.1 Architecture
- ✅ Modular code structure (core, ui, viz, ops, compare, stream, report)
- ✅ Dash callbacks with pattern matching
- ✅ Global state management
- ✅ Debug logging flag

### 10.2 Build System
- ✅ PyInstaller spec file
- ✅ build.bat script (full, fast, run modes)
- ✅ Hooks for Plotly/Kaleido

---

# MISSING FEATURES (vs Competitors)

## High Priority

| Feature | Status | Competitor Has |
|---------|--------|----------------|
| FFT/Spectrum Analysis | ❌ Missing | multi-signal-visualizer |
| Region Selection | ❌ Missing | Real-Time-Signal-Viewer |
| Polar Plot | ❌ Missing | Real-Time-Signal-Viewer |
| Statistical Panel | ⚠️ Partial | Common |
| PDF Export | ❌ Missing | Live-Multichannel-Signal-Monitor |

## Medium Priority

| Feature | Status |
|---------|--------|
| Signal Annotations | ❌ Missing |
| Dual Y-Axis | ❌ Missing |
| Measurement Cursors (2-cursor delta) | ❌ Missing |
| Signal Filtering (low/high pass) | ❌ Missing |
| WFDB/EDF format support | ❌ Missing |

## Low Priority

| Feature | Status |
|---------|--------|
| Keyboard Shortcuts | ⚠️ Minimal |
| Drag-and-Drop Assignment | ❌ Missing |
| Undo/Redo | ❌ Missing |
| Color Palette Presets | ❌ Missing |

---

# DESIGN IMPROVEMENTS

## UI Modernization

| Area | Current | Suggested |
|------|---------|-----------|
| Signal Panel | Text list | Icons + color swatches |
| Subplot Selection | Dropdown | Click on plot to select |
| Legend | Plotly default | Custom interactive legend |
| Toolbar | All visible | Collapsible/grouped |
| Loading | No indicator | Spinner/progress |

## Performance

| Area | Current | Suggested |
|------|---------|-----------|
| Large files | Load all | Lazy loading |
| Many signals | Slow tree | Virtual scrolling |
| Figure updates | Full redraw | Incremental updates |

---

# COMPETITIVE ADVANTAGES

Features we have that competitors lack:
1. ✅ Multi-tab interface
2. ✅ Derived signals with chaining
3. ✅ State signal visualization
4. ✅ X-Y plotting mode
5. ✅ Run comparison workflow
6. ✅ Session persistence
7. ✅ Report generation
8. ✅ CSV rename/replace
9. ✅ Figure caching
10. ✅ Signal linking across CSVs
