#!/usr/bin/env python3
"""
Writes a synthetic ArduPilot DataFlash log (.bin) for testing the reader - modern style with
FMT, UNIT, MULT, FMTU, instanced IMU / GPS messages, MODE, MSG, PARM.

    python tools/make_test_bin.py out.bin [--seconds 60] [--imu-hz 400] [--corrupt]
    python tools/make_test_bin.py out.bin --live 30      # keeps appending for 30 s (live mode test)
"""
import argparse
import math
import struct
import time

FMTS = {}   # name -> (type, fmt, cols, struct)
SIZES = {"b": "b", "B": "B", "h": "h", "H": "H", "i": "i", "I": "I", "q": "q", "Q": "Q", "f": "f", "d": "d",
         "n": "4s", "N": "16s", "Z": "64s", "c": "h", "C": "H", "e": "i", "E": "I", "L": "i", "M": "B"}


def fmt_msg(typ, name, fmt, cols):
    st = struct.Struct("<" + "".join(SIZES[c] for c in fmt))
    FMTS[name] = (typ, fmt, cols, st)
    return struct.pack("<BBB", 0xA3, 0x95, 128) + struct.pack("<BB4s16s64s", typ, 3 + st.size, name.encode(),
                                                              fmt.encode(), ",".join(cols).encode())


def msg(name, *vals):
    typ, _fmt, _cols, st = FMTS[name]
    return struct.pack("<BBB", 0xA3, 0x95, typ) + st.pack(*vals)


def header():
    out = [fmt_msg(128, "FMT", "BBnNZ", ["Type", "Length", "Name", "Format", "Columns"]),
           fmt_msg(177, "UNIT", "QbZ", ["TimeUS", "Id", "Label"]),
           fmt_msg(178, "MULT", "Qbd", ["TimeUS", "Id", "Mult"]),
           fmt_msg(179, "FMTU", "QBNN", ["TimeUS", "FmtType", "UnitIds", "MultIds"]),
           fmt_msg(130, "IMU", "QBffffff", ["TimeUS", "I", "GyrX", "GyrY", "GyrZ", "AccX", "AccY", "AccZ"]),
           fmt_msg(131, "GPS", "QBBLLeHi", ["TimeUS", "I", "NSats", "Lat", "Lng", "Alt", "Spd", "RelAlt"]),
           fmt_msg(132, "ATT", "QccC", ["TimeUS", "Roll", "Pitch", "Yaw"]),
           fmt_msg(133, "MODE", "QBB", ["TimeUS", "Mode", "ModeNum"]),
           fmt_msg(134, "MSG", "QZ", ["TimeUS", "Message"]),
           fmt_msg(135, "PARM", "QNff", ["TimeUS", "Name", "Value", "Default"]),
           fmt_msg(136, "EV", "QB", ["TimeUS", "Id"]),
           fmt_msg(137, "ERR", "QBB", ["TimeUS", "Subsys", "ECode"]),
           fmt_msg(138, "VIBE", "QBfffI", ["TimeUS", "IMU", "VibeX", "VibeY", "VibeZ", "Clip"]),
           fmt_msg(139, "BAT", "QBfff", ["TimeUS", "Inst", "Volt", "Curr", "CurrTot"]),
           fmt_msg(140, "RCOU", "QHHHH", ["TimeUS", "C1", "C2", "C3", "C4"]),
           fmt_msg(141, "XKF4", "QBcccc", ["TimeUS", "C", "SV", "SP", "SH", "SM"]),
           fmt_msg(142, "POWR", "Qff", ["TimeUS", "Vcc", "VServo"])]
    for i, l in ((ord("s"), "s"), (ord("m"), "m"), (ord("E"), "rad/s"), (ord("o"), "m/s/s"),
                 (ord("d"), "deg"), (ord("D"), "deglatitude"), (ord("U"), "deglongitude"),
                 (ord("n"), "m/s"), (ord("#"), "instance"), (ord("-"), "")):
        out.append(msg("UNIT", 0, i, l.encode()))
    for i, v in ((ord("-"), 0), (ord("?"), 1), (ord("0"), 1), (ord("B"), 1e-2), (ord("F"), 1e-6), (ord("G"), 1e-7)):
        out.append(msg("MULT", 0, i, v))
    for name, u, m in (("IMU", "s#EEEooo", "F-000000"), ("GPS", "s#-DUmnm", "F--GGBBB"),
                       ("ATT", "sddd", "FBBB"), ("MODE", "s--", "F--")):
        out.append(msg("FMTU", 0, FMTS[name][0], u.encode(), m.encode()))
    out.append(msg("MSG", 0, b"ArduCopter V4.6.0 (synthetic)"))
    for name, v, d in (("ATC_RAT_RLL_P", 0.135, 0.135), ("ATC_RAT_PIT_P", 0.15, 0.135), ("BATT_CAPACITY", 5200, 3300),
                       ("INS_GYRO_FILTER", 20.0, 20.0), ("RTL_ALT", 1500, 1500), ("WPNAV_SPEED", 800, 1000),
                       ("BATT_LOW_VOLT", 14.0, 0), ("BATT_CRT_VOLT", 13.0, 0), ("MOT_PWM_MAX", 1950, 0), ("MOT_PWM_MIN", 1000, 0)):
        out.append(msg("PARM", 0, name.encode(), v, d))
    out.append(msg("MSG", 0, b"PreArm: Compass not calibrated"))
    return b"".join(out)


def body(t0, t1, imu_hz):
    out = []
    n = int((t1 - t0) * imu_hz)
    for k in range(n):
        t = t0 + k / imu_hz
        us = int(t * 1e6)
        g = int(round(t * imu_hz))            # sample number from the start of the log (not of this block)
        for inst in (0, 1):
            out.append(msg("IMU", us, inst, 0.1 * math.sin(t + inst), 0.05 * math.cos(t), 0.0,
                           0.2 * inst, -0.1, -9.81 + 0.05 * math.sin(7 * t)))
        if g % (imu_hz // 10) == 0:
            out.append(msg("ATT", us, int(1000 * math.sin(t / 3)), int(500 * math.cos(t / 5)), int(18000 + 100 * t) % 36000))
        if g % (imu_hz // 10) == 0:                          # 10 Hz: health-check material, with faults planted
            vib = 18 + (45 if 30 <= t < 32 else 0)               # vibration burst at 30 s
            out.append(msg("VIBE", us, 0, vib, 16, 22, int(max(0, t - 30.5) * 4) if t > 30.5 else 0))
            out.append(msg("BAT", us, 0, 16.4 - 0.08 * t, 15 + 5 * math.sin(t), t * 4))   # under 14 V after 30 s
            fly = 4 <= t < 38
            base = 1500 if fly else 1000
            sat = 1950 if 20 <= t < 21 else 0                    # motor 1 hits the top for a second
            out.append(msg("RCOU", us, max(base + 120, sat) if fly else 1000, base - 20 if fly else 1000,
                           base + 10 if fly else 1000, base - 10 if fly else 1000))
            out.append(msg("XKF4", us, 0, int(100 * (0.9 if 12 <= t < 13 else 0.1)), 10, 8, 20))   # SV 0.9 at 12 s
            out.append(msg("POWR", us, 5.05, 5.0))
        if g % (imu_hz // 5) == 0:
            for inst in (0, 1):
                out.append(msg("GPS", us, inst, 14 + inst, int((32.0853 + 1e-5 * t) * 1e7), int((34.7818 + 2e-5 * t) * 1e7),
                               int(1000 + 10 * t), int(250 + 50 * math.sin(t)), int(5000 + 100 * t)))
        if (g - imu_hz) % (imu_hz * 10) == 0:
            out.append(msg("MODE", us, int(t // 10) % 6, 0))
            out.append(msg("MSG", us, f"t={t:.0f}s".encode()))
            out.append(msg("PARM", us, b"INS_GYRO_FILTER", 20.0 + int(t // 10) * 5, 20.0))   # tuned in flight
        if g == imu_hz * 4:
            out.append(msg("EV", us, 10))                                  # ARMED
        if g == imu_hz * 8:
            out.append(msg("ERR", us, 16, 2))
            out.append(msg("MSG", us, b"EKF variance"))
    return b"".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--imu-hz", type=int, default=400)
    ap.add_argument("--corrupt", action="store_true", help="insert garbage + a cut message in the middle")
    ap.add_argument("--live", type=float, default=0, help="keep appending for this many seconds")
    a = ap.parse_args()
    data = header() + body(1.0, 1.0 + a.seconds / 2, a.imu_hz)
    if a.corrupt:
        data += b"\xa3\x95\x82garbage\xa3\x95" + bytes(range(40))
    data += body(1.0 + a.seconds / 2, 1.0 + a.seconds, a.imu_hz)
    with open(a.out, "wb") as f:
        f.write(data)
    if a.live:
        t, end = 1.0 + a.seconds, time.time() + a.live
        while time.time() < end:
            time.sleep(0.25)
            chunk = body(t, t + 0.25, a.imu_hz)
            with open(a.out, "ab") as f:
                f.write(chunk[: len(chunk) - 7])     # leave a cut message: the reader must wait for it
                f.flush()
                f.write(chunk[len(chunk) - 7:])
            t += 0.25


if __name__ == "__main__":
    main()
