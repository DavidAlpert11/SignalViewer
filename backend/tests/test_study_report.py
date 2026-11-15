"""C10: one report of a study - the set-up, each table's goal, the shared answer, the rounds - as one HTML page."""
import os

from fastapi.testclient import TestClient

from app.main import app

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DRONES = os.path.join(ROOT, "examples", "drones", "drones.svstudy.json")
client = TestClient(app, base_url="http://127.0.0.1")


def test_the_study_report_holds_the_answer_of_every_table(tmp_path):
    out = str(tmp_path / "drones_report")
    r = client.post("/api/sweeps/study/report", json={"study_path": DRONES, "path": out, "lang": "en",
                                                       "labels": {"answer": "The shared answer", "holds": "{n} of {of} hold"}})
    assert r.status_code == 200, r.text
    assert r.json()["path"].endswith(".html") and r.json()["values"] == 150
    page = open(r.json()["path"], encoding="utf-8").read()
    assert "The shared answer" in page and "14 of 150 hold" in page          # the same numbers as the panel
    for tid in ("A", "B", "C"):
        assert f"<th>{tid}</th>" in page                                       # a column per table
    assert "<script" not in page and "http" not in page.split("<body>")[1]     # offline, nothing runs


def test_a_study_without_rows_still_reports_its_set_up(tmp_path):
    study = {"version": 1, "name": "Empty <study>", "tables": [{"id": "A", "name": "Sim", "paths": ["nothing_*.csv"],
             "objective": {"expr": "overshoot", "sense": "min"}}],
             "shared": [{"name": "Kp"}], "search": {"params": {"Kp": {"min": 0.5, "max": 4}}}}
    r = client.post("/api/sweeps/study/report", json={"study": study, "folder": str(tmp_path), "path": str(tmp_path / "r.html"),
                                                       "lang": "he"})
    assert r.status_code == 200, r.text
    page = open(r.json()["path"], encoding="utf-8").read()
    assert 'dir="rtl"' in page and "Empty &lt;study&gt;" in page and "min overshoot" in page
