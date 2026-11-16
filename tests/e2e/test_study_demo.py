"""W18 (2026-11-13): the smart-sweep demo - the welcome card opens it; Next round twice: the convergence chart
has two points and the run counter is right (768 start runs + 20 candidates x 12 runs)."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401


def test_next_round_twice(pg):
    pg.locator(".ex-card[data-example='smartSweepDemo']").click()
    pg.wait_for_selector(".dm-strip")
    if pg.locator(".dm-reset").is_enabled():                     # a demo left by an earlier run: start again
        pg.locator(".dm-reset").click()
        pg.wait_for_function("document.querySelector('.dm-strip').dataset.round === '0'")
    for k, runs in ((1, 768), (2, 1008)):
        pg.locator(".dm-next").click()
        pg.wait_for_function(f"document.querySelector('.dm-chart').dataset.points === '{k}' && "
                             "document.querySelector('[data-shot=demo]').dataset.settled === '1'", timeout=120000)
        assert pg.locator(".dm-strip").get_attribute("data-done") == str(runs)
    assert pg.locator(".dm-chart .dm-pt").count() == 2
    assert "full-grid optimum" in pg.locator(".dm-sentence").inner_text()
    assert pg.locator(".cp-space .cp-best").count() == 1


@pytest.mark.parametrize("lang", ["en", "he"])
def test_run_until_converged_writes_the_answer(pg, lang):
    """M34 FR6: at convergence the loop's page writes the best set in words - Kp = ..., Ki = ..., Kd = ... and its value."""
    import re
    if lang == "he":
        pg.evaluate("window.__sv.setState({ lang: 'he' })")
    pg.locator(".ex-card[data-example='smartSweepDemo']").click()
    pg.wait_for_selector(".dm-strip")
    if pg.locator(".dm-reset").is_enabled():
        pg.locator(".dm-reset").click()
        pg.wait_for_function("document.querySelector('.dm-strip').dataset.round === '0'")
    pg.locator(".dm-run").click()
    pg.wait_for_selector(".lp-answer", timeout=300000)
    text = pg.locator(".lp-answer").inner_text()
    for gain in ("Kp", "Ki", "Kd"):
        assert re.search(rf"\b{gain}\w* = -?[0-9.]+", text, re.I), text
    assert re.search(r"[0-9]", text.split("·")[-1]), text                  # and its value
