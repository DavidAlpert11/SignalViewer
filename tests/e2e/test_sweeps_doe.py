"""MF03: a design of experiments in the Run area - parameters varied or held, a method, the preview,
the run list exported, the design saved as a group."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _fresh, _the_goal  # noqa: E402


def test_design_export_and_group(pg):
    _fresh(pg)
    _the_goal(pg)
    pg.locator(".sw-area-btn[data-area='run']").click()
    pg.wait_for_selector(".sw-doe-table tbody tr")
    assert pg.locator(".sw-doe-table tbody tr").count() == 3
    # hold filter_hz, vary the two gains, 12 space-filling sets
    pg.locator(".sw-doe-table tr[data-param='filter_hz'] input[type=checkbox]").uncheck()
    assert "held at" in pg.locator(".sw-doe-table tr[data-param='filter_hz']").inner_text()
    pg.locator(".sw-doe-controls button.sw-num[aria-label='How many']").click()
    box = pg.locator(".sw-doe-controls input.sw-num-field"); box.fill("12"); box.press("Enter")
    pg.locator(".sw-doe-controls .btn", has_text="Make the design").click()
    pg.wait_for_selector(".sw-doe-result:has-text('12 new sets')")
    assert pg.locator(".sw-doe-preview g").count() == 1                 # two varied parameters: one pair
    pg.locator(".sw-doe .btn", has_text="Export the run list").click()
    save_as(pg, "doe.csv")
    pg.wait_for_selector(".toast:has-text('doe.csv')")
    lines = open(os.path.join(pg.env["out"], "doe.csv")).read().strip().splitlines()
    assert lines[0].startswith("kp_roll,ki_roll,filter_hz") and len(lines) - 1 == 12 * 36
    pg.locator(".sw-doe .btn", has_text="Save as a group").click()
    pg.locator(".sw-area-btn[data-area='explore']").click()
    pg.wait_for_selector(".sw-groups .sw-group:not(.auto):has-text('DOE 1')")
    assert pg.locator(".sw-group:has-text('DOE 1') .sw-group-n").inner_text() == "0"   # not run yet
