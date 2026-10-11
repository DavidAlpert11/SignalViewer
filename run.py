"""
Signal Viewer - launcher.

Starts the local API server on 127.0.0.1 (free port) and opens the UI:
  * in a native desktop window if pywebview is installed (recommended),
  * otherwise in the default browser.

    python run.py            # desktop window / browser
    python run.py --browser  # force the browser
    python run.py --port 8765 --no-open
"""
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # running from the PyInstaller executable: bundled files live in sys._MEIPASS
    BUNDLE = getattr(sys, "_MEIPASS", HERE)
    os.environ.setdefault("SV_DIST", os.path.join(BUNDLE, "frontend", "dist"))
else:
    sys.path.insert(0, os.path.join(HERE, "backend"))


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
    args = ap.parse_args()

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

    if args.no_open:
        th.join()
        return
    if not args.browser and native_window_available():
        try:
            import webview  # pywebview
            window = webview.create_window("Signal Viewer", url, width=1440, height=900, min_size=(1024, 640))
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
    main()
