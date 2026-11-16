"""
U9 (owner, 2026-11-07, docs/dev/NAVIGATION.md option A): the areas are a switch - Recordings,
Sweeps (the Fleet area was dropped in FL1, 2026-11-16); the rail keeps the same tools, Log disabled while no
flight log is open; one views menu ("+ ▾") beside the tabs: new, from a template, the tabs a
template left out.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import pg  # noqa: E402,F401


def test_areas_rail_and_views_menu(pg):
    assert pg.locator(".areas .area-btn").all_inner_texts() == ["Recordings", "Sweeps"]
    log = pg.locator("nav.rail .rail-log")
    assert log.is_disabled() and "Open a file to check it" in log.get_attribute("title")     # D7: Checks, once a file is open
    # the views menu with nothing left out: new tab, open a template
    pg.locator(".more-tabs").click()
    items = pg.locator(".menu.ctx button").all_inner_texts()
    assert items[:2] == ["New tab", "Open a template or collection…"]
    pg.keyboard.press("Escape")
