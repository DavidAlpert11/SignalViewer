"""
PyInstaller hook for kaleido - required for offline Plotly image export.

Kaleido uses a bundled Chromium executable for rendering plots to images.
This hook ensures the kaleido executable is included in the build.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all kaleido data files (includes the chromium executable)
datas = collect_data_files('kaleido', include_py_files=True)

# Collect all submodules
hiddenimports = collect_submodules('kaleido')
