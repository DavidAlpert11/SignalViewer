#!/usr/bin/env bash
# Signal Viewer - build on Linux / macOS. The result needs no Python and no internet.
#   ./build.sh            -> dist/SignalViewer/  (folder) + dist/SignalViewer-portable.tar.gz
#   ./build.sh onefile    -> dist/SignalViewer   (single file)
#   ./build.sh wheels     -> download every library into ./wheels (for an offline build machine)
set -e
cd "$(dirname "$0")"
MODE="${1:-portable}"
if [ "$MODE" = "wheels" ]; then python3 -m pip download -r requirements.txt pyinstaller -d wheels; exit 0; fi
[ -x .buildenv/bin/python ] || python3 -m venv .buildenv
PY=.buildenv/bin/python
if [ -d wheels ]; then $PY -m pip install --no-index --find-links wheels -r requirements.txt pyinstaller
else $PY -m pip install -r requirements.txt pyinstaller; fi
# the UI (frontend/dist) is not kept in git (FR10): built when missing, or again with --ui (needs Node.js)
if [ "$2" = "--ui" ] || [ ! -f frontend/dist/index.html ]; then
  command -v npm >/dev/null || { echo "The UI is not built and Node.js is not installed: install Node.js LTS (nodejs.org)."; exit 1; }
  (cd frontend && npm ci && npm run build) || exit 1
fi
if [ "$MODE" = "onefile" ]; then
  SV_ONEFILE=1 $PY -m PyInstaller SignalViewer.spec --noconfirm
else
  $PY -m PyInstaller SignalViewer.spec --noconfirm
  tar -czf dist/SignalViewer-portable.tar.gz -C dist SignalViewer
  echo "Done: dist/SignalViewer/SignalViewer and dist/SignalViewer-portable.tar.gz"
fi
