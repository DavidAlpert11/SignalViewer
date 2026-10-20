"""T49 items 2 + 13, F26: a File menu and a Help menu in the top bar; the shortcuts dialog describes
the wheel as it works (Shift = values, Ctrl = both, Alt = time; double-click = everything)."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, pg  # noqa: E402,F401


def test_file_and_help_menus(pg):
    pg.locator(".topbar .menubar-btn", has_text="File").click()
    items = [x.strip() for x in pg.locator(".menu.ctx button").all_inner_texts()]
    for want in ("Open files…", "Open session…", "Save session", "Clear everything"):
        assert any(i.startswith(want) for i in items), items
    assert "Ctrl+O" in pg.locator(".menu.ctx button", has_text="Open files").inner_text()
    assert "danger" in pg.locator(".menu.ctx button", has_text="Clear everything").get_attribute("class")
    pg.locator(".menu.ctx button", has_text="Open files").click()
    pg.wait_for_function("window.__sv.state().browserOpen === true")
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".scrim", state="detached")

    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Keyboard shortcuts").click()
    body = pg.locator(".dialog.help").inner_text()
    assert "Shift / Ctrl / Alt + wheel" in body and "values only / both / time only" in body
    assert "Show everything (time and values)" in body
    pg.keyboard.press("Escape")

    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text="three car runs").click()
    pg.wait_for_function("window.__sv.state().runs.filter(r => r.format !== 'derived').length >= 3", timeout=20000)

    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="About Signal Viewer").click()
    pg.wait_for_selector(".toast:has-text('github.com/DavidAlpert11/SignalViewer')")


def test_user_guide_in_the_app(pg):
    """T55: Help > User guide (F1) shows docs/GUIDE.md, in Hebrew docs/GUIDE.he.md."""
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="User guide").click()
    pg.wait_for_selector(".dialog.guide h2:has-text('user guide')")
    assert pg.locator(".dialog.guide h3").count() >= 10
    assert pg.locator(".dialog.guide .guide-table td", has_text="Backspace").count() == 1
    assert pg.locator(".dialog.guide code").count() > 5
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".dialog.guide", state="detached")
    pg.get_by_role("button", name="עברית").click()
    pg.keyboard.press("F1")
    pg.wait_for_selector(".dialog.guide h2:has-text('מדריך למשתמש')")
    pg.keyboard.press("Escape")
    pg.get_by_role("button", name="English").click()
