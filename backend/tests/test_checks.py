"""T57: pass / fail from the command line - checks file, template limits, JUnit XML, exit codes:
    python -m pytest backend/tests/test_checks.py"""
import json
import os
import xml.etree.ElementTree as ET

import pytest

import app.prefs as prefs
from signalviewer.cli import main

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")
RUNS = [os.path.join(EX, f"run_01{k}.csv") for k in (2, 3, 4)]


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    monkeypatch.setattr(prefs, "TEMPLATE_DIR", str(tmp_path / "templates"))
    os.makedirs(tmp_path / "templates")
    return tmp_path


def run(capsys, *args):
    rc = main(list(args))
    out = capsys.readouterr()
    return rc, out.out, out.err


def by_name(d):
    return {(os.path.basename(f["file"]), r["name"]): r for f in d["files"] for r in f["results"]}


def test_example_checks_pass_and_fail_with_junit(tmp_path, capsys):
    junit = tmp_path / "results.xml"
    rc, so, _ = run(capsys, "check", *RUNS, "--checks", os.path.join(EX, "checks.json"), "--junit", str(junit), "--json")
    assert rc == 1                                                    # one check failed
    d = json.loads(so)
    assert d["count"] == {"pass": 8, "fail": 1, "error": 0, "skipped": 0, "info": 0}
    r = by_name(d)
    bad = r[("run_013.csv", "Speed while cruising below 76 km/h")]
    assert bad["status"] == "fail" and bad["signal"] == "Speed [km/h]" and bad["worst"] > 0
    assert 20 < bad["worstT"] < 60 and bad["timeOutside"] > 0
    root = ET.parse(junit).getroot()                                  # valid XML, CI-readable counts
    assert root.get("tests") == "9" and root.get("failures") == "1" and root.get("errors") == "0"
    assert len(root.findall("./testsuite")) == 3 and len(root.findall(".//failure")) == 1


def test_window_and_state_occurrence(tmp_path, capsys):
    c = tmp_path / "c.json"
    c.write_text(json.dumps({"checks": [
        {"name": "w", "signal": "RPM", "hi": 2500, "t0": 0, "t1": 1},                     # quiet start
        {"name": "from 5 s", "signal": "RPM", "hi": 2500, "t0": 5},                        # only t0
        {"name": "first cruise", "signal": "Speed", "hi": 1000, "during": {"state": "DriveMode", "value": 2, "occurrence": 1}},
        {"name": "10th cruise", "signal": "Speed", "hi": 1000, "during": {"state": "DriveMode", "value": "cruise", "occurrence": 10}},
    ]}))
    rc, so, _ = run(capsys, "check", RUNS[0], "--checks", str(c), "--json")
    r = by_name(json.loads(so))
    assert r[("run_012.csv", "w")]["status"] == "pass"
    assert r[("run_012.csv", "from 5 s")]["status"] == "fail" and r[("run_012.csv", "from 5 s")]["first"] >= 5
    assert r[("run_012.csv", "first cruise")]["status"] == "pass"
    assert r[("run_012.csv", "10th cruise")]["status"] == "skipped"   # no 10th stretch: not a pass
    assert rc == 1


def test_errors_exit_2_and_say_what_to_do(tmp_path, capsys):
    c = tmp_path / "c.json"
    c.write_text(json.dumps({"checks": [{"signal": "Spede", "hi": 1},
                                        {"signal": "Speed", "hi": 1, "during": {"state": "DriveMode", "value": "FLY"}}]}))
    rc, so, _ = run(capsys, "check", RUNS[0], str(tmp_path / "gone.csv"), "--checks", str(c))
    assert rc == 2
    assert "Did you mean 'Speed [km/h]'" in so and "its values: ACCEL, BRAKE, CRUISE, IDLE" in so
    assert "not found" in so.lower()
    bad = tmp_path / "bad.json"
    bad.write_text('{"checks": [{"signal": "RPM"}]}')
    rc, _, se = run(capsys, "check", RUNS[0], "--checks", str(bad))
    assert rc == 2 and "neither \"lo\" nor \"hi\"" in se
    rc, _, se = run(capsys, "check", RUNS[0])
    assert rc == 2 and "--checks" in se


def test_limits_saved_in_a_template(home, capsys):
    tpl = {"version": 2, "id": "lim", "name": "Drive limits", "slots": [{"id": "main", "name": "File"}],
           "tabs": [{"name": "Drive", "rows": 2, "cols": 1, "plots": [
               {"title": "Speed", "signals": [{"name": "Speed", "limits": {"hi": 76}}]},
               {"title": "RPM", "signals": [{"name": "RPM", "scale": 0.001, "limits": {"lo": 1.0, "hi": 3.0}}]}]}]}
    (home / "templates" / "lim.json").write_text(json.dumps(tpl), encoding="utf-8")
    rc, so, _ = run(capsys, "check", *RUNS, "--template", "Drive limits", "--json")
    r = by_name(json.loads(so))
    assert r[("run_012.csv", "Speed [km/h]")]["status"] == "pass"            # 75.5 km/h at most
    assert r[("run_013.csv", "Speed [km/h]")]["status"] == "fail"            # 77.8
    assert all(r[(f, "RPM")]["status"] == "pass" for f in ("run_012.csv", "run_013.csv", "run_014.csv"))  # scale applied
    assert rc == 1
    (home / "templates" / "none.json").write_text(json.dumps({**tpl, "id": "none", "name": "No limits",
        "tabs": [{"name": "T", "rows": 1, "cols": 1, "plots": [{"signals": [{"name": "RPM"}]}]}]}), encoding="utf-8")
    rc, _, se = run(capsys, "check", RUNS[0], "--template", "No limits")
    assert rc == 2 and "has no limits" in se


# --- T58: against a golden run ---------------------------------------------------------------

def test_compare_against_golden_ranks_and_tolerances(tmp_path, capsys):
    rc, so, _ = run(capsys, "compare", RUNS[0], RUNS[2], "--json")
    assert rc == 0                                                    # no tolerance: information only
    rows = json.loads(so)["files"][0]["results"]
    assert {r["status"] for r in rows} == {"info"} and len(rows) == 6
    assert rows[0]["name"] == "RPM" and rows[0]["rmsPct"] >= rows[-1]["rmsPct"]   # most different first
    tol = tmp_path / "tol.json"
    tol.write_text(json.dumps({"default": {"abs": 15}, "signals": {"rpm": {"abs": 1000}, "Throttle": {"skip": True}}}))
    junit = tmp_path / "r.xml"
    rc, so, _ = run(capsys, "compare", RUNS[0], RUNS[1], RUNS[2], "--tolerances", str(tol), "--junit", str(junit), "--json")
    d = json.loads(so)
    assert rc == 0 and d["count"]["fail"] == 0 and d["count"]["pass"] == 10    # 5 signals x 2 files
    assert all(r["name"] != "Throttle [%]" for f in d["files"] for r in f["results"])
    root = ET.parse(junit).getroot()
    assert root.get("tests") == "10" and root.get("failures") == "0"
    rc, so, _ = run(capsys, "compare", RUNS[0], RUNS[2], "--tol-abs", "15", "--signals", "RPM,Speed", "--top", "0")
    assert rc == 1 and "FAIL  RPM" in so and "PASS  Speed [km/h]" in so


def test_compare_errors_exit_2(tmp_path, capsys):
    rc, so, _ = run(capsys, "compare", RUNS[0], str(tmp_path / "gone.csv"), "--tol-abs", "1")
    assert rc == 2 and "not found" in so.lower()
    rc, so, _ = run(capsys, "compare", RUNS[0], RUNS[1], "--signals", "Spede")
    assert rc == 2 and "Did you mean 'Speed [km/h]'" in so
