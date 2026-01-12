# Features from Original Signal Viewer Pro

## Complete Feature Analysis
Extracted from the original 9700+ line app.py

---

## 🔴 CORE FEATURES (Must Have - Phase 1)

### 1. CSV File Management
- [x] Load multiple CSV files via native file dialog
- [x] Auto-detect CSV delimiter (comma, semicolon, tab)
- [x] Auto-detect header row
- [x] Display loaded CSV list with file info
- [x] Remove individual CSV from list
- [x] Clear all CSVs (without affecting other CSVs' signals)
- [ ] Handle duplicate file names (show parent folder)
- [ ] Refresh CSV (reload from disk)

### 2. Signal Tree View
- [x] Display signals grouped by CSV file
- [x] Search/filter signals by name
- [x] Checkbox sync with assignments (two-way binding)
- [ ] Collapsible CSV sections
- [x] Show signal count per CSV
- [x] Highlight assigned signals differently

### 3. Signal Assignment
- [x] Assign signals to subplots via checkbox
- [x] Proper sync: check in tree → add to assigned
- [x] Proper sync: uncheck in tree → remove from assigned  
- [x] Proper sync: remove from assigned → uncheck in tree
- [x] Track by unique key: `{csv_id}:{signal_name}`
- [x] Support multiple subplots per tab

### 4. Plot Display
- [x] Single Plotly graph with subplots
- [x] Legend PER SUBPLOT (grouped by subplot)
- [x] Auto-color assignment for signals
- [x] Hover info with signal values
- [x] Subplot title/label
- [x] Selected subplot highlight (border)

### 5. Layout Control
- [x] Grid selector (rows × columns)
- [x] Subplot selector dropdown
- [ ] Double-click subplot to select
- [x] Update subplot options when grid changes

---

## 🟡 IMPORTANT FEATURES (Phase 2)

### 6. Time Cursor
- [x] Vertical cursor line on plot
- [x] Slider to control cursor position
- [x] Play/Stop animation
- [x] Display signal values AT cursor position
- [x] Click on plot to set cursor
- [x] Cursor visible in all subplots (synced)

### 7. Theme Support
- [x] Dark/Light theme toggle
- [x] CSS variables for theming
- [ ] Persist theme preference

### 8. Multi-Tab Support
- [ ] Create new tabs
- [ ] Delete tabs
- [ ] Rename tabs
- [ ] Each tab has independent:
  - Layout (rows × cols)
  - Assignments
  - Selected subplot

---

## 🟢 ADVANCED FEATURES (Phase 3)

### 9. Signal Properties
- [ ] Change signal color
- [ ] Change line width
- [ ] Custom display name
- [ ] Scale factor
- [ ] Time offset per signal

### 10. Derived Signals
- [ ] Derivative calculation
- [ ] Integral calculation
- [ ] Scale by constant
- [ ] Custom math expressions
- [ ] Multi-signal operations (avg, sum, diff)

### 11. X-Y Plot Mode
- [ ] Switch subplot to X-Y mode
- [ ] Select X-axis signal (not time)
- [ ] Correlation analysis

### 12. Session Management
- [x] Save session to JSON
- [x] Load session from JSON
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

## 🔵 EXPORT FEATURES (Phase 4)

### 15. Export Options
- [ ] Export plot as PNG/SVG
- [ ] Export data to CSV
- [ ] Export HTML report
- [ ] Export Word document
- [ ] Include subplot titles/descriptions

---

## 🟣 STREAMING FEATURES (Phase 5)

### 16. Live Data
- [ ] Monitor CSV for changes
- [ ] Auto-refresh on file modification
- [ ] Streaming mode indicator

---

## ✅ BUGS FIXED (v4.0.1)

1. ✅ Signals now properly sync between tree and assigned panel
2. ✅ Removing from assigned unchecks in tree
3. ✅ Clearing CSV only removes that CSV's signals
4. ✅ Legend is now grouped per subplot


