"""Named conditions: the stretches where an expression holds, in each open file."""
import numpy as np
import pytest

from app.store import LoadError, Store
from svcore.conditions import names_in, resolve, stretches


def test_stretches_plain_merge_and_min():
    t = np.arange(10.0)
    on = np.array([0, 1, 1, 0, 1, 0, 0, 1, 1, 1], bool)
    assert stretches(t, on) == [(1, 3), (4, 5), (7, 9)]
    assert stretches(t, on, merge_gap=1) == [(1, 5), (7, 9)]
    assert stretches(t, on, min_dur=2) == [(1, 3), (7, 9)]


def test_hysteresis_in_above_out_below():
    t = np.arange(8.0)
    y = np.array([1900, 1960, 1930, 1940, 1890, 1910, 1955, 1960])
    assert stretches(t, y > 1950, y < 1900) == [(1, 4), (6, 7)]          # 1930 stays in


def test_names_and_text_states():
    assert names_in('abs({Vz}) > 5 and Mode == "AUTO"') == ["Vz", "Mode"]
    expr, names = resolve('{Mode} == "auto" or not Speed > 3', lambda n: {"0": "MANUAL", "4": "AUTO"} if n == "Mode" else None)
    assert names == ["Mode", "Speed"] and "== 4" in expr and "not v1 > 3" in expr



def test_numbers_written_with_an_exponent_are_numbers_not_names():
    """Speed > 1e3 used to ask for a signal "e3" (missing in every file); 2.5E-3 for "E"."""
    assert names_in("Speed > 1e3") == ["Speed"]
    assert names_in("Speed > 2.5E-3 or Alt < 1_000") == ["Speed", "Alt"]
    expr, names = resolve("{Speed} > 1.5e3 and Mode == \"AUTO\"", lambda n: {"3": "AUTO"} if n == "Mode" else None)
    assert names == ["Speed", "Mode"] and expr == "v0 > 1.5e3 and v1 == 3"
    from svcore.conditions import evaluate_condition
    t = np.arange(0, 10, 0.1)
    r = evaluate_condition("Speed > 1e3", lambda n: (t, t * 300) if n == "Speed" else None, lambda n: None,
                           lambda a, tb, yb: np.interp(a, tb, yb))
    assert r["count"] == 1 and abs(r["intervals"][0][0] - 3.4) < 0.11

def _csv(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("Time,Speed,Mode\n" + "".join(f"{i * 0.5},{s},{m}\n" for i, (s, m) in enumerate(rows)))
    return str(p)


def test_store_evaluates_in_each_file_and_says_what_is_missing(tmp_path):
    st = Store()
    a = st.open_file(_csv(tmp_path, "a.csv", [(1, 0), (5, 0), (6, 1), (2, 1), (7, 1)])).id
    p = tmp_path / "b.csv"
    p.write_text("Time,Other\n0,1\n1,2\n")
    b = st.open_file(str(p)).id
    r = st.evaluate_condition("{Speed} > 4 and Mode == 1", run_ids=None)
    assert r[a]["count"] == 2 and r[a]["intervals"][0] == [1.0, 1.5]
    assert r[b]["missing"] == ["Speed", "Mode"]
    assert r[a]["ranges"]["Speed"] == [1.0, 7.0]
    st.set_time_offset(a, 10)                                            # as shown: with the offset
    assert st.evaluate_condition("Speed > 6", run_ids=[a])[a]["intervals"] == [[12.0, 12.0]]
    assert "error" in st.evaluate_condition("Speed >", run_ids=[a])[a]
    with pytest.raises(LoadError):
        st.evaluate_condition("  ")
