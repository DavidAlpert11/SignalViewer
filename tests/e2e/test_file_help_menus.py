"""T49 items 2 + 13, F26, F35: the top bar's buttons (sessions, Clear, settings, day / night - no File
menu since F35) and its Help menu; the shortcuts dialog describes the wheel as it works (Shift =
values, Ctrl = both, Alt = time; double-click = everything)."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, pg  # noqa: E402,F401


def close_dialog(pg):
    """Esc closes a dialog. On a slow runner an Esc pressed in the same instant the dialog appears
    was sometimes lost (a scrim stayed and blocked the next click for 30 s): wait until the scrim is
    gone, pressing Esc again if it is not - a dialog that never closes still fails."""
    for _ in range(3):
        pg.keyboard.press("Escape")
        try:
            pg.wait_for_selector(".scrim", state="detached", timeout=3000)
            return
        except Exception:
            pass
    raise AssertionError("the dialog did not close on Escape")


def test_file_and_help_menus(pg):
    assert pg.locator(".topbar .menubar-btn", has_text="File").count() == 0
    for label in ("Open session", "Save session", "Clear", "Settings", "Theme"):
        assert pg.locator(f".topbar [aria-label='{label}']").count() == 1, label
    pg.click(".topbar [aria-label='Clear']")
    items = [x.strip() for x in pg.locator(".menu.ctx button").all_inner_texts()]
    for want in ("This tab's plots", "The other tabs", "All tabs", "Clear everything"):
        assert any(i.startswith(want) for i in items), items
    assert "danger" in pg.locator(".menu.ctx button", has_text="Clear everything").get_attribute("class")
    pg.keyboard.press("Escape")
    # day / night in one click, and back
    before = pg.evaluate("window.__sv.state().theme")
    pg.click(".topbar [aria-label='Theme']")
    pg.wait_for_function(f"window.__sv.state().theme !== '{before}'")
    assert pg.evaluate("document.documentElement.dataset.theme") != before
    pg.click(".topbar [aria-label='Theme']")
    pg.wait_for_function(f"window.__sv.state().theme === '{before}'")
    pg.click(".topbar [aria-label='Settings']")
    pg.wait_for_function("window.__sv.state().settingsOpen === true")
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".scrim", state="detached")

    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Keyboard shortcuts").click()
    body = pg.locator(".dialog.help").inner_text()
    assert "Shift / Ctrl / Alt + wheel" in body and "values only / both / time only" in body
    assert "Show everything (time and values)" in body
    close_dialog(pg)

    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text="three car runs").click()
    pg.wait_for_function("window.__sv.state().runs.filter(r => r.format !== 'derived').length >= 3", timeout=20000)

    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    # T66: next to Copy error details (not clicked here: it would open the PC's own browser)
    pg.wait_for_selector(".menu.ctx button:has-text('Report a problem')")     # the menu opens after a request
    pg.locator(".menu.ctx button", has_text="About Signal Viewer").click()
    pg.wait_for_selector(".toast:has-text('github.com/DavidAlpert11/SignalViewer')")


def test_user_guide_in_the_app(pg):
    """T55: Help > User guide (F1) shows docs/GUIDE.md, in Hebrew docs/GUIDE.he.md."""
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="User guide").click()
    pg.wait_for_selector(".dialog.guide h2:has-text('user guide')")
    # the dialog's own title is that h2 too, shown before the guide's text arrives (a lazy chunk,
    # GuideDialog.tsx): wait for the text itself - on a slow CI runner it came after the count
    pg.locator(".dialog.guide h3").nth(9).wait_for()
    assert pg.locator(".dialog.guide h3").count() >= 10
    assert pg.locator(".dialog.guide .guide-table td", has_text="Backspace").count() == 1
    assert pg.locator(".dialog.guide code").count() > 5
    close_dialog(pg)
    pg.get_by_role("button", name="עברית").click()
    pg.keyboard.press("F1")
    pg.wait_for_selector(".dialog.guide h2:has-text('מדריך למשתמש')")
    pg.locator(".dialog.guide h3").nth(9).wait_for()                   # the Hebrew text, not just the title
    close_dialog(pg)
    pg.get_by_role("button", name="English").click()
