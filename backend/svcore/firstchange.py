"""What changed first around a moment (investigation spec, step 4), and the lag between two signals.

first_change: a signal's usual level and noise are measured in a window well before the event (the
baseline); its first change is the first sample, from the end of the baseline to the end of the
event, that is
more than k times that noise from the usual level and stays there for `persist` samples. A signal
that is flat in the baseline counts any change; a state (few distinct values) counts a new value.
The result is a list of CANDIDATES in time order - earlier is not proof of cause.

lag: the normalised cross-correlation of two signals in a window, on one time grid: the shift of B
that matches A best, its strength, and whether another shift matches almost as well (a periodic
signal - the lag is then not one number).
"""
from typing import Dict, List, Optional, Tuple

import numpy as np


def _f(a) -> np.ndarray:
    return np.asarray(a, dtype=np.float64)


def _spark(t: np.ndarray, y: np.ndarray, lo: float, hi: float, n: int = 40) -> List[Optional[float]]:
    """A small picture of the signal from the baseline to the end of the event (for the list)."""
    if len(t) < 2 or hi <= lo:
        return []
    g = np.linspace(lo, hi, n)
    v = np.interp(g, t, y, left=np.nan, right=np.nan)
    return [None if not np.isfinite(x) else float(x) for x in v]


def default_baseline(a: float, b: float) -> Tuple[float, float]:
    """The usual level is read well before the event: what leads to it has often started before the
    span the user marked (the anomaly). The search starts max(L, 1 s) before it; the baseline is the
    max(L, 2 s) before that."""
    L = max(b - a, 1e-6)
    lead, length = max(L, 1.0), max(L, 2.0)
    return (a - lead - length, a - lead)


def first_change(t, y, a: float, b: float, base: Tuple[float, float], k: float = 4.0, persist: int = 3,
                 discrete: bool = False) -> Dict[str, object]:
    t, y = _f(t), _f(y)
    out: Dict[str, object] = {"status": "nodata"}
    if len(t) < 2:
        return out
    dts = np.diff(t)
    dts = dts[dts > 0]
    rate = float(1.0 / np.median(dts)) if len(dts) else 0.0
    out["rate"] = rate
    out["spark"] = _spark(t, y, base[0], b)
    bm = (t >= base[0]) & (t < base[1]) & np.isfinite(y)
    sm = (t >= min(base[1], a)) & (t <= b) & np.isfinite(y)   # from the end of the baseline: causes come first
    if bm.sum() < 2 or sm.sum() < 1:
        return out
    yb, ys, ts = y[bm], y[sm], t[sm]
    if discrete:
        vals, cnt = np.unique(yb, return_counts=True)
        usual = vals[np.argmax(cnt)]
        dev = (ys != usual).astype(float) * (k + 1)
        noise, level = 1.0, float(usual)
    else:
        level = float(np.median(yb))
        noise = float(np.median(np.abs(yb - level)) * 1.4826) or float(np.std(yb))
        if noise <= 0:
            span = float(np.nanmax(np.abs(ys - level))) if len(ys) else 0.0
            noise = max(span * 1e-3, 1e-12)
        dev = (ys - level) / noise
    over = np.abs(dev) > k
    out["status"] = "same"
    out["strength"] = float(np.nanmax(np.abs(dev))) if len(dev) else 0.0
    if not over.any():
        return out
    # the first run of `persist` samples in a row beyond k (one sample when the window is that short)
    need = max(1, min(persist, len(over)))
    run = np.convolve(over.astype(int), np.ones(need, dtype=int), "valid")
    hits = np.flatnonzero(run >= need)
    if not len(hits):
        return out
    i = int(hits[0])
    out.update(status="changed", t=float(ts[i]), rel=float(ts[i] - a), up=bool(dev[i] > 0),
               level=level, noise=noise)
    return out


def lag(ta, ya, tb, yb, t0: float, t1: float, max_lag: Optional[float] = None) -> Dict[str, object]:
    """B against A in [t0, t1]: lag > 0 = B follows A by that many seconds."""
    ta, ya, tb, yb = _f(ta), _f(ya), _f(tb), _f(yb)
    lo, hi = max(t0, ta[0] if len(ta) else t0, tb[0] if len(tb) else t0), min(t1, ta[-1] if len(ta) else t1, tb[-1] if len(tb) else t1)
    if hi <= lo:
        return {"status": "nooverlap"}

    def step(t):
        m = (t >= lo) & (t <= hi)
        d = np.diff(t[m])
        d = d[d > 0]
        return float(np.median(d)) if len(d) else np.inf
    sa, sb = step(ta), step(tb)
    dt = max(min(sa, sb), (hi - lo) / 20000)
    if not np.isfinite(dt) or dt <= 0:
        return {"status": "nooverlap"}
    g = np.arange(lo, hi, dt)
    if len(g) < 8:
        return {"status": "short"}
    va = np.interp(g, ta, ya)
    vb = np.interp(g, tb, yb)
    ok = np.isfinite(va) & np.isfinite(vb)
    va, vb = np.where(ok, va, 0.0), np.where(ok, vb, 0.0)
    va, vb = va - va[ok].mean(), vb - vb[ok].mean()
    na, nb = float(np.sqrt((va ** 2).sum())), float(np.sqrt((vb ** 2).sum()))
    if na == 0 or nb == 0:
        return {"status": "flat"}
    n = len(g)
    m = int(min(n - 2, round((max_lag if max_lag else (hi - lo) / 4) / dt)))
    # c[L] = sum a[i] * b[i + L] (B later by L samples), by FFT; each shift normalised by the energy
    # of the samples that overlap at it (else large shifts look weaker than they are)
    size = 1 << int(np.ceil(np.log2(2 * n)))
    c = np.fft.irfft(np.conj(np.fft.rfft(va, size)) * np.fft.rfft(vb, size), size)
    Ls = np.arange(-m, m + 1)
    raw = np.array([c[L] if L >= 0 else c[size + L] for L in Ls])
    ea, eb = np.r_[0.0, np.cumsum(va ** 2)], np.r_[0.0, np.cumsum(vb ** 2)]
    ena = np.array([ea[n - L] - ea[0] if L >= 0 else ea[n] - ea[-L] for L in Ls])
    enb = np.array([eb[n] - eb[L] if L >= 0 else eb[n + L] - eb[0] for L in Ls])
    with np.errstate(all="ignore"):
        seg = np.where((ena > 0) & (enb > 0), raw / np.sqrt(ena * enb), 0.0)
    lags = Ls * dt
    k = int(np.argmax(np.abs(seg)))
    r = float(seg[k])
    best = abs(r)
    # another shift (away from this peak) that matches almost as well: a periodic signal
    far = np.abs(np.arange(len(seg)) - k) > max(3, len(seg) // 50)
    peaks = [i for i in range(1, len(seg) - 1) if far[i] and abs(seg[i]) >= abs(seg[i - 1]) and abs(seg[i]) >= abs(seg[i + 1])]
    ambiguous = any(abs(seg[i]) >= 0.9 * best for i in peaks)
    thin = max(1, len(seg) // 200)
    return {"status": "ok", "lag": float(lags[k]), "r": r, "ambiguous": bool(ambiguous), "weak": best < 0.5,
            "resolution": float(max(sa, sb)), "curve": {"lags": [float(x) for x in lags[::thin]], "r": [float(x) for x in seg[::thin]]}}
