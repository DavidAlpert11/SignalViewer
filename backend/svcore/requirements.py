"""CC11: requirements beyond a range - what a simulation or a test is judged by. Each kind takes the signal's samples
(t, y) inside the check's window and returns one verdict:

    {"pass": bool, "value": float | None, "limit": float, "at": float | None, "message": str}

`value` is the measured quantity (seconds, %, units), `limit` what it may be, `at` the time worth looking at.

Kinds (a checks file's entry, beside "signal"; target = a number, or "ref": another signal whose final value in the
window is the target):
    settle    {"band": 2, "band_pct": 2, "by": 3.0}    within the band around the target from `by` s (after the window's
                                                     start) on; value = the settling time
    overshoot {"max_pct": 10}                        beyond the target, as % of the step (target - first value)
    rise      {"within": 0.5}                        10 % -> 90 % of the step within `within` s
    sserror   {"max": 0.1, "last": 1.0}               |mean of the last `last` s - target| at most `max`
    rate      {"max": 50}                            |dy/dt| at most `max` (units per second)
    track     {"ref": "Cmd", "abs": 0.5, "pct": 2}    |y - ref| within max(abs, pct % of |ref|) at every sample
    order     {"first": {"signal": "A", "above": 1}, "then": {"signal": "B", "below": 0}}   A's moment before B's

Numbers are computed on every sample (CLAUDE.md: nothing left out). Messages are for an engineer in the field:
what was measured, against what, when."""
from typing import Any, Dict, Optional

import numpy as np

KINDS = ("range", "settle", "overshoot", "rise", "sserror", "rate", "track", "order")


class RequirementError(ValueError):
    """The requirement cannot be judged on these samples (too few, a flat step) - said, not guessed."""


def _f(x: float) -> str:
    return f"{x:.4g}"


def _clean(t: np.ndarray, y: np.ndarray):
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(t) & np.isfinite(y)
    t, y = t[ok], y[ok]
    if len(t) < 2:
        raise RequirementError("fewer than two samples in the window")
    return t, y


def _step(y: np.ndarray, target: float):
    y0 = float(y[0])
    step = target - y0
    if step == 0 or not np.isfinite(step):
        raise RequirementError(f"no step: the signal starts at its target ({_f(target)})")
    return y0, step


def _verdict(ok: bool, value: Optional[float], limit: float, at: Optional[float], message: str) -> Dict[str, Any]:
    return {"pass": bool(ok), "value": None if value is None else float(value), "limit": float(limit),
            "at": None if at is None else float(at), "message": message}


def settle(t, y, target: float, band: float, by: float) -> Dict[str, Any]:
    t, y = _clean(t, y)
    out = np.abs(y - target) > band
    if not out.any():
        ts = 0.0
    else:
        last = int(np.flatnonzero(out)[-1])
        if last == len(t) - 1:
            return _verdict(False, None, by, float(t[-1]),
                            f"never settles within ±{_f(band)} of {_f(target)} (still outside at the end, {_f(t[-1])} s)")
        ts = float(t[last + 1] - t[0])
    ok = ts <= by
    return _verdict(ok, ts, by, float(t[0] + ts), f"settles within ±{_f(band)} of {_f(target)} after {_f(ts)} s "
                    f"({'at most' if ok else 'more than'} {_f(by)} s)")


def overshoot(t, y, target: float, max_pct: float) -> Dict[str, Any]:
    t, y = _clean(t, y)
    y0, step = _step(y, target)
    beyond = (y - target) * np.sign(step)
    k = int(np.argmax(beyond))
    pct = max(0.0, float(beyond[k]) / abs(step) * 100)
    ok = pct <= max_pct
    return _verdict(ok, pct, max_pct, float(t[k]) if pct > 0 else None,
                    f"overshoot {_f(pct)} % of the step {_f(y0)} → {_f(target)}" + (f" at {_f(t[k])} s" if pct > 0 else "")
                    + f" ({'at most' if ok else 'more than'} {_f(max_pct)} %)")


def rise(t, y, target: float, within: float) -> Dict[str, Any]:
    t, y = _clean(t, y)
    y0, step = _step(y, target)
    frac = (y - y0) / step
    lo, hi = np.flatnonzero(frac >= 0.1), np.flatnonzero(frac >= 0.9)
    if not len(hi):
        return _verdict(False, None, within, None, f"never reaches 90 % of the step {_f(y0)} → {_f(target)}")
    tr = float(t[hi[0]] - t[lo[0]])
    ok = tr <= within
    return _verdict(ok, tr, within, float(t[hi[0]]), f"rise time (10 → 90 %) {_f(tr)} s "
                    f"({'at most' if ok else 'more than'} {_f(within)} s)")


def sserror(t, y, target: float, max_err: float, last: float) -> Dict[str, Any]:
    t, y = _clean(t, y)
    tail = y[t >= t[-1] - last]
    err = abs(float(np.mean(tail)) - target)
    ok = err <= max_err
    return _verdict(ok, err, max_err, float(t[-1]), f"steady-state error {_f(err)} over the last {_f(last)} s "
                    f"({'at most' if ok else 'more than'} {_f(max_err)})")


def rate(t, y, max_rate: float) -> Dict[str, Any]:
    t, y = _clean(t, y)
    dt = np.diff(t)
    good = dt > 0
    if not good.any():
        raise RequirementError("the time does not advance")
    r = np.abs(np.diff(y)[good] / dt[good])
    k = int(np.argmax(r))
    worst = float(r[k])
    ok = worst <= max_rate
    at = float(t[1:][good][k])
    return _verdict(ok, worst, max_rate, at, f"fastest change {_f(worst)} per s at {_f(at)} s "
                    f"({'at most' if ok else 'more than'} {_f(max_rate)} per s)")


def track(t, y, tr, yr, abs_tol: float = 0.0, pct: float = 0.0) -> Dict[str, Any]:
    t, y = _clean(t, y)
    tr, yr = _clean(tr, yr)
    inside = (t >= tr[0]) & (t <= tr[-1])               # compared only where both exist
    if inside.sum() < 2:
        raise RequirementError("the signal and its reference do not overlap in time")
    t, y = t[inside], y[inside]
    ref = np.interp(t, tr, yr)
    tol = np.maximum(abs_tol, np.abs(ref) * pct / 100)
    err = np.abs(y - ref)
    bad = err > tol
    k = int(np.argmax(err - tol))
    limit = float(abs_tol) if not pct else float(tol[k])
    if not bad.any():
        return _verdict(True, float(err.max()), limit, None, f"follows its reference within the tolerance (largest error {_f(err.max())})")
    first = float(t[np.flatnonzero(bad)[0]])
    out_s = float(np.sum(np.diff(t, append=t[-1])[bad]))
    return _verdict(False, float(err[k]), limit, float(t[k]), f"off its reference by up to {_f(err[k])} at {_f(t[k])} s "
                    f"(tolerance {_f(tol[k])}); outside for {_f(out_s)} s from {_f(first)} s")


def moment(t, y, cond: Dict[str, Any]) -> Optional[float]:
    """The first time a condition holds: {"above": x} / {"below": x} / {"equals": x}."""
    t, y = _clean(t, y)
    if "above" in cond:
        hit = y > float(cond["above"])
    elif "below" in cond:
        hit = y < float(cond["below"])
    elif "equals" in cond:
        hit = np.isclose(y, float(cond["equals"]))
    else:
        raise RequirementError('a moment needs "above", "below" or "equals"')
    idx = np.flatnonzero(hit)
    return float(t[idx[0]]) if len(idx) else None


def order(ta: Optional[float], tb: Optional[float], a: str, b: str) -> Dict[str, Any]:
    if ta is None:
        return _verdict(False, None, 0, tb, f"{a} never happens")
    if tb is None:
        return _verdict(True, None, 0, ta, f"{a} at {_f(ta)} s; {b} never happens")
    ok = ta < tb
    return _verdict(ok, tb - ta, 0, ta if ok else tb, f"{a} at {_f(ta)} s, {b} at {_f(tb)} s"
                    + ("" if ok else f" - {b} came first"))


def validate(c: Dict[str, Any]) -> Optional[str]:
    """What is missing in a requirement, said for the checks file - or None."""
    kind = c.get("kind", "range")
    if kind not in KINDS:
        return f'unknown "kind" {kind!r} (one of: {", ".join(KINDS)})'
    need = {"settle": ("by",), "overshoot": ("max_pct",), "rise": ("within",), "sserror": ("max",), "rate": ("max",),
            "track": ("ref",), "order": ("first", "then")}.get(kind, ())
    miss = [k for k in need if c.get(k) is None]
    if miss:
        return f'"{kind}" needs ' + ", ".join(f'"{m}"' for m in miss)
    if kind in ("settle", "overshoot", "rise", "sserror") and c.get("target") is None and c.get("ref") is None:
        return f'"{kind}" needs a "target" (a number) or a "ref" (a signal whose final value is the target)'
    if kind == "settle" and c.get("band") is None and c.get("band_pct") is None:
        return '"settle" needs "band" (units) or "band_pct" (% of the step)'
    if kind == "track" and not c.get("abs") and not c.get("pct"):
        return '"track" needs "abs" or "pct" (the tolerance)'
    if kind == "order":
        for k in ("first", "then"):
            m = c.get(k)
            if not isinstance(m, dict) or not m.get("signal") or not any(x in m for x in ("above", "below", "equals")):
                return f'"order": "{k}" needs "signal" and one of "above", "below", "equals"'
    if kind == "range" and c.get("lo") is None and c.get("hi") is None:
        return 'neither "lo" nor "hi"'
    return None


def judge(c: Dict[str, Any], t, y, target: Optional[float] = None, ref=None) -> Dict[str, Any]:
    """One requirement on one window's samples. target: already resolved (a number, or the ref's final value);
    ref: (t, y) of the reference signal for "track"."""
    kind = c.get("kind", "range")
    if kind == "settle":
        assert target is not None
        band = c.get("band")
        if band is None:
            y0 = float(np.asarray(y, dtype=np.float64)[0])
            band = abs(target - y0) * float(c["band_pct"]) / 100
        return settle(t, y, target, float(band), float(c["by"]))
    if kind == "overshoot":
        assert target is not None
        return overshoot(t, y, target, float(c["max_pct"]))
    if kind == "rise":
        assert target is not None
        return rise(t, y, target, float(c["within"]))
    if kind == "sserror":
        assert target is not None
        return sserror(t, y, target, float(c["max"]), float(c.get("last", 1.0)))
    if kind == "rate":
        return rate(t, y, float(c["max"]))
    if kind == "track":
        assert ref is not None
        return track(t, y, ref[0], ref[1], float(c.get("abs") or 0), float(c.get("pct") or 0))
    raise RequirementError(f"{kind} is judged elsewhere")
