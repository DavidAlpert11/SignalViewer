#!/usr/bin/env python3
"""Runs backend/svcore/example_data/make_report_demo.py - the two recordings that show every ready-made part of the
report (examples/report_demo). Optional argument: the folder to write them in."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from svcore.example_data import REPO_EXAMPLES, make_report_demo  # noqa: E402

if __name__ == "__main__":
    make_report_demo.main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "report_demo"))
