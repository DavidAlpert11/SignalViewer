"""Investigation step 7: phases and conservative automatic flags."""
import os

import numpy as np

from app.store import Store
from svcore.overview import gaps, phase_signal, phases, rank, scan

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "investigate")


def test_phase_signal_and_phases():
    assert phase_signal([("Speed", False), ("Gear", True), ("FlightMode", True)]) == "FlightMode"
    assert phase_signal([("Speed", False)]) is None
    p = phases(np.arange(6.0), np.array([0, 0, 1, 1, 1, 0]), {"0": "IDLE", "1": "RUN"})
    assert [(x["label"], x["a"], x["b"]) for x in p] == [("IDLE", 0, 2), ("RUN", 2, 5), ("IDLE", 5, 5)]


def test_flags_are_conservative():
    rng = np.random.default_rng(0)
    t = np.arange(0, 100, 0.02)
    noisy = rng.normal(0, 1, len(t))
    assert scan("quiet", t, noisy, False) == []
    frozen = noisy.copy(); frozen[(t > 40) & (t < 46)] = 0.123
    assert [f["kind"] for f in scan("frozen", t, frozen, False)] == ["stuck"]
    clipped = np.minimum(noisy + 3 * ((t > 50) & (t < 51)), 3.5)
    clipped[(t > 50.2) & (t < 50.8)] = 3.5
    assert any(f["kind"] == "saturated" and f["edge"] == "max" for f in scan("clip", t, clipped, False))
    setpoint = np.where(t > 30, 5.0, 0.0)                         # a held set point is not "stuck"
    assert scan("sp", t, setpoint, False) == []
    tt = np.r_[np.arange(0, 10, 0.1), np.arange(20, 30, 0.1)]
    assert [g["kind"] for g in gaps(tt)] == ["gap"]
    many = [{"kind": "spike", "signal": "a", "a": 1.0 + i * 0.01, "b": 1.0, "score": i} for i in range(50)]
    assert len(rank(many)) == 1


def test_demo_runs():
    st = Store()
    heavy = st.open_file(os.path.join(DEMO, "heavy_payload.csv")).id
    light = st.open_file(os.path.join(DEMO, "light_payload.csv")).id
    h, li = st.overview(heavy), st.overview(light)
    assert [p["label"] for p in h["phases"]] == ["TAKEOFF", "AUTO", "LOITER", "LAND"]
    assert [(f["kind"], f["signal"]) for f in h["flags"]] == [("saturated", "Motor3")] * 3
    assert li["flags"] == []
