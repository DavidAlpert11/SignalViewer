@echo off
REM Signal Viewer Pro - Run without console window
cd /d "%~dp0"

REM Try using Python launcher first (most reliable)
py -3 -m pip list >nul 2>&1
if %errorlevel% equ 0 (
    start "" py -3 app.py
    exit /b
)

REM Fallback: Try pythonw.exe in PATH
where pythonw.exe >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw.exe app.py
    exit /b
)

REM Fallback: Try python.exe in PATH
where python.exe >nul 2>&1
if %errorlevel% equ 0 (
    start "" python.exe app.py
    exit /b
)

REM If nothing worked, show error
echo Error: Python not found in PATH
echo Please install Python or add it to your system PATH
pause
