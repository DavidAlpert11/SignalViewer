"""Writes examples/investigate/: two quadcopter runs made to try the Investigate tools on.

    python tools/make_investigation_demo.py

The same mission (takeoff, AUTO with three wind gusts, loiter, land) flown twice, 50 Hz, 120 s:
  heavy_payload.csv   2.4 kg - at each gust motor 3 runs out of headroom (saturates near 2000) and
                      the roll leaves its set point for about a second;
  light_payload.csv   1.2 kg - the same gusts, enough headroom, the roll holds.
Built in this order on purpose, so the tools have a known answer: the gust (Wind) comes first,
the vibration (Vibe_Z) follows about 0.1 s later, motor 3 saturates about 0.1 s after that, and the
roll error comes about 0.15 s after the saturation. See examples/investigate/README.md.
"""
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "examples", "investigate")
RATE, DUR = 50.0, 120.0
GUSTS = (38.0, 63.0, 91.0)
MODES = [(0, "TAKEOFF"), (12, "AUTO"), (100, "LOITER"), (110, "LAND")]


def bump(t, at, rise=0.25, hold=0.8, fall=0.6):
    """0 -> 1 -> 0: a smooth step up at `at`, held, then down."""
    up = np.clip((t - at) / rise, 0, 1)
    down = np.clip((t - (at + rise + hold)) / fall, 0, 1)
    return (0.5 - 0.5 * np.cos(np.pi * up)) * (1 - (0.5 - 0.5 * np.cos(np.pi * down)))


def run(payload: float, seed: int):
    rng = np.random.default_rng(seed)
    t = np.arange(0, DUR, 1 / RATE)
    mode_i = np.zeros(len(t), int)
    for k, (start, _) in enumerate(MODES):
        mode_i[t >= start] = k
    alt = np.interp(t, [0, 12, 100, 110, 120], [0, 30, 30, 30, 0])
    wind = 2.0 + 0.3 * rng.normal(size=len(t)).cumsum() / 40
    vibe = 0.8 + 0.05 * rng.normal(size=len(t))
    sat = np.zeros(len(t))
    for g in GUSTS:
        wind += 9.0 * bump(t, g)
        vibe += 2.5 * bump(t, g + 0.1)
        sat += bump(t, g + 0.2, rise=0.15, hold=0.6, fall=0.4)
    hover = 1450 + 120 * payload
    m = [hover + 15 * rng.normal(size=len(t)) for _ in range(4)]
    # motor 3 works against the gust: with the heavy payload it reaches its limit
    need = hover + 260 * sat * (1.0 + 0.6 * (payload > 2))
    m[2] = np.minimum(need + 15 * rng.normal(size=len(t)), 2000)
    m[0] = m[0] - 120 * sat
    des_roll = 2.0 * np.sin(2 * np.pi * t / 30) * (mode_i == 1)
    lacking = np.clip(need - 2000, 0, None) / 60                       # what the motor could not give
    roll_err = np.zeros(len(t))
    shift = int(0.15 * RATE)
    roll_err[shift:] = lacking[:-shift] * 6.0                          # the roll answers 0.15 s later
    roll = des_roll + roll_err + 0.4 * rng.normal(size=len(t)) + (0.0 if payload > 2 else 0.8 * sat)
    batt = 16.8 - 0.012 * t * (1 + 0.3 * payload) - 0.002 * (sum(m) / 4 - 1450)
    cols = {
        "Time": t, "Mode": np.array([MODES[i][1] for i in mode_i]), "Alt": alt + 0.2 * rng.normal(size=len(t)),
        "DesRoll": des_roll, "Roll": roll, "Pitch": 1.5 * rng.normal(size=len(t)) / 3,
        "Motor1": m[0], "Motor2": m[1], "Motor3": m[2], "Motor4": m[3],
        "Vibe_Z": vibe, "Wind": wind, "Battery_V": batt, "Payload_kg": np.full(len(t), payload),
    }
    return cols


def write(path, cols):
    names = list(cols)
    n = len(cols["Time"])
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(",".join(names) + "\n")
        for i in range(n):
            f.write(",".join(c[i] if isinstance(c[i], str) else f"{c[i]:.4f}".rstrip("0").rstrip(".") for c in (cols[k] for k in names)) + "\n")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    write(os.path.join(OUT, "heavy_payload.csv"), run(2.4, 7))
    write(os.path.join(OUT, "light_payload.csv"), run(1.2, 8))
    print("written to", os.path.abspath(OUT))
