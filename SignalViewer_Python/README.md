# Signal Viewer - Python Version

A comprehensive signal analysis and visualization application built with Python, Plotly Dash, and Plotly.

This is a Python port of the MATLAB SignalViewerApp, providing equivalent functionality using modern web technologies.

## Features

### Core Functionality
- **Multi-CSV Support**: Load and manage multiple CSV files simultaneously
- **Signal Browser**: Tree-based signal selection with search functionality
- **Advanced Plotting**: Multiple tabs, subplots, and interactive Plotly plots
- **Signal Operations**: Derivative, integral, and mathematical operations (UI in progress)
- **Signal Linking**: Link related signals for synchronized analysis (UI in progress)
- **Session Management**: Save and load analysis sessions
- **Large File Support**: Optimized chunked reading for large CSV files

### Advanced Features
- **Cumulative Search**: Add multiple search terms to filter signals (OR logic)
- **Multiple Tabs**: Create and manage multiple plot tabs
- **Subplot Layout**: Customize rows and columns for subplots
- **Interactive Plots**: Zoom, pan, and hover for details
- **Signal Removal**: Remove signals from subplots
- **Auto-Scale**: Automatic plot scaling

## Installation

1. Install Python 3.8 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Running the Application

**Option 1: Run from Python (Recommended for Development)**
```bash
python app.py
```
The application will start on `http://127.0.0.1:8050` and the browser should open automatically.

**Option 2: Run the EXE (For End Users)**
1. Double-click `dist\SignalViewer.exe`
2. Wait 5-10 seconds for the server to start
3. Browser should open automatically to `http://127.0.0.1:8050`
4. If browser doesn't open, manually navigate to `http://127.0.0.1:8050`
5. **Important**: Keep the console window open (it's the server)

**Option 3: Build the EXE**
```bash
build_exe.bat
```
This creates `dist\SignalViewer.exe` using PyInstaller.

### Loading CSV Files

1. Use the file upload area at the top of the left panel
2. Drag and drop CSV files or click to select
3. Files will be automatically loaded and parsed
4. You can load multiple files at once or add files one by one

### CSV Format Requirements

- First column must be time data (named "Time")
- Subsequent columns are signal data
- Header row with column names
- Numeric data only

Example CSV format:
```csv
Time,Signal1,Signal2,Signal3
0.0,1.0,2.0,3.0
0.1,1.1,2.1,3.1
0.2,1.2,2.2,3.2
```

### Using the Signal Browser

1. **Search Signals**: Type in the search box to filter signals
   - Shows all signals by default
   - Filters as you type (current search + accumulated terms)
2. **Add to Filter List**: Click ➕ to add current search to accumulated list
3. **Apply Filter**: Click ✓ to apply all accumulated search terms
4. **Manage Searches**: Click ⋯ to view/remove accumulated searches
5. **Clear Filters**: Click 🔄 to clear all filters and show all signals
6. **Select Signals**: Check boxes next to signals to select them
7. **Assign to Plot**: Selected signals are automatically assigned to current subplot

### Plotting

- **Multiple Tabs**: Click ➕ to add new plot tabs
- **Delete Tabs**: Click 🗑️ to delete current tab (keeps at least one)
- **Subplots**: Each tab can have multiple subplots
- **Layout Control**: Set rows and columns, then click "Apply"
- **Interactive**: Zoom, pan, and hover for details
- **Legend**: Click legend items to show/hide signals
- **Remove Signals**: Select signals in "Signals in Current Subplot" and click "🗑️ Remove Selected"

### Session Management

- **Save Session**: Click 💾 to save current state to `session.json`
- **Load Session**: Click 📁 to load saved session
- Sessions include: CSV paths, signal assignments, accumulated searches, current tab/subplot

### Signal Operations (Coming Soon)

Access signal operations through the ⚙️ button:
- **Derivative**: Compute signal derivative
- **Integral**: Compute signal integral
- **Math Operations**: Add, subtract, multiply, divide signals

### CSV Linking (Coming Soon)

Link CSV nodes for synchronized analysis using the 🔗 button.

## Project Structure

```
SignalViewer_Python/
├── app.py                  # Main Dash application
├── data_manager.py         # CSV loading and data management
├── plot_manager.py         # Plotting and visualization
├── signal_operations.py    # Signal operations (derivative, integral, etc.)
├── linking_manager.py      # Signal linking functionality
├── config_manager.py       # Configuration and session management
├── utils.py                # Utility functions
├── requirements.txt        # Python dependencies
├── build_exe.spec         # PyInstaller spec file
├── build_exe.bat          # Build script for EXE
├── README.md              # This file
└── MISSING_FEATURES.md     # Features from MATLAB not yet implemented
```

## Architecture

The application follows a modular architecture:

- **DataManager**: Handles all CSV file operations, data loading, and streaming
- **PlotManager**: Manages plot creation, updates, and signal assignments
- **SignalOperationsManager**: Computes derived signals and operations
- **LinkingManager**: Handles signal linking and comparison
- **ConfigManager**: Manages sessions, templates, and configuration

## Building the EXE

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Run the build script:
```bash
build_exe.bat
```

3. The EXE will be created in `dist\SignalViewer.exe`

## Troubleshooting

### Port Already in Use
If you see "port 8050 already in use":
- Close other instances of the app
- Or change port in `app.py`: `app.run(port=8051, ...)`

### Browser Doesn't Open
- Manually open: http://127.0.0.1:8050
- Check firewall settings
- Try a different browser

### CSV Loading Issues
- Verify CSV format (first column = Time)
- Check file encoding (UTF-8 recommended)
- Ensure numeric data only

### Plot Not Updating
- Check browser console for errors (F12)
- Verify signals are assigned to subplot
- Check that data is loaded correctly

### Import Errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.8+)

## Requirements

- Python 3.8+
- See `requirements.txt` for full list of dependencies

## Differences from MATLAB Version

### Advantages
- **Web-based**: Access from any device with a browser
- **No MATLAB License**: Free and open-source
- **Modern UI**: Responsive web interface
- **Cross-platform**: Works on Windows, Mac, Linux

### Current Limitations
- Export to PDF/PPT/CSV not yet implemented (see MISSING_FEATURES.md)
- Signal properties dialog (scaling, colors, line widths) not yet implemented
- Some advanced signal operations UI needs completion
- CSV linking UI needs completion

## Notes

- The application creates `temp/`, `sessions/`, and `templates/` directories automatically
- Large CSV files (>200MB) are loaded in chunks for memory efficiency
- Plot data is automatically downsampled for datasets >50k points for performance
- The console window must stay open when running the EXE (it's the server)

## License

This is a Python port of the MATLAB SignalViewerApp. Please refer to the original project for licensing information.

## Contributing

This is a port of an existing MATLAB application. Contributions to improve functionality, add features, or fix bugs are welcome.
