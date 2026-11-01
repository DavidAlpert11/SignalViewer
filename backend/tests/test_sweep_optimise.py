"""MF07: the optimisers against known answers - sphere / Rosenbrock (one objective), ZDT1's Pareto
front (two), a constraint, the automatic choice, the loop through the runner."""
import os
import sys
import time

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.sweep import optimise as O  # noqa: E402


def _specs(d, lo=-2.0, hi=2.0):
    return [{"name": f"x{i}", "kind": "continuous", "lo": lo, "hi": hi} for i in range(d)]


def _eval_with(fn):
    def ev(sets, gen):
        return [[{**p, **fn(p), "run_status": "ok"}] for p in sets]
    return ev


def test_choose():
    assert O.choose("auto", 2, 5, 1000) == "nsga2"
    assert O.choose("auto", 1, 4, 40) == "surrogate" and O.choose("auto", 1, 4, 400) == "de"
    with pytest.raises(O.OptimiseError):
        O.choose("de", 2, 3, 100)


@pytest.mark.parametrize("method,budget,tol", [("de", 1500, 0.05), ("surrogate", 60, 0.1)])
def test_one_objective(method, budget, tol):
    opt = O.Optimiser(_specs(3), 1, method, pop=20 if method == "de" else 10, seed=1)
    f = lambda p: {"y": sum((p[f"x{i}"] - 0.5) ** 2 for i in range(3))}
    r = O.run_loop(opt, _eval_with(f), [{"column": "y", "direction": "min"}], [], budget)
    best = r["best"][0]
    assert best["objectives"][0] < tol and r["sets"] == budget
    assert all(abs(best["params"][f"x{i}"] - 0.5) < 0.3 for i in range(3))


def test_rosenbrock_maximise_negated():
    opt = O.Optimiser(_specs(2), 1, "de", pop=30, seed=2)
    f = lambda p: {"y": -((1 - p["x0"]) ** 2 + 100 * (p["x1"] - p["x0"] ** 2) ** 2)}
    r = O.run_loop(opt, _eval_with(f), [{"column": "y", "direction": "max"}], [], 3000)
    assert r["best"][0]["objectives"][0] > -0.05


def test_zdt1_front():
    d = 6
    opt = O.Optimiser(_specs(d, 0.0, 1.0), 2, "nsga2", pop=60, seed=3)

    def zdt1(p):
        x = np.array([p[f"x{i}"] for i in range(d)])
        g = 1 + 9 * x[1:].sum() / (d - 1)
        return {"f1": x[0], "f2": g * (1 - np.sqrt(x[0] / g))}
    r = O.run_loop(opt, _eval_with(zdt1), [{"column": "f1", "direction": "min"}, {"column": "f2", "direction": "min"}], [], 60 * 150)
    F = np.array([b["objectives"] for b in r["best"]])
    assert len(F) >= 30
    err = np.abs(F[:, 1] - (1 - np.sqrt(F[:, 0])))
    assert np.median(err) < 0.05 and F[:, 0].max() - F[:, 0].min() > 0.7       # near the front, spread along it


def test_constraint_respected():
    opt = O.Optimiser(_specs(2), 1, "de", pop=20, seed=4)
    f = lambda p: {"y": p["x0"] ** 2 + p["x1"] ** 2, "c": p["x0"] + p["x1"]}
    r = O.run_loop(opt, _eval_with(f), [{"column": "y", "direction": "min"}], [{"column": "c", "op": ">=", "value": 1.0}], 1200)
    b = r["best"][0]["params"]
    assert b["x0"] + b["x1"] >= 0.99 and r["best"][0]["objectives"][0] == pytest.approx(0.5, abs=0.05)


def test_failed_runs_are_worst():
    opt = O.Optimiser(_specs(1), 1, "de", pop=6, seed=5)
    def ev(sets, gen):
        return [[{**p, "y": (p["x0"] if p["x0"] > 0 else None), "run_status": "ok" if p["x0"] > 0 else "error"}] for p in sets]
    r = O.run_loop(opt, ev, [{"column": "y", "direction": "min"}], [], 60)
    assert r["best"][0]["params"]["x0"] > 0


def test_categorical_and_integer():
    specs = [{"name": "mode", "kind": "categorical", "levels": ["a", "b", "c"]}, {"name": "n", "kind": "integer", "lo": 0, "hi": 10}]
    opt = O.Optimiser(specs, 1, "de", pop=12, seed=6)
    f = lambda p: {"y": (0 if p["mode"] == "b" else 5) + (p["n"] - 7) ** 2}
    r = O.run_loop(opt, _eval_with(f), [{"column": "y", "direction": "min"}], [], 400)
    assert r["best"][0]["params"] == {"mode": "b", "n": 7}


def test_through_the_runner(tmp_path):
    """The loop end to end: a script as the simulation, the optimiser's sets run, the minimum found."""
    from fastapi.testclient import TestClient
    from app.main import app
    sim = tmp_path / "sim.py"
    sim.write_text("import json,sys\na=dict(x.split('=',1) for x in sys.argv[1:])\n"
                   "kp,w=float(a['kp']),float(a['w'])\njson.dump({'err':(kp-0.3)**2+w},open(a['out'],'w'))\n")
    rows = [{"kp": k, "w": w, "err": (k - 0.3) ** 2 + w} for k in (0.0, 0.5, 1.0) for w in (0.0, 0.1)]
    path = tmp_path / "t.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(path)}).json()["id"]
    q = {"roles": {"kp": "param", "w": "hold", "err": "output"}, "goal": {"column": "err", "direction": "min"}}
    spec = {"template": f'"{sys.executable}" "{sim}" kp={{kp}} w={{w}} out={{out}}', "workdir": str(tmp_path), "parser": "json",
            "outputs": ["err"], "parallel": 4, "timeout": 20, "results": str(tmp_path / "opt.csv")}
    r = c.post("/api/sweep/optimise/start", json={"id": tid, "question": q, "specs": [{"name": "kp", "kind": "continuous", "lo": 0, "hi": 1}],
                                                  "method": "surrogate", "budget": 12, "spec": spec}).json()
    assert r["method"] == "surrogate" and r["objectives"][0]["column"] == "err"
    for _ in range(600):
        st = c.get(f"/api/sweep/run/{r['id']}").json()
        if st["job"]["state"] != "running":
            break
        time.sleep(0.1)
    assert st["job"]["state"] == "done", st["job"]
    best = st["job"]["result"]["best"][0]
    assert abs(best["params"]["kp"] - 0.3) < 0.1 and best["objectives"][0] == pytest.approx((best["params"]["kp"] - 0.3) ** 2 + 0.1, abs=1e-6)
    assert st["live"]["gen"] >= 2 and len(pd.read_csv(tmp_path / "opt.csv")) == 24
