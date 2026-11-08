"""O2: a damaged flight log opens with what could be read, and the note after opening says what was
left out (no phantom IMU[149] signals in the list)."""
import os
import subprocess
import sys

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg  # noqa: E402,F401

TOOLS = os.path.join(os.path.dirname(__file__), "..", "..", "tools")


def test_damaged_bin_says_what_was_left_out(pg):
    p = os.path.join(pg.env["data"], "damaged.bin")
    subprocess.run([sys.executable, os.path.join(TOOLS, "make_test_bin.py"), p, "--seconds", "8", "--imu-hz", "50",
                    "--corrupt"], check=True, capture_output=True)
    open_files(pg, "damaged.bin")
    pg.wait_for_selector(".toast:has-text('damaged bytes skipped')")
    note = " | ".join(pg.locator(".toast").all_inner_texts())
    assert "messages next to damage left out" in note, note
    names = S(pg, "s.runs.filter(r => r.format !== 'derived').flatMap(r => r.signals.map(x => x.name))")
    assert names and not any(n.startswith("IMU[") and not n.startswith(("IMU[0]", "IMU[1]")) for n in names), names
