"""
U9 (owner, 2026-11-07, docs/dev/NAVIGATION.md option A): the areas are a switch - Recordings,
Sweeps, Fleet (Fleet was a panel of the rail); the rail keeps the same tools, Log disabled while no
flight log is open; one views menu ("+ ▾") beside the tabs: new, from a template, the tabs a
template left out.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import pg  # noqa: E402,F401


def test_areas_rail_and_views_menu(pg):
    assert pg.locator(".areas .area-btn").all_inner_texts() == ["Recordings", "Sweeps", "Fleet"]
    assert pg.locator("nav.rail [aria-label='Fleet']").count() == 0
    log = pg.locator("nav.rail .rail-log")
    assert log.is_disabled() and "none of the open files" in log.get_attribute("title")
    # the views menu with nothing left out: new tab, open a template
    pg.locator(".more-tabs").click()
    items = pg.locator(".menu.ctx button").all_inner_texts()
    assert items[:2] == ["New tab", "Open a template or collection…"]
    pg.keyboard.press("Escape")
    # the Fleet area: its example, a flight opened at a finding goes back to Recordings with the Log
    pg.locator(".areas .area-btn", has_text="Fleet").click()
    pg.locator(".fleet-area .fleet-example .btn").click()
    pg.wait_for_selector(".fleet-log", timeout=60000)
    pg.locator(".fleet-line").first.click()
    pg.locator(".fleet-findings button").first.click()
    pg.wait_for_function("window.__sv.state().area === 'recordings' && window.__sv.state().panel === 'log'", timeout=30000)
    assert not pg.locator("nav.rail .rail-log").is_disabled()
