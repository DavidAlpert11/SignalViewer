"""T23: with two cursors a note covers the time between them - a shaded span on the time plots,
"a – b" in the Inspector, and in the report."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def test_note_over_a_time_range(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    pg.evaluate("window.__sv.setState({ cursor: { on: true, dual: true, t1: 22, t2: 8, active: 2 } })")
    pg.keyboard.press("n")
    assert "From 8.000000 to 22.00000 s" in pg.locator(".dialog").inner_text()
    pg.locator(".dialog textarea, .dialog input").first.fill("climb")
    pg.locator(".dialog .btn.primary").click()
    pg.wait_for_function("(window.__sv.state().ws.notes || []).some(n => n.text === 'climb' && n.t === 8 && n.t2 === 22)")
    pg.evaluate("window.__sv.setState({ inspectorOpen: true })")
    assert "8 – 22" in pg.locator(".notes-list li").first.inner_text().replace("\u2009", " ")
    # the span is shaded: a pixel inside it has the note colour mixed in, one outside does not
    shade = """([f]) => { const u = document.querySelector('.plot .u-over').getBoundingClientRect();
      const c = document.querySelector('.plot canvas'); const r = c.getBoundingClientRect(); const k = c.width / r.width;
      const x = (u.left - r.left + u.width * f) * k, y = (u.top - r.top + 6) * k;
      const d = c.getContext('2d').getImageData(Math.round(x), Math.round(y), 1, 1).data; return [d[0], d[1], d[2]]; }"""
    inside, outside = pg.evaluate(shade, [15 / 30]), pg.evaluate(shade, [27 / 30])
    assert inside != outside and inside[2] >= inside[0], (inside, outside)
    # one cursor: a note at one moment, as before
    pg.evaluate("window.__sv.setState({ cursor: { on: true, dual: false, t1: 5, t2: null, active: 1 } })")
    pg.keyboard.press("n")
    pg.locator(".dialog textarea, .dialog input").first.fill("start")
    pg.locator(".dialog .btn.primary").click()
    pg.wait_for_function("(window.__sv.state().ws.notes || []).some(n => n.text === 'start' && n.t === 5 && n.t2 === undefined)")
