"""Plot data: decimated views, cursor values, statistics, limits, envelopes, segments, spectrograms."""

import base64
from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.common import b64, fail, y_reference
from app.store import store
from svcore.analysis import spectrogram as make_spectrogram
from svcore.analysis import OpError, _unwrap, align_to, state_mask, transitions, wrap_diff, wrap_period
from svcore.decimate import hold_at, interp_at, view_shifted
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
    format: str = "json"            # "json" (base64 inside JSON) | "bin" (P3: a JSON header + raw arrays)


def pack_series(parts: List[dict]) -> bytes:
    """P3: the binary /api/data answer - a little-endian uint32 with the header's length, the JSON
    header ({"series": [{id, n, total, decimated, yRef, xAt, yAt} or {id, missing}]}), then each
    series' x (float64) and y - yRef (float32) at the byte offsets the header gives (x at a multiple
    of 8, so the browser views the bytes as typed arrays without copying them)."""
    import json as _json
    body = bytearray()
    heads = []
    for p in parts:
        if p.get("missing"):
            heads.append({"id": p["id"], "missing": True})
            continue
        xb = np.ascontiguousarray(p["x"], dtype="<f8").tobytes()
        yb = np.ascontiguousarray(p["y"] - p["yRef"], dtype="<f4").tobytes()
        x_at = len(body)
        body += xb
        y_at = len(body)
        body += yb
        body += bytes((-len(body)) % 8)
        heads.append({"id": p["id"], "n": p["n"], "total": p["total"], "decimated": p["decimated"], "yRef": p["yRef"],
                      "xAt": x_at, "yAt": y_at})
    head = _json.dumps({"series": heads}).encode()
    start = 4 + len(head)
    pad = (-start) % 8
    head += b" " * pad                     # (spaces: still valid JSON) - the arrays start at a multiple of 8
    return len(head).to_bytes(4, "little") + head + bytes(body)


@router.post("/api/data")
def get_data(req: DataRequest):
    """Display points for each signal: min/max decimated inside [x0, x1], coarse outside."""
    parts: list = []
    points = int(max(200, min(req.points, 20000)))
    for sid in req.signals:
        try:
            t, y, off = store.signal_parts(sid)          # P1: the window shifted, not the time vector
        except KeyError:
            parts.append({"id": sid, "missing": True})
            continue
        rng = [req.x0, req.x1] if req.x0 is not None and req.x1 is not None else None
        xd, yd, dec = view_shifted(t, y, off, rng, points)
        yd = np.asarray(yd, dtype=np.float64)
        parts.append({"id": sid, "n": int(len(xd)), "total": int(len(t)), "decimated": bool(dec),
                      "x": xd, "y": yd, "yRef": y_reference(yd)})
    if req.format == "bin":
        return Response(pack_series(parts), media_type="application/octet-stream")
    # the JSON answer keeps its meaning for any client that reads it (absolute float32 values)
    return {"series": [p if p.get("missing") else
                       {**{k: p[k] for k in ("id", "n", "total", "decimated")},
                        "x": b64(p["x"], np.float64), "y": b64(p["y"], np.float32)} for p in parts]}



class CursorRequest(BaseModel):
    signals: List[str]
    t: float



@router.post("/api/cursor")
def cursor_values(req: CursorRequest):
    vals: Dict[str, Optional[float]] = {}
    for sid in req.signals:
        try:
            t, y, off = store.signal_parts(sid)
            # states, text values and other discrete signals: the value in force, never interpolated
            v = hold_at(t, y, req.t - off) if store.is_state(sid) else interp_at(t, y, req.t - off)
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
        t, _, off = store.signal_parts(req.signal)
    except KeyError:
        fail(404, "Signal not found.")
    n = len(t)
    if n == 0:
        return {"t": req.t, "index": None}
    k = int(req.steps)
    q = req.t - off
    if k >= 0:
        i = int(np.searchsorted(t, q, side="right")) + max(0, k - 1)       # first sample after t
        if k == 0:
            i = max(0, int(np.searchsorted(t, q, side="left")))
    else:
        i = int(np.searchsorted(t, q, side="left")) - 1 - (-k - 1)         # last sample before t
    i = min(n - 1, max(0, i))
    return {"t": float(t[i]) + off, "index": i}



class StatsRequest(BaseModel):
    signals: List[str]
    t0: Optional[float] = None
    t1: Optional[float] = None
    state: Optional[str] = None             # only where this state signal ...
    stateValues: Optional[List[float]] = None   # ... is one of these values
    stateOffset: float = 0.0                # the state signal's display time shift relative to these



def _stretches(sig_id: str, st, sy, offset: float = 0.0, where=None):
    """A state signal as stretches [(start, end, value)]: each change to the next one; the last
    lasts to the end of its file. Shared by "statistics while state = X", the segment list and
    the command line's checks (`where`: their own Store; default the app's)."""
    pts, _c, end = transitions(st, sy, cap=10 ** 9)
    lr = (where or store).runs.get(sig_id.partition("/")[0])
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
            t, y, off = store.signal_parts(it.id)
        except KeyError:
            continue
        tt = np.asarray(t, dtype=np.float64) + (it.tOffset + off)      # one copy, not two
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
            t, y, off = store.signal_parts(s["id"])
        except KeyError:
            continue
        series.append((np.asarray(t, dtype=np.float64) + (float(s.get("tOffset") or 0) + off),
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
            t, y, _off = store.signal_parts(sid)        # the shape only: the time offset does not matter
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
            st, sy, soff = store.signal_parts(req.state)
            st = np.asarray(st, dtype=np.float64) + (req.stateOffset + soff)
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
            t, y, off = store.signal_parts(sid)        # P1: the window shifted; the stats cache hits again
        except KeyError:
            continue
        t0 = None if req.t0 is None else req.t0 - off
        t1 = None if req.t1 is None else req.t1 - off
        if where is None:
            s = compute_signal_stats(t, y, t0, t1)
        else:
            t = np.asarray(t, dtype=np.float64)
            m = state_mask(t, where[0] - off, where[1], req.stateValues)
            if t0 is not None:
                m &= t >= t0
            if t1 is not None:
                m &= t <= t1
            # the mask, not t[m]: the time between two stretches is not a gap to weigh (A3)
            s = compute_signal_stats(t, y, mask=m) if m.any() else {}
            if s:
                s = {**s, "duration": seg_total, "segments": seg_count}     # time in the state, not first-to-last
        if s and off and "t_abs_max" in s:
            s = {**s, "t_abs_max": s["t_abs_max"] + off}                      # L8: on the shown time axis
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
        t, y, off = store.signal_parts(req.signal)     # P1: redrawn on every pan - no time copy
    except KeyError:
        fail(404, "The signal is no longer open.")
    try:
        r = make_spectrogram(t, y, None if req.x0 is None else req.x0 - off, None if req.x1 is None else req.x1 - off, int(max(64, min(req.nfft, 16384))),
                             int(max(50, min(req.width, 3000))), int(max(50, min(req.height, 1500))), req.fmax)
    except ValueError as e:
        fail(400, str(e))
    f = r["f"]
    step = float(f[1] - f[0]) if len(f) > 1 else r["df"]
    return {"nf": int(len(f)), "nt": int(len(r["t"])), "f0": max(0.0, float(f[0]) - step / 2), "f1": float(f[-1]) + step / 2,
            "t0": float(r["t"][0]) + off, "t1": float(r["t"][-1]) + off, "img": base64.b64encode(np.ascontiguousarray(r["img"]).tobytes()).decode(),
            "dbLo": r["dbLo"], "dbHi": r["dbHi"], "fs": r["fs"], "nfft": r["nfft"], "df": r["df"], "dt": r["dt"],
            # F24: the signal's own extent - the whole-signal view spans it like the signal's time plot
            # (the image itself starts and ends half a window inside)
            "sigT0": float(t[0]) + off, "sigT1": float(t[-1]) + off}



# =============================================================================
# T25: the error between two signals (simulation vs flight, model vs test), overall and per segment
# =============================================================================

class ErrorSegmentsRequest(BaseModel):
    a: str                              # e.g. the simulation
    b: str                              # e.g. the flight; aligned onto a's time
    state: Optional[str] = None         # a state signal (flight mode...): one row per stretch of it
    alignment: str = "linear"
    wrap: Optional[str] = None          # L9: "360" / "2pi" - an angle error, wrapped (as the "sub" op's wrap)


def _err_summary(e: np.ndarray, t: np.ndarray) -> dict:
    ok = np.isfinite(e)
    if not ok.any():
        return {"n": 0}
    x = e[ok]
    return {"n": int(x.size), "rms": float(np.sqrt(np.mean(x * x))), "mean": float(np.mean(x)),
            "maxAbs": float(np.max(np.abs(x))), "tMaxAbs": float(t[ok][int(np.argmax(np.abs(x)))])}


@router.post("/api/error-segments")
def error_segments(req: ErrorSegmentsRequest):
    """The error A - B (B aligned onto A's samples) where both have data: RMS, mean and largest |error|
    over the whole overlap, and - with a state signal - for every stretch of the state (each flight
    mode, each test phase), so the phase where the model and the flight part ways stands out."""
    try:
        ta, ya = store.signal(req.a)
        tb, yb = store.signal(req.b)
    except KeyError:
        fail(404, "One of the signals is no longer open.")
    if req.alignment not in ("linear", "nearest"):
        fail(400, "Alignment is linear or nearest.")
    ta = np.asarray(ta, dtype=np.float64)
    try:
        period = wrap_period(req.wrap)
    except OpError as err:
        fail(400, str(err))
    if period:
        yb = _unwrap(np.asarray(yb, dtype=np.float64), period)
    e = np.asarray(ya, dtype=np.float64) - align_to(ta, np.asarray(tb, dtype=np.float64), yb, req.alignment)
    if period:
        e = wrap_diff(e, period)
    if req.alignment == "nearest":            # nearest has no "outside": keep A's samples inside B's time
        e[(ta < float(np.min(tb))) | (ta > float(np.max(tb)))] = np.nan
    rows = []
    if req.state:
        try:
            st, sy = store.signal(req.state)
        except KeyError:
            fail(404, "The state signal is no longer open.")
        labels = store.labels(req.state) or {}
        seen: Dict[float, int] = {}
        for a0, a1, v in _stretches(req.state, np.asarray(st, dtype=np.float64), sy):
            seen[v] = seen.get(v, 0) + 1
            i0, i1 = int(np.searchsorted(ta, a0, "left")), int(np.searchsorted(ta, a1, "left"))
            summ = _err_summary(e[i0:i1], ta[i0:i1])
            if not summ["n"]:
                continue                        # the two signals do not overlap in this stretch
            lab = labels.get(int(v)) if float(v).is_integer() else None
            rows.append({"t0": float(a0), "t1": float(a1), "value": float(v), "label": lab, "occurrence": seen[v], **summ})
    return {"total": _err_summary(e, ta), "rows": rows}
