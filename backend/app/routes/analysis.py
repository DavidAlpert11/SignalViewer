"""Analysis: derived signals and transforms, FFT, X-Y / XYZ, object tracks, states."""

import asyncio
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.common import b64, fail, y_reference
from app.store import LoadError
from app.store import WIDE as WIDE_PARAMS, store
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
        t, y = compute(req.op, [store.signal(s) for s in req.sources], req.params or {}, [store.is_state(s) for s in req.sources])
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
            d = await asyncio.to_thread(store.add_derived, it.op, it.sources, it.params or {}, it.name, True)
            ok.append(d.name)
        except Exception as e:
            failed.append({"name": it.name, "message": str(e)})
    return {"restored": ok, "failed": failed, "runs": store.list()}



class DerivedRename(BaseModel):
    old: str
    new: str


@router.post("/api/derived/rename")
def rename_derived(req: DerivedRename):
    """A derived signal renamed in place; the signals made from it follow (owner, 2026-11-03)."""
    try:
        name = store.rename_derived(req.old, req.new)
    except KeyError:
        fail(404, f"No signal named \"{req.old}\" was made here (it may have been deleted).")
    except ValueError as e:
        fail(400, str(e))
    return {"id": f"derived/{name}", "name": name, "runs": store.list()}


@router.delete("/api/derived/{name:path}")
def delete_derived(name: str):
    store.remove_derived(name)
    return {"runs": store.list()}



class FiltersRequest(BaseModel):
    signal: str                         # the spectrum's signal: its file has the filters' parameters
    t0: Optional[float] = None
    t1: Optional[float] = None
    fs: Optional[float] = None          # the spectrum's sample rate (Hz): the filters run at it
    points: int = 2000



@router.post("/api/filters")
def filters(req: FiltersRequest):
    """ArduPilot's gyro filters over [t0, t1] (svcore.filters): the harmonic notches' lines and the
    response of all the filters, for the FFT plot's "Filters" view. {"setup": None} when the file
    has no such parameters."""
    from svcore.filters import filter_setup, response
    from svcore.naming import without_unit
    run_id = req.signal.partition("/")[0]
    try:
        lr = store.get(run_id)
    except KeyError:
        return {"setup": None}
    fl = getattr(lr.run, "_flightlog", None)
    params = dict(fl.params) if fl is not None else {}
    if not any(k.startswith(("INS_HNTCH_", "INS_HNTC2_", "INS_GYRO_FILTER")) for k in params):
        return {"setup": None}
    bare = {without_unit(n): n for n in lr.run.signals}

    def signals_of(name: str):
        n = bare.get(name)
        if n is None:
            return None
        try:
            return store.signal(f"{run_id}/{n}")
        except KeyError:
            return None
    setup = filter_setup(params, signals_of, req.t0, req.t1)
    if not setup["notches"] and not setup["lpf"]:
        return {"setup": None}
    out: dict = {"setup": setup}
    if req.fs and req.fs > 0:
        f = np.linspace(0.0, req.fs / 2.0, int(max(100, min(req.points, 20000))))
        out.update({"f": b64(f, np.float64), "gain": b64(response(setup, f, req.fs), np.float32), "fs": req.fs})
    return out



class StepRequest(BaseModel):
    pairs: List[List[str]]              # [[setpoint id, measured id], ...]
    t0: Optional[float] = None
    t1: Optional[float] = None
    length: float = 0.5



@router.post("/api/stepresp")
def stepresp(req: StepRequest):
    """1.21: a control loop's step response from flight data (svcore.stepresp), per pair."""
    from svcore.stepresp import step_response
    out: list = []
    for pair in req.pairs:
        if len(pair) != 2:
            continue
        try:
            ti, x = store.signal(pair[0])
            to, y = store.signal(pair[1])
        except KeyError:
            out.append({"pair": pair, "error": "missing"})
            continue
        r = step_response(ti, x, to, y, req.t0, req.t1, float(min(max(req.length, 0.05), 2.0)))
        if "step" in r:
            r["t"], r["step"] = b64(r["t"], np.float64), b64(r["step"], np.float32)
        out.append({"pair": pair, **r})
    return {"series": out}



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
    relative: bool = False          # P3: y as float32 around a float64 reference "yRef" (the app asks so)



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
        # P3: asked relative (the app does), y goes as float32 around a float64 reference - a latitude in
        # float32 is rounded by up to ~0.2 m (an RTK track); absolute float32 for any other client
        ref = y_reference(np.asarray(ys, dtype=np.float64)) if req.relative else 0.0
        out.append({"id": sid, "n": int(len(xs)), "x": b64(xs, np.float64), "y": b64(np.asarray(ys, dtype=np.float64) - ref, np.float32),
                    "t": b64(ts, np.float64), **({"yRef": ref} if req.relative else {})})
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
    # the track coloured by another signal (owner, 2026-11-03): a state (the flight mode - held until
    # its next sample, colorStep) or a value (altitude, speed - interpolated), on the track's times
    color: Optional[str] = None
    colorStep: bool = False
    # N5 (owner's decision 3): an object with no angles of its own, drawn by its motion - heading =
    # course over ground, pitch = flight-path angle (climb over ground speed), roll unknown; below
    # minSpeed (m/s) the last valid heading / pitch is held, so a hovering object does not spin on noise
    attitude: Optional[str] = None
    minSpeed: float = 1.0



def _unit_guess(v: np.ndarray) -> str:
    """Angles in degrees or radians, from their range."""
    f = v[np.isfinite(v)]
    return "rad" if len(f) and np.nanmax(np.abs(f)) <= 2 * np.pi + 0.05 else "deg"


from svcore.objcompare import angle_units  # noqa: E402  L12: one place for the Automatic angle-unit rule


class AngleUnitsRequest(BaseModel):
    yaw: Optional[str] = None
    pitch: Optional[str] = None
    roll: Optional[str] = None


@router.post("/api/angle_units")
def angle_units_ep(req: AngleUnitsRequest):
    """26.A5: what "Automatic" takes an object's angles to be, and why (the object dialog shows it)."""
    raw = {}
    for role in ("yaw", "pitch", "roll"):
        sid = getattr(req, role)
        if sid:
            try:
                raw[role] = (sid, *store.signal(sid))
            except KeyError:
                continue
    return {"units": {r: {"unit": u, "why": w} for r, (u, w) in angle_units(raw).items()}}



def motion_attitude(t, lat, lon, alt, i0, i1, min_speed: float = 1.0):
    """N5: an attitude from the motion alone, for an object with no angles of its own (a GPS
    receiver): heading = course over ground, pitch = flight-path angle atan(climb / ground speed),
    both in degrees, over the same ~1 s baseline as `course` (i0 / i1: the sample pairs). Where the
    ground speed is below `min_speed` (m/s) the last valid value is held (the first valid one before
    it), so a hovering or parked object does not spin on noise. Pitch is None without an altitude.
    Roll is not returned: it cannot be known from the track."""
    la, lo = np.radians(lat), np.radians(lon)
    dt = t[i1] - t[i0]
    y = np.sin(lo[i1] - lo[i0]) * np.cos(la[i1])
    x = np.cos(la[i0]) * np.sin(la[i1]) - np.sin(la[i0]) * np.cos(la[i1]) * np.cos(lo[i1] - lo[i0])
    hav = np.sin((la[i1] - la[i0]) / 2) ** 2 + np.cos(la[i0]) * np.cos(la[i1]) * np.sin((lo[i1] - lo[i0]) / 2) ** 2
    dist = 2 * 6371008.8 * np.arcsin(np.sqrt(np.clip(hav, 0, 1)))
    with np.errstate(invalid="ignore", divide="ignore"):
        gs = np.where(dt > 0, dist / dt, np.nan)
    ok = np.isfinite(gs) & (gs >= min_speed)

    def held(v):
        v = np.where(ok & np.isfinite(v), v, np.nan)
        good = np.isfinite(v)
        if not good.any():
            return np.full(len(v), np.nan)
        idx = np.where(good, np.arange(len(v)), 0)
        np.maximum.accumulate(idx, out=idx)
        first = int(np.argmax(good))
        idx[:first] = first
        return v[idx]

    yaw = held(np.mod(np.degrees(np.arctan2(y, x)), 360.0))
    pitch = None
    if alt is not None and np.isfinite(alt).any():
        with np.errstate(invalid="ignore", divide="ignore"):
            climb = np.where(dt > 0, (alt[i1] - alt[i0]) / dt, np.nan)
            pitch = held(np.degrees(np.arctan2(climb, gs)))
    return yaw, pitch


@router.post("/api/object_track")
def object_track(req: ObjectTrackRequest):
    return track_of(store, req)


def no_position_as_gap(lat: np.ndarray, lon: np.ndarray):
    """P2: latitude / longitude with every sample that is not a position (0, 0 together, out of range,
    not finite) set to NaN in both (see track_of)."""
    lat = np.asarray(lat, dtype=np.float64).copy()
    lon = np.asarray(lon, dtype=np.float64).copy()
    with np.errstate(invalid="ignore"):
        bad = ~(np.isfinite(lat) & np.isfinite(lon)) | ((lat == 0) & (lon == 0)) | (np.abs(lat) > 90) | (np.abs(lon) > 180)
    lat[bad] = np.nan
    lon[bad] = np.nan
    return lat, lon


def track_of(store, req: ObjectTrackRequest):
    """An object on the map: its signals - possibly from different files - on one time axis (the
    latitude's samples), each one interpolated in time and NaN outside its own time span; angles
    interpolated the short way round. Latitude / longitude in 1e7 degrees (MAVLink integers) are
    turned into degrees. `course`: the direction of travel in degrees from north (for objects
    without a heading signal).

    P2 - what is a position (the one rule; every drawing and export reads tracks from here): a sample
    whose latitude AND longitude are both exactly 0, or outside +-90 / +-180, or not finite, is NOT a
    position - it becomes a gap (NaN). Receivers and autopilots write 0, 0 for "no fix" (ArduPilot's
    EAHR without an external AHRS: 0, 0 for the whole flight). `valid`: how many samples are positions;
    an object with none is drawn as nothing and left out of exports."""
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
    lat, lon_a = no_position_as_gap(lat, lon_a)
    out: dict = {"n": int(len(t)), "t": b64(t, np.float64), "lat": b64(lat, np.float64), "lon": b64(lon_a, np.float64), "units": {},
                 "valid": int(np.count_nonzero(np.isfinite(lat)))}
    if req.color:
        try:
            tc, vc = (np.asarray(a, dtype=np.float64) for a in store.signal(req.color))
            ok = np.isfinite(tc) & np.isfinite(vc)
            tc, vc = tc[ok], vc[ok]
            if len(tc):
                if req.colorStep:             # the value in force at each moment (no blend of two modes)
                    k = np.searchsorted(tc, t, side="right") - 1
                    cv = np.where(k >= 0, vc[np.clip(k, 0, len(vc) - 1)], np.nan)
                else:
                    cv = np.interp(t, tc, vc)
                    cv[(t < tc[0]) | (t > tc[-1])] = np.nan
                out["color"] = b64(cv, np.float32)
        except KeyError:
            pass                              # the colour's signal is no longer open: one colour
    raw = {}
    for role in ("alt", "yaw", "pitch", "roll"):
        sid = getattr(req, role)
        if not sid:
            continue
        try:
            raw[role] = (sid, *store.signal(sid))
        except KeyError:
            continue
    # angle units: the name, else the object's angles together (angle_units, 26.A5: with why)
    guess = angle_units({r: v for r, v in raw.items() if r != "alt"})
    out["unitWhy"] = {}
    for role, (sid, ts, vs) in raw.items():
        v = onto(ts, vs, angle=role != "alt")
        if role != "alt":
            out["units"][role], out["unitWhy"][role] = guess[role]
        else:
            out["_alt"] = v                       # for a "motion" pitch (dropped before the reply)
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
    # its own name: `k` above is an index array, and with numpy 2.5 mypy typed this one by it (ci failed)
    step = max(1, int(np.searchsorted(t, t[0] + 1.0)) if len(t) > 3 else 1)
    step = max(1, min(step, len(t) // 4 or 1))
    i0, i1 = np.arange(len(t)) - step // 2, np.arange(len(t)) + (step - step // 2)
    i0, i1 = np.clip(i0, 0, len(t) - 1), np.clip(i1, 0, len(t) - 1)
    y = np.sin(lo[i1] - lo[i0]) * np.cos(la[i1])
    x = np.cos(la[i0]) * np.sin(la[i1]) - np.sin(la[i0]) * np.cos(la[i1]) * np.cos(lo[i1] - lo[i0])
    course = np.degrees(np.arctan2(y, x))
    still = (np.abs(y) + np.abs(x)) < 1e-9                       # not moving: keep the last direction
    if still.any():
        idx = np.where(~still, np.arange(len(t)), 0)
        np.maximum.accumulate(idx, out=idx)
        course = course[idx]
    if req.attitude == "motion" and "yaw" not in out:
        yaw_m, pitch_m = motion_attitude(t, lat, lon_a, out.get("_alt"), i0, i1, req.minSpeed)
        out["yaw"] = b64(yaw_m, np.float32)
        out["units"]["yaw"] = "deg"
        if pitch_m is not None and "pitch" not in out:
            out["pitch"] = b64(pitch_m, np.float32)
            out["units"]["pitch"] = "deg"
        out["derived"] = "motion"
    out.pop("_alt", None)
    out["course"] = b64(course, np.float32)
    # the ground under the object (bundled elevation): height above ground, and altitudes given
    # relative to the take-off point
    from app import basemap
    out["ground"] = b64(basemap.ground_at(lat, lon_a), np.float32)
    return out



class PositionCountRequest(BaseModel):
    objects: List[dict]                  # [{lat, lon}] signal ids


@router.post("/api/object_positions")
def object_positions(req: PositionCountRequest):
    """P2: for each object (a found candidate before it is added), how many of its samples are positions
    by track_of's rule - {valid, total}; a missing signal counts as none. Cheap: no track is built."""
    out = []
    for o in req.objects:
        try:
            t, lat = store.signal(o["lat"])
            tlo, lon = store.signal(o["lon"])
        except (KeyError, TypeError):
            out.append({"valid": 0, "total": 0})
            continue
        lat = np.asarray(lat, dtype=np.float64)
        lon_a = np.asarray(lon, dtype=np.float64)
        if len(lon_a) != len(lat):
            lon_a = np.interp(np.asarray(t, dtype=np.float64), np.asarray(tlo, dtype=np.float64), lon_a)
        fin = np.isfinite(lat) & np.isfinite(lon_a)
        if fin.any() and (np.abs(lat[fin]).max() > 90 or np.abs(lon_a[fin]).max() > 180):
            lat, lon_a = lat / 1e7, lon_a / 1e7
        la, _lo = no_position_as_gap(lat, lon_a)
        out.append({"valid": int(np.count_nonzero(np.isfinite(la))), "total": int(len(la))})
    return {"objects": out}



@router.get("/api/discrete")
def discrete(sig: str):
    """On-demand discrete-signal check (wide files skip it at load) - and why (26.A5): what was
    detected (a few whole-number levels: how many), and the user's correction for its name."""
    try:
        _t, y = store.signal(sig)
    except KeyError:
        fail(404, "Signal not found.")
    detected = store.detected_discrete(sig)
    levels = None
    if detected:
        v = np.asarray(y[:: max(1, len(y) // 200_000)], dtype=np.float64)
        levels = int(len(np.unique(v[np.isfinite(v)])))
    return {"discrete": store.is_discrete(sig), "detected": detected, "levels": levels,
            "readAs": store.read_as.get(sig.partition("/")[2])}


class ReadAsRequest(BaseModel):
    names: Dict[str, str] = {}          # signal name -> "state" | "value"


@router.post("/api/read_as")
def read_as(req: ReadAsRequest):
    """26.A5: how numeric signals are read between samples, as the user corrected it (by name)."""
    store.set_read_as(req.names)
    return {"runs": store.list()}



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


class FirstChangeRequest(BaseModel):
    a: float
    b: float
    sigs: List[str] = []
    runs: List[str] = []
    baseA: Optional[float] = None
    baseB: Optional[float] = None
    k: float = 4.0            # times the usual noise
    persist: int = 3          # samples in a row
    refs: List[str] = []      # Q130: the reference runs (a change there too is marked, sorted last)
    event: Optional[str] = None   # Q131: the event's signal (missing: the most unusual in the span)


@router.post("/api/firstchange")
def first_change_route(req: FirstChangeRequest):
    """Investigation step 4: which signals changed first around [a, b] (candidates, not causes)."""
    if req.b <= req.a:
        fail(400, "Put both cursors around the moment (the second after the first).")
    from collections import Counter
    given: Optional[Tuple[float, float]] = None
    if req.baseA is not None and req.baseB is not None and req.baseB > req.baseA:
        given = (req.baseA, req.baseB)
    items = store.first_changes(req.sigs, req.runs, req.a, req.b, given, max(1.0, req.k), max(1, req.persist))
    # the baseline shown: the one most signals used (the default is fitted to where each one's data starts)
    used = Counter(tuple(x["base"]) for x in items if x.get("base"))
    base = list(used.most_common(1)[0][0]) if used else [req.a, req.a]
    # nothing before the span to learn the usual level from: say so (it is not "nothing changed")
    no_room = bool(items) and all(x["status"] == "nodata" for x in items) and base[1] - base[0] <= 0
    from svcore.firstchange import WEIGHTS
    more = store.change_clusters(items, req.a, req.b, [r for r in req.refs if r not in req.runs], max(1.0, req.k),
                                 max(1, req.persist), req.event)
    skipped: Dict[str, int] = {}
    for x in items:
        if x.get("skip"):
            skipped[x["skip"]] = skipped.get(x["skip"], 0) + 1
    return {"items": items, "base": base, "noRoom": no_room, **more, "weights": WEIGHTS, "skipped": skipped}


class SuggestConditionRequest(BaseModel):
    a: float
    b: float
    sigs: List[str] = []


@router.post("/api/condition/suggest")
def suggest_condition_route(req: SuggestConditionRequest):
    """"Find similar": the signal most unusual inside the selection, and a condition like it."""
    if req.b <= req.a:
        fail(400, "Put both cursors around the moment (the second after the first).")
    return store.suggest_condition(req.sigs, req.a, req.b)


class LagRequest(BaseModel):
    a: str
    b: str
    t0: float
    t1: float


@router.post("/api/lag")
def lag_route(req: LagRequest):
    """Investigation step 4: how much B follows (or leads) A in a window."""
    try:
        return store.lag_between(req.a, req.b, req.t0, req.t1)
    except KeyError:
        fail(404, "One of the signals is no longer open.")


class ParamsRequest(BaseModel):
    runs: Optional[List[str]] = None


@router.post("/api/runs/params")
def runs_params(req: ParamsRequest):
    """Investigation step 5: per file, the values that tell runs apart (constant signals, name numbers)."""
    return {"params": store.run_params(req.runs)}


# F3: the parameters of a run (any format) and two runs compared - svcore/runinfo.py
@router.get("/api/runs/{run_id}/parameters")
def run_parameters(run_id: str):
    """Every parameter of a run with where it comes from (log / file / constant / name)."""
    from svcore import runinfo
    try:
        run = store.get(run_id).run
    except KeyError:
        fail(404, "File is not open.")
    return {"params": runinfo.parameters(run, WIDE_PARAMS)}


class ParamsCompareRequest(BaseModel):
    a: str
    b: str


@router.post("/api/runs/parameters/compare")
def compare_parameters(req: ParamsCompareRequest):
    """Two runs' parameters - only what differs (and what only one of them has)."""
    from svcore import runinfo
    try:
        ra, rb = store.get(req.a).run, store.get(req.b).run
    except KeyError:
        fail(404, "One of the two files is no longer open - open it again and compare.")
    return runinfo.compare(runinfo.parameters(ra, WIDE_PARAMS), runinfo.parameters(rb, WIDE_PARAMS))


@router.get("/api/runs/{run_id}/overview")
def run_overview(run_id: str, rows: List[str] = Query(default=[])):
    """Investigation step 7: phases and automatic flags of a run, for the overview strip (and the
    stretches of the state signals the user put in it as rows)."""
    try:
        return store.overview(run_id, rows)
    except KeyError:
        fail(404, "File is not open.")
