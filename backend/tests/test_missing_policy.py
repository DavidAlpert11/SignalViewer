"""C3: an explicit missing-data policy. By default a missing value stays missing - a sum with a
missing input is missing (it was the sum of the others: 1 + NaN + 3 = 4), an integral does not
treat a gap as 0, a comparison with a missing value is missing (`!=` was true), and infinity
turned into a missing value is reported. `params.nan`: "propagate" (default for new work), "skip"
(the old skipping where it makes sense, marked), "legacy" (exactly the numbers before 1.23: what a
recipe saved without `nan` is restored as)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.analysis import OpError, compute  # noqa: E402
from svcore.formula import evaluate as _evaluate  # noqa: E402


def evaluate(expr, sigs, _align, **kw):
    return _evaluate(expr, sigs, lambda t, ts, ys: np.interp(t, ts, ys), **kw)

T = np.arange(5.0)
ONE, HOLE, THREE = (T, np.ones(5)), (T, np.array([2, np.nan, 2, 2, 2.0])), (T, 3 * np.ones(5))


def nan_at(y, i):
    return bool(np.isnan(y[i]))


@pytest.mark.parametrize("op", ["sum", "norm", "mean", "min", "max"])
def test_several_signals_propagate_by_default(op):
    _, y = compute(op, [ONE, HOLE, THREE], {})
    assert nan_at(y, 1) and np.isfinite(y[[0, 2, 3, 4]]).all()


def test_sum_and_norm_values():
    assert compute("sum", [ONE, HOLE, THREE], {})[1][0] == 6.0
    assert abs(compute("norm", [ONE, HOLE], {})[1][0] - np.sqrt(5)) < 1e-12


def test_skip_is_the_old_skipping_and_is_reported():
    rep: dict = {}
    _, y = compute("sum", [ONE, HOLE, THREE], {"nan": "skip"}, report=rep)
    assert y[1] == 4.0 and rep["nan"] == "skip" and rep["skipped"] == 1
    _, y = compute("sum", [ONE, HOLE, THREE], {"nan": "legacy"})
    assert y[1] == 4.0


def test_integral_over_missing_is_not_zeroed():
    t = np.arange(6.0)
    y = np.array([1, 1, np.nan, np.nan, 1, 1.0])
    rep: dict = {}
    _, r = compute("integral", [(t, y)], {}, report=rep)
    assert list(r[:2]) == [0.0, 1.0] and np.isnan(r[2:]).all()       # unknown from the gap on
    assert rep["missing"] == [[2.0, 3.0]]
    rep = {}
    _, r = compute("integral", [(t, y)], {"nan": "skip"}, report=rep)  # bridged: the line from 1 to 4
    assert abs(r[-1] - 5.0) < 1e-12 and rep["bridged"] == [[2.0, 3.0]]
    _, r = compute("integral", [(t, y)], {"nan": "legacy"})            # the old: the gap counted as 0
    assert abs(r[-1] - 3.0) < 1e-12


def test_comparisons_on_missing_are_missing():
    v = (T, np.array([1, np.nan, 2, 1, 1.0]))
    for e in ("v0 != 1", "v0 == 1", "v0 > 0", "not (v0 == 1)"):
        assert nan_at(evaluate(e, [v], None)[1], 1), e
    assert evaluate("v0 != 1", [v], None, nan="legacy")[1][1] == 1.0          # the old: true
    # and / or: missing unless the other side decides (false and ? = false; true or ? = true)
    a = (T, np.array([0, 0, 1, 1, np.nan]))
    got = evaluate("(v0 > 0.5) and (v1 > 0)", [a, v], None)[1]
    assert got[1] == 0.0 and nan_at(got, 4)
    got = evaluate("(v0 > 0.5) or (v1 > 0)", [a, v], None)[1]
    assert nan_at(got, 1) and got[2] == 1.0
    assert nan_at(evaluate("where(v0 > 1, 5, 6)", [v], None)[1], 1)


def test_infinity_is_reported():
    rep: dict = {}
    _, y = evaluate("1 / v0", [(T, np.array([1, 0, 2, 1, 1.0]))], None, report=rep)
    assert nan_at(y, 1) and rep["infinite"] == 1


def test_unknown_policy_is_an_error():
    with pytest.raises(OpError):
        compute("sum", [ONE, THREE], {"nan": "zero"})


def test_new_recipe_is_marked_propagate_old_restored_as_legacy(tmp_path):
    from app.store import Store
    csv = tmp_path / "a.csv"
    csv.write_text("time,A,B\n0,1,2\n1,1,\n2,1,2\n3,1,2\n")
    s = Store()
    r = s.open_file(str(csv))
    src = [f"{r.id}/A", f"{r.id}/B"]
    new = s.add_derived("sum", src, {})
    assert new.params["nan"] == "propagate" and np.isnan(s.signal(f"derived/{new.name}")[1][1])
    old = s.add_derived("sum", src, {}, "old", legacy=True)            # a session saved before 1.23
    assert old.params["nan"] == "legacy" and s.signal("derived/old")[1][1] == 1.0
    kept = s.add_derived("sum", src, {"nan": "skip"}, "skip", legacy=True)
    assert kept.params["nan"] == "skip"
    assert s.add_derived("derivative", src[:1], {}).params.get("nan") is None   # not a policy op
    listed = {x["name"]: x for run in s.list() if run.get("id") == "derived" for x in run["signals"]}
    assert "quality" not in listed[new.name]                    # nothing skipped or bridged: no mark
    skip_row = listed["skip"]
    assert skip_row["quality"]["skipped"] == 1 and skip_row["quality"]["nan"] == "skip"
