"""The Data step's tables (owner, 2026-11-02): each table of a study apart, and merging as an
explicit step that makes a NEW table - rows added (concat) or side by side on key columns (join),
with an optional source column and duplicates removed; the merged table made again from its recipe."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore import sweep  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
EXAMPLE = os.path.join(DATA, "sweep_payload.csv")
REFINE = os.path.join(DATA, "sweep_payload_refine.csv")


def _a():
    return pd.DataFrame({"k": [1.0, 2.0, 3.0], "wind": [0, 5, 5], "err": [0.1, 0.2, 0.3]})


def _b():
    return pd.DataFrame({"k": [3.0, 4.0], "wind": [5, 5], "err": [0.3, 0.4], "gust": ["mild", "strong"]})


def test_concat_fills_missing_columns_with_nan_and_names_the_source():
    m = sweep.combine([_a(), _b()], ["a.csv", "b.csv"], "concat", source="_source")
    assert len(m) == 5 and list(m["_source"]) == ["a.csv"] * 3 + ["b.csv"] * 2
    assert m["gust"].isna().sum() == 3                       # a.csv has no gust column: empty there
    no_src = sweep.combine([_a(), _b()], ["a", "b"])
    assert "_source" not in no_src.columns                   # only when asked for
    dd = sweep.combine([_a(), _a()], ["a", "b"], dedupe=True)
    assert len(dd) == 3                                       # the same rows twice: once
    kept = sweep.combine([_a(), _a()], ["a", "b"], source="from", dedupe=True)
    assert len(kept) == 6                                     # the source column makes them differ


def test_join_on_keys_side_by_side():
    left = pd.DataFrame({"k": [1, 2, 3], "roll": [0.1, 0.2, 0.3]})
    right = pd.DataFrame({"k": [2, 3, 4], "roll": [1.2, 1.3, 1.4], "energy": [20, 30, 40]})
    j = sweep.combine([left, right], ["sim.csv", "hw.csv"], "join", keys=["k"])
    assert sorted(j["k"]) == [1, 2, 3, 4]                     # an outer join: every key once
    assert {"roll [sim.csv]", "roll [hw.csv]", "energy"} <= set(j.columns)
    row = j[j["k"] == 1].iloc[0]
    assert row["roll [sim.csv]"] == pytest.approx(0.1) and np.isnan(row["energy"])
    with pytest.raises(sweep.SweepError):
        sweep.combine([left, right], ["a", "b"], "join", keys=["missing"])
    with pytest.raises(sweep.SweepError):
        sweep.combine([left], ["a"])


def test_preview_says_rows_and_columns_some_tables_lack():
    p = sweep.combine_preview([_a(), _b()], ["a", "b"], "concat", source="_source")
    assert p["rows"] == 5 and p["partial"] == ["gust"] and not p["error"]
    bad = sweep.combine_preview([_a(), _b()], ["a", "b"], "join", keys=[])
    assert bad["error"]


def test_recipe_builds_the_same_table_again():
    recipe = {"merge": {"parts": [{"path": EXAMPLE}, {"path": REFINE}], "names": ["first", "refine"], "how": "concat", "source": "_source"}}
    df = sweep.build(recipe)
    assert len(df) == len(sweep.read_table(EXAMPLE)) + len(sweep.read_table(REFINE))
    assert sweep.recipe_files(recipe) == [EXAMPLE, REFINE]


def test_routes_combine_build_values_preview_export(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    a = c.post("/api/sweep/open", json={"path": EXAMPLE}).json()
    b = c.post("/api/sweep/open", json={"path": REFINE}).json()
    assert a["recipe"] == {"path": EXAMPLE}
    body = {"ids": [a["id"], b["id"]], "names": ["sweep_payload.csv", "refine.csv"], "source": "_source"}
    pv = c.post("/api/sweep/combine", json={**body, "preview": True}).json()
    assert pv["rows"] == a["rows"] + b["rows"]
    m = c.post("/api/sweep/combine", json={**body, "name": "merged (2 tables)"}).json()
    assert m["rows"] == pv["rows"] and m["id"] not in (a["id"], b["id"]) and m["name"] == "merged (2 tables)"
    assert any(col["name"] == "_source" for col in m["columns"])
    # the parts are untouched
    assert c.post("/api/sweep/summary", json={"id": a["id"], "roles": {}}).json()["rows"] == a["rows"]
    # made again from its recipe (a saved study opened again), and read again (reload)
    again = c.post("/api/sweep/build", json={"recipe": m["recipe"], "name": "merged"}).json()
    assert again["rows"] == m["rows"]
    assert c.post("/api/sweep/reload", json={"path": m["id"]}).json()["rows"] == m["rows"]
    assert c.get(f"/api/sweep/changed?id={m['id']}").json()["changed"] is False
    # a condition's values with their runs; the run count of the kept values
    roles = {col["name"]: col["role"] for col in a["columns"]}
    hold = next(n for n, r in roles.items() if r == "hold")
    vals = c.post("/api/sweep/values", json={"id": a["id"], "column": hold}).json()
    assert sum(n for _, n in vals["values"]) == a["rows"]
    first = vals["values"][0]
    s = c.post("/api/sweep/summary", json={"id": a["id"], "roles": roles, "holdValues": {hold: [first[0]]}}).json()
    assert s["rows"] == first[1] and s["rowsAll"] == a["rows"]
    # a formula's value in the first run, or what is wrong with it
    num = next(col["name"] for col in a["columns"] if col["kind"] == "number")
    ok = c.post("/api/sweep/formula-preview", json={"id": a["id"], "expr": f"{num} * 2"}).json()
    assert ok["ok"] and ok["value"] == pytest.approx(2 * a["head"][0][[col["name"] for col in a["columns"]].index(num)])
    bad = c.post("/api/sweep/formula-preview", json={"id": a["id"], "expr": "nope + 1"}).json()
    assert not bad["ok"] and "nope" in bad["error"]
    # export: CSV, and the HTML page starting from the view on screen
    r = c.post("/api/sweep/export-table", json={"id": m["id"], "path": str(tmp_path / "m"), "format": "csv"}).json()
    assert r["path"].endswith(".csv") and len(open(r["path"]).read().splitlines()) == m["rows"] + 1
    h = c.post("/api/sweep/export-table", json={"id": a["id"], "path": str(tmp_path / "p.html"), "format": "html", "axes": [num, hold],
                                               "view": {"colorBy": num, "filters": {hold: {"kind": "values", "values": [first[0]]}}, "zoom": {"k": 2}}}).json()
    page = open(h["path"], encoding="utf-8").read()
    assert '"colorBy": "' + num in page and '"k": 2.0' in page and "zreset" in page
    assert c.post("/api/sweep/drop", json={"path": b["id"]}).json()["ok"]
    assert c.post("/api/sweep/summary", json={"id": b["id"], "roles": {}}).status_code == 404


def test_rerun_for_one_value_of_a_split_condition(tmp_path):
    """Split by: a set chosen for one value of a condition is written with the combinations that
    have that value only, beside the sets chosen for all of them."""
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    a = c.post("/api/sweep/open", json={"path": EXAMPLE}).json()
    roles = {col["name"]: col["role"] for col in a["columns"]}
    holds = [n for n, r in roles.items() if r == "hold"]
    params = [n for n, r in roles.items() if r == "param"]
    q = {"roles": roles}
    vals = c.post("/api/sweep/values", json={"id": a["id"], "column": holds[0]}).json()["values"]
    v0 = vals[0][0]
    first = {pn: a["head"][0][[col["name"] for col in a["columns"]].index(pn)] for pn in params}
    r = c.post("/api/sweep/export", json={"id": a["id"], "question": q, "sets": [0], "path": str(tmp_path / "r.csv"),
                                           "extra": [{"params": first, "holds": {holds[0]: v0}}]}).json()
    lines = open(r["path"]).read().splitlines()
    whole = c.post("/api/sweep/export", json={"id": a["id"], "question": q, "sets": [0], "path": str(tmp_path / "w.csv")}).json()["rows"]
    assert r["rows"] == whole + whole // len(vals)          # the extra: only the combinations with v0
    assert len(lines) == r["rows"] + 1
