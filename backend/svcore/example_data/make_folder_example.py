#!/usr/bin/env python3
"""
The folder-of-recordings example (FL1): ten flights of two quad-copters over six weeks, as real
ArduPilot DataFlash logs, each with a story the folder's summary in Sweeps shows (measures.json beside them).

    python tools/make_folder_example.py [folder]     # default: examples/folder_of_flights

  X8-A  a motor bearing wearing out: its vibration grows flight after flight (15 -> 37 m/s/s) until
        the last flight crosses the limit with clipping - the vibration_max column in Sweeps shows the
        trend; tick that row and Open in Recordings to look at the flight.
  X8-B  healthy, but one flight with a stretch of poor GPS (5 satellites, HDOP 3.2) and one on a
        worn battery that sagged under the low-voltage limit.

The flights are made by tools/make_example_bin.py (the same flight, another date and noise) with
fewer 25 Hz samples, so the folder stays about 3 MB. Deterministic (fixed seeds).
"""
import os
import sys

from . import REPO_EXAMPLES
from . import make_example_bin as ex

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


def main(folder=None):
    folder = folder or (sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "folder_of_flights"))
    os.makedirs(folder, exist_ok=True)
    for name, (y, m, d), seed, vib, loose, gps, mah in FLIGHTS:
        ex.main(os.path.join(folder, name), start=(y, m, d, 7, 10, 0), seed=seed, vib_scale=vib,
                burst_on=loose, gps_glitch=gps, capacity=mah, thin=5)


if __name__ == "__main__":
    main()
