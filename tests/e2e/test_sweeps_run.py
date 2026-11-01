"""MF06: the run step in the Run area - the command with placeholders, the first run's command shown
before anything runs, the sets of a group. (Running real processes: backend/tests/test_sweep_runner.py.)"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _fresh, _step, _the_goal  # noqa: E402


def test_run_step_preview(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table tbody tr")
    pg.locator(".sw-sets-table tbody tr").first.locator("input[type=checkbox]").check()     # one set marked
    pg.locator(".sw-area-btn[data-area='run']").click()
    pg.wait_for_selector(".sw-runstep")
    box = pg.locator(".sw-runstep input[aria-label='The command of one run']")
    box.fill("python sim.py --kp {kp_roll} --wind {wind} --out {out}")
    pg.wait_for_selector(".sw-run-preview code")
    code = pg.locator(".sw-run-preview code").inner_text()
    assert code.startswith("python sim.py --kp ") and "--out " in code and "{" not in code
    assert "36 runs" in pg.locator(".sw-run-preview").inner_text()                         # 1 set x 36 scenarios
    box.fill("python sim.py {nope}")
    pg.wait_for_selector(".sw-runstep .sw-error:has-text('nope')")


def test_optimiser_needs_the_run_step_then_is_ready(pg):
    _fresh(pg)
    _the_goal(pg)
    pg.locator(".sw-area-btn[data-area='run']").click()
    pg.wait_for_selector(".sw-optimiser")
    start = pg.locator(".sw-optimiser .btn", has_text="Start optimising")
    assert start.is_disabled()                                         # no run step yet
    assert "energy_wh" in pg.locator(".sw-optimiser").inner_text()     # the goal's objective
    pg.locator(".sw-runstep input[aria-label='The command of one run']").fill("python sim.py --kp {kp_roll} --out {out}")
    pg.wait_for_function("!document.querySelector('.sw-optimiser .btn.primary').disabled")
