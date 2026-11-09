"""
U5 (owner, 2026-11-07): the Compare panel as the Simulink Data Inspector - with a tolerance, each
signal in the list says pass / fail (✓ / ✗); picking one shows its difference from the baseline over
time with the tolerance band, the stretches outside it in red and listed (a click goes there).
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import pg  # noqa: E402,F401


def test_where_and_why_a_signal_fails(pg):
    pg.locator(".examples-line button", has_text="three car runs").click()
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
    assert chart.locator(".diff-band").count() == 1 and chart.locator(".diff-line").count() == 2
    assert chart.locator(".diff-out").count() >= 1 and "outside" in chart.locator("figcaption").inner_text()
    chart.locator(".diff-outs button").first.click()                         # to the first stretch outside
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.dual")
    # without a tolerance: the difference alone, no band, nothing outside
    pg.locator(".cmp-panel > .tol-fields .afield", has_text="Tolerance (±)").locator("input").fill("")
    pg.wait_for_function("!document.querySelector('.sim-row .sim-pass')", timeout=30000)
    pg.locator(".sim-row", has_text="Speed").first.click()
    pg.wait_for_function("document.querySelector('.diff-chart') && !document.querySelector('.diff-band')", timeout=20000)
