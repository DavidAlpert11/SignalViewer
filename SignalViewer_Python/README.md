# Signal Viewer Pro

A modern, feature-rich signal visualization tool for analyzing time-series and correlation data from CSV files.

## Features

- **Multi-CSV Loading** - Load multiple CSV files with automatic duplicate handling
- **Multi-Tab Layout** - Up to 4x4 grid of subplots per tab
- **Interactive Time Cursor** - Synchronized value display across all subplots
- **Signal Customization** - Color, scale, line width, display name
- **X-Y Plot Mode** - Signal correlation analysis
- **Derived Signals** - Derivative, integral, custom math operations
- **Multi-Signal Operations** - Average, sum, difference, etc.
- **Session Save/Load** - Full state persistence
- **Export** - HTML reports, CSV data export

---

## Installation

### Prerequisites

- **Python 3.10+** (tested with Python 3.12)
- **pip** (Python package manager)

### Step 1: Install Dependencies

```powershell
cd SignalViewer_Python
pip install -r requirements.txt
```

### Step 2: Install Additional Build Dependencies

If you plan to build the executable:

```powershell
pip install pyinstaller==6.5.0
pip install jaraco.functools jaraco.context jaraco.text
```

---

## Running the Application

### Option 1: Run from Python (Development)

```powershell
cd SignalViewer_Python
python run.py
```

The application will start and automatically open your browser to `http://127.0.0.1:8050`

### Option 2: Run the Executable (Production)

After building (see below), navigate to the output folder:

```powershell
cd dist\SignalViewer
SignalViewer.exe
```

---

## Building the Executable

### Step 1: Clean Previous Builds

```powershell
cd SignalViewer_Python
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
```

### Step 2: Build

```powershell
pyinstaller SignalViewer.spec --clean --noconfirm
```

This takes 2-5 minutes depending on your system.

### Step 3: Verify Output

After successful build, you'll find:

```
dist/
└── SignalViewer/
    ├── SignalViewer.exe      # Main executable
    ├── _internal/            # Python runtime & packages
    ├── assets/               # CSS files
    └── uploads/              # User data folder
```

### Step 4: Test

```powershell
cd dist\SignalViewer
.\SignalViewer.exe
```

### Step 5: (Optional) Disable Console Window

After confirming everything works, edit `SignalViewer.spec` and change:

```python
console=True,   # Change to False
```

Then rebuild to create a version without the console window.

---

## Distribution

To distribute the application:

1. Copy the entire `dist\SignalViewer\` folder
2. Users can run `SignalViewer.exe` directly - no Python installation required
3. Optionally, create a shortcut to `SignalViewer.exe`

---

## Usage Guide

### Loading Data

1. Click **"Upload CSV"** or drag & drop CSV files
2. Select the time column for each CSV (if not auto-detected)
3. Signals appear in the left panel

### Adding Signals to Plots

1. Select a subplot tab (Tab 1, Tab 2, etc.)
2. Select subplot position (1x1, 1x2, etc.)
3. Check signals from the left panel to add them

### Customizing Signals

- **Color**: Click the color picker next to each signal
- **Scale**: Adjust the scale factor
- **Line Width**: Change line thickness
- **Display Name**: Rename signals for clarity

### Using the Time Cursor

- Click on any plot to place the cursor
- Values at cursor position show in the info panel
- Cursor syncs across all subplots

### Creating Derived Signals

1. Go to **Signal Operations** panel
2. Select operation type (derivative, integral, etc.)
3. Choose source signal(s)
4. Click **Create**

### Saving/Loading Sessions

- **Save Session**: File → Save Session (saves all data and settings)
- **Load Session**: File → Load Session
- **Save Template**: Saves layout without data (reusable across sessions)

### Exporting

- **HTML Report**: Exports interactive HTML with all plots
- **CSV Export**: Exports signal data to CSV file

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'xxx'"

Install the missing module:
```powershell
pip install xxx
```

### Build fails with numpy errors

Ensure you have compatible versions:
```powershell
pip install numpy==1.26.2 pandas==2.1.4
```

### Executable won't start

1. Make sure no other instance is running
2. Check if port 8050 is available
3. Run from command line to see error messages:
   ```powershell
   cd dist\SignalViewer
   .\SignalViewer.exe
   ```

### "Access denied" when deleting dist folder

Close any running SignalViewer.exe first:
```powershell
taskkill /F /IM SignalViewer.exe
```

---

## Project Structure

```
SignalViewer_Python/
├── app.py                 # Main application (Dash app)
├── run.py                 # Entry point for executable
├── config.py              # Configuration constants
├── config_manager.py      # Settings management
├── data_manager.py        # CSV data handling
├── helpers.py             # Utility functions
├── linking_manager.py     # Signal linking logic
├── plot_manager.py        # Plot generation
├── signal_operations.py   # Derived signal calculations
├── utils.py               # Additional utilities
├── SignalViewer.spec      # PyInstaller configuration
├── build.bat              # Windows build script
├── runtime_hook.py        # PyInstaller runtime fixes
├── requirements.txt       # Python dependencies
├── assets/
│   └── custom.css         # Custom styling
├── hooks/
│   └── hook-numpy.py      # Custom PyInstaller hook
└── uploads/
    └── .gitkeep           # User uploads folder
```

---

## Requirements

See `requirements.txt` for full list:

- dash
- dash-bootstrap-components
- plotly
- pandas
- numpy
- scipy
- kaleido
- openpyxl
- reportlab
- python-pptx
- watchdog

---

## License

Internal use only.

---

## Version

**2.1** - Signal Viewer Pro
