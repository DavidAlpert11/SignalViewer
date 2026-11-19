"""RE2: the numbers behind the report's automatic parts - pure functions over arrays (no Store), so they are tested
alone and the app, the command line and a script give the same answers. app/reportparts.py turns them into the
document's text, tables and plots.

    pairs        the commanded / measured pairs of a file's names (the twin of frontend/src/desired.ts - a shared
                 table of cases, backend/tests/setpoint_cases.json, is checked by both)
    tracking     one pair: the tracking error on every sample, its delay, the steps of the command and how each
                 was followed (overshoot, rise, settling), time outside a tolerance
    difference   one signal in two files: how different overall, where the difference is concentrated (its
                 central region), when it first diverged
    region       the central region of several signals' differences together
    timeline     the stretches of a state signal (the lanes' rule, svcore/overview.phases)

Every number is computed on all the samples; nothing here thins a signal.
"""
import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore.compare import angle_period, _wrap
from svcore.firstchange import lag
from svcore.ops import compute_signal_stats

Series = Tuple[np.ndarray, np.ndarray]

# ------------------------------------------------------------------------------------------------ pairs
# The words that make a name a setpoint - a prefix or a suffix, after a separator or in camel case (desired.ts,
# the owner's list 2026-11-16). Longest first, so "Commanded" is not read as "Command" + "ed".
WORDS = ["commanded", "reference", "setpoint", "command", "desired", "demand", "target", "des", "dem", "cmd", "tgt", "ref", "set", "sp"]
_ALT = "|".join(WORDS)
_CAMEL = "|".join(sorted([w[0].upper() + w[1:] for w in WORDS] + ["SetPoint", "SP"], key=len, reverse=True))
SEP_SUFFIX = re.compile(r"^(.+?)[_\-. ](?:%s)$" % _ALT, re.I)
SEP_PREFIX = re.compile(r"^(?:%s)[_\-. ](.+)$" % _ALT, re.I)
CAMEL_PREFIX = re.compile(r"^(?:%s|%s)([A-Z].*)$" % (_CAMEL, _ALT))
CAMEL_SUFFIX = re.compile(r"^(.+)(?:%s)$" % _CAMEL)
LOWER_SUFFIX = re.compile(r"^([a-z][a-z0-9]*?)dem$")
TOPIC = re.compile(r"^(.+)_(?:%s)(\[\d+\])?\.$" % _ALT, re.I)


def bare(name: str) -> str:
    """A name without its unit: "ATT.DesRoll [deg]" -> "ATT.DesRoll"."""
    return re.sub(r" \[[^\]]*\]$", "", name)


def actual_names(name: str) -> List[str]:
    """The measured value's names a setpoint name pairs with (several candidates), or [] if it is none."""
    dot = name.rfind(".")
    msg, leaf = (name[:dot + 1], name[dot + 1:]) if dot >= 0 else ("", name)
    out: List[str] = []
    for rx in (SEP_SUFFIX, SEP_PREFIX, CAMEL_PREFIX, CAMEL_SUFFIX, LOWER_SUFFIX):
        m = rx.match(leaf)
        if not m or not m.group(1):
            continue
        out.append(msg + m.group(1))
        if rx is CAMEL_PREFIX:
            out.append(msg + m.group(1)[0].lower() + m.group(1)[1:])       # desiredRoll -> roll
    m = TOPIC.match(msg)
    if m:
        out.append("%s%s.%s" % (m.group(1), m.group(2) or "", leaf))
    return [n for n in out if n != name]


def setpoint_pairs(ids: Sequence[str]) -> List[Dict[str, str]]:
    """The setpoint / measured pairs among signal ids ("<runId>/<name>"), each within one file, in the order of the
    setpoints - as desired.ts setpointPairs."""
    def file(i: str) -> str:
        return i[:i.find("/")]
    by_key: Dict[str, str] = {}
    for i in ids:
        by_key.setdefault(file(i) + "/" + bare(i[i.find("/") + 1:]), i)
    out = []
    for i in ids:
        for n in actual_names(bare(i[i.find("/") + 1:])):
            m = by_key.get(file(i) + "/" + n)
            if m and m != i:
                out.append({"setpoint": i, "measured": m})
                break
    return out


# ------------------------------------------------------------------------------------------------ helpers

def _f(a) -> np.ndarray:
    return np.asarray(a, dtype=np.float64)


def span(y: np.ndarray) -> float:
    """How much a signal moves: the 1st-to-99th percentile span (one spike does not set it); a flat signal: its
    size, else 1."""
    y = y[np.isfinite(y)]
    if not len(y):
        return 1.0
    s = float(np.percentile(y, 99) - np.percentile(y, 1))
    if s <= 0:
        s = float(np.max(y) - np.min(y))
    if s <= 0:
        s = float(np.max(np.abs(y)))
    return s if s > 0 else 1.0


def held(t: np.ndarray, y: np.ndarray, at: np.ndarray) -> np.ndarray:
    """A state at the times `at`: the value in force (the last sample at or before)."""
    i = np.searchsorted(t, at, "right") - 1
    out = y[np.clip(i, 0, len(y) - 1)].astype(np.float64)
    out[i < 0] = np.nan
    return out


def on_grid(t: np.ndarray, y: np.ndarray, at: np.ndarray, state: bool) -> np.ndarray:
    if state:
        return held(t, y, at)
    ok = np.isfinite(y)
    return np.interp(at, t[ok], y[ok]) if ok.sum() >= 2 else np.full(len(at), np.nan)


def _stretches(mask: np.ndarray) -> List[Tuple[int, int]]:
    d = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def _num(v) -> Optional[float]:
    return None if v is None or not math.isfinite(float(v)) else float(v)


# ------------------------------------------------------------------------------------------------ tracking

def steps(t: np.ndarray, sp: np.ndarray, y: np.ndarray, size: float, min_hold: float = 1.0) -> List[Dict]:
    """The steps of a command (a jump of more than 10 % of its span between two samples, then held at least
    `min_hold` s) and how the measured value followed each: overshoot (% of the step), rise 10-90 % (s), settling
    into 5 % of the step (s; None: not settled before the next step)."""
    out: List[Dict] = []
    if len(t) < 4:
        return out
    jump = np.flatnonzero(np.abs(np.diff(sp)) > 0.1 * size) + 1
    if len(jump) > 200:                                  # a noisy command, not steps
        return out
    ends = list(jump[1:]) + [len(t)]
    for i, j in zip(jump, ends):
        before, after = float(sp[i - 1]), float(sp[i])
        d = after - before
        if not math.isfinite(d) or abs(d) <= 0:
            continue
        # held: the step lasts while the command stays at its new value (a ramp or a controller's output is no step)
        moved = np.flatnonzero(np.abs(sp[i:j] - after) > 0.05 * abs(d))
        if len(moved):
            j = i + int(moved[0])
        if j - i < 3 or t[j - 1] - t[i] < min_hold:
            continue
        tw, yw = t[i:j], y[i:j]
        ok = np.isfinite(yw)
        if ok.sum() < 3:
            continue
        tw, yw = tw[ok], yw[ok]
        rel = (yw - before) / d                         # 0 at the old value, 1 at the new one
        over = max(0.0, float(np.max(rel) - 1.0)) * 100.0
        r10, r90 = np.flatnonzero(rel >= 0.1), np.flatnonzero(rel >= 0.9)
        rise = float(tw[r90[0]] - tw[r10[0]]) if len(r10) and len(r90) else None
        # settling on a 5-sample running mean: one noisy sample is not "out of the band again"
        sm = np.convolve(rel, np.ones(5) / 5, "valid") if len(rel) >= 9 else rel
        off = (len(rel) - len(sm)) // 2
        out_band = np.flatnonzero(np.abs(sm - 1.0) > 0.05)
        if not len(out_band):
            settle: Optional[float] = 0.0
        elif out_band[-1] >= len(sm) - 1:
            settle = None
        else:
            settle = float(tw[min(len(tw) - 1, out_band[-1] + 1 + off)] - t[i])
        out.append({"t": float(t[i]), "from": before, "to": after, "overshoot": over, "rise": rise, "settling": settle})
    return out


def tracking(sp: Series, ms: Series, name: str = "", tol: Optional[float] = None, sp_state: bool = False) -> Dict:
    """How a measured value followed its command, on the measured value's own samples (the command taken in force
    at each - a held state - or between its samples). error = measured - command (angles wrapped)."""
    ts, ys = _f(sp[0]), _f(sp[1])
    tm, ym = _f(ms[0]), _f(ms[1])
    if len(ts) < 2 or len(tm) < 2:
        return {"error": "too few samples"}
    lo, hi = max(ts[0], tm[0]), min(ts[-1], tm[-1])
    if hi <= lo:
        return {"error": "the two do not overlap in time"}
    k = (tm >= lo) & (tm <= hi)
    t, y = tm[k], ym[k]
    c = on_grid(ts, ys, t, sp_state)
    period = angle_period(name, [ys, ym])
    e = _wrap(y - c, period) if period else y - c
    st = compute_signal_stats(t, e) or {}
    size = span(c)
    if size == 1.0 and span(y) != 1.0 and float(np.nanmax(c) - np.nanmin(c)) <= 0:
        size = span(y)
    res: Dict = {"t0": float(lo), "t1": float(hi), "samples": int(len(t)), "rms": _num(st.get("rms")), "bias": _num(st.get("mean")),
                 "max": _num(st.get("abs_max")), "tmax": _num(st.get("t_abs_max")), "p95": _num(st.get("p95_abs")),
                 "span": size, "period": period}
    res["score"] = (res["rms"] or 0.0) / size
    # the delay: how much later the measured value follows its command (cross-correlation), when it is clear
    L = lag(ts, ys, tm, ym, float(lo), float(hi), max_lag=min(5.0, (hi - lo) / 10))
    lg = L.get("lag")
    res["delay"] = float(lg) if isinstance(lg, (int, float)) and L.get("status") == "ok" and not L.get("weak") and not L.get("ambiguous") else None
    ss = steps(t, c, y, size)
    res["steps"] = len(ss)
    if ss:
        res["overshoot"] = max(s["overshoot"] for s in ss)
        res["tOvershoot"] = max(ss, key=lambda s: s["overshoot"])["t"]
        rises = [s["rise"] for s in ss if s["rise"] is not None]
        res["rise"] = float(np.median(rises)) if rises else None
        sett = [s["settling"] for s in ss]
        res["settling"] = None if any(s is None for s in sett) else max(sett)     # None: a step never settled
        res["unsettled"] = sum(1 for s in sett if s is None)
    if tol is not None and tol > 0:
        out = np.abs(e) > tol
        dt = np.diff(t, append=t[-1])
        total = float(t[-1] - t[0]) or 1.0
        res["tol"] = tol
        res["outside"] = float(dt[out].sum()) / total * 100.0
        runs = _stretches(out)
        res["longest"] = max((float(t[min(b, len(t) - 1)] - t[a]) for a, b in runs), default=0.0)
    res["e"] = (t, e)
    return res


# ------------------------------------------------------------------------------------------------ difference

BINS = 100


def difference(base: Series, other: Series, name: str = "", state: bool = False, lo: Optional[float] = None,
               hi: Optional[float] = None) -> Optional[Dict]:
    """One signal in two files, on the base file's samples inside their common time: d = other - base.

    overall  RMS(d) / S, S = how much the base signal moves (`span`) - 0.01 is invisible on a plot, 0.2 clear;
    peak     the largest RMS(d) / S in 1 % slices of the time - a signal the same everywhere but in one place has a
             small overall and a large peak: the owner's "mostly similar, a central region differs";
    region   the slices around the peak above a quarter of it, [a, b] s;
    first    the first time |d| / S leaves its own usual level and stays out (k x its median, at least 2 %);
    shape    1 - correlation (a delay or a sign error that a small difference can hide)."""
    tb, yb = _f(base[0]), _f(base[1])
    to, yo = _f(other[0]), _f(other[1])
    if len(tb) < 3 or len(to) < 3:
        return None
    a, b = max(tb[0], to[0]), min(tb[-1], to[-1])
    if lo is not None:
        a = max(a, lo)
    if hi is not None:
        b = min(b, hi)
    if b <= a:
        return None
    k = (tb >= a) & (tb <= b)
    t, y0 = tb[k], yb[k]
    if len(t) < 3:
        return None
    y1 = on_grid(to, yo, t, state)
    period = angle_period(name, [yb, yo])
    d = _wrap(y1 - y0, period) if period else y1 - y0
    ok = np.isfinite(d)
    if ok.sum() < 3:
        return None
    t, y0, y1, d = t[ok], y0[ok], y1[ok], d[ok]
    S = span(y0)
    if float(np.nanmax(y0) - np.nanmin(y0)) <= 0 and float(np.max(np.abs(d))) > 0:
        S = max(abs(float(y0[0])), float(np.max(np.abs(d))))     # a constant that changed: its change is the size
    n = d / S
    overall = float(np.sqrt(np.mean(n ** 2)))
    edges = np.linspace(t[0], t[-1], BINS + 1)
    idx = np.clip(np.searchsorted(edges, t, "right") - 1, 0, BINS - 1)
    cnt = np.bincount(idx, minlength=BINS)
    sq = np.bincount(idx, weights=n ** 2, minlength=BINS)
    with np.errstate(invalid="ignore", divide="ignore"):
        prof = np.where(cnt > 0, np.sqrt(sq / np.maximum(cnt, 1)), np.nan)
    peak_i = int(np.nanargmax(prof)) if np.isfinite(prof).any() else 0
    peak = float(prof[peak_i]) if np.isfinite(prof[peak_i]) else 0.0
    lo_i = hi_i = peak_i
    while lo_i > 0 and np.isfinite(prof[lo_i - 1]) and prof[lo_i - 1] >= 0.25 * peak:
        lo_i -= 1
    while hi_i < BINS - 1 and np.isfinite(prof[hi_i + 1]) and prof[hi_i + 1] >= 0.25 * peak:
        hi_i += 1
    an = np.abs(n)
    usual = float(np.median(an))
    thr = max(0.02, 5 * usual)
    persist = max(3, len(an) // 500)
    first = None
    if peak >= 0.02:
        above = an > thr
        for s0, s1 in _stretches(above):
            if s1 - s0 >= persist:
                first = float(t[s0])
                break
    shape = None
    if not state and np.std(y0) > 0 and np.std(y1) > 0:
        shape = float(1.0 - np.corrcoef(y0, y1)[0, 1])
    res = {"overall": overall, "peak": peak, "region": [float(edges[lo_i]), float(edges[hi_i + 1])], "first": first,
           "shape": shape, "maxAbs": float(np.max(np.abs(d))), "tMaxAbs": float(t[int(np.argmax(np.abs(d)))]),
           "span": S, "t0": float(t[0]), "t1": float(t[-1]), "profile": [None if not np.isfinite(v) else float(v) for v in prof]}
    if state:
        res["sequences"] = [_sequence(y0), _sequence(y1)]
    return res


def _sequence(y: np.ndarray) -> List[float]:
    y = y[np.isfinite(y)]
    if not len(y):
        return []
    keep = np.r_[True, y[1:] != y[:-1]]
    return [float(v) for v in y[keep]]


def level(d: Dict, small: float = 0.02, large: float = 0.10) -> str:
    """same / small / large by the peak (a difference in one region counts as much as one everywhere)."""
    p = max(d.get("peak") or 0.0, d.get("overall") or 0.0)
    return "same" if p < small else "small" if p < large else "large"


def region(diffs: Sequence[Dict], width_share: float = 0.1) -> Optional[Dict]:
    """The central region of several signals' differences together: on a common time axis, each signal's |d| / S
    profile summed; the window (default 10 % of the time) with the largest sum, widened while neighbours stay above
    half of it. Also the first divergence among them."""
    ds = [d for d in diffs if d and d.get("profile")]
    if not ds:
        return None
    t0, t1 = min(d["t0"] for d in ds), max(d["t1"] for d in ds)
    if t1 <= t0:
        return None
    axis = np.linspace(t0, t1, BINS + 1)
    mid = (axis[:-1] + axis[1:]) / 2
    total = np.zeros(BINS)
    for d in ds:
        e = np.linspace(d["t0"], d["t1"], BINS + 1)
        m = (e[:-1] + e[1:]) / 2
        p = np.array([0.0 if v is None else v for v in d["profile"]])
        total += np.interp(mid, m, p, left=0.0, right=0.0) / max(d["peak"], 1e-12)   # each signal counts once
    w = max(1, int(round(BINS * width_share)))
    sums = np.convolve(total, np.ones(w), "valid")
    i = int(np.argmax(sums))
    a, b = i, i + w - 1
    lvl = sums[i] / w
    while a > 0 and total[a - 1] >= 0.5 * lvl:
        a -= 1
    while b < BINS - 1 and total[b + 1] >= 0.5 * lvl:
        b += 1
    firsts = [(d["first"], d) for d in ds if d.get("first") is not None]
    first = min(firsts, key=lambda x: x[0]) if firsts else None
    return {"a": float(axis[a]), "b": float(axis[b + 1]), "first": first[0] if first else None,
            "firstName": first[1].get("name") if first else None}


# ------------------------------------------------------------------------------------------------ timeline

def timeline(t, y, labels: Optional[Dict[int, str]], end: Optional[float] = None) -> List[Dict]:
    """The stretches of a state, as its lane draws them (svcore/overview.phases): value, label, a, b."""
    from svcore.overview import phases
    lab = {str(k): v for k, v in (labels or {}).items()}
    return phases(_f(t), _f(y), lab, end)


def distance_m(lat0: float, lon0: float, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Great-circle distance (m) from one point."""
    R = 6371008.8
    p0, p = math.radians(lat0), np.radians(lat)
    dp, dl = p - p0, np.radians(lon - lon0)
    h = np.sin(dp / 2) ** 2 + math.cos(p0) * np.cos(p) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def path_facts(t, lat, lon, alt=None) -> Dict:
    """A track's facts on every sample: duration, distance travelled, the farthest point from the start and the
    highest, the fastest ground speed (from the positions)."""
    t, lat, lon = _f(t), _f(lat), _f(lon)
    ok = np.isfinite(lat) & np.isfinite(lon) & ~((np.abs(lat) < 1e-9) & (np.abs(lon) < 1e-9))   # 0, 0: no fix yet
    t, lat, lon = t[ok], lat[ok], lon[ok]
    if len(t) < 2:
        return {}
    R = 6371008.8
    p = np.radians(lat)
    dp, dl = np.diff(p), np.radians(np.diff(lon))
    h = np.sin(dp / 2) ** 2 + np.cos(p[:-1]) * np.cos(p[1:]) * np.sin(dl / 2) ** 2
    seg = 2 * R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
    home = distance_m(float(lat[0]), float(lon[0]), lat, lon)
    out: Dict = {"t0": float(t[0]), "t1": float(t[-1]), "travelled": float(seg.sum()),
                 "farthest": float(home.max()), "tFarthest": float(t[int(np.argmax(home))])}
    dt = np.diff(t)
    good = dt > 0
    if good.any():
        v = seg[good] / dt[good]
        # one bad fix makes a huge speed: the 99.9th percentile is the honest "fastest"
        out["speed"] = float(np.percentile(v, 99.9)) if len(v) > 1000 else float(v.max())
    if alt is not None:
        a = _f(alt)[ok]
        if np.isfinite(a).any():
            i = int(np.nanargmax(a))
            out["highest"], out["tHighest"] = float(a[i]), float(t[i])
            out["lowest"] = float(np.nanmin(a))
    return out


def at(t, y, when: float) -> Optional[float]:
    t, y = _f(t), _f(y)
    if not len(t) or when < t[0] or when > t[-1]:
        return None
    v = float(np.interp(when, t, y))
    return v if math.isfinite(v) else None

