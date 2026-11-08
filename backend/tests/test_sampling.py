"""26.A3: filters and moving windows follow TIME, not the sample count - a gap in the data is not
filtered across, a change of logging rate does not change the filter, and a smooth / RMS window is in
seconds. Recipes saved before 1.23 keep their numbers (`sampling: "samples"`)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.analysis import compute, time_moving_average  # noqa: E402
from svcore.formula import evaluate  # noqa: E402
from svcore.ops import apply_filter  # noqa: E402


def _gap_step():
    """0 for 10 s, a 2 s logger pause, then 10 for 10 s (the step happens inside the pause)."""
    t = np.r_[np.arange(0, 10, 0.01), np.arange(12, 22, 0.01)]
    y = np.where(t < 11, 0.0, 10.0)
    return t, y


def test_a_lowpass_is_not_run_across_a_gap():
    t, y = _gap_step()
    out = apply_filter(t, y, "lowpass", 1.0)
    before, after = out[t < 10], out[t > 12]
    assert np.max(np.abs(before)) < 1e-6 and np.max(np.abs(after - 10)) < 1e-6
    old = apply_filter(t, y, "lowpass", 1.0, sampling="samples")       # the samples as if adjacent
    assert np.max(np.abs(old[t < 10])) > 1


def test_a_rate_change_does_not_change_the_filter():
    """100 Hz for 10 s, then 10 Hz for 10 s: a 2 Hz tone through a 5 Hz low-pass keeps its amplitude in
    both halves (sample-based, the 10 Hz half's tone looked like 20 Hz to the filter and was cut)."""
    t = np.r_[np.arange(0, 10, 0.01), np.arange(10, 20, 0.1)]
    y = np.sin(2 * np.pi * 2 * t)
    out = apply_filter(t, y, "lowpass", 5.0)
    slow = (t > 12) & (t < 18)
    assert np.max(np.abs(out[slow])) > 0.8
    old = apply_filter(t, y, "lowpass", 5.0, sampling="samples")
    assert np.max(np.abs(old[slow])) < 0.3


def test_filters_on_even_data_are_unchanged():
    t = np.arange(0, 10, 0.001)
    y = np.sin(2 * np.pi * 3 * t) + 0.3 * np.sin(2 * np.pi * 80 * t)
    assert np.allclose(apply_filter(t, y, "lowpass", 20.0), apply_filter(t, y, "lowpass", 20.0, sampling="samples"), atol=1e-9)


def test_smooth_and_rms_windows_in_seconds():
    t = np.r_[np.arange(0, 5, 0.01), np.arange(5, 10, 0.1)]            # the rate changes
    y = np.sin(t) + (t > 5)
    _, s = compute("smooth", [(t, y)], {"seconds": 0.5})
    assert np.allclose(s, time_moving_average(t, y, 0.5), equal_nan=True)
    _, r = compute("rms", [(t, y)], {"seconds": 0.5})
    assert np.allclose(r, np.sqrt(time_moving_average(t, y * y, 0.5)), equal_nan=True)
    _, old = compute("smooth", [(t, y)], {"window": 50, "sampling": "samples"})   # 50 samples, as before
    assert not np.allclose(old, s, equal_nan=True)


def test_formulas_and_legacy():
    t, y = _gap_step()
    new = evaluate("lowpass(v0, 1)", [(t, y)], None)[1]
    old = evaluate("lowpass(v0, 1)", [(t, y)], None, nan="legacy")[1]     # a change saved before 1.23
    assert np.max(np.abs(new[t < 10])) < 1e-6 and np.max(np.abs(old[t < 10])) > 1
    s = evaluate("smooth_s(v0, 0.5)", [(t, y)], None)[1]
    assert np.allclose(s, time_moving_average(t, y, 0.5), equal_nan=True)


def test_old_recipes_keep_their_numbers_new_ones_follow_time(tmp_path):
    from app.store import Store
    csv = tmp_path / "g.csv"
    t, y = _gap_step()
    csv.write_bytes(("time,y\n" + "".join(f"{a:.2f},{b}\n" for a, b in zip(t, y))).encode())
    s = Store()
    sid = f"{s.open_file(str(csv)).id}/y"
    old = s.add_derived("lowpass", [sid], {"cutoff": 1.0}, "old", legacy=True)
    new = s.add_derived("lowpass", [sid], {"cutoff": 1.0}, "new")
    assert old.params["sampling"] == "samples" and new.params["sampling"] == "time"
    to, yo = s.signal("derived/old")
    tn, yn = s.signal("derived/new")
    assert np.max(np.abs(yo[to < 10])) > 1 and np.max(np.abs(yn[tn < 10])) < 1e-6
    sm = s.add_derived("smooth", [sid], {"window": 20}, "sm_old", legacy=True)
    assert sm.params["sampling"] == "samples"
