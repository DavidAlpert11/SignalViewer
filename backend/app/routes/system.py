"""Browser-mode watchdog: stop the server when no tab has been open for a while."""

import time

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()




# =============================================================================
# BROWSER-MODE WATCHDOG: stop the server when no tab is open (no orphan process)
# =============================================================================

# "last": the last sign of an open tab - its ping or ANY other request of the page. A tab in the
# background gets its timers slowed to about once a minute (Chrome / Edge), so a 30 s limit on pings
# alone stopped the server under a page that was only in the background - often in the middle of
# a long load ("Failed to fetch", then nothing works until a restart). Now:
#   * the page says when it closes ("bye", sent as the tab goes away): stop soon after that;
#   * otherwise the limit is IDLE_LIMIT, far beyond any throttled ping;
#   * never while a background job (opening / refreshing a file, a report) is still running.
WATCHDOG: Dict[str, Any] = {"enabled": False, "last": None, "bye": None}
IDLE_LIMIT = 300.0          # s without any request from a tab that did not say goodbye
BYE_LIMIT = 75.0            # s after "bye": a reload pings at once; another tab in the background within a minute

# T-window: why the app opened in the browser instead of its own window (run.py fills it; the
# page shows it once, so the reason is not hidden in a console that pythonw does not have)
WINDOW_NOTE = {"browserReason": "", "mode": ""}   # mode: window / app-window / browser (Help > About)



@router.post("/api/ping")
def ping():
    WATCHDOG["last"] = time.time()
    WATCHDOG["bye"] = None
    return {"ok": True}



@router.post("/api/bye")
def bye():
    WATCHDOG["bye"] = time.time()
    return {"ok": True}



def seen_page() -> None:
    """Any request of the page: a tab is open (called by the app's middleware)."""
    if WATCHDOG["enabled"]:
        WATCHDOG["last"] = time.time()



@router.get("/api/window_note")
def window_note():
    return dict(WINDOW_NOTE)



def idle_too_long(seconds: float = IDLE_LIMIT) -> bool:
    last = WATCHDOG["last"]
    if not WATCHDOG["enabled"] or last is None:
        return False
    from app.jobs import jobs                       # (local: jobs imports the loaders)
    if any(j.state == "running" for j in list(jobs.jobs.values())):
        return False
    quiet = time.time() - last
    bye_at = WATCHDOG["bye"]
    if bye_at is not None and bye_at >= last - 1.0:
        return quiet > BYE_LIMIT
    return quiet > max(seconds, IDLE_LIMIT)


# =============================================================================
# ERROR DETAILS (T38): the UI's own errors into the log; the text for "Copy error details"
# =============================================================================

class ClientError(BaseModel):
    message: str
    stack: str = ""
    where: str = ""


@router.post("/api/client-error")
def client_error(req: ClientError):
    from app import crashlog
    return {"logged": crashlog.ui_error(req.message, req.stack, req.where)}


@router.get("/api/diagnostics")
def diagnostics(ui: Optional[str] = None):
    from app import crashlog
    return crashlog.diagnostics(ui)


# T66: Help > Report a problem. The address is fixed here (the page cannot send one), and it is the
# backend that opens it: in the desktop window (pywebview) a link from the page would open inside
# the app or not at all; webbrowser opens the user's own browser in both modes.
ISSUE_URL = "https://github.com/DavidAlpert11/SignalViewer/issues/new?template=bug_report.yml"


@router.post("/api/report-problem")
def report_problem():
    import webbrowser
    try:
        opened = bool(webbrowser.open(ISSUE_URL, new=2))
    except Exception:                 # no browser registered (a bare server): the UI shows the address
        opened = False
    return {"url": ISSUE_URL, "opened": opened}


# =============================================================================
# UI SETTINGS (T18, F30): kept in ~/.signalviewer/ui_settings.json, not in the browser
# =============================================================================

@router.get("/api/settings")
def get_settings():
    from app import prefs
    return {"settings": prefs.ui_settings()}


class SettingsChange(BaseModel):
    changes: dict


@router.put("/api/settings")
def put_settings(req: SettingsChange):
    from app import prefs
    from app.common import fail
    try:
        return {"settings": prefs.update_ui_settings(req.changes)}
    except ValueError as e:
        fail(400, str(e))



# =============================================================================
# STORAGE: the CSV cache, copies of dropped files, map tiles - sizes and clearing (Settings)
# =============================================================================

class ClearRequest(BaseModel):
    what: list = []                 # "cache", "uploads", "tiles"



@router.get("/api/storage")
def storage_info():
    from app import storage
    return storage.info()



@router.post("/api/storage/clear")
def storage_clear(req: ClearRequest):
    from app import storage
    what = [w for w in req.what if w in ("cache", "uploads", "tiles")]
    return {"result": storage.clear(what), **storage.info()}
