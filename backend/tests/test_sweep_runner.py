"""MF06 / MF11: running sets with a command - placeholders filled after splitting (no shell), the
three parsers, statuses (ok, error, timeout), resume from the results file, stop, the endpoints."""
import csv
import json
import os
import sys
import time

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.sweep import runner as R  # noqa: E402

SIM = r'''
import json, sys, time
a = dict(x.split("=", 1) for x in sys.argv[1:])
kp, wind = float(a["kp"]), float(a["wind"])
if kp < 0: sys.exit(3)
if kp > 9: time.sleep(5)
out = {"err": kp * 2 + wind, "energy": kp ** 2}
if a.get("mode") == "stdout":
    print("err =", out["err"]); print("energy: %s" % out["energy"])
else:
    json.dump(out, open(a["out"], "w"))
'''


@pytest.fixture
def sim(tmp_path):
    p = tmp_path / "sim.py"
    p.write_text(SIM)
    return p


def _spec(tmp_path, sim, **kw):
    t = f'"{sys.executable}" "{sim}" kp={{kp}} wind={{wind}} out={{out}}'
    return {"template": t, "workdir": str(tmp_path), "parser": "json", "outputs": ["err", "energy"],
            "parallel": 2, "timeout": 2, "results": str(tmp_path / "res.csv"), **kw}


def test_fill_splits_first_no_shell():
    args = R.fill("sim --name {n} --x={x}", {"n": "a b; rm -rf /", "x": 2.0}, posix=True)
    assert args == ["sim", "--name", "a b; rm -rf /", "--x=2"]
    with pytest.raises(R.RunError):
        R.fill("sim {nope}", {}, posix=True)


def test_parsers(tmp_path):
    (tmp_path / "o.json").write_text(json.dumps({"a": 1, "b": "x", "c": [1]}))
    assert R.parse("json", str(tmp_path / "o.json"), "") == {"a": 1, "b": "x"}
    (tmp_path / "o.csv").write_text("a,b\n1.5,hi\n")
    assert R.parse("csv", str(tmp_path / "o.csv"), "") == {"a": 1.5, "b": "hi"}
    assert R.parse("stdout", "", "noise\nerr = 3\nenergy: 4.5\n") == {"err": 3.0, "energy": 4.5}
    with pytest.raises(R.RunError):
        R.parse("stdout", "", "nothing")


def test_run_all_statuses_and_resume(tmp_path, sim):
    runs = [{"kp": k, "wind": w} for k in (1.0, 2.0, -1.0, 10.0) for w in (0.0, 1.0)]
    live = R.Live(len(runs))
    res = R.run_all(runs, _spec(tmp_path, sim), live, lambda f, p: None, lambda: False)
    assert res["ok"] == 4 and res["error"] == 2 and res["timeout"] == 2
    df = pd.read_csv(tmp_path / "res.csv")
    assert list(df.columns) == ["kp", "wind", "err", "energy", "run_status", "run_seconds"]
    ok = df[df.run_status == "ok"]
    assert sorted(ok.err) == [2.0, 3.0, 4.0, 5.0]
    assert any("exit code 3" in f["message"] for f in live.to_dict()["failures"])
    # again: the ok ones are cached, the others run again
    live2 = R.Live(len(runs))
    res2 = R.run_all(runs, _spec(tmp_path, sim, timeout=1), live2, lambda f, p: None, lambda: False)
    assert res2["cached"] == 4 and res2["ok"] == 0
    assert len(pd.read_csv(tmp_path / "res.csv")) == 8 + 4


def test_stdout_parser(tmp_path, sim):
    spec = _spec(tmp_path, sim, parser="stdout", template=f'"{sys.executable}" "{sim}" kp={{kp}} wind={{wind}} mode=stdout')
    live = R.Live(1)
    R.run_all([{"kp": 1.0, "wind": 0.5}], spec, live, lambda f, p: None, lambda: False)
    assert live.to_dict()["rows"][0]["err"] == 2.5


def test_stop(tmp_path, sim):
    runs = [{"kp": 10.0, "wind": float(w)} for w in range(6)]
    live = R.Live(len(runs))
    t0 = time.time()
    flag = {"stop": False}

    def cancelled():
        if time.time() - t0 > 0.5:
            flag["stop"] = True
        return flag["stop"]
    R.run_all(runs, _spec(tmp_path, sim, timeout=0), live, lambda f, p: None, cancelled)
    assert time.time() - t0 < 4 and live.counts["ok"] == 0


def test_endpoints(tmp_path, sim):
    from fastapi.testclient import TestClient
    from app.main import app
    rows = [{"kp": k, "wind": w, "err": k * 2 + w, "energy": k * k} for k in (1.0, 2.0) for w in (0.0, 1.0)]
    path = tmp_path / "t.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(path)}).json()["id"]
    q = {"roles": {"kp": "param", "wind": "hold", "err": "output", "energy": "output"}}
    body = {"id": tid, "question": q, "sets": [{"kp": 3.0}, {"kp": 4.0}], "spec": _spec(tmp_path, sim)}
    pv = c.post("/api/sweep/run/preview", json=body).json()
    assert pv["runs"] == 4 and "kp=3" in pv["args"] and pv["workdirExists"]
    job = c.post("/api/sweep/run/start", json=body).json()
    for _ in range(100):
        st = c.get(f"/api/sweep/run/{job['id']}").json()
        if st["job"]["state"] != "running":
            break
        time.sleep(0.1)
    assert st["job"]["state"] == "done" and st["live"]["counts"]["ok"] == 4 and len(st["live"]["rows"]) == 4
    bad = {**body, "spec": {**body["spec"], "template": "x {nope}"}}
    assert c.post("/api/sweep/run/start", json=bad).status_code == 400


def test_windows_style_split():
    args = R.fill(r'"C:\Program Files\Py\python.exe" C:\sims\run.py --kp {kp}', {"kp": 1.5}, posix=False)
    assert args == [r"C:\Program Files\Py\python.exe", r"C:\sims\run.py", "--kp", "1.5"]
