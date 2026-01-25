# Signal Viewer Pro

Professional signal analysis tool for engineering data visualization.

![Signal Viewer Pro Screenshot](screenshot.png)

## Features

### Core Visualization
- **Multi-tab, multi-subplot visualization** — Chrome-like tab interface with independent tabs
- **Lossless signal handling** — No downsampling, resampling, or decimation
- **Offline-first** — No external dependencies during runtime
- **Time and X-Y modes** — Plot signals vs time or against each other
- **Axis linking** — Link X axes across all subplots in a tab
- **Custom titles** — Edit subplot and tab names directly

### Signal Operations
- **Derived signals** — Create new signals from mathematical operations
  - Unary: derivative, integral, absolute, normalize, RMS (supports batch operations on multiple signals)
  - Binary: add, subtract, multiply, divide, absolute difference
  - Multi: norm, mean, max, min
- **State signal visualization** — Display discrete signals as vertical transition lines

### Compare Workflows
- **Multi-run comparison** — Compare 2+ CSV files simultaneously
- **Baseline methods** — Use mean or specific run as reference
- **Similarity metrics** — RMS difference, correlation, percent deviation
- **Delta signal generation** — Automatically create difference signals
- **Sortable results** — Sort by difference (high/low), or name (A-Z/Z-A)
- **Auto subplot creation** — Create subplots with signal names as titles

### Cursor & Inspector
- **Interactive cursor** — Click or drag to inspect values
- **Jump-to-time** — Enter exact time values
- **Active/All scope** — Show values for active subplot or all subplots
- **Nearest sample** — Cursor snaps to actual sample times

### Report Generation
- **HTML export** — Offline report with embedded Plotly charts
- **Word export** — DOCX format with images (requires python-docx)
- **RTL support** — Hebrew and Arabic text direction
- **Multi-line text** — Title, introduction, conclusion with line breaks
- **Per-subplot metadata** — Title, caption, description for each subplot

### Session Management
- **Save/Load sessions** — Preserve complete application state
- **Derived signals** — Saved and restored with sessions
- **Signal properties** — Colors, widths, scales persist

## Installation

### Requirements
- Python 3.8+
- pip

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Optional Dependencies

For Word document export:
```bash
pip install python-docx
```

## Quick Start

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Open in browser**:
   Navigate to http://127.0.0.1:8050

3. **Import CSV files**:
   - Click "📂 Import"
   - Select one or more CSV files
   - Configure import settings (delimiter, time column)
   - Click "Import"

4. **Assign signals to subplots**:
   - Click on signals in the left panel
   - They will be assigned to the active subplot

5. **Use cursor for value inspection**:
   - Enable cursor with the toggle switch
   - Click on plot or use slider to move cursor
   - View values in the Inspector panel

6. **Generate reports**:
   - Click "📄 Report"
   - Add title, introduction, conclusion
   - Configure subplot titles/captions
   - Export as HTML or Word

## CSV Format

Signal Viewer Pro expects CSV files with:
- First column: Time values (or specify time column)
- Subsequent columns: Signal values
- Optional header row

Example:
```csv
Time,Speed,Temperature,Pressure
0.0,10.5,25.0,101.3
0.1,12.3,25.1,101.2
0.2,14.1,25.2,101.4
```

## Keyboard Shortcuts

- **Tab switching**: Click tab buttons
- **Subplot selection**: Use dropdown or click on plot

## Architecture

```
SignalViewer_Python/
├── app.py                 # Main application & callbacks
├── core/
│   ├── models.py          # Data models (Run, Signal, ViewState)
│   ├── naming.py          # Display name generation
│   └── session.py         # Session save/load utilities
├── ui/
│   └── layout.py          # Dash layout components
├── viz/
│   └── figure_factory.py  # Plotly figure generation
├── loaders/
│   └── csv_loader.py      # CSV file loading
├── ops/
│   └── engine.py          # Mathematical operations
├── compare/
│   └── engine.py          # Run comparison logic
├── stream/
│   └── engine.py          # Live data streaming
├── report/
│   └── builder.py         # Report generation
└── assets/
    └── custom.css         # Custom styling
```

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and feature requests, please use the GitHub issue tracker.
