"""
PyInstaller hook for plotly - required for offline HTML export.

Ensures plotly.js and all required files are bundled.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect plotly data files (includes plotly.min.js for offline use)
datas = collect_data_files('plotly', include_py_files=False)

# Collect all submodules
hiddenimports = collect_submodules('plotly')
