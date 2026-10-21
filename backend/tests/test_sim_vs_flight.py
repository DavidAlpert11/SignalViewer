"""C13: a simulation against its flight - examples/sim_vs_flight (tools/make_sim_vs_flight.py).

The model (.mat, from 0 s) and the vehicle (.bin, from boot: the test starts 104.37 s after boot)
fly the same doublets; the vehicle's roll is less damped than the model's, its pitch matches."""
import contextlib
import io
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.checks import load_tolerances, run_compare  # noqa: E402

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "sim_vs_flight")
SIM = os.path.join(EX, "sim_attitude_doublets.mat")
FLIGHT = os.path.join(EX, "flight_attitude_doublets.bin")
TRUE_SHIFT = -104.37


def _compare(align=None, align_on=None, tol=None):
    with contextlib.redirect_stderr(io.StringIO()):
        return run_compare(SIM, FLIGHT, tol or load_tolerances(os.path.join(EX, "tolerances.json"), None, None),
                           None, align, align_on)


def _status(res):
    return {r["name"]: r["status"] for r in res["results"]}


def test_auto_alignment_on_the_command_and_the_verdict():
    res = _compare("auto", "ATT.DesRoll")
    assert res["shift"]["seconds"] == pytest.approx(TRUE_SHIFT, abs=0.02)
    st = _status(res)
    assert st["(time alignment)"] == "info"
    assert st["ATT.Roll"] == "fail" and st["RATE.R"] == "fail"           # less damped than the model
    assert st["ATT.Pitch"] == "pass" and st["RATE.P"] == "pass"          # as the model
    assert st["ATT.DesRoll"] == "pass" and st["ATT.DesPitch"] == "pass"  # the same commands
    row = next(r for r in res["results"] if r["name"] == "ATT.Roll")
    assert row["as"] == "ATT.Roll [deg]"                                 # names matched without the unit


def test_auto_alignment_without_a_signal_named():
    res = _compare("auto")
    assert res["shift"]["seconds"] == pytest.approx(TRUE_SHIFT, abs=0.06)   # an output: plus the vehicle's lag


def test_alignment_given_in_seconds():
    res = _compare(str(TRUE_SHIFT))
    assert res["shift"] == {"method": "given", "seconds": TRUE_SHIFT}
    assert _status(res)["ATT.Pitch"] == "pass"


def test_without_alignment_nothing_overlaps():
    st = _status(_compare())
    assert set(st.values()) == {"error"}


def test_a_bad_align_value_is_an_error():
    st = _status(_compare("soon"))
    assert st == {"(time alignment)": "error"}


def test_as_pairs_differently_named_signals():
    tol = {"default": {}, "signals": {"ATT.Roll": {"as": "ATT.Pitch [deg]"}}}
    res = _compare(str(TRUE_SHIFT), tol=tol)
    row = next(r for r in res["results"] if r["name"] == "ATT.Roll")
    assert row["as"] == "ATT.Pitch [deg]" and row["correlation"] < 0.3


def test_cli_exit_code_and_junit(tmp_path, capsys):
    from signalviewer.cli import main
    junit = tmp_path / "r.xml"
    code = main(["compare", SIM, FLIGHT, "--align", "auto", "--align-on", "ATT.DesRoll",
                 "--tolerances", os.path.join(EX, "tolerances.json"), "--junit", str(junit), "--json"])
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["count"]["fail"] == 2 and out["count"]["info"] == 0       # the alignment line is not a signal
    assert "time alignment" in junit.read_text(encoding="utf-8")


def test_the_apps_align_finds_it_too():
    """The app's Align (svcore.sync): signals named alike with and without their unit pair up."""
    from app.store import Store
    from svcore import sync
    st = Store()
    with contextlib.redirect_stdout(io.StringIO()):
        a, b = st.open_file(os.path.abspath(SIM)), st.open_file(os.path.abspath(FLIGHT))
    c = sync.suggest(a.run, b.run)
    assert c and c[0]["method"] == "signal" and c[0]["delta"] == pytest.approx(TRUE_SHIFT, abs=0.06)


def test_xcorr_ignores_overlaps_where_a_side_does_not_move():
    """A command that is 0 before and after its test: a near-empty overlap of two flat stretches
    once scored thousands and won (C13)."""
    from svcore.sync import _xcorr_delta
    t = np.arange(0, 90, 0.01)
    u = np.where((t > 5) & (t < 6.5), 15.0, 0.0) - np.where((t > 6.5) & (t < 8), 15.0, 0.0)
    u += np.where((t > 50) & (t < 51), 10.0, 0.0)
    tb = np.arange(95, 200, 0.02)
    ub = np.interp(tb - 104.37, t, u, left=0.0, right=0.0) + 1e-9 * np.sin(tb)
    d, r = _xcorr_delta(t, u, tb, ub)
    assert d == pytest.approx(-104.37, abs=0.02) and r > 0.9


def test_the_generator_runs(tmp_path):
    root = os.path.join(os.path.dirname(__file__), "..", "..", "tools")
    sys.path.insert(0, root)
    import make_sim_vs_flight as m
    m.main(str(tmp_path))
    for f in ("sim_attitude_doublets.mat", "flight_attitude_doublets.bin", "tolerances.json"):
        assert (tmp_path / f).stat().st_size > 0


def test_the_apps_compare_pairs_names_with_and_without_unit():
    """The Compare panel's similarity list (/api/compare/all): the .mat's "ATT.Roll" and the log's
    "ATT.Roll [deg]" are one row, with each file's own signal in "sigs"."""
    from fastapi.testclient import TestClient

    from app.main import app
    client = TestClient(app)
    opened = client.post("/api/files/open", json={"paths": [os.path.abspath(SIM), os.path.abspath(FLIGHT)]}).json()["opened"]
    sim_id, fl_id = opened[0]["id"], opened[1]["id"]
    try:
        client.patch(f"/api/runs/{fl_id}", json={"timeOffset": TRUE_SHIFT})
        rows = client.post("/api/compare/all", json={"runs": [sim_id, fl_id], "baselineRun": sim_id}).json()["signals"]
        by = {r["name"]: r for r in rows}
        assert by["ATT.Roll"]["sigs"] == {sim_id: "ATT.Roll", fl_id: "ATT.Roll [deg]"}
        assert by["ATT.Roll"]["worstMaxAbs"] > 4 > by["ATT.Pitch"]["worstMaxAbs"]
        assert "IMU[0].AccZ [m/s/s]" not in by                     # only in the flight: not compared
    finally:
        for rid in (sim_id, fl_id):
            client.delete(f"/api/runs/{rid}")
