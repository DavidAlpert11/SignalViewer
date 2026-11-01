"""MF08: robust design in the Run area - a tolerance with a distribution, the best sets' spread on a
model (mean, sigma, percentile, probability of failure, mean against sigma), the samples around one as
a group to run, a group's statistics."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401
from test_sweeps_flow import _fresh, _the_goal, _step  # noqa: E402


def test_spread_on_a_model_a_group_to_run_and_its_statistics(pg):
    _fresh(pg)
    _the_goal(pg)
    pg.locator(".sw-area-btn[data-area='run']").click()
    pg.wait_for_selector(".sw-robust-sheet")
    assert "tolerance first" in pg.locator(".sw-robust-sheet").inner_text()
    _step(pg, "goals")
    sec = pg.locator(".sw-goal-part", has_text="Robust to")
    sec.locator(".sw-colpick-btn").click()
    pg.locator(".sw-colpick-pop .msp-item", has_text="kp_roll").locator("input").check()
    pg.keyboard.press("Escape")
    sec.locator("select[aria-label='Distribution of kp_roll']").select_option("normal")
    pg.locator(".sw-area-btn[data-area='run']").click()
    sheet = pg.locator(".sw-robust-sheet")
    assert "kp_roll" in sheet.inner_text() and "normal" in sheet.inner_text()
    sheet.locator("select[aria-label='Failure comparison']").select_option("<=")
    sheet.locator(".btn", has_text="Estimate on a model").click()
    pg.wait_for_selector(".sw-robust-table tbody tr", timeout=30000)
    n = sheet.locator(".sw-robust-table tbody tr").count()
    assert 1 <= n <= 5
    assert "P(fail)" in sheet.locator(".sw-robust-table thead").inner_text()
    assert sheet.locator(".sw-robust-plot circle").count() == n
    sheet.locator(".sw-robust-table tbody tr").first.locator(".btn", has_text="Run for real").click()
    pg.wait_for_selector(".toast:has-text('saved as a group')")
    sheet.locator(".btn", has_text="Compute").click()
    pg.wait_for_selector(".sw-robust-gstats:has-text('mean')")
