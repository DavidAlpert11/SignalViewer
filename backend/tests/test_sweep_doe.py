"""MF03: designs of experiments - counts, bounds, kinds, discrepancy, the classic designs' points,
filling the gaps."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.sweep import doe as D  # noqa: E402

SP = [{"name": "kp", "kind": "continuous", "lo": 0.1, "hi": 0.5},
      {"name": "n", "kind": "integer", "lo": 1, "hi": 8},
      {"name": "mode", "kind": "categorical", "levels": ["eco", "fast"]},
      {"name": "ver", "kind": "fixed", "value": 3}]
NUM = [{"name": f"x{i}", "kind": "continuous", "lo": 0, "hi": 1} for i in range(3)]


def _inside(sets):
    for p in sets:
        assert 0.1 <= p["kp"] <= 0.5 and isinstance(p["n"], int) and 1 <= p["n"] <= 8
        assert p["mode"] in ("eco", "fast") and p["ver"] == 3


@pytest.mark.parametrize("m", ["space", "sobol", "random"])
def test_samples_count_bounds_kinds(m):
    r = D.design(SP, m, 32, seed=1)
    assert r["n"] >= 28                      # integers / levels may meet: duplicates are dropped
    _inside(r["sets"])
    assert all(p["kp"] == float(f"{p['kp']:.6g}") for p in r["sets"])     # 6 digits: ids round-trip


def test_space_filling_beats_random_on_discrepancy():
    sf = D.design(NUM, "space", 64, seed=3)["discrepancy"]
    rnd = np.mean([D.design(NUM, "random", 64, seed=s)["discrepancy"] for s in range(5)])
    assert sf < rnd


def test_factorial_box_behnken_ccd_counts():
    f = D.design(SP, "factorial", levels=3)
    assert f["n"] == 3 * 3 * 2                # kp 3 levels, n 3 levels, mode 2
    assert {p["kp"] for p in f["sets"]} == {0.1, 0.3, 0.5}
    assert D.design(NUM, "boxbehnken")["n"] == 3 * 4 + 1          # 12 edge points + centre (3 centres, one kept)
    c = D.design(NUM, "ccd")
    assert c["n"] == 8 + 6 + 1
    assert all(0 <= p["x0"] <= 1 for p in c["sets"])               # face-centred: inside
    with pytest.raises(D.DoeError):
        D.design(NUM[:2], "boxbehnken")
    with pytest.raises(D.DoeError):
        D.design(SP, "ccd")                                         # categorical


def test_fill_the_gaps_goes_where_nothing_ran():
    existing = [{"x0": a, "x1": b} for a in (0.0, 0.1, 0.2) for b in (0.0, 0.1, 0.2)]   # a corner
    sp = NUM[:2]
    r = D.design(sp, "fill", 5, existing=existing)
    far = [max(p["x0"], p["x1"]) for p in r["sets"]]
    assert min(far) > 0.3 and r["min_distance"] > 0.2


def test_bad_specs():
    for bad in ([{"name": "a", "kind": "continuous", "lo": 2, "hi": 1}], [{"name": "a", "kind": "x"}],
                [{"name": "a", "kind": "categorical", "levels": []}], [{"name": "a", "kind": "fixed", "value": 1}]):
        with pytest.raises(D.DoeError):
            D.design(bad, "space", 5)
    with pytest.raises(D.DoeError):
        D.design(NUM, "nope", 5)
    with pytest.raises(D.DoeError):
        D.design([{"name": f"x{i}", "kind": "integer", "lo": 0, "hi": 99} for i in range(4)], "factorial", levels=20)


def test_endpoint_fill(tmp_path):
    import pandas as pd
    from fastapi.testclient import TestClient
    from app.main import app
    rows = [{"a": a, "b": b, "out": a + b} for a in (0.0, 0.1) for b in (0.0, 0.1)]
    path = tmp_path / "t.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(path)}).json()["id"]
    q = {"roles": {"a": "param", "b": "param", "out": "output"}}
    specs = [{"name": "a", "kind": "continuous", "lo": 0, "hi": 1}, {"name": "b", "kind": "continuous", "lo": 0, "hi": 1}]
    r = c.post("/api/sweep/doe", json={"id": tid, "question": q, "params": specs, "method": "fill", "n": 3}).json()
    assert r["n"] == 3 and all(max(p["a"], p["b"]) > 0.3 for p in r["sets"])
    assert c.post("/api/sweep/doe", json={"id": tid, "question": q, "params": specs, "method": "x"}).status_code == 400
