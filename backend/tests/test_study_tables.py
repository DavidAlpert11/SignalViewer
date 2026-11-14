"""C2: the navigator's data - each table's files grouped by round (rows counted once per file version), the
demo listed from its work folder - and *I have results*: a study's set-up guessed from one table."""
import json
import os
import shutil
import time

from fastapi.testclient import TestClient

from app.main import app
from svcore import demo
from svcore import study as S
from svcore import sweeps_common as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEMO = os.path.join(ROOT, "examples", "smart_sweep_demo", "demo.svstudy.json")
TUNING = os.path.join(ROOT, "examples", "sweeps", "drone_tuning.csv")
client = TestClient(app, base_url="http://127.0.0.1")


def _two_rounds(folder):
    """What the demo's work folder holds after two rounds: each drone's collected table per round."""
    for k in (1, 2):
        for t, n in (("A", 3), ("B", 4), ("C", 5)):
            d = os.path.join(folder, "next", f"round_{k}")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"collected_{t}.csv"), "w") as f:
                f.write("run_id,Kp,y\n" + "".join(f"r{i},{i},{i * k}\n" for i in range(n * k)))


def test_the_demo_after_two_rounds_lists_two_rounds_of_three_tables(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    s = demo.prepare(DEMO)
    assert s.path.startswith(str(tmp_path))
    _two_rounds(s.folder)
    r = client.get("/api/sweeps/study/tables", params={"study_path": DEMO})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["demo_work"] == s.path and [t["id"] for t in j["tables"]] == ["A", "B", "C"]
    assert [[x["round"] for x in t["rounds"]] for t in j["tables"]] == [[1, 2]] * 3
    assert [t["rounds"][1]["rows"] for t in j["tables"]] == [6, 8, 10] and j["tables"][2]["rows"] == 15


def test_rows_are_counted_once_per_file_version_and_new_files_are_marked(tmp_path):
    shutil.copy(DEMO, tmp_path / "s.svstudy.json")
    _two_rounds(str(tmp_path))
    s = S.load(str(tmp_path / "s.svstudy.json"))
    before = time.time() - 1
    j = C.tables_by_round(s, since=before)
    assert all(x["new"] for t in j["tables"] for x in t["rounds"])
    j = C.tables_by_round(s, since=time.time() + 1)
    assert not any(x["new"] for t in j["tables"] for x in t["rounds"])
    f = s.table_files(s.tables[0])[0]
    calls = []
    real = C.read_any
    C.read_any = lambda p: calls.append(p) or real(p)        # a csv is counted by lines, never parsed
    try:
        C.count_rows(f)
    finally:
        C.read_any = real
    assert calls == []
    with open(f, "a") as h:
        h.write("r9,9,9\n")
    os.utime(f, (time.time() + 5, time.time() + 5))
    assert C.count_rows(f) == 4                                # the new version counted again


def test_i_have_results_guesses_the_set_up_from_the_table():
    r = client.post("/api/sweeps/setup/from-table", json={"path": TUNING})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [p["name"] for p in j["params"]] == ["kp_roll", "ki_roll", "filter_hz"]
    assert [x["name"] for x in j["scenarios"]] == ["scenario_wind_mps", "scenario_payload_kg", "scenario_gusts"]
    assert {"roll_error_deg", "settle_time_s", "overshoot_pct", "energy_wh", "crashed"} <= set(j["outputs"])
    kp = j["search"]["params"]["kp_roll"]
    assert kp["min"] < kp["max"] and j["roles"]["kp_roll"] == "shared" and j["roles"]["scenario_gusts"] == "scenario"
    assert j["scenarios"][2]["values"] and "none" in j["scenarios"][2]["values"]


def test_an_open_table_with_its_roles_as_set():
    t = client.post("/api/sweep/open", json={"path": TUNING}).json()
    roles = {c["name"]: c["role"] for c in t["columns"]}
    roles["filter_hz"] = "hold"                                 # the user made it a condition
    j = client.post("/api/sweeps/setup/from-table", json={"id": t["id"], "roles": roles}).json()
    assert [p["name"] for p in j["params"]] == ["kp_roll", "ki_roll"] and "filter_hz" in [x["name"] for x in j["scenarios"]]
    assert client.post("/api/sweeps/setup/from-table", json={}).status_code == 400
