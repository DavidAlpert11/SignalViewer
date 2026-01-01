# 📦 Signal Viewer Pro - Installation & Distribution Guide

Complete guide for installing, packaging, and distributing Signal Viewer Pro like PlotJuggler.

---

## 🎯 Distribution Methods

Signal Viewer Pro can be distributed in **5 ways**, just like PlotJuggler:

1. ✅ **PyPI Package** (pip install)
2. ✅ **Windows Executable** (.exe)
3. ✅ **Source Code** (GitHub)
4. ✅ **Docker Container**
5. ✅ **AppImage** (Linux)

---

## 📦 Method 1: PyPI Package (Recommended)

### For Users - Install from PyPI

```bash
pip install signal-viewer-pro
```

Then run:
```bash
signal-viewer
```

### For Developers - Publish to PyPI

#### Step 1: Prepare Package

Create these files:
- ✅ `setup.py` (package configuration)
- ✅ `requirements.txt` (dependencies)
- ✅ `MANIFEST.in` (include assets)
- ✅ `README.md` (documentation)
- ✅ `LICENSE` (MIT license)

#### Step 2: Build Package

```bash
# Install build tools
pip install build twine

# Build distribution packages
python -m build

# This creates:
# - dist/signal-viewer-pro-2.1.0.tar.gz (source)
# - dist/signal_viewer_pro-2.1.0-py3-none-any.whl (wheel)
```

#### Step 3: Test Locally

```bash
# Install from local build
pip install dist/signal_viewer_pro-2.1.0-py3-none-any.whl

# Test
signal-viewer
```

#### Step 4: Upload to PyPI

```bash
# Upload to Test PyPI first (recommended)
twine upload --repository testpypi dist/*

# Test install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ signal-viewer-pro

# Upload to real PyPI
twine upload dist/*
```

**PyPI Credentials**: You'll need an account at https://pypi.org

---

## 💻 Method 2: Windows Executable

### Create Standalone .exe (Like PlotJuggler Windows Release)

#### Step 1: Install PyInstaller

```bash
pip install pyinstaller
```

#### Step 2: Create Executable

**Option A: Simple (One File)**
```bash
pyinstaller --onefile --windowed --name SignalViewerPro app.py
```

**Option B: Advanced (Using .spec file)**
```bash
pyinstaller SignalViewerPro.spec
```

The `.spec` file gives you control over:
- Icon
- Hidden imports
- Data files (assets)
- Console vs windowed mode

#### Step 3: Find Your Executable

```
dist/
└── SignalViewerPro.exe  (Ready to distribute!)
```

#### Step 4: Create Installer (Optional)

Use **Inno Setup** or **NSIS** to create a professional installer:

```
SignalViewerProSetup.exe
├── Installs to Program Files
├── Creates desktop shortcut
├── Adds to Start Menu
└── Creates uninstaller
```

**Example Inno Setup Script:**
```iss
[Setup]
AppName=Signal Viewer Pro
AppVersion=2.1.0
DefaultDirName={pf}\SignalViewerPro
DefaultGroupName=Signal Viewer Pro
OutputBaseFilename=SignalViewerProSetup

[Files]
Source: "dist\SignalViewerPro.exe"; DestDir: "{app}"
Source: "assets\*"; DestDir: "{app}\assets"; Flags: recursesubdirs

[Icons]
Name: "{group}\Signal Viewer Pro"; Filename: "{app}\SignalViewerPro.exe"
Name: "{commondesktop}\Signal Viewer Pro"; Filename: "{app}\SignalViewerPro.exe"
```

---

## 🐧 Method 3: AppImage (Linux)

### Create Linux AppImage (Like PlotJuggler Linux Release)

#### Step 1: Install Tools

```bash
# Download appimagetool
wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
```

#### Step 2: Create AppDir Structure

```bash
mkdir -p SignalViewerPro.AppDir/usr/bin
mkdir -p SignalViewerPro.AppDir/usr/share/applications
mkdir -p SignalViewerPro.AppDir/usr/share/icons

# Copy application files
cp -r . SignalViewerPro.AppDir/usr/bin/

# Create desktop entry
cat > SignalViewerPro.AppDir/usr/share/applications/signal-viewer.desktop << EOF
[Desktop Entry]
Type=Application
Name=Signal Viewer Pro
Exec=signal-viewer
Icon=signal-viewer
Categories=Science;DataVisualization;
EOF

# Create AppRun script
cat > SignalViewerPro.AppDir/AppRun << 'EOF'
#!/bin/bash
APPDIR=$(dirname $(readlink -f $0))
export PATH=$APPDIR/usr/bin:$PATH
export PYTHONPATH=$APPDIR/usr/bin:$PYTHONPATH
cd $APPDIR/usr/bin
python3 app.py
EOF

chmod +x SignalViewerPro.AppDir/AppRun
```

#### Step 3: Build AppImage

```bash
./appimagetool-x86_64.AppImage SignalViewerPro.AppDir SignalViewerPro-2.1.0-x86_64.AppImage
```

#### Step 4: Distribute

```
SignalViewerPro-2.1.0-x86_64.AppImage  (Single file, ready to run!)
```

Users just:
```bash
chmod +x SignalViewerPro-2.1.0-x86_64.AppImage
./SignalViewerPro-2.1.0-x86_64.AppImage
```

---

## 🐳 Method 4: Docker Container

### Create Docker Image

#### Step 1: Build Image

```bash
docker build -t signal-viewer-pro:2.1.0 .
```

#### Step 2: Run Container

```bash
docker run -p 8050:8050 signal-viewer-pro:2.1.0
```

#### Step 3: Push to Docker Hub

```bash
# Tag image
docker tag signal-viewer-pro:2.1.0 yourusername/signal-viewer-pro:2.1.0
docker tag signal-viewer-pro:2.1.0 yourusername/signal-viewer-pro:latest

# Push
docker push yourusername/signal-viewer-pro:2.1.0
docker push yourusername/signal-viewer-pro:latest
```

Users can then:
```bash
docker pull yourusername/signal-viewer-pro
docker run -p 8050:8050 yourusername/signal-viewer-pro
```

---

## 💾 Method 5: Source Code (GitHub)

### Setup GitHub Repository

#### Step 1: Create Repository

1. Go to https://github.com/new
2. Name: `signal-viewer-pro`
3. Description: "Professional signal visualization tool"
4. Add README, .gitignore, LICENSE (MIT)

#### Step 2: Push Code

```bash
git init
git add .
git commit -m "Initial commit - Signal Viewer Pro v2.1.0"
git branch -M main
git remote add origin https://github.com/yourusername/signal-viewer-pro.git
git push -u origin main
```

#### Step 3: Create Release

1. Go to Releases → Create New Release
2. Tag: `v2.1.0`
3. Title: `Signal Viewer Pro v2.1.0`
4. Attach binaries:
   - `SignalViewerPro.exe` (Windows)
   - `SignalViewerPro-2.1.0-x86_64.AppImage` (Linux)
   - `signal-viewer-pro-2.1.0.tar.gz` (Source)

#### Step 4: Add Documentation

Create GitHub Wiki pages:
- Installation
- Usage Guide
- API Reference
- FAQ

---

## 📋 Complete Release Checklist

### Pre-Release

- [ ] Update version in `setup.py`, `app.py`, `README.md`
- [ ] Update CHANGELOG.md
- [ ] Run tests: `pytest tests/`
- [ ] Check code style: `black .` and `flake8 .`
- [ ] Update documentation

### Build Packages

- [ ] PyPI package: `python -m build`
- [ ] Windows .exe: `pyinstaller SignalViewerPro.spec`
- [ ] Linux AppImage: `appimagetool SignalViewerPro.AppDir`
- [ ] Docker image: `docker build -t signal-viewer-pro:X.X.X .`

### Test Packages

- [ ] Test PyPI install: `pip install dist/*.whl`
- [ ] Test Windows .exe on clean Windows machine
- [ ] Test AppImage on clean Linux machine
- [ ] Test Docker image: `docker run -p 8050:8050 ...`

### Publish

- [ ] Upload to PyPI: `twine upload dist/*`
- [ ] Push Docker image: `docker push ...`
- [ ] Create GitHub Release with binaries
- [ ] Update website/documentation

### Post-Release

- [ ] Announce on social media
- [ ] Post to relevant communities (Reddit, forums)
- [ ] Update package managers (conda, brew, etc.)
- [ ] Monitor for issues

---

## 🎯 PlotJuggler-Style Distribution

To match PlotJuggler's approach:

### GitHub Releases Page

Create releases with:
```
SignalViewerPro-2.1.0-Windows-x64.exe          (Windows installer)
SignalViewerPro-2.1.0-Windows-x64-portable.exe (Portable .exe)
SignalViewerPro-2.1.0-Linux-x86_64.AppImage    (Linux)
SignalViewerPro-2.1.0-macOS.dmg                (macOS - if supported)
Source-code.zip                                 (Source)
Source-code.tar.gz                              (Source)
```

### Package Manager Support

**Windows:**
```bash
# Chocolatey
choco install signal-viewer-pro

# Scoop
scoop install signal-viewer-pro
```

**Linux:**
```bash
# Snap
snap install signal-viewer-pro

# Flatpak
flatpak install signal-viewer-pro
```

**macOS:**
```bash
# Homebrew
brew install signal-viewer-pro
```

---

## 🚀 Quick Commands Reference

### Build Everything

```bash
# PyPI package
python -m build

# Windows executable
pyinstaller SignalViewerPro.spec

# Docker image
docker build -t signal-viewer-pro:latest .

# Linux AppImage
./appimagetool-x86_64.AppImage SignalViewerPro.AppDir
```

### Publish Everything

```bash
# PyPI
twine upload dist/*

# Docker
docker push yourusername/signal-viewer-pro:latest

# GitHub Release (manual upload via web interface)
```

---

## 📞 Support

For help with distribution:
- **PyPI**: https://packaging.python.org/
- **PyInstaller**: https://pyinstaller.org/
- **Docker**: https://docs.docker.com/
- **AppImage**: https://appimage.org/

---

**Your Signal Viewer Pro is now ready for professional distribution!** 🎉
