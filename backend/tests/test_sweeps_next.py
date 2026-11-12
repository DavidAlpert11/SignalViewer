"""W15: the next runs to try (svcore/sweeps_next.py, `study next / rank / status`, /api/sweeps/next-runs) -
the toy drone model as the simulator: from a coarse grid the loop through the command line finds the optimum
of a fine grid within 4 rounds of 20 candidate values; reasons, the search space, nothing proposed twice, the
same proposal from the panel's study and from the CLI."""
import itertools
import json
import os
import shutil

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from signalviewer.study import main as study_cli
from svcore import study as S
from svcore import sweeps_common as C
from svcore import sweeps_next as N
from svcore.drone_model import simulate

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SCEN = {"A": {"wind": [0, 3, 6, 10]}, "B": {"mass": [2.0, 3.5, 5.0], "wind": [0, 5]}, "C": {"wind": [0, 4, 8], "filter_hz": [15, 30, 60]}}
CONS = {"A": "overshoot < 8", "B": "overshoot < 12 and motor_sat < 0.9", "C": "phase_margin > 45"}
FINE = {"Kp": (0.5, 0.225), "Ki": (0.0, 0.1), "Kd": (0.05, 0.1)}              # 21 values each
S_CONSTRAINT = "Kp + Kd < 7.5"


def _simulate(table, rows):
    out = []
    for r in rows:
        o = simulate(table, r["Kp"], r["Ki"], r["Kd"], wind=r["wind"], mass=r.get("mass"), filter_hz=r.get("filter_hz"))
        out.append({**r, **{k: float(v) for k, v in o.items()}})
    return pd.DataFrame(out)


def _study(folder, batch=20):
    coarse = list(itertools.product(np.linspace(0.5, 5, 4), np.linspace(0, 2, 4), np.linspace(0.05, 2.05, 4)))
    for t in "ABC":
        os.makedirs(os.path.join(folder, t))
        rows = [dict(zip(["Kp", "Ki", "Kd"], g), **dict(zip(SCEN[t], c))) for g in coarse for c in itertools.product(*SCEN[t].values())]
        _simulate(t, rows).to_csv(os.path.join(folder, t, "round_0.csv"), index=False)
    outputs = {o: "output" for o in ("overshoot", "settling_time", "motor_sat", "energy", "phase_margin")}
    study = {"version": 1, "name": "converge", "tables": [
        {"id": t, "paths": [f"{t}/*.csv"], "roles": {**{k: "scenario" for k in SCEN[t]}, **({"filter_hz": "local"} if t == "C" else {}), **outputs},
         "constraints": [CONS[t]], "objective": {"expr": "settling_time", "sense": "min"}} for t in "ABC"],
        "shared": [{"name": n} for n in FINE],
        "search": {"params": {n: {"min": lo, "max": round(lo + 20 * st, 12), "step": st} for n, (lo, st) in FINE.items()},
                   "constraints": [S_CONSTRAINT]},
        "next": {"batch": batch}}
    path = os.path.join(folder, "converge.svstudy.json")
    json.dump(study, open(path, "w"), indent=1)
    return path


def _fine_optimum():
    g = np.array(list(itertools.product(*[np.round(lo + st * np.arange(21), 12) for lo, st in FINE.values()])))
    g = g[g[:, 0] + g[:, 2] < 7.5]
    worst, ok = np.zeros(len(g)), np.ones(len(g), bool)
    for t in "AB":
        for c in itertools.product(*SCEN[t].values()):
            o = simulate(t, g[:, 0], g[:, 1], g[:, 2], **dict(zip(SCEN[t], c)))
            ok &= (o["overshoot"] < 8) if t == "A" else ((o["overshoot"] < 12) & (o["motor_sat"] < 0.9))
            worst = np.maximum(worst, o["settling_time"])
    best_c = np.full(len(g), np.inf)
    for f in (15, 30, 60):
        okf, w = np.ones(len(g), bool), np.zeros(len(g))
        for wind in (0, 4, 8):
            o = simulate("C", g[:, 0], g[:, 1], g[:, 2], wind=wind, filter_hz=f)
            okf &= o["phase_margin"] > 45
            w = np.maximum(w, o["settling_time"])
        best_c = np.where(okf, np.minimum(best_c, w), best_c)
    score = np.where(ok & np.isfinite(best_c), np.maximum(worst, best_c), np.inf)
    i = int(np.argmin(score))
    return float(score[i]), dict(zip(FINE, g[i]))


def _on_grid(v, lo, st):
    return abs((v - lo) / st - round((v - lo) / st)) < 1e-6


def test_the_loop_through_the_cli_finds_the_fine_grid_optimum_within_4_rounds(tmp_path, capsys):
    path = _study(str(tmp_path))
    opt, opt_at = _fine_optimum()
    found = None
    for k in range(1, 5):
        assert study_cli(["next", path]) == 0
        s = S.load(path)
        rnd = s.history[-1]
        assert rnd.round == k and len({tuple(sorted(p.values.items())) for p in rnd.proposals}) == len(rnd.proposals)
        for p in rnd.proposals:
            assert p.reason in ("refine", "boundary", "gap") and p.state == "pending"
            v = p.values
            assert all(_on_grid(v[n], lo, st) and lo - 1e-9 <= v[n] <= lo + 20 * st + 1e-9 for n, (lo, st) in FINE.items())
            assert v["Kp"] + v["Kd"] < 7.5                                    # the constraint on S
        cands = {(p.values["Kp"], p.values["Ki"], p.values["Kd"]) for p in rnd.proposals}
        assert len(cands) <= 20                                              # the batch counts candidate values
        for t in "ABC":                                                      # "run" the round's file
            f = os.path.join(str(tmp_path), "next", f"round_{k}", f"{t}.csv")
            rows = pd.read_csv(f)
            assert {"run_id", "reason", "round"} <= set(rows.columns)
            res = _simulate(t, rows.drop(columns=["run_id", "reason", "round"]).to_dict("records"))
            res["run_id"] = rows["run_id"]
            res.to_csv(os.path.join(str(tmp_path), t, f"round_{k}.csv"), index=False)
        assert study_cli(["status", path]) == 0
        assert all(p.state == "done" for p in S.load(path).history[-1].proposals)
        best = next(x for x in C.rank(S.load(path))["rows"] if x["feasible"])
        if best["score"] == pytest.approx(opt, rel=1e-9):
            found = k
            break
    capsys.readouterr()
    assert found is not None, f"not found in 4 rounds: best {best['score']} at {best['values']}, optimum {opt} at {opt_at}"
    print(f"fine-grid optimum {opt:.4f} at {opt_at} found in round {found}")


def test_nothing_pending_is_proposed_twice_and_run_ids_are_stable(tmp_path):
    path = _study(str(tmp_path), batch=6)
    s = S.load(path)
    a = N.next_runs(s, write=True)
    b = N.next_runs(S.load(path), write=False)
    va = {tuple(sorted(c["values"].items())) for c in a["candidates"]}
    vb = {tuple(sorted(c["values"].items())) for c in b["candidates"]}
    assert va and vb and not (va & vb) and b["pending"] == a["counts"]["runs"] and b["round"] == 2
    # the same study, the same round: the same proposal and ids
    again = N.next_runs(S.load(path), write=False, round_no=1)
    assert [r["run_id"] for r in again["runs"]] != [] and N.run_id("converge", 1, "A", {"Kp": 1.0, "wind": 0}) == N.run_id("converge", 1, "A", {"wind": 0, "Kp": 1.0})
    # every candidate expands to its runs in every table: scenarios x local values
    per_cand = {"A": 4, "B": 6, "C": 9}
    for t, n in per_cand.items():
        assert sum(1 for r in a["runs"] if r["table"] == t) == n * a["counts"]["candidates"]


def test_the_panels_study_gives_the_cli_proposal(tmp_path, capsys):
    path = _study(str(tmp_path), batch=8)
    client = TestClient(app)
    as_saved = json.load(open(path, encoding="utf-8"))
    r1 = client.post("/api/sweeps/next-runs", json={"study": as_saved, "study_path": path}).json()
    r2 = client.post("/api/sweeps/next-runs", json={"study_path": path}).json()
    capsys.readouterr()
    assert study_cli(["next", path, "--json"]) == 0
    r3 = json.loads(capsys.readouterr().out)
    for r in (r2, r3):
        assert r["candidates"] == r1["candidates"] and [x["run_id"] for x in r["runs"]] == [x["run_id"] for x in r1["runs"]]
    assert r3["written"] and not r1["written"]


def test_exit_3_when_nothing_is_left_at_the_smallest_step(tmp_path):
    for t in "AB":
        os.makedirs(tmp_path / t)
    pd.DataFrame([{"Kp": kp, "wind": w, "y": kp + w} for kp in (1.0, 2.0) for w in (0, 1)]).to_csv(tmp_path / "A" / "r.csv", index=False)
    pd.DataFrame([{"Kp": kp, "mass": m, "y": kp * m} for kp in (1.0, 2.0) for m in (1, 2)]).to_csv(tmp_path / "B" / "r.csv", index=False)
    study = {"version": 1, "name": "tiny", "tables": [
        {"id": "A", "paths": ["A/*.csv"], "roles": {"wind": "scenario", "y": "output"}, "objective": {"expr": "y", "sense": "min"}},
        {"id": "B", "paths": ["B/*.csv"], "roles": {"mass": "scenario", "y": "output"}, "objective": {"expr": "y", "sense": "min"}}],
        "shared": [{"name": "Kp"}], "search": {"params": {"Kp": {"values": [1.0, 2.0]}}}}
    p = tmp_path / "tiny.svstudy.json"
    p.write_text(json.dumps(study))
    assert study_cli(["next", str(p)]) == 3
    assert study_cli(["rank", str(p)]) == 0


def test_rank_prints_the_best_and_writes_a_csv(tmp_path, capsys):
    src = os.path.join(ROOT, "tests", "fixtures", "drones")
    for f in ("drone_a.csv", "drone_b.csv", "drone_c.csv", "fixture.svstudy.json"):
        shutil.copy(os.path.join(src, f), tmp_path / f)
    assert study_cli(["rank", str(tmp_path / "fixture.svstudy.json"), "--csv", str(tmp_path / "r.csv")]) == 0
    out = capsys.readouterr().out
    assert "4 of 8 values hold in every table" in out and "Pareto" in out
    assert len(pd.read_csv(tmp_path / "r.csv")) == 8
