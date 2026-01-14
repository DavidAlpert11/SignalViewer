# 🧠 CURSOR AI AGENT — FINAL FIXES & BEHAVIOR CORRECTIONS (SDI-Level)

## Context (Read Carefully)

The app now contains most SDI-like features, but **several behaviors are still incorrect or inconsistent**.
This task is **not about adding new features**, but about **fixing semantics, UX correctness, and workflow logic**.

You must:
- Fix all issues listed below
- Not introduce regressions
- Not remove features
- Prefer correctness over shortcuts

This is the **final stabilization pass**.

---

## Non-Negotiable Constraints

- ❌ No downsampling / decimation / resampling
- ✅ Lossless signal handling
- ✅ Offline only (no CDNs)
- ✅ Canonical naming everywhere:
signal_name — csv_display_name

yaml
Copy code
- SDI-like mental model:
- views (tabs)
- runs
- subplots
- cursor inspector
- compare opens **new views**

---

## P0 — Behavioral Bugs (Must Fix Exactly)

### 1️⃣ CSV import MUST NOT auto-assign any signal
**Current bug**: first signal is auto-assigned to Subplot 1.

**Required behavior**:
- Importing CSV adds runs + signals to tree ONLY
- No subplot receives any signal automatically
- User must explicitly assign signals

**Acceptance test**:
- Load CSV → plot stays empty

---

### 2️⃣ Tabs behavior is wrong (ghost “main” tab)
**Current bug**:
- Clicking `+ Tab` creates View2/View3 but still keeps a hidden “main” view

**Required behavior**:
- Exactly **N visible tabs = N views**
- No implicit “main” tab
- First tab = `View 1` and is removable **only if at least one other tab exists**
- Closing a tab:
- removes that view entirely
- switches to nearest remaining tab

**Acceptance test**:
- Create 3 tabs → see exactly 3
- Close View 2 → View 1 + View 3 remain

---

### 3️⃣ On app restart, clear all cached state
**Requirement**:
When app starts:
- Clear:
- in-memory caches
- session stores
- derived signals
- tab state
- App must start as “first launch”

Do NOT auto-load last session.

---

### 4️⃣ Layout dropdown text is still clipped
**Requirement**:
- Layout selector must fully display:
Subplot N / M

yaml
Copy code
- Increase width / font size as needed
- This is a UX blocker — fix properly

---

### 5️⃣ Refresh / Stream behavior redesign (important)

#### Current state (wrong):
- Separate Smart Refresh panel
- Refresh button already exists → duplicated logic

#### Required SDI-like behavior:

Toolbar buttons:
- 🔄 **Refresh**
- ▶️ **Stream**

**Refresh**:
- One-shot:
- re-read CSVs
- detect added/removed signals
- recompute derived signals
- update plots

**Stream**:
- Starts with Refresh
- Then repeats incremental refresh **every X seconds**
- User can choose rate (e.g. 0.5s / 1s / 2s / 5s)
- Continues until stopped
- Only reads appended lines if possible
- If file rewritten → warn + full reload

Remove the Smart Refresh panel completely.

---

### 6️⃣ Switching subplot must NOT clear assignments
**Current bug**:
- Changing active subplot clears its signals

**Required behavior**:
- Subplot selection is **purely navigational**
- Assignments persist until user clears them
- Switching subplot only changes “where new assignments go”

---

### 7️⃣ Canonical naming bug: mysterious suffix
Example:
signal4 — Downloads/signals

yaml
Copy code

**This is WRONG.**

**Required behavior**:
- `csv_display_name` must be:
  - filename only if unique
  - parent_folder/filename if duplicate
- Never show internal folder names like `signals/`

You must:
- audit naming helper
- remove incorrect path slicing

---

### 8️⃣ Legend must be per-subplot (not global)
**Current bug**:
- One legend shared across all subplots

**Required behavior**:
- Each subplot has its own legend
- Legends only show signals assigned to that subplot
- Legends visually separated (Plotly supports this via legend groups or separate legends)

---

### 9️⃣ Cursor “Active / All” toggle is broken
**Current bug**:
- Button exists but does not change behavior

**Required behavior**:
- **Active**:
  - show cursor values only for active subplot
- **All**:
  - show cursor values grouped by subplot

Buttons must:
- visibly toggle
- actually change output

---

### 🔟 Cursor: jump to specific time
**New requirement**:
Add numeric input:
- user enters time `T`
- cursor jumps to nearest sample
- inspector updates values

Behavior:
- nearest sample (not interpolation)
- show actual sample time used

---

## P1 — Export & Reporting Fixes

### 1️⃣ Subplot description missing from export
**Required per subplot**:
- Title
- Caption
- Description (multi-line)

These must:
- be editable in Assigned panel
- persist in session
- appear in HTML and DOCX exports

---

### 2️⃣ Text fields must be multi-line
**Affected fields**:
- Report Title
- Introduction
- Per-subplot Caption
- Per-subplot Description
- Summary

Replace single-line inputs with:
- `dcc.Textarea`
- Proper resizing

---

### 3️⃣ Add Word (.docx) export
**Required**:
- Export report to `.docx`
- Use:
  - python-docx
- Include:
  - title
  - introduction
  - per-subplot sections
  - captions & descriptions
  - images (PNG via kaleido)
  - summary
- Hebrew / RTL must render correctly

---

## P2 — Compare Workflow Corrections (Critical)

### 1️⃣ Compare signal MUST open a new tab
**Current bug**:
- Compare updates current view or does nothing

**Required behavior**:
- Compare action creates **new tab**
Compare: <signal_name>

yaml
Copy code
- Layout:
- 2×1
  - top: overlay of runs
  - bottom: diff vs baseline

---

### 2️⃣ Compare must support >2 CSVs
**Required**:
- If same signal exists in 3+ runs:
- overlay all
- diffs vs chosen baseline
- Legend must reflect run names clearly

---

### 3️⃣ Compare whole runs → ranked similarity tab
**Required behavior**:
- User selects 2+ runs
- App computes similarity metric for all common signals
- Opens new tab:
Compare Runs: A vs B (+N)

yaml
Copy code
- Left: ranked table of signals (most different first)
- Clicking signal:
- updates plots (overlay + diff)
- Multi-select opens multiple plots or cycles (choose one and document)

---

## UX Polishing Rules (Do Not Ignore)

- No action should silently change data
- All toggles must visibly reflect state
- No clipped text anywhere
- No duplicate controls
- No panels that do nothing

---

## Implementation Order (MANDATORY)

1. Stop auto-assign on import
2. Fix tab system (remove ghost main)
3. Clear all state on restart
4. Fix layout dropdown clipping
5. Redesign Refresh + Stream buttons
6. Fix subplot switching behavior
7. Fix canonical naming bug
8. Implement per-subplot legends
9. Fix cursor Active/All toggle
10. Add cursor jump-to-time
11. Fix export descriptions + multiline text
12. Add DOCX export
13. Fix compare → new tab
14. Implement multi-run compare + ranking

After each step:
- App must run
- No regression
- Add manual test case

---

## Definition of Done

This task is complete only when:
- Import does NOT auto-assign
- Tabs behave exactly as expected
- Cursor behaves like SDI
- Legends are per subplot
- Compare opens new tabs
- Reports export correctly (HTML + DOCX)
- Refresh/Stream is intuitive and efficient

You are building a **professional SDI-grade tool**, not a demo.
Do not compromise correctness for speed.