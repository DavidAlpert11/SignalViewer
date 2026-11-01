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
