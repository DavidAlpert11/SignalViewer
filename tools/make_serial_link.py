#!/usr/bin/env python3
"""Runs backend/svcore/example_data/make_serial_link.py - a serial link recorded byte by byte, both directions
(examples/serial_link). Optional argument: the folder to write them in."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from svcore.example_data import REPO_EXAMPLES, make_serial_link  # noqa: E402

if __name__ == "__main__":
    make_serial_link.main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "serial_link"))
