#!/usr/bin/env python3
"""
Build the Windows portable package of Signal Viewer.

Runs on Windows, Linux and macOS (only Python 3.8+ with pip and an internet connection are
needed - to BUILD; the result needs neither):

    py tools\\make_windows_portable.py          (Windows - or just double-click build_windows_portable.bat)
    python3 tools/make_windows_portable.py      (Linux / macOS)

Result: dist/SignalViewer-Windows-portable.7z   (or .zip with --format zip)
Extract it anywhere on Windows 10/11 and double-click "Signal Viewer.bat".
(.7z: Windows 11 opens it in Explorer; on Windows 10 use 7-Zip. --format zip for no extra tool at all.)

How: the official Windows "embeddable" Python from python.org + the official win_amd64 builds of
every library (pip downloads them for Windows even when this script runs elsewhere) + the app.

Options:
    --out DIR         where to write the zip (default: dist)
    --keep-folder     also keep the assembled folder (build/winportable/SignalViewer) to try it without unzipping
    --clean           delete the download cache first (forces a fresh download)
    --build-ui        rebuild the web UI first (needs Node.js; the project already contains a built UI)
    --format 7z|zip   archive type (default 7z: about a third smaller). Uses 7-Zip when installed,
                      else the py7zr library (downloaded into the build cache on first use)
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY_FULL, PY_MM = "3.12.10", "3.12"
PY_URL = f"https://www.python.org/ftp/python/{PY_FULL}/python-{PY_FULL}-embed-amd64.zip"
APP = "SignalViewer"
# pywebview and what it needs on Windows: resolved by hand, because pip cannot resolve a Windows
# dependency tree from another platform in one go
EXTRA = ["pywebview", "pythonnet", "clr_loader", "cffi", "pycparser", "bottle", "typing_extensions"]
SOURCE_ONLY = ["proxy_tools"]            # pywebview's tiny dependency that ships only as source: built here


def say(msg=""):
    print(msg, flush=True)


def die(msg):
    say(f"\nERROR: {msg}")
    sys.exit(1)


def lp(path):
    """Long-path form on Windows: the package tree is deeper than the 260-character limit."""
    path = os.path.abspath(path)
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        return "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path
    return path


def rmtree(path):
    if os.path.exists(lp(path)):
        shutil.rmtree(lp(path), ignore_errors=True)
        if os.path.exists(lp(path)):
            die(f"Could not delete {path}. Close programs that use it (Explorer, antivirus) and try again.")


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "SignalViewer-build"})
    tmp = dest + ".part"
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            total, done = int(r.headers.get("Content-Length") or 0), 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done >> 20} / {total >> 20} MB", end="", flush=True)
    except OSError as e:
        die(f"Download failed ({url}): {e}\nAn internet connection is needed for the build (once).")
    say()
    os.replace(tmp, dest)


def pip(*args):
    r = subprocess.run([sys.executable, "-m", "pip", *args, "--disable-pip-version-check", "-q"])
    if r.returncode != 0:
        die("pip failed (the message above says why). Is pip installed (py -m pip --version) and the internet reachable?")


def extract(zip_path, dest):
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(lp(dest))


def copy_dir(src, dst, skip=()):
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", *skip)
    shutil.copytree(lp(src), lp(dst), ignore=ignore)


def find_7z():
    """7-Zip's command line, if installed: the real 7z.exe in the usual Windows folders first (a
    7z on PATH can be a Chocolatey shim, which fails on long-path working folders), then PATH."""
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        p = os.path.join(base, "7-Zip", "7z.exe")
        if os.path.isfile(p):
            return p
    for name in ("7z", "7za", "7zz"):
        p = shutil.which(name)
        if p:
            return p
    return None


def make_7z(folder, out_path, top, cache):
    """A .7z (LZMA2) of folder, with `top` as its single top folder. Returns the file count."""
    n = sum(len(files) for _h, _d, files in os.walk(lp(folder)))
    exe = find_7z()
    if exe:
        say(f"  7-Zip: {exe}")
        # 7z stores the folder under its own name, so archive "<parent>/<top>" from the parent
        parent = os.path.dirname(os.path.abspath(folder))
        if os.path.basename(os.path.abspath(folder)) != top:
            die(f"Internal: the package folder must be named {top}.")
        # a plain working folder, not the long-path (\\?\) form that lp() makes: some launchers, such as
        # Chocolatey's 7z shim, cannot use that as the current folder (the folder itself is short)
        r = subprocess.run([exe, "a", "-t7z", "-mx=7", "-m0=lzma2", "-mmt=on", "-bso0", "-bsp1", out_path, top], cwd=parent)
        if r.returncode != 0:
            die("7-Zip failed (the message above says why).")
        return n
    lib = os.path.join(cache, "py7zr")
    if not os.path.isdir(os.path.join(lib, "py7zr")):
        say("  7-Zip is not installed: getting the py7zr library (once) ...")
        pip("install", "--target", lib, "--upgrade", "py7zr")
    sys.path.insert(0, lib)
    import py7zr                                       # noqa: E402  (just installed)
    base = lp(folder)
    k = 0
    with py7zr.SevenZipFile(out_path, "w", filters=[{"id": py7zr.FILTER_LZMA2, "preset": 7}]) as z:
        for here, dirs, files in os.walk(base):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(here, name)
                z.write(full, top + "/" + os.path.relpath(full, base).replace(os.sep, "/"))
                k += 1
                if k % 1500 == 0:
                    print(f"\r  {k} files", end="", flush=True)
    say(f"\r  {k} files")
    return n


def make_zip(folder, zip_path, top):
    n = 0
    base = lp(folder)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as z:
        for here, dirs, files in os.walk(base):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(here, name)
                z.write(full, top + "/" + os.path.relpath(full, base).replace(os.sep, "/"))
                n += 1
                if n % 1500 == 0:
                    print(f"\r  {n} files", end="", flush=True)
    say(f"\r  {n} files")
    return n


def build_ui():
    """npm ci + npm run build in frontend/ (Windows: npm is npm.cmd, found through PATH)."""
    npm = shutil.which("npm")
    if not npm:
        die("Node.js (npm) was not found, so the web UI cannot be rebuilt.\n"
            "Install it from https://nodejs.org (LTS), or leave out --build-ui: the project already contains a built UI (frontend\\dist).")
    front = os.path.join(ROOT, "frontend")
    say("[0/5] Building the web UI (npm)")
    for cmd in ([npm, "ci", "--no-audit", "--no-fund"] if os.path.isfile(os.path.join(front, "package-lock.json")) else [npm, "install", "--no-audit", "--no-fund"],
                [npm, "run", "build"]):
        if subprocess.run(cmd, cwd=front).returncode != 0:
            die("The web UI build failed (the message above says why).")


def ui_is_stale():
    """The name of a UI source file newer than the built UI (frontend/dist), or None."""
    built = os.path.join(ROOT, "frontend", "dist", "index.html")
    if not os.path.isfile(built):
        return None                                   # reported as missing below
    t = os.path.getmtime(built)
    for here, _dirs, files in os.walk(os.path.join(ROOT, "frontend", "src")):
        for f in files:
            full = os.path.join(here, f)
            if os.path.getmtime(full) > t + 2:
                return os.path.relpath(full, ROOT)
    return None


def main():
    ap = argparse.ArgumentParser(description="Build the Windows portable zip of Signal Viewer.")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--keep-folder", action="store_true")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--build-ui", action="store_true")
    ap.add_argument("--format", choices=("7z", "zip"), default="7z")
    args = ap.parse_args()
    if sys.version_info < (3, 8):
        die("Python 3.8 or newer is needed to run the build.")
    t0 = time.time()
    if args.build_ui:
        build_ui()
    else:
        stale = ui_is_stale()
        if stale:
            if shutil.which("npm"):
                say(f"The web UI sources changed after the last UI build ({stale}): rebuilding it.")
                build_ui()
            else:
                say(f"WARNING: the web UI sources changed after the last UI build ({stale}), and Node.js (npm) is\n"
                    "not installed, so the package gets the UI as it was last built. Install Node.js LTS to rebuild it.")

    # --- 0. what the build needs from the project
    need = ["requirements.txt", "run.py", "backend", os.path.join("frontend", "dist", "index.html"),
            os.path.join("assets", "icon.ico"), os.path.join("assets", "png"),
            os.path.join("installer", "portable", "make_shortcut.ps1"),
            os.path.join("installer", "portable", "Signal Viewer.bat"), os.path.join("installer", "portable", "README-HE.txt"), "LICENSE", "examples"]
    missing = [n for n in need if not os.path.exists(os.path.join(ROOT, n))]
    if missing:
        die("Missing in the project: " + ", ".join(missing) +
            ("\nThe UI is not built: cd frontend && npm ci && npm run build" if any("dist" in m for m in missing) else ""))

    work = os.path.join(ROOT, "build", "winportable")
    cache = os.path.join(ROOT, "build", "winportable-cache")           # downloads survive between runs
    if args.clean:
        rmtree(cache)
    os.makedirs(cache, exist_ok=True)
    rmtree(work)
    pkg = os.path.join(work, APP)
    runtime, site = os.path.join(pkg, "runtime"), os.path.join(pkg, "runtime", "Lib", "site-packages")
    app = os.path.join(pkg, "app")
    for d in (runtime, site, app):
        os.makedirs(lp(d), exist_ok=True)

    # --- 1. Python for Windows (embeddable: no installation)
    say(f"[1/5] Python {PY_FULL} for Windows (embeddable)")
    py_zip = os.path.join(cache, f"python-{PY_FULL}-embed-amd64.zip")
    if not (os.path.isfile(py_zip) and zipfile.is_zipfile(py_zip)):
        download(PY_URL, py_zip)
    else:
        say("  (from the cache)")
    extract(py_zip, runtime)
    pth = f"python{PY_MM.replace('.', '')}._pth"
    with open(os.path.join(runtime, pth), "w", newline="") as f:
        f.write(f"python{PY_MM.replace('.', '')}.zip\r\n.\r\nLib\\site-packages\r\nimport site\r\n")

    # --- 2. the libraries, as Windows builds
    say("[2/5] Libraries for Windows (win_amd64, Python " + PY_MM + ")")
    wheels, src = os.path.join(cache, "wheels"), os.path.join(cache, "src")
    rmtree(wheels)                       # old versions from an earlier run must not be unpacked over newer ones
    rmtree(src)
    os.makedirs(wheels, exist_ok=True)
    os.makedirs(src, exist_ok=True)
    reqs = [l for l in open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8-sig").read().splitlines()
            if not re.match(r"\s*pywebview\b", l, re.I)]
    req_file = os.path.join(cache, "requirements-nowebview.txt")
    open(req_file, "w", encoding="utf-8").write("\n".join(reqs) + "\n")
    target = ["--only-binary=:all:", "--platform", "win_amd64", "--python-version", PY_MM, "--implementation", "cp", "-d", wheels]
    pip("download", *target, "-r", req_file)
    for name in EXTRA:
        pip("download", *target, "--no-deps", name)
    for name in SOURCE_ONLY:
        pip("download", "--no-binary=:all:", "--no-deps", "-d", src, name)
    sources = sorted(os.path.join(src, f) for f in os.listdir(src))
    pip("wheel", "--no-deps", "-w", wheels, *sources)
    for w in sorted(f for f in os.listdir(wheels) if f.endswith(".whl")):
        extract(os.path.join(wheels, w), site)

    # --- 3. the app
    say("[3/5] The app")
    shutil.copy2(os.path.join(ROOT, "run.py"), app)
    copy_dir(os.path.join(ROOT, "backend"), os.path.join(app, "backend"), skip=("tests",))
    copy_dir(os.path.join(ROOT, "frontend", "dist"), os.path.join(app, "frontend", "dist"))
    os.makedirs(os.path.join(app, "assets"), exist_ok=True)
    copy_dir(os.path.join(ROOT, "assets", "png"), os.path.join(app, "assets", "png"))
    shutil.copy2(os.path.join(ROOT, "assets", "icon.ico"), os.path.join(app, "assets"))
    # "Open an example" on the welcome screen (T09): routes/fs.py looks in app/examples (F10 - the
    # portable package had none, so the welcome line was hidden)
    copy_dir(os.path.join(ROOT, "examples"), os.path.join(app, "examples"))
    shutil.copy2(os.path.join(ROOT, "installer", "portable", "make_shortcut.ps1"), app)
    for f in sorted(os.listdir(os.path.join(ROOT, "installer", "portable"))):
        if f.lower().endswith(".bat") or f == "README-HE.txt":
            shutil.copy2(os.path.join(ROOT, "installer", "portable", f), pkg)
    shutil.copy2(os.path.join(ROOT, "LICENSE"), pkg)                   # the app's licence (T32)

    # --- 4. check before zipping
    say("[4/5] Checking the package")
    must = [("runtime", "python.exe"), ("runtime", "pythonw.exe"), ("runtime", pth), ("app", "run.py"),
            ("app", "backend", "svcore", "bin_loader.py"), ("app", "backend", "app", "patterns.py"),
            ("app", "backend", "svcore", "tlog_loader.py"), ("app", "backend", "svcore", "ulog_loader.py"),
            ("runtime", "Lib", "site-packages", "pymavlink"), ("runtime", "Lib", "site-packages", "pyulog"),
            ("app", "frontend", "dist", "index.html"), ("app", "assets", "icon.ico"), ("Signal Viewer.bat",)]
    must += [("runtime", "Lib", "site-packages", m) for m in ("numpy", "pandas", "pyarrow", "scipy", "h5py", "matplotlib",
                                                              "fastapi", "starlette", "pydantic_core", "uvicorn", "h11", "docx", "bidi", "webview",
                                                              "clr_loader", "pythonnet")]
    must += [("runtime", "Lib", "site-packages", "pythonnet", "runtime", "Python.Runtime.dll")]
    # the offline map: its data (tools/make_basemap.py) and Pillow, which draws its tiles
    must += [("app", "backend", "app", "basemap.py"), ("runtime", "Lib", "site-packages", "PIL")]
    # the 3D view: CesiumJS's workers / data (copied into the UI build) and the object models
    must += [("app", "frontend", "dist", "cesium", "Workers"), ("app", "frontend", "dist", "cesium", "Assets", "approximateTerrainHeights.json")]
    must += [("app", "frontend", "dist", "models", f"{k}.glb") for k in ("aircraft", "uav", "drone", "missile", "ship", "vehicle")]
    must += [("app", "backend", "app", "basemap_data", f) for f in ("dem_world.npz", "dem_region.npz", "dem_israel.npz",
                                                                    "vectors_world.json.gz", "vectors_israel.json.gz")]
    must += [("app", "examples", f) for f in sorted(os.listdir(os.path.join(ROOT, "examples")))]   # F10
    bad = [os.path.join(*m) for m in must if not os.path.exists(lp(os.path.join(pkg, *m)))]
    if bad:
        die("The package is incomplete, missing: " + ", ".join(bad))

    # --- 5. zip
    say(f"[5/5] Archive ({args.format})")
    os.makedirs(args.out, exist_ok=True)
    zip_path = os.path.join(os.path.abspath(args.out), f"{APP}-Windows-portable.{args.format}")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    n = make_7z(pkg, zip_path, APP, cache) if args.format == "7z" else make_zip(pkg, zip_path, APP)
    if not args.keep_folder:
        rmtree(work)
    mb = os.path.getsize(zip_path) / 1048576
    say(f"\nDone in {time.time() - t0:.0f} s: {zip_path}  ({mb:.0f} MB, {n} files)")
    say("On Windows: extract it anywhere and double-click \"Signal Viewer.bat\"." +
        ("\n(.7z opens in Explorer on Windows 11; on Windows 10 use 7-Zip: https://www.7-zip.org)" if args.format == "7z" else ""))


if __name__ == "__main__":
    main()
