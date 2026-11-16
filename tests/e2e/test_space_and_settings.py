"""RV11 (review B7, B9): Space after a click on a toolbar button still moves the cursor (it used to press the focused
button again); the camera's following lives under Map in Settings, beside the camera of a new Map."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg, sig  # noqa: E402,F401


def test_space_after_a_toolbar_click_is_the_cursor(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .chip")
    linked = pg.evaluate("(() => { const s = window.__sv.state(); return s.ws.tabs.find((t) => t.id === s.ws.activeTab).linkX !== false; })()")
    pg.locator(".stage-bar .link-x").click()                                   # the button keeps the focus
    after = pg.evaluate("(() => { const s = window.__sv.state(); return s.ws.tabs.find((t) => t.id === s.ws.activeTab).linkX !== false; })()")
    assert after != linked
    on = pg.evaluate("window.__sv.state().cursor.on")
    pg.keyboard.press("Space")
    pg.wait_for_function(f"window.__sv.state().cursor.on === {'false' if on else 'true'}")
    again = pg.evaluate("(() => { const s = window.__sv.state(); return s.ws.tabs.find((t) => t.id === s.ws.activeTab).linkX !== false; })()")
    assert again == after                                                      # the button was not pressed again


def test_camera_following_is_under_map(pg):
    pg.evaluate("window.__sv.setState({ settingsOpen: true })")
    row = pg.locator(".set-map .set-row", has_text="Camera following an object")
    row.wait_for()
    assert row.count() == 1
    assert pg.locator(".set-row", has_text="Camera following an object").count() == 1   # one place
