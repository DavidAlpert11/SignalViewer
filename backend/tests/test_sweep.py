"""Sweeps area (svcore/sweep.py, app/routes/sweep.py): reading, describing and guessing roles of a
results table - parameters and scenario columns first, outputs last."""
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore import sweep  # noqa: E402
import svcore.sweep.io  # noqa: E402,F401

EXAMPLE = os.path.join(os.path.dirname(__file__), "data", "sweep_payload.csv")


def _table(n_sets_rep=1):
    rows = []
    for rep in range(n_sets_rep):
        for sc in ("a", "b", "c"):
            for p in (1.0, 2.0, 3.0):
                for k in (0.1, 0.2):
                    rows.append({"scenario": sc, "p": p, "k": k, "out": p * 10 + k + np.random.rand(), "ver": "1", "ok": int(p < 3)})
    return pd.DataFrame(rows)


def test_roles_mixed_inputs_then_outputs():
    df = _table()
    cols = {c["name"]: c for c in sweep.describe(df)}
    assert cols["scenario"]["role"] == "hold"
    assert cols["p"]["role"] == "param" and cols["k"]["role"] == "param"
    assert cols["out"]["role"] == "output"
    assert cols["ok"]["role"] == "output"           # after the first output: an output, though it has 2 values
    assert cols["ver"]["role"] == "ignore" and cols["ver"]["constant"]
    assert cols["scenario"]["scale"] == "category"


def test_example_table_guess_and_summary():
    df = sweep.read_table(EXAMPLE)
    cols = sweep.describe(df)
    roles = {c["name"]: c["role"] for c in cols}
    assert [c for c, r in roles.items() if r == "hold"] == ["scenario_terrain", "scenario_wind_mps", "scenario_mission"]
    assert [c for c, r in roles.items() if r == "param"] == ["payload_kg", "kp_roll", "cruise_mps", "controller"]
    assert roles["sim_version"] == "ignore"
    s = sweep.summary(df, roles)
    assert s["sets"] == 150 and s["combos"] == 18
    assert s["missing"] > 0 and s["complete"] + s["missing"] == 150      # the example drops a few runs
    assert s["failedRuns"] > 0                                            # and has runs with no outputs


def test_summary_missing_and_duplicates():
    df = _table()
    df = pd.concat([df.iloc[1:], df.iloc[[5]]])          # one run gone, one run twice
    roles = {"scenario": "hold", "p": "param", "k": "param", "out": "output", "ver": "ignore", "ok": "output"}
    s = sweep.summary(df, roles)
    assert s["sets"] == 6 and s["combos"] == 3
    assert s["missing"] == 1 and s["duplicates"] == 1


def test_big_csv_is_cached_as_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(sweep.io, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(sweep.io, "CACHE_MIN_BYTES", 0)
    f = tmp_path / "t.csv"
    _table(5).to_csv(f, index=False)
    a = sweep.read_table(str(f))
    assert len(os.listdir(tmp_path / "cache")) == 1
    b = sweep.read_table(str(f))                         # from the copy
    assert a.shape == b.shape and list(a.columns) == list(b.columns)
    os.utime(f, (1, 1))                                  # the file changed: a new copy, not the old one
    sweep.read_table(str(f))
    assert len(os.listdir(tmp_path / "cache")) == 2


def test_routes_open_and_summary():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    p = c.get("/api/sweep/example").json()["path"]
    assert p.endswith("drone_tuning.csv")
    r = c.post("/api/sweep/open", json={"path": EXAMPLE}).json()
    assert r["rows"] > 2000 and len(r["head"]) == 20 and r["summary"]["sets"] == 150
    roles = {col["name"]: col["role"] for col in r["columns"]}
    roles["controller"] = "hold"                         # the user moves a column
    s = c.post("/api/sweep/summary", json={"id": r["id"], "roles": roles}).json()
    assert s["combos"] == 36 and s["sets"] == 75
    assert c.post("/api/sweep/open", json={"path": "/no/such.csv"}).status_code == 400


# ----------------------------------------------------------------------------- the question
def _grid():
    """2 params (p: 1,2,3 ; k: 0.1,0.2) x scenario a,b,c. out = 10p - (scenario c: 5)."""
    rows = []
    for sc in ("a", "b", "c"):
        for p in (1.0, 2.0, 3.0):
            for k in (0.1, 0.2):
                rows.append({"scenario": sc, "p": p, "k": k, "out": 10 * p - (5 if sc == "c" else 0) + k, "risk": p * (2 if sc == "b" else 1)})
    return pd.DataFrame(rows)


ROLES = {"scenario": "hold", "p": "param", "k": "param", "out": "output", "risk": "output"}


def _ans(df, **q):
    q = {"roles": ROLES, **q}
    p = sweep.prepare(df, q)
    return p, sweep.answer(p, q)


def test_condition_in_every_combination_and_worst_case():
    p, a = _ans(_grid(), conditions=[{"column": "risk", "op": "<=", "value": 3}], goal={"column": "out", "direction": "max"})
    d = a["data"]
    # risk worst = 2p (scenario b): holds only for p = 1
    assert a["counts"]["holding"] == 2
    assert set(d["p"][d["#holds"] == 1]) == {1.0}
    assert np.allclose(d["#c0.worst"][d["p"] == 2.0], 4.0) and np.allclose(d["#c0.margin"][d["p"] == 2.0], -1.0)
    # goal: worst of out over scenarios = 10p - 5 + k, ranked among the holding sets only
    best = np.nanargmin(d["#rank"])
    assert d["k"][best] == 0.2 and np.isclose(d["#goal"][best], 5.2)


def test_condition_at_least_and_only_some_scenarios():
    # risk <= 2.5: p = 1 in all three, p = 2 in a and c only, p = 3 in none
    _, a = _ans(_grid(), conditions=[{"column": "risk", "op": "<=", "value": 2.5, "mode": "atLeast", "k": 2}])
    assert a["counts"]["holding"] == 4
    _, a = _ans(_grid(), conditions=[{"column": "risk", "op": "<=", "value": 2.5, "mode": "only", "where": {"scenario": ["a", "c"]}}])
    assert a["counts"]["holding"] == 4


def test_kept_values_and_new_columns():
    _, a = _ans(_grid(), holdValues={"scenario": ["a", "b"]},
                derived=[{"name": "out2", "kind": "row", "expr": "out * 2"},
                         {"name": "out_c", "kind": "set", "op": "min", "column": "out", "where": {"scenario": ["a"]}}],
                conditions=[{"column": "out_c", "op": ">=", "value": 20}])
    assert a["counts"]["combos"] == 2 and a["counts"]["rows"] == 12
    names = [m["name"] for m in a["columns"]]
    assert "out2" in names and "out_c" in names
    assert a["counts"]["holding"] == 4                      # out in a = 10p + k >= 20: p = 2, 3


def test_a_missing_run_or_empty_output_cannot_hold():
    df = _grid()
    df = df.drop(index=0)                                   # set (p=1, k=0.1) misses scenario a
    df.loc[5, "risk"] = np.nan                              # and another run gave no result
    _, a = _ans(df, conditions=[{"column": "risk", "op": "<=", "value": 100}])
    assert a["counts"]["holding"] == 4 and a["counts"]["complete"] == 5


def test_why_a_set_fails_and_rerun_list(tmp_path):
    q = {"roles": ROLES, "conditions": [{"column": "risk", "op": "<=", "value": 3}]}
    p = sweep.prepare(_grid(), q)
    a = sweep.answer(p, q)
    s3 = int(np.where(a["data"]["p"] == 3.0)[0][0])
    r = sweep.set_rows(p, q, s3)
    assert r["why"][0]["broken"] == 1 and r["why"][0]["worst"] == 6.0 and r["why"][0]["where"] == {"scenario": "b"}
    rows = sweep.rerun_rows(p, [s3])
    assert len(rows) == 3 and rows[0]["p"] == 3.0
    sweep.write_csv(str(tmp_path / "r.csv"), rows, ["p", "k", "scenario"])
    assert (tmp_path / "r.csv").read_text().splitlines()[0] == "p,k,scenario"


def test_formula_is_safe():
    df = _grid()
    from svcore.sweep.derived import row_formula
    assert np.allclose(row_formula(df, "abs(out - 20) + col('p')"), np.abs(df.out - 20) + df.p)
    for bad in ("__import__('os')", "out.__class__", "[1][0]", "scenario * 2"):
        with pytest.raises(sweep.DerivedError):
            row_formula(df, bad)


def test_route_evaluate_with_runs():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/sweep/open", json={"path": EXAMPLE}).json()
    roles = {col["name"]: col["role"] for col in r["columns"]}
    q = {"roles": roles, "goal": {"column": "range_m"}, "conditions": [{"column": "max_roll_deg", "op": "<=", "value": 25}]}
    e = c.post("/api/sweep/evaluate", json={"id": r["id"], "question": q, "runs": True}).json()
    assert e["counts"]["sets"] == 150 and e["counts"]["holding"] > 0
    assert e["runs"]["n"] == e["runs"]["total"] > 2000
    assert {m["name"] for m in e["sets"]} >= {"#holds", "#goal", "#rank", "payload_kg", "range_m"}
    bad = c.post("/api/sweep/evaluate", json={"id": r["id"], "question": {**q, "goal": {"column": "nope"}}})
    assert bad.status_code == 400


# ----------------------------------------------------------------------------- beyond holding
def test_recording_column_and_folder_of_files(tmp_path):
    df = pd.DataFrame({"rec": [f"/data/run_{i}.csv" for i in range(60)], "p": [1, 2, 3] * 20, "out": np.arange(60) * 1.37})
    assert {c["name"]: c["role"] for c in sweep.describe(df)}["rec"] == "recording"
    for i in range(3):
        _grid().iloc[i * 6:(i + 1) * 6].to_csv(tmp_path / f"stats_{i}.csv", index=False)
    d = sweep.read_any(str(tmp_path))
    assert len(d) == 18 and set(d["_file"]) == {"stats_0.csv", "stats_1.csv", "stats_2.csv"}


def test_pareto_score_effects_and_map():
    q = {"roles": ROLES, "objectives": [{"column": "out", "direction": "max"}, {"column": "risk", "direction": "min"}]}
    p = sweep.prepare(_grid(), q)
    a = sweep.answer(p, q)
    d = a["data"]
    # out grows with p, risk grows with p: every p is a trade-off; k=0.2 beats k=0.1 on out, ties on risk
    assert set(d["k"][d["#pareto"] == 1]) == {0.2}
    assert np.nanmax(d["#score"]) <= 1 and np.nanmin(d["#score"]) >= 0
    e = sweep.effects(p, d["out"], d["#holds"])
    imp = {x["param"]: x["importance"] for x in e["params"]}
    assert imp["p"] > 0.9 and imp["k"] < 0.1
    m = sweep.pair_map(p, "p", "k", d["out"], d["#holds"])
    assert len(m["xs"]) == 3 and len(m["ys"]) == 2 and m["share"][0][0] == 1.0


def test_stability_and_suggestions():
    q = {"roles": ROLES, "conditions": [{"column": "risk", "op": "<=", "value": 2.5}], "goal": {"column": "out"}}
    p = sweep.prepare(_grid(), q)
    d = sweep.answer(p, q)["data"]
    assert np.nanmax(d["#tolerance"]) >= 0 and np.isfinite(d["#neighbours"]).all()
    s = sweep.suggest(p, d["#holds"], d["#goal"], True, d["#partial"], ["edge", "best", "gaps"], budget=7)
    got = s["suggestions"]
    assert 0 < len(got) <= 7
    keys = [tuple(x["params"].values()) for x in got]
    assert len(keys) == len(set(keys))                               # no repeats, nothing already run
    edge = [x for x in got if x["kind"] == "edge"]
    assert edge and all(x["params"]["p"] in (1.5, 2.5) for x in edge if x["param"] == "p")


def test_suspicious_run_found_and_left_out():
    rows = []
    for sc in ("a", "b"):
        for p_ in range(1, 7):
            for k in (1.0, 2.0, 3.0, 4.0):
                rows.append({"scenario": sc, "p": float(p_), "k": k, "out": 10 * p_ + k, "risk": 1.0})
    df = pd.DataFrame(rows)
    df.loc[17, "out"] = 500.0
    q = {"roles": ROLES}
    sus = sweep.suspects(sweep.prepare(df, q))
    assert sus and sus[0]["row"] == 17 and sus[0]["column"] == "out"
    p = sweep.prepare(df, {**q, "exclude": [17]})
    assert len(p.df) == len(df) - 1


def test_compare_two_studies():
    a_df, b_df = _grid(), _grid()
    b_df["risk"] = b_df["risk"] * 0.5                               # after the change: less risk
    q = {"roles": ROLES, "conditions": [{"column": "risk", "op": "<=", "value": 3}], "goal": {"column": "out"}}
    pa, pb = sweep.prepare(a_df, q), sweep.prepare(b_df, q)
    r = sweep.compare(pa, sweep.answer(pa, q), pb, sweep.answer(pb, q))
    assert r["matched"] == 6 and r["nowHold"] == 4 and r["noLongerHold"] == 0


def test_cli_sweep_exit_codes(tmp_path, capsys):
    from signalviewer.cli import main
    q = tmp_path / "q.json"
    q.write_text('{"conditions": [{"column": "max_roll_deg", "op": "<=", "value": 25}]}')
    assert main(["sweep", EXAMPLE, "--question", str(q)]) == 0
    assert "parameter sets hold" in capsys.readouterr().out
    assert main(["sweep", EXAMPLE, "--question", str(q), "--min-holding", "1000"]) == 1
    assert main(["sweep", str(tmp_path / "nope.csv")]) == 2


def test_routes_reload_changed_and_templates(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.routes.sweep as rs
    monkeypatch.setattr(rs, "TEMPLATES", str(tmp_path / "tpl"))
    c = TestClient(app)
    f = tmp_path / "t.csv"
    _grid().to_csv(f, index=False)
    r = c.post("/api/sweep/open", json={"path": str(f)}).json()
    assert c.get(f"/api/sweep/changed?id={r['id']}").json()["changed"] is False
    pd.concat([_grid(), _grid().assign(p=4.0)]).to_csv(f, index=False)
    os.utime(f, (os.stat(f).st_atime, os.stat(f).st_mtime + 5))
    assert c.get(f"/api/sweep/changed?id={r['id']}").json()["changed"] is True
    again = c.post("/api/sweep/reload", json={"path": r["id"]}).json()
    assert again["id"] == r["id"] and again["rows"] == 36
    assert c.get(f"/api/sweep/changed?id={r['id']}").json()["changed"] is False
    t = c.post("/api/sweep/templates/save", json={"name": "risk check", "template": {"columns": [{"name": "p", "role": "param"}]}}).json()
    assert [x["name"] for x in t["templates"]] == ["risk check"]
    assert c.post("/api/sweep/templates/delete", json={"name": "risk check"}).json()["templates"] == []


def test_merge_a_finer_second_sweep():
    a = sweep.read_table(EXAMPLE)
    b = sweep.read_table(EXAMPLE.replace("sweep_payload.csv", "sweep_payload_refine.csv"))
    roles = {c["name"]: c["role"] for c in sweep.describe(a)}
    keys = [c for c, r in roles.items() if r in ("param", "hold")]
    m, added, replaced = sweep.merge(a, b, keys, "new", "first.csv", "refine.csv")
    assert replaced > 0 and len(m) == len(a) + added
    assert set(m["_source"]) == {"first.csv", "refine.csv"}
    assert not m.duplicated(subset=keys).any()                          # each run once: the newer one
    both, _, _ = sweep.merge(a, b, keys, "both")
    assert len(both) == len(a) + len(b)
    p = sweep.prepare(m, {"roles": roles})
    assert p.n_sets > 150                                               # the finer grid added sets


def test_routes_merge_and_export_rows(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/sweep/open", json={"path": EXAMPLE}).json()
    roles = {col["name"]: col["role"] for col in r["columns"]}
    keys = [k for k, v in roles.items() if v in ("param", "hold")]
    m = c.post("/api/sweep/merge", json={"id": r["id"], "path": EXAMPLE.replace("sweep_payload.csv", "sweep_payload_refine.csv"), "keys": keys}).json()
    assert m["replaced"] > 0 and m["rows"] > r["rows"] and len(m["sources"]) == 2
    out = tmp_path / "shown.csv"
    e = c.post("/api/sweep/export-rows", json={"id": r["id"], "question": {"roles": roles}, "sets": [0, 1], "path": str(out)}).json()
    lines = out.read_text().splitlines()
    assert e["rows"] == len(lines) - 1 > 0 and lines[0].startswith("scenario_terrain,")


@pytest.mark.parametrize("fmt", ["html", "docx", "pdf", "csv"])
def test_report_formats(tmp_path, fmt):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/sweep/open", json={"path": EXAMPLE}).json()
    roles = {col["name"]: col["role"] for col in r["columns"]}
    q = {"roles": roles, "goal": {"column": "range_m"}, "conditions": [{"column": "max_roll_deg", "op": "<=", "value": 25}]}
    body = {"id": r["id"], "question": q, "format": fmt, "path": str(tmp_path / "rep"), "title": "Payload sweep",
            "sections": [{"title": "Question", "items": ["max_roll_deg <= 25 in every combination"]},
                         {"title": "Process", "items": ["Kept 12 sets (payload 0.5 - 1.0)"]}],
            "summary": [["Parameter sets", 150], ["Hold", 43]], "labels": {"#goal": "range_m · worst", "#best": "Best"},
            "columns": ["#rank", "payload_kg", "kp_roll", "#goal"], "axes": ["payload_kg", "kp_roll", "range_m", "#goal"],
            "shown": list(range(40)), "mapX": "payload_kg", "mapY": "kp_roll"}
    out = c.post("/api/sweep/report", json=body)
    if out.status_code == 400 and "install" in out.text.lower():
        pytest.skip("reports extra not installed")
    out = out.json()
    assert out["path"].endswith("." + fmt) and out["size"] > 500
    if fmt == "html":
        html = open(out["path"], encoding="utf-8").read()
        assert "Payload sweep" in html and "<canvas" in html and "Kept 12 sets" in html and "data:image/png" in html
    if fmt == "csv":
        lines = open(out["path"], encoding="utf-8-sig").read().splitlines()
        assert len(lines) == 151 and lines[0].startswith("payload_kg")


def test_or_variants_rows_raw_and_plot_only(tmp_path):
    q = {"roles": ROLES, "conditions": [{"column": "risk", "op": "<=", "value": 1}, {"column": "out", "op": ">=", "value": 25}]}
    p = sweep.prepare(_grid(), q)
    assert sweep.answer(p, q)["counts"]["holding"] == 0                       # no set meets both
    assert sweep.answer(p, {**q, "combine": "or"})["counts"]["holding"] == 2  # p=3 meets out in every scenario
    q2 = {**q, "conditions": [{"column": "risk", "op": "<=", "value": 2}, {"column": "out", "op": ">=", "value": 25}], "combine": "or"}
    assert sweep.answer(sweep.prepare(_grid(), q2), q2)["counts"]["holding"] == 4   # p=1 by risk, p=3 by out
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/sweep/open", json={"path": EXAMPLE}).json()
    roles = {col["name"]: col["role"] for col in r["columns"]}
    v = c.post("/api/sweep/variants", json={"id": r["id"], "question": {"roles": roles}, "variants": [
        {"goal": {"column": "range_m"}, "conditions": [{"column": "max_roll_deg", "op": "<=", "value": 25}]},
        {"goal": {"column": "range_m"}, "conditions": [{"column": "max_roll_deg", "op": "<=", "value": 22}]}]}).json()["variants"]
    assert v[0]["holding"] > v[1]["holding"] and v[0]["best"]["value"] >= v[1]["best"]["value"]
    rows = c.get(f"/api/sweep/rows?id={r['id']}&offset=10&limit=5&sort=range_m&desc=true").json()
    assert rows["total"] == r["rows"] and len(rows["rows"]) == 5
    raw = c.post("/api/sweep/raw", json={"id": r["id"], "question": {}}).json()
    assert raw["n"] == r["rows"] and {x["name"] for x in raw["columns"]} >= {"range_m", "#row"}
    out = c.post("/api/sweep/report", json={"id": r["id"], "question": {"roles": roles}, "format": "plot", "raw": True,
                                            "path": str(tmp_path / "raw"), "axes": ["payload_kg", "range_m"]}).json()
    html = open(out["path"], encoding="utf-8").read()
    assert "<canvas" in html and 'id="tw"' not in html


def test_the_example_shows_scenarios_parameters_and_outputs():
    ex = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "sweeps", "drone_tuning.csv")
    df = sweep.read_table(ex)
    roles = {c["name"]: c["role"] for c in sweep.describe(df)}
    assert [c for c, r in roles.items() if r == "hold"] == ["scenario_wind_mps", "scenario_payload_kg", "scenario_gusts"]
    assert [c for c, r in roles.items() if r == "param"] == ["kp_roll", "ki_roll", "filter_hz"]
    assert roles["run_id"] == "id" and roles["sim_version"] == "ignore" and roles["crashed"] == "output"
    q = {"roles": roles, "goal": {"column": "energy_wh", "direction": "min"},
         "conditions": [{"column": "roll_error_deg", "op": "<=", "value": 5}, {"column": "overshoot_pct", "op": "<=", "value": 15},
                        {"column": "crashed", "op": "==", "value": 0}]}
    a = sweep.answer(sweep.prepare(df, q), q)
    assert a["counts"]["sets"] == 45 and a["counts"]["combos"] == 18 and 5 <= a["counts"]["holding"] <= 20


def test_autosave_of_the_open_studies():
    """S02: the Sweeps area keeps its open studies apart from Recordings' autosave; a damaged file
    is set aside the same way (F29), not overwritten."""
    from fastapi.testclient import TestClient
    from app.common import AUTOSAVE, SWEEP_AUTOSAVE
    from app.main import app
    c = TestClient(app)
    if os.path.exists(SWEEP_AUTOSAVE):
        os.remove(SWEEP_AUTOSAVE)
    assert c.get("/api/sweep/autosave").json() == {"state": None}
    doc = {"version": 1, "active": 0, "studies": [{"kind": "signalviewer-sweep", "version": 1, "path": "/x/runs.csv"}]}
    assert c.post("/api/sweep/autosave", json=doc).json() == {"ok": True}
    assert c.get("/api/sweep/autosave").json()["state"] == doc
    assert SWEEP_AUTOSAVE != AUTOSAVE
    with open(SWEEP_AUTOSAVE, "w") as f:
        f.write('{"studies": [')                                  # half-written
    r = c.get("/api/sweep/autosave").json()
    assert r["state"] is None and r["damaged"].endswith("sweep_autosave.damaged.json") and os.path.isfile(r["damaged"])
    os.remove(r["damaged"])


def test_export_the_sets_shown(tmp_path):
    """S04: the table of sets as shown - its rows in its order, its columns, holds as 1 / 0 - and
    the runs of those sets."""
    import csv as _csv
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    p = c.get("/api/sweep/example").json()["path"]
    o = c.post("/api/sweep/open", json={"path": p}).json()
    roles = {x["name"]: x["role"] for x in o["columns"]}
    q = {"roles": roles, "combine": "and", "holdValues": {}, "goal": {"column": "energy_wh", "direction": "min"},
         "conditions": [{"column": "roll_error_deg", "op": "<=", "value": 5, "mode": "all"}], "derived": [],
         "outputAgg": {}, "objectives": [], "exclude": []}
    a = c.post("/api/sweep/evaluate", json={"id": o["id"], "question": q, "runs": False}).json()
    assert a["counts"]["holding"] > 0
    out = tmp_path / "sets.csv"
    r = c.post("/api/sweep/export-sets", json={"id": o["id"], "question": q, "sets": [3, 0, 7],
               "columns": ["#rank", "#holds", "kp_roll", "ki_roll", "filter_hz", "#goal", "no_such"],
               "labels": {"#goal": "energy (worst)"}, "path": str(out)}).json()
    assert r["rows"] == 3
    rows = list(_csv.reader(open(out, encoding="utf-8-sig")))
    assert rows[0] == ["#rank", "#holds", "kp_roll", "ki_roll", "filter_hz", "energy (worst)"]     # unknown left out
    assert len(rows) == 4 and all(x[1] in ("0", "1") for x in rows[1:])
    bad = c.post("/api/sweep/export-sets", json={"id": o["id"], "question": q, "sets": [10 ** 6], "columns": ["#holds"], "path": str(out)})
    assert bad.status_code == 400 and "export again" in bad.json()["detail"]
    runs = tmp_path / "runs.csv"
    r = c.post("/api/sweep/export-rows", json={"id": o["id"], "question": q, "sets": [3, 0, 7], "path": str(runs)}).json()
    assert r["rows"] == 3 * a["counts"]["combos"]
    # the report's table follows the table on screen (S04): its sets, in its order
    rep = tmp_path / "answer.csv"
    c.post("/api/sweep/report", json={"id": o["id"], "question": q, "format": "csv", "path": str(rep), "rows": [7, 3]})
    body = list(_csv.reader(open(rep, encoding="utf-8-sig")))
    assert len(body) == 3
    html = tmp_path / "r.html"
    c.post("/api/sweep/report", json={"id": o["id"], "question": q, "format": "html", "path": str(html), "rows": [7, 3],
                                       "columns": ["#rank", "kp_roll"], "include": {"plot": False, "effects": False, "map": False}})
    assert '"rows": [7, 3]' in open(html, encoding="utf-8").read()


def test_optimize_min_max_and_weights():
    """Optimize: one goal ranks the sets that hold by its worst case over the combinations (the
    smallest when maximizing, the largest when minimizing); two or more rank them by the weighted
    score, so moving a weight changes the order."""
    rows = []
    for sc in ("a", "b"):
        for p_ in (1, 2, 3, 4):
            rows.append({"sc": sc, "p": p_, "up": p_ * 10 + (0 if sc == "a" else -3), "down": (5 - p_) * 10 + (0 if sc == "a" else 2)})
    df = pd.DataFrame(rows)
    roles = {"sc": "hold", "p": "param", "up": "output", "down": "output"}
    base = {"roles": roles, "combine": "and", "holdValues": {}, "conditions": [], "derived": [], "outputAgg": {}, "exclude": []}

    def ranked(q):
        pr = sweep.prepare(df, {**base, **q})
        d = sweep.answer(pr, {**base, **q})["data"]
        return [int(d["p"][i]) for i in np.argsort(d["#rank"])], d
    order, d = ranked({"goal": {"column": "up", "direction": "max"}, "objectives": []})
    assert order == [4, 3, 2, 1]
    assert list(d["#goal"][np.argsort(d["p"])]) == [7, 17, 27, 37]           # worst case of a maximum: the smaller
    order, d = ranked({"goal": {"column": "up", "direction": "min"}, "objectives": []})
    assert order == [1, 2, 3, 4] and list(d["#goal"][np.argsort(d["p"])]) == [10, 20, 30, 40]
    # two objectives pulling apart: the weights decide
    up = {"column": "up", "direction": "max"}
    dn = {"column": "down", "direction": "max"}
    order, d = ranked({"goal": up, "objectives": [{**up, "weight": 5}, {**dn, "weight": 1}]})
    assert order[0] == 4 and "#score" in d and "#pareto" in d
    order, _ = ranked({"goal": up, "objectives": [{**up, "weight": 1}, {**dn, "weight": 5}]})
    assert order[0] == 1


def test_maps_a_slice_at_the_best_and_several_in_the_report(tmp_path):
    """S05: a map over every value of the other parameters, or a slice through the best set; the best
    per cell is the smallest when minimizing (the report's map once showed the largest); every map
    on screen in the report."""
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    o = c.post("/api/sweep/open", json={"path": c.get("/api/sweep/example").json()["path"]}).json()
    roles = {x["name"]: x["role"] for x in o["columns"]}
    q = {"roles": roles, "combine": "and", "holdValues": {}, "goal": {"column": "energy_wh", "direction": "min"},
         "conditions": [{"column": "roll_error_deg", "op": "<=", "value": 5, "mode": "all"}], "derived": [],
         "outputAgg": {}, "objectives": [], "exclude": []}
    every = c.post("/api/sweep/map", json={"id": o["id"], "question": q, "x": "kp_roll", "y": "ki_roll"}).json()
    sl = c.post("/api/sweep/map", json={"id": o["id"], "question": q, "x": "kp_roll", "y": "ki_roll", "rest": "best"}).json()
    assert every["fixed"] is None and list(sl["fixed"]) == ["filter_hz"]
    assert sum(map(sum, sl["count"])) < sum(map(sum, every["count"])) and max(max(r) for r in sl["count"]) == 1
    a = c.post("/api/sweep/evaluate", json={"id": o["id"], "question": q, "runs": False}).json()
    assert a["counts"]["holding"] > 0
    best = [v for r in every["best"] for v in r if v is not None]
    worst = [v for r in sl["best"] for v in r if v is not None]
    assert min(best) <= min(worst)                                   # the best over all is at least as good
    # the cell of the best set: the slice and the full map agree there (the best of all is in it)
    assert min(best) == min(worst)
    html = tmp_path / "maps.html"
    r = c.post("/api/sweep/report", json={"id": o["id"], "question": q, "format": "html", "path": str(html),
               "labels": {"#mapTitle": "Map", "#mapAt": "at"}, "include": {"plot": False, "effects": False},
               "maps": [{"x": "kp_roll", "y": "ki_roll", "rest": "all"}, {"x": "kp_roll", "y": "filter_hz", "rest": "best"}]})
    assert r.status_code == 200
    text = open(html, encoding="utf-8").read()
    assert "Map: kp_roll × ki_roll</h2>" in text and "Map: kp_roll × filter_hz (at ki_roll = " in text


def test_robust_to_a_parameter_and_next_runs_on_chosen_parameters():
    """S06: robust to p within a tolerance - a set holds robustly when the sets within it hold too;
    only those are ranked, by the goal's worst case within the tolerance. Next runs move only the
    parameters to explore; 'robust' proposes the ends of the tolerance of the best sets."""
    rows = []
    for sc in ("a", "b"):
        for p_ in (1, 2, 3, 4, 5):
            for k in (10, 20, 30):
                out = 10 - abs(p_ - 4) * 3 + k / 10 + (0 if sc == "a" else -0.5)      # best at p = 4
                rows.append({"sc": sc, "p": p_, "k": k, "out": out})
    df = pd.DataFrame(rows)
    q = {"roles": {"sc": "hold", "p": "param", "k": "param", "out": "output"}, "combine": "and", "holdValues": {},
         "goal": {"column": "out", "direction": "max"}, "objectives": [], "derived": [], "outputAgg": {}, "exclude": [],
         "conditions": [{"column": "out", "op": ">=", "value": 5, "mode": "all"}]}
    pr = sweep.prepare(df, q)
    plain = sweep.answer(pr, q)["data"]
    best_plain = int(np.nanargmin(plain["#rank"]))
    assert (int(plain["p"][best_plain]), int(plain["k"][best_plain])) == (4, 30)
    rq = {**q, "robust": {"p": {"mode": "steps", "value": 1}}}
    d = sweep.answer(sweep.prepare(df, rq), rq)["data"]
    s = best_plain
    # p = 4 ± 1 step: p 3 and 5 at k 30 - the worst of them is the robust goal, both hold
    assert d["#robustSeen"][s] == 2 and d["#robustHolds"][s] == 1
    assert d["#robustGoal"][s] == min(plain["#goal"][i] for i in range(len(plain["p"])) if plain["k"][i] == 30 and plain["p"][i] in (3, 4, 5))
    edge = next(i for i in range(len(d["p"])) if d["p"][i] == 5 and d["k"][i] == 10)
    assert d["#robustSeen"][edge] == 1                                   # at the end of the grid: one side only
    assert np.isfinite(d["#rank"]).sum() == int((d["#robustHolds"] == 1).sum())
    # next runs: only k moves
    pr2 = sweep.prepare(df, rq)
    a = sweep.answer(pr2, rq)
    dd = a["data"]
    out = sweep.suggest(pr2, dd["#holds"], dd["#goal"], True, dd["#partial"], ["edge", "best", "disagree", "gaps", "robust"], 50,
                        focus=["k"], rank=dd["#rank"], robust=rq["robust"])
    for sg in out["suggestions"]:
        base = sg["from"]
        assert sg["params"]["p"] == sweep.evaluate._py(dd["p"][base]) or sg["kind"] == "gaps"
    assert all(x["param"] == "k" for x in out["suggestions"] if "param" in x)
    # 'robust' asks for the ends of a tolerance in %: p = 4 ± 10% is 3.6 and 4.4, not on the grid
    rq3 = {**q, "robust": {"p": {"mode": "pct", "value": 10}}}
    pr3 = sweep.prepare(df, rq3)
    d3 = sweep.answer(pr3, rq3)["data"]
    assert d3["#robustSeen"][best_plain] == 0                           # nothing measured within 10 %
    rb = sweep.suggest(pr3, d3["#holds"], d3["#goal"], True, d3["#partial"], ["robust"], 10, rank=d3["#rank"], robust=rq3["robust"])
    assert {round(x["params"]["p"], 6) for x in rb["suggestions"] if x["from"] == best_plain} == {3.6, 4.4}


def test_templates_export_and_import(tmp_path):
    """S07: a template to a file and back - under its name, or with (2) when the name is taken; a
    file that is not a template is refused."""
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    tpl = {"columns": [{"name": "kp", "role": "param", "scale": "linear"}], "question": {"goals": []}, "view": {}}
    names = lambda r: [x["name"] for x in r["templates"]]
    assert "share me" in names(c.post("/api/sweep/templates/save", json={"name": "share me", "template": tpl}).json())
    out = tmp_path / "share.json"
    assert c.post("/api/sweep/templates/export", json={"name": "share me", "path": str(out)}).json()["path"] == str(out)
    saved = json.loads(out.read_text())
    assert saved["kind"] == "signalviewer-sweep-template" and saved["saved"]
    r = c.post("/api/sweep/templates/import", json={"path": str(out)}).json()
    assert r["name"] == "share me (2)" and "share me (2)" in names(r)
    bad = tmp_path / "bad.json"
    bad.write_text('{"hello": 1}')
    assert c.post("/api/sweep/templates/import", json={"path": str(bad)}).status_code == 400
    for n in ("share me", "share me (2)"):
        c.post("/api/sweep/templates/delete", json={"name": n})
