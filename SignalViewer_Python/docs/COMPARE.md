# Compare Mode — Signal Viewer Pro

This document describes the signal and run comparison features.

---

## Overview

Signal Viewer Pro supports comparing signals across multiple CSV runs to identify differences, correlations, and trends.

---

## Compare Panel

Located in the right sidebar, the Compare panel provides:

### Signal Comparison
1. **Baseline Run**: Select the reference run
2. **Compare-To Run**: Select the run to compare
3. **Signal**: Choose a signal common to both runs
4. **Alignment Method**:
   - **Baseline**: Interpolate compare-to onto baseline's time
   - **Intersection**: Only overlapping time region
   - **Union**: Full time range of both

### Metrics Computed
- **Max |Δ|**: Maximum absolute difference
- **RMS Δ**: Root mean square difference
- **Correlation**: Pearson correlation coefficient

### Delta Signal
When comparison runs, a derived signal `Δ(signal_name)` is created:
- Appears in the Derived section of the signal tree
- Can be assigned to any subplot
- Persisted with session

---

## Usage

### Compare Two Runs

1. Load two or more CSV files
2. Open Compare panel (click ▼)
3. Select Baseline Run (e.g., "run1.csv")
4. Select Compare-To Run (e.g., "run2.csv")
5. Select a common signal
6. Choose alignment method
7. Click "Compare"

### View Results

- Metrics displayed in panel
- Delta signal created automatically
- Assign delta to subplot for visualization

---

## Alignment Methods

### Baseline
Uses the baseline run's time vector. Compare-to signal is interpolated (linearly) to match.

### Intersection
Only the overlapping time region is compared. Useful when runs have different start/end times.

### Union
Full time range of both runs. Extrapolation may occur at edges.

---

## Future Enhancements (P2)

The following advanced features are planned:

### Compare Tab (P2-16)
- Clicking "Compare" opens a new tab
- Tab layout: 2×1 (overlay + diff)
- Subplot 1: Both signals overlaid
- Subplot 2: Difference trace

### Compare Runs Ranking (P2-17)
- Compare all common signals between runs
- Rank by dissimilarity (RMS diff)
- Clickable table to view individual comparisons

---

*Last updated: P0-P1 Implementation*

