"""svcore/sweep/density.py: every run counted in the picture, the outliers drawn one by one, the charts' numbers of
every run (CLAUDE.md: no point is ever left out of a picture)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.sweep import density  # noqa: E402


def _table(n=200_000, seed=2):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"a": rng.normal(0, 1, n), "b": rng.normal(5, 2, n),
                       "c": np.array(["x", "y", "z"])[rng.integers(0, 3, n)]})
    df.loc[123_457, "b"] = 60.0                                # the needle: one run far out on b
    return df


def _edges(lo, hi, k=64):
    return {"edges": np.linspace(lo, hi, k + 1).tolist()}


def test_parallel_counts_every_run_and_draws_the_outlier():
    df = _table()
    keep = (df.a > -1).to_numpy()
    axes = [{"column": "a", **_edges(-5, 5)}, {"column": "b", **_edges(-5, 65)}, {"column": "c", "labels": ["x", "y", "z"]}]
    r = density.parallel(df, axes, keep)
    for p in r["pairs"]:
        assert sum(p["kept"]["n"]) == int(keep.sum()) and sum(p["out"]["n"]) == int((~keep).sum())
    assert 123_457 in r["sparse"].tolist() and len(r["sparse"]) < 5000
    assert r["cells"] == [65, 65, 4]


def test_a_value_outside_the_edges_or_missing_is_in_the_missing_cell():
    s = pd.Series([1.0, np.nan, 99.0, 0.0, 2.0])
    assert density.cells(s, {"edges": [0.0, 1.0, 2.0]}).tolist() == [1, 2, 2, 0, 1]
    assert density.cells(pd.Series(["y", None, "q"]), {"labels": ["x", "y"]}).tolist() == [1, 2, 2]


def test_scatter_grid_counts_every_run_and_draws_the_outlier():
    df = _table()
    keep = np.ones(len(df), bool)
    g = density.grid2d(df.a, df.b, _edges(-5, 5, 200), _edges(-5, 65, 200), keep)
    assert sum(g["n"]) == len(df) and 123_457 in g["sparse"].tolist()


def test_the_charts_numbers_are_of_every_run():
    df = _table()
    v = df.b.to_numpy()
    ser = (df.c == "y").to_numpy().astype(np.int64)
    h = density.histogram(v, -5, 65, 30, ser, 2)
    at = int((60.0 + 5) // (70 / 30))
    assert sum(map(sum, h)) == len(df) and h[0][at] + h[1][at] >= 1 and sum(h[0][at - 3:] + h[1][at - 3:]) == 1   # the needle, alone
    b = density.box(v)
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    assert abs(b["q1"] - q1) < 1e-9 and abs(b["med"] - med) < 1e-9 and 60.0 in b["out"]
    r = density.correlation([df.a.to_numpy(), df.b.to_numpy()], "pearson")
    assert abs(r[0][1] - np.corrcoef(df.a, df.b)[0, 1]) < 1e-9
    rho = density.correlation([df.a.to_numpy(), df.b.to_numpy()], "spearman")[0][1]
    assert abs(rho - df.a.rank().corr(df.b.rank())) < 1e-9
