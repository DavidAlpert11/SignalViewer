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


def uav_flight(out):
    dt, T = 0.1, 600
    t = np.arange(0, T, dt)
    lat0, lon0, R = 32.80, 35.60, 6371000.0
    wp = np.array([[0, 0], [1500, 2500], [5000, 4000], [8000, 2000], [7000, -2500], [3500, -4500], [500, -2500], [0, 0]], float)
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(wp, axis=0), axis=1))]
    t_take, t_land = 30, 560
    v = np.where(t < t_take, 0, np.where(t > t_land, 0, np.clip((t - t_take) / 15, 0, 1) * np.clip((t_land - t) / 15, 0, 1) * 55))
    s = np.cumsum(v) * dt
    s = s / s[-1] * cum[-1]
    k = np.ones(150) / 150
    e = np.convolve(np.pad(np.interp(s, cum, wp[:, 0]), 75, mode="edge"), k, "valid")[:t.size]
    n = np.convolve(np.pad(np.interp(s, cum, wp[:, 1]), 75, mode="edge"), k, "valid")[:t.size]
    ground = -200.0
    alt = ground + np.where(t < t_take, 0, np.where(t > t_land + 15, 0,
                            700 * np.clip((t - t_take) / 60, 0, 1) * np.clip((t_land + 15 - t) / 70, 0, 1)))
    alt = np.convolve(np.pad(alt, 25, mode="edge"), np.ones(51) / 51, "valid")[:t.size]
    de, dn = np.gradient(e, dt), np.gradient(n, dt)
    yaw = (np.degrees(np.arctan2(de, dn)) + 360) % 360
    gs = np.hypot(de, dn)
    yaw_rate = np.gradient(np.unwrap(np.radians(yaw)), dt)
    rng = np.random.default_rng(3)
    roll = np.clip(np.degrees(np.arctan(gs * yaw_rate / 9.81)), -45, 45) + rng.normal(0, 0.4, t.size)
    climb = np.gradient(alt, dt)
    pitch = np.degrees(np.arctan2(climb, np.maximum(gs, 1))) + 2 + rng.normal(0, 0.3, t.size)
    lat = lat0 + np.degrees(n / R)
    lon = lon0 + np.degrees(e / (R * np.cos(np.radians(lat0))))
    batt = 16.8 - 2.2 * (t / T) - 0.04 * np.abs(climb) + rng.normal(0, 0.02, t.size)
    mode = np.where(t < t_take, "IDLE", np.where(t < t_take + 60, "TAKEOFF",
                    np.where(t < t_land - 40, "AUTO", np.where(t < t_land + 20, "LAND", "IDLE"))))
    with open(os.path.join(out, "uav_flight.csv"), "w", newline="", encoding="utf-8") as f:
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
    print("demo files written to", os.path.abspath(out))
