# Features from Original Signal Viewer Pro

## Complete Feature Analysis
Extracted from the original 9700+ line app.py

---

## 🔴 CORE FEATURES (Must Have - Phase 1) ✅ COMPLETE

### 1. CSV File Management
- [x] Load multiple CSV files via native file dialog
- [x] Auto-detect CSV delimiter (comma, semicolon, tab)
- [x] Auto-detect header row
- [x] Display loaded CSV list with file info
- [x] Remove individual CSV from list
- [x] Clear all CSVs (without affecting other CSVs' signals)
- [x] Handle duplicate file names (show parent folder)
- [ ] Refresh CSV (reload from disk)

### 2. Signal Tree View
- [x] Display signals grouped by CSV file
- [x] Search/filter signals by name
- [x] Checkbox sync with assignments (two-way binding)
- [x] Collapsible CSV sections
- [x] Show signal count per CSV
- [x] Highlight assigned signals differently
- [x] Autocomplete search suggestions

### 3. Signal Assignment
- [x] Assign signals to subplots via checkbox
- [x] Proper sync: check in tree → add to assigned
- [x] Proper sync: uncheck in tree → remove from assigned  
- [x] Proper sync: remove from assigned → uncheck in tree
- [x] Track by unique key: `{csv_id}:{signal_name}`
- [x] Support multiple subplots per tab

### 4. Plot Display
- [x] Single Plotly graph with subplots
- [x] Legend per signal (click toggles individual signal)
- [x] Auto-color assignment for signals
- [x] Hover info with signal values
- [x] Subplot title/label
- [x] Selected subplot highlight (border)
- [x] Unique legend names for duplicate signals (CSV prefix)

### 5. Layout Control
- [x] Grid selector (rows × columns)
- [x] Subplot selector dropdown
- [ ] Double-click subplot to select
- [x] Update subplot options when grid changes

---

## 🟡 IMPORTANT FEATURES (Phase 2) ✅ COMPLETE

### 6. Time Cursor
- [x] Vertical cursor line on plot
- [x] Slider to control cursor position (ACTUAL TIME VALUES)
- [x] Play/Stop animation
- [x] Display signal values AT cursor position
- [x] Click on plot to set cursor
- [x] Cursor visible in all subplots (synced)
- [x] Cursor value annotations on plot

### 7. Theme Support
- [x] Dark/Light theme toggle
- [x] CSS variables for theming
- [ ] Persist theme preference

### 8. Multi-Tab Support
- [ ] Create new tabs
- [ ] Delete tabs
- [ ] Rename tabs
- [ ] Each tab has independent layout/assignments

---

## 🟢 ADVANCED FEATURES (Phase 3) ✅ COMPLETE

### 9. Signal Properties
- [x] Change signal color
- [x] Change line width
- [x] Custom display name
- [x] Scale factor
- [x] Offset per signal

### 10. Derived Signals
- [x] Derivative calculation
- [x] Integral calculation
- [x] Scale by constant
- [x] Offset by constant
- [x] Absolute value
- [x] Negative (invert)
- [x] Sum of two signals
- [x] Difference of two signals
- [x] Product of two signals
- [x] Ratio of two signals

### 11. X-Y Plot Mode
- [x] Switch subplot to X-Y mode
- [x] Select X-axis signal (not time)
- [x] Correlation analysis

### 12. Session Management
- [x] Save session to JSON
- [x] Load session from JSON
- [x] Save signal properties in session
- [ ] Auto-save on exit
- [ ] Recent sessions list

### 13. Template System
- [ ] Save layout as template
- [ ] Load template
- [ ] Apply to current tab

### 14. CSV Settings
- [ ] Select time column per CSV
- [ ] Set time offset per CSV
- [ ] Configure header row
- [ ] Configure delimiter

---

## 🔵 EXPORT FEATURES (Phase 4) ✅ COMPLETE

### 15. Export Options
- [x] Export plot as PNG (via Plotly toolbar)
- [x] Export data to CSV
- [x] Export HTML report (interactive)
- [ ] Export SVG
- [ ] Export PDF
- [ ] Include subplot titles/descriptions

---

## 🟣 STREAMING FEATURES (Phase 5) - DEFERRED

### 16. Live Data
- [ ] Monitor CSV for changes
- [ ] Auto-refresh on file modification
- [ ] Streaming mode indicator

---

## ✅ BUGS FIXED (v4.0.2)

1. ✅ Legend click toggles individual signal (not subplot group)
2. ✅ Signals with same name show CSV context in legend
3. ✅ CSVs with same name show parent folder
4. ✅ Cursor values annotated on plot at cursor position
5. ✅ Signal properties modal (color, width, scale, offset)
6. ✅ Derived signals (derivative, integral, math operations)
7. ✅ X-Y plot mode toggle
8. ✅ Export to CSV with time/interpolation options
9. ✅ Export to interactive HTML
10. ✅ Autocomplete search suggestions

---

## 📊 Code Metrics

### Original App (app.py)
- ~9,700 lines
- 77+ callbacks
- Single monolithic file
- Complex caching logic

### New App (v4)
- ~1,400 lines total
- 15 callbacks
- 6 modular files
- Clean separation of concerns

### File Structure
```
v4/
├── app.py          (~30 lines)   - Entry point
├── config.py       (~50 lines)   - Constants
├── state.py        (~30 lines)   - State utilities
├── data_manager.py (~280 lines)  - Data handling
├── plot_builder.py (~320 lines)  - Figure creation
├── layout.py       (~350 lines)  - UI components
├── callbacks.py    (~700 lines)  - All interactivity
└── assets/
    └── styles.css  (~500 lines)  - Styling
```
