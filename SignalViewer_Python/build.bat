@echo off
setlocal enabledelayedexpansion
REM ============================================
REM Signal Viewer Pro v4.0 - Build Script
REM ============================================
REM 
REM Usage:
REM   build.bat          - Full clean build
REM   build.bat fast     - Fast rebuild (skip deps)
REM   build.bat venv     - Create venv and install deps only
REM
REM Output:
REM   dist\SignalViewer\SignalViewer.exe
REM   SignalViewer.zip
REM ============================================

echo.
echo ============================================
echo   Signal Viewer Pro - Build Script v4.0
echo ============================================
echo.

REM Parse arguments
set BUILD_MODE=full
set CREATE_VENV_ONLY=0

if "%1"=="fast" (
    set BUILD_MODE=fast
    echo [MODE] Fast rebuild - skipping dependency installation
) else if "%1"=="venv" (
    set CREATE_VENV_ONLY=1
    echo [MODE] Virtual environment setup only
) else (
    echo [MODE] Full clean build
)
echo.

REM ============================================
REM Step 1: Check Python
REM ============================================
echo [1/7] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo         Please install Python 3.10+ and try again.
    echo         Download: https://www.python.org/downloads/
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo       Python %PYTHON_VERSION% found

REM ============================================
REM Step 2: Virtual Environment
REM ============================================
echo.
echo [2/7] Checking virtual environment...
if not exist "venv" (
    echo       Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
    echo       Virtual environment created
) else (
    echo       Virtual environment exists
)

REM Activate venv
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    exit /b 1
)
echo       Virtual environment activated

REM ============================================
REM Step 3: Install Dependencies
REM ============================================
echo.
echo [3/7] Installing dependencies...
if "%BUILD_MODE%"=="fast" (
    echo       Skipping in fast mode
) else (
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements
        exit /b 1
    )
    REM Additional optional dependencies
    pip install python-docx kaleido --quiet 2>nul
    echo       Dependencies installed
)

REM Check PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo       Installing PyInstaller...
    pip install pyinstaller==6.5.0
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller
        exit /b 1
    )
)

REM Exit if venv-only mode
if %CREATE_VENV_ONLY%==1 (
    echo.
    echo ============================================
    echo   VENV SETUP COMPLETE
    echo ============================================
    echo   To activate: venv\Scripts\activate.bat
    echo   To run: python run.py
    exit /b 0
)

REM ============================================
REM Step 4: Stop Running Instances
REM ============================================
echo.
echo [4/7] Stopping running instances...
taskkill /F /IM SignalViewer.exe >nul 2>&1
timeout /t 1 /nobreak >nul
echo       Done

REM ============================================
REM Step 5: Clean Build Directories
REM ============================================
echo.
echo [5/7] Cleaning build directories...
if "%BUILD_MODE%"=="fast" (
    if exist "dist\SignalViewer" (
        rmdir /s /q "dist\SignalViewer" 2>nul
        echo       Cleaned dist\SignalViewer
    )
) else (
    if exist "build" (
        rmdir /s /q "build" 2>nul
        echo       Cleaned build\
    )
    if exist "dist\SignalViewer" (
        rmdir /s /q "dist\SignalViewer" 2>nul
        echo       Cleaned dist\SignalViewer
    )
)
echo       Build directories ready

REM ============================================
REM Step 6: Build Executable
REM ============================================
echo.
echo [6/7] Building executable...
echo       This may take 1-3 minutes...

if "%BUILD_MODE%"=="fast" (
    pyinstaller SignalViewer.spec --noconfirm
) else (
    pyinstaller SignalViewer.spec --clean --noconfirm
)

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check errors above.
    exit /b 1
)

REM Verify build output
if not exist "dist\SignalViewer\SignalViewer.exe" (
    echo [ERROR] Build completed but SignalViewer.exe not found
    exit /b 1
)

REM Create uploads folder in dist
if not exist "dist\SignalViewer\uploads" mkdir "dist\SignalViewer\uploads"
echo       Build successful

REM ============================================
REM Step 7: Verify Assets (PyInstaller 6.x puts data in _internal)
REM ============================================
echo.
echo [7/7] Verifying offline assets...
set ASSETS_OK=1
set ASSETS_PATH=dist\SignalViewer\_internal\assets

if not exist "%ASSETS_PATH%\custom.css" (
    echo       [WARN] Missing: _internal\assets\custom.css
    set ASSETS_OK=0
)
if not exist "%ASSETS_PATH%\bootstrap-cyborg.min.css" (
    echo       [WARN] Missing: _internal\assets\bootstrap-cyborg.min.css
    set ASSETS_OK=0
)
if not exist "%ASSETS_PATH%\font-awesome.min.css" (
    echo       [WARN] Missing: _internal\assets\font-awesome.min.css
    set ASSETS_OK=0
)

if %ASSETS_OK%==1 (
    echo       All assets verified in _internal\assets
) else (
    echo       [WARN] Some assets may be missing - check offline operation
)

REM ============================================
REM Create Distribution ZIP
REM ============================================
echo.
echo Creating distribution archive...
if exist "SignalViewer.zip" del "SignalViewer.zip"
powershell -Command "Compress-Archive -Path 'dist\SignalViewer' -DestinationPath 'SignalViewer.zip' -Force"
if exist "SignalViewer.zip" (
    echo       Created: SignalViewer.zip
) else (
    echo       [WARN] Failed to create ZIP archive
)

REM ============================================
REM Build Complete
REM ============================================
echo.
echo ============================================
echo   BUILD COMPLETE
echo ============================================
echo.
echo   Executable: dist\SignalViewer\SignalViewer.exe
echo   Archive:    SignalViewer.zip
echo.
echo   To run: dist\SignalViewer\SignalViewer.exe
echo   Then open: http://127.0.0.1:8050
echo.
echo ============================================
echo.

REM Don't pause if running from script
if "%2"=="nopause" exit /b 0
pause
