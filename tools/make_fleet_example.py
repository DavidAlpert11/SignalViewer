#!/usr/bin/env python3
"""
The Fleet example (owner, 2026-11-03: "it is not clear what the fleet is for"): ten flights of two
quad-copters over six weeks, as real ArduPilot DataFlash logs, each with a story the Fleet finds.

    python tools/make_fleet_example.py [folder]     # default: examples/fleet

  X8-A  a motor bearing wearing out: its vibration grows flight after flight (15 -> 37 m/s/s) until
        the last flight crosses the limit with clipping - Fleet > Number "Vibration · max" shows
        the trend, a search for the warning finds the flight, "Open here" opens it at the moment.
  X8-B  healthy, but one flight with a stretch of poor GPS (5 satellites, HDOP 3.2) and one on a
        worn battery that sagged under the low-voltage limit.

The flights are made by tools/make_example_bin.py (the same flight, another date and noise) with
fewer 25 Hz samples, so the folder stays about 3 MB. Deterministic (fixed seeds).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_example_bin as ex  # noqa: E402

# name, (y, m, d), seed, vibration scale, loose propeller, poor GPS (t0, t1), battery mAh
FLIGHTS = [
    ("X8-A_2026-09-02.bin", (2026, 9, 2), 101, 1.00, False, None, 5200),
    ("X8-A_2026-09-09.bin", (2026, 9, 9), 102, 1.12, False, None, 5200),
    ("X8-A_2026-09-16.bin", (2026, 9, 16), 103, 1.28, False, None, 5200),
    ("X8-A_2026-09-23.bin", (2026, 9, 23), 104, 1.50, False, None, 5200),
    ("X8-A_2026-09-30.bin", (2026, 9, 30), 105, 1.78, False, None, 5200),
    ("X8-A_2026-10-07.bin", (2026, 10, 7), 106, 2.15, True, None, 5200),
    ("X8-B_2026-09-05.bin", (2026, 9, 5), 201, 0.95, False, None, 5200),
    ("X8-B_2026-09-19.bin", (2026, 9, 19), 202, 0.98, False, (118.0, 152.0), 5200),
    ("X8-B_2026-10-03.bin", (2026, 10, 3), 203, 1.00, False, None, 5200),
    ("X8-B_2026-10-17.bin", (2026, 10, 17), 204, 0.97, False, None, 880),
]


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples", "fleet")
    os.makedirs(folder, exist_ok=True)
    for name, (y, m, d), seed, vib, loose, gps, mah in FLIGHTS:
        ex.main(os.path.join(folder, name), start=(y, m, d, 7, 10, 0), seed=seed, vib_scale=vib,
                burst_on=loose, gps_glitch=gps, capacity=mah, thin=5)


if __name__ == "__main__":
    main()
