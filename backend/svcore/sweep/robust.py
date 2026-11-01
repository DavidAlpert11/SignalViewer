"""MF08 Robust design: how a set's result spreads when its parameters are not exactly what was asked.

Extends the goal's tolerance (``question.robust``, S06: {param: {mode pct | abs | steps, value}}) -
the same band - with a distribution inside it (``dist``, optional, default ``uniform``):

- uniform:    value - d .. value + d
- triangular: value - d .. value + d, most likely the value itself
- normal:     mean the value, sigma = d / 2 (the band is +-2 sigma, about 95 %)

where d is the band's half width (pct: |value| x v / 100; abs: v; steps: v x the parameter's median
step between its levels in the table). Samples: Monte Carlo (independent random) or a Latin
hypercube (scipy.stats.qmc, stratified: the statistics settle with fewer runs).

Two sources: a model of the result (MF04's surrogates - fast, virtual) and real runs (the samples as
a group, run by the run step, MF06; their statistics from the group's sets). Statistics per centre:
mean, sigma, a percentile on the bad side, and the probability of failure (the share of samples that
break a limit). No new dependency (numpy, scipy).
"""
from __future__ import annotations

import math
import operator
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import numpy as np
from scipy import stats as st
from scipy.stats import qmc

DISTS = ("uniform", "triangular", "normal")
METHODS = ("lhs", "mc")
MAX_SAMPLES = 20000
_OPS: Dict[str, Callable[[Any, Any], Any]] = {"<=": operator.le, "<": operator.lt, ">=": operator.ge, ">": operator.gt}


class RobustError(ValueError):
    pass


def half_width(tol: Dict[str, Any], value: float, levels: Optional[Sequence[float]] = None) -> float:
    mode, v = tol.get("mode", "pct"), abs(float(tol.get("value", 0) or 0))
    if mode == "steps":
        lv = np.unique(np.asarray([x for x in (levels or []) if math.isfinite(x)], dtype=float))
        step = float(np.median(np.diff(lv))) if len(lv) > 1 else 0.0
        return v * step
    return abs(value) * v / 100 if mode == "pct" else v


def _ppf(dist: str, u: np.ndarray, x: float, d: float) -> np.ndarray:
    if d <= 0:
        return np.full_like(u, x)
    if dist == "normal":
        return np.asarray(st.norm.ppf(np.clip(u, 1e-12, 1 - 1e-12), loc=x, scale=d / 2))
    if dist == "triangular":
        return np.asarray(st.triang.ppf(u, 0.5, loc=x - d, scale=2 * d))
    return x - d + 2 * d * u


def sample(centre: Dict[str, Any], tols: Dict[str, Dict[str, Any]], n: int, method: str = "lhs", seed: int = 0,
           levels: Optional[Dict[str, Sequence[float]]] = None) -> List[Dict[str, Any]]:
    """n points around ``centre``: each toleranced numeric parameter drawn from its distribution, the
    others as they are."""
    if method not in METHODS:
        raise RobustError(f"Sampling is one of {', '.join(METHODS)}.")
    names = [k for k in tols if k in centre and isinstance(centre[k], (int, float)) and math.isfinite(float(centre[k]))]
    if not names:
        raise RobustError("Give a tolerance to at least one numeric parameter (the goal's *Robust to*).")
    n = max(2, min(MAX_SAMPLES, int(n)))
    for k in names:
        if tols[k].get("dist", "uniform") not in DISTS:
            raise RobustError(f"A distribution is one of {', '.join(DISTS)}.")
    u = (qmc.LatinHypercube(d=len(names), seed=seed).random(n) if method == "lhs"
         else np.random.default_rng(seed).random((n, len(names))))
    cols = {k: _ppf(tols[k].get("dist", "uniform"), u[:, j], float(centre[k]),
                    half_width(tols[k], float(centre[k]), (levels or {}).get(k))) for j, k in enumerate(names)}
    return [{**centre, **{k: float(cols[k][i]) for k in names}} for i in range(n)]


def statistics(y: Union[Sequence[float], np.ndarray], direction: str = "max", pct: float = 95.0,
               limit: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Mean, sigma (sample), the percentile on the bad side (pct = 95: the value 95 % of the samples are
    better than), and the share breaking ``limit`` ({op, value}; a missing value breaks it)."""
    a = np.asarray(y, dtype=float)
    ok = a[np.isfinite(a)]
    out: Dict[str, Any] = {"n": int(len(a)), "valid": int(len(ok))}
    if len(ok):
        q = 100 - pct if direction == "max" else pct
        out.update({"mean": float(ok.mean()), "std": float(ok.std(ddof=1)) if len(ok) > 1 else 0.0,
                    "pct": float(np.percentile(ok, q)), "min": float(ok.min()), "max": float(ok.max())})
    else:
        out.update({"mean": None, "std": None, "pct": None, "min": None, "max": None})
    if limit and limit.get("op") in _OPS:
        good = np.zeros(len(a), dtype=bool)
        fin = np.isfinite(a)
        good[fin] = _OPS[limit["op"]](a[fin], float(limit["value"]))
        out["pFail"] = float(1 - good.mean()) if len(a) else None
    return out


def on_model(predict: Callable[[List[Dict[str, Any]]], np.ndarray], centres: Sequence[Dict[str, Any]],
             tols: Dict[str, Dict[str, Any]], n: int = 200, method: str = "lhs", seed: int = 0,
             direction: str = "max", pct: float = 95.0, limit: Optional[Dict[str, Any]] = None,
             levels: Optional[Dict[str, Sequence[float]]] = None) -> List[Dict[str, Any]]:
    """Each centre's statistics over n samples evaluated on a model (the same samples' pattern for each
    centre, so the centres are compared on equal terms)."""
    out = []
    for c in centres:
        pts = sample(c, tols, n, method, seed, levels)
        y = np.asarray(predict(pts), dtype=float)
        out.append({"centre": c, **statistics(y, direction, pct, limit), "nominal": float(predict([c])[0])})
    return out
