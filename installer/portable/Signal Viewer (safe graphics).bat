@echo off
rem Safe graphics: draws without the graphics card - for a blank, white or black window
rem (old graphics drivers, virtual machines, remote desktop). Slower 3D, otherwise the same app.
cd /d "%~dp0"
start "" "%~dp0runtime\pythonw.exe" "%~dp0app\run.py" --safe-graphics
