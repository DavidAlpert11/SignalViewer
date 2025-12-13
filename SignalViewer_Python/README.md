# Signal Viewer Pro

A professional signal visualization and analysis application built with Python, Plotly Dash, and Plotly.

## Features

### Core Visualization
- **Multi-CSV Support**: Load and manage multiple CSV files simultaneously
- **Signal Browser**: Tree-based signal selection with cumulative search filtering
- **Multi-Tab Layout**: Create multiple tabs with independent subplot configurations
- **Subplot Grid**: Flexible rows × columns layout (up to 4×4 per tab)
- **Interactive Plots**: Zoom, pan, hover, and click interactions via Plotly

### Analysis Tools
- **Time Cursor**: Synchronized cursor across all subplots showing interpolated values
- **X-Y Plot Mode**: Plot signals against each other (not just vs. time)
- **Derived Signals**: Calculate derivative, integral, absolute, sqrt, and negation
- **Multi-Signal Operations**: Average, sum, difference, product, and norm of signals
- **Custom Time Column**: Select which column to use as X-axis per CSV file

### Data Management
- **Session Save/Load**: Complete state persistence (CSV paths, assignments, layouts, settings)
- **Template Save/Load**: Reuse layouts and signal assignments with different CSVs
- **Signal Customization**: Per-signal color, scale factor, line width, and display name

### Export Features
- **HTML Report Export**: Interactive HTML with all tabs/subplots, metadata, and descriptions
- **CSV Export**: Export signal data for selected scope (subplot/tab/all)
- **Subplot Metadata**: Title, caption, and description per subplot for reports

### User Interface
- **Resizable Panels**: Drag to resize sidebar and subplot panels (Split.js)
- **Dark/Light Theme**: Toggle between themes with persistent preference
- **Browser-Style Tabs**: Add/remove tabs with visual tab strip

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd SignalViewer_Python
```

2. Create virtual environment (recommended):
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Application

```bash
python app.py
```

The application starts at `http://127.0.0.1:8050` and should open automatically in your browser.

### Loading CSV Files

1. Drag and drop CSV files onto the upload area, or click to browse
2. Multiple files can be loaded at once
3. Files appear in the Data Sources panel with signal count

**CSV Format:**
```csv
Time,Signal1,Signal2,Signal3
0.0,1.5,2.3,0.8
0.1,1.6,2.4,0.9
...
```

By default, the first column is used as time. Use the ⏱️ button to select a different time column.

### Working with Signals

1. **Search**: Type in the search box to filter signals
2. **Select**: Check the box next to a signal to assign it to the current subplot
3. **Highlight**: Use the orange checkbox to highlight signals for batch operations

### Subplot Management

- **Select Subplot**: Click anywhere on a subplot to select it
- **Change Layout**: Use the Rows/Cols inputs in the plot header
- **Remove Signals**: Select signals in the Assigned panel and click Remove

### Time Cursor

1. Enable the "Time Cursor" checkbox in the plot header
2. Click and drag on any subplot to move the cursor
3. Signal values at the cursor position display on each subplot

### X-Y Plot Mode

1. Toggle "X-Y Mode" switch in the Assigned panel
2. Select a signal from the X-axis dropdown (from assigned signals)
3. Assigned signals plot against the selected X signal instead of time

### Export

#### HTML Report
1. Click the PDF/HTML export button (📊)
2. Enter report title, introduction, and conclusion
3. Select scope: Current Subplot, Current Tab, or All Tabs
4. Click Export to download interactive HTML

#### CSV Export
1. Click the CSV export button
2. Select scope and options
3. Download the CSV file

### Session Management

- **Save Session**: Click 💾 to save complete state as JSON
- **Load Session**: Upload a saved session file to restore state
- **Save Template**: Save layout and assignments without CSV paths
- **Load Template**: Apply a template to current session (requires compatible signals)

## Project Structure

```
SignalViewer_Python/
├── app.py                 # Main application (layout + callbacks)
├── config.py              # Configuration constants and themes
├── helpers.py             # Utility functions
├── data_manager.py        # CSV loading and data management
├── signal_operations.py   # Derived signal calculations
├── linking_manager.py     # Signal linking functionality
├── requirements.txt       # Python dependencies
├── assets/
│   └── custom.css        # Custom styling
└── uploads/              # Uploaded CSV storage
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Middle-click on tab | Close tab |
| Click on subplot | Select subplot |

## Configuration

Edit `config.py` to customize:
- `SIGNAL_COLORS`: Color palette for signal traces
- `APP_HOST`, `APP_PORT`: Server settings
- `MAX_ROWS`, `MAX_COLS`: Maximum subplot grid size
- Theme colors (dark/light)

## Troubleshooting

### Port Already in Use
```bash
# Find and kill process on port 8050
netstat -ano | findstr :8050
taskkill /PID <pid> /F
```

Or change port in `config.py`:
```python
APP_PORT = 8051
```

### Browser Doesn't Open
Navigate manually to: http://127.0.0.1:8050

### CSV Loading Issues
- Ensure UTF-8 encoding
- Verify numeric data (no text in data cells)
- Check column headers are valid

### Plot Not Updating
- Verify signals are assigned to the current subplot
- Check browser console (F12) for errors
- Try refreshing the page

## Requirements

See `requirements.txt` for full dependencies. Key packages:
- dash >= 2.0
- dash-bootstrap-components
- plotly >= 5.0
- pandas
- numpy

## License

See LICENSE file for details.

## Version History

- **v2.1**: HTML export with all tabs, subplot metadata, X-Y mode improvements
- **v2.0**: Template system, time cursor, X-Y plotting
- **v1.0**: Initial release with core functionality
