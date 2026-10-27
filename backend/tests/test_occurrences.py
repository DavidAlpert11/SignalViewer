"""Investigation step 3: the stretches of a condition looked at together."""
import numpy as np

from app.store import Store
from svcore.occurrences import differ_one, inside_mask, occurrence_stats, windows


def test_stats_per_stretch():
    t = np.arange(10.0)
    y = np.array([0, 1, 5, 2, 0, 0, 3, 9, 1, 0], float)
    s = occurrence_stats(t, y, [(1, 3), (6, 8)])
    assert s[0]["max"] == 5 and s[0]["tMax"] == 2 and s[1]["max"] == 9 and s[1]["mean"] == np.mean([3, 9, 1])


def test_windows_line_up_the_stretches():
    t = np.arange(0, 20, 0.1)
    y = np.zeros_like(t)
    y[(t >= 3) & (t < 4)] = 1
    y[(t >= 12) & (t < 13)] = 1
    w = windows(t, y, [(3, 4), (12, 13)], "start", 0.5, 101)
    g = np.array(w["grid"])
    c0, c1 = (np.array([np.nan if v is None else v for v in c]) for c in w["curves"])
    at = np.argmin(np.abs(g - 0.5))
    assert c0[at] == 1 and c1[at] == 1 and w["mean"][at] == 1           # both "on" half a second in
    assert c0[np.argmin(np.abs(g + 0.3))] == 0                          # the padding before the start
    assert g[0] < 0 < g[-1]


def test_differ_ranks_what_changes_inside():
    t = np.arange(0, 100, 0.1)
    iv = [(20, 30), (60, 70)]
    m = inside_mask(t, iv)
    rng = np.random.default_rng(0)
    hot = rng.normal(0, 1, len(t)) + 8 * m                                # clearly higher inside
    calm = rng.normal(0, 1, len(t))
    assert differ_one(t, hot, iv)[0] > 5 > differ_one(t, calm, iv)[0]


def test_store_table_and_differ(tmp_path):
    p = tmp_path / "r.csv"
    rows = "".join(f"{i * 0.5},{5 if 10 <= i < 20 else 1},{i % 3}\n" for i in range(60))
    p.write_text("Time,Load,Noise\n" + rows)
    st = Store()
    rid = st.open_file(str(p)).id
    iv = st.evaluate_condition("Load > 3", run_ids=[rid])[rid]["intervals"]
    table = st.occurrence_rows({rid: iv}, ["Load"])
    assert len(table) == 1 and table[0]["values"]["Load"]["max"] == 5
    top = st.occurrence_differ({rid: iv})
    assert top[0]["name"] == "Load" and top[0]["up"]
    ov = st.occurrence_windows([{"sig": f"{rid}/Load", "intervals": iv}], "start", 0.5)
    assert len(ov[0]["curves"]) == 1 and len(ov[0]["grid"]) == 400
