"""
U6 (owner, 2026-11-07): the pointer over a time plot moves a ghost of each object on the map and in
3D (the time under the pointer, also while the cursors are on), faint; it goes when the pointer
leaves and never touches the cursor or the undo history.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import open_ardupilot_example, pg  # noqa: E402,F401
from test_features import frames, settled  # noqa: E402


def test_hover_moves_a_ghost_on_the_map(pg):
    open_ardupilot_example(pg)
    pg.locator(".tabs .tab", has_text="Flight").click()
    pg.wait_for_selector(".plot canvas")
    # a time plot beside the map and the 3D (the built-in Flight tab has none)
    pg.evaluate("""(() => { const s = window.__sv.state(); const rid = s.runs.find((r) => r.format === 'bin').id;
      s.commit((ws) => { const tab = ws.tabs.find((t) => t.name === 'Flight'); tab.rows = 2; tab.cols = 2;
        tab.plots.push({ id: 'ghost-roll', title: 'Roll', signals: [{ sig: rid + '/ATT.Roll [deg]', color: '#F2A33A', width: 1.5, scale: 1, offset: 0 }] });
        return ws; }); })()""")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: false, t1: 60, active: 1 } })")
    settled(pg); frames(pg, 3)
    past = pg.evaluate("window.__sv.state().past.length")
    roll = pg.locator(".plot", has_text="Roll").locator(".u-over")
    roll.wait_for()
    mp = pg.locator(".plot", has_text="Map").locator("canvas").first
    before = mp.screenshot()
    box = roll.bounding_box()
    for k in range(5):
        pg.mouse.move(box["x"] + box["width"] * (0.5 + 0.03 * k), box["y"] + box["height"] * 0.5)
        pg.wait_for_timeout(120)
    pg.wait_for_function("window.__sv.state().pointer !== null")
    t = pg.evaluate("window.__sv.state().pointer.t")
    assert 100 < t < 200                                        # the time under the pointer, cursors on
    pg.wait_for_timeout(500)
    assert mp.screenshot() != before                            # the ghost is drawn on the map
    c = pg.evaluate("window.__sv.state().cursor")
    assert c["t1"] == 60 and pg.evaluate("window.__sv.state().past.length") == past   # no cursor move, no undo step
    pg.mouse.move(5, 5)                                         # leaving the plot: the ghost goes
    pg.wait_for_function("window.__sv.state().pointer === null")
