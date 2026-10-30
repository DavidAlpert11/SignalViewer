"""Makes sweep_payload.csv: an invented run-envelope result table, one row per run.

The columns are laid out the way run envelopes usually write them: scenario columns and parameters
mixed at the start, the outputs at the end. 150 parameter sets x 18 scenario combinations
(terrain x wind x mission) = 2700 runs, a few of them missing and a few that crashed (empty
outputs) - so the "missing combination" and "failed run" paths have something to show - and four runs
that quietly went wrong (range far below their neighbours') for the suspicious-runs check.

    python make_sweep.py                       # the example (about 0.3 MB)
    python make_sweep.py --refine              # the second sweep: finer where the first looked good
    python make_sweep.py --repeat 400 big.csv  # ~1M rows, to time the reading of a big file
"""
import argparse
import itertools

import numpy as np
import pandas as pd


def make(repeat: int = 1, seed: int = 7, refine: bool = False) -> pd.DataFrame:
    """refine: a second sweep, run after looking at the first - a finer grid where the good sets are
    (light payloads, kp_roll around 0.16, cruise 13-15), plus a few sets the first sweep already
    ran (run again, so merging has something to decide about)."""
    rng = np.random.default_rng(seed + (100 if refine else 0))
    terrain = {"flat": 0.0, "hills": 0.08, "urban": 0.14}
    mission = {"survey": 0.0, "delivery": 0.06}
    rows = []
    payloads = np.round(np.arange(0.5, 2.51, 0.5), 2)
    kps = [0.10, 0.14, 0.18, 0.22, 0.26]
    cruises = [12, 14, 16]
    if refine:
        payloads = np.array([0.5, 0.75, 1.0, 1.25])
        kps = [0.12, 0.14, 0.16, 0.18, 0.20]
        cruises = [13, 14, 15]
    ctrls = ["PID", "LQR"]
    for rep in range(repeat):
        for ter, pay, wind, kp, mis, cru, ctl in itertools.product(terrain, payloads, (0, 4, 8), kps, mission, cruises, ctrls):
            load = terrain[ter] + mission[mis] + 0.02 * wind
            rng_m = 2100 - 260 * pay - 14 * (cru - 14) ** 2 - 900 * load - 1400 * (kp - 0.17) ** 2 + (60 if ctl == "LQR" else 0)
            roll = 9 + 30 * abs(kp - 0.15) * (1 + wind / 8) + 30 * load + 2.2 * pay + (-1.5 if ctl == "LQR" else 0)
            batt = 40 - 6 * pay - 1.2 * (cru - 12) - 30 * load
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
    if refine:
        df["sim_version"] = "4.2.2"
        return df.round({"range_m": 1, "max_roll_deg": 2, "battery_end_pct": 2, "flight_time_s": 1, "max_current_a": 2})
    gone = rng.random(len(df)) < 0.006                                     # runs that never ran
    df = df[~gone].reset_index(drop=True)
    crashed = rng.random(len(df)) < 0.004                                  # runs that crashed: no outputs
    for c in ("range_m", "max_roll_deg", "battery_end_pct", "flight_time_s", "max_current_a"):
        df.loc[crashed, c] = np.nan
    odd = rng.choice(np.where(~crashed)[0], 4, replace=False)             # runs that broke quietly: odd values
    df.loc[odd, "range_m"] = df.loc[odd, "range_m"] * 0.45
    return df.round({"range_m": 1, "max_roll_deg": 2, "battery_end_pct": 2, "flight_time_s": 1, "max_current_a": 2})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--refine", action="store_true", help="the second, finer sweep (sweep_payload_refine.csv)")
    ap.add_argument("out", nargs="?", default=None)
    a = ap.parse_args()
    make(a.repeat, refine=a.refine).to_csv(a.out or ("sweep_payload_refine.csv" if a.refine else "sweep_payload.csv"), index=False)
