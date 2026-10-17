"""Browser-mode watchdog: stop the server when no tab has been open for a while."""

import time

from fastapi import APIRouter

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
