@echo off
REM ============================================
REM Signal Viewer Pro v3.0 - Build Script
REM ============================================
REM 
REM Usage:
REM   build.bat          - Build Dash (web) version
REM   build.bat tk       - Build Tkinter (native) version
REM   build.bat both     - Build both versions
REM   build.bat fast     - Fast rebuild Dash version
REM   build.bat tk fast  - Fast rebuild Tkinter version
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

REM Parse arguments
set BUILD_TK=0
set BUILD_DASH=1
set CLEAN_FLAG=--clean
set BUILD_MODE=Full Build

if "%1"=="tk" (
    set BUILD_TK=1
    set BUILD_DASH=0
    echo Target: TKINTER ^(Native GUI^)
    if "%2"=="fast" (
        set CLEAN_FLAG=
        set BUILD_MODE=Fast Rebuild
    )
) else if "%1"=="both" (
    set BUILD_TK=1
    set BUILD_DASH=1
    echo Target: BOTH VERSIONS
) else if "%1"=="fast" (
    set CLEAN_FLAG=
    set BUILD_MODE=Fast Rebuild
    echo Target: DASH ^(Web GUI^) - Fast
) else (
    echo Target: DASH ^(Web GUI^)
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
taskkill /F /IM SignalViewerTk.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Create required folders
echo.
echo Creating required folders...
if not exist "uploads" mkdir uploads
if not exist "uploads\.cache" mkdir uploads\.cache

REM Install required packages (skip in fast mode)
if "%BUILD_MODE%"=="Fast Rebuild" (
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

REM ============================================
REM Build Dash Version
REM ============================================
if %BUILD_DASH%==1 (
    echo.
    echo ============================================
    echo   Building DASH Version...
    echo ============================================
    
    if "%BUILD_MODE%"=="Fast Rebuild" (
        echo Cleaning dist folder only...
        powershell -Command "if (Test-Path 'dist\SignalViewer') { Remove-Item -Recurse -Force 'dist\SignalViewer' -ErrorAction SilentlyContinue }"
    ) else (
        echo Cleaning previous builds...
        powershell -Command "if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' -ErrorAction SilentlyContinue }"
        powershell -Command "if (Test-Path 'dist\SignalViewer') { Remove-Item -Recurse -Force 'dist\SignalViewer' -ErrorAction SilentlyContinue }"
    )
    timeout /t 1 /nobreak >nul
    
    echo Building Signal Viewer Pro - Dash Version...
    pyinstaller SignalViewer.spec %CLEAN_FLAG% --noconfirm
    
    if errorlevel 1 (
        echo.
        echo BUILD FAILED for Dash version!
        echo Check errors above.
    ) else (
        echo Dash version built successfully!
        if not exist "dist\SignalViewer\uploads" mkdir "dist\SignalViewer\uploads"
        if not exist "dist\SignalViewer\uploads\.cache" mkdir "dist\SignalViewer\uploads\.cache"
    )
)

REM ============================================
REM Build Tkinter Version
REM ============================================
if %BUILD_TK%==1 (
    echo.
    echo ============================================
    echo   Building TKINTER Version...
    echo ============================================
    
    if "%BUILD_MODE%"=="Fast Rebuild" (
        echo Cleaning dist folder only...
        powershell -Command "if (Test-Path 'dist\SignalViewerTk') { Remove-Item -Recurse -Force 'dist\SignalViewerTk' -ErrorAction SilentlyContinue }"
    ) else (
        powershell -Command "if (Test-Path 'dist\SignalViewerTk') { Remove-Item -Recurse -Force 'dist\SignalViewerTk' -ErrorAction SilentlyContinue }"
    )
    
    echo Building Signal Viewer Pro - Tkinter Version...
    
    REM Create spec file for Tkinter version if not exists
    if not exist "SignalViewerTk.spec" (
        echo Creating Tkinter spec file...
        pyinstaller --name SignalViewerTk ^
            --onedir ^
            --windowed ^
            --icon=assets/icon.ico ^
            --add-data "assets;assets" ^
            --hidden-import=matplotlib ^
            --hidden-import=matplotlib.backends.backend_tkagg ^
            --hidden-import=pandas ^
            --hidden-import=numpy ^
            --collect-all matplotlib ^
            app_tk.py
    ) else (
        pyinstaller SignalViewerTk.spec %CLEAN_FLAG% --noconfirm
    )
    
    if errorlevel 1 (
        echo.
        echo BUILD FAILED for Tkinter version!
        echo Check errors above.
    ) else (
        echo Tkinter version built successfully!
        if not exist "dist\SignalViewerTk\uploads" mkdir "dist\SignalViewerTk\uploads"
    )
)

REM Create ZIP files for distribution
echo.
echo Creating distribution ZIP files...

if %BUILD_DASH%==1 (
    if exist "dist\SignalViewer" (
        powershell -Command "if (Test-Path 'SignalViewer.zip') { Remove-Item 'SignalViewer.zip' -Force }"
        powershell -Command "Compress-Archive -Path 'dist\SignalViewer' -DestinationPath 'SignalViewer.zip' -Force"
        echo Created: SignalViewer.zip ^(Dash/Web version^)
    )
)

if %BUILD_TK%==1 (
    if exist "dist\SignalViewerTk" (
        powershell -Command "if (Test-Path 'SignalViewerTk.zip') { Remove-Item 'SignalViewerTk.zip' -Force }"
        powershell -Command "Compress-Archive -Path 'dist\SignalViewerTk' -DestinationPath 'SignalViewerTk.zip' -Force"
        echo Created: SignalViewerTk.zip ^(Tkinter/Native version^)
    )
)

echo.
echo ============================================
echo   BUILD COMPLETE!
echo ============================================
echo.
if %BUILD_DASH%==1 (
    echo DASH Version:
    echo   Folder:     dist\SignalViewer\
    echo   Executable: dist\SignalViewer\SignalViewer.exe
    echo   ZIP:        SignalViewer.zip
    echo.
)
if %BUILD_TK%==1 (
    echo TKINTER Version:
    echo   Folder:     dist\SignalViewerTk\
    echo   Executable: dist\SignalViewerTk\SignalViewerTk.exe
    echo   ZIP:        SignalViewerTk.zip
    echo.
)
echo Usage:
echo   build.bat       - Build Dash version
echo   build.bat tk    - Build Tkinter version  
echo   build.bat both  - Build both versions
echo   build.bat fast  - Fast rebuild
echo.

pause
