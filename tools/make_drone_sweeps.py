"""Make the W14 example: three drones that must fly with the same attitude gains (examples/drones/).

    python tools/make_drone_sweeps.py            # writes examples/drones/drone_{a,b,c}.csv + drones.svstudy.json

The runs come from the closed-form toy model in backend/svcore/drone_model.py (formulas in its docstring):
~6 x 5 x 5 gain values (Kp, Ki, Kd) per drone, each run over that drone's scenarios.

* Drone A - light quad: wind 0 / 3 / 6 / 10 m/s; overshoot < 8; minimise the settling time.
* Drone B - heavy hexa: mass 2 / 3.5 / 5 kg x wind 0 / 5 m/s; extra output motor_sat;
  overshoot < 12 and motor_sat < 0.9; minimise the energy.
* Drone C - VTOL: its columns are P_gain, I_gain, D_gain (the name mapping), a local choice filter_hz
  (15 / 30 / 60 Hz) over wind 0 / 4 / 8 m/s; phase_margin > 45; minimise the settling time; a few runs
  deliberately missing (seeded), so "not run" shows.
Deterministic: running it again gives the same files.
"""
import csv
import itertools
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
from svcore.drone_model import simulate  # noqa: E402

OUT = os.path.join(ROOT, "examples", "drones")
KP = [0.5, 1.4, 2.3, 3.2, 4.1, 5.0]
KI = [0.0, 0.5, 1.0, 1.5, 2.0]
KD = [0.05, 0.3, 0.55, 0.8, 1.05]


def r(x):
    return round(float(x), 4)


def write(name, cols, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        w.writerows(rows)
    return len(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    gains = list(itertools.product(KP, KI, KD))
    a = []
    for (kp, ki, kd), wind in itertools.product(gains, [0, 3, 6, 10]):
        o = simulate("A", kp, ki, kd, wind=wind)
        a.append([kp, ki, kd, wind, r(o["overshoot"]), r(o["settling_time"])])
    b = []
    for (kp, ki, kd), m, wind in itertools.product(gains, [2.0, 3.5, 5.0], [0, 5]):
        o = simulate("B", kp, ki, kd, wind=wind, mass=m)
        b.append([kp, ki, kd, m, wind, r(o["overshoot"]), r(o["motor_sat"]), r(o["energy"]), r(o["settling_time"])])
    rnd = random.Random(13)
    c = []
    for (kp, ki, kd), fh, wind in itertools.product(gains, [15, 30, 60], [0, 4, 8]):
        if rnd.random() < 0.02:                      # a few runs that never ran
            continue
        o = simulate("C", kp, ki, kd, wind=wind, filter_hz=fh)
        c.append([kp, ki, kd, fh, wind, r(o["phase_margin"]), r(o["overshoot"]), r(o["settling_time"])])
    na = write("drone_a.csv", ["Kp", "Ki", "Kd", "wind", "overshoot", "settling_time"], a)
    nb = write("drone_b.csv", ["Kp", "Ki", "Kd", "mass", "wind", "overshoot", "motor_sat", "energy", "settling_time"], b)
    nc = write("drone_c.csv", ["P_gain", "I_gain", "D_gain", "filter_hz", "wind", "phase_margin", "overshoot", "settling_time"], c)
    study = {
        "version": 1, "name": "Three drones, one set of gains",
        "tables": [
            {"id": "A", "name": "Drone A - light quad", "paths": ["drone_a.csv"],
             "roles": {"wind": "scenario", "overshoot": "output", "settling_time": "output"},
             "constraints": ["overshoot < 8"], "objective": {"expr": "settling_time", "sense": "min"}, "aggregate": "worst"},
            {"id": "B", "name": "Drone B - heavy hexa", "paths": ["drone_b.csv"],
             "roles": {"mass": "scenario", "wind": "scenario", "overshoot": "output", "motor_sat": "output",
                       "energy": "output", "settling_time": "output"},
             "constraints": ["overshoot < 12 and motor_sat < 0.9"], "objective": {"expr": "energy", "sense": "min"}, "aggregate": "worst"},
            {"id": "C", "name": "Drone C - VTOL", "paths": ["drone_c.csv"], "rename": {"P_gain": "Kp", "I_gain": "Ki", "D_gain": "Kd"},
             "roles": {"filter_hz": "local", "wind": "scenario", "phase_margin": "output", "overshoot": "output", "settling_time": "output"},
             "constraints": ["phase_margin > 45"], "objective": {"expr": "settling_time", "sense": "min"}, "aggregate": "worst"},
        ],
        "shared": [{"name": "Kp"}, {"name": "Ki"}, {"name": "Kd"}],
        "combine": {"mode": "auto"},
        "search": {"params": {"Kp": {"min": 0.5, "max": 5.0, "step": 0.05}, "Ki": {"min": 0.0, "max": 2.0, "step": 0.025},
                              "Kd": {"min": 0.05, "max": 1.05, "step": 0.0125}}, "constraints": []},
        "next": {"batch": 20},
    }
    with open(os.path.join(OUT, "drones.svstudy.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(study, f, indent=2)
    print(f"examples/drones: A {na} runs, B {nb}, C {nc}")


if __name__ == "__main__":
    main()
