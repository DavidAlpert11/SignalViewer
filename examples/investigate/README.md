# Investigate demo

Two runs of the same quadcopter mission through three wind gusts: `heavy_payload.csv` (2.4 kg -
motor 3 saturates, the roll leaves its set point) and `light_payload.csv` (1.2 kg - it holds).
Made by `tools/make_investigation_demo.py` with a known chain: wind → vibration (+0.1 s) → motor 3
saturation (+0.1 s, heavy only) → roll error (+0.15 s).

The walkthrough: docs/investigate-tutorial.md (Hebrew: docs/investigate-tutorial.he.md).
