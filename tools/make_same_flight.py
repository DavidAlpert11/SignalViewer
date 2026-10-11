#!/usr/bin/env python3
"""
One simulated flight recorded twice, for testing time alignment: the autopilot's log (.bin, time
since boot) and the ground station's telemetry (.tlog, Unix receive time with link latency), with a
known offset between them.

    python tools/make_same_flight.py out_dir [--boot-at 37.25] [--seconds 60]
    -> out_dir/flight.bin, out_dir/flight.tlog; prints the true offset
The .tlog starts recording when the autopilot has been up for --boot-at seconds, so the .tlog's
time + boot-at = the .bin's time (plus 10-60 ms of radio latency per packet).
"""
import argparse
import math
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import make_test_bin as mk                       # noqa: E402
os.environ.setdefault("MAVLINK20", "1")
from pymavlink.dialects.v20 import ardupilotmega as mav  # noqa: E402


def roll(t):                                     # the flight's roll angle, deg: a few distinct manoeuvres
    return 12 * math.sin(0.7 * t) + (20 if 18 < t < 21 else 0) - (15 if 33 < t < 34.5 else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--boot-at", type=float, default=37.25)
    ap.add_argument("--seconds", type=float, default=60)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    random.seed(1)
    T = a.seconds
    # ---- .bin: boot clock, the whole flight from boot 2 s
    mk.FMTS.clear()
    parts = [mk.header(), mk.fmt_msg(150, "ATT", "QffffffB", ["TimeUS", "DesRoll", "Roll", "DesPitch", "Pitch", "DesYaw", "Yaw", "AEKF"])]
    events = [(a.boot_at + 3, "MSG", b"Arming motors"), (a.boot_at + 3, "EV", 10), (a.boot_at + 15, "MODE", 5),
              (a.boot_at + 30, "MODE", 6), (a.boot_at + 31, "MSG", b"Reached waypoint #3"), (a.boot_at + 50, "EV", 11)]
    t = 2.0
    while t < a.boot_at + T:
        us = int(t * 1e6)
        r = roll(t - a.boot_at)
        parts.append(mk.msg("ATT", us, r, r + 0.2, 0, 0, 90, 90, 1))
        t += 0.02
    for te, kind, v in events:
        us = int(te * 1e6)
        parts.append(mk.msg("MSG", us, v) if kind == "MSG" else mk.msg("EV", us, v) if kind == "EV" else mk.msg("MODE", us, v, v))
    # messages must be in time order in a real log; the reader does not need it, but keep it tidy
    with open(os.path.join(a.out, "flight.bin"), "wb") as f:
        f.write(b"".join(parts))
    # ---- .tlog: starts boot-at s after boot, receive time = boot time - boot-at + latency
    v = mav.MAVLink(None, srcSystem=1, srcComponent=1)
    T0 = 1_760_000_000_000_000
    out = []

    def put(t_boot, msg):
        lat = random.uniform(0.010, 0.060)
        out.append((t_boot - a.boot_at + lat, msg.pack(v)))

    tb = a.boot_at
    mode = 0
    while tb < a.boot_at + T:
        r = math.radians(roll(tb - a.boot_at))
        put(tb, mav.MAVLink_attitude_message(int(tb * 1000), r, 0.0, 1.57, 0, 0, 0))
        if abs(tb * 4 - round(tb * 4)) < 1e-6:
            armed = a.boot_at + 3 <= tb < a.boot_at + 50
            mode = 6 if tb >= a.boot_at + 30 else 5 if tb >= a.boot_at + 15 else 0
            put(tb, mav.MAVLink_heartbeat_message(2, 3, 128 * armed | 1, mode, 4, 3))
        tb = round(tb + 0.1, 6)
    for te, kind, val in events:
        if kind == "MSG":
            put(te, mav.MAVLink_statustext_message(6, val))
    out.sort()
    with open(os.path.join(a.out, "flight.tlog"), "wb") as f:
        for tr, buf in out:
            f.write(struct.pack(">Q", int(T0 + tr * 1e6)) + buf)
    print(f"true offset: .tlog time + {a.boot_at} = .bin time (plus 10-60 ms latency)")


if __name__ == "__main__":
    main()
