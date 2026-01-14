# Signal Viewer Pro - Installation Guide

## Prerequisites

### Required
- **Python 3.10+** (tested with 3.12)
- **pip** (Python package manager)

### Recommended
- **Windows 10/11** (primary development platform)
- **4GB+ RAM** for large CSV files
- **Modern browser** (Chrome, Firefox, Edge)

---

## Installation Methods

### Method 1: Pre-built Executable (Recommended for Users)

1. Download `SignalViewer.zip` from releases
2. Extract to any folder
3. Run `SignalViewer.exe`
4. Open browser to `http://127.0.0.1:8050`

No Python installation required.

---

### Method 2: Run from Source (Development)

#### Step 1: Clone or Download Repository

```bash
git clone <repository-url>
cd SignalViewer/SignalViewer_Python
```

Or download and extract the ZIP.

#### Step 2: Create Virtual Environment

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Windows (CMD)
python -m venv venv
venv\Scripts\activate.bat

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

#### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 4: Run Application

```bash
python run.py
```

Or:

```bash
python app.py
```

#### Step 5: Open in Browser

Navigate to: `http://127.0.0.1:8050`

---

### Method 3: Build Executable (Distribution)

#### Step 1: Complete Method 2 setup

#### Step 2: Run Build Script

```bash
# Windows
build.bat
```

#### Step 3: Find Output

The executable will be in `dist/SignalViewer/SignalViewer.exe`

See `docs/RELEASE_CHECKLIST.md` for full release process.

---

## Offline Operation

Signal Viewer Pro is designed for **fully offline** operation:

- ✅ No internet connection required
- ✅ All CSS/JS bundled locally
- ✅ No CDN dependencies
- ✅ No telemetry or analytics

### Bundled Assets

All required files are in `assets/`:
- Bootstrap CSS (dark theme)
- Font Awesome icons
- Custom styling
- JavaScript helpers

---

## Troubleshooting

### Application Won't Start

1. **Check Python version**: `python --version` (need 3.10+)
2. **Check dependencies**: `pip list` (verify dash, plotly, pandas)
3. **Port conflict**: Try different port in `config.py`

### Browser Shows Blank Page

1. **Check console**: Open browser DevTools (F12)
2. **Check terminal**: Look for Python errors
3. **Hard refresh**: Ctrl+Shift+R to clear cache

### Large CSV Slow to Load

1. **Expected behavior**: First load parses entire file
2. **Subsequent loads**: Use cached data (faster)
3. **Memory**: Ensure adequate RAM for data size

### Session Won't Load

1. **Version mismatch**: Old sessions may not be compatible
2. **File moved**: CSV paths in session must be valid
3. **Corrupted JSON**: Check session file syntax

### Build Fails

1. **Dependencies**: Run `pip install pyinstaller`
2. **Anti-virus**: May block EXE creation
3. **Path issues**: Avoid special characters in path

---

## Configuration

Edit `config.py` for customization:

```python
# Server settings
HOST = "127.0.0.1"
PORT = 8050

# Debug mode (disable in production)
DEBUG = False

# Cache settings
CACHE_SIGNALS = True
```

---

## File Structure

```
SignalViewer_Python/
├── app.py              # Main application
├── run.py              # Entry point
├── config.py           # Configuration
├── helpers.py          # Utilities
├── callback_helpers.py # UI helpers
├── data_manager.py     # CSV handling
├── signal_operations.py # Math operations
├── requirements.txt    # Dependencies
├── build.bat           # Build script
├── SignalViewer.spec   # PyInstaller config
├── assets/             # CSS, JS, fonts
│   ├── custom.css
│   ├── collapse.js
│   ├── features.js
│   └── webfonts/
├── docs/               # Documentation
│   ├── INSTALLATION.md
│   ├── RELEASE_CHECKLIST.md
│   └── CLEANUP.md
└── uploads/            # Uploaded files
```

---

## Getting Help

1. Check this guide first
2. Review `UX_CHANGES.md` for feature documentation
3. Check terminal output for error messages
4. Open browser console (F12) for frontend errors

---

*Last updated: Following task.md Section 5 specifications*

