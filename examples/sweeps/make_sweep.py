"""Makes sweep_payload.csv: an invented run-envelope result table, one row per run.

The columns are laid out the way run envelopes usually write them: scenario columns and parameters
mixed at the start, the outputs at the end. 150 parameter sets x 18 scenario combinations
(terrain x wind x mission) = 2700 runs, a few of them missing and a few that crashed (empty
outputs) - so the "missing combination" and "failed run" paths have something to show.

    python make_sweep.py                       # the example (about 0.3 MB)
    python make_sweep.py --repeat 400 big.csv  # ~1M rows, to time the reading of a big file
"""
import argparse
import itertools

import numpy as np
import pandas as pd


def make(repeat: int = 1, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    terrain = {"flat": 0.0, "hills": 0.08, "urban": 0.14}
    mission = {"survey": 0.0, "delivery": 0.06}
    rows = []
    payloads = np.round(np.arange(0.5, 2.51, 0.5), 2)
    kps = [0.10, 0.14, 0.18, 0.22, 0.26]
    cruises = [12, 14, 16]
    ctrls = ["PID", "LQR"]
    for rep in range(repeat):
        for ter, pay, wind, kp, mis, cru, ctl in itertools.product(terrain, payloads, (0, 4, 8), kps, mission, cruises, ctrls):
            load = terrain[ter] + mission[mis] + 0.02 * wind
            rng_m = 2100 - 260 * pay - 14 * (cru - 14) ** 2 - 900 * load - 1400 * (kp - 0.17) ** 2 + (60 if ctl == "LQR" else 0)
            roll = 9 + 30 * abs(kp - 0.15) * (1 + wind / 8) + 6 * load * 10 + 2.2 * pay + (-1.5 if ctl == "LQR" else 0)
            batt = 38 - 7 * pay - 1.2 * (cru - 12) - 60 * load
            rows.append({
                "scenario_terrain": ter, "payload_kg": pay, "scenario_wind_mps": wind, "kp_roll": kp,
                "scenario_mission": mis, "cruise_mps": cru, "controller": ctl,
                "range_m": rng_m + rng.normal(0, 25), "max_roll_deg": roll + rng.normal(0, 0.6),
                "battery_end_pct": batt + rng.normal(0, 0.8),
                "flight_time_s": (rng_m / cru) + rng.normal(0, 3),
                "max_current_a": 18 + 6 * pay + 0.4 * wind + rng.normal(0, 0.5),
                "sim_version": "4.2.1",                                    # the same in every run
                "mission_ok": int(roll < 25 and batt > 20),
            })
    df = pd.DataFrame(rows)
    gone = rng.random(len(df)) < 0.006                                     # runs that never ran
    df = df[~gone].reset_index(drop=True)
    crashed = rng.random(len(df)) < 0.004                                  # runs that crashed: no outputs
    for c in ("range_m", "max_roll_deg", "battery_end_pct", "flight_time_s", "max_current_a"):
        df.loc[crashed, c] = np.nan
    return df.round({"range_m": 1, "max_roll_deg": 2, "battery_end_pct": 2, "flight_time_s": 1, "max_current_a": 2})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("out", nargs="?", default="sweep_payload.csv")
    a = ap.parse_args()
    make(a.repeat).to_csv(a.out, index=False)
