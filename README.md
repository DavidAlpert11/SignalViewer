# Signal Viewer Pro

A modern, feature-rich signal visualization tool for analyzing time-series and correlation data from CSV files.

## Branches

| Branch | Description |
|--------|-------------|
| `main` | Python/Dash web application |
| `matlab` | MATLAB desktop application |

## Python Application

The main application is located in `SignalViewer_Python/`.

### Quick Start

```powershell
cd SignalViewer_Python
pip install -r requirements.txt
python run.py
```

### Build Executable

```powershell
cd SignalViewer_Python
.\build.bat
```

See [SignalViewer_Python/README.md](SignalViewer_Python/README.md) for full documentation.

## Features

- Multi-CSV loading with automatic duplicate handling
- Multi-tab, multi-subplot layouts (up to 4x4 grid per tab)
- Interactive time cursor with synchronized value display
- Signal customization (color, scale, line width, display name)
- X-Y plot mode for signal correlation analysis
- Derived signals (derivative, integral, custom math operations)
- Session save/load with full state persistence
- HTML report export

## Distribution

Pre-built executable: Download `SignalViewer.zip` from the Python folder, extract, and run `SignalViewer.exe`.
