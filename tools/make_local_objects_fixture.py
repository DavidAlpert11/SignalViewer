#!/usr/bin/env python3
"""
The local-position recordings of the 2026-11-10 round (L0): one flight seen through positions in
metres - NED, ENU, ECEF - instead of latitude / longitude.

    examples/ardupilot_lanes.csv   ArduPilot names as the .bin loader makes them: POS (the EKF's output),
                                   ATT, two EKF3 lanes XKF1[0] / XKF1[1] (Roll / Pitch / Yaw, VN / VE / VD,
                                   PN / PE / PD relative to the EKF origin), ORGN[0] (that origin, constant)
                                   and GPS[0] (5 Hz, noisy). Lane 1 is lane 0 moved +1.5 m north and its
                                   yaw +0.5 deg, so the two lanes are visibly different by a known amount.
    examples/local_frames.csv      generic names: tgt.ned.x / y / z, ship.ecef_x / _y / _z,
                                   boat.pos.north / east / up (ENU), rov.pos.n / e / d (NED) and
                                   origin.lat / lon / alt (the origin of the local ones).

The flight: 300 s at 10 Hz, a left-hand circle of 600 m radius at 15 m/s climbing 0.5 m/s from 300 m
above sea level, so the heading wraps through 359 / 0 deg. The local positions are converted with the
SAME maths as the backend's "frame" op (svcore/analysis.py: WGS-84, ECEF, the NED rotation at the
origin), so lane 0 converted back lands on POS to well under 0.05 m. Seeded: the files are the same
on every run.

    python tools/make_local_objects_fixture.py
"""
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
from svcore.analysis import _ecef_to_ned, ecef_to_lla, lla_to_ecef  # noqa: E402 - the backend's own maths

EXAMPLES = os.path.join(HERE, "..", "examples")
LAT0, LON0, ALT0 = 32.80, 35.60, 300.0          # the origin (ORGN / origin.*), the area of the other examples
RADIUS, SPEED, CLIMB = 600.0, 15.0, 0.5          # m, m/s, m/s
RATE, DURATION = 10, 300                          # Hz, s
LANE1_DN, LANE1_DYAW = 1.5, 0.5                   # lane 1 - lane 0: m north, deg


def truth(t):
    """NED offset from the origin (m), attitude (deg) and NED velocity of the circle at time t."""
    w = SPEED / RADIUS
    a = w * t
    n, e, d = RADIUS * math.sin(a), -RADIUS * (1 - math.cos(a)), -CLIMB * t
    vn, ve, vd = SPEED * math.cos(a), -SPEED * math.sin(a), -CLIMB
    yaw = math.degrees(math.atan2(ve, vn)) % 360
    roll = -math.degrees(math.atan(SPEED * w / 9.80665))
    pitch = math.degrees(math.atan2(CLIMB, SPEED))
    return (n, e, d), (roll, pitch, yaw), (vn, ve, vd)


REF_ECEF = lla_to_ecef(LAT0, LON0, ALT0)
R_NED = _ecef_to_ned(LAT0, LON0)                  # ECEF -> NED at the origin


def ned_to_lla(ned):
    lat, lon, alt = ecef_to_lla(*(REF_ECEF + R_NED.T @ np.asarray(ned, float)))
    return float(lat), float(lon), float(alt)


def ned_to_ecef(ned):
    return REF_ECEF + R_NED.T @ np.asarray(ned, float)


def f(v, k=3):
    return f"{v:.{k}f}"


def ardupilot(rnd):
    cols = ["time", "POS.Lat [deg]", "POS.Lng [deg]", "POS.Alt [m]", "ATT.Roll [deg]", "ATT.Pitch [deg]", "ATT.Yaw [deg]"]
    for k in (0, 1):
        cols += [f"XKF1[{k}].{x} [deg]" for x in ("Roll", "Pitch", "Yaw")]
        cols += [f"XKF1[{k}].{x} [m/s]" for x in ("VN", "VE", "VD")]
        cols += [f"XKF1[{k}].{x} [m]" for x in ("PN", "PE", "PD")]
    cols += ["ORGN[0].Lat [deg]", "ORGN[0].Lng [deg]", "ORGN[0].Alt [m]", "GPS[0].Lat [deg]", "GPS[0].Lng [deg]", "GPS[0].Alt [m]"]
    rows = [",".join(cols)]
    for i in range(RATE * DURATION + 1):
        t = i / RATE
        ned, (roll, pitch, yaw), vel = truth(t)
        lat, lon, alt = ned_to_lla(ned)
        cells = [f(t, 1), f(lat, 9), f(lon, 9), f(alt, 3), f(roll), f(pitch), f(yaw)]
        for k in (0, 1):
            dn, dy = (LANE1_DN, LANE1_DYAW) if k else (0.0, 0.0)
            cells += [f(roll), f(pitch), f((yaw + dy) % 360)] + [f(v) for v in vel] + [f(ned[0] + dn, 4), f(ned[1], 4), f(ned[2], 4)]
        cells += [f(LAT0, 9), f(LON0, 9), f(ALT0, 3)]
        if i % 2 == 0:
            g = ned_to_lla((ned[0] + rnd.gauss(0, 1.5), ned[1] + rnd.gauss(0, 1.5), ned[2] + rnd.gauss(0, 3.0)))
            cells += [f(g[0], 9), f(g[1], 9), f(g[2], 3)]
        else:
            cells += ["", "", ""]
        rows.append(",".join(cells))
    return rows


def local_frames():
    """Four objects on the same circle, each shifted so they do not overlap on the map."""
    cols = ["time", "tgt.ned.x", "tgt.ned.y", "tgt.ned.z", "ship.ecef_x", "ship.ecef_y", "ship.ecef_z",
            "boat.pos.north", "boat.pos.east", "boat.pos.up", "rov.pos.n", "rov.pos.e", "rov.pos.d",
            "origin.lat", "origin.lon", "origin.alt"]
    rows = [",".join(cols)]
    for i in range(RATE * DURATION + 1):
        t = i / RATE
        (n, e, d), _, _ = truth(t)
        tgt = (n, e, d)
        ship = ned_to_ecef((n + 200.0, e, 0.0))                     # on the origin's level
        boat = (n - 200.0, e, 0.0)                                  # columns north, east, up (an ENU group)
        rov = (n - 400.0, e, 10.0)                                  # NED: 10 m below the origin
        cells = [f(t, 1)] + [f(v, 4) for v in tgt] + [f(v, 4) for v in ship] + [f(v, 4) for v in boat] + [f(v, 4) for v in rov]
        cells += [f(LAT0, 9), f(LON0, 9), f(ALT0, 3)]
        rows.append(",".join(cells))
    return rows


def main():
    rnd = random.Random(20261110)
    for name, rows in (("ardupilot_lanes.csv", ardupilot(rnd)), ("local_frames.csv", local_frames())):
        path = os.path.join(EXAMPLES, name)
        with open(path, "w", newline="\n") as fh:
            fh.write("\n".join(rows) + "\n")
        print(f"wrote {os.path.normpath(path)} ({len(rows) - 1} rows, {rows[0].count(',')} signals)")


if __name__ == "__main__":
    main()
