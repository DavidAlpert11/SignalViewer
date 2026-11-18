"""E4: the test-bench example (examples/bench/) - a pump on a bench, not a flight: one Parquet run and the
checks it must pass (examples/bench/checks.json, for the Checks view's limits and `signalviewer-cli check`).

    python tools/make_bench_example.py

Deterministic (fixed seed). What it holds, on purpose, for the tools to find:
- phases as a state (IDLE, RAMP, STEADY, STOP), 50 Hz, 10 minutes;
- the motor temperature creeps over its 85 °C limit late in STEADY (Checks: one limit fails);
- one pressure spike of 0.2 s (it must survive decimation on screen);
- 2 s with no samples in the middle of STEADY (data quality: a gap)."""
import os

import numpy as np
import pandas as pd

from . import REPO_EXAMPLES


def main(out=None) -> None:
    out = out or os.path.join(REPO_EXAMPLES, "bench")
    rng = np.random.default_rng(7)
    t = np.round(np.arange(0, 600, 0.02), 3)
    phase = np.where(t < 30, "IDLE", np.where(t < 90, "RAMP", np.where(t < 560, "STEADY", "STOP")))
    rpm_target = np.interp(t, [0, 30, 90, 560, 590, 600], [0, 0, 2900, 2900, 0, 0])
    rpm = rpm_target + rng.normal(0, 8, t.size) * (rpm_target > 0)
    flow = 0.042 * rpm + rng.normal(0, 0.6, t.size) * (rpm > 50)                        # l/min
    pressure = 1.0 + 1.6e-6 * rpm ** 2 + rng.normal(0, 0.03, t.size)                    # bar
    spike = (t >= 412.0) & (t < 412.2)
    pressure[spike] += 6.5                                                              # a short spike
    current = 0.6 + 0.0042 * rpm + rng.normal(0, 0.05, t.size)                          # A
    heat = np.cumsum(np.clip(rpm, 0, None)) * 0.02 / 2900                               # s at full speed
    temp = 24 + 62 * (1 - np.exp(-heat / 260)) + 0.02 * np.clip(t - 380, 0, None) ** 1.18 * (phase == "STEADY")
    temp += rng.normal(0, 0.08, t.size)
    vib = 0.02 + 0.00012 * rpm * (1 + 0.15 * np.sin(2 * np.pi * t / 37)) + np.abs(rng.normal(0, 0.01, t.size))
    keep = ~((t >= 300.0) & (t < 302.0))                                                # a 2 s gap
    df = pd.DataFrame({
        "Time": t, "Phase": phase, "RPM": rpm, "Flow [l/min]": flow, "Pressure [bar]": pressure,
        "Current [A]": current, "MotorTemp [°C]": temp, "Vibration [g]": vib,
    })[keep]
    df["Phase"] = df["Phase"].astype("category")
    os.makedirs(out, exist_ok=True)
    df.to_parquet(os.path.join(out, "pump_run_07.parquet"), index=False, compression="zstd")
    print(len(df), "rows ->", out)


if __name__ == "__main__":
    main()
