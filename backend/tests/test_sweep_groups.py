"""MF00: groups of parameter sets (svcore/sweep/groups.py) - ids, rules, automatic groups, ∪ ∩ ∖."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.sweep import groups as G  # noqa: E402

COLS = {
    "p": np.array([1.0, 2.0, 3.0, 4.0]),
    "k": np.array([0.1, 0.1, 0.2, np.nan]),
    "#holds": np.array([1.0, 0.0, 1.0, 0.0]),
    "#pareto": np.array([1.0, 0.0, 0.0, 0.0]),
    "#complete": np.array([1.0, 1.0, 1.0, 0.0]),
}
IDS = G.set_ids({"p": COLS["p"], "k": COLS["k"]}, ["p", "k"])


def test_set_ids_stable_and_exact():
    assert IDS == ["p=1|k=0.1", "p=2|k=0.1", "p=3|k=0.2", "p=4|k="]
    assert G.set_id({"k": 0.1, "p": 1}, ["p", "k"]) == IDS[0]   # order from the parameters, not the dict
    assert G.set_id({"p": "fast"}, ["p"]) == "p=fast"


def test_rule_like_the_page():
    r = {"p": {"kind": "ranges", "ranges": [[3, 1.5]]}}       # reversed range still works
    assert G.rule_mask(COLS, r, 4).tolist() == [False, True, True, False]
    r2 = {"k": {"kind": "values", "values": [0.1]}, "gone": {"kind": "ranges", "ranges": [[0, 1]]}}
    assert G.rule_mask(COLS, r2, 4).tolist() == [True, True, False, False]   # a filter on a column gone is ignored
    m = G.rule_mask({"k": np.array([0.1, 0.1, 0.2, np.nan], dtype=np.float32)}, {"k": {"kind": "values", "values": [0.2]}}, 4)
    assert m.tolist() == [False, False, True, False]                  # NaN never kept
    assert G.rule_mask(COLS, {}, 4).all()


def test_automatic_groups():
    a = G.auto_masks(COLS, 4, suggested=["p=2|k=0.1"], ids=IDS)
    assert a["all"].sum() == 4
    assert a["holds"].tolist() == [True, False, True, False]
    assert a["pareto"].tolist() == [True, False, False, False]
    assert a["error"].tolist() == [False, False, False, True]
    assert a["fails"].tolist() == [False, True, False, False]       # complete and not holding
    assert a["suggested"].tolist() == [False, True, False, False]
    assert set(a) == set(G.AUTO)


def test_live_vs_frozen():
    live = {"source": "user", "rule": {"p": {"kind": "ranges", "ranges": [[2, 4]]}}, "frozen": False}
    frozen = {"source": "user", "ids": ["p=2|k=0.1", "p=9|k=1"], "frozen": True}
    assert G.mask(live, COLS, IDS).tolist() == [False, True, True, True]
    assert G.mask(frozen, COLS, IDS).tolist() == [False, True, False, False]
    # a new set comes in: the live group takes it, the frozen one does not
    cols = {**COLS, "p": np.append(COLS["p"], 3.5), "k": np.append(COLS["k"], 0.3)}
    ids = G.set_ids(cols, ["p", "k"])
    assert G.mask(live, cols, ids)[-1] and not G.mask(frozen, cols, ids)[-1]


def test_set_operations():
    a = np.array([1, 1, 0, 0], dtype=bool)
    b = np.array([0, 1, 1, 0], dtype=bool)
    assert G.combine("union", a, b).tolist() == [True, True, True, False]
    assert G.combine("intersect", a, b).tolist() == [False, True, False, False]
    assert G.combine("minus", a, b).tolist() == [True, False, False, False]
    assert G.freeze(G.combine("union", a, b), IDS) == IDS[:3]
    with pytest.raises(G.GroupError):
        G.combine("xor", a, b)


def test_check_rejects_bad_groups():
    for bad in ({"source": "auto", "rule": {}}, {"source": "magic", "rule": {}},
                {"source": "user", "frozen": True}, {"source": "user"}):
        with pytest.raises(G.GroupError):
            G.check(bad)
    G.check({"source": "doe", "frozen": True, "ids": []})


def test_answer_sends_how_many_combinations_a_condition_needs():
    """MF00's "fails in k of n": n per condition, k = n - passed per set."""
    import test_sweep as T
    _, a = T._ans(T._grid(), conditions=[{"column": "risk", "op": "<=", "value": 2.5},
                                         {"column": "risk", "op": "<=", "value": 2.5, "mode": "atLeast", "k": 2}])
    assert a["conditions"][0]["needed"] == 3 and a["conditions"][1]["needed"] == 2
    d = a["data"]
    p2 = d["p"] == 2.0                                   # passes in a and c, fails in b
    assert np.allclose(a["conditions"][0]["needed"] - d["#c0.passed"][p2], 1)
    masks = G.auto_masks(d, len(d["p"]))
    assert masks["fails"].sum() + masks["holds"].sum() == len(d["p"])


def test_condition_one_of_for_a_categorical_parameter():
    """MF01: a parameter among values - text and numbers; set_rows says why a set fails."""
    import pandas as pd
    from svcore import sweep
    rows = [{"mode": m, "p": p, "sc": s, "out": p + (1 if m == "fast" else 0)}
            for m in ("fast", "safe", "eco") for p in (1.0, 2.0) for s in ("a", "b")]
    df = pd.DataFrame(rows)
    roles = {"mode": "param", "p": "param", "sc": "hold", "out": "output"}
    q = {"roles": roles, "conditions": [{"column": "mode", "op": "==", "value": 0, "in": ["fast", "eco"], "mode": "all"}]}
    pr = sweep.prepare(df, q)
    a = sweep.answer(pr, q)
    assert a["counts"]["holding"] == 4 and a["conditions"][0]["label"] == "mode ∈ {fast, eco}"
    q2 = {**q, "conditions": [{"column": "p", "op": "==", "value": 0, "in": [2], "mode": "all"}]}
    assert sweep.answer(sweep.prepare(df, q2), q2)["counts"]["holding"] == 3
    safe = [i for i in range(pr.n_sets) if df["mode"].iloc[pr.first_row[i]] == "safe"][0]
    assert sweep.set_rows(pr, q, safe)["why"][0]["worst"] == "safe"
    with pytest.raises(Exception):
        bad = {**q, "conditions": [{"column": "out", "op": "==", "value": 0, "in": [1]}]}
        sweep.answer(sweep.prepare(df, bad), bad)
