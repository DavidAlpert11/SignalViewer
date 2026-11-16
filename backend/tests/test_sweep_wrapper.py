"""The sweep wrapper (owner, 2026-11-16): examples/smart_sweep_demo/sweep_wrapper.py runs ONE simulation per set of
inputs (a JSON file each) and writes the sweep's rows; the inputs as 'name: 1,2,5,8:0.1:9' lines, a table of rows, or
the app's parameter files. `study wrap` runs it in this program (the Portable); the launcher's run_as "wrapper" runs a
round through it in the background (the smart-sweep demo)."""
import csv
import importlib.util
import json
import os
import sys

import pytest

from signalviewer.study import main as study_cli

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DIR = os.path.join(ROOT, "examples", "smart_sweep_demo")
WRAPPER = os.path.join(DIR, "sweep_wrapper.py")


@pytest.fixture(scope="module")
def W():
    spec = importlib.util.spec_from_file_location("sweep_wrapper_t", WRAPPER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_matlab_style_values(W):
    assert W.parse_values("1,2,5,8:0.1:9") == [1, 2, 5, 8, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 9]
    assert W.parse_values("1:3; 0.5") == [1, 2, 3, 0.5]
    assert W.parse_values("calm, gusty") == ["calm", "gusty"]
    with pytest.raises(ValueError, match="step"):
        W.parse_values("5:1:2")


def test_a_spec_runs_every_combination_and_resumes(W, tmp_path):
    spec = tmp_path / "grid.txt"
    spec.write_text("# a comment\nKp: 1, 2:1:3\nKi: 0.4\nKd: 0.3\nwind: 0, 5\n", encoding="utf-8")
    out = tmp_path / "sweep.csv"
    assert W.main(["--spec", str(spec), "--set", "table=A", "--out", str(out)]) == 0
    rows = _rows(out)
    assert len(rows) == 6
    assert {(r["Kp"], r["wind"]) for r in rows} == {(k, w) for k in ("1", "2", "3") for w in ("0", "5")}
    assert {"overshoot", "settling_time", "run_id"} <= set(rows[0])        # inputs, outputs and run_id: one row per run
    assert W.main(["--spec", str(spec), "--set", "table=A", "--out", str(out)]) == 0
    assert len(_rows(out)) == 6                                            # done runs are not run again


def test_a_table_of_rows_and_an_outside_simulation(W, tmp_path):
    runs = tmp_path / "runs.csv"
    runs.write_text("Kp,Ki,Kd,wind\n1.2,0.4,0.3,0\n1.2,0.4,0.3,10\n", encoding="utf-8")
    out = tmp_path / "sweep.csv"
    sim = f'"{sys.executable}" "{os.path.join(DIR, "sim.py")}" {{params}}'    # a program of its own, run per row
    assert W.main(["--inputs", str(runs), "--sim", sim, "--set", "table=A", "--out", str(out)]) == 0
    rows = _rows(out)
    assert [r["wind"] for r in sorted(rows, key=lambda r: r["run_id"])] == ["0", "10"]
    assert float(rows[0]["settling_time"]) > 0


def test_a_failed_run_is_reported_and_the_rest_done(W, tmp_path):
    runs = tmp_path / "runs.csv"
    runs.write_text("table,Kp,Ki,Kd\nA,1,0.4,0.3\nZ,1,0.4,0.3\n", encoding="utf-8")   # no drone Z
    out = tmp_path / "sweep.csv"
    assert W.main(["--inputs", str(runs), "--out", str(out)]) == 1
    assert len(_rows(out)) == 1


def test_study_wrap_runs_the_app_s_parameter_files(tmp_path):
    files = []
    for i, wind in enumerate((0, 5)):
        p = tmp_path / f"r{i}.json"
        p.write_text(json.dumps({"run_id": f"r{i}", "table": "A", "Kp": 1.0, "Ki": 0.3, "Kd": 0.3, "wind": wind,
                                 "out": str(tmp_path / "results" / f"r{i}.csv")}), encoding="utf-8")
        files.append(str(p))
    lst = tmp_path / "params_files_A.txt"
    lst.write_text("".join(f + "\n" for f in files), encoding="utf-8")
    assert study_cli(["wrap", WRAPPER, "--list", str(lst), "--workers", "2"]) == 0      # the Portable's way
    assert sorted(os.listdir(tmp_path / "results")) == ["r0.csv", "r1.csv"]               # each run's row where it asked
    assert study_cli(["wrap", str(tmp_path / "missing.py")]) == 1


def test_the_demo_runs_its_rounds_through_the_wrapper():
    with open(os.path.join(DIR, "demo.svstudy.json"), encoding="utf-8") as f:
        L = json.load(f)["launcher"]
    assert L["run_as"] == "wrapper" and L["submit_mode"] == "round" and "{{params_files}}" in L["submit"]
    assert "sweep_wrapper.py" in " ".join(L["submit"]) and not L.get("local_workers")
