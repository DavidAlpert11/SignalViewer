"""C1: Compare judges at full resolution, in both directions.

`pass`, `withinPct` and `maxAbsDiff` used to be computed on the baseline's samples strided down to
`max_points` (200k in the CLI, 20k-50k in the UI list), and the run was only looked at the baseline's
times - so a short excursion between those points passed. Both curves are piecewise linear between
their own samples, so judging on the union of both sample sets gives the exact largest difference."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.compare import compare  # noqa: E402


def _excursion_2m():
    t = np.arange(2_000_000) * 0.001                    # 2M samples at 1 kHz
    golden = np.sin(2 * np.pi * 0.01 * t)
    run = golden.copy()
    i = 1_234_567                                       # an index the old stride (10) skipped
    run[i:i + 5] += 5.0                                 # 5 ms at +5
    return t, golden, run


def test_short_excursion_in_2m_samples_fails():
    t, g, r = _excursion_2m()
    for max_points in (200_000, 20_000):                # the CLI's and the UI list's old grids
        row = compare([("g/X", t, g), ("n/X", t, r)], "g/X", "linear", 0.1, None, max_points=max_points)["rows"][0]
        assert row["pass"] is False
        assert abs(row["maxAbsDiff"] - 5.0) < 1e-9
        assert row["withinPct"] < 100.0


def test_violation_between_golden_samples_fails():
    """A 10 Hz golden run, a 1 kHz run with a spike between two golden samples."""
    tg = np.arange(0, 100, 0.1)
    tr = np.arange(0, 100, 0.001)
    g = np.sin(0.1 * tg)
    r = np.sin(0.1 * tr)
    r[(tr > 50.02) & (tr < 50.07)] += 2.0               # golden samples at 50.0 and 50.1
    row = compare([("g/X", tg, g), ("n/X", tr, r)], "g/X", "linear", 0.1, None)["rows"][0]
    assert row["pass"] is False and row["maxAbsDiff"] > 1.9


def test_violation_in_a_faster_golden_run_fails():
    """The other direction: the golden run has the feature between the run's samples."""
    tg = np.arange(0, 100, 0.001)
    tr = np.arange(0, 100, 0.1)
    g = np.sin(0.1 * tg)
    g[(tg > 50.02) & (tg < 50.07)] += 2.0
    row = compare([("g/X", tg, g), ("n/X", tr, np.sin(0.1 * tr))], "g/X", "linear", 0.1, None)["rows"][0]
    assert row["pass"] is False


def test_identical_runs_at_different_rates_pass():
    """Linear interpolation of a smooth signal at 10 Hz vs 1 kHz: small, inside a sane band."""
    tg = np.arange(0, 100, 0.1)
    tr = np.arange(0, 100, 0.001)
    row = compare([("g/X", tg, np.sin(0.1 * tg)), ("n/X", tr, np.sin(0.1 * tr))], "g/X", "linear", 0.01, None)["rows"][0]
    assert row["pass"] is True


def test_mean_baseline_sees_a_short_excursion():
    t, g, r = _excursion_2m()
    t, g, r = t[:400_000], g[:400_000], r[:400_000]
    r2 = r.copy()
    r2[234_567:234_572] += 5.0
    rows = compare([("a/X", t, g), ("b/X", t, g), ("c/X", t, r2)], "mean", "linear", 0.1, None, max_points=20_000)["rows"]
    assert any(x["pass"] is False for x in rows)


def test_time_tolerance_still_works_at_full_resolution():
    t = np.arange(0, 10, 0.0001)                        # 100k samples, more than a 20k grid
    golden = np.where((t % 2) < 1, 0.0, 5.0)
    late = np.where((np.maximum(t - 0.05, 0) % 2) < 1, 0.0, 5.0)
    s = [("g/S", t, golden), ("n/S", t, late)]
    assert compare(s, "g/S", "linear", 0.1, None, max_points=20_000)["rows"][0]["pass"] is False
    assert compare(s, "g/S", "linear", 0.1, None, tol_time=0.1, max_points=20_000)["rows"][0]["pass"] is True
    assert compare(s, "g/S", "linear", None, None, tol_time=0.02, max_points=20_000)["rows"][0]["pass"] is False


def test_trace_marks_the_short_excursion():
    t, g, r = _excursion_2m()
    row = compare([("g/X", t, g), ("n/X", t, r)], "g/X", "linear", 0.1, None, trace=500)["rows"][0]
    tr = row["trace"]
    assert len(tr["t"]) <= 1100                         # still decimated for drawing
    assert max(v for v in tr["d"] if v is not None) > 4.9
    assert len(tr["out"]) == 1 and abs(tr["out"][0][0] - 1234.567) < 0.002
