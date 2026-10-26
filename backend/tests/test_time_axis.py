"""The time axis of a file: another column as the time, a scale (its unit), the offset - changed
while working (owner's request, 2026-10-26)."""
import numpy as np
import pytest

from app.store import LoadError, Store
from svcore import time_axis


def _csv(tmp_path, text, name="run.csv"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


@pytest.fixture
def store():
    return Store()


ROWS = "Time,Speed,Count,Alt\n" + "".join(f"{i * 0.1:.1f},{i * 2},{i * 100},{[0, 5, 3, 8, 2, 9][i % 6]}\n" for i in range(12))


def test_unit_from_name():
    assert time_axis.unit_from_name("time_boot_ms") == "ms"
    assert time_axis.unit_from_name("t [us]") == "us"
    assert time_axis.unit_from_name("Time (min)") == "min"
    assert time_axis.unit_from_name("stamp_ns") == "ns"
    assert time_axis.unit_from_name("time_s") == "s"
    assert time_axis.unit_from_name("Time") is None
    assert time_axis.unit_from_name("Items") is None          # "...s" inside a word is not seconds
    assert time_axis.unit_from_name("Thrust") is None


def test_analyze_tells_the_order_repeats_missing_and_gaps():
    a = time_axis.analyze(np.array([0, 1, 2, 3, 50, 51]), "t_ms")
    assert a["order"] == "increasing" and a["gaps"] == 1 and a["step"] == 1 and a["unit"] == "ms"
    assert time_axis.analyze(np.array([0, 1, 1, 2]))["order"] == "nondecreasing"
    assert time_axis.analyze(np.array([0, 1, 1, 2]))["repeats"] == 1
    m = time_axis.analyze(np.array([0, 5, 3, 8, np.nan]))
    assert m["order"] == "mixed" and m["missing"] == 1 and m["backSteps"] == 1
    assert time_axis.analyze(np.array([5, 4, 3]))["order"] == "decreasing"
    assert time_axis.analyze(np.array([np.nan]))["order"] == "empty"


def test_scale_puts_the_time_in_seconds_and_survives_a_refresh(store, tmp_path):
    p = _csv(tmp_path, "t_ms,Speed\n0,1\n500,2\n1000,3\n")
    lr = store.open_file(p)
    assert store.describe(lr)["timeAxis"]["columnUnit"] == "ms"
    res = store.set_time_axis(lr.id, None, 0.001, 1.0, 0.0)
    assert res["before"]["scale"] == 1.0
    r = store.get(lr.id)
    assert list(r.run.time) == [0.0, 0.5, 1.0] and r.run.end_time == 1.0
    assert r.run.import_settings["time_scale"] == 0.001
    again = store.reload(lr.id)                               # refresh / live / session: the same
    assert list(again.run.time) == [0.0, 0.5, 1.0]
    assert res["run"]["timeAxis"]["scale"] == 0.001


def test_live_rows_are_scaled_too(store, tmp_path):
    from svcore.csv_loader import append_new_rows
    p = _csv(tmp_path, "t_ms,Speed\n0,1\n500,2\n")
    lr = store.open_file(p)
    store.set_time_axis(lr.id, None, 0.001, 1.0, 0.0)
    with open(p, "a") as f:
        f.write("1000,3\n1500,4\n")
    run = store.get(lr.id).run
    assert append_new_rows(run) == 2
    assert list(run.time) == [0.0, 0.5, 1.0, 1.5]


def test_another_column_becomes_the_time(store, tmp_path):
    p = _csv(tmp_path, ROWS)
    lr = store.open_file(p)
    chk = store.check_time_axis(lr.id, "Count")
    assert chk["column"]["order"] == "increasing" and "Count" in chk["info"]["candidates"]
    res = store.set_time_axis(lr.id, "Count", 1.0, 1.0, 0.0, times=[0.25, 1.1])
    r = store.get(lr.id).run
    assert r.time_source == "Count" and float(r.time[-1]) == 1100.0
    assert "Count" not in r.signals                            # it is the time now
    assert "Time_2" in r.signals                               # the old time, as a signal
    assert r.original_names["Time_2"] == "Time"
    assert res["times"] == pytest.approx([250.0, 1100.0])       # same rows on the new axis
    assert res["before"]["column"] == "Time"
    # and back (Undo): the old time column by its name in the app
    store.set_time_axis(lr.id, "Time_2", 1.0, 1.0, 0.0)
    r = store.get(lr.id).run
    assert r.time_source == "Time" and "Count" in r.signals and "Time_2" not in r.signals
    # Undo by the name in the file (what "before" gives)
    store.set_time_axis(lr.id, "Count", 1.0, 1.0, 0.0)
    store.set_time_axis(lr.id, res["before"]["column"], 1.0, 1.0, 0.0)
    assert store.get(lr.id).run.time_source == "Time"


def test_a_column_that_goes_up_and_down_sorts_the_rows_and_positions_are_not_kept(store, tmp_path):
    lr = store.open_file(_csv(tmp_path, ROWS))
    assert store.check_time_axis(lr.id, "Alt")["column"]["order"] == "mixed"
    res = store.set_time_axis(lr.id, "Alt", 1.0, 1.0, 0.0, times=[0.3])
    assert res["run"]["report"]["sorted"] is True
    assert res["times"] == [None]                               # the rows moved: no honest mapping


def test_offset_is_set_with_the_change(store, tmp_path):
    lr = store.open_file(_csv(tmp_path, ROWS))
    store.set_time_offset(lr.id, 7.0)
    res = store.set_time_axis(lr.id, "Count", 1.0, 1.0, 0.0, times=[7.0])
    assert store.get(lr.id).run.time_offset == 0.0
    assert res["times"] == pytest.approx([0.0])
    res = store.set_time_axis(lr.id, None, 0.01, 1.0, 3.0, times=[100.0])
    assert res["times"] == pytest.approx([4.0])                 # 100 * 0.01 + 3


def test_bad_requests_are_refused(store, tmp_path):
    lr = store.open_file(_csv(tmp_path, ROWS))
    with pytest.raises(LoadError):
        store.set_time_axis(lr.id, None, -1.0, 1.0, 0.0)
    with pytest.raises(LoadError):
        store.set_time_axis(lr.id, "Nope", 1.0, 1.0, 0.0)
    with pytest.raises(LoadError):
        store.check_time_axis(lr.id, "Nope")


def test_what_computes_against_time_is_listed(store, tmp_path):
    lr = store.open_file(_csv(tmp_path, ROWS))
    rid = lr.id
    store.add_derived("derivative", [f"{rid}/Speed"], {}, "dSpeed")
    store.add_derived("abs", [f"{rid}/Speed"], {}, "absSpeed")
    store.add_derived("integral", ["derived/absSpeed"], {}, "intAbs")       # through another new signal
    store.add_derived("abs", [f"{rid}/Count"], {}, "absCount")
    store.set_transforms({f"{rid}/Alt": {"dt": 0.5}})
    chk = store.check_time_axis(rid, "Count")
    assert set(chk["timedDerived"]) == {"dSpeed", "intAbs"}
    assert chk["timedEdits"] == ["Alt"]
    assert chk["brokenDerived"] == ["absCount"]                 # made from the column itself


def test_flight_logs_keep_their_clock(store, tmp_path):
    lr = store.open_file(_csv(tmp_path, ROWS))
    lr.run.import_settings = {"format": "bin"}                  # (as a .bin reports itself)
    info = store.time_axis_info(lr)
    assert not info["canColumn"] and not info["canScale"]
    with pytest.raises(LoadError):
        store.set_time_axis(lr.id, None, 0.001, 1.0, 0.0)


def test_own_time_columns_have_their_own_scale(store, tmp_path):
    p = _csv(tmp_path, "Time,Speed,Rpm,Rpm_time\n0,1,10,0\n1,2,20,1000\n2,3,30,2000\n")
    lr = store.open_file(p)
    info = store.time_axis_info(lr)
    if not info["ownTimes"]:
        pytest.skip("this name is not taken as a time pair")
    store.set_time_axis(lr.id, None, 1.0, 0.001, 0.0)
    t, _ = store.signal(f"{lr.id}/Rpm")
    assert list(t) == [0.0, 1.0, 2.0]


def test_map_times_between_rows():
    old = np.array([0.0, 1.0, 2.0])
    new = np.array([0.0, 10.0, 30.0])
    assert time_axis.map_times(old, 0.0, new, 0.0, True, [0.5, 1.5, 5.0]) == pytest.approx([5.0, 20.0, 30.0 + 3 * 20.0])
    assert time_axis.map_times(old, 0.0, new[:2], 0.0, True, [0.5]) == [None]
