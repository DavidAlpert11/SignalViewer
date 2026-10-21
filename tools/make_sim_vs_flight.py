#!/usr/bin/env python3
"""
C13: the "simulation against flight" example - the same attitude test flown in a simulation
(MATLAB .mat, as a Simulink model logs it) and on the vehicle (ArduPilot DataFlash .bin).

    python tools/make_sim_vs_flight.py [out_dir]        # default: examples/sim_vs_flight/

The test: in ALT_HOLD the pilot flies roll doublets (10, 15, 20 deg) and then pitch doublets - the
usual way to check an attitude loop against its model. Both sides follow the SAME commands
(ATT.DesRoll / ATT.DesPitch); what they do with them differs on purpose, so the example has
something to find:

  * pitch: the vehicle behaves like the model (natural frequency 7 rad/s, damping 0.8);
  * roll: the vehicle is LESS damped than the model (0.5 instead of 0.8, 6.5 rad/s) - it
    overshoots each doublet by ~15 % where the model barely does;
  * the vehicle answers 25 ms later than the model (the model leaves out the ESC and motor lag);
  * a motor vibration at 82 Hz on the IMU, which the model does not have (see it in the spectrum);
  * the clocks differ: the simulation starts at 0 s, the flight log counts from boot and the test
    starts 104.37 s after boot - aligning them in time is the first step.

Files:
  sim_attitude_doublets.mat     tout + ATT (DesRoll, Roll, DesPitch, Pitch, DesYaw, Yaw) + RATE
                                (RDes, R, PDes, P), 100 Hz, 0 .. 90 s
  flight_attitude_doublets.bin  ATT / RATE at 50 Hz, IMU at 250 Hz, MODE, PARM, MSG; boot 95 .. 200 s
  tolerances.json               the limits for `signalviewer-cli compare` (roll fails, pitch passes)

Deterministic (fixed seed). The numbers the documentation shows come from this script.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_test_bin as mk  # noqa: E402  (FMT / message writer)

T_TEST = 90.0                     # s, length of the test
BOOT_AT_SIM0 = 104.37             # the flight's boot time at the simulation's t = 0
BOOT_START, BOOT_END = 95.0, 200.0
SIM_HZ, ATT_HZ, IMU_HZ = 100.0, 50.0, 250.0
VIB_HZ = 82.0

# (start s in test time, axis, amplitude deg, half-length s): a doublet is +A for half, -A for half
DOUBLETS = ((5.0, "roll", 10.0, 1.5), (17.0, "roll", 15.0, 1.5), (29.0, "roll", 20.0, 1.5),
            (41.0, "roll", 15.0, 0.8),
            (53.0, "pitch", 10.0, 1.5), (65.0, "pitch", 15.0, 1.5), (77.0, "pitch", 15.0, 0.8))
MODEL = {"roll": (7.0, 0.8), "pitch": (7.0, 0.8)}            # the model: (natural frequency rad/s, damping)
VEHICLE = {"roll": (6.5, 0.5), "pitch": (7.0, 0.8)}          # the vehicle: roll less damped
MODEL_DELAY, VEHICLE_DELAY = 0.020, 0.045                    # s
YAW0 = 92.0                                                  # deg, heading during the test


def commands(t: np.ndarray):
    """The pilot's commands (deg), smoothed like a stick and the RC input filter (first order, 120 ms)."""
    raw = {"roll": np.zeros_like(t), "pitch": np.zeros_like(t)}
    for t0, ax, a, h in DOUBLETS:
        raw[ax] += np.where((t >= t0) & (t < t0 + h), a, 0.0) + np.where((t >= t0 + h) & (t < t0 + 2 * h), -a, 0.0)
    dt = t[1] - t[0]
    k = 1 - np.exp(-dt / 0.12)
    out = {}
    for ax, x in raw.items():
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc += k * (v - acc)
            y[i] = acc
        out[ax] = y
    return out


def second_order(t: np.ndarray, u: np.ndarray, wn: float, zeta: float, delay: float) -> np.ndarray:
    """Closed-loop attitude: y'' = wn^2 (u(t - delay) - y) - 2 zeta wn y' (semi-implicit Euler, fine step)."""
    sub = 10
    dt = (t[1] - t[0]) / sub
    tf = np.arange(t[0], t[-1] + dt / 2, dt)
    uf = np.interp(tf - delay, t, u, left=0.0)
    y = v = 0.0
    out = np.empty_like(tf)
    for i, ui in enumerate(uf):
        v += dt * (wn * wn * (ui - y) - 2 * zeta * wn * v)
        y += dt * v
        out[i] = y
    return np.interp(t, tf, out)


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
        f(133, "MODE", "QMBB", ["TimeUS", "Mode", "ModeNum", "Rsn"]),
        f(134, "ATT", "QffffffB", ["TimeUS", "DesRoll", "Roll", "DesPitch", "Pitch", "DesYaw", "Yaw", "AEKF"]),
        f(135, "RATE", "Qffffff", ["TimeUS", "RDes", "R", "PDes", "P", "YDes", "Y"]),
        f(136, "IMU", "QBffffff", ["TimeUS", "I", "GyrX", "GyrY", "GyrZ", "AccX", "AccY", "AccZ"]),
    ]


def metadata():
    out = []
    for i, label in (("s", "s"), ("d", "deg"), ("k", "deg/s"), ("E", "rad/s"), ("o", "m/s/s"), ("#", "instance"), ("-", "")):
        out.append(mk.msg("UNIT", 0, ord(i), label.encode()))
    for i, v in (("-", 0), ("F", 1e-6)):
        out.append(mk.msg("MULT", 0, ord(i), v))
    for name, (u, m) in {"ATT": ("sdddddd-", "F-------"), "RATE": ("skkkkkk", "F------"),
                         "IMU": ("s#EEEooo", "F-------"), "MODE": ("s---", "F---")}.items():
        out.append(mk.msg("FMTU", 0, mk.FMTS[name][0], u.encode(), m.encode()))
    return out


def write_sim(path: str):
    from scipy.io import savemat
    t = np.round(np.arange(0, T_TEST + 1e-9, 1 / SIM_HZ), 6)
    c = commands(t)
    roll = second_order(t, c["roll"], *MODEL["roll"], MODEL_DELAY)
    pitch = second_order(t, c["pitch"], *MODEL["pitch"], MODEL_DELAY)
    g = lambda x: np.gradient(x, t)  # noqa: E731
    savemat(path, {
        "tout": t,
        "ATT": {"DesRoll": c["roll"], "Roll": roll, "DesPitch": c["pitch"], "Pitch": pitch,
                "DesYaw": np.full_like(t, YAW0), "Yaw": np.full_like(t, YAW0)},
        "RATE": {"RDes": g(c["roll"]), "R": g(roll), "PDes": g(c["pitch"]), "P": g(pitch)},
    }, do_compression=True, oned_as="column")


def write_flight(path: str):
    rng = np.random.default_rng(13)
    out = formats() + metadata()
    us = lambda tb: int(round(tb * 1e6))  # noqa: E731
    out.append(mk.msg("MSG", us(BOOT_START), b"ArduCopter V4.5.7 (sim vs flight example)"))
    for name, val in (("ATC_RAT_RLL_P", 0.135), ("ATC_RAT_RLL_D", 0.0024), ("ATC_RAT_PIT_P", 0.135),
                      ("ATC_RAT_PIT_D", 0.0036), ("INS_HNTCH_ENABLE", 0.0)):
        out.append(mk.msg("PARM", us(BOOT_START), name.encode(), val, val))
    modes = ((BOOT_START + 0.5, "STABILIZE", 0, 1), (BOOT_AT_SIM0 - 3.0, "ALT_HOLD", 2, 1),
             (BOOT_AT_SIM0 + T_TEST + 2.0, "LOITER", 5, 1))
    events = [(tb, mk.msg("MODE", us(tb), num, num, rsn)) for tb, _n, num, rsn in modes]
    events.append((BOOT_AT_SIM0 + 0.2, mk.msg("MSG", us(BOOT_AT_SIM0 + 0.2), b"Doublets: roll, then pitch")))
    # attitude at 50 Hz
    tb = np.arange(BOOT_START, BOOT_END, 1 / ATT_HZ)
    ts = tb - BOOT_AT_SIM0                                       # test time
    fine = np.round(np.arange(ts[0], ts[-1] + 1e-9, 1 / SIM_HZ), 6)    # on the simulation's 10 ms grid
    c = commands(fine)
    roll = second_order(fine, c["roll"], *VEHICLE["roll"], VEHICLE_DELAY)
    pitch = second_order(fine, c["pitch"], *VEHICLE["pitch"], VEHICLE_DELAY)
    at = lambda x: np.interp(ts, fine, x)  # noqa: E731
    des_r, des_p, r, p = at(c["roll"]), at(c["pitch"]), at(roll), at(pitch)
    r = r + rng.normal(0, 0.15, len(ts))
    p = p + rng.normal(0, 0.15, len(ts))
    yaw = YAW0 + 0.6 * np.sin(2 * np.pi * ts / 37) + rng.normal(0, 0.1, len(ts))
    rr, pr = np.gradient(r, ts), np.gradient(p, ts)
    rdes, pdes = np.gradient(des_r, ts), np.gradient(des_p, ts)
    for i in range(len(tb)):
        events.append((tb[i], mk.msg("ATT", us(tb[i]), des_r[i], r[i], des_p[i], p[i], YAW0, yaw[i], 1)))
        events.append((tb[i], mk.msg("RATE", us(tb[i]), rdes[i], rr[i], pdes[i], pr[i], 0.0, 0.0)))
    # IMU at 250 Hz: the body rates plus the 82 Hz motor vibration
    ti = np.arange(BOOT_START, BOOT_END, 1 / IMU_HZ)
    tti = ti - BOOT_AT_SIM0
    gx = np.radians(np.interp(tti, fine, np.gradient(roll, fine)))
    gy = np.radians(np.interp(tti, fine, np.gradient(pitch, fine)))
    vib = np.sin(2 * np.pi * VIB_HZ * ti)
    gx = gx + 0.04 * vib + rng.normal(0, 0.01, len(ti))
    gy = gy + 0.03 * np.sin(2 * np.pi * VIB_HZ * ti + 0.7) + rng.normal(0, 0.01, len(ti))
    gz = rng.normal(0, 0.008, len(ti))
    ax = 0.6 * vib + rng.normal(0, 0.15, len(ti))
    ay = 0.5 * np.sin(2 * np.pi * VIB_HZ * ti + 1.1) + rng.normal(0, 0.15, len(ti))
    az = -9.81 + 2.4 * np.sin(2 * np.pi * VIB_HZ * ti + 0.3) + rng.normal(0, 0.25, len(ti))
    for i in range(len(ti)):
        events.append((ti[i], mk.msg("IMU", us(ti[i]), 0, gx[i], gy[i], gz[i], ax[i], ay[i], az[i])))
    events.sort(key=lambda e: e[0])
    with open(path, "wb") as f:
        f.write(b"".join(out) + b"".join(m for _, m in events))


def write_tolerances(path: str):
    tol = {
        "_comment": "Simulation (golden) against the flight. Angles in degrees, rates in deg/s. "
                    "Run: signalviewer-cli compare sim_attitude_doublets.mat flight_attitude_doublets.bin "
                    "--align auto --align-on ATT.DesRoll --tolerances tolerances.json",
        "default": {"abs": 3.0},
        "signals": {
            "ATT.DesYaw": {"skip": True},
            "ATT.Yaw": {"abs": 3.0},
            "RATE.RDes": {"skip": True},
            "RATE.PDes": {"skip": True},
            "RATE.R": {"abs": 30.0},
            "RATE.P": {"abs": 30.0},
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tol, f, indent=2)
        f.write("\n")


def main(out_dir=None) -> str:
    out_dir = out_dir or (sys.argv[1] if len(sys.argv) > 1 else
                          os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples", "sim_vs_flight"))
    os.makedirs(out_dir, exist_ok=True)
    write_sim(os.path.join(out_dir, "sim_attitude_doublets.mat"))
    write_flight(os.path.join(out_dir, "flight_attitude_doublets.bin"))
    write_tolerances(os.path.join(out_dir, "tolerances.json"))
    return out_dir


if __name__ == "__main__":
    print(main())
