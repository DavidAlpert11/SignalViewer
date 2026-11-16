"""S1 (PLAN_2026-11-17 §2a): a Sweeps column with conditions and text - if, comparisons, and / or / not,
in, between, contains, text(), bins, rank / pct; a text column is a scenario; share per set."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svcore import sweep  # noqa: E402
from svcore.sweep.derived import row_formula  # noqa: E402

DF = pd.DataFrame({"wind": [2.0, 9.0, np.nan, 5.0], "name": ["mildA", "strongB", None, "mild"], "kp": [1, 2, 3, 4]})


def _eq(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])


def test_if_text_and_nested():
    assert list(row_formula(DF, 'if(wind > 8, "high", "low")')) == ["low", "high", None, "low"]
    assert _eq(row_formula(DF, "if(kp > 2, if(kp > 3, 1, 2), 3)"), [3, 3, 2, 1])
    assert _eq(row_formula(DF, "where(wind > 4, kp, nan)"), [np.nan, 2, np.nan, 4])   # the older name
    assert _eq(row_formula(DF, '"if(" == "if("'), [1, 1, 1, 1])                         # text is not rewritten


def test_comparisons_and_logic_with_missing_values():
    assert _eq(row_formula(DF, "0 < wind <= 5"), [1, 0, np.nan, 1])
    assert _eq(row_formula(DF, "between(wind, 2, 5)"), [1, 0, np.nan, 1])
    assert _eq(row_formula(DF, "not (wind > 3)"), [1, 0, np.nan, 0])
    assert _eq(row_formula(DF, "wind > 3 and kp > 1"), [0, 1, np.nan, 1])
    assert _eq(row_formula(DF, "wind > 3 or kp > 1"), [0, 1, 1, 1])          # a known true decides
    assert _eq(row_formula(DF, "kp in (1, 3)"), [1, 0, 1, 0])
    assert _eq(row_formula(DF, "kp not in (1, 3)"), [0, 1, 0, 1])


def test_text_columns():
    assert _eq(row_formula(DF, 'name == "mild"'), [0, 0, np.nan, 1])
    assert _eq(row_formula(DF, 'name != "mild"'), [1, 1, np.nan, 0])
    assert _eq(row_formula(DF, 'name in ("mild", "strongB")'), [0, 1, np.nan, 1])
    assert _eq(row_formula(DF, 'contains(name, "B")'), [0, 1, np.nan, 0])
    assert list(row_formula(DF, "text(kp)")) == ["1", "2", "3", "4"]


def test_bins_rank_pct():
    assert list(row_formula(DF, "bins(wind, [0, 5, 10])")) == ["0–5", "5–10", None, "5–10"]
    assert list(row_formula(DF, "bins(kp, [2])")) == ["<2", "≥2", "≥2", "≥2"]
    assert _eq(row_formula(DF, "rank(kp)"), [1, 2, 3, 4])
    assert _eq(row_formula(DF, "pct(kp)"), [25, 50, 75, 100])


@pytest.mark.parametrize("bad", ['name > "a"', 'text(kp) + "x"', 'name == 3', "bins(kp, [5, 1])", "if(kp > 1, 2)",
                                 'if(kp > 1, "a", 2)', "__import__('os')", "kp.real", "[1][0]", "lambda: 1"])
def test_clear_errors(bad):
    with pytest.raises(sweep.DerivedError):
        row_formula(DF, bad)


def _grid():
    rows = []
    for wind in (2.0, 6.0, 10.0):
        for p in (1.0, 2.0, 3.0):
            rows.append({"p": p, "wind": wind, "out": 10 * p - wind})
    return pd.DataFrame(rows)


def test_a_text_column_is_a_scenario():
    q = {"roles": {"p": "param", "wind": "ignore", "out": "output"},
         "derived": [{"name": "gust", "kind": "row", "expr": 'if(wind > 5, "strong", "mild")'}],
         "conditions": [{"column": "out", "op": ">=", "value": 5}]}
    p = sweep.prepare(_grid(), q)
    assert "gust" in p.holds and "gust" not in p.outputs
    assert p.n_combos == 2
    # kept values of the new scenario: only "mild" (wind 2) -> out = 10p - 2 >= 5 for p >= 1
    q2 = {**q, "holdValues": {"gust": ["mild"]}}
    a = sweep.answer(sweep.prepare(_grid(), q2), q2)
    assert a["counts"]["holding"] == 3
    a = sweep.answer(p, q)                          # both: the worst is wind 10 -> p >= 2 (10*2-10 = 10 >= 5)
    assert a["counts"]["holding"] == 2


def test_a_number_column_as_a_scenario_and_share_per_set():
    q = {"roles": {"p": "param", "wind": "ignore", "out": "output"},
         "derived": [{"name": "windy", "kind": "row", "expr": "wind >= 6", "role": "hold"},
                     {"name": "ok", "kind": "row", "expr": "out >= 5"},
                     {"name": "ok_share", "kind": "set", "op": "share", "column": "ok"},
                     {"name": "ok_n", "kind": "set", "op": "count_true", "column": "ok"}]}
    p = sweep.prepare(_grid(), q)
    assert "windy" in p.holds and "ok" in p.outputs
    order = np.argsort(p.df["p"].to_numpy()[p.first_row])
    # p = 1: out 8, 4, 0 -> 1 of 3; p = 2: 18, 14, 10 -> 3 of 3
    assert np.allclose(p.set_cols["ok_share"][order], [1 / 3, 1, 1])
    assert np.allclose(p.set_cols["ok_n"][order], [1, 3, 3])


def test_preview_says_text_and_ranks_the_whole_table(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    f = tmp_path / "t.csv"
    _grid().to_csv(f, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(f)}).json()["id"]
    r = c.post("/api/sweep/formula-preview", json={"id": tid, "expr": 'if(wind > 5, "strong", "mild")'}).json()
    assert r == {"ok": True, "value": "mild", "text": True}
    r = c.post("/api/sweep/formula-preview", json={"id": tid, "expr": "pct(out)"}).json()
    assert r["ok"] and r["value"] < 100                  # of the whole table, not of the first run alone
    r = c.post("/api/sweep/formula-preview", json={"id": tid, "expr": 'out > "a"'}).json()
    assert not r["ok"] and "Text" in r["error"]


def test_evaluate_lists_a_new_scenario_and_its_values(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    f = tmp_path / "t.csv"
    _grid().to_csv(f, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(f)}).json()["id"]
    q = {"roles": {"p": "param", "wind": "ignore", "out": "output"}, "holdValues": {"gust": ["mild"]},
         "derived": [{"name": "gust", "kind": "row", "expr": 'if(wind > 5, "strong", "mild")'}]}
    r = c.post("/api/sweep/evaluate", json={"id": tid, "question": q}).json()
    assert r["newHolds"] == {"gust": ["mild", "strong"]}      # every value, not only the kept one
    assert r["counts"]["sets"] == 3
