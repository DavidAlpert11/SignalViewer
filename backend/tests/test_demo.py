"""W18: the smart-sweep demo (svcore/demo.py, examples/smart_sweep_demo/, `study demo / demo-sim`, the demo
routes): the simulator's input / output contract, the full-grid reference, the convergence rule, and the
whole demo - it reaches the full-grid optimum within the tolerance in under 60 s, at least 10x fewer runs."""
import csv
import importlib.util
import itertools
import json
import os
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from signalviewer.study import main as study_cli
from svcore import demo, loop
from svcore import study as S
from svcore.drone_model import simulate

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEMO = os.path.join(ROOT, "examples", "smart_sweep_demo", "demo.svstudy.json")
SIM = os.path.join(ROOT, "examples", "smart_sweep_demo", "sim.py")


def _sim():
    spec = importlib.util.spec_from_file_location("demo_sim", SIM)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_sim_reads_a_params_file_and_writes_one_row(tmp_path):
    out = tmp_path / "res" / "abc123.csv"
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"run_id": "abc123", "table": "C", "Kp": 2.0, "Ki": 0.5, "Kd": 0.8, "wind": 5,
                             "filter_hz": 30, "out": str(out), "sim": SIM, "sleep_ms": 0, "noise": 0}))
    assert study_cli(["demo-sim", str(p)]) == 0                    # the Portable's way: no python of its own
    rows = list(csv.DictReader(open(out)))
    assert len(rows) == 1
    r = rows[0]
    assert set(r) == {"Kp", "Ki", "Kd", "wind", "filter_hz", "overshoot", "settling_time", "motor_sat", "energy",
                      "phase_margin", "run_id"}
    ref = simulate("C", 2.0, 0.5, 0.8, wind=5, filter_hz=30)
    for k, v in ref.items():
        assert float(r[k]) == pytest.approx(float(v), abs=1e-5), k


def test_the_stdlib_sim_is_the_drone_model():
    m = _sim()
    rng = np.random.default_rng(3)
    for t in "ABC":
        for _ in range(50):
            kp, ki, kd, wind = rng.uniform(0.3, 6), rng.uniform(0, 2.5), rng.uniform(0.02, 2.5), rng.uniform(0, 10)
            kw = {"mass": rng.uniform(1, 6)} if t == "B" else {"filter_hz": rng.uniform(10, 80)} if t == "C" else {}
            a = m.model(t, kp, ki, kd, wind, **kw)
            b = simulate(t, kp, ki, kd, wind=wind, **kw)
            for k in a:
                assert a[k] == pytest.approx(float(b[k]), rel=1e-9, abs=1e-12), (t, k)


def test_noise_is_seeded_by_the_run(tmp_path):
    m = _sim()
    vals = []
    for i in range(2):
        p = tmp_path / f"p{i}.json"
        p.write_text(json.dumps({"run_id": "same", "table": "A", "Kp": 1, "Ki": 0.5, "Kd": 0.5, "wind": 0,
                                 "out": str(tmp_path / f"o{i}.csv"), "noise": 0.01, "seed": 4}))
        vals.append(m.run(str(p))["settling_time"])
    assert vals[0] == vals[1] and vals[0] != pytest.approx(float(simulate("A", 1, 0.5, 0.5)["settling_time"]), rel=1e-6)


def test_the_reference_is_the_brute_force_optimum_of_the_fine_grid(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    s = demo.prepare(DEMO, reset=True)
    t0 = time.perf_counter()
    ref = demo.reference(s)
    took = time.perf_counter() - t0
    axes = [np.round(0.5 + 0.225 * np.arange(21), 12), np.round(0.1 * np.arange(21), 12), np.round(0.05 + 0.1 * np.arange(21), 12)]
    g = np.array(list(itertools.product(*axes)))
    sc = s.demo.scenarios
    worst, ok = np.zeros(len(g)), np.ones(len(g), bool)
    for t, cons in (("A", lambda o: o["overshoot"] < 8), ("B", lambda o: (o["overshoot"] < 12) & (o["motor_sat"] < 0.9))):
        for c in itertools.product(*sc[t].values()):
            o = simulate(t, g[:, 0], g[:, 1], g[:, 2], **dict(zip(sc[t], c)))
            ok &= cons(o)
            worst = np.maximum(worst, o["settling_time"])
    best_c = np.full(len(g), np.inf)
    for f in sc["C"]["filter_hz"]:
        okf, w = np.ones(len(g), bool), np.zeros(len(g))
        for wind in sc["C"]["wind"]:
            o = simulate("C", g[:, 0], g[:, 1], g[:, 2], wind=wind, filter_hz=f)
            okf &= o["phase_margin"] > 45
            w = np.maximum(w, o["settling_time"])
        best_c = np.where(okf, np.minimum(best_c, w), best_c)
    score = np.where(ok & np.isfinite(best_c), np.maximum(worst, best_c), np.inf)
    assert ref["score"] == pytest.approx(score.min())
    assert ref["values_count"] == 9261 and ref["runs"] == 9261 * 12
    print(f"reference: {took:.2f} s on {os.cpu_count()} CPUs")
    assert demo.reference(s)["key"] == ref["key"]                  # cached


def test_the_convergence_rule():
    p = lambda r, v: {"round": r, "runs": 10 * r, "best": 1.0, "values": v, "gap_pct": 0}
    assert not loop.converged([p(1, {"a": 1}), p(2, {"a": 1})])
    assert loop.converged([p(1, {"a": 2}), p(2, {"a": 1}), p(3, {"a": 1}), p(4, {"a": 1})])
    assert not loop.converged([p(1, {"a": 1}), p(2, {"a": 1}), p(3, {"a": 2})])
    prog = {"points": [{"round": 1, "runs": 768, "best": 1.5, "gap_pct": 20.0}, {"round": 2, "runs": 1008, "best": 1.24, "gap_pct": 0.2},
                       {"round": 3, "runs": 1248, "best": 1.24, "gap_pct": 0.2}],
            "tolerance_pct": 0.5, "full_grid": {"values": 9261, "runs": 111132}, "saving": 111132 / 1008}
    assert demo.sentence(prog) == ("Found the full-grid optimum within 0.5 % after 1,008 runs - the full grid needs "
                                   "9,261 x 12 = 111,132 runs (≈ 110× fewer).")


def test_the_demo_converges_in_a_minute_with_10x_fewer_runs(tmp_path, monkeypatch, capsys):
    """W18's Done when, through the CLI with the default settings (the panel calls the same functions)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    t0 = time.perf_counter()
    code = study_cli(["demo", DEMO, "--json"])
    took = time.perf_counter() - t0
    out = capsys.readouterr().out.splitlines()
    p = json.loads(next(x for x in out if x.startswith("{")))
    hit = next((x for x in p["points"] if x["gap_pct"] is not None and x["gap_pct"] <= p["tolerance_pct"]), None)
    print(f"demo: {took:.1f} s on {os.cpu_count()} CPUs, {len(p['points'])} rounds, reached at {hit and hit['runs']} runs, "
          f"saving {p['saving']}x; {out[-1]}")
    assert code in (0, 3)
    assert hit is not None and p["saving"] >= 10 and took < 60
    assert out[-1].startswith("Found the full-grid optimum within 0.5 %")
    # determinism: the same rounds again
    capsys.readouterr()
    study_cli(["demo", DEMO, "--max-rounds", "2", "--json"])
    again = json.loads(next(x for x in capsys.readouterr().out.splitlines() if x.startswith("{")))
    assert again["points"] == p["points"][:2]


def test_the_routes_next_round_twice(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    c = TestClient(app)
    r = c.post("/api/sweeps/demo/step", json={"study_path": DEMO, "action": "reset"}).json()
    assert r["round"] == 0 and r["points"] == [] and r["full_grid"]["runs"] == 111132
    for k in (1, 2):
        c.post("/api/sweeps/demo/step", json={"study_path": DEMO, "action": "next"})
        t0 = time.time()
        while True:
            p = c.get("/api/sweeps/demo/progress", params={"study_path": DEMO}).json()
            if not p["running"] and len(p["points"]) == k:
                break
            assert time.time() - t0 < 60
            time.sleep(0.2)
    assert [x["runs"] for x in p["points"]] == [768, 1008] and p["runs"]["done"] == 1008
    assert len(p["tried"]) == 64 + 20 and p["best"] is not None
