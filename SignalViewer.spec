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
sys.path.insert(0, os.path.join(ROOT, "backend"))
from svcore.example_data import GENERATED  # noqa: E402 - the examples' recordings written by code

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("app", filter=lambda m: True)
    + collect_submodules("svcore")
    + collect_submodules("signalviewer")       # W17 / W18: `SignalViewer.exe study ...` (run.py imports it inside main)
    + ["scipy.io.matlab", "h5py", "docx", "bidi", "bidi.algorithm", "multipart", "python_multipart",
       "openpyxl",   # pandas imports it by name for .xlsx
       "latex2mathml", "latex2mathml.converter",   # RE4: imported inside a function
       "matplotlib.backends.backend_agg", "matplotlib.backends.backend_pdf", "matplotlib.backends.backend_svg",
       # live MAVLink (T12): imported inside functions / by name, PyInstaller cannot see them
       "pymavlink.mavutil", "pymavlink.dialects.v20.ardupilotmega", "serial", "serial.tools.list_ports"]
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
] + ([
    # RE4: the built-in LaTeX - Tectonic + the small TeX bundle (tools/get_tectonic.py, tools/make_tex_bundle.py;
    # build.yml makes both). Absent: the app uses the computer's TeX, or writes the project for Overleaf.
    (os.path.join(ROOT, "backend", "app", "tex"), os.path.join("app", "tex")),
] if os.path.isdir(os.path.join(ROOT, "backend", "app", "tex")) else []) + [
    (os.path.join(ROOT, "assets", "png"), os.path.join("assets", "png")),
    (os.path.join(ROOT, "assets", "icon.ico"), "assets"),          # the window icon on Windows
    (os.path.join(ROOT, "LICENSE"), "."),                          # the app's licence (T32)
    (os.path.join(ROOT, "backend", "signalviewer", "push_client.py"), "clients"),  # T39: saved for the user as a file
    # the built-in templates (T11b: data, read by svcore/templates.py for the app and the CLI)
    (os.path.join(ROOT, "backend", "svcore", "builtin_templates.json"), "svcore"),
    # 1.21: ArduPilot's device / parameter names for the hardware summary (svcore/hardware.py)
    (os.path.join(ROOT, "backend", "svcore", "ap_names.json"), "svcore"),
    # L12: the names map objects are found by - one table for the app's UI and Python (svcore/objects.py)
    (os.path.join(ROOT, "backend", "svcore", "object_names.json"), "svcore"),
] + collect_data_files("docx") + collect_data_files("webview")
# "Open an example" on the welcome screen - without its recordings: the app writes them on first use
# (svcore/example_data, owner 2026-11-18)
_ex = os.path.join(ROOT, "examples")
for _d, _dirs, _names in os.walk(_ex):
    _dirs[:] = [x for x in _dirs if x != "__pycache__"]
    for _n in _names:
        _rel = os.path.relpath(os.path.join(_d, _n), _ex).replace(os.sep, "/")
        if _rel not in GENERATED and not _n.endswith(".pyc"):
            datas.append((os.path.join(_d, _n), os.path.join("examples", os.path.dirname(_rel))))

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
