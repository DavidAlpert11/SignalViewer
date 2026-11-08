"""C2: state signals (modes, gears, text columns) are aligned with the value IN FORCE in formulas,
operations and conditions - linear interpolation made values the mode never had, and the nearest
sample started a mode halfway to the previous change."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.analysis import compute, hold_to  # noqa: E402
from svcore.conditions import evaluate_condition  # noqa: E402

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "copter_flight.bin")


def test_hold_to_is_the_value_in_force():
    ts, ys = np.array([1.0, 3.0, 6.0]), np.array([0.0, 2.0, 5.0])
    got = hold_to(np.array([0.5, 1.0, 2.9, 3.0, 5.99, 6.0, 9.0]), ts, ys)
    assert np.isnan(got[0]) and list(got[1:]) == [0.0, 0.0, 2.0, 2.0, 5.0, 5.0]
    assert list(hold_to(np.array([2.5]), ts, np.array([1.0, np.nan, 3.0]))) == [1.0]   # a blank sample holds


def _mode_and_fast():
    tm, m = np.array([0.0, 10.0, 20.0, 30.0]), np.array([0.0, 2.0, 5.0, 3.0])          # change-only
    tf = np.arange(0, 35, 0.01)
    return (tf, np.sin(tf)), (tm, m)


def test_formula_never_makes_a_state_value_that_does_not_exist():
    fast, mode = _mode_and_fast()
    for alignment in ("linear", "nearest"):
        _, y = compute("expr", [fast, mode], {"expr": "v1", "alignment": alignment}, [False, True])
        assert set(np.unique(y[np.isfinite(y)])) <= {0.0, 2.0, 5.0, 3.0}
        _, y = compute("expr", [fast, mode], {"expr": "v1 * 10", "alignment": alignment}, [False, True])
        assert set(np.unique(y[np.isfinite(y)])) <= {0.0, 20.0, 50.0, 30.0}


def test_operations_hold_a_state_source():
    fast, mode = _mode_and_fast()
    t, y = compute("add", [fast, mode], {}, [False, True])
    assert set(np.unique(np.round(y - np.sin(t), 9))) <= {0.0, 2.0, 5.0, 3.0}
    t, y = compute("max", [fast, mode], {}, [False, True])
    assert np.allclose(y[(t > 10.5) & (t < 19.5)], 2.0)


def test_hold_false_keeps_the_old_interpolation():
    """`params.hold: false` - the saved choice to align every source the same way (before 1.23)."""
    fast, mode = _mode_and_fast()
    _, y = compute("expr", [fast, mode], {"expr": "v1", "hold": False}, [False, True])
    assert len(set(np.unique(y[np.isfinite(y)])) - {0.0, 2.0, 5.0, 3.0}) > 100
    _, y = compute("expr", [fast, mode], {"expr": "v1"})                         # no states known: as before
    assert len(set(np.unique(y[np.isfinite(y)])) - {0.0, 2.0, 5.0, 3.0}) > 100


def test_condition_on_a_mode_starts_at_the_change():
    fast, mode = _mode_and_fast()
    sig = {"X": fast, "Mode": mode}
    from svcore.analysis import align_to
    near = lambda t, ts, ys: align_to(t, ts, ys, "nearest")    # noqa: E731  (what investigate passes)
    r = evaluate_condition("{X} > -10 and {Mode} == 5", sig.get, lambda n: None, near, is_state=lambda n: n == "Mode")
    (a, b), = r["intervals"]
    assert abs(a - 20.0) < 0.011 and abs(b - 30.0) < 0.011
    r = evaluate_condition("{X} > -10 and {Mode} == 5", sig.get, lambda n: None, near)          # old: nearest
    assert abs(r["intervals"][0][0] - 15.0) < 0.011


@pytest.mark.skipif(not os.path.exists(EX), reason="examples/copter_flight.bin not here")
def test_copter_example_mode_condition_and_formula():
    from app.store import Store
    s = Store()
    r = s.open_file(os.path.abspath(EX))
    _, m = s.signal(f"{r.id}/MODE.Mode")
    got = s.evaluate_condition("{ATT.Roll [deg]} > -1000 and {MODE.Mode} == 5")[r.id]["intervals"]
    assert len(got) == 1 and abs(got[0][0] - 46.41) < 0.01 and abs(got[0][1] - 60.41) < 0.01
    d = s.add_derived("expr", [f"{r.id}/ATT.Roll [deg]", f"{r.id}/MODE.Mode"], {"expr": "v1"})
    _, y = s.signal(f"derived/{d.name}")
    assert set(np.unique(y[np.isfinite(y)])) <= set(np.unique(m))


def test_old_session_keeps_its_numbers_new_recipes_hold(tmp_path):
    """C2b (owner, 2026-11-08): a recipe restored from a session saved before 1.23 (no `hold`) gets
    `"hold": false` - its numbers stay what they were; a new recipe stores `"hold": true`, so a session
    saved now and re-opened keeps holding (the restore path cannot tell them apart otherwise)."""
    from app.store import Store
    csv = tmp_path / "m.csv"
    rows = ["time,X,Mode"] + [f"{i / 10},{i / 10},{(i // 20) * 2}" for i in range(80)]
    csv.write_bytes(("\n".join(rows) + "\n").encode())
    s = Store()
    r = s.open_file(str(csv))
    x, m = f"{r.id}/X", f"{r.id}/Mode"
    assert s.is_state(m)
    old = s.add_derived("expr", [x, m], {"expr": "v1"}, "old", legacy=True)
    assert old.params["hold"] is False
    new = s.add_derived("expr", [x, m], {"expr": "v1"}, "new")
    assert new.params["hold"] is True
    again = s.add_derived("add", [x, m], {"hold": True}, "saved_now", legacy=True)   # 1.23 session
    assert again.params["hold"] is True
    assert s.add_derived("derivative", [x], {}).params.get("hold") is None          # no alignment
    for op in ("add", "sum"):
        assert s.add_derived(op, [x, m], {}, f"{op}_old", legacy=True).params["hold"] is False
