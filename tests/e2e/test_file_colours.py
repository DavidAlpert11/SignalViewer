"""M34 FR4: one colour rule for two runs - the same signal from several files in one plot takes each file's colour
(A blue, B rose), in every way such a plot is made; a colour set by hand stays."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, open_example, pg, sig  # noqa: E402,F401

LINES = """() => { const s = window.__sv.state(); const col = Object.fromEntries(s.runs.map((r) => [r.id, r.color.toUpperCase()]));
  return s.ws.tabs.flatMap((t) => t.plots.flatMap((p) => p.signals.map((x) => [x.sig, x.color.toUpperCase(), col[x.sig.split('/')[0]]]))); }"""


def test_a_simulation_against_its_flight_in_the_files_colours(pg):
    pg.locator(".ex-card").first.wait_for()
    open_example(pg, "simVsFlight")                                            # CC16: Help -> Examples
    pg.wait_for_selector(".demo-guide[data-demo='simVsFlight']", timeout=30000)
    lines = pg.evaluate(LINES)
    assert len(lines) >= 10
    for sigid, color, file_color in lines:
        assert color == file_color, (sigid, color, file_color)            # every line of A blue, of B rose
    # the chips' A / B badges are drawn in the same two colours as the lines
    tags = pg.eval_on_selector_all(".plot .chip .file-tag", "els => els.map((e) => getComputedStyle(e).getPropertyValue('--tag').trim().toUpperCase())")
    assert tags and set(tags) == {c for _, _, c in lines}


def test_a_hand_colour_stays_when_its_namesake_joins(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    pg.evaluate("window.__sv.setState({ linkRuns: false })")
    sig(pg, "Speed", 0).click()
    pg.wait_for_selector(".plot .chip")
    pg.evaluate("""window.__sv.state().commit((w) => { w.tabs[0].plots[0].signals[0].color = '#123456'; return w; })""")
    sig(pg, "Speed", 1).click()                                     # the same signal of file B joins
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 2")
    lines = pg.evaluate(LINES)
    assert lines[0][1] == "#123456"                                       # set by hand: kept
    assert lines[1][1] == lines[1][2]                                     # the newcomer: its file's colour
