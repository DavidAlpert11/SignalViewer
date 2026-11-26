"""T49 items 2 + 13, F26, F35: the top bar's buttons (sessions, Clear, settings, day / night - no File
menu since F35) and its Help menu; the shortcuts dialog describes the wheel as it works (Shift =
values, Ctrl = both, Alt = time; double-click = everything)."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, pg, set_language  # noqa: E402,F401


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
    # CC1 (owner, 2026-11-26: calm and clear): the top row is the name, the areas, search, the area's File ▾, its
    # views, live, undo / redo, ⚙ and Help - language and theme are in Settings, the Inspector in the stage bar
    assert pg.locator(".topbar [aria-label='Settings']").count() == 1
    for gone in ("Theme", "Save session", "Clear", "Live mode settings", "Export recording…"):
        assert pg.locator(f".topbar [aria-label='{gone}']").count() == 0, gone
    assert pg.get_by_role("button", name="עברית").count() == 0
    # File ▾: data files first, then a session, the recent files; save, export, the live links, Clear ▸
    opener = pg.locator(".area-tools .file-menu-btn")
    assert opener.inner_text().strip().startswith("File")
    opener.click()
    pg.locator(".menu.ctx button", has_text="Clear").wait_for()          # the END state: the whole menu is open
    items = [x.strip() for x in pg.locator(".menu.ctx button").all_inner_texts()]
    assert items[0].startswith("Open files…") and items[1].startswith("Open session…") and items[2].startswith("Recent files"), items
    for want in ("Save session", "Export recording…", "Live mode settings…", "Clear"):
        assert any(i.startswith(want) for i in items), (want, items)
    pg.locator(".menu.ctx button", has_text="Open files…").click()
    pg.wait_for_function("window.__sv.state().browserOpen === true")
    close_dialog(pg)
    # Live follows the open files: with none open there is nothing to follow (the links are in File ▾)
    assert pg.locator(".topbar .live-btn").count() == 0
    # Clear ▸: from this tab to everything
    opener.click()
    pg.locator(".menu.ctx button", has_text="Clear").hover()
    pg.locator(".menu.ctx.sub button", has_text="Clear everything").wait_for()
    items = [x.strip() for x in pg.locator(".menu.ctx.sub button").all_inner_texts()]
    for want in ("This tab's plots", "The other tabs", "All tabs", "Clear everything"):
        assert any(i.startswith(want) for i in items), items
    assert "danger" in pg.locator(".menu.ctx.sub button", has_text="Clear everything").get_attribute("class")
    pg.keyboard.press("Escape")
    # language and theme: in Settings (the first group), changed at once
    before = pg.evaluate("window.__sv.state().theme")
    pg.click(".topbar [aria-label='Settings']")
    pg.wait_for_function("window.__sv.state().settingsOpen === true")
    other = "Light" if before == "dark" else "Dark"
    pg.locator(".dialog.settings [role='radiogroup'][aria-label='Theme'] [role='radio']", has_text=other).click()
    pg.wait_for_function(f"window.__sv.state().theme !== '{before}'")
    assert pg.evaluate("document.documentElement.dataset.theme") != before
    assert pg.locator(".dialog.settings [role='radiogroup'][aria-label='Language'] [role='radio']", has_text="עברית").count() == 1
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
    # with files open: Live in the area's tools, gone in another area
    pg.locator(".area-tools .live-btn").wait_for()
    pg.evaluate("window.__sv.setState({ area: 'sweeps' })")
    pg.wait_for_selector(".topbar .live-btn", state="detached")
    pg.evaluate("window.__sv.setState({ area: 'recordings' })")
    pg.locator(".area-tools .live-btn").wait_for()

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
    set_language(pg, "he")
    pg.keyboard.press("F1")
    pg.wait_for_selector(".dialog.guide h2:has-text('מדריך למשתמש')")
    pg.locator(".dialog.guide h3").nth(9).wait_for()                   # the Hebrew text, not just the title
    close_dialog(pg)
    set_language(pg, "en")
