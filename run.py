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
from typing import List, Optional, Tuple

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
    ap.add_argument("--safe-graphics", action="store_true",
                    help="draw without the graphics card (a blank or black window on some computers, virtual machines, remote desktop)")
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
    from app import storage                 # old dropped-file copies, the CSV cache within its limits
    threading.Thread(target=storage.startup_cleanup, daemon=True, name="cleanup").start()
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
    from app.routes import system as app_system
    import logging
    wlog = logging.getLogger("signalviewer").getChild("window")
    safe = args.safe_graphics or bool(os.environ.get("SV_SAFE_GRAPHICS"))
    if safe:
        _safe_graphics_env()
        print("Safe graphics: drawing without the graphics card.", flush=True)
    why_not = "" if args.browser else window_unavailable_reason()
    if not args.browser and not why_not:
        try:
            import webview  # pywebview
            window = webview.create_window("Signal Viewer", url, width=1440, height=900, min_size=(1024, 640))
            push.ON_OPEN.append(lambda: _to_front(window))
            app_system.WINDOW_NOTE["mode"] = "window"
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
            why_not = f"{e.__class__.__name__}: {e}"
            wlog.warning("the app window could not start; opening the browser", exc_info=True)
    opened = False
    if why_not:
        # the launcher has no console (pythonw): say it in the log AND in the page, else the app
        # just "opens in the browser" with no way to know why
        wlog.warning("native window not available: %s", why_not)
        # the best other engine on this computer: Edge / Chrome as a window of its own (no tabs,
        # no address bar), else Firefox; none new enough -> say so in a message box (no console)
        browsers = find_browsers()
        pick = choose_fallback(browsers)
        if pick:
            kind, exe, version = pick
            try:
                open_in(kind, exe, url, safe)
                opened = True
                app_system.WINDOW_NOTE["mode"] = "app-window" if kind in CHROMIUM_KINDS else "browser"
                why_not = f"{why_not} - opened in {kind} {version} instead"
            except OSError as e:
                wlog.warning("could not start %s: %s", exe, e)
        elif sys.platform == "win32":
            message_box(no_engine_message(why_not, browsers))
        print(f"Native window not available ({why_not}).", flush=True)
        app_system.WINDOW_NOTE["browserReason"] = why_not
    if not opened:
        app_system.WINDOW_NOTE["mode"] = "browser"
    # Browser mode: the page pings the server; when no tab has been open for a while the
    # server exits, so no invisible process is left behind (the .exe has no console).
    from app import main as app_main
    app_main.WATCHDOG["enabled"] = True
    if not opened:
        webbrowser.open(url)
    started = time.time()
    try:
        while th.is_alive():
            th.join(1.0)
            never_opened = app_main.WATCHDOG["last"] is None and time.time() - started > 120
            if (app_main.idle_too_long() or never_opened) and not server.should_exit:
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


def _unblock_windows_dlls() -> None:
    """Files extracted from a downloaded zip / 7z carry Windows' "came from the internet" mark
    (the Zone.Identifier stream), and .NET refuses to load such DLLs - pywebview's window (pythonnet,
    the WebView2 loader) then fails and the app opened in the browser every time. Removing the mark
    from the app's own DLLs is what "Properties > Unblock" does, for these files only."""
    if sys.platform != "win32":
        return
    roots = set()
    for name in ("webview", "pythonnet", "clr_loader"):
        try:
            import importlib.util
            spec = importlib.util.find_spec(name)
        except Exception:
            spec = None
        for loc in (spec.submodule_search_locations or []) if spec else []:
            roots.add(loc)
    for root in roots:
        for folder, _dirs, files in os.walk(root):
            for f in files:
                if f.lower().endswith((".dll", ".exe", ".pyd")):
                    try:
                        os.remove(os.path.join(folder, f) + ":Zone.Identifier")
                    except OSError:
                        pass                    # no mark (the usual case), or not NTFS


# The oldest engines the UI is built for (frontend/vite.config.ts `build.target` - keep the two
# in step). Offline computers often keep an old WebView2 / Edge for years; code built for a newer
# engine does not even start there, and the window stays blank.
MIN_CHROMIUM = 87
MIN_FIREFOX = 78
CHROMIUM_KINDS = ("Edge", "Chrome")


def _major(version: str) -> int:
    try:
        return int(str(version).split(".")[0])
    except (ValueError, IndexError):
        return 0


def _version_folders(app_dir: str) -> List[str]:
    """Edge, Chrome and WebView2 keep each installed version in a folder named by it."""
    try:
        return [d for d in os.listdir(app_dir) if d[:1].isdigit() and d.count(".") == 3]
    except OSError:
        return []


def _newest(versions) -> str:
    vs = [v for v in versions if v and v != "0.0.0.0"]
    return max(vs, key=lambda v: tuple(int(p) if p.isdigit() else 0 for p in v.split("."))) if vs else ""


def webview2_version() -> str:
    """The newest Edge WebView2 runtime on this computer ("" = none): the registry keys its
    installer writes, or its folders (Windows 11 ships it with the system, and some installs - per
    user, by policy - leave no key we know)."""
    found = []
    try:
        import winreg
        guid = r"{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"     # Microsoft Edge WebView2 Runtime
        key = lambda *parts: "\\".join(parts + ("Microsoft", "EdgeUpdate", "Clients", guid))
        for root, sub in ((winreg.HKEY_LOCAL_MACHINE, key("SOFTWARE", "WOW6432Node")),
                          (winreg.HKEY_LOCAL_MACHINE, key("SOFTWARE")),
                          (winreg.HKEY_CURRENT_USER, key("Software"))):
            try:
                with winreg.OpenKey(root, sub) as k:
                    found.append(str(winreg.QueryValueEx(k, "pv")[0]))
            except OSError:
                continue
    except Exception:
        pass
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if not base:
            continue
        app = os.path.join(base, "Microsoft", "EdgeWebView", "Application")
        found += [d for d in _version_folders(app) if os.path.isfile(os.path.join(app, d, "msedgewebview2.exe"))]
    return _newest(found)


def _webview2_installed() -> bool:
    return bool(webview2_version())


def find_browsers() -> List[Tuple[str, str, str]]:
    """(kind, executable, version) of the browsers installed on this computer (Windows; other
    systems use the default browser)."""
    if sys.platform != "win32":
        return []
    out: List[Tuple[str, str, str]] = []
    bases = [b for b in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                         os.environ.get("LOCALAPPDATA")) if b]
    for kind, parts, exe_name in (("Edge", ("Microsoft", "Edge", "Application"), "msedge.exe"),
                                  ("Chrome", ("Google", "Chrome", "Application"), "chrome.exe")):
        for base in bases:
            app = os.path.join(base, *parts)
            exe = os.path.join(app, exe_name)
            if os.path.isfile(exe):
                out.append((kind, exe, _newest(_version_folders(app))))
                break
    for base in bases:
        exe = os.path.join(base, "Mozilla Firefox", "firefox.exe")
        if os.path.isfile(exe):
            version = ""
            try:
                with open(os.path.join(base, "Mozilla Firefox", "application.ini"), encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if line.startswith("Version="):
                            version = line.split("=", 1)[1].strip()
                            break
            except OSError:
                pass
            out.append(("Firefox", exe, version))
            break
    return out


def choose_fallback(browsers: List[Tuple[str, str, str]]) -> Optional[Tuple[str, str, str]]:
    """The engine to open the app in when its own window cannot start: Edge, then Chrome (they
    open it as a window of its own), then Firefox - the first one new enough for the UI."""
    order = {"Edge": 0, "Chrome": 1, "Firefox": 2}
    for kind, exe, version in sorted(browsers, key=lambda b: order.get(b[0], 9)):
        need = MIN_FIREFOX if kind == "Firefox" else MIN_CHROMIUM
        if _major(version) >= need:
            return kind, exe, version
    return None


def open_in(kind: str, exe: str, url: str, safe: bool = False) -> None:
    """Edge / Chrome: the app as a window of its own (--app: no tabs, no address bar), with a
    profile of its own so the user's browser profile is never touched. Firefox: a new window."""
    if kind in CHROMIUM_KINDS:
        profile = os.path.join(os.path.expanduser("~"), ".signalviewer", "browser-profile")
        os.makedirs(profile, exist_ok=True)
        cmd = [exe, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run",
               "--no-default-browser-check", "--window-size=1440,900"]
        if safe:
            cmd += SAFE_GRAPHICS_ARGS
    else:
        cmd = [exe, "-new-window", url]
    subprocess.Popen(cmd, close_fds=True)


def no_engine_message(why_not: str, browsers: List[Tuple[str, str, str]]) -> str:
    found = ", ".join(f"{k} {v or '?'}" for k, _e, v in browsers) or "none"
    return ("Signal Viewer cannot open its own window: " + why_not + ".\n\n"
            f"Browsers found on this computer: {found}.\n"
            f"The app needs Microsoft Edge WebView2 / Edge / Chrome {MIN_CHROMIUM} or newer, or Firefox {MIN_FIREFOX} or newer.\n\n"
            "What to do: install the current Microsoft Edge WebView2 Runtime (the \"Evergreen Standalone "
            "Installer\" - on a computer without internet, ask IT to bring it). The app will now try the "
            "default browser; if the page stays blank, that browser is too old as well.\n\n"
            "Log: %USERPROFILE%\\.signalviewer\\logs\\signalviewer.log")


def message_box(text: str) -> None:
    """A Windows message box (the launcher has no console), shown without holding the start."""
    def show():
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, "Signal Viewer", 0x30 | 0x40000)   # warning, on top
        except Exception:
            pass
    threading.Thread(target=show, daemon=True, name="message").start()


# No graphics card: Chromium 139+ no longer draws WebGL in software by itself, so the 3D view would
# go to its simplified fallback; the software renderer is allowed back. "Unsafe" is about web pages
# from the internet - this window shows only the app's own page from 127.0.0.1.
SAFE_GRAPHICS_ARGS = ["--disable-gpu", "--enable-unsafe-swiftshader"]


def _safe_graphics_env() -> None:
    """Draw without the graphics card: WebView2 (Windows) and WebKitGTK (Linux) read these."""
    extra = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    for a in SAFE_GRAPHICS_ARGS:
        if a not in extra.split():
            extra = (extra + " " + a).strip()
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = extra
    os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")


def window_unavailable_reason() -> str:
    """Why the app cannot open its own window ("" = it can): pywebview missing or not loading, or
    (Windows) no WebView2 runtime."""
    _unblock_windows_dlls()
    try:
        import webview  # noqa: F401
    except Exception as e:                      # ImportError, or pythonnet failing to load .NET
        return f"pywebview could not be loaded ({e.__class__.__name__}: {e})"
    if sys.platform == "win32":
        version = webview2_version()
        if not version:
            return "the Microsoft Edge WebView2 runtime was not found"
        if _major(version) < MIN_CHROMIUM:
            return f"the Microsoft Edge WebView2 runtime is too old ({version}; the app needs {MIN_CHROMIUM} or newer)"
    return ""


def native_window_available() -> bool:
    """pywebview installed, and on Windows the Edge WebView2 runtime present."""
    return not window_unavailable_reason()


if __name__ == "__main__":
    # T31: the Python-operations worker is a separate process; in the packaged app it starts
    # this executable again, which must then run the worker and not a second app
    import multiprocessing
    multiprocessing.freeze_support()
    main()
