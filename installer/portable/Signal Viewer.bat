@echo off
rem Signal Viewer - double-click to start. Nothing to install, no internet needed.
cd /d "%~dp0"
start "" "%~dp0runtime\pythonw.exe" "%~dp0app\run.py"
