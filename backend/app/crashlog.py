"""T38: a local record of what went wrong, so the owner can be told without a debugger.

Everything under the "signalviewer" logger goes to a rotating file in the app's folder
(~/.signalviewer/logs/signalviewer.log, 1 MB x 4); unhandled errors in requests, threads and the
UI are logged there too. Help > "Copy error details" copies the version, the system and the end
of that file. Nothing is ever sent anywhere."""
import logging
import logging.handlers
import os
import platform
import sys
import threading
from typing import Dict, Optional

from app.common import APP_DIR
from app.version import __version__

LOG_DIR = os.environ.get("SV_LOG_DIR") or os.path.join(APP_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "signalviewer.log")
TAIL_BYTES = 48_000                     # the end of the log in a report: the last few sessions
UI_REPORTS_MAX = 50                     # per run: a loop of UI errors must not fill the log

log = logging.getLogger("signalviewer").getChild(__name__)
_installed = False
_file_ok = False
_ui_reports = 0


def install() -> None:
    """Once per process: the file handler, a console copy of warnings, and the hooks that log
    exceptions nobody caught (main thread and other threads)."""
    global _installed, _file_ok
    if _installed:
        return
    _installed = True
    root = logging.getLogger("signalviewer")
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        _file_ok = True
    except OSError:                     # read-only home: the app works, there is just no file
        pass
    if sys.stderr is not None:          # (pythonw / the windowed build have no console)
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(logging.WARNING)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    prev_hook = sys.excepthook

    def excepthook(tp, value, tb):
        if not issubclass(tp, KeyboardInterrupt):
            log.critical("unhandled error", exc_info=(tp, value, tb))
        prev_hook(tp, value, tb)

    sys.excepthook = excepthook

    def thread_hook(args):
        if args.exc_type is not SystemExit:
            name = args.thread.name if args.thread else "?"
            log.error("unhandled error in thread %s", name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = thread_hook
    log.info("Signal Viewer %s started - Python %s, %s", __version__, platform.python_version(), platform.platform())


def ui_error(message: str, stack: str = "", where: str = "") -> bool:
    """An error the UI caught (window.onerror / a rejected promise / a plot that failed to draw).
    False once the per-run limit is reached."""
    global _ui_reports
    if _ui_reports >= UI_REPORTS_MAX:
        return False
    _ui_reports += 1
    log.error("UI error%s: %s%s", f" ({where[:200]})" if where else "", message[:2000],
              ("\n" + stack[:6000]) if stack else "")
    return True


def _tail(path: str, nbytes: int) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - nbytes))
            data = f.read()
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace")
    if size > nbytes and "\n" in text:  # start at a whole line
        text = text.split("\n", 1)[1]
    return text


def diagnostics(ui_version: Optional[str] = None) -> Dict[str, str]:
    """The text "Copy error details" puts on the clipboard. File paths may appear in it (the log
    names the files that failed); signal values never do."""
    frozen = "packaged" if getattr(sys, "frozen", False) else "from source"
    lines = [f"Signal Viewer {__version__} ({frozen})" + (f", UI {ui_version}" if ui_version and ui_version != __version__ else ""),
             f"System: {platform.platform()}",
             f"Python: {platform.python_version()}",
             f"Log: {LOG_FILE if _file_ok else '(no log file: the folder is not writable)'}",
             "", "--- end of the log ---"]
    tail = _tail(LOG_FILE, TAIL_BYTES) if _file_ok else ""
    lines.append(tail.rstrip() or "(empty)")
    return {"text": "\n".join(lines) + "\n", "logFile": LOG_FILE, "version": __version__}
