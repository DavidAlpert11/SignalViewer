# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for Signal Viewer Pro
============================================

Optimized build - faster and smaller.

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
        # Include assets folder
        ('assets', 'assets'),
        # Include uploads folder structure (just .gitkeep)
        ('uploads/.gitkeep', 'uploads'),
        # Include all Python source files
        ('app.py', '.'),
        ('config.py', '.'),
        ('config_manager.py', '.'),
        ('data_manager.py', '.'),
        ('helpers.py', '.'),
        ('linking_manager.py', '.'),
        ('plot_manager.py', '.'),
        ('signal_operations.py', '.'),
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
        # Dash and Plotly - only essential modules
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
        'reportlab',
        'reportlab.lib.pagesizes',
        'reportlab.platypus',
        'pptx',
        # File watching
        'watchdog',
        'watchdog.events',
        'watchdog.observers',
        # Web server
        'flask',
        'werkzeug',
        'jinja2',
        # Required utilities - jaraco is needed by pkg_resources
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
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[
        # Exclude unnecessary modules
        'tkinter',
        'matplotlib',
        'PIL',
        'sqlite3',
        'unittest',
        'test',
        'tests',
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
