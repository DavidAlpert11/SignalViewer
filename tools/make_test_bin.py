#!/usr/bin/env python3
"""Runs backend/svcore/example_data/make_test_bin.py (moved there 2026-11-18 so the app can write the examples on first use).
Same arguments as before; see that file for what it writes."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from svcore.example_data import make_test_bin  # noqa: E402

if __name__ == "__main__":
    make_test_bin.main()
