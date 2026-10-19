"""
Signal Viewer - launcher.

Starts the local API server on 127.0.0.1 (free port) and opens the UI:
  * in a native desktop window if pywebview is installed (recommended),
  * otherwise in the default browser.

    python run.py            # desktop window / browser
    python run.py --browser  # force the browser
    python run.py --port 8765 --no-open
    python run.py flight.bin run_012.csv        (opens them - in the running app, if there is one)
    python run.py --no-build # never build the UI (see ensure_ui)
    python run.py --build    # build the UI now, even when it looks up to date

From the source folder the UI is always the CURRENT code: when frontend/ changed since the UI
was last built (a pull, a patch, an edit), run.py builds it once (Node.js / npm needed) into
frontend/.local-dist - ignored by git, so the tracked frontend/dist is never touched - and
serves that. The packaged app (.exe / portable) is not affected.
"""
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # running from the PyInstaller executable: bundled files live in sys._MEIPASS
    BUNDLE = getattr(sys, "_MEIPASS", HERE)
    os.environ.setdefault("SV_DIST", os.path.join(BUNDLE, "frontend", "dist"))
    os.environ.setdefault("SV_EXAMPLES", os.path.join(BUNDLE, "examples"))
else:
    sys.path.insert(0, os.path.join(HERE, "backend"))


FRONT = os.path.join(HERE, "frontend")
LOCAL_DIST = os.path.join(FRONT, ".local-dist")
STAMP = ".sv-source-hash"                       # in LOCAL_DIST: the sources it was built from
UI_SOURCES = ("src", "public", "index.html", "package.json", "package-lock.json", "vite.config.ts",
              "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json")


def ui_source_hash(front: str = "") -> str:
    """Fingerprint of everything the UI build is made from (paths and contents)."""
    front = front or FRONT
    h = hashlib.sha256()
    for item in UI_SOURCES:
        top = os.path.join(front, item)
        files = [top] if os.path.isfile(top) else sorted(
            os.path.join(d, f) for d, _, fs in os.walk(top) for f in fs) if os.path.isdir(top) else []
        for f in sorted(files):
            h.update(os.path.relpath(f, front).replace(os.sep, "/").encode())
            with open(f, "rb") as fh:
                h.update(hashlib.sha256(fh.read()).digest())
    return h.hexdigest()


def _git(*args) -> str:
    return subprocess.run(["git", "-C", HERE, *args], capture_output=True, text=True, timeout=20, check=True).stdout.strip()


def _newest_source_mtime(front: str) -> float:
    newest = 0.0
    for item in UI_SOURCES:
        top = os.path.join(front, item)
        files = [top] if os.path.isfile(top) else [os.path.join(d, f) for d, _, fs in os.walk(top) for f in fs] if os.path.isdir(top) else []
        for f in files:
            newest = max(newest, os.path.getmtime(f))
    return newest


def committed_dist_is_current() -> bool:
    """Was frontend/dist built from the sources as they are now?

    Git history decides, because file times do not: `git checkout`, `pull` and `clone` give every
    file they write a fresh time, so a dist restored or cloned AFTER newer UI sources looked "built
    later" and the old UI was served without a word (found in T38's e2e run). So:
      * no local changes: current when no commit touched the UI sources after the last commit that
        touched frontend/dist;
      * local changes (edited sources, or a dist rebuilt by hand): current only when dist was
        built after the newest source (`npm run build` after the edits);
      * no git (a zip of the code): it cannot tell, so it trusts the committed UI."""
    index = os.path.join(FRONT, "dist", "index.html")
    built_after = os.path.isfile(index) and os.path.getmtime(index) > _newest_source_mtime(FRONT)
    sources = [f"frontend/{p}" for p in UI_SOURCES]
    try:
        if _git("status", "--porcelain", "--", *sources) or _git("status", "--porcelain", "--", "frontend/dist"):
            return built_after
        last_dist = _git("log", "-1", "--format=%H", "--", "frontend/dist")
        if not last_dist:
            return built_after
        return not _git("log", "--format=%H", f"{last_dist}..HEAD", "--", *sources)
    except (OSError, subprocess.SubprocessError):
        return True


def _build_ui(src_hash: str) -> bool:
    npm = shutil.which("npm")
    if not npm:
        print("The UI code changed but Node.js (npm) is not installed, so it cannot be built here:\n"
              "  showing the UI from the last build. Install Node.js (nodejs.org) and run again.", flush=True)
        return False
    print("The UI code changed - building it once (about half a minute)...", flush=True)
    try:
        lock, mods = os.path.join(FRONT, "package-lock.json"), os.path.join(FRONT, "node_modules", ".package-lock.json")
        if not os.path.isfile(mods) or (os.path.isfile(lock) and os.path.getmtime(lock) > os.path.getmtime(mods)):
            subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=FRONT, check=True)
        subprocess.run([npm, "run", "build", "--", "--outDir", ".local-dist", "--emptyOutDir"], cwd=FRONT, check=True)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"Building the UI failed ({e}); showing the UI from the last build.", flush=True)
        return False
    with open(os.path.join(LOCAL_DIST, STAMP), "w", encoding="utf-8") as f:
        json.dump({"source": src_hash, "built": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
    print("UI built.", flush=True)
    return True


def ensure_ui(force: bool = False, skip: bool = False) -> None:
    """Point the server (SV_DIST) at a UI built from the current sources - see the module doc."""
    if getattr(sys, "frozen", False) or os.environ.get("SV_DIST") or not os.path.isdir(os.path.join(FRONT, "src")):
        return                                  # packaged app, an explicit choice, or no sources here
    src_hash = ui_source_hash()
    try:
        with open(os.path.join(LOCAL_DIST, STAMP), encoding="utf-8") as f:
            local_ok = json.load(f).get("source") == src_hash
    except (OSError, ValueError):
        local_ok = False
    if local_ok and not force:
        os.environ["SV_DIST"] = LOCAL_DIST
        return
    if skip or os.environ.get("SV_NO_BUILD") or (not force and committed_dist_is_current()):
        return                                  # the tracked frontend/dist (default)
    if _build_ui(src_hash):
        os.environ["SV_DIST"] = LOCAL_DIST


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _log_to_file_when_windowless():
    """pythonw / a windowed .exe have no console: sys.stdout is None and libraries that log
    would fail. Send the output to a log file instead (also handy for troubleshooting)."""
    if sys.stdout is None or sys.stderr is None:
        folder = os.path.join(os.path.expanduser("~"), ".signalviewer")
        os.makedirs(folder, exist_ok=True)
        f = open(os.path.join(folder, "signalviewer.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or f
        sys.stderr = sys.stderr or f


def main():
    _log_to_file_when_windowless()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--browser", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--build", action="store_true", help="build the UI now (from the source folder)")
    ap.add_argument("--no-build", action="store_true", help="never build the UI; use the last build")
    ap.add_argument("--new-window", action="store_true",
                    help="open the files in a new app even when one is running")
    ap.add_argument("paths", nargs="*", help="files (or a .svsession) to open - in the running app, if there is one")
    args = ap.parse_args()
    # T54: files from outside (Open with, a double-click) go to the app that is already running
    paths = [os.path.abspath(p) for p in args.paths]
    leading = False
    if paths and not args.new_window:
        from app import instance
        if instance.hand_over(paths) or instance.wait_or_lead(paths):
            print("Opened in the Signal Viewer that is already running.", flush=True)
            return
        leading = True
    ensure_ui(force=args.build, skip=args.no_build)

    import uvicorn
    from app.main import app

    port = args.port or free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    while not server.started:
        time.sleep(0.05)
    print(f"Signal Viewer running at {url}", flush=True)
    # T39: where the Python client (signalviewer_push.show) finds this app, with a fresh token
    from app import push
    import atexit
    try:
        push.write_push_file(url)
        atexit.register(push.remove_push_file)
    except OSError as e:
        print(f"Sending data from Python is off: {e}", flush=True)
    if paths:
        push.add_open_event(paths)          # the page opens them once it has restored the last work
    if leading:
        from app import instance
        instance.release_lock()             # other starts now find this app through push.json

    if args.no_open:
        th.join()
        return
    if not args.browser and native_window_available():
        try:
            import webview  # pywebview
            window = webview.create_window("Signal Viewer", url, width=1440, height=900, min_size=(1024, 640))
            push.ON_OPEN.append(lambda: _to_front(window))
            # Windows (pywebview 6, WinForms) needs a real .ico; GTK / Qt take a png
            assets = os.path.join(getattr(sys, "_MEIPASS", HERE), "assets")
            icon = os.path.join(assets, "icon.ico") if sys.platform == "win32" else os.path.join(assets, "png", "icon-256.png")
            kw = {"private_mode": False}
            if sys.platform == "win32":
                kw["gui"] = "edgechromium"     # never fall back silently to the old IE engine
            try:
                use_icon = os.path.isfile(icon) and not os.environ.get("SV_NO_ICON")
                webview.start(_bind_drop, window, icon=icon if use_icon else None, **kw)
            except TypeError:   # older pywebview without the icon argument
                webview.start(_bind_drop, window, **kw)
            server.should_exit = True
            return
        except Exception as e:   # no usable native window: use the browser instead
            print(f"Native window not available ({e}); opening the browser.", flush=True)
    # Browser mode: the page pings the server; when no tab has been open for a while the
    # server exits, so no invisible process is left behind (the .exe has no console).
    from app import main as app_main
    app_main.WATCHDOG["enabled"] = True
    webbrowser.open(url)
    started = time.time()
    try:
        while th.is_alive():
            th.join(1.0)
            never_opened = app_main.WATCHDOG["last"] is None and time.time() - started > 120
            if (app_main.idle_too_long(30) or never_opened) and not server.should_exit:
                print("No open browser tab - stopping.", flush=True)
                server.should_exit = True
    except KeyboardInterrupt:
        server.should_exit = True


def _to_front(window):
    """T54: files handed over from outside - show the window (it may be minimised or behind)."""
    for name in ("restore", "show"):
        f = getattr(window, name, None)
        if f:
            f()
    try:                                  # Windows only lets a window come forward briefly on top
        window.on_top = True
        window.on_top = False
    except Exception:
        pass


def _bind_drop(window):
    """Files dropped on the desktop window: pywebview knows their REAL paths (a browser only
    gives contents). Open them from the original file, so refresh and live mode follow edits.
    If anything here is unavailable, the page falls back to uploading a copy (marked "copy")."""
    try:
        import json
        from webview.dom import DOMEventHandler

        def on_drop(e):
            try:
                files = (e or {}).get("dataTransfer", {}).get("files", []) or []
                paths = [f.get("pywebviewFullPath") for f in files if isinstance(f, dict) and f.get("pywebviewFullPath")]
                if paths:
                    window.evaluate_js("window.__svOpenDroppedPaths && window.__svOpenDroppedPaths(%s)" % json.dumps(paths))
            except Exception as err:
                print(f"Drop with paths failed ({err}); the page uploads a copy instead.", flush=True)

        window.dom.document.events.drop += DOMEventHandler(on_drop, False, False)
    except Exception as err:
        print(f"Real paths for dropped files not available ({err}).", flush=True)


def native_window_available() -> bool:
    """pywebview installed, and on Windows the Edge WebView2 runtime present."""
    try:
        import webview  # noqa: F401
    except ImportError:
        return False
    if sys.platform != "win32":
        return True
    try:
        import winreg
        guid = r"{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"     # Microsoft Edge WebView2 Runtime
        key = lambda *parts: "\\".join(parts + ("Microsoft", "EdgeUpdate", "Clients", guid))
        for root, sub in ((winreg.HKEY_LOCAL_MACHINE, key("SOFTWARE", "WOW6432Node")),
                          (winreg.HKEY_LOCAL_MACHINE, key("SOFTWARE")),
                          (winreg.HKEY_CURRENT_USER, key("Software"))):
            try:
                with winreg.OpenKey(root, sub) as k:
                    version, _ = winreg.QueryValueEx(k, "pv")
                    if version and version != "0.0.0.0":
                        return True
            except OSError:
                continue
    except Exception:
        pass
    return False


if __name__ == "__main__":
    # T31: the Python-operations worker is a separate process; in the packaged app it starts
    # this executable again, which must then run the worker and not a second app
    import multiprocessing
    multiprocessing.freeze_support()
    main()
