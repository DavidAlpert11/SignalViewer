# 📊 Signal Viewer Pro

A professional signal visualization and analysis tool built with Python and Dash. Perfect for analyzing CSV data with multiple signals, comparing waveforms, and creating publication-ready plots.

## ✨ Features

### Core Functionality
- **Multi-CSV Support**: Load and compare signals from multiple CSV files simultaneously
- **Multi-Tab Interface**: Organize different analyses in separate tabs
- **Flexible Subplot Grid**: Configure 1x1 to 4x4 subplot layouts
- **Signal Operations**: Derivative, integral, math operations between signals
- **Real-time Cursor**: Click to set cursor, displays values at any time point

### Performance Optimized
- **LTTB Decimation**: Intelligent downsampling preserves visual features
- **WebGL Rendering**: GPU-accelerated plotting for large datasets
- **Smart Caching**: LRU cache for signal data and decimated views
- **Instant Interactions**: Clientside JavaScript for collapse/expand (no server delay)

### Visualization
- **Dark/Light Themes**: Professional appearance in any environment
- **Consistent Signal Colors**: Each signal maintains its color across all subplots
- **Customizable Signals**: Per-signal colors, line widths, display names, time offsets
- **Linked CSV Groups**: Synchronize signals from related files
- **State Signals**: Vertical line rendering for discrete state changes
- **X-Y Mode**: Plot any signal against another (not just time)
- **Quick Statistics**: Toggle min/max/mean/std display for assigned signals
- **Marker Mode**: Show data point markers on signal traces
- **Normalize Mode**: Scale signals to 0-1 range for comparison
- **Annotations**: Add custom text notes at specific points on plots

### Data Management
- **Time Column Selection**: Choose any column as the time axis
- **Time Offsets**: Shift signal timing per-signal or per-CSV for alignment
- **CSV Header Settings**: Support for CSVs without headers or headers in different rows
- **Collapsible Tree**: Organize large signal lists with expandable/collapsible CSV nodes

### Export & Reporting
- **HTML Reports**: Generate interactive reports with all plots (works offline!)
- **Word Documents**: Export publication-ready reports with embedded plots
- **CSV Export**: Export selected signals to new CSV files
- **Session Management**: Save/load complete analysis sessions (all settings preserved)
- **Plot Templates**: Reuse configurations across different data files

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Installation

```bash
# Clone or download the repository
cd SignalViewer_Python

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

The application will open in your default web browser at `http://127.0.0.1:8050`

### Basic Usage

1. **Load CSV Files**: Click "Browse Files..." to open native file picker and select CSV files
2. **Select Signals**: Check the 📊 checkbox next to signals to add them to the current subplot
3. **Select Subplot**: Double-click on a subplot to make it active for signal assignment
4. **Place Cursor**: Single-click on the plot to set the time cursor and view values
5. **Configure Signals**: Click ✎ to change color, scale, time offset, etc.
6. **Export**: Use 📑 for HTML reports, 📝 for Word documents

**Note**: Files are loaded from their original location (not copied). This enables live streaming and refresh from source files.

## 🎯 User Guide

### Signal Assignment
- **📊 Checkbox**: Assign/unassign signal to current subplot
- **⚙ Checkbox**: Select signals for multi-signal operations
- **✎ Button**: Open signal properties (color, scale, time offset)
- **⚙ Button**: Single-signal operations (derivative, integral, etc.)

### Subplot Selection
- **Double-click** on a subplot to select it for signal assignment
- The selected subplot has a highlighted blue border
- Use the dropdown to quickly switch between subplots

### Time Offsets
Time offsets let you align signals that were recorded with timing differences:
1. Click the **⏱** button in the Data Sources panel
2. Enter offset values in seconds (positive = shift right, negative = shift left)
3. Or click **✎** on a specific signal to set its individual offset

### X-Y Plot Mode
To plot one signal against another (instead of time):
1. Select **⚡ X-Y** mode in the Assigned panel
2. Assign signals to the subplot
3. Use the X-Axis dropdown to select which signal is on X-axis
4. Other signals will be plotted on Y-axis

### Display Options
In the Assigned panel, toggle these options:
- **📊 Stats**: Show quick statistics (min/max/mean/std) for assigned signals
- **⚫ Markers**: Display data point markers on signal traces
- **📏 Normalize**: Scale all signals to 0-1 range for visual comparison

### Annotations
Add text notes at specific points on your plots:
1. Click the **📌** button in the plot header
2. Set X/Y position (click on plot first to populate X position)
3. Enter annotation text and customize color/font/arrow
4. Click "Add" to place the annotation
5. Use "Clear All" to remove all annotations from current subplot

### Exporting

#### HTML Report (Recommended for Interactive Sharing)
- Click 📑 button to open export dialog
- Add title, introduction, and conclusion text
- Set captions/descriptions for each subplot in the Assigned panel
- Export creates a standalone HTML file that works offline!

#### Word Document (Recommended for Printing/Editing)
- Click 📝 button to open Word export dialog
- Add report title, introduction, and conclusion text
- Choose export scope: current subplot, tab, or all tabs
- Generates a .docx file with embedded plot images
- Requires: `pip install python-docx kaleido`

#### Session Save/Load
- Click 💾 to save entire session (CSV paths, assignments, settings)
- Click 📂 to load a previously saved session
- Templates (📋/📄) save only layout and signal names (not CSV paths)

## 📁 Project Structure

```
SignalViewer_Python/
├── app.py                 # Main application (Dash layout & callbacks)
├── run.py                 # Application entry point
├── data_manager.py        # CSV loading and data caching
├── signal_operations.py   # Mathematical signal operations
├── linking_manager.py     # CSV linking/grouping functionality
├── config.py              # Theme colors and constants
├── helpers.py             # Utility functions
├── callback_helpers.py    # UI callback utilities
├── flexible_csv_loader.py # Smart CSV parsing
├── requirements.txt       # Python dependencies
├── assets/                # CSS and JavaScript assets
│   ├── custom.css         # Custom styles
│   ├── collapse.js        # Clientside collapse handling
│   ├── split.min.js       # Resizable panels
│   └── ...
└── uploads/               # Cache directory for LOD data
```

## ⚙️ Configuration

### Time Settings (⏱️ Button)
- **Time Column**: Select which column to use as the X-axis for each CSV
- **Time Offset**: Add positive/negative offset to shift signal timing
- **Header Settings**: Specify header row or mark CSVs as having no headers

### Signal Properties (✎ Button)
- **Display Name**: Custom name shown in tree and legends
- **Scale Factor**: Multiply signal values (e.g., 1000 for mV→V)
- **Color**: Signal line color (consistent across all subplots)
- **Line Width**: Thickness of the signal line
- **Time Offset**: Per-signal time shift in seconds
- **State Signal**: Enable for discrete/step signals

### Layout Options
- **Rows × Columns**: Subplot grid configuration (up to 4×4)
- **Link Axes**: Synchronize zoom/pan across subplots
- **Cursor**: Show/hide the time cursor

## 📊 Performance Tips

For large CSV files (>100k rows):

1. **WebGL**: Automatically enabled for datasets >500 points
2. **LTTB Decimation**: Reduces display points to 5000 while preserving features
3. **Collapse CSV Nodes**: Click on CSV folder headers to hide unused signals
4. **Use Search Filters**: Filter signals by name (+ button adds persistent filters)
5. **Limit Subplots**: Fewer subplots = faster rendering

## 🛠️ Building a Standalone Executable

### Windows

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable
build.bat

# Output: dist/SignalViewer/SignalViewer.exe
```

## 📝 Dependencies

Core dependencies (see `requirements.txt` for versions):
- **dash**: Web application framework
- **dash-bootstrap-components**: UI components
- **plotly**: Interactive plotting
- **pandas**: Data manipulation
- **numpy**: Numerical operations

Optional (for Word export):
- **python-docx**: Word document generation
- **kaleido**: Static image export from Plotly

## 🔧 Troubleshooting

### Application won't start
- Check Python version: `python --version` (need 3.10+)
- Reinstall dependencies: `pip install -r requirements.txt`

### Slow with large files
- Reduce subplot count if using many signals
- Use search filters to limit visible signals
- Collapse CSV folders you're not using

### Refresh button not showing updated data
- v3.0 fixed disk cache invalidation - refresh now clears all caches including .npz files
- If issues persist, delete the `uploads/.cache/` directory

### Streaming stops but still shows old data
- v3.0 improved streaming with automatic timeout detection (stops after 1s of no file updates)
- Live status shows current row counts and progress

### Subplot not selecting
- Use **double-click** to select a subplot (single-click places cursor)
- Or use the subplot dropdown in the header

### Signals have wrong colors
- Colors are now consistent per signal (based on signal name)
- To change: click ✎ button and set custom color

### HTML export doesn't show plots offline
- Use the 📑 export button (not browser's "Save Page As")
- Plotly.js is embedded automatically for offline viewing

## 📜 License

MIT License - See LICENSE file for details.

## 🙏 Acknowledgments

- Built with [Dash](https://dash.plotly.com/) by Plotly
- Icons by [Font Awesome](https://fontawesome.com/)
- Styling by [Bootstrap](https://getbootstrap.com/)

---

**Signal Viewer Pro v3.0** - Professional signal analysis made simple. 📊✨
