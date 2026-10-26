"""State lanes: where a lane is shown (this plot / every plot of the tab / every time plot of every
tab), removed from the lane itself, "always as a state" by signal name, and the lane's name off the
data (owner's report, 2026-10-26).

    python -m pytest tests/e2e/test_state_lanes.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, menu_item, open_files, pg, sig  # noqa: E402,F401


def _lane_point(pg):
    """A point inside the bottom lane of the first plot (lanes sit along the bottom under lines)."""
    box = pg.locator(".plot").first.locator(".u-over").bounding_box()
    return box["x"] + box["width"] * 0.5, box["y"] + box["height"] - 4


def test_lane_scope_from_the_signal_list_and_removed_from_the_lane(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 1")
    sig(pg, "Gear").click(button="right"); menu_item(pg, "Lane on every plot of this tab")
    pg.wait_for_function("(window.__sv.state().ws.tabs[0].sharedStates || []).length === 1")
    sig(pg, "Gear").click(button="right"); menu_item(pg, "Lane on every time plot, all tabs")
    pg.wait_for_function("(window.__sv.state().ws.globalStates || []).length === 1")
    assert S(pg, "(s.ws.tabs[0].sharedStates || []).length") == 0      # one place at a time
    # hovering the lane says what it is and where it is shown
    x, y = _lane_point(pg)
    pg.mouse.move(x, y)
    pg.wait_for_function("(document.querySelector('.plot .u-over').title || '').includes('Gear')")
    assert "every tab" in pg.evaluate("document.querySelector('.plot .u-over').title")
    # right-click on the lane: its own menu, with Remove
    pg.mouse.click(x, y, button="right")
    menu_item(pg, "Remove this lane")
    pg.wait_for_function("(window.__sv.state().ws.globalStates || []).length === 0")
    assert S(pg, "s.ws.tabs[0].plots[0].signals.length") == 1           # Speed stays


def test_always_as_a_state_follows_the_name_in_every_file(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    sig(pg, "Gear").click()                                             # a line (no texts)
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    assert not S(pg, "s.ws.tabs[0].plots[0].signals[0].state")
    pg.locator(".plot .chip").first.click(button="right"); menu_item(pg, "Always as a state")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals[0].state === true")
    assert S(pg, "s.ws.stateNames.Gear") is True
    sig(pg, "Gear", 1).click()                                          # the other file's Gear: a lane at once
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 2")
    assert S(pg, "s.ws.tabs[0].plots[0].signals.every(x => x.state)")
    pg.locator(".plot .chip").first.click(button="right"); menu_item(pg, "Always as a state")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.every(x => !x.state)")


def test_lane_on_this_plot_only_from_a_tab_lane(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    sig(pg, "Gear").click(button="right"); menu_item(pg, "Lane on every plot of this tab")
    pg.wait_for_function("(window.__sv.state().ws.tabs[0].sharedStates || []).length === 1")
    x, y = _lane_point(pg)
    pg.mouse.click(x, y, button="right")
    menu_item(pg, "Lane on this plot only")
    pg.wait_for_function("(window.__sv.state().ws.tabs[0].sharedStates || []).length === 0")
    assert S(pg, "s.ws.tabs[0].plots[0].signals.some(x => x.sig.endsWith('/Gear') && x.state)")
