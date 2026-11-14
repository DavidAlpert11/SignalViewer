"""W14: one parameter set for many sweep tables (svcore/sweeps_common.py) - the vectorised answer against a
reference written with plain loops, the name mapping, "not run", dropped scenarios, the time for 3 x 1000 rows."""
import copy
import csv
import itertools
import json
import os
import time

import numpy as np
import pandas as pd
import pytest

from svcore import study as S
from svcore import sweeps_common as C
from svcore.drone_model import simulate

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
FIX = os.path.join(ROOT, "tests", "fixtures", "drones")
EX = os.path.join(ROOT, "examples", "drones", "drones.svstudy.json")


def _key(v):
    return tuple(sorted((k, float(x)) for k, x in v.items()))


def test_the_fixture_gives_the_hand_checked_answer():
    r = C.rank(S.load(os.path.join(FIX, "fixture.svstudy.json")))
    exp = json.load(open(os.path.join(FIX, "expected.json"), encoding="utf-8"))
    assert r["mode"] == exp["mode"] == "pareto"
    assert {_key(x["values"]) for x in r["rows"] if x["feasible"]} == {_key(v) for v in exp["feasible"]}
    assert {_key(x["values"]) for x in r["rows"] if x["pareto"]} == {_key(v) for v in exp["pareto"]}
    got = {_key(x["values"]): {p["table"]: p for p in x["tables"]} for x in r["rows"]}
    for e in exp["values"]:
        g = got[_key(e["values"])]
        for t, et in e["tables"].items():
            assert g[t]["status"] == et["status"], (e["values"], t)
            if et["status"] == "pass":
                assert g[t]["score"] == pytest.approx(et["score"]) and g[t]["local"] == et["local"]
                assert g[t]["worst"] == et["worst"], (e["values"], t)


def test_not_run_is_said_and_where():
    r = C.rank(S.load(os.path.join(FIX, "fixture.svstudy.json")))
    row = next(x for x in r["rows"] if x["values"] == {"Kp": 4.0, "Ki": 0.5})      # Kp = 4 only in table A
    per = {p["table"]: p for p in row["tables"]}
    assert per["B"]["status"] == per["C"]["status"] == "not_run"
    assert per["B"]["failed"]["constraint"] == "not run" and not row["feasible"]
    # a scenario run missing for one local value: the other local value is chosen (C, Kp 1, Ki 1: 20 Hz missing at wind 5)
    row = next(x for x in r["rows"] if x["values"] == {"Kp": 1.0, "Ki": 1.0})
    assert {p["table"]: p for p in row["tables"]}["C"]["local"] == {"filter_hz": 10}


def test_the_failure_names_table_scenario_constraint_and_by_how_much():
    r = C.rank(S.load(os.path.join(FIX, "fixture.svstudy.json")))
    row = next(x for x in r["rows"] if x["values"] == {"Kp": 3.0, "Ki": 1.0})
    a = {p["table"]: p for p in row["tables"]}["A"]
    assert a["status"] == "fail"
    assert a["failed"] == {"scenario": {"wind": 5}, "constraint": "overshoot < 10", "by": pytest.approx(1.0)}
    assert len(a["runs"]) == 2                                   # the runs of that value, to open them


def test_mapping_proposes_p_gain_as_kp():
    m = C.propose_mapping({"A": ["Kp", "Ki", "Kd", "wind", "overshoot"], "B": ["Kp", "Ki", "Kd", "mass"],
                           "C": ["P_gain", "I_gain", "D_gain", "filter_hz", "wind", "Overshoot [%]"]})
    pairs = {(x["table"], x["column"]): x["name"] for x in m}
    assert pairs[("C", "P_gain")] == "Kp" and pairs[("C", "I_gain")] == "Ki" and pairs[("C", "D_gain")] == "Kd"
    assert pairs[("C", "Overshoot [%]")] == "overshoot"
    assert ("A", "Kp") not in pairs and ("C", "wind") not in pairs          # nothing renamed that already matches
    assert C.normalise("Proportional gain") == C.normalise("k_p") == "kp"


# ------------------------------------------------------------------ the reference: plain loops

CONS = {"A": lambda r: r["overshoot"] < 8, "B": lambda r: r["overshoot"] < 12 and r["motor_sat"] < 0.9,
        "C": lambda r: r["phase_margin"] > 45}
OBJ = {"A": "settling_time", "B": "energy", "C": "settling_time"}
SCEN = {"A": ["wind"], "B": ["mass", "wind"], "C": ["wind"]}
LOCAL = {"A": [], "B": [], "C": ["filter_hz"]}
RENAME = {"C": {"P_gain": "Kp", "I_gain": "Ki", "D_gain": "Kd"}}


def _rows(t, drop=None):
    path = os.path.join(ROOT, "examples", "drones", f"drone_{t.lower()}.csv")
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r = {RENAME.get(t, {}).get(k, k): float(v) for k, v in r.items()}
            if drop and any(r[c] in vals for c, vals in drop.get(t, {}).items()):
                continue
            out.append(r)
    return out


def _reference(drop=None):
    """value of (Kp, Ki, Kd) -> {table: score or None}: worst case over scenarios, best local value."""
    tables = {t: _rows(t, drop) for t in "ABC"}
    values = sorted({(r["Kp"], r["Ki"], r["Kd"]) for rows in tables.values() for r in rows})
    out = {}
    for v in values:
        per = {}
        for t, rows in tables.items():
            combos = sorted({tuple(r[c] for c in SCEN[t]) for r in rows})
            mine = [r for r in rows if (r["Kp"], r["Ki"], r["Kd"]) == v]
            locs = sorted({tuple(r[c] for c in LOCAL[t]) for r in mine}) or [()]
            best = None
            for loc in locs:
                worst, ok = -np.inf, True
                for e in combos:
                    run = [r for r in mine if tuple(r[c] for c in SCEN[t]) == e and tuple(r[c] for c in LOCAL[t]) == loc]
                    if not run or not CONS[t](run[0]):
                        ok = False
                        break
                    worst = max(worst, run[0][OBJ[t]])
                if ok and (best is None or worst < best):
                    best = worst
            per[t] = best if mine else "not_run"
        out[v] = per
    return out


def _pareto(feas):
    keys = list(feas)
    sc = np.array([[feas[k][t] for t in "ABC"] for k in keys])
    return {k for i, k in enumerate(keys) if not any(np.all(sc[j] <= sc[i]) and np.any(sc[j] < sc[i]) for j in range(len(keys)) if j != i)}


@pytest.mark.parametrize("drop", [None, {"B": {"mass": [5.0]}}])
def test_vectorised_equals_plain_loops_on_the_example(drop):
    s = S.load(EX)
    if drop:
        s.table("B").drop = {"mass": [5.0]}
    ref = _reference(drop)
    r = C.rank(s)
    got = {(x["values"]["Kp"], x["values"]["Ki"], x["values"]["Kd"]): x for x in r["rows"]}
    assert set(got) == set(ref)
    feas_ref = {v: per for v, per in ref.items() if all(isinstance(per[t], float) for t in "ABC")}
    assert {v for v, x in got.items() if x["feasible"]} == set(feas_ref)
    for v, per in feas_ref.items():
        for p in got[v]["tables"]:
            assert p["score"] == pytest.approx(per[p["table"]]), (v, p["table"])
    assert {v for v, x in got.items() if x["pareto"]} == _pareto(feas_ref)


def test_dropping_a_scenario_changes_the_feasible_set_as_expected():
    s = S.load(EX)
    before = {_key(x["values"]) for x in C.rank(s)["rows"] if x["feasible"]}
    s.table("B").drop = {"mass": [5.0]}                           # the heaviest payload no longer has to hold
    after = {_key(x["values"]) for x in C.rank(s)["rows"] if x["feasible"]}
    assert before < after                                         # only gains: nothing that held stops holding
    s.table("A").drop = {"wind": [0, 3, 6, 10]}
    with pytest.raises(C.StudyError, match="every scenario value is left out"):
        C.rank(s)


def test_one_objective_everywhere_minimises_the_worst_table():
    s = S.load(EX)
    s.table("B").objective = S.Objective(expr="settling_time", sense="min")
    r = C.rank(s)
    assert r["mode"] == "minworst"
    feas = [x for x in r["rows"] if x["feasible"]]
    worst = [max(p["score"] for p in x["tables"]) for x in feas]
    assert [x["score"] for x in feas] == pytest.approx(worst)
    assert worst == sorted(worst) and feas[0]["rank"] == 1


def test_mean_over_scenarios_and_a_tolerance_on_the_values():
    s = S.load(os.path.join(FIX, "fixture.svstudy.json"))
    s.table("A").aggregate = "mean"
    r = C.rank(s)
    a = {p["table"]: p for x in r["rows"] if x["values"] == {"Kp": 1.0, "Ki": 0.5} for p in x["tables"]}["A"]
    assert a["score"] == pytest.approx((6.0 + 6.5) / 2)
    # values written slightly differently in another table match within the tolerance
    frames = {t.id: C.read_table_files(s.table_files(t)) for t in s.tables}
    frames["B"] = frames["B"].assign(Kp=frames["B"]["Kp"] + 1e-4)
    s.shared = [S.SharedParam(name="Kp", tolerance=0.01), S.SharedParam(name="Ki")]
    assert C.rank(s, frames)["counts"]["feasible"] == 4
    s.shared = [S.SharedParam(name="Kp"), S.SharedParam(name="Ki")]
    assert C.rank(s, frames)["counts"]["feasible"] == 0           # exact matching: B's values are other values


def test_three_tables_of_1000_rows_in_under_a_second():
    s = S.load(EX)
    rng = np.random.default_rng(0)
    frames = {}
    gains = np.array(list(itertools.product(np.linspace(0.5, 5, 10), np.linspace(0, 2, 5), np.linspace(0.05, 1.05, 5))))  # 250 values
    for t, scen in (("A", {"wind": [0, 3, 6, 10]}), ("B", {"mass": [2.0, 5.0], "wind": [0, 5]})):
        rows = [dict(zip(["Kp", "Ki", "Kd"], g), **dict(zip(scen, c))) for g in gains for c in itertools.product(*scen.values())]
        df = pd.DataFrame(rows)
        o = simulate(t, df.Kp, df.Ki, df.Kd, wind=df.wind, mass=df.get("mass"))
        frames[t] = df.assign(**{k: v for k, v in o.items()})
    rows = [dict(zip(["P_gain", "I_gain", "D_gain"], g), filter_hz=f, wind=w) for g in gains for f, w in itertools.product([15, 30], [0, 8])]
    df = pd.DataFrame(rows)
    o = simulate("C", df.P_gain, df.I_gain, df.D_gain, wind=df.wind, filter_hz=df.filter_hz)
    frames["C"] = df.assign(**{k: v for k, v in o.items()})
    assert all(len(f) == 1000 for f in frames.values())
    C.rank(s, frames)                                             # warm (imports, first pandas paths)
    t0 = time.perf_counter()
    r = C.rank(s, frames)
    took = time.perf_counter() - t0
    print(f"3 x 1000 rows: {took:.3f} s on {os.cpu_count()} CPUs")
    assert r["counts"]["values"] == 250 and took < 1.0, took
    assert rng is not None


def test_the_ranking_exports_as_a_csv(tmp_path):
    r = C.rank(S.load(os.path.join(FIX, "fixture.svstudy.json")))
    df = C.to_csv_rows(r)
    assert list(df.columns[:3]) == ["rank", "Kp", "Ki"] and "C:filter_hz" in df.columns
    assert df.loc[df["Kp"] == 4.0, "B:failed"].iloc[0] == "not run"


def test_a_study_with_one_table_or_no_shared_column_says_what_to_do():
    s = S.load(os.path.join(FIX, "fixture.svstudy.json"))
    none = copy.deepcopy(s)
    none.tables = []
    with pytest.raises(C.StudyError, match="at least one table"):
        C.rank(none)
    one = copy.deepcopy(s)                 # one system (C1: a study started from nothing): ranked on its own
    one.tables = one.tables[:1]
    r = C.rank(one)
    assert r["rows"] and all(len(x["tables"]) == 1 for x in r["rows"])
    one.shared, one.search.params = [], {}
    with pytest.raises(C.StudyError, match="Say which columns are the parameters"):
        C.rank(one)
    s.table("C").rename = {}
    with pytest.raises(C.StudyError, match="Map its name"):
        C.rank(s)
