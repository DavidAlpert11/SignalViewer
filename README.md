# 📊 Signal Viewer Pro

A professional signal visualization and analysis tool built with Python and Dash. Perfect for analyzing CSV time-series data, comparing waveforms, and creating publication-ready plots.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Dash](https://img.shields.io/badge/Dash-2.14+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

### 📈 Core Functionality
- **Multi-CSV Support** - Load and compare signals from multiple CSV files simultaneously
- **Multi-Tab Interface** - Organize different analyses in separate tabs
- **Flexible Subplot Grid** - Configure 1×1 to 4×4 subplot layouts
- **Signal Operations** - Derivative, integral, add, subtract, multiply, divide between signals
- **Real-time Cursor** - Click to set cursor, displays values at any time point
- **Live Streaming** - Watch CSV files update in real-time (great for live data logging)

### ⚡ Performance Optimized
- **LTTB Decimation** - Intelligent downsampling preserves visual features for large files
- **WebGL Rendering** - GPU-accelerated plotting for datasets with millions of points
- **Smart Caching** - LRU cache for signal data and decimated views
- **Instant Interactions** - Client-side JavaScript for collapse/expand (no server delay)

### 🎨 Visualization
- **Dark/Light Themes** - Professional appearance in any environment
- **Consistent Signal Colors** - Each signal maintains its color across all subplots
- **Customizable Signals** - Per-signal colors, line widths, display names, time offsets
- **Linked CSV Groups** - Synchronize signals from related files
- **State Signals** - Vertical line rendering for discrete state changes
- **X-Y Mode** - Plot any signal against another (not just time)
- **Quick Statistics** - Toggle min/max/mean/std display for assigned signals
- **Marker Mode** - Show data point markers on signal traces
- **Normalize Mode** - Scale signals to 0-1 range for comparison
- **Annotations** - Add custom text notes at specific points on plots

### 📁 Data Management
- **Native File Picker** - Browse and select files from anywhere on your system
- **Original Path Loading** - Files loaded from source location (enables refresh/streaming)
- **Time Column Selection** - Choose any column as the time axis
- **Time Offsets** - Shift signal timing per-signal or per-CSV for alignment
- **CSV Header Settings** - Support for CSVs without headers or headers in different rows
- **Collapsible Tree** - Organize large signal lists with expandable/collapsible CSV nodes
- **Search & Filter** - Find signals quickly with persistent search filters

### 📤 Export & Reporting
- **HTML Reports** - Generate interactive reports (works offline!)
- **Word Documents** - Export publication-ready reports with embedded plots
- **CSV Export** - Export selected signals to new CSV files
- **Session Management** - Save/load complete analysis sessions
- **Plot Templates** - Reuse configurations across different data files

---

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/SignalViewer.git
cd SignalViewer/SignalViewer_Python

# 2. (Optional) Create a virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python run.py
```

The application will open in your default web browser at `http://127.0.0.1:8050`

### Optional Dependencies (for Word export)
```bash
pip install python-docx kaleido
```

---

## 📖 User Guide

### Getting Started

1. **Load CSV Files**: Click **"Browse Files..."** button to open native file picker
2. **View Signals**: Expand CSV folders in the signal tree to see available signals
3. **Assign Signals**: Check the **📊** checkbox next to signals to add them to current subplot
4. **Select Subplot**: **Double-click** on a subplot to make it active
5. **Place Cursor**: **Single-click** on plot to set time cursor and view values

### Signal Tree Controls
| Control | Action |
|---------|--------|
| 📊 Checkbox | Assign/unassign signal to current subplot |
| ⚙ Checkbox | Select signal for multi-signal operations |
| ✎ Button | Open signal properties (color, scale, offset) |
| ⚙ Button | Single-signal operations (derivative, integral) |

### Toolbar Buttons
| Button | Function |
|--------|----------|
| 💾 | Save session (all settings, CSV paths, assignments) |
| 📂 | Load saved session |
| 📋 | Save template (layout only, no data) |
| 📄 | Load template |
| 📊 | Export signals to CSV |
| 📑 | Export to HTML report |
| 📝 | Export to Word document |
| 📌 | Add annotation to plot |
| 🔄 | Refresh all CSVs from disk |
| ▶️ Stream | Watch CSVs for live updates |

### Display Options
In the **Assigned** panel, toggle these options:
- **📊 Stats** - Show quick statistics (min/max/mean/std)
- **⚫ Markers** - Display data point markers
- **📏 Normalize** - Scale all signals to 0-1 range

### Plot Modes
- **📈 Time Mode** - Plot signals against time (default)
- **⚡ X-Y Mode** - Plot one signal against another

### Time Alignment
Align signals recorded with timing differences:
1. Click **⏱** button in Data Sources panel
2. Enter offset values in seconds (positive = shift right)
3. Or click **✎** on specific signal for individual offset

---

## ⌨️ Keyboard & Mouse Controls

| Action | Control |
|--------|---------|
| Select subplot | Double-click on subplot |
| Place cursor | Single-click on plot |
| Zoom | Scroll wheel / Box select |
| Pan | Click and drag |
| Reset zoom | Double-click on plot background |

---

## 📁 Project Structure

```
SignalViewer/
├── README.md                    # This file
└── SignalViewer_Python/         # Main application
    ├── app.py                   # Dash application & callbacks
    ├── run.py                   # Entry point
    ├── data_manager.py          # CSV loading & caching
    ├── signal_operations.py     # Math operations on signals
    ├── linking_manager.py       # CSV linking functionality
    ├── config.py                # Theme colors & constants
    ├── helpers.py               # Utility functions
    ├── callback_helpers.py      # UI callback utilities
    ├── flexible_csv_loader.py   # Smart CSV parsing
    ├── requirements.txt         # Python dependencies
    ├── build.bat                # Build executable script
    ├── SignalViewer.spec        # PyInstaller spec file
    └── assets/                  # CSS & JavaScript assets
        ├── custom.css
        ├── collapse.js
        └── ...
```

---

## 🛠️ Building Standalone Executable

### Windows

```bash
cd SignalViewer_Python

# Install PyInstaller
pip install pyinstaller

# Build the executable
build.bat

# Output: dist/SignalViewer/SignalViewer.exe
```

The executable can be distributed without requiring Python installation.

---

## 📊 Performance Tips

For large CSV files (>100k rows):

1. **WebGL** - Automatically enabled for datasets >500 points
2. **LTTB Decimation** - Reduces display points while preserving features
3. **Collapse CSV Nodes** - Click folder headers to hide unused signals
4. **Use Search Filters** - Filter signals by name (+ button adds persistent filters)
5. **Limit Subplots** - Fewer subplots = faster rendering

---

## 🔧 Troubleshooting

### Application won't start
- Check Python version: `python --version` (need 3.10+)
- Reinstall dependencies: `pip install -r requirements.txt`

### Slow with large files
- Reduce subplot count
- Use search filters to limit visible signals
- Collapse CSV folders you're not using

### Refresh not showing updated data
- Click 🔄 button to force refresh from disk
- If issues persist, delete `uploads/.cache/` directory

### Streaming not detecting changes
- Ensure source CSV is being modified (check file timestamp)
- Streaming auto-stops after 1 second of no updates

### Subplot not selecting
- Use **double-click** to select (single-click places cursor)

### HTML export doesn't work offline
- Use the 📑 export button (not browser's "Save Page As")
- Plotly.js is automatically embedded for offline viewing

---

## 📝 Dependencies

**Core:**
- dash >= 2.14.0
- dash-bootstrap-components >= 1.5.0
- plotly >= 5.18.0
- pandas >= 2.0.0
- numpy >= 1.24.0

**Optional (Word export):**
- python-docx >= 0.8.11
- kaleido >= 0.2.1

**Optional (Comparison features):**
- scipy >= 1.10.0

---

## 📜 License

MIT License - See [LICENSE](SignalViewer_Python/LICENSE) for details.

---

## 🙏 Acknowledgments

- Built with [Dash](https://dash.plotly.com/) by Plotly
- Icons by [Font Awesome](https://fontawesome.com/)
- Styling by [Bootstrap](https://getbootstrap.com/)

---

**Signal Viewer Pro v3.0** - Professional signal analysis made simple. 📊✨
