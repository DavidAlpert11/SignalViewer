"""W16 / T50 / W13.7 (2026-11-13): a calmer screen - each moved control is still reachable; plots too short to
read say so; every button class shows a focus ring."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, menu_item, open_files, pg, sig  # noqa: E402,F401
from test_sweeps_flow import _to_sweeps  # noqa: E402


def test_moved_controls_are_still_reachable(pg):
    open_files(pg, "run_a.csv")
    assert pg.locator(".status .status-help").count() == 0                  # shortcuts: Help ▾ and the ? key
    pg.keyboard.press("?")
    pg.wait_for_selector(".help")
    pg.keyboard.press("Escape")
    assert pg.locator(".stage-bar .btn", has_text="Y").count() == 0          # Link value axes: in More, shown while on
    pg.click(".stage-bar .stage-more"); menu_item(pg, "Link value axes")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].linkY === true")
    pg.wait_for_selector(".stage-bar .btn[aria-pressed=true]:has-text('Y')")
    pg.keyboard.press("Control+k"); pg.fill(".palette-input", "Link value axes"); pg.keyboard.press("Enter")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].linkY === false")
    pg.click(".topbar [aria-label='Settings']")
    fold = pg.locator(".dialog.settings details.set-fold")
    assert not fold.evaluate("d => d.open")
    fold.locator("summary").click()
    pg.wait_for_selector(".set-storage .btn")
    pg.keyboard.press("Escape")


def test_sweeps_welcome_has_one_way_in(pg):
    _to_sweeps(pg)
    pg.wait_for_selector(".sw-welcome")
    labels = pg.locator(".sw-welcome-actions .btn").all_inner_texts()
    assert not any("folder" in x.lower() or "saved study" in x.lower() for x in labels)
    pg.locator(".areabar .btn", has_text="Open").click()
    pg.wait_for_selector(".menu.ctx button:has-text('Open a folder of tables')")
    pg.keyboard.press("Escape")


def test_too_many_plots_for_the_window(pg):
    pg.set_viewport_size({"width": 1100, "height": 700})
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.evaluate("window.__sv.state().commit((ws) => { ws.tabs[0].rows = 6; ws.tabs[0].cols = 1; "
                "while (ws.tabs[0].plots.length < 6) ws.tabs[0].plots.push({ id: 'p' + ws.tabs[0].plots.length, title: '', signals: [] }); return ws; })")
    hint = pg.locator(".too-many-plots")
    hint.wait_for()
    hint.locator(".linklike").click()
    pg.wait_for_function("window.__sv.state().soloPlot === true")
    pg.wait_for_selector(".too-many-plots", state="detached")


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_focus_ring_on_every_button_class(pg, theme):
    pg.evaluate(f"window.__sv.setState({{ theme: '{theme}' }})")
    open_files(pg, "run_a.csv")
    for sel in (".btn", ".iconbtn", ".search-trigger"):
        el = pg.locator(f"{sel}:visible").first
        el.focus()
        pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Tab")             # a keyboard focus: :focus-visible
        style = pg.evaluate("() => { const e = document.activeElement; const s = getComputedStyle(e); return [s.outlineStyle, s.outlineWidth]; }")
        assert style[0] != "none" and style[1] != "0px", (sel, style)
