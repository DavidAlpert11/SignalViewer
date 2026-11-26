#!/usr/bin/env python3
"""
AU4 (owner, 2026-11-26: "suggest to the user what to record, so he knows it is worth producing such variables"):
one platform recorded the way the app recognises by itself - every *Found in this file* find lights up:

    6dof.*                    the simulation's truth (a 6-DOF model): lat / lon / alt, att.roll / pitch / yaw, vel.n / e / d
    ins.*                     the navigation system of the same platform: the truth plus a drift, a bias and noise
    ctrl.<x>_cmd / ctrl.<x>   commands and what the platform did (roll, alt, speed)
    mode                      a text column - the flight phase (TAKEOFF, CLIMB, CRUISE, TURN, DESCENT)
    imu[0].* / imu[1].*       two copies of one accelerometer; the second's x axis drifts away at 150 s
    act.*                     what drives it: the elevator servo, the throttle (saturates in the climb)

The flight: 240 s at 10 Hz - a take-off, a climb, a cruise, a turn, a descent. Seeded: the file is the same on
every run (byte for byte: fixed number formats).

    python tools/make_automations_example.py        # writes examples/automations/platform_run.csv
"""
import math
import os
import random

from . import REPO_EXAMPLES

R_EARTH = 6378137.0
LAT0, LON0, ALT0 = 32.80, 35.60, 0.0
RATE, DURATION = 10, 240
G = 9.80665

PHASES = [(0, "TAKEOFF"), (20, "CLIMB"), (80, "CRUISE"), (140, "TURN"), (200, "DESCENT")]


def phase(t):
    return [p for t0, p in PHASES if t >= t0][-1]


def commands(t):
    """The commanded roll (deg), altitude (m) and speed (m/s) at time t."""
    m = phase(t)
    roll = 25.0 if m == "TURN" else (8.0 if 100 <= t < 110 else 0.0)        # a doublet in the cruise
    alt = {"TAKEOFF": 20.0, "CLIMB": 150.0, "CRUISE": 150.0, "TURN": 150.0, "DESCENT": 40.0}[m]
    speed = {"TAKEOFF": 18.0, "CLIMB": 22.0, "CRUISE": 25.0, "TURN": 23.0, "DESCENT": 20.0}[m]
    return roll, alt, speed


def lag(prev, want, tau, dt):
    return prev + (want - prev) * (1 - math.exp(-dt / tau))


def main(out=None):
    folder = os.path.join(out or REPO_EXAMPLES, "automations")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "platform_run.csv")
    rnd = random.Random(20261126)
    dt = 1.0 / RATE
    cols = ["time", "mode",
            "6dof.lat", "6dof.lon", "6dof.alt", "6dof.att.roll", "6dof.att.pitch", "6dof.att.yaw",
            "6dof.vel.n", "6dof.vel.e", "6dof.vel.d",
            "ins.lat", "ins.lon", "ins.alt", "ins.att.roll", "ins.att.pitch", "ins.att.yaw",
            "ins.vel.n", "ins.vel.e", "ins.vel.d",
            "ctrl.roll_cmd", "ctrl.roll", "ctrl.alt_cmd", "ctrl.alt", "ctrl.speed_cmd", "ctrl.speed",
            "imu[0].ax", "imu[0].ay", "imu[0].az", "imu[1].ax", "imu[1].ay", "imu[1].az",
            "act.servo_elevator", "act.throttle"]
    rows = [",".join(cols)]
    n = e = 0.0
    alt, roll, speed, yaw, pitch = ALT0, 0.0, 15.0, 30.0, 0.0       # a catapult launch: 15 m/s at once
    drift_n = drift_e = 0.0
    for i in range(RATE * DURATION + 1):
        t = i * dt
        rc, ac, sc = commands(t)
        roll = lag(roll, rc, 0.8, dt)
        before = speed
        speed = lag(speed, sc, 4.0, dt)
        climb = max(-4.0, min(5.0, 0.15 * (ac - alt)))
        alt += climb * dt
        pitch = math.degrees(math.atan2(climb, max(speed, 1.0)))
        yaw = (yaw + math.degrees(G * math.tan(math.radians(roll)) / max(speed, 1.0)) * dt) % 360
        vn, ve, vd = speed * math.cos(math.radians(yaw)), speed * math.sin(math.radians(yaw)), -climb
        n += vn * dt
        e += ve * dt
        lat = LAT0 + math.degrees(n / R_EARTH)
        lon = LON0 + math.degrees(e / (R_EARTH * math.cos(math.radians(LAT0))))
        # the INS: a slow drift, a heading bias, noise
        drift_n += rnd.gauss(0.0, 0.02)
        drift_e += rnd.gauss(0.0, 0.02)
        ilat = LAT0 + math.degrees((n + drift_n + 0.01 * t) / R_EARTH)
        ilon = LON0 + math.degrees((e + drift_e) / (R_EARTH * math.cos(math.radians(LAT0))))
        ins = [ilat, ilon, alt + rnd.gauss(0.0, 0.6), roll + rnd.gauss(0.0, 0.3), pitch + rnd.gauss(0.0, 0.3),
               (yaw + 0.8 + rnd.gauss(0.0, 0.2)) % 360, vn + rnd.gauss(0.0, 0.15), ve + rnd.gauss(0.0, 0.15),
               vd + rnd.gauss(0.0, 0.1)]
        ax = (speed - before) / dt
        ay = G * math.tan(math.radians(roll))
        az = -G
        imu0 = [ax + rnd.gauss(0.0, 0.05), ay + rnd.gauss(0.0, 0.05), az + rnd.gauss(0.0, 0.05)]
        bad = 0.02 * (t - 150.0) if t > 150.0 else 0.0                         # the second copy drifts away
        imu1 = [ax + bad + rnd.gauss(0.0, 0.05), ay + rnd.gauss(0.0, 0.05), az + rnd.gauss(0.0, 0.05)]
        elev = max(-25.0, min(25.0, -2.0 * climb + rnd.gauss(0.0, 0.3)))
        thr = max(0.0, min(100.0, 45.0 + 4.0 * (sc - speed) + 12.0 * climb))
        cells = [f"{t:.1f}", phase(t),
                 f"{lat:.8f}", f"{lon:.8f}", f"{alt:.2f}", f"{roll:.3f}", f"{pitch:.3f}", f"{yaw:.3f}",
                 f"{vn:.3f}", f"{ve:.3f}", f"{vd:.3f}",
                 f"{ins[0]:.8f}", f"{ins[1]:.8f}", *(f"{v:.3f}" for v in ins[2:]),
                 f"{rc:.1f}", f"{roll + rnd.gauss(0.0, 0.2):.3f}", f"{ac:.1f}", f"{alt:.2f}", f"{sc:.1f}", f"{speed:.3f}",
                 *(f"{v:.4f}" for v in imu0), *(f"{v:.4f}" for v in imu1),
                 f"{elev:.2f}", f"{thr:.1f}"]
        rows.append(",".join(cells))
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(rows) + "\n")
    print("wrote", path)
    return path


if __name__ == "__main__":
    main()
