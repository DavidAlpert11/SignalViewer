"""
26.U8: one list of events - the log's modes / events / errors, the health check's findings, the
conditions' stretches and the limits' violations - and ] / [ to step through them (the status bar says
which one); a focused condition keeps its own stepping.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import open_ardupilot_example, pg  # noqa: E402,F401


def _t1(pg):
    return pg.evaluate("window.__sv.state().cursor.t1")


def test_step_through_events_and_one_list(pg):
    open_ardupilot_example(pg)
    pg.wait_for_selector(".findings-dock")
    pg.evaluate("document.activeElement && document.activeElement.blur()")
    pg.keyboard.press("]")
    pg.wait_for_selector(".status .ev-at", timeout=10000)
    first = _t1(pg)
    label = pg.locator(".status .ev-at").inner_text()
    assert label.startswith("◆ 1/")
    total = int(label.split("/")[1].split(" ")[0])
    pg.keyboard.press("]")
    pg.wait_for_function(f"window.__sv.state().cursor.t1 > {first}")
    assert pg.locator(".status .ev-at").inner_text().startswith("◆ 2/")
    pg.keyboard.press("[")
    pg.wait_for_function(f"window.__sv.state().cursor.t1 === {first}")
    # a limit on a plotted signal: its violations are events too
    pg.evaluate("""window.__sv.state().commit((ws) => { const t = ws.tabs.find(x => x.id === ws.activeTab);
        t.plots[0].signals[0].limits = { lo: -5, hi: 5 }; return ws; })""")
    pg.locator("[aria-label='Flight log']").first.click()
    pg.locator(".log-tabs button", has_text="Events").click()
    chips = pg.locator(".log-chips")
    chips.locator("button", has_text="Findings").wait_for(timeout=10000)
    chips.locator("button", has_text="Limits").wait_for(timeout=10000)
    for k in ("Modes", "Messages"):
        chips.locator("button", has_text=k).click()                  # only findings and limits left
    rows = pg.locator(".log-list .log-row")
    assert rows.count() >= 4 and pg.locator(".log-list .kind-dot.limit").count() >= 1
    times = [float(x.replace(",", "")) for x in pg.locator(".log-list .log-t").all_inner_texts()]
    assert times == sorted(times)                                      # one list, in time order
    pg.locator(".log-list .log-row:has(.kind-dot.limit)").first.click()
    t_lim = _t1(pg)
    assert t_lim is not None
    # ] from just before it lands on it (limits are stepped through like the rest)
    pg.evaluate(f"window.__sv.setState({{ cursor: {{ ...window.__sv.state().cursor, t1: {t_lim} - 1e-6 }} }})")
    pg.evaluate("document.activeElement && document.activeElement.blur()")
    pg.keyboard.press("]")
    pg.wait_for_function(f"Math.abs(window.__sv.state().cursor.t1 - {t_lim}) < 1e-9")
    after = pg.locator(".status .ev-at").inner_text()
    assert int(after.split("/")[1].split(" ")[0]) > total              # the limit's violations are stepped through too
