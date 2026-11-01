"""MF05: sensitivity on the sets - against known answers (Ishigami's Sobol indices, an additive
function's shares, a pure interaction)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.sweep import sensitivity as S  # noqa: E402

# Ishigami (a=7, b=0.1) on [-pi, pi]^3: analytic first-order and total indices
S1 = {"x1": 0.3139, "x2": 0.4424, "x3": 0.0}
ST = {"x1": 0.5576, "x2": 0.4424, "x3": 0.2437}


def _ishigami_grid(m=12):
    g = -np.pi + (np.arange(m) + 0.5) * 2 * np.pi / m          # midpoints: the grid's quadrature
    x1, x2, x3 = (a.ravel() for a in np.meshgrid(g, g, g, indexing="ij"))
    y = np.sin(x1) + 7 * np.sin(x2) ** 2 + 0.1 * x3 ** 4 * np.sin(x1)
    return {"x1": x1, "x2": x2, "x3": x3}, y


def test_ishigami_sobol_on_a_grid():
    X, y = _ishigami_grid()
    r = S.analyse(X, y, max_levels=12)
    got = {p["name"]: p for p in r["params"]}
    for k in S1:
        assert got[k]["first"] == pytest.approx(S1[k], abs=0.02), k
        assert got[k]["total"] == pytest.approx(ST[k], abs=0.03), k
    # x1 and x3 interact (0.2437), x3 alone does nothing
    top = r["pairs"][0]
    assert {top["a"], top["b"]} == {"x1", "x3"} and top["share"] == pytest.approx(0.2437, abs=0.03)
    assert got["x3"]["main"] < 0.01 and not got["x3"]["weak"]          # weak = main + interactions


def test_additive_shares_and_weak_parameter():
    rng = np.random.default_rng(0)
    a, b, c = (np.repeat(np.arange(5.0), 1) for _ in range(3))
    A, B, C = (v.ravel() for v in np.meshgrid(a, b, c, indexing="ij"))
    y = 3 * A + B + 0.001 * C + rng.normal(0, 1e-6, A.size)
    r = S.analyse({"A": A, "B": B, "C": C}, y)
    got = {p["name"]: p for p in r["params"]}
    assert got["A"]["main"] == pytest.approx(0.9, abs=1e-3) and got["B"]["main"] == pytest.approx(0.1, abs=1e-3)
    assert got["C"]["weak"] and not got["A"]["weak"]
    assert r["params"][0]["name"] == "A"
    assert got["A"]["pearson"] == pytest.approx(0.9487, abs=1e-3)       # sqrt(0.9)
    assert r["rest"] == pytest.approx(0, abs=1e-3)


def test_categorical_and_scattered_sets():
    rng = np.random.default_rng(1)
    mode = rng.choice(["eco", "fast", "safe"], 300)
    x = rng.uniform(0, 1, 300)
    y = np.where(mode == "fast", 5.0, 0.0) + x
    r = S.analyse({"mode": mode, "x": x}, y)
    got = {p["name"]: p for p in r["params"]}
    assert got["mode"]["main"] > 0.8 and got["mode"]["levels"] == 3
    assert got["x"]["levels"] == S.MAX_LEVELS                          # binned
    assert got["mode"]["total"] == pytest.approx(got["mode"]["main"], abs=0.05)   # x binned: its bins repeat
    # three scattered parameters, few sets: the others' (binned) combinations do not repeat - no total
    X = {k: rng.uniform(0, 1, 50) for k in ("a", "b", "c")}
    r2 = S.analyse(X, X["a"] + X["b"] * X["c"])
    assert all(p["total"] is None for p in r2["params"])


def test_flat_or_tiny():
    assert S.analyse({"a": np.arange(5.0)}, np.ones(5))["flat"]
    assert S.analyse({"a": np.arange(2.0)}, np.arange(2.0))["flat"]


def test_on_a_prepared_table_and_a_group():
    from svcore import sweep
    rows = [{"p": p, "k": k, "sc": s, "out": 10 * p + k} for p in (1.0, 2.0, 3.0) for k in (0.1, 0.2) for s in ("a", "b")]
    df = pd.DataFrame(rows)
    q = {"roles": {"p": "param", "k": "param", "sc": "hold", "out": "output"}, "goal": {"column": "out", "direction": "max"}}
    pr = sweep.prepare(df, q)
    a = sweep.answer(pr, q)
    r = S.for_sets(pr, a["data"]["#goal"])
    assert r["params"][0]["name"] == "p" and r["n"] == 6
    assert S.for_sets(pr, a["data"]["#goal"], sets=[0, 1, 2])["n"] == 3


def test_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    rows = [{"p": p, "k": k, "sc": s, "out": 10 * p + k} for p in (1.0, 2.0, 3.0) for k in (0.1, 0.2) for s in ("a", "b")]
    path = tmp_path / "t.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(path)}).json()["id"]
    q = {"roles": {"p": "param", "k": "param", "sc": "hold", "out": "output"}, "goal": {"column": "out", "direction": "max"}}
    r = c.post("/api/sweep/sensitivity", json={"id": tid, "question": q}).json()
    assert r["params"][0]["name"] == "p" and r["params"][1]["weak"]
    assert c.post("/api/sweep/sensitivity", json={"id": tid, "question": q, "column": "nope"}).status_code == 400
