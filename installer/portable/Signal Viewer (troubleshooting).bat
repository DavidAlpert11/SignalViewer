@echo off
rem Troubleshooting: starts with a console window that shows any error message.
cd /d "%~dp0"
"%~dp0runtime\python.exe" "%~dp0app\run.py"
echo.
echo The app has stopped. Any error is shown above. Log: %USERPROFILE%\.signalviewer\logs\signalviewer.log
pause
