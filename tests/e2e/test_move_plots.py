"""N2: plots change places - the drag handle onto another plot, the plot menu's Move to…, and
Ctrl+Shift+arrows; one Undo each, the cells keep their sizes.

    python -m pytest tests/e2e/test_move_plots.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig, menu_item  # noqa: E402,F401


@pytest.fixture()
def grid(pg):
    open_files(pg, "run_a.csv")
    pg.evaluate("""window.__sv.state().commit((ws) => { const tab = ws.tabs[0]; tab.rows = 2; tab.cols = 2;
        while (tab.plots.length < 4) tab.plots.push({ id: 'pm' + tab.plots.length, title: '', signals: [] });
        tab.plots.forEach((p, i) => { p.title = 'P' + i; }); tab.active = 0; return ws; })""")
    pg.wait_for_selector(".plot >> nth=3")
    return pg


def titles(pg):
    return [p["title"] for p in S(pg, "s.ws.tabs[0].plots")]


def test_drag_handle_swaps(grid):
    pg = grid
    grip = pg.locator(".plot").nth(0).locator(".plot-grip")
    grip.drag_to(pg.locator(".plot").nth(3))
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[3].title === 'P0'")
    assert titles(pg) == ["P3", "P1", "P2", "P0"]
    pg.keyboard.press("Control+z")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].title === 'P0'")


def test_move_to_menu_and_keys(grid):
    pg = grid
    pg.locator(".plot").nth(1).locator(".plot-more").click()
    pg.locator(".menu.ctx button", has_text="Move to…").hover()
    pg.locator(".menu.ctx button", has_text="row 2, column 1").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[2].title === 'P1'")
    assert titles(pg) == ["P0", "P2", "P1", "P3"] and S(pg, "s.ws.tabs[0].active") == 2
    pg.locator("body").click(position={"x": 2, "y": 2})
    pg.keyboard.press("Control+Shift+ArrowRight")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[3].title === 'P1'")
    pg.keyboard.press("Control+Shift+ArrowUp")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[1].title === 'P1'")
    assert titles(pg) == ["P0", "P1", "P3", "P2"]
