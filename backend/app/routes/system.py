"""Browser-mode watchdog: stop the server when no tab has been open for a while."""

import time

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()




# =============================================================================
# BROWSER-MODE WATCHDOG: stop the server when no tab is open (no orphan process)
# =============================================================================

WATCHDOG = {"enabled": False, "last": None}



@router.post("/api/ping")
def ping():
    WATCHDOG["last"] = time.time()
    return {"ok": True}



def idle_too_long(seconds: float) -> bool:
    last = WATCHDOG["last"]
    return bool(WATCHDOG["enabled"] and last is not None and time.time() - last > seconds)


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
