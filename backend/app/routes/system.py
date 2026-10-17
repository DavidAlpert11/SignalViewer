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
