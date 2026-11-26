"""CC16 (owner, 2026-11-26: not an ArduPilot app - simulations and tests of any kind): the simulation examples, made
by code (deterministic, small). Each holds something on purpose for the tools to find:

  simulation/servo_step.mat + servo_step.checks.json
      a position servo as Simulink logs it with To Workspace (*Structure with time*): the command and the position
      at 1 kHz, the motor current at 200 Hz (multi-rate, each with its own time), `tout`. Its requirements (found
      beside it by Checks and `signalviewer-cli check`): it settles, rises and holds its target, the drive's current
      stays within its 60 A - and it overshoots 11 % against an 8 % limit (one requirement fails, on purpose).
  simulation/process_plant.h5 + process_plant.checks.json
      a heated tank as an HDF5 simulation output: the plant (temperature, heater power, inflow) at 10 Hz in one
      group, the controller (setpoint, output) at 1 Hz in another; a set-point change at 600 s, an inflow
      disturbance at 1500 s the loop takes 4 minutes to reject (the tracking requirement fails there).
  simulation/montecarlo/mc_m{mass}_f{friction}_s{seed}.csv (+ measures.json, checks.json)
      24 runs of the servo with its mass, friction and noise varied: a folder of runs -> one row each in Sweeps
      (overshoot, settling time, peak current) - the heavy, low-friction runs overshoot.
  simulation/cruise_sim.csv, simulation/cruise_test.csv
      a car's cruise control: the model against the test drive (same command, the test with a road grade and
      sensor noise) - Compare's tolerances, Align time.

    python tools/make_simulation_examples.py
"""
import json
import os

import numpy as np

from . import REPO_EXAMPLES


def _servo(t: np.ndarray, cmd: np.ndarray, mass: float = 1.0, friction: float = 1.0, kp: float = 90.0, kd: float = 7.2,
           noise: float = 0.0, seed: int = 0):
    """A PD-controlled mass (Euler at the grid's step): position, velocity, motor current (the force / Kt, limited)."""
    rng = np.random.default_rng(seed)
    dt = float(t[1] - t[0])
    x = v = 0.0
    pos, cur = np.empty_like(t), np.empty_like(t)
    for i, c in enumerate(cmd):
        u = kp * (c - x) - kd * v
        u = float(np.clip(u, -60.0, 60.0))                       # the drive's current limit (x Kt = 1)
        a = (u - 2.0 * friction * v) / mass
        v += a * dt
        x += v * dt
        pos[i] = x
        cur[i] = u
    if noise:
        pos = pos + rng.normal(0, noise, len(t))
        cur = cur + rng.normal(0, 10 * noise, len(t))
    return pos, cur


def servo_step(out: str) -> None:
    import scipy.io as sio
    t = np.round(np.arange(0, 6.0, 0.001), 6)
    cmd = np.where(t >= 1.0, 10.0, 0.0) + np.where(t >= 4.0, -5.0, 0.0)
    pos, cur = _servo(t, cmd)
    tc = t[::5]                                                    # the current logged at 200 Hz
    sio.savemat(os.path.join(out, "servo_step.mat"), {
        "cmd": {"time": t[:, None], "signals": {"values": cmd[:, None], "label": "pos_cmd", "blockName": "servo/Command"}},
        "plant": {"time": t[:, None], "signals": {"values": pos[:, None], "label": "pos", "blockName": "servo/Plant"}},
        "drive": {"time": tc[:, None], "signals": {"values": cur[::5][:, None], "label": "current", "blockName": "servo/Drive"}},
        "tout": t[:, None], "Kp": 90.0, "Kd": 7.2, "mass_kg": 1.0,
    }, do_compression=True)
    checks = {"checks": [
        {"name": "Overshoot at most 8 %", "kind": "overshoot", "signal": "plant.pos", "ref": "cmd.pos_cmd", "max_pct": 8, "t0": 1.0, "t1": 3.99},
        {"name": "Settles within 2 % in 1.5 s", "kind": "settle", "signal": "plant.pos", "ref": "cmd.pos_cmd", "band_pct": 2, "by": 1.5, "t0": 1.0, "t1": 3.99},
        {"name": "Rises in 0.6 s", "kind": "rise", "signal": "plant.pos", "ref": "cmd.pos_cmd", "within": 0.6, "t0": 1.0, "t1": 3.99},
        {"name": "Steady-state error at most 0.05", "kind": "sserror", "signal": "plant.pos", "ref": "cmd.pos_cmd", "max": 0.05, "last": 0.5, "t0": 1.0, "t1": 3.99},
        {"name": "Current within the drive's 60 A", "signal": "drive.current", "lo": -60, "hi": 60},
        {"name": "Command before motion", "kind": "order", "first": {"signal": "cmd.pos_cmd", "above": 1},
         "then": {"signal": "plant.pos", "above": 0.5}},
    ]}
    with open(os.path.join(out, "servo_step.checks.json"), "w", encoding="utf-8") as f:
        json.dump(checks, f, indent=1)
        f.write("\n")


def process_plant(out: str) -> None:
    import h5py
    rng = np.random.default_rng(11)
    dt = 0.1
    t = np.round(np.arange(0, 2400, dt), 3)
    sp = np.where(t >= 600, 65.0, 55.0)
    inflow = np.where((t >= 1500) & (t < 1800), 1.8, 1.0)          # l/s - a disturbance for 5 minutes
    T = 55.0
    integ = 1.6
    temp, power = np.empty_like(t), np.empty_like(t)
    tc, spc, outc = [], [], []
    u = 0.0
    for i, ti in enumerate(t):
        if i % 10 == 0:                                            # the controller runs at 1 Hz (a slow PI)
            e = sp[i] - T
            integ += 0.0008 * e * 1.0
            integ = float(np.clip(integ, 0, 4))
            u = float(np.clip(0.35 * e + integ, 0, 4))             # kW
            tc.append(ti); spc.append(sp[i]); outc.append(u)
        loss = 0.012 * (T - 15) + 0.045 * inflow[i] * (T - 15)
        T += dt * (u * 0.5 - loss * 0.5) / 4.2 * 4.0
        temp[i] = T + rng.normal(0, 0.05)
        power[i] = u
    with h5py.File(os.path.join(out, "process_plant.h5"), "w") as f:
        g = f.create_group("plant")
        g["time"] = t
        g["temperature_C"] = temp
        g["heater_kW"] = power
        g["inflow_lps"] = inflow
        c = f.create_group("controller")
        c["time"] = np.asarray(tc)
        c["setpoint_C"] = np.asarray(spc)
        c["output_kW"] = np.asarray(outc)
        f.attrs["model"] = "heated tank, PI temperature control"
    checks = {"checks": [
        {"name": "Temperature within 1 °C of the set point", "kind": "track", "signal": "plant/temperature_C",
         "ref": "controller/setpoint_C", "abs": 1.0, "t0": 1200},
        {"name": "Reaches the new set point in 6 minutes", "kind": "settle", "signal": "plant/temperature_C",
         "target": 65, "band": 1.0, "by": 360, "t0": 600, "t1": 1500},
        {"name": "Heater within 4 kW", "signal": "plant/heater_kW", "lo": 0, "hi": 4},
    ]}
    with open(os.path.join(out, "process_plant.checks.json"), "w", encoding="utf-8") as f:
        json.dump(checks, f, indent=1)
        f.write("\n")


def montecarlo(out: str) -> None:
    os.makedirs(out, exist_ok=True)
    t = np.round(np.arange(0, 3.0, 0.002), 6)
    cmd = np.where(t >= 0.5, 10.0, 0.0)
    seed = 0
    for mass in (0.8, 1.0, 1.3):
        for friction in (0.6, 1.0):
            for s in range(1, 5):
                seed += 1
                pos, cur = _servo(t, cmd, mass=mass, friction=friction, noise=0.004, seed=seed)
                path = os.path.join(out, f"mc_m{mass:g}_f{friction:g}_s{s}.csv")
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write("Time,pos_cmd,pos,current\n")
                    for row in zip(t, cmd, pos, cur):
                        f.write(f"{row[0]:.3f},{row[1]:.1f},{row[2]:.5f},{row[3]:.4f}\n")
    measures = {"measures": [
        {"name": "overshoot_pct", "signal": "pos", "op": "overshoot", "where": "pos_cmd > 5"},
        {"name": "settle_s", "signal": "pos", "op": "settle", "where": "pos_cmd > 5"},
        {"name": "peak_current", "signal": "current", "op": "max"},
    ], "pattern": "mc_m{mass}_f{friction}_s{seed}"}
    with open(os.path.join(out, "measures.json"), "w", encoding="utf-8") as f:
        json.dump(measures, f, indent=1)
        f.write("\n")
    checks = {"checks": [
        {"name": "Overshoot at most 20 %", "kind": "overshoot", "signal": "pos", "ref": "pos_cmd", "max_pct": 20, "t0": 0.5},
        {"name": "Settles within 2 % in 1.5 s", "kind": "settle", "signal": "pos", "ref": "pos_cmd", "band_pct": 2, "by": 1.5, "t0": 0.5},
    ]}
    with open(os.path.join(out, "checks.json"), "w", encoding="utf-8") as f:
        json.dump(checks, f, indent=1)
        f.write("\n")


def cruise(out: str) -> None:
    rng = np.random.default_rng(5)
    t = np.round(np.arange(0, 120, 0.05), 3)
    cmd = np.interp(t, [0, 10, 10.01, 60, 60.01, 120], [20, 20, 27, 27, 22, 22])        # m/s
    grade = np.where((t > 35) & (t < 50), 0.04, 0.0)                                     # a hill, in the test only

    def drive(with_grade: bool):
        v, integ = 20.0, 0.38
        vs, th = np.empty_like(t), np.empty_like(t)
        for i in range(len(t)):
            e = cmd[i] - v
            integ = float(np.clip(integ + 0.004 * e * 0.05, 0, 1))
            u = float(np.clip(0.12 * e + integ, 0, 1))
            a = 4.0 * u - 0.0016 * v * v - 0.15 - (9.81 * grade[i] if with_grade else 0.0)
            v += a * 0.05
            vs[i], th[i] = v, u
        return vs, th
    for name, g, noise in (("cruise_sim.csv", False, 0.0), ("cruise_test.csv", True, 0.08)):
        v, th = drive(g)
        v = v + (rng.normal(0, noise, len(t)) if noise else 0)
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as f:
            f.write("Time,speed_cmd [m/s],speed [m/s],throttle\n")
            for row in zip(t, cmd, v, th):
                f.write(f"{row[0]:.2f},{row[1]:.3f},{row[2]:.4f},{row[3]:.4f}\n")


def main(out=None) -> None:
    out = out or os.path.join(REPO_EXAMPLES, "simulation")
    os.makedirs(out, exist_ok=True)
    servo_step(out)
    process_plant(out)
    montecarlo(os.path.join(out, "montecarlo"))
    cruise(out)


if __name__ == "__main__":
    main()
