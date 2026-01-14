# 🧠 CURSOR AI AGENT INSTRUCTIONS: Fix Remaining UX Bugs + Tabs + Reports + Compare Workflows (SDI-like)

## Context

The app currently implements:
- multi-subplots (grid)
- per-subplot cursor values panel
- time/X-Y mode toggle
- operations panel (derived signals in tree)
- compare panel (basic)
- multi-file import
- show all signals in tree
- remove run
- clear all / clear subplot

But there are many remaining issues and missing SDI-like workflows. This task is to fix them **without removing features** and to implement SDI-style “compare in new view/tab” and reporting.

Constraints:
- **Lossless** (no downsampling/resampling for visualization)
- **Offline** (no CDNs)
- Canonical naming everywhere: `signal — csv_display_name`
- Maintain stability: avoid regressions in existing working features.

---

## Acceptance Criteria (Hard)

Each numbered issue below must have:
- a fix
- a manual test step added to `docs/MANUAL_TESTS.md`
- no regression of existing functionality

---

## P0 — Critical UX Bugs (Fix first)

### 1) Run/CSV node collapse triangle does not work
**Requirement**
- Clicking the triangle must collapse/expand the signal list for that run.
- Must preserve scroll position when expanding.

**Implementation**
- Store collapsed state per run in a dedicated store, e.g. `collapsed_runs: {run_id: bool}`
- Render signals list conditionally.
- Triangle icon must toggle state reliably.

---

### 2) X-Y mode must align signals first
**Requirement**
- Before rendering X-Y, align chosen X signal time vector with each Y signal.
- Alignment method selector: `Nearest` / `Linear`
- Alignment must be explicit; no silent truncation.

**Implementation**
- Implement `align_two_signals(t_ref, y_ref, t_other, y_other, method)` returning y_other_on_ref
- For X-Y: choose X signal time as reference; align Y signals to X time; plot y_on_x vs x_values.
- If alignment fails (no overlap), show UI error message.

---

### 3) Layout dropdown too small; current subplot label confusing
**Requirement**
- Layout control must display rows×cols clearly and be readable.
- Current subplot dropdown must show `Subplot 1 / N` by default on app start (not blank).
- Increase width and font size slightly.

**Implementation**
- Ensure initial store values set `active_subplot=1`
- Ensure dropdown value is initialized, not set only after user interaction.

---

### 4) Save/Load session does not save layout
**Requirement**
Session must save/load:
- rows, cols
- active subplot
- assignments per subplot
- per-subplot mode (Time/X-Y)
- X selection per subplot (for X-Y)
- derived signals
- run collapse states (optional)

Add schema versioning if needed.

---

### 5) Loading CSV automatically assigns a signal to Subplot 1 (must not)
**Requirement**
After import, no signals should be assigned automatically.
User must explicitly assign.

---

### 6) Switching current subplot clears its signals (bug)
**Requirement**
Changing active subplot must not alter assignments.
Assignments must be stable and persistent.

---

### 8) Derived signals removal controls missing
**Requirement**
- Provide:
  - “Remove derived signal” (per derived item)
  - “Clear all derived signals”
- Removing derived signals must:
  - remove from tree
  - remove from subplot assignments
  - remove dependent derived signals (or warn user)

---

### 9) Report button does not work
**Requirement**
Report button must open Report Builder modal and export offline HTML.

---

### 10) Per-subplot Title/Caption/Description for report
**Requirement**
For each subplot, user can set:
- Title (short)
- Caption (short)
- Description (multi-line)

UI placement:
- In **Assigned** panel under each subplot section.

Persist in session and include in report export.

---

### 11) Cursor Values alignment issue (value not aligned with label)
**Requirement**
In Cursor Values panel, each row must align:
- left: signal name
- right: numeric value
Same baseline/height.

Implementation:
- Use a 2-column flex row with fixed alignment, monospace for values.

---

### 12) Time/X-Y toggle UI state mismatch
**Requirement**
When user selects X-Y mode:
- Time button must visually turn off
- X-Y must be visually selected
No dual-selection.

Implementation:
- Ensure single source of truth store: `subplot_mode[i] in {"time","xy"}` and render buttons from it.

---

### 13) X-Y UI: only pick X; Y chosen by assigning signals
**Requirement**
In X-Y mode:
- user chooses **only X signal** from dropdown
- Y signals come from Assigned list (like Time mode)
- i.e., assignment mechanism stays the same, but x-axis changes to X

Implementation:
- Remove “Y dropdown” from X-Y settings
- Render help text: “Assign Y signals normally; choose X here.”

---

### 14) Report modal must support Title + Introduction + Summary (Hebrew supported)
**Requirement**
Report Builder modal must include:
- Report Title (string)
- Introduction (multi-line, Hebrew supported)
- Summary/Conclusion (multi-line, Hebrew supported)

Implementation:
- Ensure UTF-8 everywhere.
- HTML export must embed text correctly with RTL support:
  - Add CSS direction option per field or global RTL toggle.
  - At minimum: if Hebrew detected or RTL toggle enabled, wrap text blocks with `dir="rtl"`.

---

### 15) Refresh must re-read CSV and reconcile signals + operations
**Requirement**
Refresh must:
- re-read each CSV file from disk
- detect added/removed columns/signals
- update tree + assignments
- update derived signals:
  - re-compute if inputs still exist
  - mark broken if missing inputs (do not crash)
- preserve user settings where possible (colors, offsets, state flags)

---

### 18) Replace “Stream panel” with a Smart Incremental Refresh button
**Requirement**
Instead of streaming panel:
- Provide button: `Smart Refresh`
- It must update large CSV efficiently by reading only appended lines:
  - store file offset / last row count / last mtime
  - on click, if file grew, append new rows
  - if file rewritten (mtime changed but size smaller), full reload with warning

Must update plots and derived signals incrementally.

---

### 19) Cursor “All/Active” selector styling must match Time/X-Y (square buttons)
**Requirement**
Replace the small toggle icon with square segmented buttons:
- `Active subplot`
- `All subplots`

Must match Time/X-Y style.

---

## P1 — Tabs (Views) System (Missing)

### 4) Add/Remove plot tabs (must exist)
**Requirement**
Implement SDI-like views as tabs:
- Add Tab
- Rename Tab
- Remove Tab (disabled if only 1)
Each tab has its own:
- layout (rows, cols)
- assignments
- per-subplot mode (time/xy)
- per-subplot metadata (title/caption/description)
- compare results (if opened in that tab)

Session must persist tabs.

---

## P2 — Compare Workflows (SDI-like) (Major)

### 16) Compare a signal across 2+ runs → open a new Compare tab
**Requirement**
When user compares a signal:
- Open a NEW tab named like: `Compare: <signal>`
- Layout must be 2×1:
  - Subplot 1: overlay of all selected runs for that signal
  - Subplot 2: difference vs baseline (baseline selectable)
Support >2 CSVs if same signal name exists:
- overlay all
- diffs computed vs baseline for each

Compare UI must allow selecting:
- baseline run
- additional runs (multi-select)
- alignment method (linear/nearest)
- time range mode (overlap/union)

---

### 17) Compare entire CSVs (2+ runs) → new tab with ranking by dissimilarity
**Requirement**
Implement “Compare Runs” mode:
- User selects 2+ runs
- System computes similarity for all common signals:
  - metric: RMS diff or max abs diff after alignment
- Create a new tab: `Compare Runs: A vs B (+n)`
Tab layout:
- Left list (ranked table) of common signals by dissimilarity (descending)
- Clicking a signal row:
  - Subplot 1: overlay that signal across runs
  - Subplot 2: diff vs baseline
- Multi-select signals in table:
  - overlay multiple signals (or open multiple subplots) — choose one consistent design and document.

Design requirement: keep it visually clean (SDI-like), no clutter.

---

## Implementation Order (Must Follow)

1) Fix collapse triangle (1)
2) Fix subplot/layout dropdown UX + default active subplot (3)
3) Stop auto-assign on import (5)
4) Fix “switch subplot clears signals” (6)
5) Fix toggle UI state mismatch (12) + cursor toggle style (19)
6) Cursor values per subplot layout alignment (11)
7) X-Y alignment engine (2) + X-only selection UX (13)
8) Save/Load includes layout + modes + tab state (4)
9) Derived signal remove controls (8)
10) Report builder works + per-subplot metadata + RTL Hebrew support (9,10,14)
11) Refresh full reload + reconcile + derived dependency handling (15)
12) Smart incremental refresh replaces stream panel (18)
13) Implement tabs system (P1)
14) Compare signal → new compare tab (16)
15) Compare runs → ranking tab + clickable signals (17)

After each step:
- app runs
- add manual test steps to docs
- no regression of existing working features

---

## Deliverables

- Fixed UX issues and bugs listed above
- Tabs system with persistence
- Report builder working (offline HTML), with Hebrew/RTL option
- Smart incremental refresh
- SDI-like compare workflows implemented via new tabs
- Updated `docs/MANUAL_TESTS.md` covering all items
- Updated `docs/COMPARE.md` and `docs/REPORTS.md`

---

## Definition of Done

Done only when:
- Collapse works
- X-Y works with proper alignment and X-only picker
- Subplot switching preserves assignments
- Sessions save/load layout and tabs
- Derived signals can be removed individually or all
- Report export works, supports Hebrew and includes per-subplot metadata
- Refresh and Smart Refresh update signals and derived ops correctly
- Compare creates new tabs (signal compare and run compare ranking)
