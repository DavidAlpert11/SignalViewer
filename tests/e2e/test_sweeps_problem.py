"""MF01 / Q129: Explore's values typed, not only slid (outside the results kept, Esc restores), and
the problem as one table - the same draft as the sliders."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _fresh, _holding, _step, _the_goal  # noqa: E402


def _explore(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table th:has-text('worst')")
    holding = _holding(pg)
    pg.locator(".sw-center-tabs button", has_text="Explore").click()
    pg.wait_for_selector(".sw-funnel")
    return holding


def _funnel(pg):
    return [int(x.replace(",", "")) for x in pg.locator(".sw-funnel li b").all_inner_texts()]


def test_type_a_condition_below_every_result_and_escape(pg):
    holding = _explore(pg)
    assert _funnel(pg)[1] == holding
    f = pg.locator(".sw-explore button.sw-num[aria-label='Limit of roll_error_deg']")
    before = f.inner_text()
    f.click()
    box = pg.locator(".sw-explore input.sw-num-field")
    box.fill("-1"); box.press("Enter")
    pg.wait_for_function("+document.querySelectorAll('.sw-funnel li b')[1].innerText.replace(/,/g, '') === 0")
    f = pg.locator(".sw-explore button.sw-num[aria-label='Limit of roll_error_deg']")
    assert "-1" in f.inner_text() and "outside" in f.get_attribute("class")          # kept, and said
    # Esc restores the value it had
    f.click()
    box = pg.locator(".sw-explore input.sw-num-field")
    box.fill("123"); box.press("Escape")
    assert "-1" in pg.locator(".sw-explore button.sw-num[aria-label='Limit of roll_error_deg']").inner_text()
    assert before != "-1"


def test_problem_as_a_table_is_the_same_draft(pg):
    _explore(pg)
    pg.locator(".sw-explore-as button", has_text="Table").click()
    pg.wait_for_selector(".sw-problem-table tr[data-param='kp_roll']")
    all_sets = _funnel(pg)[2]
    pg.locator(".sw-problem-table button.sw-num[aria-label='kp_roll up to']").click()
    box = pg.locator(".sw-problem-table input.sw-num-field")
    box.fill("0.2"); box.press("Enter")
    pg.wait_for_function(f"+document.querySelectorAll('.sw-funnel li b')[2].innerText.replace(/,/g, '') < {all_sets}")
    assert "limited" in pg.locator(".sw-problem-table tr[data-param='kp_roll']").get_attribute("class")
    # back to the sliders: the same limit
    pg.locator(".sw-explore-as button", has_text="Sliders").click()
    assert "0.2" in pg.locator(".sw-explore button.sw-num[aria-label='kp_roll up to']").inner_text()
