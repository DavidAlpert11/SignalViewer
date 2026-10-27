"""The overview strip of a run (investigation spec, step 7): its phases and automatic flags - places
worth a look, not faults. Conservative on purpose: a strip full of flags would be ignored.

  stuck       a signal that moves elsewhere holds one exact value for a long stretch (a frozen sensor);
  saturated   a signal sits flat at its own maximum or minimum (an actuator at its limit);
  gap         the recording has no samples for much longer than its usual step;
  spike       one or two samples jump far from both neighbours and come back (a glitch).
"""
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

PHASE_NAMES = re.compile(r"(^|[._ ])(mode|flight_?mode|phase|state|stage|fm)$", re.I)
MAX_FLAGS = 30


def phase_signal(names_labels: List[Tuple[str, bool]]) -> Optional[str]:
    """The signal that names the run's phases: a state named like a mode / phase, else the first
    signal with texts."""
    with_text = [n for n, has in names_labels if has]
    for n in with_text:
        if PHASE_NAMES.search(n):
            return n
    return with_text[0] if with_text else None


def phases(t, y, labels: Dict[str, str]) -> List[dict]:
    t, y = np.asarray(t, float), np.asarray(y, float)
    if len(t) == 0:
        return []
    out: List[dict] = []
    start = 0
    for i in range(1, len(y) + 1):
        if i == len(y) or y[i] != y[start]:
            v = y[start]
            if np.isfinite(v):
                key = str(int(v)) if float(v).is_integer() else str(v)
                out.append({"a": float(t[start]), "b": float(t[i] if i < len(t) else t[-1]), "label": labels.get(key, key)})
            start = i
    return out


def _runs(mask: np.ndarray) -> List[Tuple[int, int]]:
    d = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def scan(name: str, t, y, discrete: bool) -> List[dict]:
    t, y = np.asarray(t, float), np.asarray(y, float)
    ok = np.isfinite(y)
    if ok.sum() < 20:
        return []
    dur = float(t[-1] - t[0]) if len(t) > 1 else 0.0
    yy = y[ok]
    lo, hi = float(yy.min()), float(yy.max())
    if hi == lo or discrete:
        return []
    flags: List[dict] = []
    # only signals that normally move from sample to sample (a sensor, an actuator output): a held set
    # point, a stick at centre or a counter holding a value is normal, not a frozen sensor
    moving = np.diff(yy) != 0
    if moving.mean() < 0.8:
        return []
    t0, t1 = float(t[0]), float(t[-1])
    inside = lambda a, b: a > t0 + 0.05 * dur and b < t1 - 0.05 * dur        # noqa: E731 - not the run's ends (ground, idle)
    # stuck: exactly the same value for max(2 s, 5% of the run), not at its limits (that is "saturated")
    same = np.r_[False, np.diff(y) == 0] & ok
    for a, b in _runs(same):
        a0 = max(0, a - 1)
        ta, tb = float(t[a0]), float(t[min(b, len(t) - 1)])
        v = y[a0]
        if tb - ta >= max(2.0, 0.05 * dur) and lo < v < hi and inside(ta, tb):
            flags.append({"kind": "stuck", "signal": name, "a": ta, "b": tb, "value": float(v), "score": tb - ta})
    # saturated: flat at the very maximum / minimum (>= 0.3 s, >= 10 samples), rarely there (<= 10% of the run)
    for edge, kind in ((hi, "max"), (lo, "min")):
        at = ok & (y == edge)
        if at.mean() > 0.10:
            continue
        for a, b in _runs(at):
            ta, tb = float(t[a]), float(t[min(b, len(t) - 1)])
            if b - a >= 10 and tb - ta >= 0.3 and inside(ta, tb):
                flags.append({"kind": "saturated", "signal": name, "a": ta, "b": tb, "value": float(edge), "edge": kind, "score": tb - ta})
    # spike: one or two samples far from both neighbours (8x the usual sample-to-sample change), and back
    d = np.diff(yy)
    noise = float(np.median(np.abs(d - np.median(d)))) * 1.4826
    if noise > 0 and len(yy) > 4:
        idx = np.flatnonzero(ok)
        ys = yy
        prev, nxt = ys[:-2], ys[2:]
        mid = ys[1:-1]
        jump = np.minimum(np.abs(mid - prev), np.abs(mid - nxt))
        back = np.abs(nxt - prev) < 3 * noise
        hit = np.flatnonzero((jump > 8 * noise + 0.02 * (hi - lo)) & back)
        for k in hit[:5]:
            if not inside(float(t[idx[k + 1]]), float(t[idx[k + 1]])):
                continue
            i = idx[k + 1]
            flags.append({"kind": "spike", "signal": name, "a": float(t[i]), "b": float(t[i]), "value": float(y[i]),
                          "score": float(jump[k] / noise)})
    return flags


def gaps(t, name: str = "") -> List[dict]:
    t = np.asarray(t, float)
    if len(t) < 3:
        return []
    d = np.diff(t)
    pos = d[d > 0]
    if not len(pos):
        return []
    step = float(np.median(pos))
    out = []
    for i in np.flatnonzero(d > max(20 * step, 0.5)):
        out.append({"kind": "gap", "signal": name, "a": float(t[i]), "b": float(t[i + 1]), "score": float(d[i] / step)})
    return out


def rank(flags: List[dict]) -> List[dict]:
    """The strongest few, one per kind and signal within a second of each other."""
    flags = sorted(flags, key=lambda f: -f.get("score", 0))
    kept: List[dict] = []
    for f in flags:
        if any(k["kind"] == f["kind"] and k["signal"] == f["signal"] and abs(k["a"] - f["a"]) < 1.0 for k in kept):
            continue
        kept.append(f)
        if len(kept) >= MAX_FLAGS:
            break
    return sorted(kept, key=lambda f: f["a"])
