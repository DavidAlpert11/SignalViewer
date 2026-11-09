#!/usr/bin/env python3
"""
The three-object recording of the 2026-11-09 round (N1, N5, N6, N7): one aircraft seen three ways -
simulation truth (`phys.*`), a navigation solution (`nav.*`, truth plus a slow drift and noise) and a
GPS receiver (`gps.*`, position only, 5 Hz: its cells are empty between fixes, so missing stays
missing). The 19 signals (plus time) are the ones the round's findings were verified with:

    time, phys.lat, phys.lon, phys.alt, phys.att.roll/pitch/yaw, phys.vel.north/east,
    nav.lat, nav.lon, nav.alt, nav.att.roll/pitch/yaw, nav.vel.north/east, gps.lat, gps.lon, gps.alt

The flight: 120 s at 10 Hz, a left-hand circle of 600 m radius at 60 m/s with a
gentle climb, so heading wraps through 359/0 deg and the errors have a known shape. Seeded: the file is
the same on every run.

    python tools/make_objects_fixture.py            # writes examples/three_objects.csv
"""
import math
import os
import random

OUT = os.path.join(os.path.dirname(__file__), "..", "examples", "three_objects.csv")
R_EARTH = 6378137.0
LAT0, LON0, ALT0 = 32.80, 35.60, 300.0          # the area of the other examples
RADIUS, SPEED, CLIMB = 600.0, 60.0, 1.0          # m, m/s, m/s
RATE, DURATION = 10, 120                          # Hz, s


def truth(t):
    """North / east offset (m), altitude, attitude (deg) and NED velocity of the circle at time t."""
    w = SPEED / RADIUS                            # rad/s, turning left (counter-clockwise seen from above)
    a = w * t
    n, e = RADIUS * math.sin(a), RADIUS * (1 - math.cos(a)) * -1
    vn, ve = SPEED * math.cos(a), -SPEED * math.sin(a)
    yaw = math.degrees(math.atan2(ve, vn)) % 360
    roll = -math.degrees(math.atan(SPEED * w / 9.80665))   # banked left
    pitch = math.degrees(math.atan2(CLIMB, SPEED))
    return n, e, ALT0 + CLIMB * t, roll, pitch, yaw, vn, ve


def to_lla(n, e, alt):
    return LAT0 + math.degrees(n / R_EARTH), LON0 + math.degrees(e / (R_EARTH * math.cos(math.radians(LAT0)))), alt


def main():
    rnd = random.Random(20261109)
    cols = ["time", "phys.lat", "phys.lon", "phys.alt", "phys.att.roll", "phys.att.pitch", "phys.att.yaw",
            "phys.vel.north", "phys.vel.east", "nav.lat", "nav.lon", "nav.alt", "nav.att.roll",
            "nav.att.pitch", "nav.att.yaw", "nav.vel.north", "nav.vel.east", "gps.lat", "gps.lon", "gps.alt"]
    rows = [",".join(cols)]
    for i in range(RATE * DURATION + 1):
        t = i / RATE
        n, e, alt, roll, pitch, yaw, vn, ve = truth(t)
        phys = [*to_lla(n, e, alt), roll, pitch, yaw, vn, ve]
        dn, de, dh = 0.02 * t + rnd.gauss(0, 0.3), -0.01 * t + rnd.gauss(0, 0.3), rnd.gauss(0, 0.5)  # drift + noise
        nav = [*to_lla(n + dn, e + de, alt + dh), roll + rnd.gauss(0, 0.2), pitch + rnd.gauss(0, 0.2),
               (yaw + 0.5 + rnd.gauss(0, 0.3)) % 360, vn + rnd.gauss(0, 0.1), ve + rnd.gauss(0, 0.1)]
        gps = [*to_lla(n + rnd.gauss(0, 2.0), e + rnd.gauss(0, 2.0), alt + rnd.gauss(0, 4.0))] if i % 2 == 0 else None
        cells = [f"{t:.1f}"]
        cells += [f"{phys[0]:.8f}", f"{phys[1]:.8f}", f"{phys[2]:.2f}"] + [f"{v:.3f}" for v in phys[3:]]
        cells += [f"{nav[0]:.8f}", f"{nav[1]:.8f}", f"{nav[2]:.2f}"] + [f"{v:.3f}" for v in nav[3:]]
        cells += [f"{gps[0]:.8f}", f"{gps[1]:.8f}", f"{gps[2]:.2f}"] if gps else ["", "", ""]
        rows.append(",".join(cells))
    with open(OUT, "w", newline="\n") as f:
        f.write("\n".join(rows) + "\n")
    print(f"{os.path.normpath(OUT)}: {len(rows) - 1} rows, {len(cols)} columns")


if __name__ == "__main__":
    main()
