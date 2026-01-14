# Signal Viewer Pro

A professional signal analysis and visualization tool built with Python and Dash.

## Features

- **Multi-CSV Support** - Load and visualize signals from multiple CSV files
- **Canonical Naming** - Automatic disambiguation of signals with same names (N1-N4)
- **Multi-Subplot Layouts** - Up to 4×4 subplot grid
- **Lossless Visualization** - All data points displayed, no downsampling
- **Offline Operation** - No internet required, all assets bundled
- **Interactive Cursor** - Time cursor with value readout
- **Dark/Light Themes** - Toggle between themes
- **Session Save/Load** - Save and restore your analysis sessions
- **CSV Export** - Export visible data to CSV

## Quick Start

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Installation

```bash
# Clone or download the repository
cd SignalViewer_Python

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

Then open http://127.0.0.1:8050 in your browser.

### Using the Executable

1. Download `SignalViewer.zip` from releases
2. Extract to any folder
3. Run `SignalViewer.exe`
4. Open http://127.0.0.1:8050

## Usage

1. **Load CSV** - Click "📂 Load CSV" to select CSV files
2. **Browse Signals** - Signals appear in the tree, grouped by CSV
3. **Assign Signals** - Click a signal to assign it to the current subplot
4. **Change Layout** - Use the Rows/Cols selectors to create subplots
5. **Use Cursor** - Enable the cursor switch to see values at a specific time
6. **Save Session** - Click "💾 Save" to save your current setup

## CSV Format

CSV files should have:
- First column: Time (or any numeric column as time base)
- Remaining columns: Signal values (numeric)

Example:
```csv
Time,Speed,Temperature,Pressure
0.0,0,25.0,101.3
0.1,10,25.1,101.2
0.2,20,25.2,101.1
```

## Naming Rules

### N1 - Same Signal Names Across CSVs
When signals have the same name in different CSVs, they are displayed as:
- `signal — csv_name` (e.g., `RPM — data1`)

### N2 - Same CSV Filenames
When CSVs have the same filename from different folders:
- `folder/filename.csv` (e.g., `run1/data.csv`)

## Building

```bash
# Windows
build.bat
```

Output: `dist/SignalViewer/SignalViewer.exe`

## Project Structure

```
SignalViewer_Python/
├── app.py              # Main application (~600 lines)
├── config.py           # Configuration and constants
├── data_manager.py     # CSV loading and caching
├── helpers.py          # Utility functions
├── run.py              # Entry point
├── requirements.txt    # Python dependencies
├── build.bat           # Build script
├── SignalViewer.spec   # PyInstaller config
├── assets/             # CSS, JS, fonts (offline)
├── docs/               # Documentation
└── signals.csv         # Sample data
```

## License

See LICENSE file.
