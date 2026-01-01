@echo off
REM ============================================
REM Signal Viewer Pro - Build Full Installer
REM ============================================
REM 
REM This script creates a professional Windows installer.
REM 
REM Prerequisites:
REM   1. Python 3.10+ with pip
REM   2. Inno Setup (https://jrsoftware.org/isdl.php)
REM 
REM Usage:
REM   build_installer.bat
REM
REM ============================================

echo.
echo ============================================
echo   Signal Viewer Pro - Installer Builder
echo ============================================
echo.

REM Step 1: Build the application with PyInstaller
echo Step 1: Building application...
call build.bat
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

REM Step 2: Check if Inno Setup is installed
echo.
echo Step 2: Checking for Inno Setup...

set ISCC_PATH=
REM Try common installation paths
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
)
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
)

if "%ISCC_PATH%"=="" (
    echo.
    echo WARNING: Inno Setup not found!
    echo.
    echo To create the installer, please:
    echo   1. Download Inno Setup from: https://jrsoftware.org/isdl.php
    echo   2. Install it
    echo   3. Run this script again
    echo.
    echo Alternatively, open installer.iss directly in Inno Setup Compiler.
    echo.
    echo The portable version is available in: dist\SignalViewer\
    echo.
    pause
    exit /b 0
)

REM Step 3: Create output directory
echo.
echo Step 3: Creating installer output directory...
if not exist "installer_output" mkdir installer_output

REM Step 4: Build the installer
echo.
echo Step 4: Building Windows installer...
echo Using: %ISCC_PATH%
echo.

"%ISCC_PATH%" installer.iss

if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup compilation failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   INSTALLER BUILD SUCCESSFUL!
echo ============================================
echo.
echo Output files:
echo   Portable:  dist\SignalViewer\SignalViewer.exe
echo   Installer: installer_output\SignalViewerProSetup-*.exe
echo.
echo To distribute:
echo   - Share the installer .exe for easy installation
echo   - Or share the dist\SignalViewer folder for portable use
echo.

pause
