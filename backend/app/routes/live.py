"""Live data: following growing files (stream) and live MAVLink links."""

import asyncio
import os
import time
from typing import Any, Dict, List, Optional, Tuple

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
            "errors": getattr(store, "poll_errors", {}), "activity": store.activity(), "newFiles": new_files,
            "writing": list(getattr(store, "writing", []))}



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


# ----------------------------------------------------------------------------- L5 F4: live instruments
class InstrumentItem(BaseModel):
    name: str                      # a signal NAME ("a|b": a, else b), as a profile's at-a-glance numbers


class InstrumentObject(BaseModel):
    """The object the map would draw for this run (objectDetect's picks): signal ids, all optional."""
    roll: Optional[str] = None
    pitch: Optional[str] = None
    yaw: Optional[str] = None
    qw: Optional[str] = None
    qx: Optional[str] = None
    qy: Optional[str] = None
    qz: Optional[str] = None
    lat: Optional[str] = None
    lon: Optional[str] = None
    alt: Optional[str] = None
    angleUnit: Optional[str] = None    # "deg" / "rad"; else the app's Automatic rule


class InstrumentsRequest(BaseModel):
    t: float                       # the time shown (offsets applied): the cursor, or the newest data while live
    items: List[InstrumentItem] = []
    object: Optional[InstrumentObject] = None


@router.post("/api/runs/{run_id}/instruments")
def run_instruments(run_id: str, req: InstrumentsRequest):
    """F4: each tile's value in force at t (the last sample at or before it, never interpolated) and how old
    it is; the attitude (degrees), heading (0-360), altitude and ground speed of the run's object. A name the
    file does not have comes back with sig None - the view says so instead of hiding the tile."""
    import numpy as np

    from svcore import templates as tplm
    from svcore.instruments import ground_speed, last_sample, quat_to_euler, typical_step
    from svcore.naming import without_unit
    from svcore.objcompare import angle_units
    try:
        lr = store.get(run_id)
    except KeyError:
        fail(404, "File is not open.")
    ix = tplm.index_of({"id": run_id, "signals": [{"name": n} for n in lr.run.signals]})

    def at(sid: str) -> Optional[Tuple[float, float]]:
        t, y, off = store.signal_parts(sid)
        hit = last_sample(t, y, req.t - off)
        return None if hit is None else (hit[0], hit[1] + off)

    items = []
    for it in req.items:
        name = ix.match(it.name)
        row: Dict[str, Any] = {"name": it.name, "sig": None, "unit": None, "value": None, "text": None, "at": None, "age": None,
                               "state": False, "step": None}
        if name is not None:
            sid = f"{run_id}/{name}"
            unit = name[len(without_unit(name)):].strip().strip("[]")
            row.update(sig=sid, unit=unit or None, state=store.is_state(sid))
            hit = at(sid)
            if hit is not None:
                t_raw, _y, off = store.signal_parts(sid)
                row.update(value=hit[0], at=hit[1], age=max(0.0, req.t - hit[1]), step=typical_step(t_raw, req.t - off))
                labels = store.labels(sid)
                if labels:
                    row["text"] = labels.get(int(hit[0]))
        items.append(row)

    obj: Optional[Dict[str, Any]] = None
    o = req.object
    if o is not None:
        obj = {"roll": None, "pitch": None, "yaw": None, "alt": None, "gs": None, "age": None}
        raw = {}
        for role in ("roll", "pitch", "yaw"):
            sid = getattr(o, role)
            if sid:
                try:
                    raw[role] = (sid, *store.signal(sid))
                except KeyError:
                    continue
        units = angle_units(raw)
        newest: Optional[float] = None
        for role, (sid, _ts, _vs) in raw.items():
            hit = at(sid)
            if hit is None:
                continue
            unit = o.angleUnit if o.angleUnit in ("deg", "rad") else units[role][0]
            obj[role] = float(np.degrees(hit[0])) if unit == "rad" else hit[0]
            newest = hit[1] if newest is None else max(newest, hit[1])
        if all(getattr(o, q) for q in ("qw", "qx", "qy", "qz")) and any(obj[r] is None for r in ("roll", "pitch", "yaw")):
            try:
                hits = [at(getattr(o, q)) for q in ("qw", "qx", "qy", "qz")]
            except KeyError:
                hits = []
            if hits and all(h is not None for h in hits):
                e = quat_to_euler(*(h[0] for h in hits if h is not None))
                for role, v in (e or {}).items():
                    if obj[role] is None:
                        obj[role] = v
                newest = max(h[1] for h in hits if h is not None)
        if obj["yaw"] is not None:
            obj["yaw"] = obj["yaw"] % 360.0           # a heading, 0-360
        if o.alt:
            try:
                hit = at(o.alt)
                obj["alt"] = None if hit is None else hit[0]
            except KeyError:
                pass
        if o.lat and o.lon:
            try:
                tl, la = store.signal(o.lat)
                tn, ln = store.signal(o.lon)
                if len(tl) == len(tn):            # one clock (a log's message, a CSV's rows)
                    obj["gs"] = ground_speed(tl, la, ln, req.t)
            except KeyError:
                pass
        obj["age"] = None if newest is None else max(0.0, req.t - newest)
    return {"t": req.t, "items": items, "object": obj}
