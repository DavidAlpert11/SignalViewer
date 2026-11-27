"""P (owner, 2026-11-16): the commanded / measured pairs of a log in one click - a new tab with a plot per pair,
the setpoint dashed beside its measured value, one Undo; from the file's menu (*Found in this file ▸*, 1.39) and from Ctrl+K."""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, menu_item, open_files, pg, S  # noqa: E402,F401

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def test_pairs_in_one_click_and_one_undo(pg):
    shutil.copy(os.path.join(ROOT, "examples", "copter_flight.bin"), os.path.join(pg.env["data"], "copter_flight.bin"))
    open_files(pg, "copter_flight.bin")
    tabs = S(pg, "s.ws.tabs.length")
    pg.locator(".run-head").first.click(button="right")
    # AU1 (1.39): the file's menu lists it under *Found in this file ▸*
    pg.locator(".menu.ctx button", has_text="Found in this file").first.hover()
    pg.locator(".menu.ctx.sub button", has_text="command / response pairs").click()
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length === {tabs + 1}")
    assert S(pg, "s.ws.tabs.at(-1).name") == "Commanded / measured"
    assert S(pg, "s.ws.tabs.at(-1).plots.length") == 6                  # ATT Roll / Pitch / Yaw, RATE R / P / Y
    assert S(pg, "s.ws.tabs.at(-1).plots[0].signals.map((x) => x.sig.split('/')[1]).join()") == "ATT.Roll [deg],ATT.DesRoll [deg]"
    pg.wait_for_function("document.querySelectorAll('.plot').length >= 6")
    pg.keyboard.press("Control+z")
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length === {tabs}")
    # the same from the command palette
    pg.keyboard.press("Control+k")
    pg.fill(".palette-input", "commanded / measured")
    pg.keyboard.press("Enter")
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length === {tabs + 1}")
