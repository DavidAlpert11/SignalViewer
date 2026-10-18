#!/usr/bin/env python3
"""
The ArduPilot example on the welcome screen (T45): a 4-minute quad-copter flight written as a real
DataFlash log (.bin), so the flight-log features show on it - flight modes, the health summary,
the ArduPilot templates, the map and 3D.

    python tools/make_example_bin.py [out.bin]      # default: examples/copter_flight.bin

The flight, from a field by Ein Gev (Sea of Galilee, ground -198 m): GPS fix, arm, a hand take-off
in STABILIZE, ALT_HOLD, LOITER, an AUTO mission of five waypoints at 40 m in a 3 m/s westerly, RTL,
LAND, disarm. Planted for the health summary: a loose-propeller vibration burst in the mission
(VIBE over 30 with clipping, "Vibration compensation ON"); battery, GPS, EKF and motors healthy.
A simple point-mass model (tilt from acceleration + drag, motors from thrust + the attitude
torques) keeps the signals consistent with each other: the attitude follows the turns, the
current the climbs, the motors the attitude. Deterministic (fixed seed).
"""
import math
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_test_bin as mk  # noqa: E402  (FMT / message writer)

HOME = (32.7840, 35.6420, -198.0)          # lat, lon, ground AMSL (the app's DEM there)
DT = 0.04                                   # 25 Hz model step
WIND = np.array([0.0, 3.0])                 # m/s (north, east): from the west
GPS_START = (2026, 9, 14, 6, 30, 0)         # UTC at boot - the fleet view's flight date


def formats():
    mk.FMTS.clear()
    f = mk.fmt_msg
    return [
        f(128, "FMT", "BBnNZ", ["Type", "Length", "Name", "Format", "Columns"]),
        f(177, "UNIT", "QbZ", ["TimeUS", "Id", "Label"]),
        f(178, "MULT", "Qbd", ["TimeUS", "Id", "Mult"]),
        f(179, "FMTU", "QBNN", ["TimeUS", "FmtType", "UnitIds", "MultIds"]),
        f(130, "PARM", "QNff", ["TimeUS", "Name", "Value", "Default"]),
        f(131, "MSG", "QZ", ["TimeUS", "Message"]),
        f(132, "EV", "QB", ["TimeUS", "Id"]),
        f(133, "MODE", "QMBB", ["TimeUS", "Mode", "ModeNum", "Rsn"]),
        f(134, "ATT", "QffffffB", ["TimeUS", "DesRoll", "Roll", "DesPitch", "Pitch", "DesYaw", "Yaw", "AEKF"]),
        f(135, "RATE", "Qffffff", ["TimeUS", "RDes", "R", "PDes", "P", "YDes", "Y"]),
        f(136, "IMU", "QBffffff", ["TimeUS", "I", "GyrX", "GyrY", "GyrZ", "AccX", "AccY", "AccZ"]),
        f(137, "VIBE", "QBfffI", ["TimeUS", "IMU", "VibeX", "VibeY", "VibeZ", "Clip"]),
        f(138, "GPS", "QBBIHBfLLefffB", ["TimeUS", "I", "Status", "GMS", "GWk", "NSats", "HDop", "Lat", "Lng",
                                          "Alt", "Spd", "GCrs", "VZ", "U"]),
        f(139, "BAT", "QBfffff", ["TimeUS", "Inst", "Volt", "VoltR", "Curr", "CurrTot", "EnrgTot"]),
        f(140, "POWR", "Qff", ["TimeUS", "Vcc", "VServo"]),
        f(141, "CTUN", "Qffffffff", ["TimeUS", "ThI", "ThO", "ThH", "DAlt", "Alt", "BAlt", "DCRt", "CRt"]),
        f(142, "BARO", "QBfff", ["TimeUS", "I", "Alt", "Press", "Temp"]),
        f(143, "RCIN", "QHHHH", ["TimeUS", "C1", "C2", "C3", "C4"]),
        f(144, "RCOU", "QHHHH", ["TimeUS", "C1", "C2", "C3", "C4"]),
        f(145, "XKF3", "QBfff", ["TimeUS", "C", "IVN", "IVE", "IVD"]),
        f(146, "XKF4", "QBffff", ["TimeUS", "C", "SV", "SP", "SH", "SM"]),
    ]


def metadata():
    out = []
    units = (("s", "s"), ("m", "m"), ("n", "m/s"), ("o", "m/s/s"), ("d", "deg"), ("k", "deg/s"), ("E", "rad/s"),
             ("D", "deglatitude"), ("U", "deglongitude"), ("v", "V"), ("A", "A"), ("a", "Ah"), ("w", "Wh"),
             ("P", "Pa"), ("O", "degC"), ("Y", "PWM"), ("S", "satellites"), ("h", "degheading"), ("#", "instance"),
             ("-", ""))
    for i, label in units:
        out.append(mk.msg("UNIT", 0, ord(i), label.encode()))
    for i, v in (("-", 0), ("?", 1), ("0", 1), ("B", 1e-2), ("C", 1e-3), ("F", 1e-6), ("G", 1e-7)):
        out.append(mk.msg("MULT", 0, ord(i), v))
    fmtu = {"ATT": ("sdddddd-", "F-------"), "RATE": ("skkkkkk", "F------"),
            "IMU": ("s#EEEooo", "F-------"), "VIBE": ("s#ooo-", "F-----"),
            "GPS": ("s#-s-S-DUmnhn-", "F--C-0-GGB000-"),          # as ArduPilot writes it (GMS: ms)
            "BAT": ("s#vvAaw", "F------"), "POWR": ("svv", "F--"), "CTUN": ("s---mmmnn", "F--------"),
            "BARO": ("s#mPO", "F----"), "RCIN": ("sYYYY", "F----"), "RCOU": ("sYYYY", "F----"),
            "XKF3": ("s#nnn", "F----"), "XKF4": ("s#----", "F-----"), "MODE": ("s---", "F---")}
    for name, (u, m) in fmtu.items():
        assert len(u) == len(m) == len(mk.FMTS[name][1]), name
        out.append(mk.msg("FMTU", 0, mk.FMTS[name][0], u.encode(), m.encode()))
    return out


PARAMS = (("FRAME_CLASS", 1, 0), ("FRAME_TYPE", 1, 1), ("BATT_CAPACITY", 5200, 3300), ("BATT_LOW_VOLT", 14.0, 10.5),
          ("BATT_CRT_VOLT", 13.2, 0), ("BATT_FS_LOW_ACT", 2, 0), ("MOT_PWM_MIN", 1000, 0), ("MOT_PWM_MAX", 2000, 0),
          ("MOT_SPIN_ARM", 0.1, 0.1), ("MOT_THST_HOVER", 0.38, 0.35), ("FS_EKF_THRESH", 0.8, 0.8),
          ("WPNAV_SPEED", 800, 1000), ("WPNAV_ACCEL", 250, 250), ("RTL_ALT", 3000, 1500), ("LAND_SPEED", 50, 50),
          ("ATC_RAT_RLL_P", 0.135, 0.135), ("ATC_RAT_RLL_I", 0.135, 0.135), ("ATC_RAT_RLL_D", 0.0036, 0.0036),
          ("ATC_RAT_PIT_P", 0.135, 0.135), ("ATC_RAT_PIT_I", 0.135, 0.135), ("ATC_RAT_PIT_D", 0.0036, 0.0036),
          ("ATC_RAT_YAW_P", 0.18, 0.18), ("INS_GYRO_FILTER", 40, 20), ("INS_HNTCH_ENABLE", 1, 0),
          ("INS_HNTCH_FREQ", 80, 80), ("GPS_TYPE", 2, 1), ("EK3_ENABLE", 1, 1), ("LOG_BITMASK", 180222, 176126))

# (time since boot s, mode name, ArduCopter mode number, reason) - reason 1 = RC, 2 = GCS, 3 = RTL / mission
MODES = ((1.0, "STABILIZE", 0, 0), (34.0, "ALT_HOLD", 2, 1), (46.0, "LOITER", 5, 1), (60.0, "AUTO", 3, 2),
         (177.0, "RTL", 6, 3), (218.0, "LAND", 9, 1))         # RTL: the mission's last command
WAYPOINTS = ((150, -20, 40), (150, 140, 40), (-40, 170, 40), (-140, 30, 40), (-30, -120, 40))   # north, east, up (m)
T_ARM, T_TAKEOFF, T_END = 22.0, 25.0, 246.0
VIB = (137.0, 143.0)                        # the loose propeller, mid-leg (not in a turn)


def gps_time(t_boot):
    import calendar
    epoch = calendar.timegm(GPS_START) - calendar.timegm((1980, 1, 6, 0, 0, 0)) + 18      # GPS is 18 s ahead of UTC
    s = epoch + t_boot
    return int(s // 604800), int((s % 604800) * 1000)


def mode_at(t):
    m = MODES[0]
    for x in MODES:
        if t >= x[0]:
            m = x
    return m


def simulate():
    """Point-mass flight at 25 Hz -> arrays of position, velocity, acceleration, yaw, phase."""
    n = int(T_END / DT)
    t = np.arange(n) * DT
    pos, vel = np.zeros(3), np.zeros(3)
    P, V, A, Y = np.zeros((n, 3)), np.zeros((n, 3)), np.zeros((n, 3)), np.zeros(n)
    wp_i, yaw, landed_at = 0, math.radians(35.0), None      # parked facing 35 deg (not north: no 0/360 flicker)
    events = []
    for k, tk in enumerate(t):
        name = mode_at(tk)[1]
        vdes = np.zeros(3)
        if tk < T_TAKEOFF or landed_at is not None:
            vdes[:] = 0
        elif name == "STABILIZE":                       # hand take-off to ~8 m, a little forward
            vdes[2] = 1.6 if pos[2] < 8 else 0.0
            vdes[0] = 1.0 if 29 < tk < 32 else 0.0
        elif name == "ALT_HOLD":                        # the pilot moves it east and back
            vdes[1] = 2.0 if tk < 39 else -2.0 if tk < 44 else 0.0
        elif name == "LOITER":                          # climbs to 20 m, turns to the mission
            vdes[2] = 1.5 if pos[2] < 20 else 0.0
        elif name == "AUTO":
            tgt = np.array(WAYPOINTS[min(wp_i, len(WAYPOINTS) - 1)], float)
            d = tgt - pos
            dist = np.linalg.norm(d[:2])
            if dist < 3 and wp_i < len(WAYPOINTS):
                events.append((tk, f"Reached command #{wp_i + 2}"))
                wp_i += 1
            sp = min(8.0, math.sqrt(2 * 1.8 * max(dist, 0)))
            vdes[:2] = d[:2] / max(dist, 1e-6) * sp
            vdes[2] = np.clip(d[2] * 0.5, -1.5, 2.5)
        elif name == "RTL":                             # home at mission height, then down
            d = -pos
            dist = np.linalg.norm(d[:2])
            vdes[:2] = d[:2] / max(dist, 1e-6) * min(8.0, math.sqrt(2 * 1.8 * dist))
            vdes[2] = 0.0 if dist > 2 else -1.5 if pos[2] > 10 else -0.5
        elif name == "LAND":
            vdes[:2] = -pos[:2] * 0.3
            vdes[2] = -1.0 if pos[2] > 10 else -0.5
        acc = np.clip((vdes - vel) / 1.2, -2.0, 2.0)
        if landed_at is None and tk > T_TAKEOFF + 5 and pos[2] <= 0.05 and vdes[2] < 0:
            landed_at = tk
            events.append((tk, "LAND_COMPLETE"))
        vel = vel + acc * DT
        pos = pos + vel * DT
        if pos[2] < 0:
            pos[2], vel[2] = 0.0, max(vel[2], 0.0)
        if np.hypot(vel[0], vel[1]) > 1.5 and name in ("AUTO", "RTL"):     # nose along the track
            want = math.atan2(vel[1], vel[0])
            yaw += np.clip((want - yaw + math.pi) % (2 * math.pi) - math.pi, -0.035, 0.035)  # ~50 deg/s
        elif name == "LOITER" and tk > 52:
            yaw += np.clip((math.atan2(WAYPOINTS[0][1], WAYPOINTS[0][0]) - yaw + math.pi) % (2 * math.pi) - math.pi, -0.02, 0.02)
        P[k], V[k], A[k], Y[k] = pos, vel, acc, yaw
    return t, P, V, A, Y, events, landed_at


def main(out=None):
    out = out or (sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                                                       "examples", "copter_flight.bin"))
    rng = np.random.default_rng(45)
    t, P, V, A, Y, ev, landed_at = simulate()
    rtl = next(m[0] for m in MODES if m[1] == "RTL")
    assert len(ev) > len(WAYPOINTS) and ev[len(WAYPOINTS) - 1][0] < rtl, "the mission must end before RTL"
    assert landed_at and landed_at < T_END - 3, "landed and disarmed before the log ends"
    n, g = len(t), 9.81
    # attitude needed: acceleration + drag against the air (wind) -> tilt in the body frame
    air = V.copy()
    air[:, :2] -= WIND * (P[:, 2:3] > 0.5)
    f_n = A[:, 0] + 0.12 * air[:, 0]
    f_e = A[:, 1] + 0.12 * air[:, 1]
    cy, sy = np.cos(Y), np.sin(Y)
    fx, fy = f_n * cy + f_e * sy, -f_n * sy + f_e * cy
    flying = P[:, 2] > 0.05
    des_pitch = np.where(flying, -np.degrees(np.arctan(fx / g)), 0.0)
    des_roll = np.where(flying, np.degrees(np.arctan(fy / g)), 0.0)
    lag = np.exp(-DT / 0.08)                                   # the vehicle follows with ~80 ms lag

    def follow(x):
        y = np.empty_like(x)
        acc = x[0]
        for i, v in enumerate(x):
            acc = lag * acc + (1 - lag) * v
            y[i] = acc
        return y
    in_vib = (t >= VIB[0]) & (t < VIB[1])
    shake = np.where(in_vib, 1.6, 0.25)
    roll = follow(des_roll) + rng.normal(0, 1, n) * shake * flying
    pitch = follow(des_pitch) + rng.normal(0, 1, n) * shake * flying
    yaw_deg = np.degrees(Y) % 360
    des_yaw = yaw_deg.copy()
    yaw_act = (follow(np.degrees(np.unwrap(Y))) + rng.normal(0, 0.3, n) * flying) % 360
    grad = lambda x: np.gradient(x, DT)  # noqa: E731
    r_des, p_des, y_des = grad(des_roll), grad(des_pitch), grad(np.degrees(np.unwrap(Y)))
    r_act, p_act, y_act = grad(roll), grad(pitch), grad(np.degrees(np.unwrap(np.radians(yaw_act))))
    # thrust and motors (quad X: 1 front-right, 2 back-left, 3 front-left, 4 back-right)
    thrust = np.where(flying | (t > T_TAKEOFF) & (t < (landed_at or T_END)), (g + A[:, 2] + 0.3 * V[:, 2]) / g, 0)
    tilt = np.sqrt(1 + (fx / g) ** 2 + (fy / g) ** 2)
    thr = np.clip(0.38 * thrust * tilt, 0, 1)                  # MOT_THST_HOVER 0.38
    armed = (t >= T_ARM) & (t < (landed_at or T_END) + 2.5)
    thr = np.where(armed, np.maximum(thr, 0.1), 0)            # MOT_SPIN_ARM
    rr, pp, yy = np.gradient(r_act, DT) * 0.004, np.gradient(p_act, DT) * 0.004, y_act * 0.002
    mix = np.array([[-1, 1, 1], [1, -1, 1], [1, 1, -1], [-1, -1, -1]], float)   # roll, pitch, yaw per motor
    pwm = []
    for m in range(4):
        u = thr + np.clip(mix[m, 0] * rr + mix[m, 1] * pp + mix[m, 2] * yy, -0.12, 0.12) * (thr > 0.15)
        u = u + rng.normal(0, 0.004 if m != 2 else 0.006, n) * (thr > 0.15) + np.where(in_vib & (m == 2), 0.03, 0)
        pwm.append(np.where(armed, 1000 + 1000 * np.clip(np.sqrt(np.maximum(u, 0)), 0, 1) ** 2, 1000))
    # battery 4S 5200 mAh
    cur = np.where(armed, 0.8 + 52 * thr ** 1.5, 0.6) + rng.normal(0, 0.15, n)
    mah = np.cumsum(cur) * DT / 3.6
    soc = 1 - mah / 5200 - 0.04
    ocv = 4 * (3.5 + 0.7 * soc - 0.15 * np.exp(-12 * soc) + 0.05 * soc ** 2)
    volt = ocv - cur * 0.022 + rng.normal(0, 0.01, n)
    wh = np.cumsum(volt * cur) * DT / 3600
    # vibration (m/s/s) and clipping
    vib_lvl = np.where(armed, 7 + 6 * thr, 0.3)
    vibe = [vib_lvl * k + np.abs(rng.normal(0, 0.8, n)) for k in (1.0, 1.1, 1.6)]
    burst = np.where(in_vib, np.sin(np.pi * (t - VIB[0]) / (VIB[1] - VIB[0])), 0)
    vibe = [v + burst * a for v, a in zip(vibe, (22, 26, 34))]
    clip = np.cumsum((burst > 0.6) & (rng.random(n) < 0.2)).astype(int)
    # sensors
    lat = HOME[0] + np.degrees(P[:, 0] / 6371000)
    lon = HOME[1] + np.degrees(P[:, 1] / (6371000 * math.cos(math.radians(HOME[0]))))
    baro_alt = P[:, 2] + 0.15 * np.sin(t / 7) + rng.normal(0, 0.08, n)
    gs = np.hypot(V[:, 0], V[:, 1])
    crs = (np.degrees(np.arctan2(V[:, 1], V[:, 0])) + 360) % 360
    alt_des = np.where(flying, np.r_[P[0, 2], P[:-1, 2]] + 0.1, 0)
    sv = 0.06 + 0.04 * np.abs(np.sin(t / 13)) + burst * 0.32 + np.abs(rng.normal(0, 0.01, n))
    events = {round(te / DT): txt for te, txt in ev}

    parts = formats() + metadata()
    us = lambda tk: int(tk * 1e6) + 412_000  # noqa: E731  (the log starts 0.4 s after boot)
    for txt in ("ArduCopter V4.6.2 (8b2c1d7e)", "ChibiOS: 1a2b3c4d", "CubeOrange 00340024 3138510B 37373332",
                "RCOut: PWM:1-14", "Frame: QUAD/X"):
        parts.append(mk.msg("MSG", us(0), txt.encode()))
    for name, v, d in PARAMS:
        parts.append(mk.msg("PARM", us(0), name.encode(), float(v), float(d)))
    mode_i = 0
    gwk0 = None
    for k in range(n):
        tk, T = t[k], us(t[k])
        while mode_i < len(MODES) and tk >= MODES[mode_i][0]:
            _, mname, num, why = MODES[mode_i]
            parts.append(mk.msg("MODE", T, num, num, why))
            mode_i += 1
        if abs(tk - T_ARM) < DT / 2:
            parts.append(mk.msg("EV", T, 10))                                 # ARMED
            parts.append(mk.msg("MSG", T, b"Arming motors"))
        if abs(tk - 60.0) < DT / 2:
            parts.append(mk.msg("MSG", T, b"Mission: 1 WP"))
        if abs(tk - 177.0) < DT / 2:
            parts.append(mk.msg("MSG", T, b"Mission: 7 RTL"))
        if abs(tk - VIB[0] - 1.0) < DT / 2:
            parts.append(mk.msg("MSG", T, b"Vibration compensation ON"))
        if abs(tk - VIB[1] - 3.0) < DT / 2:
            parts.append(mk.msg("MSG", T, b"Vibration compensation OFF"))
        if k in events:
            if events[k] == "LAND_COMPLETE":
                parts.append(mk.msg("EV", T, 18))
                parts.append(mk.msg("MSG", T, b"Land complete"))
            else:
                parts.append(mk.msg("MSG", T, events[k].encode()))
        if landed_at and abs(tk - landed_at - 2.5) < DT / 2:
            parts.append(mk.msg("EV", T, 11))                                 # DISARMED
            parts.append(mk.msg("MSG", T, b"Disarming motors"))
        # 25 Hz
        parts.append(mk.msg("ATT", T, des_roll[k], roll[k], des_pitch[k], pitch[k], des_yaw[k], yaw_act[k], 3))
        parts.append(mk.msg("RATE", T, r_des[k], r_act[k], p_des[k], p_act[k], y_des[k], y_act[k]))
        ax = -g * math.sin(math.radians(pitch[k])) + rng.normal(0, 0.2 + burst[k] * 3)
        ay = g * math.sin(math.radians(roll[k])) + rng.normal(0, 0.2 + burst[k] * 3)
        az = -g * thrust[k] / max(thr[k] / 0.38, 1e-3) * thr[k] / 0.38 if flying[k] else -g
        parts.append(mk.msg("IMU", T, 0, math.radians(r_act[k]), math.radians(p_act[k]), math.radians(y_act[k]),
                            ax, ay, az + rng.normal(0, 0.3 + burst[k] * 6)))
        if k % 2:
            continue
        # 12.5 Hz
        parts.append(mk.msg("RCOU", T, *(int(p[k]) for p in pwm)))
        stick = 1500 if mode_at(tk)[1] in ("AUTO", "RTL", "LAND") or not armed[k] else None
        thr_in = 1000 if not armed[k] else 1500 if stick else int(1300 + 500 * thr[k])
        parts.append(mk.msg("RCIN", T, int(1500 + 6 * des_roll[k]) if stick is None else 1500,
                            int(1500 - 6 * des_pitch[k]) if stick is None else 1500, thr_in, 1500))
        parts.append(mk.msg("CTUN", T, 0.0, thr[k], 0.38, alt_des[k], P[k, 2], baro_alt[k], V[k, 2], V[k, 2]))
        if k % 5:
            continue
        # 5 Hz
        parts.append(mk.msg("VIBE", T, 0, vibe[0][k], vibe[1][k], vibe[2][k], int(clip[k])))
        parts.append(mk.msg("BAT", T, 0, volt[k], volt[k] + cur[k] * 0.022, cur[k], mah[k] / 1000, wh[k]))
        parts.append(mk.msg("BARO", T, 0, baro_alt[k], 101325 * math.exp(-(HOME[2] + baro_alt[k]) / 8434),
                            31.0 + 0.4 * math.sin(tk / 60)))
        parts.append(mk.msg("XKF3", T, 0, *(float(x) for x in rng.normal(0, [0.05, 0.05, 0.08]) * (1 + 3 * burst[k]))))
        parts.append(mk.msg("XKF4", T, 0, sv[k], sv[k] * 0.7, 0.03 + 0.02 * burst[k], 0.05))
        fix = 3 if tk > 9 else 1
        sats = int(min(16, 5 + tk * 1.1)) if tk < 10 else 15 + (1 if math.sin(tk / 23) > 0.3 else 0)
        hdop = max(0.62, 3.5 - tk * 0.3)
        wk, ms = gps_time(tk)
        gwk0 = gwk0 or wk
        parts.append(mk.msg("GPS", T, 0, fix, ms, wk, sats, hdop,
                            int(round((lat[k] + rng.normal(0, 2e-6)) * 1e7)), int(round((lon[k] + rng.normal(0, 2e-6)) * 1e7)),
                            int(round((HOME[2] + P[k, 2] + rng.normal(0, 0.2)) * 100)), gs[k], crs[k], -V[k, 2], 1))
        if k % 25 == 0:
            parts.append(mk.msg("POWR", T, 5.12 + rng.normal(0, 0.01), 5.3 + rng.normal(0, 0.02)))
    data = b"".join(parts)
    with open(out, "wb") as f:
        f.write(data)
    print(f"{out}: {len(data) / 1e6:.2f} MB, {t[-1]:.0f} s, landed at {landed_at:.1f} s")


if __name__ == "__main__":
    main()
