"""MF05: how much each parameter matters - the table of shares and Sobol indices for the goal, a
threshold that marks the weak parameters, and taking them off the lines."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _fresh, _step, _the_goal  # noqa: E402


def test_sensitivity_table_threshold_and_weak_off_the_lines(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table tbody tr")
    pg.locator(".sw-center-tabs button", has_text="Which parameter matters").click()
    pg.wait_for_selector(".sw-sens-table tbody tr")
    rows = pg.locator(".sw-sens-table tbody tr")
    assert rows.count() == 3                                          # kp_roll, ki_roll, filter_hz
    # a high threshold makes every parameter weak; the button takes them off the lines
    pg.locator(".sw-sens-head button.sw-num").click()
    box = pg.locator(".sw-sens-head input.sw-num-field")
    box.fill("99"); box.press("Enter")
    pg.wait_for_function("document.querySelectorAll('.sw-sens-table tr.weak').length === 3")
    pg.locator(".sw-sens-head .btn", has_text="Take the weak ones off the lines").click()
    pg.keyboard.press("Control+z")                                     # undo brings them back
