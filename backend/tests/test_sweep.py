"""Sweeps area (svcore/sweep.py, app/routes/sweep.py): reading, describing and guessing roles of a
results table - parameters and scenario columns first, outputs last."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore import sweep  # noqa: E402
import svcore.sweep.io  # noqa: E402,F401

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "sweeps", "sweep_payload.csv")


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
    r = c.post("/api/sweep/open", json={"path": p}).json()
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
    r = c.post("/api/sweep/open", json={"path": c.get("/api/sweep/example").json()["path"]}).json()
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
