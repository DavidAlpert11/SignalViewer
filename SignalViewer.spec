# PyInstaller build definition for Signal Viewer. Everything the app needs is bundled:
# Python, all libraries, the UI (with its fonts), report assets and icons. Nothing is
# downloaded when the app runs.
#
#   pyinstaller SignalViewer.spec --noconfirm                  -> dist/SignalViewer/  (folder: fast start;
#                                                                  used by the installer and the portable zip)
#   set SV_ONEFILE=1 & pyinstaller SignalViewer.spec ...      -> dist/SignalViewer.exe (one file; slower start)
#
# build.bat / build.sh run this for you.
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(".")
ONEFILE = os.environ.get("SV_ONEFILE") == "1"

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("app", filter=lambda m: True)
    + collect_submodules("svcore")
    + ["scipy.io.matlab", "h5py", "docx", "bidi", "bidi.algorithm", "multipart", "python_multipart",
       "matplotlib.backends.backend_agg", "matplotlib.backends.backend_pdf", "matplotlib.backends.backend_svg"]
)
try:                       # native window (pywebview); without it the app opens in the browser
    import webview  # noqa: F401
    hidden += collect_submodules("webview")
except ImportError:
    pass

datas = [
    (os.path.join(ROOT, "frontend", "dist"), os.path.join("frontend", "dist")),
    (os.path.join(ROOT, "backend", "app", "report_assets"), os.path.join("app", "report_assets")),
    # the offline map (elevation grids, Natural Earth and OpenStreetMap layers): tools/make_basemap.py
    (os.path.join(ROOT, "backend", "app", "basemap_data"), os.path.join("app", "basemap_data")),
    (os.path.join(ROOT, "assets", "png"), os.path.join("assets", "png")),
    (os.path.join(ROOT, "assets", "icon.ico"), "assets"),          # the window icon on Windows
    (os.path.join(ROOT, "examples"), "examples"),                  # "Open an example" on the welcome screen
] + collect_data_files("docx") + collect_data_files("webview")

a = Analysis(
    ["run.py"],
    pathex=[os.path.join(ROOT, "backend")],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "PyQt5", "PySide6", "IPython", "notebook", "pytest", "playwright"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = os.path.join(ROOT, "assets", "icon.icns" if sys.platform == "darwin" else "icon.ico")
version_file = os.path.join(ROOT, "installer", "version_info.txt") if sys.platform == "win32" else None

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="SignalViewer", console=False, upx=False,
              icon=icon, version=version_file)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SignalViewer", console=False, upx=False,
              icon=icon, version=version_file)
    coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="SignalViewer")
