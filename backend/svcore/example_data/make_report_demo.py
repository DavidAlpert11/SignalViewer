"""RE2 (owner, 2026-11-19): two recordings that show every ready-made part of the report - a generic vehicle test,
on purpose not a flight log's names (the parts find things by their rules, not by one format):

    mission.phase            the scenario: IDLE, TAKEOFF, CRUISE, TURN, CRUISE, DESCENT, LAND, IDLE (text)  [[states]]
    ctrl.<x>_cmd / ctrl.<x>  four commanded / measured pairs - altitude, speed, roll (with steps), pitch      [[tracking]]
    sim.* / nav.* / gps.*    three objects: the simulated truth, the navigation estimate, the receiver       [[navigation]]
                             (position, velocity, attitude) - the track                                       [[trajectory]]
    gps.status, act.elevator special moments: the receiver lost (LOST), the elevator at its limit             [[moments]]

    mission_ref.csv          the baseline
    mission_gust.csv         the same mission, but a gust hits at 140-160 s and the receiver is lost at 150-170 s:
                             the roll does not follow, the estimate drifts - mostly the same file, one central region
                             different                                                                         [[differences]]

Deterministic (a fixed seed, fixed number formats), so the files are the same on every system.

    python tools/make_report_demo.py [folder]       (default: examples/report_demo)
"""
import csv
import math
import os
import sys

import numpy as np

PHASES = [(0, "IDLE"), (10, "TAKEOFF"), (40, "CRUISE"), (120, "TURN"), (150, "CRUISE"), (210, "DESCENT"), (260, "LAND"), (290, "IDLE")]
LAT0, LON0, R = 32.0800, 34.7800, 6378137.0


def _phase(t):
    name = PHASES[0][1]
    for a, n in PHASES:
        if t >= a:
            name = n
    return name


def simulate(gust: bool):
    dt = 0.1
    t = np.round(np.arange(0, 300 + dt / 2, dt), 3)
    n = len(t)
    rng = np.random.default_rng(12)
    out = {k: np.zeros(n) for k in ("alt_cmd", "alt", "speed_cmd", "speed", "roll_cmd", "roll", "pitch_cmd", "pitch", "yaw",
                                    "north", "east", "vn", "ve", "vd", "elevator")}
    alt = speed = roll = p_rate = pitch = yaw = north = east = 0.0
    gr = gq = 0.0                                      # the gust's own roll response: it rolls the vehicle, the path holds
    for i, ti in enumerate(t):
        ph = _phase(ti)
        # the commands: a ramp up, a step in altitude at 180 s, a step in speed at 170 s, roll doublets at 60-70 s and a turn
        alt_cmd = 0.0 if ti < 10 else min(120.0, (ti - 10) * 4.0) if ti < 210 else max(0.0, 120.0 - (ti - 210) * 2.4)
        if 180 <= ti < 210:
            alt_cmd = 90.0
        if ti >= 210:
            alt_cmd = max(0.0, 90.0 - (ti - 210) * 1.8)
        speed_cmd = {"IDLE": 0.0, "TAKEOFF": 15.0, "CRUISE": 22.0, "TURN": 18.0, "DESCENT": 15.0, "LAND": 6.0}[ph]
        if 170 <= ti < 210:
            speed_cmd = 26.0
        roll_cmd = 25.0 if ph == "TURN" else 0.0
        if 60 <= ti < 70:
            roll_cmd = 10.0 if ti < 65 else -10.0
        # the vehicle: first-order altitude and speed, a second-order roll, pitch from the altitude error
        speed += (speed_cmd - speed) * dt / 2.0
        alt += (alt_cmd - alt) * dt / 3.0
        pitch_cmd = float(np.clip(0.4 * (alt_cmd - alt), -15, 15))
        pitch += (pitch_cmd - pitch) * dt / 0.5
        dist = 0.0
        if gust and 140 <= ti < 160:
            dist = 60.0 * math.sin((ti - 140) / 20 * math.pi) * (1 + 0.5 * math.sin(ti * 3.1))
        wn, z = 3.0, 0.6
        acc = wn * wn * (roll_cmd - roll) - 2 * z * wn * p_rate
        p_rate += acc * dt
        roll += p_rate * dt
        gq += (dist - wn * wn * gr - 2 * z * wn * gq) * dt
        gr += gq * dt
        v = max(speed, 0.1)
        yaw = (yaw + math.degrees(9.81 * math.tan(math.radians(roll)) / v) * dt * (1 if speed > 1 else 0)) % 360
        roll_seen = roll + gr
        vn, ve = speed * math.cos(math.radians(yaw)), speed * math.sin(math.radians(yaw))
        vd = -(alt_cmd - alt) / 3.0
        north += vn * dt
        east += ve * dt
        elevator = float(np.clip(2.5 * pitch_cmd + 0.8 * (pitch_cmd - pitch), -20, 20))
        for k, val in (("alt_cmd", alt_cmd), ("alt", alt), ("speed_cmd", speed_cmd), ("speed", speed), ("roll_cmd", roll_cmd),
                       ("roll", roll_seen), ("pitch_cmd", pitch_cmd), ("pitch", pitch), ("yaw", yaw), ("north", north), ("east", east),
                       ("vn", vn), ("ve", ve), ("vd", vd), ("elevator", elevator)):
            out[k][i] = val
    # measurement noise (seeded): the recorded values are noisy, the truth is not
    for k, s in (("alt", 0.3), ("speed", 0.05), ("roll", 0.2), ("pitch", 0.1)):
        out["m_" + k] = out[k] + rng.normal(0, s, n)
    # the navigation estimate: the truth with a slow error; the receiver: the truth with noise, lost at 150-170 s (gust file)
    lost = (t >= 150) & (t < 170) if gust else np.zeros(n, bool)
    drift = np.where(lost, (t - 150) * 0.6, 0.0)
    if gust:
        after = t >= 170
        drift[after] = 12.0 * np.exp(-(t[after] - 170) / 6.0)
    out["nav_n"] = out["north"] + 0.8 * np.sin(t / 37) + drift + rng.normal(0, 0.1, n)
    out["nav_e"] = out["east"] - 0.6 * np.cos(t / 29) + 0.5 * drift + rng.normal(0, 0.1, n)
    out["nav_alt"] = out["alt"] + 0.4 * np.sin(t / 23) + rng.normal(0, 0.1, n)
    out["gps_n"] = out["north"] + rng.normal(0, 1.2, n)
    out["gps_e"] = out["east"] + rng.normal(0, 1.2, n)
    out["gps_alt"] = out["alt"] + rng.normal(0, 2.0, n)
    for k in ("gps_n", "gps_e", "gps_alt"):
        out[k][lost] = np.nan
    out["lost"] = lost
    return t, out


def _lat(nm):
    return LAT0 + np.degrees(nm / R)


def _lon(em):
    return LON0 + np.degrees(em / (R * math.cos(math.radians(LAT0))))


def write(path: str, gust: bool):
    t, o = simulate(gust)
    cols = [
        ("time", t, "%.1f"),
        ("ctrl.alt_cmd [m]", o["alt_cmd"], "%.2f"), ("ctrl.alt [m]", o["m_alt"], "%.2f"),
        ("ctrl.speed_cmd [m/s]", o["speed_cmd"], "%.2f"), ("ctrl.speed [m/s]", o["m_speed"], "%.3f"),
        ("ctrl.roll_cmd [deg]", o["roll_cmd"], "%.2f"), ("ctrl.roll [deg]", o["m_roll"], "%.3f"),
        ("ctrl.pitch_cmd [deg]", o["pitch_cmd"], "%.3f"), ("ctrl.pitch [deg]", o["m_pitch"], "%.3f"),
        ("act.elevator [deg]", o["elevator"], "%.3f"),
        ("sim.lat [deg]", _lat(o["north"]), "%.7f"), ("sim.lon [deg]", _lon(o["east"]), "%.7f"), ("sim.alt [m]", o["alt"], "%.2f"),
        ("sim.att.roll [deg]", o["roll"], "%.3f"), ("sim.att.pitch [deg]", o["pitch"], "%.3f"), ("sim.att.yaw [deg]", o["yaw"], "%.3f"),
        ("sim.vel.north [m/s]", o["vn"], "%.3f"), ("sim.vel.east [m/s]", o["ve"], "%.3f"), ("sim.vel.down [m/s]", o["vd"], "%.3f"),
        ("nav.lat [deg]", _lat(o["nav_n"]), "%.7f"), ("nav.lon [deg]", _lon(o["nav_e"]), "%.7f"), ("nav.alt [m]", o["nav_alt"], "%.2f"),
        ("nav.att.roll [deg]", o["m_roll"], "%.3f"), ("nav.att.pitch [deg]", o["m_pitch"], "%.3f"), ("nav.att.yaw [deg]", o["yaw"] + 0.5, "%.3f"),
        ("nav.vel.north [m/s]", o["vn"] + np.gradient(o["nav_n"] - o["north"], t), "%.3f"),
        ("nav.vel.east [m/s]", o["ve"] + np.gradient(o["nav_e"] - o["east"], t), "%.3f"),
        ("nav.vel.down [m/s]", o["vd"], "%.3f"),
        ("gps.lat [deg]", _lat(o["gps_n"]), "%.7f"), ("gps.lon [deg]", _lon(o["gps_e"]), "%.7f"), ("gps.alt [m]", o["gps_alt"], "%.2f"),
    ]
    phase = [_phase(x) for x in t]
    status = ["LOST" if x else "OK" for x in o["lost"]]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([c[0] for c in cols] + ["mission.phase", "gps.status"])
        for i in range(len(t)):
            w.writerow(["" if not np.isfinite(c[1][i]) else (c[2] % c[1][i]).replace("-0.000", "0.000") for c in cols] + [phase[i], status[i]])


def main(folder: str):
    write(os.path.join(folder, "mission_ref.csv"), False)
    write(os.path.join(folder, "mission_gust.csv"), True)


if __name__ == "__main__":
    from svcore.example_data import REPO_EXAMPLES
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "report_demo"))
