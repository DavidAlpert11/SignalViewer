@echo off
setlocal enabledelayedexpansion
REM ============================================
REM Signal Viewer Pro v2.5 - Build Script
REM ============================================
REM 
REM Usage:
REM   build.bat          - Full clean build
REM   build.bat fast     - Fast rebuild (skip deps)
REM   build.bat run      - Run without building
REM
REM Output:
REM   dist\SignalViewer\SignalViewer.exe
REM ============================================

echo.
echo ============================================
echo   Signal Viewer Pro - Build Script v2.5
echo ============================================
echo.

REM Parse arguments
set BUILD_MODE=full

if "%1"=="fast" (
    set BUILD_MODE=fast
    echo [MODE] Fast rebuild - skipping dependency check
) else if "%1"=="run" (
    echo [MODE] Run only - no build
    goto :RUN_APP
) else (
    echo [MODE] Full clean build
)
echo.

REM ============================================
REM Step 1: Check Python
REM ============================================
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo       Python %%v

REM ============================================
REM Step 2: Virtual Environment
REM ============================================
echo.
echo [2/5] Virtual environment...
if not exist "venv" (
    python -m venv venv
    if errorlevel 1 exit /b 1
    echo       Created venv
)
call venv\Scripts\activate.bat
echo       Activated

REM ============================================
REM Step 3: Dependencies
REM ============================================
echo.
echo [3/5] Dependencies...
if "%BUILD_MODE%"=="fast" (
    echo       Skipped ^(fast mode^)
) else (
    pip install -r requirements.txt -q
    pip install pyinstaller -q
    echo       Installed
)

REM ============================================
REM Step 4: Build
REM ============================================
echo.
echo [4/5] Building executable...
taskkill /F /IM SignalViewer.exe >nul 2>&1

if "%BUILD_MODE%"=="fast" (
    pyinstaller SignalViewer.spec --noconfirm
) else (
    if exist "build" rmdir /s /q "build"
    if exist "dist\SignalViewer" rmdir /s /q "dist\SignalViewer"
    pyinstaller SignalViewer.spec --clean --noconfirm
)

if errorlevel 1 (
    echo [ERROR] Build failed
    exit /b 1
)

if not exist "dist\SignalViewer\SignalViewer.exe" (
    echo [ERROR] Executable not found
    exit /b 1
)

REM ============================================
REM Step 5: Verify
REM ============================================
echo.
echo [5/5] Verifying...
if exist "dist\SignalViewer\_internal\assets\custom.css" (
    echo       Assets OK
) else (
    echo       [WARN] Assets may be missing
)

echo.
echo ============================================
echo   BUILD COMPLETE
echo ============================================
echo   Run: dist\SignalViewer\SignalViewer.exe
echo   URL: http://127.0.0.1:8050
echo ============================================
echo.
goto :END

:RUN_APP
echo Starting Signal Viewer Pro...
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat
python app.py
goto :END

:END
if not "%2"=="nopause" pause
