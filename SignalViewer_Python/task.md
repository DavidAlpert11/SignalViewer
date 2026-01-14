# 🧠 AI Agent Task: Modernizing & UX-Polishing Signal Viewer Pro (Lossless, Offline)

## Introduction

You are working on an **existing, mature, feature-rich Dash application** called **Signal Viewer Pro**.  
This is **not a greenfield project**.

The goal is to **refactor, simplify, and modernize the user experience and internal structure** of the existing app **without breaking its core strengths**:

- Lossless signal visualization (no downsampling)
- Offline-only operation
- Support for very large CSV files
- Power-user analytical workflows

You must treat the current application as a **production engineering tool**, not a demo.

Your task is to **incrementally improve clarity, usability, maintainability, and visual polish**, while preserving all critical analytical functionality.

Reference implementation file: `app.py`. :contentReference[oaicite:0]{index=0}

---

## Non-Negotiable Constraints

### C1 — Lossless Data Handling
- Do **not** introduce downsampling, resampling, LTTB, or data reduction.
- All visualized points must correspond to real samples.
- Any performance improvements must be architectural or UI-level, not data-altering.

### C2 — Offline-First
- No external CDNs.
- All CSS/JS assets must remain local.
- App must run without internet access.

### C3 — Modify, Don’t Replace
- You must work **within the existing architecture** (`app.py`, `DataManager`, signal ops, etc.).
- Refactor only where it improves clarity or separation of concerns.
- Avoid breaking existing session files or user workflows.

---

## Naming & Disambiguation Requirements (Mandatory)

### N1 — Disambiguate Same Signal Names Across CSVs (Plot + UI)
When the **same signal name appears in different CSV files**, it must be displayed with a CSV identifier everywhere a user sees the signal:

- Plot legends
- Assigned list
- Signal tree labels (at least in tooltip; preferably in-line when needed)
- Export outputs (CSV export column naming and report labeling)

**Required format (minimum):**
- `signal_name (csv_display_name)`

Where `csv_display_name` follows rule N2 below.

### N2 — Disambiguate Same CSV Filenames from Different Folders
When multiple CSV files share the **same filename** but are located in different folders, the UI must display them using **parent-folder/filename** form:

- Example: `TestRunA/signal.csv` and `TestRunB/signal.csv`

This display name must be used consistently in:
- Data Sources panel list
- Signal tree CSV node headers
- Plot legends (via N1)
- Assigned list (via N1)
- Reports/exports (where file identity is shown)

### N3 — Consistency Rules
- The chosen CSV display name must be produced by **one canonical helper** (single source of truth).
- The same CSV identity string must be used consistently across:
  - signal tree
  - legends
  - assigned list
  - exports/reports
- If the full path is needed, keep it in tooltip; do not clutter main UI with full paths.

### N4 — Test Cases (Must Pass)
Implement and verify behavior for these cases:

1. **Same signal name, different CSVs**
   - CSV1: `Time, RPM`
   - CSV2: `Time, RPM`
   - Legend must show:
     - `RPM (csv1)` and `RPM (csv2)` (using display naming rules)

2. **Same CSV filename, different folders**
   - `/data/run1/signal.csv`
   - `/data/run2/signal.csv`
   - Data Sources list + tree must show:
     - `run1/signal.csv`
     - `run2/signal.csv`

3. **Both conditions together**
   - Same CSV filename in different folders AND same signal names in both
   - Legend must show:
     - `RPM (run1/signal)` and `RPM (run2/signal)` (whatever the canonical csv_display_name is)

---

## High-Level Goals

1. **Make the app easier to understand for first-time users**
2. **Reduce cognitive load in the UI**
3. **Make advanced features discoverable but not overwhelming**
4. **Improve visual consistency and modern feel**
5. **Improve internal code readability and structure**
6. **Preserve power-user efficiency**
7. **Ensure naming disambiguation rules N1–N4 are fully implemented**

---

## UX & UI Improvement Tasks

### UX-1: Progressive Disclosure
Implement collapsible / expandable “Advanced” sections for:
- Signal operations
- Derived signals
- Compare features
- Export options

Default view should show:
- Load data
- Browse signals
- Assign to plot
- Zoom / cursor / basic export

### UX-2: Clear User Flow
Re-organize UI conceptually into:

1. **Data**
   - Load CSVs
   - Time column selection
   - Offsets
2. **Signals**
   - Browse
   - Filter
   - Assign
3. **Plot**
   - Layout
   - Cursor
   - X-Y mode
4. **Analysis**
   - Operations
   - Derived signals
5. **Output**
   - Export
   - Reports
   - Sessions

### UX-3: Reduce Visual Noise
- Reduce icon overuse where text is clearer.
- Ensure consistent icon meaning across the app.
- Standardize font sizes (small / normal / header).
- Use consistent spacing and alignment.

### UX-4: Improve Feedback & Status
Add clear user feedback for:
- CSV loading progress
- Large file warnings (informational, not blocking)
- Active mode indicators (X-Y mode, linked axes, cursor active)
- Empty states (“No signals assigned”, “No CSV loaded”)

---

## Interaction Improvements

### INT-1: Safer Defaults
- Default to **Time mode**, **Cursor off**, **Linked axes off**
- Avoid enabling advanced modes silently

### INT-2: Keyboard Shortcuts Discoverability
Add:
- A small “⌨ Shortcuts” help modal or tooltip

### INT-3: Cursor UX
- Make cursor state obvious (active/inactive)
- Improve cursor play/stop affordance
- Ensure cursor value readout is visually grouped and readable

---

## Code Architecture Improvements (Incremental)

### ARCH-1: Reduce `app.py` Cognitive Load
Refactor incrementally by:
- Extracting layout sections into functions (can remain in same file initially)
- Group callbacks logically:
  - CSV handling
  - Signal tree
  - Plot rendering
  - Cursor logic
  - Export logic
- Add clear section headers and docstrings

### ARCH-2: Explicit UI State Naming
- Make it clear which stores are per-tab vs global
- Add comments explaining non-obvious state interactions

### ARCH-3: Defensive UX Coding
- Validate user actions before applying them
- Provide user-visible error messages instead of silent failures
- Log technical details to console, not UI

---

## Visual Design Guidelines

- Maintain dark/light themes
- Prefer:
  - Rounded corners
  - Subtle shadows
  - Clear grouping
- Avoid visual “flashing” or layout jumps
- Preserve plot stability (no white flashes)

---

## Performance Guardrails

You must:
- Preserve WebGL rendering
- Avoid unnecessary figure rebuilds
- Keep UI responsive during CSV loading

If you add features, they must not degrade performance.

---

## Deliverables

1. Incrementally refactored code
2. Cleaner, more readable `app.py`
3. Improved UX without removing power features
4. No regression in lossless behavior
5. Full implementation of naming/disambiguation rules N1–N4
6. Short `UX_CHANGES.md` summarizing improvements

---

## Implementation Approach (Required)

Work in **small, safe steps**:

1. Implement N1–N4 (canonical naming helpers + UI/legend/export consistency)
2. Improve layout clarity
3. Improve labels, grouping, defaults
4. Add progressive disclosure
5. Refactor code structure lightly
6. Polish interactions

After each step:
- App must run
- Existing sessions must still load
- Large CSVs must still work
- Disambiguation behavior must remain correct

---

## Summary

This task is about **polish, clarity, and maturity**, not raw features.

Treat Signal Viewer Pro as a professional tool that should feel:
- powerful
- predictable
- modern
- trustworthy

Optimize for real users analyzing real data, with correct identity labeling for signals and files.
