"""Which parameter matters, and how much (MF05) - on the parameter sets themselves, no model.

One value per set ``y`` (the goal's worst case, an output's aggregate, any per-set column) and the
sets' parameter values ``X``:

* **correlation** per parameter - Pearson (straight lines) and Spearman (any monotonic relation);
* **variance shares** - an ANOVA of the sets: each parameter's *main effect* (how far the mean of
  ``y`` moves between its levels) and each pair's *interaction* (what the pair's cell means add to
  the two main effects), as a share of the variance of ``y``; the rest is what neither explains
  (three-way terms, scenarios' noise). A parameter whose main effect and interactions together are
  under a threshold is *weak* - a candidate to fix and stop sweeping;
* **Sobol indices** from the same data: first order ``S_i = Var(E[y | x_i]) / Var(y)`` (= the main
  effect's share) and total ``ST_i = 1 - Var(E[y | x_~i]) / Var(y)`` (``x_~i``: all the other
  parameters). On a full grid they are the indices of the grid's quadrature; on scattered sets a
  parameter with many distinct values is binned (quantiles), and the total index needs the other
  parameters' combinations to repeat - when they don't, it is not given (``None``) rather than
  guessed. (A surrogate-based estimate comes with MF04.)

Computed with numpy only (no dependency), checked against the Ishigami function's known indices.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

MAX_LEVELS = 12          # more distinct values than this: quantile bins


def levels(x: np.ndarray, max_levels: int = MAX_LEVELS) -> np.ndarray:
    """Integer level codes of one parameter (NaN: -1): its values when few, else quantile bins."""
    s = pd.Series(x)
    finite = s.notna()
    out = np.full(len(s), -1, dtype=np.int64)
    if not finite.any():
        return out
    vals = s[finite]
    if vals.nunique() <= max_levels:
        out[finite.to_numpy()] = pd.factorize(vals, sort=True)[0]
    else:
        out[finite.to_numpy()] = pd.qcut(vals.rank(method="first"), max_levels, labels=False).to_numpy()
    return out


def _between(codes: np.ndarray, y: np.ndarray) -> float:
    """Sum over groups of n * (group mean - grand mean)^2."""
    df = pd.DataFrame({"g": codes, "y": y})
    g = df.groupby("g")["y"].agg(["mean", "count"])
    return float((g["count"] * (g["mean"] - y.mean()) ** 2).sum())


def _corr(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _code_numbers(x: np.ndarray) -> np.ndarray:
    """A parameter as numbers for a correlation: numbers as they are, text by its sorted level."""
    try:
        return np.asarray(x, dtype=float)
    except (TypeError, ValueError):
        return pd.factorize(pd.Series(x).astype(str), sort=True)[0].astype(float)


def analyse(X: Dict[str, np.ndarray], y: np.ndarray, threshold: float = 0.05, max_levels: int = MAX_LEVELS,
            interactions: bool = True) -> Dict[str, Any]:
    """The sensitivity of ``y`` to each parameter of ``X`` (one row per set). Sets with ``y`` or a
    parameter missing are left out."""
    names = list(X)
    y = np.asarray(y, dtype=float)
    num = {k: _code_numbers(np.asarray(v)) for k, v in X.items()}
    ok = np.isfinite(y)
    for k in names:
        ok &= ~pd.isna(pd.Series(X[k])).to_numpy()
    y = y[ok]
    n = int(len(y))
    out: Dict[str, Any] = {"n": n, "threshold": threshold, "params": [], "pairs": [], "rest": None}
    if n < 3 or float(np.var(y)) == 0.0:
        out["flat"] = True
        return out
    codes = {k: levels(num[k][ok], max_levels) for k in names}
    sst = float(((y - y.mean()) ** 2).sum())
    main = {k: _between(codes[k], y) / sst for k in names}
    pairs: List[Dict[str, Any]] = []
    if interactions:
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                cell = codes[a] * (codes[b].max() + 1) + codes[b]
                share = _between(cell, y) / sst - main[a] - main[b]
                pairs.append({"a": a, "b": b, "share": max(0.0, share)})
    pairs.sort(key=lambda p: -p["share"])
    # total index: what is left when every OTHER parameter is fixed (their combinations must repeat)
    total: Dict[str, Optional[float]] = {}
    for k in names:
        others = [codes[o] for o in names if o != k]
        if not others:
            total[k] = 1.0
            continue
        key = pd.Series(list(zip(*others))) if len(others) > 1 else pd.Series(others[0])
        g = pd.factorize(key)[0]
        repeats = np.bincount(g).mean()
        total[k] = None if repeats < 1.5 else max(0.0, 1.0 - _between(g, y) / sst)
    params = []
    for k in names:
        inter = sum(p["share"] for p in pairs if k in (p["a"], p["b"]))
        params.append({
            "name": k,
            "pearson": _corr(num[k][ok], y),
            "spearman": _corr(pd.Series(num[k][ok]).rank().to_numpy(), pd.Series(y).rank().to_numpy()),
            "main": main[k], "interactions": inter, "first": main[k], "total": total[k],
            "levels": int(codes[k].max() + 1),
            "weak": bool(main[k] + inter < threshold),
        })
    params.sort(key=lambda p: -(p["main"] + p["interactions"]))
    out["params"] = params
    out["pairs"] = pairs[:20]
    out["rest"] = max(0.0, 1.0 - sum(main.values()) - sum(p["share"] for p in pairs))
    return out


def for_sets(p: Any, value: np.ndarray, sets: Optional[Sequence[int]] = None, **kw: Any) -> Dict[str, Any]:
    """`analyse` on a prepared table's parameter sets (``p.first_row`` gives each set's values);
    ``sets``: only these (a group)."""
    idx = np.arange(p.n_sets) if sets is None else np.asarray([s for s in sets if 0 <= s < p.n_sets], dtype=np.int64)
    X = {c: p.df[c].to_numpy()[p.first_row][idx] for c in p.params}
    return analyse(X, np.asarray(value, dtype=float)[idx], **kw)
