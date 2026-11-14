"""C1: a start round for any study - `start` (a grid per parameter x each table's scenarios) runs round 1 of a
study that has no runs yet, with the user's own program on local workers; studies written before C1 (the demo's
`demo.start_grid` / `demo.scenarios`) start exactly as before."""
import json
import os
import sys
import textwrap

import pytest

from svcore import loop
from svcore import study as S
from svcore import launcher as L

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEMO = os.path.join(ROOT, "examples", "smart_sweep_demo", "demo.svstudy.json")

PROGRAM = textwrap.dedent('''
    import csv, json, os, sys
    p = json.load(open(sys.argv[1], encoding="utf-8"))
    row = {"a": p["a"], "b": p["b"], "wind": p["wind"], "run_id": p["run_id"],
           "err": (p["a"] - 1) ** 2 + (p["b"] - 2) ** 2 + 0.1 * p["wind"]}
    os.makedirs(os.path.dirname(p["out"]), exist_ok=True)
    with open(p["out"], "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row)); w.writeheader(); w.writerow(row)
''')


def _new_study(tmp_path, **start):
    """A study made from nothing: two parameters, one scenario column, an output to minimise, a command."""
    (tmp_path / "sim.py").write_text(PROGRAM)
    d = {
        "version": 1, "name": "From nothing",
        "tables": [{"id": "T", "name": "My system", "paths": ["next/round_*/collected_T.csv"],
                    "roles": {"wind": "scenario", "err": "output"}, "objective": {"expr": "err", "sense": "min"}}],
        "shared": [{"name": "a"}, {"name": "b"}],
        "search": {"params": {"a": {"min": 0, "max": 2, "step": 0.1}, "b": {"min": 1, "max": 3, "step": 0.1}}},
        "start": {"grid": {"a": 3, "b": 2}, "scenarios": {"T": {"wind": [0, 5]}}, **start},
        "launcher": {"params_name": "params/{{table}}/{{run_id}}.json",
                     "params_template": '{"run_id": "{{run_id}}", "a": {{a}}, "b": {{b}}, "wind": {{wind}}, '
                                        '"out": "{{study_dir}}/results/{{table}}/{{run_id}}.csv"}',
                     "submit": [sys.executable, "{{study_dir}}/sim.py", "{{params_file}}"], "submit_mode": "run",
                     "results": {"glob": "results/{{table}}/{{run_id}}.csv", "format": "csv_row"},
                     "local_workers": 2},
    }
    path = tmp_path / "new.svstudy.json"
    path.write_text(json.dumps(d))
    return str(path)


def test_a_study_with_start_and_no_runs_runs_round_1(tmp_path):
    path = _new_study(tmp_path)
    s = S.load(path)
    assert s.start is not None and s.start.count("a") == 3 and s.start.count("b") == 2
    out = loop.run_round(s)
    s = S.load(path)
    assert out["round"] == 1 and out["candidates"] == 6 and out["runs"] == 12          # 3 x 2 values x 2 winds
    props = s.history[0].proposals
    assert {p.reason for p in props} == {"start"} and all(p.state == "done" for p in props)
    assert sorted({p.values["a"] for p in props}) == [0.0, 1.0, 2.0] and sorted({p.values["b"] for p in props}) == [1.0, 3.0]
    assert out["point"]["best"] is not None and out["point"]["values"] == {"a": 1.0, "b": 1.0}   # ties at b = 1, 3: worst wind
    assert len(s.table_files(s.tables[0])) == 1                                         # round 1's collected table


def test_one_count_for_every_parameter_and_the_file_round_trips(tmp_path):
    path = _new_study(tmp_path, grid=2)
    s = S.load(path)
    assert s.start.count("a") == s.start.count("b") == 2
    assert loop.propose(s)["runs"] == 2 * 2 * 2
    d = json.load(open(path, encoding="utf-8"))
    assert d["start"]["grid"] == 2 and d["start"]["scenarios"] == {"T": {"wind": [0, 5]}}


def test_without_a_start_it_says_what_to_give(tmp_path):
    path = _new_study(tmp_path)
    d = json.load(open(path, encoding="utf-8"))
    d.pop("start")
    json.dump(d, open(path, "w", encoding="utf-8"))
    with pytest.raises(L.LauncherError, match="start.grid and start.scenarios"):
        loop.propose(S.load(path))


def test_the_demo_without_start_starts_as_before_and_start_wins_over_demo(tmp_path):
    d = json.load(open(DEMO, encoding="utf-8"))
    s = S.loads(json.dumps(d), str(tmp_path / "a.svstudy.json"))
    assert s.start is None
    plan = s.start_plan()
    assert plan.count("Kp") == 4 and plan.scenarios["C"] == {"wind": [0, 5], "filter_hz": [15, 30, 60]}
    old = loop.start_round(s)
    # the same start written as `start` gives the same round 1, run for run
    d2 = dict(d, start={"grid": 4, "scenarios": d["demo"]["scenarios"]})
    d2["demo"] = dict(d["demo"], start_grid=2, scenarios={})                          # `start` is read first
    s2 = S.loads(json.dumps(d2), str(tmp_path / "b.svstudy.json"))
    new = loop.start_round(s2)
    assert old == new
    assert [p.run_id for p in s.history[0].proposals] == [p.run_id for p in s2.history[0].proposals]
