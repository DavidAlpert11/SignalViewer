"""Designs of experiments (MF03): new parameter sets to run, before (or beside) any results.

Each parameter is a spec ``{name, kind, lo, hi, levels?, value?}``:

* ``continuous`` - any value in ``[lo, hi]`` (rounded to 6 significant digits, so that a set read
  back from the results table has the same id as the one designed);
* ``integer``    - whole values in ``[lo, hi]``;
* ``categorical``- one of ``levels`` (text or numbers);
* ``fixed``      - not varied: always ``value`` (the problem table's *off*).

Methods (open, by what they do - no proprietary algorithm):

* ``space``     space-filling: a Latin hypercube improved for centred discrepancy (scipy.stats.qmc,
  BSD-3 - already a dependency);
* ``sobol``     a scrambled Sobol sequence (scipy.stats.qmc);
* ``random``    uniform random;
* ``factorial`` every combination of ``levels`` values per parameter (a categorical: all its levels);
* ``boxbehnken``each pair of parameters at their ends, the others at the middle, plus centre points
  (3 parameters or more);
* ``ccd``       central composite, face-centred: the corners, a point on each face, the centre
  (stays inside the ranges);
* ``fill``      fill the gaps of the sets already run: candidates from a space-filling sample,
  each next point the one farthest from every set so far (max-min distance).
"""
from __future__ import annotations

import itertools
import math
import warnings
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy.stats import qmc

METHODS = ("space", "sobol", "random", "factorial", "boxbehnken", "ccd", "fill")
KINDS = ("continuous", "integer", "categorical", "fixed")
MAX_SETS = 20000


class DoeError(ValueError):
    pass


def _round6(v: float) -> float:
    if v == 0 or not math.isfinite(v):
        return float(v)
    return float(f"{v:.6g}")


def check_specs(specs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for s in specs:
        k = s.get("kind")
        if k not in KINDS:
            raise DoeError(f"{s.get('name')}: unknown kind {k!r}")
        if k == "categorical":
            lv = list(s.get("levels") or [])
            if not lv:
                raise DoeError(f"{s.get('name')}: a categorical parameter needs its levels")
            out.append({**s, "levels": lv})
        elif k == "fixed":
            out.append(s)
        else:
            lo, hi = float(s.get("lo")), float(s.get("hi"))  # type: ignore[arg-type]
            if not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
                raise DoeError(f"{s.get('name')}: the range must go from low to high")
            out.append({**s, "lo": lo, "hi": hi})
    if not any(s["kind"] != "fixed" for s in out):
        raise DoeError("Choose at least one parameter to vary.")
    return out


def _value(s: Dict[str, Any], u: float) -> Any:
    """A unit coordinate (0..1) to a parameter's value."""
    k = s["kind"]
    u = min(1.0, max(0.0, float(u)))
    if k == "categorical":
        lv = s["levels"]
        return lv[min(len(lv) - 1, int(u * len(lv)))]
    if k == "integer":
        lo, hi = math.ceil(s["lo"]), math.floor(s["hi"])
        return int(min(hi, max(lo, round(lo + u * (hi - lo)))))
    return _round6(s["lo"] + u * (s["hi"] - s["lo"]))


def _unit(s: Dict[str, Any], v: Any) -> float:
    """A parameter's value back to 0..1 (for distances)."""
    if s["kind"] == "categorical":
        lv = [str(x) for x in s["levels"]]
        return (lv.index(str(v)) + 0.5) / len(lv) if str(v) in lv else 0.5
    span = s["hi"] - s["lo"]
    return (float(v) - s["lo"]) / span if span > 0 else 0.5


def _three(d: int, kind: str) -> np.ndarray:
    """Box-Behnken or face-centred CCD in -1 / 0 / 1 coordinates, d dimensions."""
    pts: List[List[float]] = []
    if kind == "boxbehnken":
        if d < 3:
            raise DoeError("Box-Behnken needs 3 parameters or more to vary.")
        for i, j in itertools.combinations(range(d), 2):
            for a, b in itertools.product((-1, 1), repeat=2):
                p = [0.0] * d
                p[i], p[j] = a, b
                pts.append(p)
        pts += [[0.0] * d] * 3
    else:
        pts += [list(c) for c in itertools.product((-1.0, 1.0), repeat=d)]
        for i in range(d):
            for e in (-1.0, 1.0):
                p = [0.0] * d
                p[i] = e
                pts.append(p)
        pts.append([0.0] * d)
    return np.asarray(pts)


def design(specs: Sequence[Dict[str, Any]], method: str, n: float = 20, seed: int = 0, levels: int = 3,
           existing: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """The designed sets: ``{"sets": [{name: value}], "method", "n", "discrepancy", "min_distance"}``."""
    if method not in METHODS:
        raise DoeError(f"Unknown method: {method}")
    specs = check_specs(specs)
    free = [s for s in specs if s["kind"] != "fixed"]
    d = len(free)
    n = int(max(1, min(MAX_SETS, int(n))))
    rng = np.random.default_rng(seed)
    if method in ("space", "fill"):
        u = qmc.LatinHypercube(d=d, optimization="random-cd" if d > 1 else None, seed=seed).random(n if method == "space" else max(50 * n, 500))
    elif method == "sobol":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")           # n not a power of 2: still a good sample
            u = qmc.Sobol(d=d, scramble=True, seed=seed).random(n)
    elif method == "random":
        u = rng.random((n, d))
    elif method == "factorial":
        axes = []
        for s in free:
            k = len(s["levels"]) if s["kind"] == "categorical" else max(2, int(levels))
            if s["kind"] == "integer":
                k = min(k, int(math.floor(s["hi"]) - math.ceil(s["lo"])) + 1)
            axes.append((np.arange(k) + 0.5) / k if s["kind"] == "categorical" else np.linspace(0, 1, max(1, k)))
        total = int(np.prod([len(a) for a in axes]))
        if total > MAX_SETS:
            raise DoeError(f"{total:,} combinations: too many - fewer levels or parameters.")
        u = np.asarray(list(itertools.product(*axes)), dtype=float).reshape(-1, d)
    else:
        if any(s["kind"] == "categorical" for s in free):
            raise DoeError("Box-Behnken and central composite are for number parameters.")
        u = (_three(d, method) + 1) / 2
    if method == "fill":
        old = np.asarray([[_unit(s, e.get(s["name"])) for s in free] for e in (existing or [])], dtype=float).reshape(-1, d)
        chosen: List[int] = []
        dist = np.full(len(u), np.inf)
        for row in old:
            dist = np.minimum(dist, np.sqrt(((u - row) ** 2).sum(axis=1)))
        for _ in range(n):
            i = int(np.argmax(dist))
            chosen.append(i)
            dist = np.minimum(dist, np.sqrt(((u - u[i]) ** 2).sum(axis=1)))
        u = u[chosen]
    sets = []
    for row in u:
        p: Dict[str, Any] = {}
        k = 0
        for s in specs:
            if s["kind"] == "fixed":
                p[s["name"]] = s.get("value")
            else:
                p[s["name"]] = _value(s, row[k])
                k += 1
        sets.append(p)
    # the same set twice (integers, levels): once
    seen, uniq = set(), []
    for p in sets:
        key = tuple(str(p[s["name"]]) for s in specs)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    out_u = np.asarray([[_unit(s, p[s["name"]]) for s in free] for p in uniq], dtype=float).reshape(-1, d)
    disc = float(qmc.discrepancy(np.clip(out_u, 0, 1))) if len(out_u) > 1 else None
    md = None
    if 1 < len(out_u) <= 4000:
        diff = out_u[:, None, :] - out_u[None, :, :]
        dd = np.sqrt((diff ** 2).sum(axis=2))
        np.fill_diagonal(dd, np.inf)
        md = float(dd.min())
    return {"sets": uniq, "method": method, "n": len(uniq), "discrepancy": disc, "min_distance": md}
