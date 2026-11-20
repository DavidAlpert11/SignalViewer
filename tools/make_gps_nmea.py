#!/usr/bin/env python3
"""Runs backend/svcore/example_data/make_gps_nmea.py - a GPS receiver's raw NMEA, and the same byte by byte
(examples/gps_nmea). Optional argument: the folder to write them in."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from svcore.example_data import REPO_EXAMPLES, make_gps_nmea  # noqa: E402

if __name__ == "__main__":
    make_gps_nmea.main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "gps_nmea"))
