#!/usr/bin/env python3
"""
Writes a synthetic MAVLink telemetry log (.tlog) for testing: an ArduCopter (system 1) plus a ground
station's heartbeats (system 255), attitude, GPS, battery, vibration, mode changes, arming,
STATUSTEXT and parameters, in MAVLink 2 (and a few MAVLink 1 packets).

    python tools/make_test_tlog.py out.tlog [--seconds 60] [--live 30]
"""
import argparse
import math
import os
import struct
import time

os.environ.setdefault("MAVLINK20", "1")
from pymavlink.dialects.v20 import ardupilotmega as mav  # noqa: E402

T0 = 1_760_000_000_000_000          # some Unix time, microseconds


class Writer:
    def __init__(self, f):
        self.f = f
        self.v = mav.MAVLink(None, srcSystem=1, srcComponent=1)
        self.g = mav.MAVLink(None, srcSystem=255, srcComponent=190)

    def put(self, t, msg, gcs=False, v1=False):
        m = self.g if gcs else self.v
        if v1:
            m.WIRE_PROTOCOL_VERSION = "1.0"
        buf = msg.pack(m)
        m.WIRE_PROTOCOL_VERSION = "2.0"
        self.f.write(struct.pack(">Q", int(T0 + t * 1e6)) + buf)


def block(w: Writer, t0, t1, rate=20):
    n = int((t1 - t0) * rate)
    for k in range(n):
        t = t0 + k / rate
        g = int(round(t * rate))
        if g % rate == 0:                                      # 1 Hz
            mode = 5 if t < 20 else (6 if t < 40 else 9)        # LOITER, RTL, LAND
            armed = 5 <= t < 50
            w.put(t, mav.MAVLink_heartbeat_message(2, 3, 128 * armed | 1, mode, 4, 3))
            w.put(t + 0.001, mav.MAVLink_heartbeat_message(6, 8, 0, 0, 0, 3), gcs=True)
            w.put(t + 0.002, mav.MAVLink_sys_status_message(0, 0, 0, 500, int((16.4 - 0.02 * (t % 60)) * 1000), 1500, 80,
                                                           0, 0, 0, 0, 0, 0), v1=True)
            w.put(t + 0.003, mav.MAVLink_battery_status_message(0, 1, 1, 2500, [4100, 4090, 4080, 4070] + [65535] * 6,
                                                               1500, int(t * 10), -1, 80))
            w.put(t + 0.004, mav.MAVLink_vibration_message(int(t * 1e6), 12 + (30 if 30 <= t < 33 else 0), 11, 14, 0, 0, 0))
        if g % (rate // 5) == 0:                               # 5 Hz
            w.put(t + 0.005, mav.MAVLink_gps_raw_int_message(int(t * 1e6), 3, int((32.0853 + 1e-5 * t) * 1e7),
                                                             int((34.7818 + 2e-5 * t) * 1e7), int((50 + t) * 1000), 90, 120,
                                                             500, 9000, 12 if t < 25 else 5))
        w.put(t + 0.006, mav.MAVLink_attitude_message(int(t * 1000), 0.1 * math.sin(t), 0.05 * math.cos(t), 1.0, 0, 0, 0))
        if k == 0 and t0 == 0:
            w.put(t, mav.MAVLink_statustext_message(6, b"ArduCopter V4.5.7 (2a3dc4b7)"))
            w.put(t, mav.MAVLink_statustext_message(4, b"PreArm: GPS not healthy"))
            for i, (nm, v) in enumerate((("ATC_RAT_RLL_P", 0.135), ("BATT_CAPACITY", 5200), ("RTL_ALT", 1500))):
                w.put(t + 0.01 * i, mav.MAVLink_param_value_message(nm.encode(), v, 9, 3, i))
        if abs(t - 35) < 1e-9:
            w.put(t, mav.MAVLink_statustext_message(2, b"EKF variance"))
            w.put(t, mav.MAVLink_param_value_message(b"RTL_ALT", 2000, 9, 3, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--live", type=float, default=0)
    a = ap.parse_args()
    with open(a.out, "wb") as f:
        w = Writer(f)
        block(w, 0, a.seconds)
    if a.live:
        t, end = a.seconds, time.time() + a.live
        while time.time() < end:
            time.sleep(0.25)
            with open(a.out, "ab") as f:
                block(Writer(f), t, t + 0.25)
            t += 0.25


if __name__ == "__main__":
    main()
