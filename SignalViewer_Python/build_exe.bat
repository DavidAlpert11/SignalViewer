@echo off
REM ============================================================================
REM Signal Viewer Pro - Build Script
REM ============================================================================
REM This script builds a standalone executable using PyInstaller.
REM 
REM Prerequisites:
REM   - Python 3.8+ installed
REM   - Virtual environment created: python -m venv venv
REM   - Dependencies installed: pip install -r requirements.txt
REM   - PyInstaller installed: pip install pyinstaller
REM ============================================================================

echo.
echo ============================================
echo   Signal Viewer Pro - Build Script
echo ============================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please create it first: python -m venv venv
    echo Then install dependencies: venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/4] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
echo [2/4] Cleaning previous builds...
if exist "build\SignalViewer" rmdir /s /q "build\SignalViewer"
if exist "dist\SignalViewer.exe" del /f "dist\SignalViewer.exe"

REM Build the executable
echo [3/4] Building executable (this may take several minutes)...
echo.

python -m PyInstaller ^
    --name SignalViewer ^
    --onefile ^
    --console ^
    --noconfirm ^
    --clean ^
    --hidden-import dash ^
    --hidden-import dash.dcc ^
    --hidden-import dash.html ^
    --hidden-import dash_bootstrap_components ^
    --hidden-import plotly ^
    --hidden-import plotly.graph_objects ^
    --hidden-import plotly.subplots ^
    --hidden-import pandas ^
    --hidden-import numpy ^
    --hidden-import scipy ^
    --hidden-import kaleido ^
    --hidden-import config ^
    --hidden-import helpers ^
    --hidden-import data_manager ^
    --hidden-import signal_operations ^
    --hidden-import linking_manager ^
    --collect-all dash ^
    --collect-all dash_bootstrap_components ^
    --collect-all plotly ^
    --add-data "assets;assets" ^
    app.py

echo.
echo [4/4] Build complete!
echo.

if exist "dist\SignalViewer.exe" (
    echo ============================================
    echo   BUILD SUCCESSFUL!
    echo ============================================
    echo.
    echo   Executable: dist\SignalViewer.exe
    echo.
    echo   To run: Double-click SignalViewer.exe
    echo   The app will open at http://127.0.0.1:8050
    echo ============================================
) else (
    echo ============================================
    echo   BUILD FAILED!
    echo ============================================
    echo   Check the error messages above.
    echo   Common issues:
    echo   - Missing dependencies: pip install -r requirements.txt
    echo   - Antivirus blocking: Add exception for this folder
    echo ============================================
)

echo.
pause
