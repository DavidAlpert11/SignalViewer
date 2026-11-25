"""
U5 (owner, 2026-11-07): the Compare panel as the Simulink Data Inspector - with a tolerance, each
signal in the list says pass / fail (✓ / ✗); picking one shows its difference from the baseline over
time with the tolerance band, the stretches outside it in red and listed (a click goes there).
"""
import pytest

from test_features import open_example  # noqa: E402

pytest.importorskip("playwright.sync_api")
from test_template_tabs import pg  # noqa: E402,F401


def test_where_and_why_a_signal_fails(pg):
    open_example(pg, "car")
    pg.wait_for_function("document.querySelectorAll('.run-head').length === 3")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row", timeout=30000)
    pg.locator(".sim-settings-toggle").click()
    pg.locator(".cmp-panel > .tol-fields .afield", has_text="Tolerance (±)").locator("input").fill("2")
    pg.wait_for_selector(".sim-row .sim-pass", timeout=30000)
    assert pg.locator(".sim-row .sim-fail").count() >= 1                     # ✓ and ✗ in the list
    pg.locator(".sim-row", has_text="Speed").first.click()
    chart = pg.locator(".diff-chart")
    chart.wait_for(timeout=20000)
    # review C8: the differences in the signal's unit, correlation written out, the match % defined where it is shown
    head = pg.locator("table.cmp2 thead").inner_text()
    assert "[km/h]" in head and head.count("[km/h]") == 2 and "CORRELATION" in head.upper()
    assert "share of the signal's range" in pg.locator(".sim-row .sim-pct").first.get_attribute("title")
    assert chart.locator(".diff-band").count() == 1 and chart.locator(".diff-line").count() == 2
    assert chart.locator(".diff-out").count() >= 1 and "outside" in chart.locator("figcaption").inner_text()
    chart.locator(".diff-outs button").first.click()                         # to the first stretch outside
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.dual")
    # without a tolerance: the difference alone, no band, nothing outside
    pg.locator(".cmp-panel > .tol-fields .afield", has_text="Tolerance (±)").locator("input").fill("")
    pg.wait_for_function("!document.querySelector('.sim-row .sim-pass')", timeout=30000)
    pg.locator(".sim-row", has_text="Speed").first.click()
    pg.wait_for_function("document.querySelector('.diff-chart') && !document.querySelector('.diff-band')", timeout=20000)


def test_a_row_click_never_takes_over_the_users_plot(pg):
    """Review 2026-11-25 (C4): a click on a ranked signal replaced the signals of whichever plot was active. Now the
    first click makes Compare's own plot, later clicks flip through that one; the user's plots stay as they were;
    Undo takes it all back; Shift+click is said on screen."""
    open_example(pg, "car")
    pg.wait_for_function("document.querySelectorAll('.run-head').length === 3")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row", timeout=30000)
    assert "Shift+click" in pg.inner_text(".sim-click-hint")
    tab = "window.__sv.state().ws.tabs.find(t => t.id === window.__sv.state().ws.activeTab)"
    tabs = "window.__sv.state().ws.tabs.map(t => t.id + '|' + t.rows + 'x' + t.cols + '|' + t.plots.map(p => p.id + ':' + p.signals.map(s => s.sig).join(',')).join(';'))"
    before = pg.evaluate(tabs)
    names = [x.split("\n")[0] for x in pg.locator(".sim-row .sim-name").all_inner_texts()][:2]
    for name in names:
        pg.locator(".sim-row", has_text=name).first.click()
        pg.wait_for_function(f"{tab}.plots[{tab}.active].title === {name!r}")
        assert pg.evaluate("window.__sv.state().ws.tabs.length") == len(before) + 1    # one tab of its own, the second click too
    assert pg.evaluate(f"{tab}.name") == "Similarity" and pg.evaluate(f"{tab}.plots.length") == 1
    assert pg.evaluate(tabs)[:len(before)] == before                         # the user's tabs, plots and layout untouched
    assert pg.evaluate("window.__sv.state().comparePlot") == pg.evaluate(f"{tab}.plots[0].id")
    # round 2: after a restart the id is gone (UI state) - the tab is found by its mark, not made twice
    pg.evaluate("window.__sv.setState({ comparePlot: null })")
    pg.locator(".sim-row", has_text=names[0]).first.click()
    pg.wait_for_function(f"{tab}.plots[{tab}.active].title === {names[0]!r}")
    assert pg.evaluate("window.__sv.state().ws.tabs.length") == len(before) + 1
    assert pg.evaluate(f"{tab}.kind") == "similarity"
    pg.evaluate("window.__sv.setState({ lang: 'he' })")                         # its name follows the language
    pg.wait_for_function("[...document.querySelectorAll('.tabs [role=tab]')].some(x => x.textContent.includes('דמיון'))")
    pg.evaluate("window.__sv.setState({ lang: 'en' })")
    for _ in range(3):
        pg.keyboard.press("Control+z")
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length === {len(before)}")
