@echo off
rem Creates a "Signal Viewer" shortcut with the app icon on the desktop.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\make_shortcut.ps1"
if errorlevel 1 (
  echo.
  echo The shortcut could not be created. The message above says why.
) else (
  echo Done. Double-click "Signal Viewer" on the desktop to start the app.
)
pause
