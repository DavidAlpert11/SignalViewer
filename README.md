# Signal Viewer Pro v2.5

Professional signal analysis tool for engineering data visualization.

![Signal Viewer Screenshot](SignalViewer_Python/preview.png)

## Features

### Core Visualization
- **Multi-tab, multi-subplot visualization** — Chrome-like tab interface with independent tabs
- **Lossless signal handling** — No downsampling, resampling, or decimation
- **Offline-first** — No external dependencies during runtime
- **Time and X-Y modes** — Plot signals vs time or against each other
- **Axis linking** — Link X axes across all subplots in a tab
- **Custom titles** — Edit subplot and tab names directly
- **Figure caching** — Faster rendering when data hasn't changed

### Signal Operations
- **Derived signals** — Create new signals from mathematical operations
  - Unary: derivative, integral, absolute, normalize, RMS (batch support)
  - Binary: add, subtract, multiply, divide, absolute difference
  - Multi: norm, mean, max, min
- **State signal visualization** — Vertical lines at state transitions (like MATLAB xline)

### CSV Management
- **Rename CSVs** — Set custom display names
- **Replace CSV path** — Swap data files without losing signal assignments
- **Multi-file import** — Load multiple CSVs at once

### Compare Workflows
- **Multi-run comparison** — Compare 2+ CSV files simultaneously
- **Baseline methods** — Use mean or specific run as reference
- **Similarity metrics** — RMS difference, correlation, percent deviation
- **Delta signal generation** — Automatically create difference signals
- **Sortable results** — Sort by difference or name
- **Selective subplot creation** — Choose which signals to compare

### Cursor & Inspector
- **Interactive cursor** — Click or drag to inspect values
- **Jump-to-time** — Enter exact time values
- **Active/All scope** — Show values for active subplot or all subplots

### Report Generation
- **HTML export** — Offline report with embedded Plotly charts
- **Word export** — DOCX format with images
- **RTL support** — Hebrew and Arabic text direction
- **Per-subplot metadata** — Title, caption, description

### Session Management
- **Save/Load sessions** — Preserve complete application state
- **Derived signals persistence** — Saved and restored with sessions
- **Signal properties** — Colors, widths, scales persist

## Installation

### Requirements
- Python 3.8+

### Quick Install

```bash
cd SignalViewer_Python
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050

### Build Executable (Windows)

```bash
cd SignalViewer_Python
build.bat
```

Output: `dist\SignalViewer\SignalViewer.exe`

## Quick Start

1. **Import CSV files** — Click "Import" and select files
2. **Assign signals** — Click signals in the left panel to add to subplots
3. **Enable cursor** — Toggle cursor to inspect values
4. **Generate reports** — Click "Report" to export HTML/Word

## CSV Format

```csv
Time,Speed,Temperature,Pressure
0.0,10.5,25.0,101.3
0.1,12.3,25.1,101.2
0.2,14.1,25.2,101.4
```

## Project Structure

```
SignalViewer_Python/
├── app.py              # Main application
├── build.bat           # Build script
├── requirements.txt    # Dependencies
├── sample_data/        # Test CSV files
├── core/               # Data models
├── ui/                 # Layout components
├── viz/                # Figure generation
├── loaders/            # CSV loading
├── ops/                # Mathematical operations
├── compare/            # Run comparison
├── stream/             # Live streaming
├── report/             # Report generation
└── assets/             # CSS and fonts
```

## License

MIT License - See LICENSE file for details.

## Support

For issues and feature requests, use the [GitHub issue tracker](https://github.com/DavidAlpert11/SignalViewer/issues).
