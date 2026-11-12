"""W13.9 (2026-11-13): the performance budget as a test - opening the largest bundled example (the simulation
against its flight: a 1.3 MB ArduPilot log + a .mat) from the welcome screen until its plots are drawn takes
less than BUDGET_S on the CI machine. FINAL records the measured number and the machine's CPU count here."""
import os
import time

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401

# Measured in FINAL (see docs/dev/lanes/final.md): set to about 3x the CI machine's time.
BUDGET_S = 30.0


def test_the_largest_example_opens_within_budget(pg):
    t0 = time.perf_counter()
    pg.locator(".examples-line button", has_text="simulation against its flight").click()
    pg.wait_for_function("window.__sv.state().busy === 0 && window.__sv.state().ws.tabs.some((t) => t.plots.filter((p) => p.signals.length).length >= 2)",
                         timeout=int(BUDGET_S * 1000) + 30000)
    pg.wait_for_function("document.querySelectorAll('.grid .plot canvas').length >= 2 && !document.querySelector('.plot-loading')",
                         timeout=int(BUDGET_S * 1000) + 30000)
    took = time.perf_counter() - t0
    print(f"W13.9: the largest example opened in {took:.2f} s on {os.cpu_count()} CPUs")
    assert took < BUDGET_S, f"{took:.1f} s > {BUDGET_S} s"
