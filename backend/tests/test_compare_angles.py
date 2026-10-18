"""F16: Compare runs treats headings / yaw as angles - 359 deg vs 1 deg is 2 deg apart."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.compare import angle_period, compare  # noqa: E402

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def test_which_signals_are_angles():
    sweep = [np.linspace(0, 350, 50)]
    small = [np.linspace(-20, 20, 50)]
    assert angle_period("ATT.Yaw [deg]", small) == 360.0           # named like a direction
    assert angle_period("GPS.Course [rad]", small) == 2 * np.pi
    assert angle_period("Servo [deg]", sweep) == 360.0            # sweeps most of a turn
    assert angle_period("ATT.Roll [deg]", small) is None          # an angle that never wraps
    assert angle_period("Gyr.Yaw [deg/s]", sweep) is None         # a rate is not an angle
    assert angle_period("Yaw", sweep) is None                     # no unit: not assumed
    assert angle_period("Temp [degC]", sweep) is None


def test_heading_across_north_is_close():
    t = np.linspace(0, 10, 501)
    a = (355 + 2 * t) % 360                     # 355 -> 15 through north
    b = (a + 3) % 360                           # 3 deg to the right, all the way
    r = compare([("r1/Heading [deg]", t, a), ("r2/Heading [deg]", t, b)], "r1/Heading [deg]")
    row = r["rows"][0]
    assert r["angle"] == 360.0
    assert abs(row["rmsDiff"] - 3) < 1e-6 and abs(row["maxAbsDiff"] - 3) < 1e-6 and abs(row["meanDiff"] - 3) < 1e-6
    assert row["correlation"] > 0.99
    assert max(v for v in row["profile"] if v is not None) < 20
    m = compare([("r1/Heading [deg]", t, a), ("r2/Heading [deg]", t, b)], "mean")["rows"]   # circular mean
    assert all(abs(x["rmsDiff"] - 1.5) < 1e-6 for x in m)


def test_the_two_flights_yaw():
    a = pd.read_csv(os.path.join(EXAMPLES, "uav_flight.csv"))
    b = pd.read_csv(os.path.join(EXAMPLES, "uav_flight_windy.csv"))
    tc = a.columns[0]
    r = compare([("a/ATT.Yaw [deg]", a[tc].to_numpy(float), a["ATT.Yaw [deg]"].to_numpy(float)),
                 ("b/ATT.Yaw [deg]", b[tc].to_numpy(float), b["ATT.Yaw [deg]"].to_numpy(float))], "a/ATT.Yaw [deg]")
    row = r["rows"][0]
    assert row["maxAbsDiff"] <= 180 and row["rmsDiff"] < 40       # was 315 / 75.8 without wrapping


def test_other_signals_unchanged():
    t = np.linspace(0, 10, 101)
    r = compare([("r1/Speed [m/s]", t, t * 10), ("r2/Speed [m/s]", t, t * 10 + 400)], "r1/Speed [m/s]")
    assert "angle" not in r and abs(r["rows"][0]["rmsDiff"] - 400) < 1e-9
