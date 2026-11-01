"""Response surfaces (MF04): a model of one result as a function of the parameters, trained on the
sets run, validated, explored, and optimised *virtually* - the best sets the model predicts, to be
run for real.

Models (named by what they are; no proprietary algorithm):

* ``poly``     quadratic polynomial, least squares with a small ridge (numpy);
* ``rbf``      radial basis functions, thin-plate spline, lightly smoothed (scipy);
* ``knn``      the k nearest sets, weighted by inverse distance (numpy);
* ``kriging``  a Gaussian process, one length scale per parameter (scikit-learn, BSD-3 - in every full
  install since 2026-11-01; only ``signalviewer-lite`` lacks it without the extra ``sweeps-opt``, and then
  this model says what to install and the others work).

Validation: k-fold cross-validation (leave-one-out under 20 sets) - each set predicted by a model
that did not see it. Per model: mean absolute error, relative (to the mean |value|), normalised (to
the range), R². The best is the highest R².

Parameters: numbers standardised; text parameters one-hot. A model is kept (key -> fitted) for the
explore panel and the optimisation; the cache holds the last few.
"""
from __future__ import annotations

import itertools
import math
import operator
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import RBFInterpolator
from scipy.optimize import minimize
from scipy.stats import qmc

MODELS = ("poly", "rbf", "knn", "kriging")
MAX_TRAIN = 3000            # more sets: a random subset
KRIGING_MAX = 800           # Kriging's own limit (O(n^3)); the request stays seconds, not a job
_OPS: Dict[str, Callable[[Any, Any], Any]] = {">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt}


class SurrogateError(ValueError):
    pass


def have_sklearn() -> bool:
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------- encoding
class Encoder:
    """Parameters -> a standardised matrix. Numbers: (x - mean) / sd; text: one column per level."""

    def __init__(self, X: Dict[str, np.ndarray]):
        self.names = list(X)
        self.num: Dict[str, Tuple[float, float, float, float]] = {}      # mean, sd, lo, hi
        self.cat: Dict[str, List[str]] = {}
        for k, v in X.items():
            try:
                a = np.asarray(v, dtype=float)
                sd = float(np.std(a)) or 1.0
                self.num[k] = (float(np.mean(a)), sd, float(np.min(a)), float(np.max(a)))
            except (TypeError, ValueError):
                self.cat[k] = sorted({str(x) for x in v})

    def matrix(self, X: Dict[str, Any]) -> np.ndarray:
        cols = []
        for k in self.names:
            if k in self.num:
                m, sd, _, _ = self.num[k]
                cols.append((np.asarray(X[k], dtype=float) - m) / sd)
            else:
                v = np.asarray([str(x) for x in X[k]])
                cols += [(v == lv).astype(float) for lv in self.cat[k]]
        return np.column_stack(cols) if cols else np.zeros((0, 0))

    def rows(self, points: Sequence[Dict[str, Any]]) -> np.ndarray:
        return self.matrix({k: [p.get(k) for p in points] for k in self.names})

    def ranges(self) -> List[Dict[str, Any]]:
        return ([{"name": k, "kind": "number", "lo": v[2], "hi": v[3]} for k, v in self.num.items()]
                + [{"name": k, "kind": "categorical", "levels": v} for k, v in self.cat.items()])


# ---------------------------------------------------------------------------- the models
def _poly_features(Z: np.ndarray) -> np.ndarray:
    n, d = Z.shape
    cols = [np.ones(n)] + [Z[:, i] for i in range(d)]
    cols += [Z[:, i] * Z[:, j] for i, j in itertools.combinations_with_replacement(range(d), 2)]
    return np.column_stack(cols)


def _fit(kind: str, Z: np.ndarray, y: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
    """A fitted model as a function of standardised rows."""
    ym, ys = float(np.mean(y)), float(np.std(y)) or 1.0
    t = (y - ym) / ys
    if kind == "poly":
        F = _poly_features(Z)
        lam = 1e-6 * len(y)
        w = np.linalg.solve(F.T @ F + lam * np.eye(F.shape[1]), F.T @ t)
        return lambda Q: _poly_features(Q) @ w * ys + ym
    if kind == "rbf":
        f = RBFInterpolator(Z, t, kernel="thin_plate_spline", smoothing=1e-6, degree=1)
        return lambda Q: f(Q) * ys + ym
    if kind == "knn":
        k = max(1, min(5, len(y) - 1))

        def knn(Q: np.ndarray) -> np.ndarray:
            d = np.sqrt(((Q[:, None, :] - Z[None, :, :]) ** 2).sum(axis=2))
            idx = np.argsort(d, axis=1)[:, :k]
            dd = np.take_along_axis(d, idx, axis=1)
            w = 1.0 / np.maximum(dd, 1e-12)
            exact = dd[:, 0] < 1e-12
            out = (w * t[idx]).sum(axis=1) / w.sum(axis=1)
            out[exact] = t[idx[exact, 0]]
            return out * ys + ym
        return knn
    if kind == "kriging":
        if not have_sklearn():
            raise SurrogateError("kriging needs scikit-learn")
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
        if len(t) > KRIGING_MAX:                       # O(n^3): a random subset keeps it seconds
            pick = np.random.default_rng(0).choice(len(t), KRIGING_MAX, replace=False)
            Z, t = Z[pick], t[pick]
        kern = ConstantKernel(1.0) * RBF(length_scale=np.ones(Z.shape[1]), length_scale_bounds=(1e-2, 1e3)) + WhiteKernel(1e-4, (1e-9, 1e-1))
        import warnings
        with warnings.catch_warnings():                 # a length scale at its bound: still a fit
            warnings.simplefilter("ignore")
            gp = GaussianProcessRegressor(kern, normalize_y=False, n_restarts_optimizer=1, random_state=0).fit(Z, t)
        return lambda Q: gp.predict(Q) * ys + ym
    raise SurrogateError(f"Unknown model: {kind}")


def _folds(n: int, k: int, seed: int = 0) -> List[np.ndarray]:
    idx = np.random.default_rng(seed).permutation(n)
    return [idx[i::k] for i in range(k)]


def metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, Optional[float]]:
    ok = np.isfinite(p)
    if ok.sum() < 2:
        return {"mae": None, "rel": None, "norm": None, "r2": None}
    y, p = y[ok], p[ok]
    mae = float(np.mean(np.abs(y - p)))
    sst = float(((y - y.mean()) ** 2).sum())
    span = float(y.max() - y.min())
    scale = float(np.mean(np.abs(y)))
    return {"mae": mae, "rel": mae / scale if scale > 0 else None, "norm": mae / span if span > 0 else None,
            "r2": 1.0 - float(((y - p) ** 2).sum()) / sst if sst > 0 else None}


# ---------------------------------------------------------------------------- training
class Fitted:
    def __init__(self, enc: Encoder, models: Dict[str, Callable[[np.ndarray], np.ndarray]], y: np.ndarray,
                 X: Dict[str, np.ndarray]):
        self.enc, self.models, self.y, self.X = enc, models, y, X

    def predict(self, model: str, points: Sequence[Dict[str, Any]]) -> np.ndarray:
        if model not in self.models:
            raise SurrogateError(f"The model {model!r} was not trained.")
        return np.asarray(self.models[model](self.enc.rows(points)), dtype=float)


_CACHE: "OrderedDict[str, Fitted]" = OrderedDict()
_LOCK = threading.Lock()
_KEEP = 8


def remember(key: str, f: Fitted) -> None:
    with _LOCK:
        _CACHE[key] = f
        _CACHE.move_to_end(key)
        while len(_CACHE) > _KEEP:
            _CACHE.popitem(last=False)


def recall(key: str) -> Fitted:
    with _LOCK:
        f = _CACHE.get(key)
    if f is None:
        raise SurrogateError("The model is no longer kept: train it again.")
    return f


def train(X: Dict[str, np.ndarray], y: np.ndarray, models: Sequence[str] = MODELS, folds: int = 5,
          seed: int = 0) -> Tuple[Fitted, Dict[str, Any]]:
    """Cross-validate each model, then fit it on every set. Returns (fitted, report)."""
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(y)
    for v in X.values():
        ok &= ~pd.isna(pd.Series(v)).to_numpy()
    idx = np.flatnonzero(ok)
    if len(idx) > MAX_TRAIN:
        idx = np.sort(np.random.default_rng(seed).choice(idx, MAX_TRAIN, replace=False))
    if len(idx) < 4:
        raise SurrogateError("A model needs 4 sets or more with this value.")
    X = {k: np.asarray(v)[idx] for k, v in X.items()}
    y = y[idx]
    enc = Encoder(X)
    Z = enc.matrix(X)
    n = len(y)
    nfold = n if n <= 20 else max(2, min(folds, n))
    parts = _folds(n, nfold, seed)
    table, fitted, cv_pred = [], {}, {}
    for m in models:
        row: Dict[str, Any] = {"model": m, "available": True}
        if m == "kriging" and not have_sklearn():
            row.update({"available": False, "error": "needs scikit-learn - install it with: pip install scikit-learn (or pip install \"signalviewer-lite[sweeps-opt]\")"})
            table.append(row)
            continue
        try:
            pred = np.full(n, np.nan)
            for test in parts:
                train_i = np.setdiff1d(np.arange(n), test)
                pred[test] = _fit(m, Z[train_i], y[train_i])(Z[test])
            row.update(metrics(y, pred))
            fitted[m] = _fit(m, Z, y)
            cv_pred[m] = pred
        except (np.linalg.LinAlgError, ValueError, SurrogateError) as e:
            row.update({"available": False, "error": str(e)[:200]})
        table.append(row)
    scored = [r for r in table if r.get("r2") is not None]
    best = max(scored, key=lambda r: r["r2"])["model"] if scored else None
    report = {"n": n, "folds": nfold, "table": table, "best": best,
              "predicted": {m: [[float(a), float(b)] for a, b in zip(y, p)] for m, p in cv_pred.items()},
              "params": enc.ranges()}
    return Fitted(enc, fitted, y, X), report


# ---------------------------------------------------------------------------- exploring
def grid(f: Fitted, model: str, base: Dict[str, Any], x: str, y: Optional[str] = None, steps: int = 40) -> Dict[str, Any]:
    """The model along one parameter (a cut) or over two (a surface), the others at ``base``."""
    def axis(name: str) -> List[Any]:
        if name in f.enc.num:
            _, _, lo, hi = f.enc.num[name]
            return [float(v) for v in np.linspace(lo, hi, steps)]
        if name in f.enc.cat:
            return list(f.enc.cat[name])
        raise SurrogateError(f"{name} is not a parameter of the model")
    xs = axis(x)
    if y is None:
        pts = [{**base, x: a} for a in xs]
        return {"x": x, "xs": xs, "z": [_num(v) for v in f.predict(model, pts)]}
    ys = axis(y)
    pts = [{**base, x: a, y: b} for b in ys for a in xs]
    z = f.predict(model, pts).reshape(len(ys), len(xs))
    return {"x": x, "y": y, "xs": xs, "ys": ys, "z": [[_num(v) for v in row] for row in z]}


def _num(v: float) -> Optional[float]:
    return float(v) if math.isfinite(v) else None


def optimise(f: Fitted, model: str, direction: str, n: int = 10, seed: int = 0,
             constraints: Sequence[Tuple[Fitted, str, float]] = (), pool: int = 4000) -> List[Dict[str, Any]]:
    """The ``n`` best sets the model predicts (distinct; numbers refined locally), meeting the
    constraints' models (``(fitted, op, value)``, each its own model of a condition's worst case).
    Each: {params, predicted, meets}."""
    names = f.enc.names
    nums = [k for k in names if k in f.enc.num]
    cats = [k for k in names if k in f.enc.cat]
    sign = -1.0 if direction == "max" else 1.0
    rng = np.random.default_rng(seed)
    u = qmc.LatinHypercube(d=max(1, len(nums)), seed=seed).random(pool)
    pts: List[Dict[str, Any]] = []
    for i in range(pool):
        p: Dict[str, Any] = {}
        for j, k in enumerate(nums):
            _, _, lo, hi = f.enc.num[k]
            p[k] = lo + u[i, j] * (hi - lo)
        for k in cats:
            p[k] = f.enc.cat[k][int(rng.integers(len(f.enc.cat[k])))]
        pts.append(p)

    def meets(ps: List[Dict[str, Any]]) -> np.ndarray:
        ok = np.ones(len(ps), dtype=bool)
        for cf, op, val in constraints:
            ok &= _OPS[op](cf.predict(model if model in cf.models else next(iter(cf.models)), ps), val)
        return ok

    val = f.predict(model, pts)
    good = meets(pts)
    order = np.argsort(np.where(good, sign * val, np.inf))
    out: List[Dict[str, Any]] = []
    for i in order[: max(n * 3, 10)]:
        p = dict(pts[int(i)])
        if nums and model != "knn":                           # a local step: L-BFGS-B in the box
            x0 = np.array([p[k] for k in nums], dtype=float)
            bounds = [(f.enc.num[k][2], f.enc.num[k][3]) for k in nums]

            def obj(x: np.ndarray, base: Dict[str, Any] = p) -> float:
                q = {**base, **{k: float(v) for k, v in zip(nums, x)}}
                pen = 0.0 if meets([q])[0] else 1e6
                return float(sign * f.predict(model, [q])[0] + pen)
            try:
                r = minimize(obj, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 40})
                if r.fun < obj(x0):
                    p.update({k: float(v) for k, v in zip(nums, r.x)})
            except (ValueError, np.linalg.LinAlgError):
                pass
        for k in nums:
            p[k] = float(f"{p[k]:.6g}")
        key = tuple(str(p[k]) for k in names)
        if any(tuple(str(o["params"][k]) for k in names) == key for o in out):
            continue
        out.append({"params": p, "predicted": _num(float(f.predict(model, [p])[0])), "meets": bool(meets([p])[0])})
        if len(out) >= n:
            break
    out.sort(key=lambda o: (not o["meets"], sign * (o["predicted"] if o["predicted"] is not None else np.inf)))
    return out
