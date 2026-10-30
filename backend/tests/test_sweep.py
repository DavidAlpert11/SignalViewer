"""Sweeps area (svcore/sweep.py, app/routes/sweep.py): reading, describing and guessing roles of a
results table - parameters and scenario columns first, outputs last."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore import sweep  # noqa: E402
import svcore.sweep.io  # noqa: E402,F401

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "sweeps", "sweep_payload.csv")


def _table(n_sets_rep=1):
    rows = []
    for rep in range(n_sets_rep):
        for sc in ("a", "b", "c"):
            for p in (1.0, 2.0, 3.0):
                for k in (0.1, 0.2):
                    rows.append({"scenario": sc, "p": p, "k": k, "out": p * 10 + k + np.random.rand(), "ver": "1", "ok": int(p < 3)})
    return pd.DataFrame(rows)


def test_roles_mixed_inputs_then_outputs():
    df = _table()
    cols = {c["name"]: c for c in sweep.describe(df)}
    assert cols["scenario"]["role"] == "hold"
    assert cols["p"]["role"] == "param" and cols["k"]["role"] == "param"
    assert cols["out"]["role"] == "output"
    assert cols["ok"]["role"] == "output"           # after the first output: an output, though it has 2 values
    assert cols["ver"]["role"] == "ignore" and cols["ver"]["constant"]
    assert cols["scenario"]["scale"] == "category"


def test_example_table_guess_and_summary():
    df = sweep.read_table(EXAMPLE)
    cols = sweep.describe(df)
    roles = {c["name"]: c["role"] for c in cols}
    assert [c for c, r in roles.items() if r == "hold"] == ["scenario_terrain", "scenario_wind_mps", "scenario_mission"]
    assert [c for c, r in roles.items() if r == "param"] == ["payload_kg", "kp_roll", "cruise_mps", "controller"]
    assert roles["sim_version"] == "ignore"
    s = sweep.summary(df, roles)
    assert s["sets"] == 150 and s["combos"] == 18
    assert s["missing"] > 0 and s["complete"] + s["missing"] == 150      # the example drops a few runs
    assert s["failedRuns"] > 0                                            # and has runs with no outputs


def test_summary_missing_and_duplicates():
    df = _table()
    df = pd.concat([df.iloc[1:], df.iloc[[5]]])          # one run gone, one run twice
    roles = {"scenario": "hold", "p": "param", "k": "param", "out": "output", "ver": "ignore", "ok": "output"}
    s = sweep.summary(df, roles)
    assert s["sets"] == 6 and s["combos"] == 3
    assert s["missing"] == 1 and s["duplicates"] == 1


def test_big_csv_is_cached_as_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(sweep.io, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(sweep.io, "CACHE_MIN_BYTES", 0)
    f = tmp_path / "t.csv"
    _table(5).to_csv(f, index=False)
    a = sweep.read_table(str(f))
    assert len(os.listdir(tmp_path / "cache")) == 1
    b = sweep.read_table(str(f))                         # from the copy
    assert a.shape == b.shape and list(a.columns) == list(b.columns)
    os.utime(f, (1, 1))                                  # the file changed: a new copy, not the old one
    sweep.read_table(str(f))
    assert len(os.listdir(tmp_path / "cache")) == 2


def test_routes_open_and_summary():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    p = c.get("/api/sweep/example").json()["path"]
    r = c.post("/api/sweep/open", json={"path": p}).json()
    assert r["rows"] > 2000 and len(r["head"]) == 20 and r["summary"]["sets"] == 150
    roles = {col["name"]: col["role"] for col in r["columns"]}
    roles["controller"] = "hold"                         # the user moves a column
    s = c.post("/api/sweep/summary", json={"id": r["id"], "roles": roles}).json()
    assert s["combos"] == 36 and s["sets"] == 75
    assert c.post("/api/sweep/open", json={"path": "/no/such.csv"}).status_code == 400


# ----------------------------------------------------------------------------- the question
def _grid():
    """2 params (p: 1,2,3 ; k: 0.1,0.2) x scenario a,b,c. out = 10p - (scenario c: 5)."""
    rows = []
    for sc in ("a", "b", "c"):
        for p in (1.0, 2.0, 3.0):
            for k in (0.1, 0.2):
                rows.append({"scenario": sc, "p": p, "k": k, "out": 10 * p - (5 if sc == "c" else 0) + k, "risk": p * (2 if sc == "b" else 1)})
    return pd.DataFrame(rows)


ROLES = {"scenario": "hold", "p": "param", "k": "param", "out": "output", "risk": "output"}


def _ans(df, **q):
    q = {"roles": ROLES, **q}
    p = sweep.prepare(df, q)
    return p, sweep.answer(p, q)


def test_condition_in_every_combination_and_worst_case():
    p, a = _ans(_grid(), conditions=[{"column": "risk", "op": "<=", "value": 3}], goal={"column": "out", "direction": "max"})
    d = a["data"]
    # risk worst = 2p (scenario b): holds only for p = 1
    assert a["counts"]["holding"] == 2
    assert set(d["p"][d["#holds"] == 1]) == {1.0}
    assert np.allclose(d["#c0.worst"][d["p"] == 2.0], 4.0) and np.allclose(d["#c0.margin"][d["p"] == 2.0], -1.0)
    # goal: worst of out over scenarios = 10p - 5 + k, ranked among the holding sets only
    best = np.nanargmin(d["#rank"])
    assert d["k"][best] == 0.2 and np.isclose(d["#goal"][best], 5.2)


def test_condition_at_least_and_only_some_scenarios():
    # risk <= 2.5: p = 1 in all three, p = 2 in a and c only, p = 3 in none
    _, a = _ans(_grid(), conditions=[{"column": "risk", "op": "<=", "value": 2.5, "mode": "atLeast", "k": 2}])
    assert a["counts"]["holding"] == 4
    _, a = _ans(_grid(), conditions=[{"column": "risk", "op": "<=", "value": 2.5, "mode": "only", "where": {"scenario": ["a", "c"]}}])
    assert a["counts"]["holding"] == 4


def test_kept_values_and_new_columns():
    _, a = _ans(_grid(), holdValues={"scenario": ["a", "b"]},
                derived=[{"name": "out2", "kind": "row", "expr": "out * 2"},
                         {"name": "out_c", "kind": "set", "op": "min", "column": "out", "where": {"scenario": ["a"]}}],
                conditions=[{"column": "out_c", "op": ">=", "value": 20}])
    assert a["counts"]["combos"] == 2 and a["counts"]["rows"] == 12
    names = [m["name"] for m in a["columns"]]
    assert "out2" in names and "out_c" in names
    assert a["counts"]["holding"] == 4                      # out in a = 10p + k >= 20: p = 2, 3


def test_a_missing_run_or_empty_output_cannot_hold():
    df = _grid()
    df = df.drop(index=0)                                   # set (p=1, k=0.1) misses scenario a
    df.loc[5, "risk"] = np.nan                              # and another run gave no result
    _, a = _ans(df, conditions=[{"column": "risk", "op": "<=", "value": 100}])
    assert a["counts"]["holding"] == 4 and a["counts"]["complete"] == 5


def test_why_a_set_fails_and_rerun_list(tmp_path):
    q = {"roles": ROLES, "conditions": [{"column": "risk", "op": "<=", "value": 3}]}
    p = sweep.prepare(_grid(), q)
    a = sweep.answer(p, q)
    s3 = int(np.where(a["data"]["p"] == 3.0)[0][0])
    r = sweep.set_rows(p, q, s3)
    assert r["why"][0]["broken"] == 1 and r["why"][0]["worst"] == 6.0 and r["why"][0]["where"] == {"scenario": "b"}
    rows = sweep.rerun_rows(p, [s3])
    assert len(rows) == 3 and rows[0]["p"] == 3.0
    sweep.write_csv(str(tmp_path / "r.csv"), rows, ["p", "k", "scenario"])
    assert (tmp_path / "r.csv").read_text().splitlines()[0] == "p,k,scenario"


def test_formula_is_safe():
    df = _grid()
    from svcore.sweep.derived import row_formula
    assert np.allclose(row_formula(df, "abs(out - 20) + col('p')"), np.abs(df.out - 20) + df.p)
    for bad in ("__import__('os')", "out.__class__", "[1][0]", "scenario * 2"):
        with pytest.raises(sweep.DerivedError):
            row_formula(df, bad)


def test_route_evaluate_with_runs():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/sweep/open", json={"path": c.get("/api/sweep/example").json()["path"]}).json()
    roles = {col["name"]: col["role"] for col in r["columns"]}
    q = {"roles": roles, "goal": {"column": "range_m"}, "conditions": [{"column": "max_roll_deg", "op": "<=", "value": 25}]}
    e = c.post("/api/sweep/evaluate", json={"id": r["id"], "question": q, "runs": True}).json()
    assert e["counts"]["sets"] == 150 and e["counts"]["holding"] > 0
    assert e["runs"]["n"] == e["runs"]["total"] > 2000
    assert {m["name"] for m in e["sets"]} >= {"#holds", "#goal", "#rank", "payload_kg", "range_m"}
    bad = c.post("/api/sweep/evaluate", json={"id": r["id"], "question": {**q, "goal": {"column": "nope"}}})
    assert bad.status_code == 400
