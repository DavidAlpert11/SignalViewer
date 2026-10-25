"""T25: Create signals > Two signals (A − B) shows how far apart A and B are, overall and for each
stretch of a state (the flight mode) - the stretch where they part ways stands out."""
import os

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def test_error_per_stretch_of_a_state(pg):
    d = pg.env["data"]
    with open(os.path.join(d, "es_sim.csv"), "w") as f:
        f.write("Time,Alt,Mode\n")
        for x in np.arange(0, 30, 0.1):
            f.write(f"{x:.3f},{x:.4f},{'TAKEOFF' if x < 10 else 'CRUISE' if x < 20 else 'LAND'}\n")
    with open(os.path.join(d, "es_flight.csv"), "w") as f:
        f.write("Time,Alt\n")
        for x in np.arange(0.05, 29.5, 0.1):
            f.write(f"{x:.3f},{x - (2 if 10 <= x < 20 else 0):.4f}\n")
    open_files(pg, "es_sim.csv", "es_flight.csv")
    sig(pg, "Alt", 0).click(); sig(pg, "Alt", 1).click()
    pg.click("[aria-label='Create signals']")
    pg.click(".seg.wide button:has-text('Two signals')")
    box = pg.locator(".err-seg")
    box.wait_for()
    box.locator(".picker-btn").click(); pg.keyboard.type("Mode"); pg.keyboard.press("Enter")   # typed, like the search
    box.locator("button", has_text="Show").click()
    box.locator(".err-table").wait_for()
    rows = box.locator(".err-table tbody tr").all_inner_texts()
    assert len(rows) == 4 and rows[-1].startswith("All"), rows
    worst = box.locator(".err-table tr.worst")
    assert worst.count() == 1 and "CRUISE" in worst.inner_text()
    worst.locator("button").first.click()                       # the stretch: the plots zoom to it
    pg.wait_for_function("Object.values(window.__sv.state().ranges).some(r => r && Math.abs(r[0] - 10) < 0.2 && Math.abs(r[1] - 20) < 0.2)")
