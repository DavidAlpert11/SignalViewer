"""Optimisers in the loop (MF07): each generation of new sets is RUN (MF06's runner), its results
read back, and the next generation chosen from them.

Written here, from the published algorithms (no dependency): pymoo was the candidate, but one of its
required dependencies (moocore) is LGPL-2.1-or-later - outside the permissive-only rule (§3, checked
2026-11-01 in the released wheels' metadata).

* ``de``        differential evolution (rand/1/bin) - one objective;
* ``nsga2``     NSGA-II: non-dominated sorting, crowding distance, SBX crossover and polynomial
  mutation - two or three objectives (the Pareto front);
* ``surrogate`` model-assisted: after a space-filling start, each generation half from the best
  predicted points of a radial-basis model of everything run so far (MF04), half space-filling
  around the best - for few, costly runs;
* ``auto``      by the problem: several objectives → nsga2; a small budget (under 15 runs per
  parameter) → surrogate; else de.

Constraints (the goal's conditions) by Deb's rules: a set that meets every condition beats one that
does not; between two that do not, the smaller total violation wins.

Parameters work in 0..1 inside; integers rounded, a categorical parameter's level by its slice.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import qmc

from svcore.sweep.doe import _unit, _value, check_specs

METHODS = ("auto", "de", "nsga2", "surrogate")


class OptimiseError(ValueError):
    pass


def choose(method: str, n_obj: int, dims: int, budget: int) -> str:
    if method != "auto":
        if method not in METHODS:
            raise OptimiseError(f"Unknown method: {method}")
        if method == "de" and n_obj > 1:
            raise OptimiseError("Differential evolution is for one objective: use NSGA-II for several.")
        return method
    if n_obj > 1:
        return "nsga2"
    return "surrogate" if budget < 15 * max(1, dims) else "de"


# --------------------------------------------------------------------------- non-dominated sorting
def _dominates(a: np.ndarray, b: np.ndarray, va: float, vb: float) -> bool:
    """Constrained domination (all objectives minimised)."""
    if va > 0 or vb > 0:
        return va < vb
    return bool(np.all(a <= b) and np.any(a < b))


def fronts(F: np.ndarray, V: np.ndarray) -> List[List[int]]:
    """Fronts by constrained domination (all objectives minimised), vectorised."""
    n = len(F)
    if n == 0:
        return []
    le = np.all(F[:, None, :] <= F[None, :, :], axis=2)
    lt = np.any(F[:, None, :] < F[None, :, :], axis=2)
    feas = V <= 0
    D = le & lt & feas[:, None] & feas[None, :]                      # both feasible: Pareto
    D |= feas[:, None] & ~feas[None, :]                              # feasible beats infeasible
    D |= (~feas[:, None] & ~feas[None, :]) & (V[:, None] < V[None, :])
    np.fill_diagonal(D, False)
    cnt = D.sum(axis=0)
    out: List[List[int]] = []
    left = np.ones(n, dtype=bool)
    while left.any():
        cur = np.flatnonzero(left & (cnt == 0))
        if not len(cur):
            break
        out.append(cur.tolist())
        left[cur] = False
        cnt = cnt - D[cur].sum(axis=0)
    return out


def crowding(F: np.ndarray) -> np.ndarray:
    n, m = F.shape
    d = np.zeros(n)
    if n <= 2:
        return np.full(n, np.inf)
    for j in range(m):
        o = np.argsort(F[:, j])
        span = F[o[-1], j] - F[o[0], j] or 1.0
        d[o[0]] = d[o[-1]] = np.inf
        d[o[1:-1]] += (F[o[2:], j] - F[o[:-2], j]) / span
    return d


def pareto_front(F: np.ndarray, V: Optional[np.ndarray] = None) -> List[int]:
    V = np.zeros(len(F)) if V is None else V
    return fronts(F, V)[0] if len(F) else []


# --------------------------------------------------------------------------- the loop
class Optimiser:
    """Ask / tell over the unit cube; `history` keeps every set told."""

    def __init__(self, specs: Sequence[Dict[str, Any]], n_obj: int, method: str, pop: int, seed: int = 0):
        self.specs = check_specs(specs)
        self.free = [s for s in self.specs if s["kind"] != "fixed"]
        self.d = len(self.free)
        self.n_obj = n_obj
        self.method = method
        self.pop = max(4, int(pop))
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.U = np.zeros((0, self.d))          # every set told, in 0..1
        self.F = np.zeros((0, n_obj))           # its objectives (minimised)
        self.V = np.zeros(0)                    # its total violation (0: meets every condition)
        self._asked = np.zeros((0, self.d))
        self.gen = 0
        self.pop_idx = np.zeros(0, dtype=int)    # the current population (indices into U)

    def params(self, u: np.ndarray) -> Dict[str, Any]:
        p: Dict[str, Any] = {}
        k = 0
        for s in self.specs:
            if s["kind"] == "fixed":
                p[s["name"]] = s.get("value")
            else:
                p[s["name"]] = _value(s, u[k])
                k += 1
        return p

    def unit(self, p: Dict[str, Any]) -> np.ndarray:
        return np.array([_unit(s, p.get(s["name"])) for s in self.free])

    # the population: the best `pop` of the last population and its children
    def _select(self, cand: np.ndarray) -> np.ndarray:
        F, V = self.F[cand], self.V[cand]
        if self.n_obj == 1:
            key = np.where(V > 0, 1e300 + V, F[:, 0])
            return cand[np.argsort(key)[: self.pop]]
        chosen: List[int] = []
        for fr in fronts(F, V):
            if len(chosen) + len(fr) <= self.pop:
                chosen += fr
            else:
                cd = crowding(F[fr])
                chosen += [fr[i] for i in np.argsort(-cd)[: self.pop - len(chosen)]]
                break
        return cand[np.asarray(chosen, dtype=int)]

    def _survivors(self) -> np.ndarray:
        return self.pop_idx

    def ask(self) -> List[Dict[str, Any]]:
        n = self.pop
        if len(self.U) == 0:
            U = qmc.LatinHypercube(d=self.d, seed=self.seed).random(n)
        elif self.method == "de":
            U = self._de()
        elif self.method == "nsga2":
            U = self._nsga2()
        else:
            U = self._surrogate()
        U = np.clip(U, 0, 1)
        self._asked = U
        self.gen += 1
        return [self.params(u) for u in U]

    def tell(self, objectives: np.ndarray, violation: np.ndarray, asked: Optional[np.ndarray] = None) -> None:
        U = self._asked if asked is None else asked
        F = np.asarray(objectives, dtype=float).reshape(len(U), self.n_obj)
        V = np.asarray(violation, dtype=float)
        bad = ~np.all(np.isfinite(F), axis=1)            # a run that failed: worst, and a violation
        F = np.where(np.isfinite(F), F, 1e300)
        V = np.where(bad, np.maximum(V, 1e9), V)
        start = len(self.U)
        self.U = np.vstack([self.U, U])
        self.F = np.vstack([self.F, F])
        self.V = np.concatenate([self.V, V])
        self.pop_idx = self._select(np.concatenate([self.pop_idx, np.arange(start, len(self.U))]))

    # -- differential evolution (rand/1/bin), the trial against its parent through survivor choice
    def _de(self) -> np.ndarray:
        P = self.U[self._survivors()]
        n = len(P)
        out = []
        for i in range(self.pop):
            a, b, c = P[self.rng.choice(n, 3, replace=n < 3)]
            mutant = a + 0.7 * (b - c)
            cross = self.rng.random(self.d) < 0.9
            cross[self.rng.integers(self.d)] = True
            out.append(np.where(cross, mutant, P[i % n]))
        return np.asarray(out)

    # -- NSGA-II: binary tournament (rank, crowding), SBX, polynomial mutation
    def _nsga2(self) -> np.ndarray:
        idx = self._survivors()
        P, F, V = self.U[idx], self.F[idx], self.V[idx]
        rank = np.zeros(len(P))
        for r, fr in enumerate(fronts(F, V)):
            rank[fr] = r
        cd = np.zeros(len(P))
        for fr in fronts(F, V):
            cd[fr] = crowding(F[fr])

        def pick() -> np.ndarray:
            i, j = self.rng.integers(len(P), size=2)
            return P[i] if (rank[i], -cd[i]) < (rank[j], -cd[j]) else P[j]
        out: List[np.ndarray] = []
        eta_c, eta_m = 15.0, 20.0
        while len(out) < self.pop:
            p1, p2 = pick(), pick()
            c1, c2 = p1.copy(), p2.copy()
            for k in range(self.d):
                if self.rng.random() < 0.5 and abs(p1[k] - p2[k]) > 1e-12:
                    u = self.rng.random()
                    beta = (2 * u) ** (1 / (eta_c + 1)) if u <= 0.5 else (1 / (2 * (1 - u))) ** (1 / (eta_c + 1))
                    c1[k] = 0.5 * ((1 + beta) * p1[k] + (1 - beta) * p2[k])
                    c2[k] = 0.5 * ((1 - beta) * p1[k] + (1 + beta) * p2[k])
            for c in (c1, c2):
                c[:] = np.clip(c, 0, 1)
                for k in range(self.d):                     # polynomial mutation, bounded (Deb)
                    if self.rng.random() < 1.0 / max(1, self.d):
                        u, x = self.rng.random(), c[k]
                        if u < 0.5:
                            val = 2 * u + (1 - 2 * u) * (1 - x) ** (eta_m + 1)
                            dq = val ** (1 / (eta_m + 1)) - 1
                        else:
                            val = 2 * (1 - u) + 2 * (u - 0.5) * x ** (eta_m + 1)
                            dq = 1 - val ** (1 / (eta_m + 1))
                        c[k] = min(1.0, max(0.0, x + dq))
                out.append(c)
        return np.asarray(out[: self.pop])

    # -- model-assisted: half the best predicted, half exploring around the best
    def _surrogate(self) -> np.ndarray:
        from scipy.interpolate import RBFInterpolator
        ok = self.V <= 0
        y = self.F[:, 0] + np.where(ok, 0, 1e3 * (1 + self.V))
        y = np.where(np.isfinite(y), y, np.nanmax(np.where(np.isfinite(y), y, np.nan)) if np.isfinite(y).any() else 0)
        pool = qmc.LatinHypercube(d=self.d, seed=self.seed + self.gen).random(4000)
        half = self.pop // 2
        try:
            f = RBFInterpolator(self.U, (y - y.mean()) / (y.std() or 1), kernel="thin_plate_spline", smoothing=1e-6, degree=1)
            pred = f(pool)
            exploit = pool[np.argsort(pred)][: half * 4]
            # spread: greedy max-min among the best predicted
            chosen = [exploit[0]]
            for _ in range(half - 1):
                d = np.min(np.linalg.norm(exploit[:, None, :] - np.asarray(chosen)[None, :, :], axis=2), axis=1)
                chosen.append(exploit[int(np.argmax(d))])
            A = np.asarray(chosen)
        except (np.linalg.LinAlgError, ValueError):
            A = pool[:half]
        best = self.U[int(np.argmin(y))]
        B = best + self.rng.normal(0, 0.1, (self.pop - len(A), self.d))
        return np.vstack([A, B])


def objectives_of(rows: Sequence[Dict[str, Any]], objectives: Sequence[Dict[str, Any]],
                  constraints: Sequence[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
    """One set's runs (every scenario) → its objectives (worst case, minimised) and its violation."""
    def vals(col: str) -> np.ndarray:
        out = []
        for r in rows:
            v = r.get(col)
            out.append(float(v) if isinstance(v, (int, float)) and r.get("run_status", "ok") == "ok" else np.nan)
        return np.asarray(out, dtype=float)
    F = []
    for o in objectives:
        v = vals(o["column"])
        if not len(v) or np.isnan(v).any():
            F.append(np.inf)
        else:
            F.append(-float(v.min()) if o.get("direction") == "max" else float(v.max()))
    viol = 0.0
    for c in constraints:
        v = vals(c["column"])
        if not len(v) or np.isnan(v).any():
            viol += 1e6
            continue
        lim = float(c["value"])
        if c["op"] in ("<=", "<"):
            viol += max(0.0, float(v.max()) - lim)
        elif c["op"] in (">=", ">"):
            viol += max(0.0, lim - float(v.min()))
    return np.asarray(F), np.asarray(viol)


def run_loop(opt: Optimiser, evaluate: Callable[[List[Dict[str, Any]], int], List[List[Dict[str, Any]]]],
             objectives: Sequence[Dict[str, Any]], constraints: Sequence[Dict[str, Any]], budget: int,
             cancelled: Callable[[], bool] = lambda: False) -> Dict[str, Any]:
    """Generations until ``budget`` sets were run (or stopped). ``evaluate(sets, gen)`` runs them and
    returns, per set, its runs' rows."""
    while len(opt.U) < budget and not cancelled():
        sets = opt.ask()[: max(1, budget - len(opt.U))]
        opt._asked = opt._asked[: len(sets)]
        per_set = evaluate(sets, opt.gen)
        F, V = zip(*(objectives_of(r, objectives, constraints) for r in per_set)) if per_set else ((), ())
        opt.tell(np.asarray(F), np.asarray(V))
    ok = np.flatnonzero(opt.V <= 0)
    best: List[int]
    if opt.n_obj == 1:
        best = [int(ok[np.argmin(opt.F[ok, 0])])] if len(ok) else []
    else:
        # the last population holds the front found (elitist); among its feasible sets, the first front
        cand = np.asarray([i for i in opt.pop_idx if opt.V[i] <= 0], dtype=int)
        best = [int(cand[i]) for i in pareto_front(opt.F[cand])] if len(cand) else []
    return {"sets": len(opt.U), "generations": opt.gen,
            "best": [{"params": opt.params(opt.U[i]), "objectives": [(-f if o.get("direction") == "max" else f) for f, o in zip(opt.F[i].tolist(), objectives)]}
                     for i in best]}


def _finite(x: float) -> Optional[float]:
    return x if math.isfinite(x) else None
