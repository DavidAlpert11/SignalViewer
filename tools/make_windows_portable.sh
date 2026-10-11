#!/bin/sh
# Builds the Windows portable package on Linux / macOS (no Windows PC needed):
#     ./tools/make_windows_portable.sh            ->  dist/SignalViewer-Windows-portable.7z
#     ./tools/make_windows_portable.sh --format zip
# Same builder as build_windows_portable.bat on Windows (tools/make_windows_portable.py): the official
# embeddable Python + the official Windows builds of every library + the app. Options are passed on.
cd "$(dirname "$0")/.." || exit 1
exec python3 tools/make_windows_portable.py "$@"
