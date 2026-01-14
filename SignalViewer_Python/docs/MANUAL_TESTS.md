# Manual Test Script — Signal Viewer Pro

This document provides step-by-step test cases for validating Signal Viewer Pro functionality.

---

## Test 1: CSV Import Variants

### 1.1 Standard CSV with Header
**Setup:** Create `test_standard.csv`:
```csv
Time,Speed,Temperature
0.0,0,25.0
0.1,10,25.1
0.2,20,25.2
```

**Steps:**
1. Click "📂 Import"
2. Browse to file
3. Keep "Has Header Row" checked
4. Click "Import"

**Expected:**
- [ ] File appears in Runs panel as "test_standard.csv"
- [ ] Signals "Speed" and "Temperature" appear in tree
- [ ] Preview shows correct data

### 1.2 Headerless CSV
**Setup:** Create `test_noheader.csv`:
```
0.0,100,200
0.1,110,210
0.2,120,220
```

**Steps:**
1. Click "📂 Import"
2. Uncheck "Has Header Row"
3. Set Time Column to "Col0"
4. Click "Import"

**Expected:**
- [ ] Signals named "Col1", "Col2" appear
- [ ] Time axis uses first column

### 1.3 Header at Row 3
**Setup:** Create `test_headerrow3.csv`:
```
# Test data file
# Created: 2024-01-01
# 
Time,Signal1,Signal2
0.0,1.0,2.0
0.1,1.1,2.1
```

**Steps:**
1. Click "📂 Import"
2. Set "Header Row" to 3
3. Set "Skip Rows" to 3
4. Click "Import"

**Expected:**
- [ ] Header correctly parsed from row 3
- [ ] Data starts from row 4

### 1.4 Semicolon Delimiter
**Setup:** Create `test_semicolon.csv`:
```
Time;Pressure;Flow
0.0;101.3;5.0
0.1;101.2;5.1
```

**Steps:**
1. Click "📂 Import"
2. Set Delimiter to "Semicolon (;)"
3. Click "Import"

**Expected:**
- [ ] Columns correctly split
- [ ] Signals "Pressure" and "Flow" appear

---

## Test 2: Subplot Selection & Assignment

### 2.1 Multi-Subplot Layout
**Steps:**
1. Load a CSV with multiple signals
2. Set Layout to 2×2
3. Select Subplot 1 (default)
4. Click on "Speed" signal

**Expected:**
- [ ] 4 subplots visible
- [ ] Subplot 1 highlighted with blue border
- [ ] "Speed" appears in Assigned panel

### 2.2 Switch Subplot
**Steps:**
1. With signals assigned to Subplot 1
2. Select Subplot 2 from dropdown
3. Assign different signals

**Expected:**
- [ ] Subplot 2 now highlighted
- [ ] Assigned panel updates to show Subplot 2 signals
- [ ] Both subplots show their respective signals

### 2.3 Remove Signal
**Steps:**
1. Assign multiple signals
2. Click "×" next to a signal in Assigned panel

**Expected:**
- [ ] Signal removed from Assigned panel
- [ ] Signal removed from plot
- [ ] Signal still available in tree

---

## Test 3: Cursor Inspector

### 3.1 Enable Cursor
**Steps:**
1. Load CSV and assign signals
2. Enable "Cursor" switch

**Expected:**
- [ ] Cursor controls appear (slider, play buttons)
- [ ] Vertical cursor line on plot
- [ ] Inspector panel shows values

### 3.2 Move Cursor
**Steps:**
1. With cursor enabled
2. Drag slider to middle of data

**Expected:**
- [ ] Cursor line moves
- [ ] Time display updates (T = X.XXXX)
- [ ] Inspector values update to match cursor position

### 3.3 Cursor on Multiple Subplots
**Steps:**
1. Create 2×1 layout
2. Assign signals to both subplots
3. Enable cursor

**Expected:**
- [ ] Cursor line appears on ALL subplots
- [ ] Values shown for all visible signals

---

## Test 4: Signal Operations

### 4.1 Unary Operation (Derivative)
**Steps:**
1. Assign a signal
2. Open Operations panel
3. Select "Unary"
4. Select "Derivative"
5. Click "Apply"

**Expected:**
- [ ] New signal appears: "derivative(signal_name)"
- [ ] Listed under "Derived" in tree
- [ ] Can be assigned to subplot

### 4.2 Binary Operation (A + B)
**Steps:**
1. Assign two signals to same subplot
2. Open Operations panel
3. Select "Binary"
4. Select "+"
5. Click "Apply"

**Expected:**
- [ ] New signal: "Signal1 + Signal2"
- [ ] Correct sum values

### 4.3 Different Time Bases
**Steps:**
1. Load two CSVs with different sample rates
2. Apply binary operation between them
3. Set Alignment to "Linear interpolation"

**Expected:**
- [ ] Operation completes without error
- [ ] Result uses denser time base

---

## Test 5: X-Y Mode

### 5.1 Enable X-Y Mode
**Steps:**
1. Assign signals Speed and Temperature
2. Select "X-Y" radio button

**Expected:**
- [ ] X signal selector appears
- [ ] Y signals list appears
- [ ] Plot changes to X-Y view

### 5.2 X-Y Plot
**Steps:**
1. Set X = Speed
2. Set Y = Temperature

**Expected:**
- [ ] Plot shows Temperature vs Speed
- [ ] Not vs Time

---

## Test 6: Compare Mode

### 6.1 Compare Runs
**Setup:** Load two CSVs with same signal names

**Steps:**
1. Open Compare panel
2. Select Baseline Run
3. Select Compare-To Run
4. Select Signal
5. Click "Compare"

**Expected:**
- [ ] Overlay plot appears
- [ ] Delta shown
- [ ] Metrics displayed (RMS, max diff, correlation)

### 6.2 Different Time Bases
**Steps:**
1. Load CSVs with different lengths/rates
2. Set Sync Method to "Intersection only"
3. Compare

**Expected:**
- [ ] Only overlapping region compared
- [ ] No errors from length mismatch

---

## Test 7: Streaming

### 7.1 Enable Streaming
**Steps:**
1. Load a CSV that will be appended externally
2. Open Stream panel
3. Enable "Enable Streaming"

**Expected:**
- [ ] Status shows "Watching..."
- [ ] No errors

### 7.2 Append Data
**Steps:**
1. While streaming, append rows to CSV externally
2. Wait for update interval

**Expected:**
- [ ] New data appears on plot
- [ ] Row count updates

### 7.3 Time Span
**Steps:**
1. Set Time Span to 10 seconds
2. Data should scroll to show last 10s

**Expected:**
- [ ] X-axis shows only last 10 seconds
- [ ] Earlier data scrolls off

---

## Test 8: Report Export

### 8.1 Generate Report
**Steps:**
1. Load data, assign signals
2. Click "📊 Report"
3. Enter Title and Introduction
4. Click "Export HTML"

**Expected:**
- [ ] HTML file downloaded
- [ ] Opens in browser offline
- [ ] Contains title, intro, plots

---

## Test 9: Session Save/Load

### 9.1 Save Session
**Steps:**
1. Load multiple CSVs
2. Create 2×2 layout
3. Assign various signals
4. Click "💾 Save"

**Expected:**
- [ ] JSON file downloaded
- [ ] Contains all paths, assignments

### 9.2 Load Session
**Steps:**
1. Clear app (refresh page)
2. Click "📁 Load"
3. Select saved session

**Expected:**
- [ ] All CSVs reloaded (if paths valid)
- [ ] Layout restored
- [ ] Assignments restored

---

## Test 10: Canonical Naming (N1-N4)

### 10.1 Same Signal, Different CSVs
**Setup:** Two CSVs with signal named "RPM"

**Expected:**
- [ ] Legend shows: "RPM — csv1" and "RPM — csv2"
- [ ] Assigned panel shows same format

### 10.2 Same Filename, Different Folders
**Setup:** `run1/data.csv` and `run2/data.csv`

**Expected:**
- [ ] Runs panel shows: "run1/data.csv", "run2/data.csv"
- [ ] Signal labels include folder prefix

---

## Test 11: MULTI_SUBPLOTS (task.md A1-A4)

### 11.1 True Grid Rendering (A1)
**Steps:**
1. Load a CSV with multiple signals
2. Set Rows to 2
3. Set Cols to 2

**Expected:**
- [ ] **4 separate subplots** visible with distinct axes/gridlines
- [ ] NOT a single plot with internal divisions
- [ ] Each subplot has its own x-axis (shared) and y-axis
- [ ] Figure height increases to accommodate rows (~700px for 1 row, ~1020px for 2 rows)

**Console verification:**
```
[LAYOUT] Changed to 2x2 = 4 subplots
[FIGURE] Building figure: 2x2 = 4 subplots, active=0
[FIGURE] Traces per subplot: {0: N, 1: 0, 2: 0, 3: 0}
```

### 11.2 Independent Subplot Assignment (A2)
**Steps:**
1. With 2×2 grid visible
2. Select "Subplot 1" (dropdown)
3. Click on "Speed" signal
4. Select "Subplot 3" (dropdown)
5. Click on "Temperature" signal

**Expected:**
- [ ] Speed trace appears ONLY in subplot 1 (top-left)
- [ ] Temperature trace appears ONLY in subplot 3 (bottom-left)
- [ ] Other subplots remain empty
- [ ] Assigned panel updates when switching subplot selection

**Console verification:**
```
[FIGURE] Traces per subplot: {0: 1, 1: 0, 2: 1, 3: 0}
```

### 11.3 Active Subplot Selection (A3)
**Steps:**
1. With 2×2 grid
2. Select "Subplot 2" from dropdown

**Expected:**
- [ ] Subplot 2 (top-right) shows **blue accent border** (thicker, highlighted)
- [ ] "⬤ Subplot 2" label appears in top-left corner of that subplot
- [ ] Other subplots have normal gray border
- [ ] Assigned panel title shows "Subplot 2"

**Console verification:**
```
[SUBPLOT] Active subplot changed to 1
```

### 11.4 Layout Change Preserves Assignments (A4)
**Steps:**
1. With 2×2 grid, assign signals to subplot 4 (bottom-right)
2. Change Cols to 1 (now 2×1 = 2 subplots)
3. Check subplot 2

**Expected:**
- [ ] Grid changes to 2 rows × 1 column
- [ ] Orphan signals from subplot 4 are moved to subplot 2 (last valid)
- [ ] No signals lost
- [ ] Active subplot clamped to valid range

**Console verification:**
```
[LAYOUT] Orphan signals moved to subplot 2
[LAYOUT] Selector updated: 2 options, selected=1
```

### 11.5 Subplot Index Mapping Verification
**Steps:**
1. Set layout to 3×2 (3 rows, 2 cols = 6 subplots)
2. Verify subplot positions:

**Expected mapping:**
| Index | Row | Col | Position |
|-------|-----|-----|----------|
| 0 | 1 | 1 | top-left |
| 1 | 1 | 2 | top-right |
| 2 | 2 | 1 | middle-left |
| 3 | 2 | 2 | middle-right |
| 4 | 3 | 1 | bottom-left |
| 5 | 3 | 2 | bottom-right |

- [ ] Assigning to subplot 3 places trace in middle-right position
- [ ] Cursor line appears on all 6 subplots when enabled

---

## Test 12: Cursor Values Panel (Per Subplot)

### 12.1 Grouped Values Display
**Steps:**
1. Load CSV and create 2×1 layout
2. Assign different signals to Subplot 1 and Subplot 2
3. Enable Cursor
4. Move cursor slider

**Expected:**
- [ ] Cursor Values panel shows "T = X.XXXX" at top
- [ ] Values grouped by "Subplot 1" and "Subplot 2" headers
- [ ] Each signal shows color dot, label, and value
- [ ] Active subplot header highlighted in blue

### 12.2 Toggle Active Only
**Steps:**
1. With values showing for both subplots
2. Toggle "All" switch off in Cursor Values panel header

**Expected:**
- [ ] Only active subplot's values shown
- [ ] Toggle on shows all subplots again

---

## Test 13: X-Y Mode

### 13.1 Enable X-Y Mode
**Steps:**
1. Assign signals to a subplot
2. Click "🔀 X-Y" mode button

**Expected:**
- [ ] X-Y controls appear below assigned list
- [ ] X signal dropdown populated with all signals
- [ ] Y signals dropdown (multi-select) populated

### 13.2 X-Y Plot
**Steps:**
1. Select X signal
2. Select one or more Y signals

**Expected:**
- [ ] Plot changes to X vs Y scatter
- [ ] Console shows: `[X-Y] Subplot 0: X=..., Y=[...]`

---

## Test 14: Operations Panel

### 14.1 Unary Operation
**Steps:**
1. Open Operations panel (click ▼)
2. Select "Unary (1)" type
3. Select one signal from dropdown
4. Select "Derivative (d/dt)"
5. Click "Create Derived Signal"

**Expected:**
- [ ] Status shows "✅ Created: d(signal)/dt"
- [ ] Signal tree shows "Derived" section with new signal
- [ ] Derived signal can be assigned to subplot

### 14.2 Binary Operation
**Steps:**
1. Select "Binary (2)" type
2. Select exactly 2 signals
3. Select "A − B"
4. Click "Create Derived Signal"

**Expected:**
- [ ] Status shows success
- [ ] Derived signal appears in tree

---

## Test 15: Compare Panel

### 15.1 Compare Two Runs
**Steps:**
1. Load two CSVs with same signal name
2. Open Compare panel
3. Select Run A, Run B
4. Select common signal
5. Click "Compare"

**Expected:**
- [ ] Results show Max |Δ|, RMS Δ, Correlation
- [ ] Delta signal created in Derived section
- [ ] Console shows comparison metrics

---

## Test 16: Multi-File Import

### 16.1 Import Multiple Files
**Steps:**
1. Click "📂 Import"
2. In file dialog, select multiple CSV files (Ctrl+click)
3. Click "Import"

**Expected:**
- [ ] Preview shows "Selected N file(s):" with list
- [ ] All files appear in Runs panel after import
- [ ] Console shows: `[IMPORT] Loaded N file(s)`

---

## Test 17: Signal Tree & Run Management

### 17.1 Full Signal List
**Steps:**
1. Load CSV with 50+ signals

**Expected:**
- [ ] All signals shown (no "... +N more" truncation)
- [ ] Scrollable container for long lists

### 17.2 Remove Run
**Steps:**
1. Load multiple CSVs
2. Click "×" next to a run in Signals panel

**Expected:**
- [ ] Run removed from tree
- [ ] Assignments referencing that run cleared
- [ ] Console shows: `[REMOVE] Removed run: ...`

---

## Test 18: Clear Controls

### 18.1 Clear Subplot
**Steps:**
1. Assign signals to multiple subplots
2. Select Subplot 2
3. Click "🗑️ Clear" in toolbar

**Expected:**
- [ ] Only Subplot 2 assignments cleared
- [ ] Other subplots unchanged

### 18.2 Clear All
**Steps:**
1. Load CSVs, create derived signals, make assignments
2. Click "🗑️ Clear All" in header

**Expected:**
- [ ] All runs removed
- [ ] All derived signals removed
- [ ] All assignments cleared
- [ ] Console shows: `[CLEAR ALL] Reset to initial state`

---

## Acceptance Criteria Summary

For release, ALL tests must pass:
- [ ] All 18 test sections completed
- [ ] **MULTI_SUBPLOTS (Test 11) all checkboxes pass**
- [ ] **NEW FEATURES (Tests 12-18) all checkboxes pass**
- [ ] No console errors during tests
- [ ] App remains responsive
- [ ] Offline operation verified (disconnect internet)
- [ ] Large CSV (1M+ rows) renders without crash

---

## Test 19: Collapse Triangle (P0-1)

### 19.1 Collapse Run Signals
**Steps:**
1. Load a CSV with signals
2. Click the triangle (▼) next to the run name

**Expected:**
- [ ] Triangle changes to (▶)
- [ ] Signal list collapses/hides
- [ ] Click again to expand

---

## Test 20: X-Y Mode - Y from Assigned (P0-13)

### 20.1 X-Y Uses Assigned Signals for Y
**Steps:**
1. Assign multiple signals to a subplot
2. Switch to X-Y mode
3. Select X signal from dropdown

**Expected:**
- [ ] Help text: "Y signals: Assign signals normally in the list above"
- [ ] All assigned signals (except X) become Y signals
- [ ] Plot shows Y signals vs X signal

---

## Test 21: Derived Signal Removal (P0-8)

### 21.1 Remove Single Derived
**Steps:**
1. Create a derived signal (e.g., derivative)
2. Click "×" next to the derived signal in tree

**Expected:**
- [ ] Derived signal removed from tree
- [ ] Removed from assignments
- [ ] Dependent derived signals also removed

### 21.2 Clear All Derived
**Steps:**
1. Create multiple derived signals
2. Click "Clear All" button in Derived section

**Expected:**
- [ ] All derived signals removed
- [ ] Assignments updated

---

## Test 22: Report Builder (P0-9, P0-14)

### 22.1 Export HTML Report
**Steps:**
1. Assign signals to subplots
2. Click "📊 Report"
3. Enter Title, Introduction, Conclusion
4. Click "Export"

**Expected:**
- [ ] HTML file downloaded
- [ ] Opens offline in browser
- [ ] Contains title, intro, plots, conclusion

### 22.2 RTL/Hebrew Support
**Steps:**
1. Open Report modal
2. Enable "Right-to-Left" toggle
3. Enter Hebrew text in Introduction
4. Export HTML

**Expected:**
- [ ] HTML has dir="rtl"
- [ ] Hebrew text displays correctly

---

## Test 23: Smart Refresh (P0-18)

### 23.1 Incremental Append Detection
**Steps:**
1. Load a CSV
2. Open Smart Refresh panel
3. Externally append rows to CSV
4. Click "🔄 Smart Refresh"

**Expected:**
- [ ] Status shows "N updated"
- [ ] New data appears on plot
- [ ] Only new rows were read (efficient)

### 23.2 File Rewrite Detection
**Steps:**
1. Load a CSV
2. Externally rewrite CSV (smaller size)
3. Click "🔄 Smart Refresh"

**Expected:**
- [ ] Status shows "N reloaded"
- [ ] Full reload performed
- [ ] Data refreshed correctly

---

## Test 24: Tab System (P1)

### 24.1 Add Tab
**Steps:**
1. Click "+ Tab" button

**Expected:**
- [ ] New tab appears in tab bar
- [ ] New tab becomes active
- [ ] Layout resets for new tab

### 24.2 Switch Tab
**Steps:**
1. Create multiple tabs
2. Click on a different tab

**Expected:**
- [ ] Tab becomes active (highlighted)
- [ ] Plot shows that tab's data

### 24.3 Close Tab
**Steps:**
1. Create multiple tabs
2. Click "×" next to a non-main tab

**Expected:**
- [ ] Tab removed
- [ ] If active tab closed, switch to first tab
- [ ] Main tab cannot be closed

---

## Test 25: Session Save/Load with Layout (P0-4)

### 25.1 Session Includes Layout
**Steps:**
1. Create 2×2 layout
2. Assign signals to multiple subplots
3. Set subplot modes (Time/X-Y)
4. Save session
5. Reload page
6. Load session

**Expected:**
- [ ] Layout restored (2×2)
- [ ] Assignments restored per subplot
- [ ] Modes restored (Time/X-Y)
- [ ] Cursor settings restored

---

## Acceptance Criteria Summary

For release, ALL tests must pass:
- [ ] All 25 test sections completed
- [ ] **MULTI_SUBPLOTS (Test 11) all checkboxes pass**
- [ ] **P0 Fixes (Tests 19-25) all checkboxes pass**
- [ ] No console errors during tests
- [ ] App remains responsive
- [ ] Offline operation verified (disconnect internet)
- [ ] Large CSV (1M+ rows) renders without crash

---

*Last updated: Full P0-P1 Implementation + Manual Tests*

