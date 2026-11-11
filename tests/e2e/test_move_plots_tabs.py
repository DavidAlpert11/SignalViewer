"""L10: a plot to another tab (its handle dragged onto the tab, or Move to… → a tab / New tab), and a plot's
lines into another plot (Add its lines to…, or Shift+drop) - one Undo each; a map keeps its objects.

    python -m pytest tests/e2e/test_move_plots_tabs.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, menu_item, open_files, pg  # noqa: E402,F401


@pytest.fixture()
def two(pg):
    """Tab 1: P0 (x) and P1 (y) side by side; tab 2 ("Other"): one plot with z."""
    open_files(pg, "run_a.csv")
    pg.evaluate("""() => { const st = window.__sv.state(); const rid = st.runs[0].id;
        const line = (n) => ({ sig: rid + '/' + n, color: '#3d8bfd', width: 1.5, scale: 1, offset: 0 });
        const names = st.runs[0].signals.map((s) => s.name);
        st.commit((ws) => { const t = ws.tabs[0]; t.rows = 1; t.cols = 2;
          t.plots = [{ id: 'p0', title: 'P0', signals: [line(names[0])] }, { id: 'p1', title: 'P1', signals: [line(names[1])] }]; t.active = 0;
          ws.tabs.push({ id: 'tb2', name: 'Other', rows: 1, cols: 1, plots: [{ id: 'q0', title: 'Q0', signals: [line(names[2])] }], active: 0, linkX: true });
          return ws; }); }""")
    pg.wait_for_selector(".plot >> nth=1")
    return pg


def test_drag_handle_onto_a_tab(two):
    pg = two
    pg.locator(".plot").nth(0).locator(".plot-grip").drag_to(pg.locator(".tabs [role=tab]", has_text="Other"))
    pg.wait_for_function("window.__sv.state().ws.tabs[1].plots.some((p) => p.id === 'p0')")
    t2 = S(pg, "s.ws.tabs[1]")
    assert [p["id"] for p in t2["plots"]] == ["q0", "p0"] and t2["cols"] == 2                 # the grid grew by a column
    assert S(pg, "s.ws.activeTab") == "tb2"
    assert S(pg, "s.ws.tabs[0].plots[0].signals") == []                                       # the source cell left empty
    pg.keyboard.press("Control+z")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].id === 'p0'")


def test_move_to_new_tab_and_add_lines(two):
    pg = two
    pg.locator(".plot").nth(1).locator(".plot-more").click()
    pg.locator(".menu.ctx button", has_text="Move to…").hover()
    pg.locator(".menu.ctx button", has_text="New tab").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 3")
    t3 = S(pg, "s.ws.tabs[2]")
    assert t3["name"] == "P1" and t3["plots"][0]["id"] == "p1" and S(pg, "s.ws.activeTab") == t3["id"]
    # back on tab 1: P0's lines into Other's Q0
    pg.locator(".tabs [role=tab]").nth(0).click()
    pg.locator(".plot").nth(0).locator(".plot-more").click()
    pg.locator(".menu.ctx button", has_text="Add its lines to…").hover()
    pg.locator(".menu.ctx button", has_text="Other · Q0").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[1].plots[0].signals.length === 2")
    assert S(pg, "s.ws.tabs[0].plots[0].signals") == [] and S(pg, "s.ws.activeTab") == "tb2"


def test_palette_moves_the_active_plot(two):
    pg = two
    pg.locator(".plot").nth(0).click()
    pg.keyboard.press("Control+k"); pg.keyboard.type("Move plot to tab: Other"); pg.keyboard.press("Enter")
    pg.wait_for_function("window.__sv.state().ws.tabs[1].plots.some((p) => p.id === 'p0')")
