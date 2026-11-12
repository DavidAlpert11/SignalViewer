"""The smart-sweep demo's "simulation" (W18): a real program with a real input and output.

    python sim.py params.json          (or, from the Portable: SignalViewer.exe study demo-sim params.json)

Input  - one JSON parameters file, written by the study's params_template for one run:
         {"run_id": "...", "table": "A", "Kp": 1.2, "Ki": 0.4, "Kd": 0.3, "wind": 5, ...,
          "out": "<where to write the result>", "sleep_ms": 30, "noise": 0.005, "seed": 1}
         (B adds "mass", C adds "filter_hz").
Output - one CSV file at "out": a header and one row - every input column, the outputs
         (overshoot, settling_time, motor_sat, energy, phase_margin) and run_id.

The model is the closed-form drone attitude loop of the app's examples (backend/svcore/drone_model.py,
formulas there), written here with the standard library only, so this file runs anywhere. To use your own
program, keep the same contract - read the parameters file, write one CSV row named by the run - and change
the study's `launcher.submit` to run it.
"""
import csv
import hashlib
import json
import math
import os
import random
import sys
import time

DRONES = {"A": (0.05, 1.2, 30.0), "B": (0.12, 3.5, 90.0), "C": (0.08, 2.5, 45.0)}   # J, m, T
OUTPUTS = ("overshoot", "settling_time", "motor_sat", "energy", "phase_margin")


def model(table, Kp, Ki, Kd, wind=0.0, mass=None, filter_hz=None):
    J0, m0, T = DRONES[table]
    m = m0 if mass is None else mass
    Kp = max(Kp, 1e-6)
    J = J0 * m / m0
    wn = math.sqrt(Kp / J)
    z = Kd / (2 * math.sqrt(Kp * J))
    zi = max(0.05, z - 0.35 * Ki / math.sqrt(Kp))
    os_ = 100 * math.exp(-math.pi * zi / math.sqrt(max(1 - zi * zi, 1e-12))) if zi < 1 else 0.0
    overshoot = os_ + 0.4 * wind / (1 + Ki)
    sat = (0.5 * Kp + 0.3 * Kd * wn) * m / T + 0.02 * wind
    ts = 4 / (zi * wn) if zi < 1 else 4 / (wn * (zi - math.sqrt(max(zi * zi - 1, 0))))
    ts = ts * (1 + 6 * max(0.0, sat - 0.6) ** 2) + 0.05 * wind / max(Ki, 0.05)
    energy = m * (5 + 0.8 * Kp + 0.3 * Kd * wn) * (1 + 0.05 * wind) + 2 * sat * sat
    g = math.sqrt(math.sqrt(1 + 4 * z ** 4) - 2 * z * z)
    wc = wn * g
    pm = math.degrees(math.atan2(2 * z, g))
    if filter_hz is not None:
        pm -= math.degrees(math.atan(wc / (2 * math.pi * filter_hz)))
        ts += 0.01 * filter_hz * Kd
        energy += 0.002 * m * filter_hz * Kd
    pm -= math.degrees(math.atan(Ki / max(Kp * wc / 2, 1e-9)))
    return {"overshoot": overshoot, "settling_time": ts, "motor_sat": sat, "energy": energy, "phase_margin": pm}


def run(params_path):
    with open(params_path, encoding="utf-8") as f:
        p = json.load(f)
    out = model(p["table"], float(p["Kp"]), float(p["Ki"]), float(p["Kd"]), float(p.get("wind", 0)),
                None if p.get("mass") is None else float(p["mass"]),
                None if p.get("filter_hz") is None else float(p["filter_hz"]))
    noise = float(p.get("noise", 0) or 0)
    if noise:                                  # seeded by the run: the same run gives the same "measurement"
        rnd = random.Random(int(hashlib.sha1(f"{p.get('seed', 1)}|{p['run_id']}".encode()).hexdigest()[:12], 16))
        out = {k: v * (1 + noise * rnd.gauss(0, 1)) for k, v in out.items()}
    if p.get("sleep_ms"):
        time.sleep(float(p["sleep_ms"]) / 1000)
    inputs = {k: v for k, v in p.items() if k not in ("out", "sim", "sleep_ms", "noise", "seed", "table", "round", "run_id")}
    row = {**inputs, **{k: round(v, 6) for k, v in out.items()}, "run_id": p["run_id"]}
    target = p["out"]
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row), lineterminator="\n")
        w.writeheader()
        w.writerow(row)
    os.replace(tmp, target)                    # the result appears whole, never half written
    return row


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python sim.py params.json")
    run(sys.argv[1])
