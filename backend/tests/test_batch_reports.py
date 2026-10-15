"""T11b: one report per file from a template, from the command line (no server):
    python -m pytest backend/tests/test_batch_reports.py"""
import json
import os

import pytest

import app.prefs as prefs
from signalviewer.cli import main

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")
TPL = {"version": 2, "id": "speed-rpm", "name": "Speed and RPM", "slots": [{"id": "main", "name": "File"}],
       "tabs": [{"name": "Drive", "rows": 2, "cols": 1, "plots": [
           {"title": "Speed", "signals": [{"name": "Speed", "color": "#3D8BFD"}]},          # loose: finds "Speed [km/h]"
           {"title": "RPM", "signals": [{"name": "RPM"}], "caption": "engine"}]}]}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    monkeypatch.setattr(prefs, "TEMPLATE_DIR", str(tmp_path / "templates"))
    os.makedirs(tmp_path / "templates")
    with open(tmp_path / "templates" / "speed-rpm.json", "w", encoding="utf-8") as f:
        json.dump(TPL, f)
    return tmp_path


def run(capsys, *args):
    rc = main(list(args))
    out = capsys.readouterr()
    return rc, out.out, out.err


def test_one_report_per_file(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("not,a\nrecording\n")
    out = tmp_path / "reports"
    rc, so, se = run(capsys, "report", "--template", "speed and rpm", "--out", str(out), "--json",
                     os.path.join(EX, "run_01[23].csv"), os.path.join(EX, "uav_flight.csv"), str(bad))
    assert rc == 0
    res = {os.path.basename(r["file"]): r for r in json.loads(so)}
    assert set(res) == {"run_012.csv", "run_013.csv", "uav_flight.csv", "bad.csv"}           # the wildcard was expanded
    for n in ("run_012.csv", "run_013.csv"):
        assert res[n]["plots"] == 2 and res[n]["missing"] == [] and os.path.isfile(res[n]["report"])
        html = open(res[n]["report"], encoding="utf-8").read()
        assert "Speed and RPM" in html and "engine" in html and "Speed [km/h]" in html
    assert "error" in res["uav_flight.csv"] and "report" not in res["uav_flight.csv"]       # nothing it asks for
    assert "error" in res["bad.csv"]
    assert "skip" in se


def test_builtin_template_by_name_and_pdf(tmp_path, capsys):
    pytest.importorskip("pypdf")
    from pypdf import PdfReader
    out = tmp_path / "r"
    rc, so, _ = run(capsys, "report", "--template", "ArduPilot · Attitude", "--format", "pdf", "--out", str(out),
                    os.path.join(EX, "uav_flight.csv"))
    assert rc == 0 and "1 of 1" in so
    pdf = PdfReader(str(out / "uav_flight.pdf"))
    assert len(pdf.pages) >= 3 and "ATT.Roll" in "".join(p.extract_text() for p in pdf.pages)


def test_template_from_a_json_file(tmp_path, capsys):
    p = tmp_path / "mine.json"
    p.write_text(json.dumps({"templates": [{**TPL, "id": "x", "name": "From file"}]}))      # an export file
    rc, so, _ = run(capsys, "report", "--template", str(p), "--out", str(tmp_path / "o"), os.path.join(EX, "run_014.csv"))
    assert rc == 0 and os.path.isfile(tmp_path / "o" / "run_014.html")


def test_errors_say_what_to_do(tmp_path, capsys):
    rc, _, se = run(capsys, "report", "--template", "Quick look", "--out", str(tmp_path), os.path.join(EX, "run_012.csv"))
    assert rc == 1 and "own tabs" in se
    rc, _, se = run(capsys, "report", "--template", "ArduPilot", "--out", str(tmp_path), os.path.join(EX, "run_012.csv"))
    assert rc == 1 and "Did you mean" in se and "ArduPilot · Attitude" in se
    rc, so, _ = run(capsys, "templates", "--json")
    names = [t["name"] for t in json.loads(so)]
    assert "Speed and RPM" in names and "ArduPilot · Full review" in names
