# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for Signal Viewer Pro v3.0
=================================================

Build with: pyinstaller SignalViewer.spec --clean
"""

import os
import sys

# Get the directory containing this spec file
spec_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['run.py'],  # Entry point
    pathex=[spec_dir],
    binaries=[],
    datas=[
        # Include assets folder (CSS, JS, fonts - all offline)
        ('assets', 'assets'),
        # Include all Python source files
        ('app.py', '.'),
        ('config.py', '.'),
        ('data_manager.py', '.'),
        ('helpers.py', '.'),
        ('linking_manager.py', '.'),
        ('signal_operations.py', '.'),
        ('flexible_csv_loader.py', '.'),
        ('callback_helpers.py', '.'),
        ('utils.py', '.'),
    ],
    hiddenimports=[
        # Core packages
        'numpy',
        'numpy.core._methods',
        'numpy.core._dtype_ctypes',
        'pandas',
        'pandas._libs.tslibs.base',
        'scipy',
        'scipy.integrate',
        'scipy.interpolate',
        'scipy.signal',
        'scipy.special',
        'scipy.linalg',
        'scipy.sparse',
        'scipy.stats',
        'scipy.optimize',
        'scipy.fft',
        # Dash and Plotly - essential modules
        'dash',
        'dash.dcc',
        'dash.html',
        'dash_bootstrap_components',
        'plotly',
        'plotly.graph_objects',
        'plotly.subplots',
        'plotly.io',
        # Export libraries
        'kaleido',
        'openpyxl',
        'python-docx',
        'docx',
        # Web server
        'flask',
        'werkzeug',
        'jinja2',
        # Required utilities
        'pkg_resources',
        'jaraco',
        'jaraco.functools',
        'jaraco.context',
        'jaraco.text',
        'packaging',
        'packaging.version',
        'packaging.specifiers',
        'packaging.requirements',
        'importlib_resources',
        'zipp',
        # Native file dialog (required for file browser)
        'tkinter',
        'tkinter.filedialog',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[
        # Exclude unnecessary modules (NOT tkinter - we need it!)
        'matplotlib',
        'PIL',
        'sqlite3',
        'unittest',
        'test',
        'tests',
        'watchdog',  # Not used anymore
        'reportlab',  # Not used
        'pptx',  # Not used
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SignalViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to False after testing works
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SignalViewer',
)
