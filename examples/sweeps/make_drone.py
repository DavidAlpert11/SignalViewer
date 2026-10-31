"""Makes the Sweeps example: tuning a drone's roll controller.

What we choose - the PARAMETERS:      kp_roll, ki_roll, filter_hz
What we don't choose - the SCENARIOS: scenario_wind_mps, scenario_payload_kg, scenario_gusts
   (a controller is good only if it is good in every scenario)
What we measure - the OUTPUTS:        roll_error_deg, settle_time_s, overshoot_pct, energy_wh, crashed

45 parameter sets x 18 scenarios = 810 runs, one row each, columns mixed the way run envelopes write
them (scenario and parameter columns first, outputs last), plus a run id and a constant column.
A goal to try: roll_error_deg <= 5 and overshoot_pct <= 15 and crashed == 0 in every scenario,
then the least energy_wh. Two runs went wrong quietly (energy far off) for Data health.

    python make_drone.py            # drone_tuning.csv
    python make_drone.py --refine   # drone_tuning_refine.csv: a second sweep, finer where the first looked good
"""
import argparse
import itertools

import numpy as np
import pandas as pd

GUST = {"none": 0.0, "mild": 0.45, "strong": 1.0}


def make(refine: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(11 if refine else 7)
    kps = [0.18, 0.20, 0.22, 0.24, 0.26] if refine else [0.10, 0.15, 0.20, 0.25, 0.30]
    kis = [0.015, 0.02, 0.03] if refine else [0.01, 0.02, 0.04]
    filt = [15, 20, 30] if refine else [10, 20, 40]
    rows = []
    run = 5000 if refine else 1
    for wind, kp, payload, ki, gust, fhz in itertools.product((0, 5, 10), kps, (0.5, 1.5), kis, GUST, filt):
        load = 0.06 * wind + 0.35 * payload + 1.4 * GUST[gust]                     # how hard the scenario is
        err = 1.2 + load * (0.9 + 9 * max(0.0, 0.22 - kp)) + 25 * abs(ki - 0.02) + 0.02 * abs(fhz - 20)
        over = 4 + 90 * max(0.0, kp - 0.21) + 180 * max(0.0, ki - 0.02) + 2.2 * load + 0.08 * max(0, 20 - fhz) * 4
        settle = 0.6 + 0.09 / kp + 6 * ki + 0.25 * load + (8 / fhz)
        energy = 18 + 9 * payload + 0.6 * wind + 30 * kp + 4 * GUST[gust] + 0.05 * fhz
        crashed = int(err + rng.normal(0, 0.4) > 6.8)
        rows.append({
            "scenario_wind_mps": wind, "kp_roll": kp, "scenario_payload_kg": payload, "ki_roll": ki, "scenario_gusts": gust, "filter_hz": fhz,
            "run_id": run, "sim_version": "5.1.0" if refine else "5.0.3",
            "roll_error_deg": round(err + rng.normal(0, 0.15), 3), "settle_time_s": round(settle + rng.normal(0, 0.03), 3),
            "overshoot_pct": round(over + rng.normal(0, 0.5), 2), "energy_wh": round(energy + rng.normal(0, 0.3), 2),
            "crashed": crashed,
        })
        run += 1
    df = pd.DataFrame(rows)
    if not refine:
        odd = rng.choice(len(df), 2, replace=False)                                # two runs that broke quietly
        df.loc[odd, "energy_wh"] = df.loc[odd, "energy_wh"] * 3.1
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refine", action="store_true")
    a = ap.parse_args()
    make(a.refine).to_csv("drone_tuning_refine.csv" if a.refine else "drone_tuning.csv", index=False)
