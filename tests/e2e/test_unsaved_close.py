"""W10 (2026-11-13): ask before closing with unsaved changes - the browser's own prompt in a tab, the app's
Save / Don't save / Cancel for the window (the pywebview close itself needs a manual check), the setting.
W8: the command palette with nothing typed - recent commands first, group headers, keys, an icon per row."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, save_as, sig  # noqa: E402,F401


def _close_and_catch(pg):
    seen = []
    pg.on("dialog", lambda d: (seen.append(d.type), d.dismiss()))
    pg.close(run_before_unload=True)
    pg.wait_for_timeout(300) if not pg.is_closed() else None
    return seen


def test_the_browser_asks_when_the_work_is_unsaved(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("(() => { const s = window.__sv.state(); return s.wsRev !== s.savedRev; })()")
    assert _close_and_catch(pg) == ["beforeunload"]


def test_saved_work_closes_without_asking(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Control+s")
    save_as(pg, "w10.svsession")
    pg.wait_for_function("(() => { const s = window.__sv.state(); return s.wsRev === s.savedRev; })()")
    sig(pg, "RPM").click()                                            # a change after the save: unsaved again
    pg.wait_for_function("(() => { const s = window.__sv.state(); return s.wsRev !== s.savedRev; })()")
    pg.keyboard.press("Control+z")                                    # undone back to what was saved: saved
    pg.wait_for_function("(() => { const s = window.__sv.state(); return s.wsRev === s.savedRev; })()")
    assert _close_and_catch(pg) == []


def test_the_window_close_offers_save_dont_save_cancel(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("(() => { const s = window.__sv.state(); return s.wsRev !== s.savedRev; })()")
    assert pg.evaluate("window.__svCloseRequest()") is False          # what run.py asks the page
    dlg = pg.locator(".unsaved-dialog")
    dlg.wait_for()
    assert [b.strip() for b in dlg.locator(".dialog-foot .btn").all_inner_texts()] == ["Don't save", "Cancel", "Save…"]
    dlg.locator(".btn", has_text="Cancel").click()
    pg.wait_for_selector(".unsaved-dialog", state="detached")
    assert pg.evaluate("window.__svCloseRequest()") is False
    with pg.expect_response("**/api/window/close") as r:
        pg.locator(".unsaved-dialog .btn", has_text="Don't save").click()
    assert r.value.json()["ok"] is True
    assert pg.evaluate("window.__svCloseRequest()") is True           # chosen: nothing asks again


def test_the_setting_turns_it_off(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.click(".topbar [aria-label='Settings']")
    pg.locator(".dialog.settings button[role=radio]", has_text="Don't ask").click()
    pg.keyboard.press("Escape")
    pg.wait_for_function("window.__sv.state().askBeforeClose === false")
    assert pg.evaluate("window.__svCloseRequest()") is True
    assert _close_and_catch(pg) == []


def test_palette_recent_first_groups_keys_and_icons(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Control+k")
    pg.wait_for_selector(".pal-head")
    assert "Recent" not in pg.locator(".pal-head").all_inner_texts()
    items = pg.locator(".pal-item")
    n = items.count()
    assert n > 10 and pg.locator(".pal-item svg").count() == n           # every row has its icon
    assert pg.locator(".pal-item[data-cmd='reset'] .pal-keys .kbd").inner_text() == "R"
    pg.locator(".pal-item[data-cmd='reset']").click()
    pg.keyboard.press("Control+k")
    pg.wait_for_selector(".pal-head")
    assert pg.locator(".pal-head").first.inner_text().strip().lower() == "recent"
    assert pg.locator(".pal-item").first.get_attribute("data-cmd") == "reset"
    pg.fill(".palette-input", "zoom")                                  # typing: no headers, the group shown
    pg.wait_for_function("!document.querySelector('.pal-head')")
    pg.keyboard.press("Escape")
