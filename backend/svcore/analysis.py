"""
Analysis engine (phase 3): derived signals, FFT, X-Y alignment, state transitions.

Derived signals store their FORMULA (operation + source ids + parameters), not
just numbers. They are recomputed automatically when a source file is reloaded
or grows (live mode), and sessions save only the formula, never the arrays.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from svcore.decimate import minmax_decimate, stride_decimate
from svcore.ops import apply_filter, compute_fft, compute_welch, cumulative_trapezoid, moving_average, nearest_indices

UNARY = {"derivative", "integral", "abs", "negate", "normalize", "smooth", "rms", "lowpass", "highpass", "affine"}
FORMULA = {"expr"}
BINARY = {"add", "sub", "mul", "div", "absdiff"}
MULTI = {"mean", "sum", "min", "max", "norm"}
FRAME = {"frame"}
OPS = UNARY | BINARY | MULTI | FORMULA | FRAME


class OpError(ValueError):
    pass


@dataclass
class DerivedDef:
    name: str
    op: str
    sources: List[str]
    params: Dict = field(default_factory=dict)
    time: Optional[np.ndarray] = None
    data: Optional[np.ndarray] = None
    source_versions: Tuple = ()

    def formula(self, short) -> str:
        n = [short(s) for s in self.sources]
        p = self.params
        return {
            "derivative": lambda: f"derivative({n[0]})",
            "integral": lambda: f"∫ {n[0]} dt",
            "abs": lambda: f"|{n[0]}|",
            "negate": lambda: f"−{n[0]}",
            "normalize": lambda: f"norm01({n[0]})",
            "smooth": lambda: f"smooth({n[0]}, {p.get('window', 10)})",
            "rms": lambda: f"rms({n[0]}, {p.get('window', 10)})",
            "lowpass": lambda: f"lowpass({n[0]}, {p.get('cutoff')} Hz)",
            "highpass": lambda: f"highpass({n[0]}, {p.get('cutoff')} Hz)",
            "expr": lambda: str(p.get("text") or p.get("expr")),
            "affine": lambda: _affine_name(n[0], float(p.get("gain", 1) or 0), float(p.get("bias", 0) or 0)),
            "add": lambda: f"{n[0]} + {n[1]}",
            "sub": lambda: f"{n[0]} − {n[1]}",
            "mul": lambda: f"{n[0]} × {n[1]}",
            "div": lambda: f"{n[0]} ÷ {n[1]}",
            "absdiff": lambda: f"|{n[0]} − {n[1]}|",
            "mean": lambda: f"mean({', '.join(n)})",
            "sum": lambda: f"sum({', '.join(n)})",
            "min": lambda: f"min({', '.join(n)})",
            "max": lambda: f"max({', '.join(n)})",
            "norm": lambda: f"‖{', '.join(n)}‖",
            "frame": lambda: frame_name(n[:3], p),
        }[self.op]()


def _affine_name(name: str, k: float, c: float) -> str:
    g = "" if k == 1 else ("−" if k == -1 else f"{k:g}×")
    b = "" if c == 0 else (f" + {c:g}" if c > 0 else f" − {-c:g}")
    return f"{g}{name}{b}"


def _f64(a) -> np.ndarray:
    return np.asarray(a, dtype=np.float64)


def align_to(t_base: np.ndarray, t_src: np.ndarray, y_src: np.ndarray, method: str) -> np.ndarray:
    if method == "nearest":
        return _f64(y_src)[nearest_indices(t_src, t_base)]
    return np.interp(t_base, _f64(t_src), _f64(y_src), left=np.nan, right=np.nan)


def compute(op: str, signals: List[Tuple[np.ndarray, np.ndarray]], params: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """signals: [(time, data), ...] in source order. Returns (time, data)."""
    if op not in OPS:
        raise OpError(f"Unknown operation: {op}")
    if op == "expr":
        from svcore.formula import FormulaError, evaluate
        try:
            return evaluate(str(params.get("expr", "")), signals,
                            lambda t, ts, ys: align_to(t, ts, ys, params.get("alignment", "linear")))
        except FormulaError as e:
            raise OpError(str(e)) from None
    if op in UNARY:
        if len(signals) != 1:
            raise OpError("This operation needs exactly one signal.")
        t, y = _f64(signals[0][0]), _f64(signals[0][1])
        if len(t) < 2:
            raise OpError("The signal is too short.")
        if op == "derivative":
            with np.errstate(divide="ignore", invalid="ignore"):
                r = np.gradient(y, t)
            r[~np.isfinite(r)] = np.nan
        elif op == "integral":
            r = cumulative_trapezoid(t, y)
        elif op == "abs":
            r = np.abs(y)
        elif op == "negate":
            r = -y
        elif op == "normalize":
            lo, hi = np.nanmin(y), np.nanmax(y)
            r = (y - lo) / (hi - lo) if hi > lo else np.zeros_like(y)
        elif op == "affine":
            r = y * float(params.get("gain", 1)) + float(params.get("bias", 0))
        elif op == "smooth":
            r = moving_average(y, int(params.get("window", 10)))
        elif op == "rms":
            r = np.sqrt(np.maximum(moving_average(y * y, int(params.get("window", 10))), 0))
        else:
            cutoff = float(params.get("cutoff") or 0)
            if cutoff <= 0:
                raise OpError("Enter a cut-off frequency above 0 Hz.")
            r = apply_filter(t, y, op, cutoff)
        return t, _f64(r)

    if op == "frame":
        return _frame(signals, params)

    if op in BINARY:
        if len(signals) != 2:
            raise OpError("This operation needs exactly two signals.")
        (ta, ya), (tb, yb) = signals
        ta, ya = _f64(ta), _f64(ya)
        t0, t1 = max(ta[0], tb[0]), min(ta[-1], tb[-1])
        if t1 <= t0:
            raise OpError("The two signals do not overlap in time.")
        i0, i1 = np.searchsorted(ta, t0, "left"), np.searchsorted(ta, t1, "right")
        t = ta[i0:i1]
        a = ya[i0:i1]
        b = align_to(t, tb, yb, params.get("alignment", "linear"))
        with np.errstate(divide="ignore", invalid="ignore"):
            r = {"add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b,
                 "div": lambda: np.where(b != 0, a / np.where(b == 0, 1, b), np.nan),
                 "absdiff": lambda: np.abs(a - b)}[op]()
        return t, r

    if len(signals) < 2:
        raise OpError("Choose at least two signals.")
    t_base = _f64(signals[0][0])
    t0 = max(s[0][0] for s in signals)
    t1 = min(s[0][-1] for s in signals)
    if t1 <= t0:
        raise OpError("The signals do not overlap in time.")
    i0, i1 = np.searchsorted(t_base, t0, "left"), np.searchsorted(t_base, t1, "right")
    t = t_base[i0:i1]
    stack = np.vstack([align_to(t, ts, ys, params.get("alignment", "linear")) for ts, ys in signals])
    with np.errstate(invalid="ignore"):
        r = {"mean": lambda: np.nanmean(stack, axis=0), "sum": lambda: np.nansum(stack, axis=0),
             "min": lambda: np.nanmin(stack, axis=0), "max": lambda: np.nanmax(stack, axis=0),
             "norm": lambda: np.sqrt(np.nansum(stack * stack, axis=0))}[op]()
    return t, r


# -------------------------------------------------------------------------- frames
# Coordinate frames (flight logs). One derived signal = one output axis, so the three outputs of a
# conversion are three ordinary derived signals that share sources and differ only in
# params["axis"] - sessions, autosave and live recompute need nothing new.
#
# params["qty"] says WHAT is converted, because the maths differs:
#   "vector"   (default) velocity, acceleration, magnetic field... - a direction and a length, no
#              place. Converting is a rotation only: NED, ENU, body, ECEF.
#   "position" a place. LLA (lat, lon in degrees, height above the WGS84 ellipsoid in m), ECEF
#              (m from the Earth's centre) and NED / ENU (m from a reference point). Converting
#              moves the origin as well as rotating: ECEF -> NED subtracts the reference point
#              first; LLA <-> ECEF is the ellipsoid formula. Body is not a place.
# Sources: the three components in the "src" frame, then (vector only)
#   - when body is involved: the attitude (body -> NED, as PX4 / ArduPilot log it): roll, pitch,
#     yaw ("euler", aerospace order, params["unit"] "deg" (default) or "rad") or a Hamilton
#     w-first quaternion ("quat");
#   - when ECEF is involved: the vehicle's latitude and longitude (degrees), because "north" in
#     ECEF depends on where you are.
# Position to / from NED or ENU needs the reference point: params["ref"] "first" (the first sample
# with a valid position - only when the source is LLA or ECEF), "manual" with params ref_lat,
# ref_lon (degrees) and ref_alt (m above the ellipsoid), or "signals": three more sources (lat,
# lon, alt of something else - e.g. the GPS of the vehicle whose local track this is), whose first
# valid sample is the origin. "signals" is how a local XYZ track is put on the map (T17c).
VECTOR_FRAMES = ("ned", "enu", "body", "ecef")
POSITION_FRAMES = ("lla", "ecef", "ned", "enu")
AXES = {"ned": ("N", "E", "D"), "enu": ("E", "N", "U"), "body": ("X", "Y", "Z"),
        "ecef": ("X", "Y", "Z"), "lla": ("lat", "lon", "alt")}
WGS84_A = 6378137.0                    # m, semi-major axis
WGS84_F = 1 / 298.257223563
WGS84_E2 = WGS84_F * (2 - WGS84_F)     # first eccentricity squared


def frame_sources(params: Dict) -> int:
    """How many source signals a conversion needs: 3 components (+ attitude) (+ lat / lon)."""
    if params.get("qty") == "position":
        return 6 if params.get("ref") == "signals" else 3
    ends = (params.get("src"), params.get("dst"))
    return 3 + ((4 if params.get("att") == "quat" else 3) if "body" in ends else 0) + (2 if "ecef" in ends else 0)


def frame_name(n: List[str], p: Dict) -> str:
    src, dst = str(p.get("src", "")), str(p.get("dst", ""))
    lbl = AXES.get(dst, ("?", "?", "?"))[int(p.get("axis", 0)) % 3]
    pos = " pos" if p.get("qty") == "position" else ""
    return f"{lbl}{pos} {src.upper()}→{dst.upper()}({', '.join(n[:3])})"


def _unwrap(y: np.ndarray, period: float) -> np.ndarray:
    out = y.copy()
    ok = np.isfinite(y)
    out[ok] = np.unwrap(y[ok], period=period)
    return out


def _continuous_quat(q: np.ndarray) -> np.ndarray:
    """q and -q are the same attitude; flip signs so neighbours agree (else interpolating between
    two samples that straddle a flip passes through a non-rotation)."""
    flip = np.zeros(q.shape[1], dtype=bool)
    if q.shape[1] > 1:
        dots = np.einsum("ij,ij->j", q[:, 1:], q[:, :-1])
        flip[1:] = np.cumsum(np.nan_to_num(dots) < 0) % 2 == 1
    return np.where(flip, -q, q)


def _rotation(att: str, a: np.ndarray, unit: str) -> np.ndarray:
    """(3, 3, n) rotation matrices body -> NED from aligned attitude rows `a`."""
    if att == "quat":
        w, x, y, z = a / np.linalg.norm(a, axis=0)          # logs drift a little off unit length
        return np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    r, p, yw = np.radians(a) if unit != "rad" else a
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(yw), np.sin(yw)
    return np.array([                                       # Rz(yaw) . Ry(pitch) . Rx(roll)
        [cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
        [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
        [-sp, sr * cp, cr * cp]])


def _ecef_to_ned(lat_deg, lon_deg) -> np.ndarray:
    """(3, 3[, n]) rotation ECEF -> NED at latitude / longitude (degrees)."""
    la, lo = np.radians(lat_deg), np.radians(lon_deg)
    sla, cla, slo, clo = np.sin(la), np.cos(la), np.sin(lo), np.cos(lo)
    z = np.zeros_like(la)
    return np.array([[-sla * clo, -sla * slo, cla],
                     [-slo, clo, z],
                     [-cla * clo, -cla * slo, -sla]])


def lla_to_ecef(lat_deg, lon_deg, alt):
    la, lo = np.radians(lat_deg), np.radians(lon_deg)
    n = WGS84_A / np.sqrt(1 - WGS84_E2 * np.sin(la) ** 2)    # prime-vertical radius
    return np.array([(n + alt) * np.cos(la) * np.cos(lo), (n + alt) * np.cos(la) * np.sin(lo),
                     (n * (1 - WGS84_E2) + alt) * np.sin(la)])


def ecef_to_lla(x, y, z):
    """Iterative inverse (sub-millimetre after a few rounds, stable at the poles)."""
    p = np.hypot(x, y)
    lat = np.arctan2(z, p * (1 - WGS84_E2))
    for _ in range(6):
        s = np.sin(lat)
        n = WGS84_A / np.sqrt(1 - WGS84_E2 * s * s)
        lat = np.arctan2(z + WGS84_E2 * n * s, p)
    s, c = np.sin(lat), np.cos(lat)
    alt = p * c + z * s - WGS84_A * np.sqrt(1 - WGS84_E2 * s * s)
    return np.degrees(lat), np.degrees(np.arctan2(y, x)), alt


def _swap(v: np.ndarray) -> np.ndarray:
    """NED <-> ENU (the same swap both ways)."""
    return np.vstack([v[1], v[0], -v[2]])


def _overlap(signals: List[Tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    """The first signal's samples inside the time all sources share - the output time base."""
    t_base = _f64(signals[0][0])
    t0, t1 = max(s[0][0] for s in signals), min(s[0][-1] for s in signals)
    if t1 <= t0:
        raise OpError("The signals do not overlap in time.")
    return t_base[np.searchsorted(t_base, t0, "left"):np.searchsorted(t_base, t1, "right")]


def _reference(params: Dict, ecef: np.ndarray, src: str, ref_sigs=None) -> Tuple[float, float, float]:
    """(lat, lon, alt) of the NED / ENU origin."""
    if params.get("ref") == "signals":
        (tla, la), (tlo, lo), (tal, al) = [(_f64(ts), _f64(ys)) for ts, ys in ref_sigs]
        m = np.vstack([la, align_to(tla, tlo, lo, "nearest"), align_to(tla, tal, al, "nearest")])
        ok = np.flatnonzero(np.isfinite(m).all(axis=0) & (tla >= max(tlo[0], tal[0])) & (tla <= min(tlo[-1], tal[-1])))
        if not len(ok):
            raise OpError("The reference latitude, longitude and altitude have no valid sample in common.")
        lat, lon, alt = (float(v) for v in m[:, ok[0]])
        if abs(lat) > 90:
            raise OpError("The reference latitude must be between -90 and 90 degrees.")
        return lat, lon, alt
    if params.get("ref", "first") == "manual":
        try:
            ref = tuple(float(params[k]) for k in ("ref_lat", "ref_lon", "ref_alt"))
        except (KeyError, TypeError, ValueError):
            raise OpError("Enter the reference point: latitude, longitude (degrees) and altitude (m).") from None
        if not all(np.isfinite(ref)) or abs(ref[0]) > 90:
            raise OpError("The reference latitude must be between -90 and 90 degrees.")
        return ref
    if src not in ("lla", "ecef"):
        raise OpError("A local position has no place on Earth by itself - enter the reference point (Manual).")
    ok = np.flatnonzero(np.isfinite(ecef).all(axis=0))
    if not len(ok):
        raise OpError("The position has no valid sample to use as the reference point.")
    lat, lon, alt = ecef_to_lla(*ecef[:, ok[0]])
    return float(lat), float(lon), float(alt)


def _frame_position(signals, params, t, how) -> np.ndarray:
    src, dst = params.get("src"), params.get("dst")
    if "body" in (src, dst):
        raise OpError("Body axes are not a place. To convert a body offset, choose Vector.")
    if src not in POSITION_FRAMES or dst not in POSITION_FRAMES:
        raise OpError("Choose the frames to convert from and to: LLA, ECEF, NED or ENU.")
    rows = [(_f64(ts), _f64(ys)) for ts, ys in signals[:3]]
    if src == "lla":                                        # longitude across +-180 must not sweep the globe
        rows[1] = (rows[1][0], _unwrap(rows[1][1], 360.0))
    v = np.vstack([align_to(t, ts, ys, how) for ts, ys in rows])
    local = ("ned", "enu")
    if src in local and dst in local:                       # same origin: a swap, no reference needed
        return _swap(v)
    if src == "enu":
        v = _swap(v)
    if src == "lla":
        ecef = lla_to_ecef(*v)
    elif src == "ecef":
        ecef = v
    else:
        ecef = None
    if src in local or dst in local:
        ref = _reference(params, ecef, src, signals[3:6])
        ref_ecef, R = lla_to_ecef(*ref), _ecef_to_ned(ref[0], ref[1])
        if ecef is None:                                    # NED (offset from ref) -> ECEF
            ecef = ref_ecef[:, None] + R.T @ v
    if dst == "ecef":
        return ecef
    if dst == "lla":
        lat, lon, alt = ecef_to_lla(*ecef)
        return np.vstack([lat, lon, alt])
    ned = R @ (ecef - ref_ecef[:, None])                    # position: move the origin, then rotate
    return _swap(ned) if dst == "enu" else ned


def _frame_vector(signals, params, t, how) -> np.ndarray:
    src, dst, att = params.get("src"), params.get("dst"), params.get("att", "euler")
    if "lla" in (src, dst):
        raise OpError("LLA is a position, not a direction. To convert a position, choose Position.")
    if src not in VECTOR_FRAMES or dst not in VECTOR_FRAMES:
        raise OpError("Choose the frames to convert from and to: NED, ENU, body or ECEF.")
    v = np.vstack([align_to(t, ts, ys, how) for ts, ys in signals[:3]])
    rest = list(signals[3:])
    R_nb = R_ne = None
    if "body" in (src, dst):
        n_att = 4 if att == "quat" else 3
        rows, rest = [(_f64(ts), _f64(ys)) for ts, ys in rest[:n_att]], rest[n_att:]
        unit = params.get("unit", "deg")
        if att == "quat":
            same_base = len({len(ts) for ts, _ in rows}) == 1        # one message: q[0..3] together
            q = _continuous_quat(np.vstack([ys for _, ys in rows])) if same_base else [ys for _, ys in rows]
            a = np.vstack([align_to(t, rows[k][0], q[k], how) for k in range(4)])
        else:                                               # unwrap so +179 -> -179 is not a 358 deg sweep
            full = 360.0 if unit != "rad" else 2 * np.pi
            a = np.vstack([align_to(t, ts, _unwrap(ys, full), how) for ts, ys in rows])
        R_nb = _rotation(att, a, unit)
    if "ecef" in (src, dst):
        (tla, la), (tlo, lo) = [(_f64(ts), _f64(ys)) for ts, ys in rest[:2]]
        R_ne = _ecef_to_ned(align_to(t, tla, la, how), align_to(t, tlo, _unwrap(lo, 360.0), how))
    # everything goes through NED; a vector only rotates - no origin, no reference point
    if src == "enu":
        v = _swap(v)
    elif src == "body":
        v = np.einsum("ijn,jn->in", R_nb, v)
    elif src == "ecef":
        v = np.einsum("ijn,jn->in", R_ne, v)
    if dst == "enu":
        return _swap(v)
    if dst == "body":
        return np.einsum("jin,jn->in", R_nb, v)
    if dst == "ecef":
        return np.einsum("jin,jn->in", R_ne, v)
    return v


def _frame(signals: List[Tuple[np.ndarray, np.ndarray]], params: Dict) -> Tuple[np.ndarray, np.ndarray]:
    qty = params.get("qty", "vector")
    if qty not in ("vector", "position"):
        raise OpError("Choose what to convert: a vector (velocity, acceleration...) or a position.")
    src, dst = params.get("src"), params.get("dst")
    if src == dst:
        raise OpError("The two frames are the same - choose a different target frame.")
    axis = params.get("axis", 0)
    if axis not in (0, 1, 2):
        raise OpError("The output axis must be 0, 1 or 2.")
    if qty == "vector" and "body" in (src, dst) and params.get("att", "euler") not in ("euler", "quat"):
        raise OpError("Choose how the attitude is given: roll / pitch / yaw or a quaternion.")
    need = frame_sources(params)
    if qty == "vector" and not ({src, dst} <= set(VECTOR_FRAMES)):
        need = len(signals)                                 # let _frame_vector name the real problem
    if len(signals) != need:
        extra = [w for w, on in (("the attitude", "body" in (src, dst)),
                                 ("the latitude and longitude", "ecef" in (src, dst))) if on and qty == "vector"]
        raise OpError(f"This conversion needs {need} signals: the three components"
                      + (" and " + " and ".join(extra) if extra else "") + ".")
    t = _overlap(signals[:3] if qty == "position" else signals)   # a reference may be from another time
    how = params.get("alignment", "linear")
    v = (_frame_position if qty == "position" else _frame_vector)(signals, params, t, how)
    return t, v[axis]


# ----------------------------------------------------------------------------- FFT

_fft_cache: Dict[tuple, Tuple[np.ndarray, np.ndarray]] = {}


def fft_for(sig_id: str, version, t: np.ndarray, y: np.ndarray, window: str,
            t0: Optional[float], t1: Optional[float], method: str = "fft") -> Tuple[np.ndarray, np.ndarray]:
    """method: "fft" (magnitude of one FFT) or "welch" (averaged power spectral density)."""
    key = (sig_id, version, window, t0, t1, method)
    hit = _fft_cache.get(key)
    if hit is not None:
        return hit
    if t0 is not None and t1 is not None:
        i0, i1 = np.searchsorted(t, min(t0, t1), "left"), np.searchsorted(t, max(t0, t1), "right")
        t, y = t[i0:i1], y[i0:i1]
    if len(t) < 16:
        res = (np.array([]), np.array([]))
    else:
        res = (compute_welch if method == "welch" else compute_fft)(_f64(t), _f64(y), window)
    if len(_fft_cache) > 32:
        _fft_cache.pop(next(iter(_fft_cache)))
    _fft_cache[key] = res
    return res


def fft_display(freqs: np.ndarray, mags: np.ndarray, points: int) -> Tuple[np.ndarray, np.ndarray, float]:
    ok = np.isfinite(mags) if len(mags) else np.zeros(0, bool)
    peak = float(freqs[int(np.nanargmax(np.where(ok, mags, -np.inf)))]) if ok.any() else None
    fx, fy = minmax_decimate(freqs, mags, points) if len(freqs) > points else (freqs, mags)
    return fx, fy, peak


# ------------------------------------------------------------------------------ X-Y

def xy_pair(tx, x, ty, y, method: str, t0=None, t1=None, points: int = 16000, with_t: bool = False):
    """Y aligned onto X's sample times over the overlap (optionally a time window).
    with_t: also the time of each point (the timeline draws an X-Y plot / map up to a time)."""
    tx = _f64(tx)
    lo, hi = max(tx[0], ty[0]), min(tx[-1], ty[-1])
    if t0 is not None and t1 is not None:
        lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
    if hi <= lo:
        return (np.array([]), np.array([]), np.array([])) if with_t else (np.array([]), np.array([]))
    i0, i1 = np.searchsorted(tx, lo, "left"), np.searchsorted(tx, hi, "right")
    ts, xs, _ = stride_decimate(tx[i0:i1], _f64(x[i0:i1]), points)
    ys = align_to(_f64(ts), ty, y, method)
    return (_f64(xs), ys, _f64(ts)) if with_t else (_f64(xs), ys)


# --------------------------------------------------------------------------- states

def is_discrete(y: np.ndarray, max_levels: int = 12) -> bool:
    n = len(y)
    if n < 4:
        return False
    sample = _f64(y[:: max(1, n // 200_000)])
    sample = sample[np.isfinite(sample)]
    if not len(sample) or not np.all(np.mod(sample, 1) == 0):
        return False
    return len(np.unique(sample)) <= max_levels and len(np.unique(sample)) > 1


def transitions(t: np.ndarray, y: np.ndarray, x0=None, x1=None, cap: int = 4000, bins: int = 1500):
    """State changes in [x0, x1] -> (points, collapsed, end).
    points = [(time, new value)]; value None starts a stretch with too many changes to draw one
    by one (more than one change per 1/bins of the window: drawn hatched, zoom in for detail).
    `end` is the last sample time, where the last state stops."""
    i0 = 0 if x0 is None else max(0, int(np.searchsorted(t, x0, "left")) - 1)
    i1 = len(t) if x1 is None else min(len(t), int(np.searchsorted(t, x1, "right")) + 1)
    # a sparse state column (blank cells between values): the state in force at the window start
    # is the last REAL value before it
    if 0 < i0 < len(y) and not np.isfinite(y[i0]):
        lo = max(0, i0 - 1_000_000)
        back = np.flatnonzero(np.isfinite(_f64(y[lo:i0])))
        if len(back):
            i0 = lo + int(back[-1])
    yy = _f64(y[i0:i1])
    tt = _f64(t[i0:i1])
    ok = np.isfinite(yy)
    tt, yy = tt[ok], yy[ok]
    if not len(yy):
        return [], False, None
    idx = np.flatnonzero(np.diff(yy) != 0) + 1
    end = float(tt[-1])
    if len(idx) <= cap:
        return [(float(tt[0]), float(yy[0]))] + [(float(tt[i]), float(yy[i])) for i in idx], False, end
    lo, hi = float(tt[0]), float(tt[-1])
    w = (hi - lo) / bins or 1.0
    b = np.clip(((tt[idx] - lo) / w).astype(np.int64), 0, bins - 1)
    cnt = np.bincount(b, minlength=bins)
    first = np.searchsorted(b, np.arange(bins), "left")
    pts, in_busy = [(lo, float(yy[0]))], False
    for k in np.flatnonzero(cnt).tolist():
        busy = cnt[k] >= 2
        if busy and not in_busy:
            pts.append((lo + k * w, None))
            in_busy = True
        if busy:
            if not (k + 1 < bins and cnt[k + 1] >= 2):
                last = idx[first[k] + cnt[k] - 1]
                pts.append((lo + (k + 1) * w, float(yy[last])))
                in_busy = False
        else:
            i = idx[first[k]]
            pts.append((float(tt[i]), float(yy[i])))
    return pts, True, end


def ffill_state(y: np.ndarray) -> np.ndarray:
    """A state signal with blank (NaN) samples -> every sample holds the last real value."""
    y = _f64(y).copy()
    bad = ~np.isfinite(y)
    if bad.any():
        idx = np.where(~bad, np.arange(len(y)), 0)
        np.maximum.accumulate(idx, out=idx)
        y = y[idx]                    # before the first real value: stays NaN (y[0] is NaN then)
    return y


def state_mask(t: np.ndarray, st: np.ndarray, sy: np.ndarray, values) -> np.ndarray:
    """For each time in t: is the state in force (last sample of (st, sy) at or before it) one of values?"""
    if not len(st):
        return np.zeros(len(t), dtype=bool)
    sy = ffill_state(sy)
    i = np.searchsorted(st, t, side="right") - 1
    ok = i >= 0
    out = np.zeros(len(t), dtype=bool)
    out[ok] = np.isin(sy[i[ok]], np.asarray(values, dtype=np.float64))
    return out


def spectrogram(t: np.ndarray, y: np.ndarray, x0=None, x1=None, nfft: int = 1024, width: int = 800,
                height: int = 300, fmax: Optional[float] = None):
    """Spectrogram of a signal over [x0, x1]: power in dB on a (frequency x time) grid of about
    height x width cells, quantised to 0..255 between a low and a high percentile (the colour scale).
    Non-uniform sampling is resampled onto the median sample interval first."""
    from scipy.signal import spectrogram as sp_spec
    t = _f64(t)
    i0 = 0 if x0 is None else int(np.searchsorted(t, x0, "left"))
    i1 = len(t) if x1 is None else int(np.searchsorted(t, x1, "right"))
    tt, yy = t[i0:i1], _f64(y[i0:i1])
    ok = np.isfinite(yy)
    tt, yy = tt[ok], yy[ok]
    if len(tt) < 64:
        raise ValueError("Too few samples in view for a spectrogram - zoom out.")
    dt = float(np.median(np.diff(tt)))
    if not dt > 0:
        raise ValueError("The signal has no usable sample interval.")
    jitter = float(np.std(np.diff(tt))) / dt
    if jitter > 0.01:                                           # irregular: resample
        n = int((tt[-1] - tt[0]) / dt) + 1
        if n > 20_000_000:
            raise ValueError("Too many samples in view - zoom in.")
        grid = tt[0] + np.arange(n) * dt
        yy = np.interp(grid, tt, yy)
        tt = grid
    fs = 1.0 / dt
    nfft = int(min(nfft, max(64, 2 ** int(np.log2(len(yy) // 4 or 64)))))
    hop = max(1, (len(yy) - nfft) // max(1, width))
    nover = max(0, nfft - hop) if hop < nfft else 0
    f, ts, sxx = sp_spec(yy - np.mean(yy), fs=fs, window="hann", nperseg=nfft, noverlap=nover, scaling="density", mode="psd")
    if fmax:
        keep = f <= fmax
        f, sxx = f[keep], sxx[keep]
    if len(ts) > width * 1.5:                                   # many columns: keep the maximum per pixel
        k = int(np.ceil(len(ts) / width))
        m = (len(ts) // k) * k
        sxx = sxx[:, :m].reshape(len(f), -1, k).max(axis=2)
        ts = ts[:m].reshape(-1, k).mean(axis=1)
    if len(f) > height:                                         # many rows: the maximum per pixel row
        k = int(np.ceil(len(f) / height))
        m = (len(f) // k) * k
        sxx = sxx[:m].reshape(-1, k, sxx.shape[1]).max(axis=1)
        f = f[:m].reshape(-1, k).mean(axis=1)
    db = 10 * np.log10(np.maximum(sxx, 1e-30))
    lo, hi = np.percentile(db, 5), np.percentile(db, 99.7)
    if hi - lo < 1:
        hi = lo + 1
    q = np.clip((db - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    return {"f": f, "t": ts + tt[0], "img": q, "dbLo": float(lo), "dbHi": float(hi), "fs": fs, "nfft": nfft,
            "df": float(fs / nfft), "dt": float(hop * dt)}
