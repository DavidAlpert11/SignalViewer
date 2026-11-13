"""The optimisation loop with your own program (owner, 2026-11-13): a copy of the demo whose launcher runs a
plain script of the user's - it reads one parameters file and writes one CSV row into a results folder - and
Signal Viewer manages the rounds: propose, run, wait for the results in the folder, read, rank, propose again."""
import json
import os
import sys
import textwrap
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from svcore import demo, loop
from svcore import study as S

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEMO = os.path.join(ROOT, "examples", "smart_sweep_demo", "demo.svstudy.json")

MY_PROGRAM = textwrap.dedent('''
    # a user's own program: one run = one parameters file in, one CSV row out (where the study says)
    import csv, json, os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sim import model                                   # stands for "your simulation"
    p = json.load(open(sys.argv[1], encoding="utf-8"))
    out = model(p["table"], p["Kp"], p["Ki"], p["Kd"], p.get("wind", 0), p.get("mass"), p.get("filter_hz"))
    row = {k: v for k, v in p.items() if k not in ("out", "sim", "sleep_ms", "noise", "seed", "table", "round", "run_id")}
    row.update(out); row["run_id"] = p["run_id"]
    os.makedirs(os.path.dirname(p["out"]), exist_ok=True)
    with open(p["out"], "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row)); w.writeheader(); w.writerow(row)
''')


def _my_study(tmp_path):
    path = demo.copy_to(DEMO, str(tmp_path / "mine"))
    (tmp_path / "mine" / "my_program.py").write_text(MY_PROGRAM)
    d = json.load(open(path, encoding="utf-8"))
    d["launcher"]["submit"] = [sys.executable, "{{study_dir}}/my_program.py", "{{params_file}}"]   # the user's program, per run
    d["launcher"]["local_workers"] = 2
    d["demo"]["start_grid"] = 2
    d["next"]["batch"] = 4
    json.dump(d, open(path, "w", encoding="utf-8"), indent=1)
    return path


def test_copy_needs_an_empty_folder(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "a.txt").write_text("1")
    with pytest.raises(Exception, match="not empty"):
        demo.copy_to(DEMO, str(tmp_path / "x"))


def test_the_loop_runs_your_own_program_until_it_stops(tmp_path):
    path = _my_study(tmp_path)
    code = loop.run_until(S.load(path), max_rounds=3)
    s = S.load(path)
    pts = loop.points(s)
    assert code in (0, 3) and [p["round"] for p in pts] == [1, 2, 3][:len(pts)] and len(pts) >= 2
    assert pts[-1]["best"] is not None and pts[-1]["runs"] > pts[0]["runs"]
    assert all(p.state == "done" for r in s.history for p in r.proposals)            # every result found in the folder
    assert os.path.isdir(tmp_path / "mine" / "results" / "A")                         # where the program wrote them
    prog = loop.progress(s)
    assert prog["state"] in ("stopped", "converged", "exhausted") and prog["best"] is not None
    assert prog["launcher"]["command"][1].endswith("my_program.py")


def test_a_program_that_writes_nothing_stops_the_loop_with_its_output(tmp_path):
    path = _my_study(tmp_path)
    (tmp_path / "mine" / "my_program.py").write_text("print('cannot find the licence server')\n")
    with pytest.raises(Exception) as e:
        loop.run_until(S.load(path), max_rounds=2)
    assert "No run of round 1 gave a result" in str(e.value) and "licence server" in str(e.value)


def test_the_loop_from_the_routes_in_the_background(tmp_path):
    path = _my_study(tmp_path)
    c = TestClient(app, base_url="http://127.0.0.1")
    r = c.post("/api/sweeps/loop", json={"study_path": path, "action": "next"})
    assert r.status_code == 200, r.text
    t0 = time.time()
    while True:
        p = c.get("/api/sweeps/loop/progress", params={"study_path": path}).json()
        if not p["running"] and len(p["points"]) == 1:
            break
        assert time.time() - t0 < 120
        time.sleep(0.3)
    assert p["round"] == 1 and p["runs"]["done"] == 8 * 12 and not p["error"]
    assert c.post("/api/sweeps/loop", json={"study_path": path, "action": "reset"}).json()["points"] == []


def test_a_study_without_a_command_says_what_to_do(tmp_path):
    path = _my_study(tmp_path)
    d = json.load(open(path, encoding="utf-8"))
    d["launcher"]["submit"] = []
    json.dump(d, open(path, "w", encoding="utf-8"))
    c = TestClient(app, base_url="http://127.0.0.1")
    r = c.post("/api/sweeps/loop", json={"study_path": path, "action": "run"})
    assert r.status_code == 409 and "launcher command" in r.json()["detail"]
