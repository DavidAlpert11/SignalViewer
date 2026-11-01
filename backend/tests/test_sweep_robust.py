"""MF08: sampling around a set and its statistics, against known answers."""
import numpy as np
import pytest

from svcore.sweep import robust


def _col(pts, k):
    return np.array([p[k] for p in pts])


def test_uniform_band_and_untouched_parameters():
    pts = robust.sample({"x": 10.0, "m": "a", "z": 3}, {"x": {"mode": "pct", "value": 10}}, 1000)
    x = _col(pts, "x")
    assert x.min() >= 9 - 1e-9 and x.max() <= 11 + 1e-9
    assert x.mean() == pytest.approx(10, abs=0.01)
    # LHS: one sample in each of 1000 strata -> the variance of U(9, 11) = 4 / 12 almost exactly
    assert x.var() == pytest.approx(4 / 12, rel=0.01)
    assert all(p["m"] == "a" and p["z"] == 3 for p in pts)


def test_normal_is_two_sigma_band_and_triangular_mean():
    pts = robust.sample({"x": 5.0}, {"x": {"mode": "abs", "value": 1, "dist": "normal"}}, 4000)
    x = _col(pts, "x")
    assert x.mean() == pytest.approx(5, abs=0.01)
    assert x.std() == pytest.approx(0.5, rel=0.02)
    pts = robust.sample({"x": 0.0}, {"x": {"mode": "abs", "value": 2, "dist": "triangular"}}, 4000)
    x = _col(pts, "x")
    # symmetric triangle on -2..2: variance = (a^2 + b^2 + c^2 - ab - ac - bc) / 18 = 12 / 18
    assert x.var() == pytest.approx(12 / 18, rel=0.02)


def test_steps_use_the_tables_median_step_and_monte_carlo():
    d = robust.half_width({"mode": "steps", "value": 2}, 0.3, [0.1, 0.2, 0.3, 0.4, 0.6])
    assert d == pytest.approx(0.2)
    pts = robust.sample({"x": 1.0}, {"x": {"mode": "abs", "value": 1}}, 500, method="mc", seed=1)
    assert len(pts) == 500 and _col(pts, "x").min() >= 0


def test_statistics_by_hand():
    s = robust.statistics([1, 2, 3, 4, float("nan")], "max", 75, {"op": ">=", "value": 2})
    assert s["mean"] == pytest.approx(2.5)
    assert s["std"] == pytest.approx(np.std([1, 2, 3, 4], ddof=1))
    assert s["pct"] == pytest.approx(np.percentile([1, 2, 3, 4], 25))     # the bad side when maximizing
    assert s["pFail"] == pytest.approx(2 / 5)                             # 1 and the missing one
    assert robust.statistics([1, 2, 3, 4], "min", 75)["pct"] == pytest.approx(np.percentile([1, 2, 3, 4], 75))


def test_on_a_linear_model_mean_and_sigma_are_exact():
    # y = 2x + 1 with x ~ U(c - 1, c + 1): mean 2c + 1, sigma 2 / sqrt(3)
    f = lambda pts: np.array([2 * p["x"] + 1 for p in pts])
    r = robust.on_model(f, [{"x": 0.0}, {"x": 3.0}], {"x": {"mode": "abs", "value": 1}}, n=2000,
                        limit={"op": ">=", "value": 7})
    assert r[0]["mean"] == pytest.approx(1, abs=0.01) and r[1]["mean"] == pytest.approx(7, abs=0.01)
    assert r[1]["std"] == pytest.approx(2 / np.sqrt(3), rel=0.01)
    assert r[1]["pFail"] == pytest.approx(0.5, abs=0.01) and r[0]["pFail"] == 1.0
    assert r[1]["nominal"] == pytest.approx(7)


def test_errors():
    with pytest.raises(robust.RobustError):
        robust.sample({"x": 1.0}, {}, 10)
    with pytest.raises(robust.RobustError):
        robust.sample({"x": 1.0}, {"x": {"mode": "abs", "value": 1, "dist": "cauchy"}}, 10)
    with pytest.raises(robust.RobustError):
        robust.sample({"x": 1.0}, {"x": {"mode": "abs", "value": 1}}, 10, method="sobol")


def test_endpoints(tmp_path):
    """A linear result out = 2a + b: on the model, the spread follows a's tolerance; the samples to run;
    a group's statistics."""
    import pandas as pd
    from fastapi.testclient import TestClient
    from app.main import app
    rows = [{"a": a, "b": b, "out": 2 * a + b} for a in np.linspace(0, 1, 6) for b in np.linspace(0, 1, 6)]
    path = tmp_path / "t.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(path)}).json()["id"]
    q = {"roles": {"a": "param", "b": "param", "out": "output"}, "goal": {"column": "out", "direction": "max"}}
    assert c.post("/api/sweep/robust/sample", json={"id": tid, "question": q, "centre": {"a": 0.5, "b": 0.5}}).status_code == 400
    q["robust"] = {"a": {"mode": "abs", "value": 0.1, "dist": "uniform"}}
    s = c.post("/api/sweep/robust/sample", json={"id": tid, "question": q, "centre": {"a": 0.5, "b": 0.5}, "n": 20}).json()
    assert len(s["sets"]) == 20 and all(0.4 - 1e-9 <= x["a"] <= 0.6 + 1e-9 and x["b"] == 0.5 for x in s["sets"])
    key = c.post("/api/sweep/surrogate/train", json={"id": tid, "question": q, "models": ["poly"]}).json()["key"]
    r = c.post("/api/sweep/robust/model", json={"id": tid, "question": q, "key": key, "model": "poly", "n": 1000,
                                                "centres": [{"a": 0.5, "b": 0.5}], "limit": {"op": ">=", "value": 1.5}}).json()
    row = r["rows"][0]
    assert row["mean"] == pytest.approx(1.5, abs=1e-3) and row["std"] == pytest.approx(0.2 / np.sqrt(3), rel=0.02)
    assert row["pFail"] == pytest.approx(0.5, abs=0.01)
    st = c.post("/api/sweep/robust/stats", json={"id": tid, "question": q, "sets": [0, 1, 2]}).json()
    assert st["n"] == 3 and st["mean"] is not None
