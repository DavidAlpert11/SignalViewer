"""
U4 (owner, 2026-11-07): a setpoint beside its measured value in one plot (ArduPilot DesRoll / Roll,
PX4 roll_sp / roll) is drawn dashed and faded by itself; a style set by hand (Inspector ▸ Line)
wins, and Auto brings the automatic one back.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import open_ardupilot_example, pg  # noqa: E402,F401


def test_desired_dashed_until_styled_by_hand(pg):
    open_ardupilot_example(pg)
    roll = pg.locator(".plot").first
    des = roll.locator(".chip", has_text="ATT.DesRoll")
    act = roll.locator(".chip", has_text="ATT.Roll [deg]").filter(has_not_text="Des")
    des.wait_for()
    assert des.locator(".sw.dashed").count() == 1 and act.locator(".sw.dashed").count() == 0
    des.click()                                                        # the Inspector opens on it
    pg.locator(".seg button", has_text="Solid").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.find((s) => s.sig.includes('DesRoll')).dash === false")
    assert des.locator(".sw.dashed").count() == 0
    pg.locator(".seg button", has_text="Auto").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.find((s) => s.sig.includes('DesRoll')).dash === undefined")
    assert des.locator(".sw.dashed").count() == 1
    # alone in a plot (its measured value removed) it is an ordinary line
    act.locator(".rm").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    assert des.locator(".sw.dashed").count() == 0
