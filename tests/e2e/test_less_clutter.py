"""
U7 (owner, 2026-11-07): less on screen in the ArduPilot example. Measured here as the owner did
(visible <button> and <select>: 107 on 1.21.0) and as controls only (the same without data items:
signal rows, state stretches, flags and event marks). Also: "1 file", the points wording, the
strip's how-to line until first used, automatic flags told from the log's events.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import open_ardupilot_example, pg  # noqa: E402,F401

COUNT = """(dataToo) => { const vis = (e) => { const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return false;
  if (r.bottom < 0 || r.right < 0 || r.top > innerHeight || r.left > innerWidth) return false;
  const s = getComputedStyle(e); return s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.05; };
  const data = '.sig, .ov-phase, .band-seg, .ov-flag, .tl-event, .tl-finding';
  return [...document.querySelectorAll('button, select')].filter(vis).filter((e) => dataToo || !e.matches(data)).length; }"""


def test_fewer_buttons_and_clearer_words(pg):
    open_ardupilot_example(pg)
    pg.wait_for_selector(".findings-dock")
    pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelectorAll('.toast button[aria-label]').forEach(b => b.click())")
    pg.mouse.move(5, 5)
    pg.wait_for_timeout(400)
    total, controls = pg.evaluate(COUNT, True), pg.evaluate(COUNT, False)
    print("visible buttons:", total, "controls:", controls)
    assert controls <= 54, controls               # 26.U3: 58 -> 54 (the folded template strip, the strip's + / hide on hover)
    assert total < 90, total                      # 107 on 1.21.0; the rest is data (see TASKS U7)
    status = pg.locator(".status").inner_text()
    assert "1 file" in status and "1 files" not in status
    assert "drawn for" in status and "Showing" not in status
    # the strip's how-to line until it is first used; automatic flags say what they are
    assert pg.locator(".ov-hint").count() == 1
    assert "Automatic flag" in (pg.locator(".ov-flag").first.get_attribute("title") or "")
    pg.locator(".ov-phase", has_text="LOITER").first.click()
    pg.wait_for_selector(".ov-hint", state="detached")
    # the stage bar's icon-only buttons are in one menu
    pg.locator(".stage-more").click()
    assert pg.locator(".menu.ctx button", has_text="Clear all plots").count() == 1


def test_what_does_not_apply_is_hidden(pg):
    """26.U3: the Flight tab (map + 3D, 80 -> 71 controls): a map whose object draws the track has no
    Lon / Lat pickers or alignment (they come back from Plot options); the 3D view's image and remove
    are in its Plot options, not on the globe."""
    open_ardupilot_example(pg)
    pg.locator(".tab", has_text="Flight").first.click()
    geo = pg.locator(".plot:has(.obj-add)").first
    geo.wait_for()
    assert geo.locator(".picker-btn").count() == 0
    assert geo.locator("select[aria-label='Alignment']").count() == 0
    geo.locator(".plot-more").click()
    pg.locator(".menu.ctx button", has_text="Lat / lon track").click()
    assert geo.locator(".picker-btn").count() == 2
    pg.locator(".plot:has(.globe3d)").wait_for()
    assert pg.locator(".g3-remove").count() == 0
    pg.locator(".plot:has(.globe3d) .plot-more").click()
    assert pg.locator(".menu.ctx button", has_text="Remove the 3D view").count() == 1
