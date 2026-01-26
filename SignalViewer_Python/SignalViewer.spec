# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for Signal Viewer Pro v2.6
=================================================

Build with: pyinstaller SignalViewer.spec --clean
"""

import os
import sys

spec_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['run.py'],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('sample_data', 'sample_data'),
        ('app.py', '.'),
        ('core', 'core'),
        ('loaders', 'loaders'),
        ('viz', 'viz'),
        ('ops', 'ops'),
        ('compare', 'compare'),
        ('stream', 'stream'),
        ('report', 'report'),
        ('ui', 'ui'),
    ],
    hiddenimports=[
        'numpy',
        'pandas',
        'dash',
        'dash.dcc',
        'dash.html',
        'dash_bootstrap_components',
        'plotly',
        'plotly.graph_objects',
        'plotly.subplots',
        'flask',
        'werkzeug',
        'jinja2',
        'tkinter',
        'tkinter.filedialog',
        # Optional DOCX export
        'docx',
        'docx.shared',
        'docx.enum.text',
        'kaleido',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'PIL',
        'sqlite3',
        'unittest',
        'test',
        'pytest',
    ],
    noarchive=False,
    optimize=1,  # Basic optimization
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
    console=False,  # No console window
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
