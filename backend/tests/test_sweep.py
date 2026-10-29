"""Sweeps area (svcore/sweep.py, app/routes/sweep.py): reading, describing and guessing roles of a
results table - parameters and scenario columns first, outputs last."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore import sweep  # noqa: E402

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
    monkeypatch.setattr(sweep, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(sweep, "CACHE_MIN_BYTES", 0)
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
