@echo off
setlocal enabledelayedexpansion
rem ===========================================================================
rem  Signal Viewer - build for Windows. The RESULT needs no Python, no packages
rem  and no internet. Only this build step needs Python 3.10+ (and, without a
rem  "wheels" folder, internet to install the libraries once).
rem
rem    build.bat installer   -> dist\SignalViewer-Setup-1.4.0.exe   (recommended: one file, installs
rem                                                                    with Start menu / desktop icons)
rem    build.bat portable    -> dist\SignalViewer-portable.zip      (unzip anywhere, run SignalViewer.exe)
rem    build.bat onefile     -> dist\SignalViewer.exe               (single file; starts a few seconds slower)
rem    build.bat all         -> all three
rem    build.bat wheels      -> download every library into .\wheels (run once on a connected PC; copy the
rem                             project with .\wheels to an offline PC and build there)
rem ===========================================================================
cd /d "%~dp0"
set MODE=%1
if "%MODE%"=="" set MODE=installer
set VERSION=1.4.0

where python >nul 2>nul || (echo Python 3.10+ is needed to BUILD ^(not to run the result^). & exit /b 1)

if "%MODE%"=="wheels" (
  python -m pip download -r requirements.txt pyinstaller -d wheels || exit /b 1
  echo Libraries saved in .\wheels - copy the whole folder to the offline PC and run build.bat there.
  exit /b 0
)

rem --- build environment (isolated, so the user's Python is not touched)
if not exist .buildenv\Scripts\python.exe python -m venv .buildenv || exit /b 1
set PY=.buildenv\Scripts\python.exe
if exist wheels (
  echo Installing libraries from .\wheels ^(offline^)
  %PY% -m pip install --no-index --find-links wheels -r requirements.txt pyinstaller || exit /b 1
) else (
  %PY% -m pip install --upgrade pip >nul
  %PY% -m pip install -r requirements.txt pyinstaller || exit /b 1
)

rem --- the UI is already built (frontend\dist); rebuild only with: build.bat <mode> --ui  (needs Node.js)
if "%2"=="--ui" (pushd frontend & call npm ci & call npm run build & popd)
if not exist frontend\dist\index.html (echo frontend\dist is missing. Run with --ui ^(needs Node.js^). & exit /b 1)

if /i "%MODE%"=="onefile" goto onefile
if /i "%MODE%"=="all" call :onefile_sub || exit /b 1

rem --- folder build (installer and portable use it)
set SV_ONEFILE=
%PY% -m PyInstaller SignalViewer.spec --noconfirm || exit /b 1

if /i "%MODE%"=="portable" goto portable
if /i "%MODE%"=="all" call :portable_sub

rem --- installer (Inno Setup 6: free, https://jrsoftware.org - only needed on the build PC)
set ISCC=
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set ISCC=%%P
if "%ISCC%"=="" (
  echo.
  echo Inno Setup 6 was not found, so no installer was made.
  echo Install it once from https://jrsoftware.org/isdl.php, or use: build.bat portable
  exit /b 1
)
%ISCC% /Qp /DAppVersion=%VERSION% installer\SignalViewer.iss || exit /b 1
echo.
echo Done: dist\SignalViewer-Setup-%VERSION%.exe
exit /b 0

:portable
call :portable_sub
exit /b 0
:portable_sub
if exist dist\SignalViewer-portable.zip del dist\SignalViewer-portable.zip
powershell -NoProfile -Command "Compress-Archive -Path dist\SignalViewer -DestinationPath dist\SignalViewer-portable.zip" || exit /b 1
echo Done: dist\SignalViewer-portable.zip  ^(unzip, run SignalViewer\SignalViewer.exe^)
exit /b 0

:onefile
call :onefile_sub
exit /b %errorlevel%
:onefile_sub
set SV_ONEFILE=1
%PY% -m PyInstaller SignalViewer.spec --noconfirm --distpath dist\onefile || exit /b 1
set SV_ONEFILE=
move /y dist\onefile\SignalViewer.exe dist\SignalViewer.exe >nul
echo Done: dist\SignalViewer.exe
exit /b 0
