"""MF10 Decide: ranking a group of parameter sets on several objectives (published MCDM methods,
written here with numpy - no dependency).

Input: a matrix ``values`` (sets x objectives, the objectives' worst cases), each objective's
direction (min / max) and weight. Every method works on the same normalised utilities
``u`` in [0, 1] (1 = the best of the group on that objective, min-max over the group), so the
explanation "A above B because..." is the same arithmetic for each one:

- weighted sum: score = sum w_j u_j (weights normalised to 1).
- TOPSIS (Hwang & Yoon 1981): vector-normalised, weighted; distance to the ideal and the anti-ideal
  point; score = d- / (d+ + d-).
- Hurwicz (optimism alpha): score = alpha * max_j(w'_j u_j) + (1 - alpha) * min_j(w'_j u_j), with
  w'_j = w_j / max(w) so that equal weights leave u as it is.
- Savage minimax regret: regret_j = w'_j (1 - u_j) (the best of the group has none); score =
  -max_j regret_j (less regret is better).
- pairwise comparisons (Saaty's AHP): weights = the principal eigenvector of a reciprocal matrix,
  consistency ratio CR = CI / RI, CI = (lambda_max - n) / (n - 1); CR > 0.1 is a warning.

Indifference margin: two sets whose scores differ by less than ``margin`` (a share of the score's
range in the group) are tied - they get the same rank.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

METHODS = ("weighted", "topsis", "hurwicz", "savage")

# Saaty's random index by matrix size (n = 1..10)
RANDOM_INDEX = [0.0, 0.0, 0.0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]
CR_LIMIT = 0.1


def ahp(matrix: Sequence[Sequence[float]]) -> Dict[str, Any]:
    """Weights from a pairwise comparison matrix: a[i][j] = how much more objective i matters than j.
    The lower triangle is taken from the upper one (a[j][i] = 1 / a[i][j]), so a half-filled matrix works."""
    a = np.array(matrix, dtype=float)
    n = a.shape[0]
    if a.ndim != 2 or a.shape[1] != n or n < 1:
        raise ValueError("The comparisons must be a square table, one row and column per objective.")
    for i in range(n):
        a[i, i] = 1.0
        for j in range(i + 1, n):
            if not np.isfinite(a[i, j]) or a[i, j] <= 0:
                raise ValueError("Each comparison must be a positive number (1 = equal, 9 = far more important).")
            a[j, i] = 1.0 / a[i, j]
    vals, vecs = np.linalg.eig(a)
    k = int(np.argmax(vals.real))
    w = np.abs(vecs[:, k].real)
    w = w / w.sum()
    lam = float(vals[k].real)
    ci = (lam - n) / (n - 1) if n > 2 else 0.0
    ri = RANDOM_INDEX[n] if n < len(RANDOM_INDEX) else RANDOM_INDEX[-1]
    cr = ci / ri if ri > 0 else 0.0
    return {"weights": w.tolist(), "lambdaMax": lam, "ci": ci, "cr": cr, "consistent": cr <= CR_LIMIT}


def utilities(values: np.ndarray, directions: Sequence[str]) -> np.ndarray:
    """0..1 per objective over the group, 1 = best; a constant objective is 1 for all; NaN -> 0."""
    u = np.zeros_like(values, dtype=float)
    for j, d in enumerate(directions):
        v = values[:, j]
        ok = np.isfinite(v)
        if not ok.any():
            continue
        lo, hi = float(v[ok].min()), float(v[ok].max())
        if hi == lo:
            u[ok, j] = 1.0
        else:
            u[ok, j] = (v[ok] - lo) / (hi - lo) if d == "max" else (hi - v[ok]) / (hi - lo)
    return u


def _weights(weights: Sequence[float], m: int) -> np.ndarray:
    w = np.array([max(0.0, float(x)) for x in weights][:m] + [1.0] * max(0, m - len(weights)))
    return w / w.sum() if w.sum() > 0 else np.full(m, 1.0 / m)


def scores(values: np.ndarray, directions: Sequence[str], w: np.ndarray, method: str, alpha: float = 0.5) -> np.ndarray:
    """Higher is better for every method."""
    u = utilities(values, directions)
    if method == "weighted":
        return u @ w
    rel = w / w.max() if w.max() > 0 else w
    if method == "hurwicz":
        a = min(1.0, max(0.0, alpha))
        wu = u * rel
        return a * wu.max(axis=1) + (1 - a) * wu.min(axis=1)
    if method == "savage":
        return -((1 - u) * rel).max(axis=1)
    if method == "topsis":
        x = np.where(np.isfinite(values), values, np.nan)
        norm = np.sqrt(np.nansum(x * x, axis=0))
        norm[norm == 0] = 1.0
        v = x / norm * w
        best = np.array([np.nanmax(v[:, j]) if d == "max" else np.nanmin(v[:, j]) for j, d in enumerate(directions)])
        worst = np.array([np.nanmin(v[:, j]) if d == "max" else np.nanmax(v[:, j]) for j, d in enumerate(directions)])
        # a missing value counts as the worst of the group on that objective
        v = np.where(np.isnan(v), worst, v)
        dp = np.sqrt(((v - best) ** 2).sum(axis=1))
        dm = np.sqrt(((v - worst) ** 2).sum(axis=1))
        tot = dp + dm
        return np.where(tot > 0, dm / np.where(tot > 0, tot, 1), 1.0)
    raise ValueError(f"Unknown ranking method {method!r}; one of {', '.join(METHODS)}.")


def ranks_with_margin(s: np.ndarray, margin: float) -> List[int]:
    """Rank 1 = best; consecutive sets (in score order) closer than margin x the score range tie with
    the first of their run, so a chain of small steps still breaks once it adds up."""
    order = np.argsort(-s, kind="stable")
    span = float(s.max() - s.min()) if len(s) else 0.0
    tol = max(0.0, margin) * span
    ranks = [0] * len(s)
    lead = None
    r = 0
    for pos, i in enumerate(order):
        if lead is None or s[lead] - s[i] > tol:
            lead, r = i, pos + 1
        ranks[int(i)] = r
    return ranks


def rank(values: Sequence[Sequence[float]], directions: Sequence[str], weights: Sequence[float], method: str = "weighted",
         alpha: float = 0.5, margin: float = 0.0, pairwise: Optional[Sequence[Sequence[float]]] = None,
         explain: int = 20) -> Dict[str, Any]:
    """The ranking of the sets (rows) and, for the first ``explain`` in order, each objective's part in
    the step to the next one: "A above B because" - the weighted utility difference per objective."""
    x = np.array(values, dtype=float).reshape(len(values), -1) if len(values) else np.zeros((0, len(directions)))
    m = x.shape[1]
    if m != len(directions) or m == 0:
        raise ValueError("Give one direction per objective (at least one objective).")
    if any(d not in ("min", "max") for d in directions):
        raise ValueError("A direction is min or max.")
    out: Dict[str, Any] = {"method": method}
    if pairwise is not None:
        a = ahp(pairwise)
        if len(a["weights"]) != m:
            raise ValueError("The comparisons table needs one row per objective.")
        out["ahp"] = a
        w = np.array(a["weights"])
    else:
        w = _weights(weights, m)
    out["weights"] = w.tolist()
    if x.shape[0] == 0:
        return {**out, "scores": [], "ranks": [], "order": [], "why": []}
    s = scores(x, directions, w, method, alpha)
    # an objective missing everywhere leaves NaN: such a set is last (and JSON has no NaN)
    s = np.where(np.isfinite(s), s, (np.nanmin(s) if np.isfinite(s).any() else 0.0) - 1.0)
    rk = ranks_with_margin(s, margin)
    order = sorted(range(len(s)), key=lambda i: (rk[i], -s[i], i))
    u = utilities(x, directions)
    why = []
    for a_i, b_i in zip(order[: max(0, explain)], order[1: max(0, explain) + 1]):
        why.append({"a": a_i, "b": b_i, "tie": rk[a_i] == rk[b_i],
                    "parts": [float(w[j] * (u[a_i, j] - u[b_i, j])) for j in range(m)]})
    return {**out, "scores": s.tolist(), "ranks": rk, "order": order, "utilities": u.tolist(), "why": why}
