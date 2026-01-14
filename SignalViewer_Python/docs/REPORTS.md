# Report Builder — Signal Viewer Pro

This document describes the report generation and export features.

---

## Overview

Signal Viewer Pro can export analysis results as standalone HTML reports that work offline.

---

## Accessing Report Builder

Click the **📊 Report** button in the header toolbar to open the Report Builder modal.

---

## Report Configuration

### Report Title
A main heading for the report (default: "Signal Analysis Report").

### Text Direction (RTL Support)
Toggle **Right-to-Left** for Hebrew or Arabic text. When enabled:
- HTML uses `dir="rtl"`
- Text fields display right-to-left
- Full Unicode/UTF-8 support

### Introduction
Multi-line text field for report introduction. Supports Hebrew and other languages.

### Summary / Conclusion
Multi-line text field for conclusions and summary.

### Include Subplots
Each subplot can be individually included/excluded from the report. For each:
- **Title**: Optional short title
- **Caption**: Optional caption text
- These persist with session save/load

### Export Format
- **HTML (offline)**: Standalone HTML with embedded plots
- **CSV (data only)**: Raw signal data export

---

## HTML Report Features

### Offline Capable
- All CSS embedded inline
- Plots rendered as interactive Plotly figures
- No external dependencies required

### Structure
1. Title and timestamp
2. Introduction section
3. Plots (embedded interactive figures)
4. Per-subplot metadata (title, caption, signal count)
5. Conclusion section

### RTL/Hebrew Support (P0-14)
When RTL is enabled:
- Document direction set to `dir="rtl"`
- Text sections use `text-align: right`
- Hebrew characters render correctly

---

## CSV Export

Exports signal data as comma-separated values:
- Time column first
- One column per assigned signal
- Only signals from included subplots
- Uses common time base (densest)

---

## Usage Example

1. Configure plot with signals and layout
2. Click **📊 Report**
3. Enter Title: "Motor Test Analysis"
4. Enable RTL if using Hebrew
5. Write Introduction: "This report analyzes..."
6. Add subplot titles/captions
7. Click **Export**
8. HTML file downloads automatically

---

## Per-Subplot Metadata (P0-10)

Each subplot can have:
- **Title**: Short identifier (e.g., "Speed Profile")
- **Caption**: Brief description (e.g., "Motor speed during acceleration phase")
- **Description**: Detailed notes (multi-line, for internal use)

These are:
- Editable in Report Builder modal
- Saved with session
- Included in HTML export

---

## Troubleshooting

### Hebrew Text Not Displaying
- Ensure RTL toggle is enabled
- Check browser supports Unicode
- Verify file saved as UTF-8

### Plot Not Appearing
- Ensure at least one subplot has assigned signals
- Check that subplot is included in report

### Large File Size
- Plots with many data points create larger HTML
- Consider reducing displayed time range
- No downsampling is applied (lossless)

---

*Last updated: P0-P1 Implementation*

