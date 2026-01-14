# Signal Viewer Pro - Release Checklist

## Pre-Release Preparation

### Version Bump
- [ ] Update version in `app.py` (search for `version` or `__version__`)
- [ ] Update version in `SignalViewer.spec` if present
- [ ] Update version in `setup.py` if present
- [ ] Update changelog/UX_CHANGES.md if applicable

### Code Review
- [ ] All linter warnings addressed
- [ ] No debug `print()` statements left (except PERF/CALLBACK)
- [ ] No hardcoded test file paths
- [ ] `DEBUG = False` in config.py

---

## Build Validation

### Clean Build
```bash
# 1. Clean previous build artifacts
rmdir /s /q build
rmdir /s /q dist

# 2. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 3. Install fresh dependencies
pip install -r requirements.txt

# 4. Run build
build.bat
```

### Build Output Check
- [ ] `dist/SignalViewer/SignalViewer.exe` exists
- [ ] `dist/SignalViewer/assets/` folder exists with all files
- [ ] `dist/SignalViewer/_internal/` contains Python runtime
- [ ] No build warnings about missing modules

---

## Offline Validation

### Test Without Internet
1. Disconnect from internet
2. Run `SignalViewer.exe`
3. Verify:
   - [ ] Application starts
   - [ ] UI loads correctly (no broken icons)
   - [ ] CSS themes work
   - [ ] No "CDN" or "fetch" errors in console

### Asset Check
- [ ] Font Awesome icons display correctly
- [ ] Bootstrap styling applies
- [ ] Custom CSS loads
- [ ] JavaScript features work (collapsible panels, etc.)

---

## Functional Smoke Tests

### Large CSV Test
1. Prepare a large CSV (1M+ rows or 100MB+)
2. Load the file
3. Verify:
   - [ ] File loads without crash
   - [ ] All signals visible in tree
   - [ ] Plot renders with all data points
   - [ ] Scrolling/zooming is responsive

### Session Save/Load Test
1. Load multiple CSV files
2. Assign signals to different subplots
3. Configure display options (colors, scales)
4. Save session
5. Close application, restart
6. Load session
7. Verify:
   - [ ] All CSV files re-loaded
   - [ ] Signal assignments preserved
   - [ ] Display options match
   - [ ] No error messages

### Naming Disambiguation Test
1. Load CSVs with same signal names
2. Assign overlapping signals
3. Verify:
   - [ ] Legend shows `signal — csv_name` format
   - [ ] No duplicate labels
4. Load CSVs with same filename from different folders
5. Verify:
   - [ ] Shows `parent/filename` format

### Export Test
1. Assign signals to plot
2. Export to CSV
3. Verify:
   - [ ] File created successfully
   - [ ] Column headers match UI labels
   - [ ] Data is complete (no truncation)

---

## Performance Sanity Check

### Console Output Review
- [ ] Figure build times < 500ms for typical plots
- [ ] No repeated full rebuilds on cursor movement
- [ ] Callback counts are reasonable

### Memory Check
- [ ] Memory usage stable over time
- [ ] No memory leaks with repeated file loads

---

## Package for Distribution

### Create ZIP Archive
```bash
cd dist
powershell Compress-Archive -Path SignalViewer -DestinationPath SignalViewer_v1.x.x.zip
```

### Archive Contents Verification
- [ ] SignalViewer.exe
- [ ] assets/ folder (complete)
- [ ] _internal/ folder (Python runtime)
- [ ] No venv/ or __pycache__/
- [ ] No source code (unless intended)

---

## Documentation Update

- [ ] README.md reflects current features
- [ ] UX_CHANGES.md is current
- [ ] INSTALLATION.md is accurate
- [ ] Version numbers consistent

---

## Git Release

### Commit Changes
```bash
git add .
git commit -m "Release vX.X.X - description"
```

### Tag Release
```bash
git tag -a vX.X.X -m "Version X.X.X release"
git push origin main --tags
```

### Create GitHub Release (if applicable)
- [ ] Upload ZIP file
- [ ] Write release notes
- [ ] Mark as latest release

---

## Post-Release

### Verify Download
- [ ] Download release from distribution point
- [ ] Extract and run on clean machine
- [ ] Verify basic functionality

### Update Issues/Tracking
- [ ] Close related issues
- [ ] Update project roadmap

---

## Quick Reference Commands

```bash
# Clean build
rmdir /s /q build && rmdir /s /q dist && build.bat

# Test run from source
python run.py

# Create distribution ZIP
cd dist && powershell Compress-Archive -Path SignalViewer -DestinationPath SignalViewer.zip

# Git release
git add . && git commit -m "Release vX.X.X" && git tag vX.X.X && git push --tags
```

---

*Last updated: Following task.md Section 5 specifications*

