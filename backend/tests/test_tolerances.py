"""26.U5: per-signal tolerances - the Compare panel (/api/compare/all, /api/compare) and
`signalviewer-cli compare` read the same file and give the same pass / fail."""
import os

import pytest
from fastapi.testclient import TestClient

from svcore import tolerances as tol

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")
GOLDEN, RUN = (os.path.abspath(os.path.join(EX, f"run_01{k}.csv")) for k in (2, 4))


def test_parse_merge_and_names():
    t = tol.parse({"default": {"abs": 15, "pct": ""}, "signals": {"RPM": {"abs": 1000}, "Gear": {"skip": 1}, "Speed": {"pct": 2}, "x": {"as": "y", "note": "kept"}}})
    assert t["default"] == {"abs": 15.0}
    assert tol.for_signal(t, "Speed [km/h]") == {"abs": 15.0, "pct": 2.0}   # the key without its unit
    assert tol.for_signal(t, "rpm") == {"abs": 1000.0}                   # any case when it is one match
    assert tol.for_signal(t, "Temp") == {"abs": 15.0}                    # the default
    assert tol.for_signal(t, "Gear")["skip"] is True
    assert t["signals"]["x"] == {"as": "y", "note": "kept"}             # the file's other keys round-trip
    for bad, says in (({"default": {"abs": -1}}, "0 or more"), ({"signals": {"A": {"outside_pct": 120}}}, "from 0 to 100"),
                      ({"signals": {"A": {"pct": "a lot"}}}, "A: pct"), ([1], "expected")):
        with pytest.raises(ValueError, match=says):
            tol.parse(bad)


def test_judge_outside_share():
    row = {"pass": False, "withinPct": 99.5}
    assert tol.judge(row, {"abs": 1}) == (False, pytest.approx(0.5))
    assert tol.judge(row, {"abs": 1, "outside_pct": 0.5})[0] is True
    assert tol.judge(row, {"abs": 1, "outside_pct": 0.4})[0] is False
    assert tol.judge(row, {}) == (None, None) and tol.judge(row, {"abs": 1, "skip": True}) == (None, None)


def test_gui_and_cli_give_the_same_result():
    from app.checks import run_compare
    from app.main import app
    t = {"default": {"abs": 15}, "signals": {"RPM": {"abs": 40, "outside_pct": 1}, "Throttle": {"skip": True}, "Speed": {"pct": 1}}}
    cli = {r["name"]: r for r in run_compare(GOLDEN, RUN, tol.parse(t))["results"]}
    client = TestClient(app, base_url="http://127.0.0.1")
    ids = [r["id"] for r in client.post("/api/files/open", json={"paths": [GOLDEN, RUN]}).json()["opened"]]
    try:
        rows = client.post("/api/compare/all", json={"runs": ids, "baselineRun": ids[0], "tolerances": t}).json()["signals"]
        gui = {r["name"]: r for r in rows}
        assert set(cli) == {n for n, r in gui.items() if not r["skipped"]}          # Throttle left out by both
        assert gui["Throttle [%]"]["skipped"] and gui["Throttle [%]"]["pass"] is None
        assert {n: r["status"] == "pass" for n, r in cli.items()} == {n: gui[n]["pass"] for n in cli}
        assert {r["status"] for r in cli.values()} == {"pass", "fail"}            # both outcomes are exercised
        rpm = gui["RPM"]
        assert rpm["tolKey"] == "RPM" and rpm["tol"] == {"abs": 40.0, "outside_pct": 1.0}
        assert rpm["diffs"][0]["outsidePct"] == pytest.approx(cli["RPM"]["outsidePct"])
        # the detail view judges the same way (the signal's name is the baseline's)
        d = client.post("/api/compare", json={"signals": [f"{ids[0]}/RPM", f"{ids[1]}/RPM"],
                                              "baseline": f"{ids[0]}/RPM", "tolerances": t}).json()
        assert [r.get("pass") for r in d["rows"] if r["id"].startswith(ids[1])] == [rpm["pass"]]
        bad = client.post("/api/compare/all", json={"runs": ids, "tolerances": {"default": {"abs": "x"}}})
        assert bad.status_code == 400 and "abs" in bad.json()["detail"]
        # the older fields still work (one tolerance for every signal)
        old = client.post("/api/compare/all", json={"runs": ids, "baselineRun": ids[0], "tolAbs": 15}).json()["signals"]
        assert all(r["tol"] == {"abs": 15.0} for r in old)
    finally:
        for i in ids:
            client.delete(f"/api/runs/{i}")


def test_the_panels_file_is_the_clis_file(tmp_path, capsys):
    """Saved from the panel, read by `signalviewer-cli compare --tolerances` (and opened again)."""
    import json
    from app.main import app
    from signalviewer.cli import main
    client = TestClient(app, base_url="http://127.0.0.1")
    t = {"default": {"abs": 15}, "signals": {"RPM": {"abs": 40, "outside_pct": 1}, "Throttle": {"skip": True}}}
    r = client.post("/api/compare/tolerances/save", json={"path": str(tmp_path / "tol"), "tolerances": t}).json()
    assert r["path"].endswith("tol.json")
    assert client.post("/api/compare/tolerances/load", json={"path": r["path"]}).json()["tolerances"] == tol.parse(t)
    rc = main(["compare", GOLDEN, RUN, "--tolerances", r["path"], "--json"])
    rows = {x["name"]: x for x in json.loads(capsys.readouterr().out)["files"][0]["results"]}
    assert rc in (0, 1) and "Throttle [%]" not in rows and rows["RPM"]["status"] in ("pass", "fail")
    (tmp_path / "bad.json").write_text('{"default": {"pct": -2}}')
    bad = client.post("/api/compare/tolerances/load", json={"path": str(tmp_path / "bad.json")})
    assert bad.status_code == 400 and "bad.json: default: pct" in bad.json()["detail"]
