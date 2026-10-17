"""Live data: following growing files (stream) and live MAVLink links."""

import asyncio
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.common import APP_DIR, fail
from app.store import store
from svcore import mavlive

router = APIRouter()




# Live mode. Start: the UI refreshes every file (job "reloadAll"), then calls /start, then polls
# once a second. A poll reads only what was ADDED to each file, says how long ago each file last
# grew (so the UI can show which files are still being written), and every few seconds looks for
# NEW files next to the open ones (same name pattern) that appeared since live mode started.
LIVE: Dict[str, Any] = {"since": None, "reported": set(), "last_scan": 0.0}



class StreamStart(BaseModel):
    lookBack: float = 0.0          # also report files created up to this many seconds before now



@router.post("/api/stream/start")
def stream_start(req: StreamStart = StreamStart()):
    LIVE["since"] = time.time() - max(0.0, req.lookBack)
    LIVE["reported"] = set()
    LIVE["last_scan"] = 0.0
    for lr in store.runs.values():
        lr.last_change = 0.0
    return {"ok": True}



@router.post("/api/stream/stop")
def stream_stop():
    LIVE["since"] = None
    return {"ok": True}



@router.post("/api/stream/poll")
async def stream_poll():
    changed = await asyncio.to_thread(store.poll_appends)
    new_files = []
    now = time.time()
    if LIVE["since"] is not None and now - LIVE["last_scan"] >= 2.0:
        LIVE["last_scan"] = now
        found = await asyncio.to_thread(store.new_files, LIVE["since"], LIVE["reported"])
        for f in found:
            LIVE["reported"].add(f["path"])
        new_files = found
    return {"changed": changed, "runs": store.list() if changed else None,
            "errors": getattr(store, "poll_errors", {}), "activity": store.activity(), "newFiles": new_files}



# Live MAVLink (T12): a receiver records the link to a .tlog in the recordings folder; the UI opens
# that file and follows it with live mode above (one code path for live and recorded data).
MAVLINK: Dict[str, Optional[mavlive.Receiver]] = {"rx": None}

RECORDINGS = os.path.join(APP_DIR, "recordings")



class MavStart(BaseModel):
    conn: str                       # pymavlink connection string: udpin:127.0.0.1:14550, tcp:host:5760, COM5, /dev/ttyUSB0
    baud: int = 57600               # serial only
    request: bool = False           # act as a minimal ground station (heartbeat + ask for data streams)
    rate: int = 4                   # Hz, with request
    folder: Optional[str] = None    # where to record (default: ~/.signalviewer/recordings)



@router.post("/api/mavlink/start")
def mavlink_start(req: MavStart):
    conn = req.conn.strip()
    if not conn:
        fail(400, "Type a connection, e.g. udpin:127.0.0.1:14550 (SITL / MAVProxy) or COM5 (serial).")
    old = MAVLINK["rx"]
    if old is not None and old.running:
        fail(409, f"Already receiving from {old.conn_str}. Stop that connection first.")
    folder = os.path.abspath(os.path.expanduser(req.folder)) if req.folder else RECORDINGS
    try:
        rx = mavlive.Receiver(conn, mavlive.recording_path(folder), baud=int(req.baud), request=bool(req.request),
                              rate_hz=int(max(1, min(req.rate, 50))))
    except mavlive.MavLiveError as e:
        fail(400, str(e))
    except OSError as e:
        fail(400, f"Cannot write the recording in {folder}: {e}")
    MAVLINK["rx"] = rx
    return rx.status()



@router.post("/api/mavlink/stop")
def mavlink_stop():
    rx = MAVLINK["rx"]
    if rx is None:
        return {"running": False}
    rx.stop()
    return rx.status()



@router.get("/api/mavlink/ports")
def mavlink_ports():
    return {"ports": mavlive.serial_ports(), "presets": list(mavlive.PRESETS), "folder": RECORDINGS}



@router.get("/api/mavlink/status")
def mavlink_status():
    rx = MAVLINK["rx"]
    return rx.status() if rx is not None else {"running": False}
