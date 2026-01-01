@echo off
REM ============================================
REM Signal Viewer Pro v3.0 - Build Script
REM ============================================
REM 
REM Usage:
REM   build.bat        - Full clean build
REM   build.bat fast   - Fast rebuild (uses cached analysis)
REM
REM Features:
REM   - Fully offline (no internet required)
REM   - Native file browser
REM   - Streaming from original files
REM ============================================

echo.
echo ============================================
echo   Signal Viewer Pro v3.0 - Build Script
echo ============================================
echo.

REM Check for fast mode
set CLEAN_FLAG=--clean
set BUILD_MODE=Full Build
if "%1"=="fast" (
    set CLEAN_FLAG=
    set BUILD_MODE=Fast Rebuild
    echo Mode: FAST REBUILD ^(using cached analysis^)
) else (
    echo Mode: FULL BUILD ^(clean^)
)
echo.

REM Check if Python is installed
python --version
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

REM Kill any running SignalViewer.exe processes
echo.
echo Stopping any running SignalViewer instances...
taskkill /F /IM SignalViewer.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Create required folders
echo.
echo Creating required folders...
if not exist "uploads" mkdir uploads
if not exist "uploads\.cache" mkdir uploads\.cache

REM Install required packages (skip in fast mode)
if "%1"=="fast" (
    echo Skipping dependency installation in fast mode...
) else (
    echo.
    echo Installing/updating dependencies...
    pip install -r requirements.txt --quiet
    pip install jaraco.functools jaraco.context jaraco.text --quiet
    REM Word export support
    pip install python-docx --quiet
    REM Static image export
    pip install kaleido --quiet
)

REM Check if PyInstaller is installed
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller==6.5.0
)

REM Clean previous builds (only in full mode)
if "%1"=="fast" (
    echo.
    echo Cleaning dist folder only...
    powershell -Command "if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' -ErrorAction SilentlyContinue }"
) else (
    echo.
    echo Cleaning previous builds...
    powershell -Command "if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' -ErrorAction SilentlyContinue }"
    powershell -Command "if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' -ErrorAction SilentlyContinue }"
)
timeout /t 1 /nobreak >nul

REM Build the application
echo.
echo Building Signal Viewer Pro v3.0 (%BUILD_MODE%)...
if "%1"=="fast" (
    echo This should take about 1 minute...
) else (
    echo This may take 2-5 minutes...
)
echo.

pyinstaller SignalViewer.spec %CLEAN_FLAG% --noconfirm

if errorlevel 1 (
    echo.
    echo ============================================
    echo   BUILD FAILED!
    echo ============================================
    echo.
    echo Check the error messages above.
    echo Common fixes:
    echo   - Close any running SignalViewer.exe
    echo   - Close any File Explorer windows in dist folder
    echo   - Run: pip install -r requirements.txt
    echo   - Try full build: build.bat ^(without 'fast'^)
    echo.
    pause
    exit /b 1
)

REM Create uploads folder in dist
echo.
echo Setting up distribution folder...
if not exist "dist\SignalViewer\uploads" mkdir "dist\SignalViewer\uploads"
if not exist "dist\SignalViewer\uploads\.cache" mkdir "dist\SignalViewer\uploads\.cache"

REM Create ZIP file for distribution
echo.
echo Creating distribution ZIP file...
powershell -Command "if (Test-Path 'SignalViewer.zip') { Remove-Item 'SignalViewer.zip' -Force }"
powershell -Command "Compress-Archive -Path 'dist\SignalViewer' -DestinationPath 'SignalViewer.zip' -Force"

if errorlevel 1 (
    echo WARNING: Failed to create ZIP file
) else (
    echo ZIP file created: SignalViewer.zip
)

echo.
echo ============================================
echo   BUILD SUCCESSFUL!
echo ============================================
echo.
echo Output folder: dist\SignalViewer\
echo Executable:    dist\SignalViewer\SignalViewer.exe
echo ZIP file:      SignalViewer.zip
echo.
echo To run:
echo   cd dist\SignalViewer
echo   SignalViewer.exe
echo.
echo To distribute:
echo   Share the SignalViewer.zip file
echo   Users extract and run SignalViewer.exe
echo.
echo Features:
echo   - Fully OFFLINE (no internet needed)
echo   - Native file browser (Browse Files button)
echo   - Streaming from original file locations
echo.
echo TIP: Use "build.bat fast" for faster rebuilds!
echo.

pause
