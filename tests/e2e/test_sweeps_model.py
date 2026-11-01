"""MF04: a model of the goal - the validation table (best marked, ★), predicted vs real, the 2x2
explore panel, virtual optimisation saved as a group."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _fresh, _step, _the_goal  # noqa: E402


def test_train_explore_and_virtual_group(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table tbody tr")
    pg.locator(".sw-center-tabs button", has_text="Model").click()
    pg.locator(".sw-model-head .btn", has_text="Train the models").click()
    pg.wait_for_selector(".sw-model-table tbody tr.best")
    assert pg.locator(".sw-model-table tbody tr").count() == 4
    assert pg.locator(".sw-model-table input[type=radio]:checked").count() == 1
    pg.wait_for_selector(".sw-model-2x2 svg")
    assert pg.locator(".sw-model-2x2 figure").count() == 4
    pg.locator(".sw-virtual .btn", has_text="Find the best predicted sets").click()
    pg.wait_for_selector(".sw-virtual-table tbody tr")
    pg.locator(".sw-virtual .btn", has_text="Save as a group of virtual sets").click()
    pg.locator(".sw-center-tabs button", has_text="Lines").click()
    pg.wait_for_selector(".sw-groups .sw-group:has-text('Virtual 1')")
