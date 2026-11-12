"""W13.8 (2026-11-13): the 30-second tour - from Help ▾ (it does not start by itself under automation), four
coach marks on the data-tour anchors, Next / Skip, remembered once done, en + he."""
import json
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, menu_item, pg  # noqa: E402,F401


def _start(pg):
    pg.click(".topbar button:has-text('Help')")
    menu_item(pg, "Tour")
    pg.wait_for_selector(".tour-card")


def test_the_tour_walks_the_anchors_and_is_remembered(pg):
    assert pg.locator(".tour-card").count() == 0                     # not by itself under automation
    _start(pg)
    seen = []
    for _ in range(6):
        card = pg.locator(".tour-card")
        if not card.count():
            break
        seen.append(card.get_attribute("data-step"))
        ring = pg.locator(".tour-ring").bounding_box()
        assert ring["width"] > 10 and ring["height"] > 10
        pg.locator(".tour-next").click()
    assert len(seen) >= 3 and pg.locator(".tour-card").count() == 0
    path = os.path.join(pg.env["home"], ".signalviewer", "ui_settings.json")
    for _ in range(50):
        if os.path.exists(path) and json.load(open(path)).get("tourDone") is True:
            break
        pg.wait_for_timeout(100)
    assert json.load(open(path)).get("tourDone") is True


def test_the_tour_in_hebrew_and_skip(pg):
    pg.evaluate("window.__sv.setState({ lang: 'he' })")
    pg.click(".topbar button:has-text('עזרה')")
    menu_item(pg, "סיור")
    pg.wait_for_selector(".tour-card")
    assert any("\u0590" <= ch <= "\u05FF" for ch in pg.locator(".tour-card").inner_text())
    pg.locator(".tour-skip").click()
    pg.wait_for_selector(".tour-card", state="detached")
