"""Several things to optimize (owner, 2026-11-03): the Pareto levels (non-dominated sorting) agree
with the definition, in two objectives (sort and sweep) and in three (blocks); the balanced choice
is on the front; rankBy "pareto" ranks the front first, within it the closest to the ideal."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore import sweep  # noqa: E402
import svcore.sweep.io  # noqa: E402,F401
from svcore.sweep.analysis import pareto_levels  # noqa: E402


def _brute(m):
    n = len(m)
    level, left, k = np.zeros(n, int), set(range(n)), 1
    while left:
        on = [i for i in left if not any(np.all(m[j] >= m[i]) and np.any(m[j] > m[i]) for j in left)]
        for i in on:
            level[i] = k
        left -= set(on)
        k += 1
    return level


def test_levels_match_the_definition():
    rng = np.random.default_rng(3)
    for k in (2, 3):
        m = np.round(rng.normal(size=(300, k)), 1)       # rounded: ties on purpose
        assert np.array_equal(pareto_levels(m, max_level=1000), _brute(m))


def test_rank_by_pareto_and_knee():
    rows = []
    for p_ in range(1, 8):
        rows.append({"sc": "a", "p": p_, "up": p_, "down": 8 - p_})        # a trade-off: all on the front
    rows.append({"sc": "a", "p": 9, "up": 2, "down": 2})                    # dominated
    df = pd.DataFrame(rows)
    roles = {"sc": "hold", "p": "param", "up": "output", "down": "output"}
    up, dn = {"column": "up", "direction": "max"}, {"column": "down", "direction": "max"}
    q = {"roles": roles, "combine": "and", "holdValues": {}, "conditions": [], "derived": [], "outputAgg": {}, "exclude": [],
         "goal": up, "objectives": [{**up, "weight": 5}, {**dn, "weight": 1}]}
    d = sweep.answer(sweep.prepare(df, q), q)["data"]
    p = np.asarray(d["p"]).astype(int)
    assert set(p[np.asarray(d["#front"]) == 2]) == {9}
    knee = p[np.asarray(d["#knee"]) == 1]
    assert list(knee) == [4]                                                # the middle of the trade-off
    first = lambda d: int(p[np.nanargmin(np.asarray(d["#rank"], dtype=float))])  # noqa: E731
    assert first(d) == 7                                                    # the weights favour "up"
    d2 = sweep.answer(sweep.prepare(df, {**q, "rankBy": "pareto"}), {**q, "rankBy": "pareto"})["data"]
    r = np.asarray(d2["#rank"], dtype=float)
    assert r[p == 9][0] == r.max()                                          # the dominated set last
    # within the front the closest to the ideal (weighted) first
    assert first(d2) in (5, 6, 7)


def test_levels_are_fast_enough():
    """Ten thousand sets, three objectives: well under a few seconds (it took 46 s in blocks)."""
    import time
    m = np.random.default_rng(1).normal(size=(10000, 3))
    t0 = time.time()
    lv = pareto_levels(m)
    assert time.time() - t0 < 10 and lv.max() == 11
