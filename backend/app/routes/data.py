"""Plot data: decimated views, cursor values, statistics, limits, envelopes, segments, spectrograms."""

import base64
from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

from app.common import b64, fail
from app.store import store
from svcore.analysis import spectrogram as make_spectrogram
from svcore.analysis import state_mask, transitions
from svcore.decimate import decimate_for_view, hold_at, interp_at
from svcore.envelope import envelope
from svcore.limits import check_limits
from svcore.ops import compute_signal_stats

router = APIRouter()




# =============================================================================
# DATA
# =============================================================================

class DataRequest(BaseModel):
    signals: List[str]
    x0: Optional[float] = None
    x1: Optional[float] = None
    points: int = 4000



@router.post("/api/data")
def get_data(req: DataRequest):
    """Display points for each signal: min/max decimated inside [x0, x1], coarse outside."""
    out: list = []
    points = int(max(200, min(req.points, 20000)))
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
        except KeyError:
            out.append({"id": sid, "missing": True})
            continue
        rng = [req.x0, req.x1] if req.x0 is not None and req.x1 is not None else None
        xd, yd, dec = decimate_for_view(t, y, rng, points)
        out.append({"id": sid, "n": int(len(xd)), "total": int(len(t)), "decimated": bool(dec),
                    "x": b64(xd, np.float64), "y": b64(yd, np.float32)})
    return {"series": out}



class CursorRequest(BaseModel):
    signals: List[str]
    t: float



@router.post("/api/cursor")
def cursor_values(req: CursorRequest):
    vals: Dict[str, Optional[float]] = {}
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
            # states, text values and other discrete signals: the value in force, never interpolated
            v = hold_at(t, y, req.t) if store.is_state(sid) else interp_at(t, y, req.t)
            vals[sid] = None if v is None or not np.isfinite(v) else float(v)
        except KeyError:
            vals[sid] = None
    return {"t": req.t, "values": vals}



class NeighborRequest(BaseModel):
    signal: str
    t: float
    steps: int = 1          # > 0: forward, < 0: backward (in samples)



@router.post("/api/neighbor")
def neighbor(req: NeighborRequest):
    """Time of the sample `steps` samples after / before time `t` (no interpolation):
    what the arrow keys use to move the cursor from one recorded value to the next."""
    try:
        t, _ = store.signal(req.signal)
    except KeyError:
        fail(404, "Signal not found.")
    n = len(t)
    if n == 0:
        return {"t": req.t, "index": None}
    k = int(req.steps)
    if k >= 0:
        i = int(np.searchsorted(t, req.t, side="right")) + max(0, k - 1)   # first sample after t
        if k == 0:
            i = max(0, int(np.searchsorted(t, req.t, side="left")))
    else:
        i = int(np.searchsorted(t, req.t, side="left")) - 1 - (-k - 1)     # last sample before t
    i = min(n - 1, max(0, i))
    return {"t": float(t[i]), "index": i}



class StatsRequest(BaseModel):
    signals: List[str]
    t0: Optional[float] = None
    t1: Optional[float] = None
    state: Optional[str] = None             # only where this state signal ...
    stateValues: Optional[List[float]] = None   # ... is one of these values
    stateOffset: float = 0.0                # the state signal's display time shift relative to these



def _stretches(sig_id: str, st, sy, offset: float = 0.0):
    """A state signal as stretches [(start, end, value)]: each change to the next one; the last
    lasts to the end of its file. Shared by "statistics while state = X" and the segment list."""
    pts, _c, end = transitions(st, sy, cap=10 ** 9)
    lr = store.runs.get(sig_id.partition("/")[0])
    if lr is not None and end is not None:
        end = max(end, float(lr.run.end_time) + float(lr.run.time_offset or 0) + offset)
    out: list = []
    for i, (a, v) in enumerate(pts):
        b = pts[i + 1][0] if i + 1 < len(pts) else end
        if v is not None and b is not None:
            out.append((float(a), float(b), float(v)))
    return out



class LimitItem(BaseModel):
    id: str
    lo: Optional[float] = None
    hi: Optional[float] = None
    scale: float = 1.0
    offset: float = 0.0
    tOffset: float = 0.0



class LimitsRequest(BaseModel):
    items: List[LimitItem]
    t0: Optional[float] = None          # plot time (time offsets included); None = whole signal
    t1: Optional[float] = None



@router.post("/api/limits")
def limits(req: LimitsRequest):
    """T13: pass / fail of each signal against its limits, on the values as plotted."""
    out: dict = {}
    for it in req.items:
        try:
            t, y = store.signal(it.id)
        except KeyError:
            continue
        tt = np.asarray(t, dtype=np.float64) + it.tOffset
        yy = np.asarray(y, dtype=np.float64) * (it.scale or 1.0) + it.offset
        out[it.id] = check_limits(tt, yy, it.lo, it.hi, req.t0, req.t1)
    return {"results": out}



class EnvelopeRequest(BaseModel):
    signals: List[dict]                 # [{id, scale, offset, tOffset}] - as plotted
    t0: Optional[float] = None
    t1: Optional[float] = None
    points: int = 2000
    pct: float = 5.0



@router.post("/api/envelope")
def envelope_view(req: EnvelopeRequest):
    """T14: the plot's signals (many runs of one quantity) as min/max, percentile band and median."""
    series, ids = [], []
    for s in req.signals:
        try:
            t, y = store.signal(s["id"])
        except KeyError:
            continue
        series.append((np.asarray(t, dtype=np.float64) + float(s.get("tOffset") or 0),
                       np.asarray(y, dtype=np.float64) * float(s.get("scale", 1) or 1) + float(s.get("offset") or 0)))
        ids.append(s["id"])
    r = envelope(series, req.t0, req.t1, req.points, max(0.0, min(req.pct, 49.0)))
    if r is None:
        return {"n": len(ids), "empty": True}
    enc = lambda a, dt=np.float32: b64(np.asarray(a), dt)
    return {"n": len(ids), "pct": r["pct"], "t": enc(r["t"], np.float64),
            **{k: enc(r[k]) for k in ("min", "max", "lo", "median", "hi")},
            "runs": [{"id": i, "deviation": d, "outlier": o} for i, d, o in zip(ids, r["deviation"], r["outlier"])]}



class SegmentsRequest(BaseModel):
    signal: str
    limit: int = 2000



@router.post("/api/segments")
def segments(req: SegmentsRequest):
    """T10: a state signal (flight mode, gear...) split into its stretches, with the text of each
    value when the signal has labels, and the total time per value."""
    try:
        st, sy = store.signal(req.signal)
    except KeyError:
        fail(404, "This signal is no longer open.")
    st = np.asarray(st, dtype=np.float64)
    parts = _stretches(req.signal, st, sy)
    labels = store.labels(req.signal) or {}
    lab = lambda v: labels.get(int(v), None) if float(v).is_integer() else None
    totals: Dict[float, list] = {}
    for a, b, v in parts:
        tot = totals.setdefault(v, [0.0, 0])
        tot[0] += b - a; tot[1] += 1
    return {
        "segments": [{"t0": a, "t1": b, "value": v, "label": lab(v)} for a, b, v in parts[:max(1, req.limit)]],
        "total": len(parts),
        "byValue": [{"value": v, "label": lab(v), "duration": d, "count": n}
                    for v, (d, n) in sorted(totals.items(), key=lambda kv: -kv[1][0])],
    }



class SegmentAcrossRequest(BaseModel):
    runs: List[str]
    state: str                      # the state signal's NAME (the same name in every run)
    value: float
    occurrence: int = 1             # 1 = first, 2 = second ...; -1 = last



def segment_windows(runs: List[str], state: str, value: float, occurrence: int) -> List[dict]:
    """T10b: the same segment (e.g. the 2nd AUTO) in every run: [{run, t0, t1} or {run, missing}].
    Uses the stretches of the run's own state signal, in that run's time (offset included)."""
    out: list = []
    for rid in runs:
        sid = f"{rid}/{state}"
        try:
            st, sy = store.signal(sid)
        except KeyError:
            out.append({"run": rid, "missing": "signal"})
            continue
        parts = [p for p in _stretches(sid, np.asarray(st, dtype=np.float64), sy) if p[2] == float(value)]
        k = occurrence - 1 if occurrence > 0 else len(parts) + occurrence
        if not parts or not 0 <= k < len(parts):
            out.append({"run": rid, "missing": "segment", "count": len(parts)})
            continue
        a, b, _v = parts[k]
        out.append({"run": rid, "t0": a, "t1": b, "count": len(parts)})
    return out



@router.post("/api/segments/across")
def segments_across(req: SegmentAcrossRequest):
    if req.occurrence == 0:
        fail(400, "Occurrence starts at 1 (first); -1 is the last.")
    return {"windows": segment_windows(req.runs, req.state, req.value, req.occurrence)}



def _windowed(sid: str, windows: Optional[Dict[str, List[float]]]):
    """A signal cut to its run's segment window, on "time since the segment started" (T10b),
    or the whole signal on its own time when there are no windows."""
    t, y = store.signal(sid)
    if not windows:
        return t, y
    w = windows.get(sid.partition("/")[0])
    if not w:
        raise KeyError(sid)
    t = np.asarray(t, dtype=np.float64)
    m = (t >= w[0]) & (t <= w[1])
    return t[m] - w[0], np.asarray(y)[m]



class SparkRequest(BaseModel):
    signals: List[str]
    points: int = 40



@router.post("/api/sparks")
def sparks(req: SparkRequest):
    """T22: small pictures of whole signals for the file list (only the rows on screen ask)."""
    from app.store import spark
    out: dict = {}
    for sid in req.signals[:200]:
        try:
            t, y = store.signal(sid)
            out[sid] = spark(t, y, max(8, min(int(req.points), 120)))
        except (KeyError, ValueError, TypeError):     # closed, or not numeric: no picture
            out[sid] = None
    return {"sparks": out}



@router.post("/api/stats")
def stats(req: StatsRequest):
    res: dict = {}
    where = None
    seg_total, seg_count = 0.0, 0
    if req.state and req.stateValues:
        try:
            st, sy = store.signal(req.state)
            st = np.asarray(st, dtype=np.float64) + req.stateOffset
            where = (st, sy)
        except KeyError:
            fail(404, "The state signal is no longer open.")
        want = set(float(v) for v in req.stateValues)
        for a, b, v in _stretches(req.state, st, sy, req.stateOffset):
            if float(v) not in want:
                continue
            a2, b2 = max(a, req.t0) if req.t0 is not None else a, min(b, req.t1) if req.t1 is not None else b
            if b2 > a2:
                seg_total += b2 - a2
                seg_count += 1
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
        except KeyError:
            continue
        if where is None:
            s = compute_signal_stats(t, y, req.t0, req.t1)
        else:
            t = np.asarray(t, dtype=np.float64)
            m = state_mask(t, where[0], where[1], req.stateValues)
            if req.t0 is not None:
                m &= t >= req.t0
            if req.t1 is not None:
                m &= t <= req.t1
            s = compute_signal_stats(t[m], np.asarray(y)[m]) if m.any() else {}
            if s:
                s = {**s, "duration": seg_total, "segments": seg_count}     # time in the state, not first-to-last
        if s:
            res[sid] = s
    return {"stats": res}



class SpecRequest(BaseModel):
    signal: str
    x0: Optional[float] = None
    x1: Optional[float] = None
    nfft: int = 1024
    width: int = 800
    height: int = 300
    fmax: Optional[float] = None



@router.post("/api/spectrogram")
def spectrogram_ep(req: SpecRequest):
    """Spectrogram image of one signal over the visible time window (power in dB, 0..255 coded)."""
    try:
        t, y = store.signal(req.signal)
    except KeyError:
        fail(404, "The signal is no longer open.")
    try:
        r = make_spectrogram(t, y, req.x0, req.x1, int(max(64, min(req.nfft, 16384))),
                             int(max(50, min(req.width, 3000))), int(max(50, min(req.height, 1500))), req.fmax)
    except ValueError as e:
        fail(400, str(e))
    f = r["f"]
    step = float(f[1] - f[0]) if len(f) > 1 else r["df"]
    return {"nf": int(len(f)), "nt": int(len(r["t"])), "f0": max(0.0, float(f[0]) - step / 2), "f1": float(f[-1]) + step / 2,
            "t0": float(r["t"][0]), "t1": float(r["t"][-1]), "img": base64.b64encode(np.ascontiguousarray(r["img"]).tobytes()).decode(),
            "dbLo": r["dbLo"], "dbHi": r["dbHi"], "fs": r["fs"], "nfft": r["nfft"], "df": r["df"], "dt": r["dt"],
            # F24: the signal's own extent - the whole-signal view spans it like the signal's time plot
            # (the image itself starts and ends half a window inside)
            "sigT0": float(t[0]), "sigT1": float(t[-1])}
