"""U5: the Compare panel's difference view - each run's difference over time with the tolerance band
and the stretches outside it (svcore.compare.compare(..., trace=N))."""
import numpy as np

from svcore.compare import compare


def _series():
    t = np.linspace(0, 10, 10001)
    base = np.sin(t)
    other = base + np.where((t > 4) & (t < 5), 0.5, 0.0)       # 0.5 off between 4 and 5 s
    return [("a/X", t, base), ("b/X", t, other)]


def test_trace_band_and_the_stretch_outside():
    r = compare(_series(), "a/X", tol_abs=0.1, trace=300)
    row = r["rows"][0]
    tr = row["trace"]
    assert len(tr["t"]) <= 2 * 300 + 2 and len(tr["t"]) == len(tr["d"]) == len(tr["lo"]) == len(tr["hi"])
    assert all(abs(h - 0.1) < 1e-9 for h in tr["hi"]) and all(abs(lo + 0.1) < 1e-9 for lo in tr["lo"])
    assert len(tr["out"]) == 1 and abs(tr["out"][0][0] - 4.0) < 0.01 and abs(tr["out"][0][1] - 5.0) < 0.01
    assert max(tr["d"]) >= 0.5 - 1e-9                          # the step kept by the min / max buckets
    assert not row["pass"] and abs(row["withinPct"] - 90.0) < 0.2


def test_no_tolerance_no_band_and_no_trace_unless_asked():
    r = compare(_series(), "a/X", trace=100)
    assert "lo" not in r["rows"][0]["trace"] and r["rows"][0]["trace"]["out"] == []
    assert "trace" not in compare(_series(), "a/X", tol_abs=0.1)["rows"][0]


def test_time_tolerance_widens_the_band_where_the_baseline_moves():
    t = np.linspace(0, 10, 1001)
    base = np.where(t >= 5, 1.0, 0.0)
    late = np.where(t >= 5.05, 1.0, 0.0)                         # 50 ms late
    r = compare([("a/S", t, base), ("b/S", t, late)], "a/S", tol_abs=0.01, tol_time=0.1, trace=200)
    row = r["rows"][0]
    assert row["pass"] and row["trace"]["out"] == []
