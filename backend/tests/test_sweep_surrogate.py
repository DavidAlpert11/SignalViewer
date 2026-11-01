"""MF04: response surfaces on analytic functions - validation (R² thresholds), the best model,
predictions on a grid, virtual optimisation (finds the known optimum, respects a constraint)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.sweep import surrogate as M  # noqa: E402


def _branin_like(n=60, seed=0):
    rng = np.random.default_rng(seed)
    a, b = rng.uniform(-2, 2, n), rng.uniform(-2, 2, n)
    return {"a": a, "b": b}, (a - 0.5) ** 2 + 2 * (b + 1) ** 2 + 0.5 * a * b


def test_quadratic_is_learned_and_poly_is_best():
    X, y = _branin_like()
    f, rep = M.train(X, y, models=("poly", "rbf", "knn"))
    t = {r["model"]: r for r in rep["table"]}
    assert t["poly"]["r2"] > 0.999 and t["rbf"]["r2"] > 0.95 and t["knn"]["r2"] > 0.6
    assert rep["best"] == "poly" and rep["folds"] == 5
    assert len(rep["predicted"]["poly"]) == 60
    p = f.predict("poly", [{"a": 0.5, "b": -1.0}])[0]
    assert p == pytest.approx(0.5 * 0.5 * -1, abs=1e-3)


def test_sine_needs_a_flexible_model():
    rng = np.random.default_rng(2)
    x = rng.uniform(0, 2 * np.pi, 80)
    f, rep = M.train({"x": x}, np.sin(2 * x), models=("poly", "rbf"))
    t = {r["model"]: r for r in rep["table"]}
    assert t["rbf"]["r2"] > 0.98 and t["poly"]["r2"] < 0.5 and rep["best"] == "rbf"


def test_kriging_when_installed():
    pytest.importorskip("sklearn")
    X, y = _branin_like(40)
    _, rep = M.train(X, y, models=("kriging",))
    assert rep["table"][0]["r2"] > 0.98


def test_kriging_missing_says_what(monkeypatch):
    monkeypatch.setattr(M, "have_sklearn", lambda: False)
    X, y = _branin_like(30)
    _, rep = M.train(X, y, models=("poly", "kriging"))
    k = [r for r in rep["table"] if r["model"] == "kriging"][0]
    assert not k["available"] and "sweeps-opt" in k["error"] and rep["best"] == "poly"


def test_categorical_and_grid():
    rng = np.random.default_rng(3)
    mode = rng.choice(["eco", "fast"], 60)
    x = rng.uniform(0, 1, 60)
    y = np.where(mode == "fast", 2.0, 0.0) + x ** 2
    f, rep = M.train({"mode": mode, "x": x}, y, models=("poly",))
    assert rep["table"][0]["r2"] > 0.99
    g = M.grid(f, "poly", {"mode": "eco", "x": 0.5}, "x", steps=11)
    assert len(g["z"]) == 11 and g["z"][-1] == pytest.approx(x.max() ** 2, abs=0.02)
    s = M.grid(f, "poly", {"mode": "eco", "x": 0.5}, "x", "mode", steps=5)
    assert len(s["z"]) == 2 and s["ys"] == ["eco", "fast"]


def test_virtual_optimum_and_constraint():
    X, y = _branin_like(80)
    f, _ = M.train(X, y, models=("poly",))
    best = M.optimise(f, "poly", "min", n=3)
    # the minimum of (a-.5)^2 + 2(b+1)^2 + .5ab: grad = 0 -> a = 0.8, b = -1.1 (approximately)
    p = best[0]["params"]
    assert p["a"] == pytest.approx(0.8, abs=0.05) and p["b"] == pytest.approx(-1.1, abs=0.05)
    assert best[0]["meets"] and best[0]["predicted"] == pytest.approx(min(y), abs=0.5) or best[0]["predicted"] <= min(y) + 1e-6
    # constraint: a >= 1.5 (a model of `a` itself)
    fa, _ = M.train(X, X["a"], models=("poly",))
    c = M.optimise(f, "poly", "min", n=2, constraints=[(fa, ">=", 1.5)])
    assert c[0]["meets"] and c[0]["params"]["a"] >= 1.49


def test_too_few_sets():
    with pytest.raises(M.SurrogateError):
        M.train({"a": np.arange(3.0)}, np.arange(3.0))


def test_endpoints(tmp_path):
    import pandas as pd
    from fastapi.testclient import TestClient
    from app.main import app
    rows = [{"a": a, "b": b, "sc": s, "out": -(a - 0.3) ** 2 - (b - 0.6) ** 2 + (0.01 if s == "y" else 0), "risk": a}
            for a in np.linspace(0, 1, 7) for b in np.linspace(0, 1, 7) for s in ("x", "y")]
    path = tmp_path / "t.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(path)}).json()["id"]
    q = {"roles": {"a": "param", "b": "param", "sc": "hold", "out": "output", "risk": "output"},
         "goal": {"column": "out", "direction": "max"}, "conditions": [{"column": "risk", "op": "<=", "value": 0.2, "mode": "all"}]}
    r = c.post("/api/sweep/surrogate/train", json={"id": tid, "question": q, "models": ["poly", "rbf"]}).json()
    assert r["n"] == 49 and r["best"] in ("poly", "rbf") and r["table"][0]["r2"] > 0.99
    g = c.post("/api/sweep/surrogate/grid", json={"key": r["key"], "model": "poly", "base": {"a": 0.5, "b": 0.5}, "x": "a", "y": "b", "steps": 9}).json()
    assert len(g["z"]) == 9 and len(g["z"][0]) == 9
    o = c.post("/api/sweep/surrogate/optimise", json={"id": tid, "question": q, "model": "poly", "direction": "max", "n": 3}).json()
    best = o["sets"][0]
    assert best["meets"] and best["params"]["a"] <= 0.21 and best["params"]["b"] == pytest.approx(0.6, abs=0.05)
    assert c.post("/api/sweep/surrogate/grid", json={"key": "gone", "model": "poly", "base": {}, "x": "a"}).status_code == 400
