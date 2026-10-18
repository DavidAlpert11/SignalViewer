#!/usr/bin/env python3
"""
Writes the demo files used for the screenshots and videos in the README.

    python tools/make_demo_data.py [out_dir]        # default: examples/

  run_012.csv, run_013.csv, run_014.csv  three runs of the same drive (for Compare):
                                          Speed, RPM, Gear, Throttle, EngineTemp and a text
                                          column DriveMode (shown as a state lane)
  uav_flight.csv                          a 10-minute UAV flight over the Sea of Galilee with
                                          GPS.Lat / GPS.Lng / GPS.Alt and ATT.Roll / Pitch / Yaw
                                          (opens with the "Position on the map & 3D" template)
  uav_flight_windy.csv                    the same mission flown again in a cross-wind, 12 s later
                                          (two tracks on the map, Compare runs)

ArduPilot / MAVLink demo logs come from tools/make_test_bin.py and tools/make_same_flight.py.
"""
import csv
import os
import sys

import numpy as np


def drive_runs(out):
    t = np.arange(0, 60, 0.01)
    rng = np.random.default_rng(1)
    for name, shift, gain, noise in (("run_012", 0, 1, 0.25), ("run_013", 0.4, 1.03, 0.3), ("run_014", 1.2, 0.92, 0.35)):
        tt = t - shift
        base = gain * (5 + 45 * (np.tanh((tt - 8) / 3) + 1) / 2 + 25 * (np.tanh((tt - 22) / 3) + 1) / 2
                       - 60 * (np.tanh((tt - 42) / 4) + 1) / 2)
        speed = base + rng.normal(0, noise, t.size)
        acc = np.gradient(base, 0.01)
        thr = np.clip(18 + 9 * acc, 0, 100) + rng.normal(0, 0.5, t.size)
        gear = np.clip(np.floor(base / 20) + 1, 1, 5)
        rpm = 900 + base * 60 / gear * 1.6 + 120 * np.sin(tt * 1.3) + rng.normal(0, 15, t.size)
        temp = 70 + 18 * (1 - np.exp(-tt.clip(0) / 18)) + rng.normal(0, 0.15, t.size)
        mode = np.where(acc > 0.6, "ACCEL", np.where(acc < -0.6, "BRAKE", np.where(base < 8, "IDLE", "CRUISE")))
        with open(os.path.join(out, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Time", "Speed [km/h]", "RPM", "Gear", "Throttle [%]", "EngineTemp [°C]", "DriveMode"])
            for i in range(t.size):
                w.writerow([f"{t[i]:.2f}", f"{speed[i]:.3f}", f"{rpm[i]:.1f}", int(gear[i]), f"{thr[i]:.2f}",
                            f"{temp[i]:.3f}", mode[i]])


def uav_flight(out, name="uav_flight", wind=None, seed=3, t_take=30, t_land=560, drain=2.2):
    """A mission over the Sea of Galilee. wind=(speed m/s, blowing TOWARD deg): the same waypoints
    flown with a cross-wind - ground speed changes with the track, the track drifts downwind
    between corrections, the nose crabs into the wind, gusts shake the roll, the battery drains
    faster. wind=None writes the original uav_flight.csv unchanged (tests and README media use it)."""
    dt, T = 0.1, 600
    t = np.arange(0, T, dt)
    lat0, lon0, R = 32.80, 35.60, 6371000.0
    wp = np.array([[0, 0], [1500, 2500], [5000, 4000], [8000, 2000], [7000, -2500], [3500, -4500], [500, -2500], [0, 0]], float)
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(wp, axis=0), axis=1))]
    v = np.where(t < t_take, 0, np.where(t > t_land, 0, np.clip((t - t_take) / 15, 0, 1) * np.clip((t_land - t) / 15, 0, 1) * 55))
    if wind is not None:
        W, to = wind[0], np.radians(wind[1])
        seg = np.diff(wp, axis=0)
        trk = np.arctan2(seg[:, 0], seg[:, 1])                        # each leg's track, from north
        legs = np.minimum(np.searchsorted(cum, np.cumsum(v) * dt / (np.sum(v) * dt) * cum[-1], side="right") - 1, len(seg) - 1)
        v = v * (1 + W / 55 * np.cos(trk[legs] - to))                 # tail wind: faster over the ground
    s = np.cumsum(v) * dt
    s = s / s[-1] * cum[-1]
    k = np.ones(150) / 150
    e = np.convolve(np.pad(np.interp(s, cum, wp[:, 0]), 75, mode="edge"), k, "valid")[:t.size]
    n = np.convolve(np.pad(np.interp(s, cum, wp[:, 1]), 75, mode="edge"), k, "valid")[:t.size]
    if wind is not None:
        leg = np.minimum(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1)
        drift = 25 * W * np.sin(to - trk[leg])                                # metres right of each leg
        smooth = np.ones(301) / 301                                           # the autopilot corrects slowly
        de_off = np.convolve(np.pad(drift * np.cos(trk[leg]), 150, mode="edge"), smooth, "valid")[:t.size]
        dn_off = np.convolve(np.pad(-drift * np.sin(trk[leg]), 150, mode="edge"), smooth, "valid")[:t.size]
        flying = np.clip(v / 55, 0, 1) ** 3                                   # none while climbing out / landing
        flying = np.convolve(np.pad(flying, 150, mode="edge"), smooth, "valid")[:t.size]
        e, n = e + de_off * flying, n + dn_off * flying
    ground = -200.0
    alt = ground + np.where(t < t_take, 0, np.where(t > t_land + 15, 0,
                            700 * np.clip((t - t_take) / 60, 0, 1) * np.clip((t_land + 15 - t) / 70, 0, 1)))
    alt = np.convolve(np.pad(alt, 25, mode="edge"), np.ones(51) / 51, "valid")[:t.size]
    de, dn = np.gradient(e, dt), np.gradient(n, dt)
    yaw = (np.degrees(np.arctan2(de, dn)) + 360) % 360
    gs = np.hypot(de, dn)
    yaw_rate = np.gradient(np.unwrap(np.radians(yaw)), dt)
    rng = np.random.default_rng(seed)
    roll = np.clip(np.degrees(np.arctan(gs * yaw_rate / 9.81)), -45, 45) + rng.normal(0, 0.4, t.size)
    climb = np.gradient(alt, dt)
    pitch = np.degrees(np.arctan2(climb, np.maximum(gs, 1))) + 2 + rng.normal(0, 0.3, t.size)
    if wind is not None:
        flying = gs > 5
        crab = np.degrees(np.arcsin(np.clip(W * np.sin(to - np.radians(yaw)) / 55, -1, 1)))
        yaw = np.where(flying, (yaw - crab + 360) % 360, yaw)                    # nose into the wind
        moving = np.flatnonzero(gs > 15)                                         # climbing / hovering: the
        hold = moving[np.clip(np.searchsorted(moving, np.arange(t.size)) - 1, 0, None)]   # nose stays where it was
        hold[: moving[0]] = moving[0]
        yaw = np.where(gs > 15, yaw, yaw[hold])
        turn = np.convolve(np.pad(yaw_rate, 15, mode="edge"), np.ones(31) / 31, "valid")[:t.size]
        roll = roll - np.clip(np.degrees(np.arctan(gs * yaw_rate / 9.81)), -45, 45) \
            + np.clip(np.degrees(np.arctan(gs * np.clip(turn, -0.3, 0.3) / 9.81)), -35, 35)   # a real turn, not a glitch
        gust = np.convolve(rng.normal(0, 1, t.size + 30), np.ones(31) / 31 * 4, "valid")[:t.size]
        roll = roll + np.where(flying, 0.35 * W * gust, 0)
    lat = lat0 + np.degrees(n / R)
    lon = lon0 + np.degrees(e / (R * np.cos(np.radians(lat0))))
    batt = 16.8 - drain * (t / T) - 0.04 * np.abs(climb) + rng.normal(0, 0.02, t.size)
    mode = np.where(t < t_take, "IDLE", np.where(t < t_take + 60, "TAKEOFF",
                    np.where(t < t_land - 40, "AUTO", np.where(t < t_land + 20, "LAND", "IDLE"))))
    with open(os.path.join(out, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Time", "GPS.Lat [deg]", "GPS.Lng [deg]", "GPS.Alt [m]", "ATT.Roll [deg]", "ATT.Pitch [deg]",
                    "ATT.Yaw [deg]", "GroundSpeed [m/s]", "Battery [V]", "FlightMode"])
        for i in range(t.size):
            w.writerow([f"{t[i]:.1f}", f"{lat[i]:.7f}", f"{lon[i]:.7f}", f"{alt[i]:.2f}", f"{roll[i]:.2f}",
                        f"{pitch[i]:.2f}", f"{yaw[i]:.2f}", f"{gs[i]:.2f}", f"{batt[i]:.3f}", mode[i]])


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples")
    os.makedirs(out, exist_ok=True)
    drive_runs(out)
    uav_flight(out)
    # T44: the same mission flown again in a 9 m/s wind blowing toward the east, 12 s later
    uav_flight(out, "uav_flight_windy", wind=(9.0, 90.0), seed=7, t_take=42, t_land=566, drain=2.6)
    print("demo files written to", os.path.abspath(out))
