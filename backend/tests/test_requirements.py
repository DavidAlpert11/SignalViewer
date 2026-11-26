"""CC11: requirements beyond a range - the metrics (svcore/requirements.py) and a checks file that uses them
(app/checks.py: the same verdict for the app's Checks and `signalviewer-cli check`)."""
import json
import os

import numpy as np
import pytest

from svcore import requirements as req


def _step(zeta=0.3, wn=4.0, T=6.0, n=6001, target=1.0):
    """A second-order step response: overshoot exp(-pi zeta / sqrt(1 - zeta^2)) of the step."""
    t = np.linspace(0, T, n)
    wd = wn * np.sqrt(1 - zeta ** 2)
    y = target * (1 - np.exp(-zeta * wn * t) * (np.cos(wd * t) + zeta / np.sqrt(1 - zeta ** 2) * np.sin(wd * t)))
    return t, y


def test_overshoot_matches_the_formula():
    t, y = _step(zeta=0.3)
    want = 100 * np.exp(-np.pi * 0.3 / np.sqrt(1 - 0.09))
    v = req.overshoot(t, y, 1.0, 40)
    assert v["value"] == pytest.approx(want, rel=1e-3) and v["pass"]
    assert not req.overshoot(t, y, 1.0, 20)["pass"]
    assert "%" in v["message"] and v["at"] == pytest.approx(np.pi / (4 * np.sqrt(1 - 0.09)), rel=1e-2)


def test_settle_rise_and_steady_state():
    t, y = _step(zeta=0.7, wn=4.0)
    s = req.settle(t, y, 1.0, 0.02, by=2.0)
    assert s["pass"] and 1.0 < s["value"] < 2.0                    # ~ 4 / (zeta wn) = 1.4 s
    assert not req.settle(t, y, 1.0, 0.02, by=1.0)["pass"]
    r = req.rise(t, y, 1.0, within=1.0)
    assert r["pass"] and 0.4 < r["value"] < 0.8
    e = req.sserror(t, y + 0.05, 1.0, max_err=0.01, last=1.0)
    assert not e["pass"] and e["value"] == pytest.approx(0.05, abs=1e-3)
    never = req.settle(t, np.where(t > 5, 3.0, y), 1.0, 0.02, by=2.0)
    assert not never["pass"] and "never settles" in never["message"]


def test_rate_track_and_order():
    t = np.linspace(0, 10, 1001)
    y = np.clip(t * 2, 0, 10)                                       # 2 per s, then flat
    assert req.rate(t, y, 2.5)["pass"] and not req.rate(t, y, 1.5)["pass"]
    ref = np.sin(t)
    ok = req.track(t, ref + 0.01, t, ref, abs_tol=0.05)
    assert ok["pass"]
    bump = ref + np.where((t > 4) & (t < 5), 0.3, 0.0)
    bad = req.track(t, bump, t, ref, abs_tol=0.05)
    assert not bad["pass"] and 4 < bad["at"] < 5 and "outside for" in bad["message"]
    ta, tb = req.moment(t, y, {"above": 5}), req.moment(t, ref, {"below": -0.5})
    assert ta == pytest.approx(2.51, abs=0.02) and tb == pytest.approx(3.67, abs=0.02)
    assert req.order(ta, tb, "A", "B")["pass"] and not req.order(tb, ta, "B", "A")["pass"]
    assert "never happens" in req.order(None, 1.0, "A", "B")["message"]


def test_a_flat_step_is_said_not_guessed():
    t = np.linspace(0, 1, 11)
    with pytest.raises(req.RequirementError, match="no step"):
        req.overshoot(t, np.ones(11), 1.0, 10)


def test_validate_says_what_is_missing():
    assert req.validate({"signal": "x", "hi": 1}) is None                         # an old check: a range
    assert "neither" in req.validate({"signal": "x"})
    assert "unknown" in req.validate({"signal": "x", "kind": "wobble"})
    assert '"by"' in req.validate({"signal": "x", "kind": "settle", "target": 1, "band": 0.1})
    assert "target" in req.validate({"signal": "x", "kind": "overshoot", "max_pct": 5})
    assert "tolerance" in req.validate({"signal": "x", "kind": "track", "ref": "r"})


def test_a_checks_file_with_requirements(tmp_path):
    """A simulated servo (cmd steps to 1 at 1 s, the position follows) judged by a checks file of every kind, as
    the app's Checks and the CLI do."""
    from app.checks import ChecksError, load_checks, run_checks
    t, y = _step(zeta=0.4, wn=6.0, T=5.0, n=5001)
    tt = t + 1.0                                                   # the step at 1 s
    time = np.concatenate([np.linspace(0, 0.999, 1000), tt])
    pos = np.concatenate([np.zeros(1000), y])
    cmd = (time >= 1.0).astype(float)
    csv = tmp_path / "servo.csv"
    with open(csv, "w") as f:
        f.write("Time,Cmd,Pos\n")
        for a, b, c in zip(time, cmd, pos):
            f.write(f"{a:.6f},{b:.6f},{c:.6f}\n")
    checks = {"checks": [
        {"name": "Overshoot at most 30 %", "kind": "overshoot", "signal": "Pos", "ref": "Cmd", "max_pct": 30, "t0": 1.0},
        {"name": "Overshoot at most 10 %", "kind": "overshoot", "signal": "Pos", "target": 1.0, "max_pct": 10, "t0": 1.0},
        {"name": "Settles in 2 s", "kind": "settle", "signal": "Pos", "target": 1.0, "band_pct": 2, "by": 2.0, "t0": 1.0},
        {"name": "Follows the command", "kind": "track", "signal": "Pos", "ref": "Cmd", "abs": 0.05},
        {"name": "Slew", "kind": "rate", "signal": "Pos", "max": 100},
        {"name": "Command before motion", "kind": "order", "first": {"signal": "Cmd", "above": 0.5},
         "then": {"signal": "Pos", "above": 0.1}},
        {"name": "A plain range", "signal": "Pos", "lo": -0.1, "hi": 1.5},
    ]}
    path = tmp_path / "checks.json"
    path.write_text(json.dumps(checks))
    res = {r["name"]: r for r in run_checks(str(csv), load_checks(str(path)))["results"]}
    want = 100 * np.exp(-np.pi * 0.4 / np.sqrt(1 - 0.16))         # ~25 %
    assert res["Overshoot at most 30 %"]["status"] == "pass"
    assert res["Overshoot at most 30 %"]["value"] == pytest.approx(want, rel=0.02)
    assert res["Overshoot at most 10 %"]["status"] == "fail" and res["Overshoot at most 10 %"]["first"] > 1.0
    assert res["Settles in 2 s"]["status"] == "pass"
    assert res["Follows the command"]["status"] == "fail"           # a step cannot be followed within 0.05
    assert "off its reference" in res["Follows the command"]["message"]
    assert res["Slew"]["status"] == "pass"
    assert res["Command before motion"]["status"] == "pass"
    assert res["A plain range"]["status"] == "pass"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"checks": [{"signal": "Pos", "kind": "settle", "target": 1, "band": 0.1}]}))
    with pytest.raises(ChecksError, match='"by"'):
        load_checks(str(bad))
    os.remove(bad)


def test_the_any_data_profile_and_a_user_profile(tmp_path, monkeypatch):
    """CC12: /api/runs/{id}/health answers for ANY file - holes in the numbers, a commanded / measured pair and its
    steps - and a user's profile (a JSON in ~/.signalviewer/profiles whose `match` finds the signals) adds its rules."""
    from fastapi.testclient import TestClient
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    from app.main import app
    t = np.linspace(0, 20, 4001)
    cmd = np.where(t >= 5, 10.0, 0.0)
    _, resp = _step(zeta=0.3, wn=3.0, T=15.0, n=3001, target=10.0)
    pos = np.r_[np.zeros(1000), resp[:3001]][:len(t)]
    temp = 20 + 0.1 * t
    temp[2000:2010] = np.nan                                      # a hole inside the run
    csv = tmp_path / "rig.csv"
    with open(csv, "w") as f:
        f.write("Time,Pos_cmd,Pos,Temp\n")
        for row in zip(t, cmd, pos, temp):
            f.write(",".join("" if not np.isfinite(v) else f"{v:.6f}" for v in row) + "\n")
    prof = tmp_path / ".signalviewer" / "profiles"
    prof.mkdir(parents=True)
    (prof / "rig.json").write_text(json.dumps({"name": "Rig", "match": ["^Pos$"], "checks": [
        {"name": "Pos overshoot at most 20 %", "kind": "overshoot", "signal": "Pos", "target": 10, "max_pct": 20, "t0": 5}]}))
    (prof / "other.json").write_text(json.dumps({"name": "Other", "match": ["^Nope$"], "checks": [{"signal": "X", "hi": 1}]}))
    (prof / "broken.json").write_text("{")
    c = TestClient(app)
    r = c.post("/api/files/open", json={"paths": [str(csv)]})
    assert r.status_code == 200
    rid = next(r["id"] for r in c.get("/api/runs").json() if r.get("path") == str(csv) or r.get("name") == "rig.csv")
    h = c.get(f"/api/runs/{rid}/health").json()
    codes = {f["code"]: f for f in h["findings"]}
    assert codes["nonFinite"]["vals"]["n"] == 10 and codes["nonFinite"]["signals"] == ["Temp"]
    assert codes["tracking"]["vals"]["meas"] == "Pos" and codes["tracking"]["vals"]["cmd"] == "Pos_cmd"
    want = 100 * np.exp(-np.pi * 0.3 / np.sqrt(1 - 0.09))         # ~37 %
    assert codes["stepResponse"]["vals"]["os"] == pytest.approx(want, rel=0.05)
    assert codes["stepResponse"]["level"] == "warning"           # over 25 %
    rule = codes["rule"]
    assert rule["level"] == "error" and rule["vals"]["profile"] == "Rig" and "overshoot" in rule["vals"]["msg"]
    ids = [(p["id"], p.get("name"), bool(p.get("error"))) for p in h["profiles"]]
    assert ("any", None, False) in ids and ("user", "Rig", False) in ids and ("user", "broken.json", True) in ids
    assert not any(p.get("name") == "Other" for p in h["profiles"])
    assert ("flightlog", None, False) not in ids
