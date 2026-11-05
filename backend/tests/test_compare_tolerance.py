"""The tolerance band of a comparison: the larger of abs and pct x |golden| (as the Simulink Data
Inspector). The smaller closed the band to 0 where the golden value crossed 0."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.compare import metrics  # noqa: E402


def test_band_is_the_larger_of_abs_and_pct():
    t = np.linspace(0, 10, 1001)
    golden = 10 * np.sin(t)                       # crosses 0
    run = golden + 0.2                            # 0.2 off everywhere
    assert metrics(golden, run, 0.5, None)["pass"]
    assert metrics(golden, run, 0.5, 5.0)["pass"]           # adding pct no longer tightens abs
    m = metrics(golden, run, None, 5.0)                     # pct alone: fails near the zero crossings
    assert not m["pass"] and 50 < m["withinPct"] < 100
    big = golden + np.where(np.abs(golden) > 9.5, 0.45, 0.0)  # 0.45 off where |golden| > 9.5: within 5 % there
    assert metrics(golden, big, 0.1, 5.0)["pass"] and not metrics(golden, big, 0.1, None)["pass"]


def test_time_tolerance_as_the_simulink_data_inspector():
    """A run 50 ms late fails a tight value tolerance at every fast change; with a time tolerance of
    0.1 s the baseline's band is its lowest / highest within +-0.1 s, and it passes."""
    from svcore.compare import compare
    t = np.arange(0, 10, 0.01)
    golden = np.where((t % 2) < 1, 0.0, 5.0)                  # a square wave: steep steps
    late = np.where((np.maximum(t - 0.05, 0) % 2) < 1, 0.0, 5.0)
    r = compare([("g", t, golden), ("n", t, late)], "g", "linear", 0.1, None)["rows"][0]
    assert not r["pass"]
    r = compare([("g", t, golden), ("n", t, late)], "g", "linear", 0.1, None, tol_time=0.1)["rows"][0]
    assert r["pass"]
    r = compare([("g", t, golden), ("n", t, late)], "g", "linear", None, None, tol_time=0.02)["rows"][0]
    assert not r["pass"]                                      # 20 ms is not enough for 50 ms late
