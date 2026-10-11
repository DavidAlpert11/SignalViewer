@echo off
rem ===========================================================================
rem  Builds the Windows portable package: dist\SignalViewer-Windows-portable.7z
rem  (7-Zip is used when installed; otherwise a small Python library is fetched once.)
rem  For a .zip instead:  build_windows_portable.bat --format zip
rem  Needs on THIS PC (to build only): Python 3.8+ with pip, and internet (about 150 MB, once).
rem  The result needs neither. Extra options are passed on, e.g.:  build_windows_portable.bat --keep-folder
rem ===========================================================================
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython
%PY% -c "import sys, pip; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if errorlevel 1 goto nopython

if not exist "tools\make_windows_portable.py" (
  echo.
  echo tools\make_windows_portable.py was not found. Run this file from the project's main folder.
  pause
  exit /b 1
)

%PY% tools\make_windows_portable.py %*
if errorlevel 1 (
  echo.
  echo The build failed. The message above says why.
) else (
  echo.
  echo Finished. The package is in the dist folder.
)
pause
exit /b %errorlevel%

:nopython
echo.
echo Python 3.8 or newer with pip was not found. Install it from https://www.python.org/downloads/
echo ^(tick "Add python.exe to PATH"^), then run this file again. Python is needed only to BUILD the package.
pause
exit /b 1
