"""
D4 (2026-11-15): the Compare panel shows, for each file against the baseline file, the parameters that
differ (F3's one source - here the number in each file's name), read-only, following the panel's choice.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import pg  # noqa: E402,F401


def test_parameters_that_differ_from_the_baseline(pg):
    pg.locator(".examples-line button", has_text="three car runs").click()
    pg.wait_for_function("document.querySelectorAll('.run-head').length === 3")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row", timeout=30000)
    cards = pg.locator(".cmp-params [data-param-diff]")
    pg.wait_for_function("document.querySelectorAll('.cmp-params [data-param-diff]').length === 2", timeout=20000)
    # each other file against the baseline (run_012.csv): its file-name number differs
    for i in range(2):
        c = cards.nth(i)
        assert int(c.get_attribute("data-differ")) >= 1
        assert "differ from run_012.csv" in c.inner_text()
        assert c.locator("table.data tbody tr").count() == int(c.get_attribute("data-differ"))
    # the mean of the runs as the baseline: no file to compare against, the section goes
    pg.locator(".cmp-panel select").first.select_option("mean")
    pg.wait_for_selector(".cmp-params", state="detached", timeout=5000)
