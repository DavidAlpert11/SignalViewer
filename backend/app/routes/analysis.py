"""Analysis: derived signals and transforms, FFT, X-Y / XYZ, object tracks, states."""

import asyncio
import re
from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

from app.common import b64, fail
from app.store import LoadError
from app.store import store
from svcore.analysis import OPS, OpError, fft_display, fft_for, transitions, xy_pair
from svcore.decimate import decimate_for_view

router = APIRouter()




# =============================================================================
# ANALYSIS (phase 3)
# =============================================================================

class DerivedRequest(BaseModel):
    op: str
    sources: List[str]
    params: Optional[dict] = None
    name: Optional[str] = None



@router.post("/api/derived")
async def create_derived(req: DerivedRequest):
    if req.op not in OPS:
        fail(400, f"Unknown operation: {req.op}")
    try:
        d = await asyncio.to_thread(store.add_derived, req.op, req.sources, req.params or {}, req.name)
    except KeyError:
        fail(404, "One of the chosen signals is no longer open.")
    except OpError as e:
        fail(400, str(e))
    return {"id": f"derived/{d.name}", "name": d.name, "runs": store.list()}



class PreviewRequest2(BaseModel):
    op: str
    sources: List[str]
    params: Optional[dict] = None
    x0: Optional[float] = None
    x1: Optional[float] = None
    points: int = 3000



@router.post("/api/derived/preview")
def preview_derived(req: PreviewRequest2):
    """Compute an operation WITHOUT keeping it, for a dashed preview in the plot (O-04)."""
    from svcore.analysis import compute
    try:
        t, y = compute(req.op, [store.signal(s) for s in req.sources], req.params or {})
    except KeyError:
        fail(404, "One of the chosen signals is no longer open.")
    except OpError as e:
        fail(400, str(e))
    rng = [req.x0, req.x1] if req.x0 is not None and req.x1 is not None else None
    xd, yd, _ = decimate_for_view(t, y, rng, int(max(200, min(req.points, 20000))))
    return {"n": int(len(xd)), "x": b64(xd, np.float64), "y": b64(yd, np.float32)}



class TransformRequest(BaseModel):
    signals: List[str] = []
    transform: Optional[dict] = None            # None clears
    specs: Optional[Dict[str, Optional[dict]]] = None   # or one spec per signal (undo / restore)



@router.post("/api/transforms")
def set_transforms(req: TransformRequest):
    """Change signals THEMSELVES (no new signals): function, scale, offset, time shift."""
    specs = req.specs if req.specs is not None else {sid: req.transform for sid in req.signals}
    if not specs:
        fail(400, "No signals chosen.")
    try:
        previous = store.set_transforms(specs)
    except KeyError as e:
        fail(404, f"Not an open file signal: {e}")
    except OpError as e:
        fail(400, str(e))
    return {"previous": previous, "runs": store.list()}



class DerivedBatch(BaseModel):
    items: List[DerivedRequest]



@router.post("/api/derived/restore")
async def restore_derived(req: DerivedBatch):
    """Recreate derived signals from saved formulas (autosave / sessions). Idempotent: a formula
    whose name already exists REPLACES it (no "name (2)" duplicates, and "derived/<name>"
    references in the layout stay valid) - e.g. when the same work is re-opened with new files."""
    ok, failed = [], []
    for it in req.items:
        if it.name and it.name in store.derived:
            store.remove_derived(it.name)
        try:
            d = await asyncio.to_thread(store.add_derived, it.op, it.sources, it.params or {}, it.name)
            ok.append(d.name)
        except Exception as e:
            failed.append({"name": it.name, "message": str(e)})
    return {"restored": ok, "failed": failed, "runs": store.list()}



@router.delete("/api/derived/{name:path}")
def delete_derived(name: str):
    store.remove_derived(name)
    return {"runs": store.list()}



class FFTRequest(BaseModel):
    signals: List[str]
    window: str = "hanning"
    method: str = "fft"                 # fft | welch (power spectral density)
    t0: Optional[float] = None
    t1: Optional[float] = None
    points: int = 4000



@router.post("/api/fft")
def fft(req: FFTRequest):
    out: list = []
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
        except KeyError:
            out.append({"id": sid, "missing": True})
            continue
        how: dict = {}
        f, m = fft_for(sid, store.version(sid), t, y, req.window, req.t0, req.t1, req.method, how)
        fx, fy, peak = fft_display(f, m, int(max(200, min(req.points, 20000))))
        # grid: how the samples were put on an even time grid (A1) - resampled, fs, gaps, gapTime, error
        out.append({"id": sid, "n": int(len(fx)), "peak": peak, "x": b64(fx, np.float64), "y": b64(fy, np.float32),
                    "grid": how})
    return {"series": out}



class XYRequest(BaseModel):
    x: str
    ys: List[str]
    alignment: str = "linear"
    t0: Optional[float] = None
    t1: Optional[float] = None
    points: int = 16000



@router.post("/api/xy")
def xy(req: XYRequest):
    try:
        tx, x = store.signal(req.x)
    except KeyError:
        fail(404, "The X signal is no longer open.")
    out: list = []
    for sid in req.ys:
        try:
            ty, y = store.signal(sid)
        except KeyError:
            out.append({"id": sid, "missing": True})
            continue
        xs, ys, ts = xy_pair(tx, x, ty, y, req.alignment, req.t0, req.t1, req.points, with_t=True)
        out.append({"id": sid, "n": int(len(xs)), "x": b64(xs, np.float64), "y": b64(ys, np.float32), "t": b64(ts, np.float64)})
    return {"series": out}



class XYZTrack(BaseModel):
    x: str
    y: str
    z: str



class XYZRequest(BaseModel):
    tracks: List[XYZTrack]
    alignment: str = "linear"
    points: int = 20000



@router.post("/api/xyz")
def xyz(req: XYZRequest):
    """T17c: plain 3D plot - each track's Y and Z on its X signal's samples (svcore.xyz)."""
    from svcore.xyz import xyz_track
    out: list = []
    for tr in req.tracks:
        try:
            sx, sy, sz = store.signal(tr.x), store.signal(tr.y), store.signal(tr.z)
        except KeyError:
            out.append({"id": tr.x, "missing": True})
            continue
        r = xyz_track(sx, sy, sz, req.alignment, max(100, min(req.points, 200000)))
        if r is None:
            out.append({"id": tr.x, "empty": True})
            continue
        out.append({"id": tr.x, "n": int(len(r["t"])), **{k: b64(r[k], np.float64 if k == "t" else np.float32) for k in ("t", "x", "y", "z")}})
    return {"tracks": out}



class ObjectTrackRequest(BaseModel):
    lat: str
    lon: str
    alt: Optional[str] = None
    yaw: Optional[str] = None
    pitch: Optional[str] = None
    roll: Optional[str] = None
    # or the attitude as a quaternion (w, x, y, z - e.g. PX4's vehicle_attitude.q[0..3]): turned into
    # heading / pitch / roll here
    qw: Optional[str] = None
    qx: Optional[str] = None
    qy: Optional[str] = None
    qz: Optional[str] = None
    points: int = 20000



def _unit_guess(v: np.ndarray) -> str:
    """Angles in degrees or radians, from their range."""
    f = v[np.isfinite(v)]
    return "rad" if len(f) and np.nanmax(np.abs(f)) <= 2 * np.pi + 0.05 else "deg"



@router.post("/api/object_track")
def object_track(req: ObjectTrackRequest):
    """An object on the map: its signals - possibly from different files - on one time axis (the
    latitude's samples), each one interpolated in time and NaN outside its own time span; angles
    interpolated the short way round. Latitude / longitude in 1e7 degrees (MAVLink integers) are
    turned into degrees. `course`: the direction of travel in degrees from north (for objects
    without a heading signal)."""
    try:
        t, lat = store.signal(req.lat)
        tlo, lon = store.signal(req.lon)
    except KeyError:
        fail(404, "A position signal of this object is no longer open.")
    t = np.asarray(t, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    keep = np.isfinite(t) & np.isfinite(lat)
    t, lat = t[keep], lat[keep]
    if len(t) < 2:
        fail(400, "The latitude signal has no samples.")
    step = max(1, int(np.ceil(len(t) / max(100, req.points))))
    t, lat = t[::step], lat[::step]

    def onto(tt, vv, angle=False):
        tt = np.asarray(tt, dtype=np.float64)
        vv = np.asarray(vv, dtype=np.float64)
        ok = np.isfinite(tt) & np.isfinite(vv)
        tt, vv = tt[ok], vv[ok]
        if len(tt) < 2:
            return np.full(len(t), np.nan)
        if angle:                                   # the short way round: unwrap, interpolate, wrap
            per = 2 * np.pi if _unit_guess(vv) == "rad" else 360.0
            vv = np.unwrap(vv, period=per)
        out = np.interp(t, tt, vv)
        out[(t < tt[0]) | (t > tt[-1])] = np.nan
        if angle:
            out = np.mod(out + per / 2, per) - per / 2
        return out

    lon_a = onto(tlo, lon)
    if np.nanmax(np.abs(lat)) > 90 or np.nanmax(np.abs(lon_a)) > 180:     # 1e7 degrees (MAVLink ints)
        lat, lon_a = lat / 1e7, lon_a / 1e7
    out: dict = {"n": int(len(t)), "t": b64(t, np.float64), "lat": b64(lat, np.float64), "lon": b64(lon_a, np.float64), "units": {}}
    raw = {}
    for role in ("alt", "yaw", "pitch", "roll"):
        sid = getattr(req, role)
        if not sid:
            continue
        try:
            raw[role] = (sid, *store.signal(sid))
        except KeyError:
            continue
    # angle units: the signal's name says it ("... [rad]", "_deg"), else the object's angles together -
    # if any of them goes beyond 2 pi they are all degrees (one log uses one unit), else radians.
    # (By its own range alone, a pitch of a few degrees would pass for radians.)
    angles = {r: v for r, v in raw.items() if r != "alt"}
    beyond = any(np.nanmax(np.abs(np.asarray(v[2], dtype=np.float64))) > 2 * np.pi + 0.05 for v in angles.values() if len(v[2]))
    for role, (sid, ts, vs) in raw.items():
        v = onto(ts, vs, angle=role != "alt")
        if role != "alt":
            name = sid.split("/", 1)[-1].lower()
            if re.search(r"(\[rad\]|\brad\b|_rad\b|\(rad\))", name):
                out["units"][role] = "rad"
            elif re.search(r"(\[deg\]|\bdeg\b|_deg\b|\(deg\)|°)", name):
                out["units"][role] = "deg"
            else:
                out["units"][role] = "deg" if beyond else "rad"
        out[role] = b64(v, np.float32)
    # a quaternion (Hamilton, w first; body to NED as PX4 logs it) -> roll / pitch / yaw in radians,
    # for the angles not given as signals
    if req.qw and req.qx and req.qy and req.qz:
        try:
            q = [onto(*store.signal(s)) for s in (req.qw, req.qx, req.qy, req.qz)]
        except KeyError:
            q = None
        if q is not None:
            w, x, y, z = q
            norm = np.sqrt(w * w + x * x + y * y + z * z)
            norm[norm == 0] = np.nan
            w, x, y, z = w / norm, x / norm, y / norm, z / norm
            euler = {"roll": np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)),
                     "pitch": np.arcsin(np.clip(2 * (w * y - z * x), -1, 1)),
                     "yaw": np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))}
            for role, v in euler.items():
                if role not in out:
                    out[role] = b64(v, np.float32)
                    out["units"][role] = "rad"
    # direction of travel: bearing between points ~1 s apart (or 3 samples), in degrees from north
    la, lo = np.radians(lat), np.radians(lon_a)
    k = max(1, int(np.searchsorted(t, t[0] + 1.0)) if len(t) > 3 else 1)
    k = max(1, min(k, len(t) // 4 or 1))
    i0, i1 = np.arange(len(t)) - k // 2, np.arange(len(t)) + (k - k // 2)
    i0, i1 = np.clip(i0, 0, len(t) - 1), np.clip(i1, 0, len(t) - 1)
    y = np.sin(lo[i1] - lo[i0]) * np.cos(la[i1])
    x = np.cos(la[i0]) * np.sin(la[i1]) - np.sin(la[i0]) * np.cos(la[i1]) * np.cos(lo[i1] - lo[i0])
    course = np.degrees(np.arctan2(y, x))
    still = (np.abs(y) + np.abs(x)) < 1e-9                       # not moving: keep the last direction
    if still.any():
        idx = np.where(~still, np.arange(len(t)), 0)
        np.maximum.accumulate(idx, out=idx)
        course = course[idx]
    out["course"] = b64(course, np.float32)
    # the ground under the object (bundled elevation): height above ground, and altitudes given
    # relative to the take-off point
    from app import basemap
    out["ground"] = b64(basemap.ground_at(lat, lon_a), np.float32)
    return out



@router.get("/api/discrete")
def discrete(sig: str):
    """On-demand discrete-signal check (wide files skip it at load)."""
    try:
        store.signal(sig)
    except KeyError:
        fail(404, "Signal not found.")
    return {"discrete": store.is_discrete(sig)}



class StatesRequest(BaseModel):
    signals: List[str]
    x0: Optional[float] = None
    x1: Optional[float] = None
    bins: int = 1500                  # about the plot width in pixels



@router.post("/api/states")
def states(req: StatesRequest):
    out: dict = {}
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
        except KeyError:
            continue
        pts, collapsed, end = transitions(t, y, req.x0, req.x1, bins=int(max(100, min(req.bins, 4000))))
        # a state holds until the next change: the last one lasts to the end of its file
        lr = store.runs.get(sid.partition("/")[0])
        if end is not None and lr is not None:
            end = max(end, float(lr.run.end_time) + float(lr.run.time_offset or 0))
        out[sid] = {"points": pts, "tooMany": collapsed, "end": end}
    return {"states": out}


class ConditionRequest(BaseModel):
    text: str
    exit: str = ""
    minDur: float = 0.0
    mergeGap: float = 0.0
    runs: Optional[List[str]] = None


@router.post("/api/conditions/eval")
def condition_eval(req: ConditionRequest):
    """Investigation step 2: where a named condition holds, in each open file (or the ones given)."""
    try:
        return {"results": store.evaluate_condition(req.text, req.exit, req.minDur, req.mergeGap, req.runs)}
    except LoadError as e:
        fail(400, str(e))


class OccRows(BaseModel):
    runs: Dict[str, List[List[float]]]
    names: List[str] = []


@router.post("/api/occurrences/table")
def occurrences_table(req: OccRows):
    """Investigation step 3: one row per stretch of a condition, with max / min / mean of signals."""
    return {"rows": store.occurrence_rows(req.runs, req.names)}


class OccWindows(BaseModel):
    items: List[dict]
    align: str = "start"
    pad: float = 0.5


@router.post("/api/occurrences/windows")
def occurrences_windows(req: OccWindows):
    """Investigation step 3: the stretches of signals on one axis (from start / end / peak)."""
    try:
        return {"items": store.occurrence_windows(req.items, req.align, max(0.0, min(req.pad, 5.0)))}
    except KeyError:
        fail(404, "One of the signals is no longer open.")


class OccDiffer(BaseModel):
    runs: Dict[str, List[List[float]]]
    top: int = 25


@router.post("/api/occurrences/differ")
def occurrences_differ(req: OccDiffer):
    """Investigation step 3: which signals differ most inside the stretches from outside them."""
    return {"items": store.occurrence_differ(req.runs, max(1, min(req.top, 200)))}
