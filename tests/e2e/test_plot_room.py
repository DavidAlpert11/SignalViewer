"""M34 (the owner's review of 2026-11-16): the window back to the data.
FR1: the plots' own area (inside their axes, `.u-over`) as a share of the window, on the ArduPilot demo at
1440 x 900 with the Inspector closed - in English, in Hebrew and in dark; a plot with one line says its name once.
FR2: at most two rows above the plots (a demo's line, the run at a glance, the flags and the mode band); the first
curve within 200 px of the window's top; a demo's line does not keep offering what was just done."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

# FR1 alone reached 32 % (21 % before it); with FR2's rows above the plots 36 % - the owner's line is 35 %
MIN_SHARE = 35.0
TOP_MAX = 200          # FR2: the first curve starts no lower than this from the top of the window

AREA = """() => { const o = [...document.querySelectorAll('.plot .u-over')].map((e) => e.getBoundingClientRect()).filter((r) => r.width > 0);
  return { n: o.length, share: 100 * o.reduce((s, r) => s + r.width * r.height, 0) / (innerWidth * innerHeight),
           top: Math.min(...o.map((r) => r.top)) }; }"""


def ardupilot_demo(pg):
    pg.locator(".examples-line button", has_text="ArduPilot").click()
    pg.wait_for_function("window.__sv.state().runs.some((r) => r.format === 'bin')")
    pg.wait_for_function("document.querySelectorAll('.plot .u-over').length === 3 && !!window.__sv.state().demoGuide")
    assert not S(pg, "s.inspectorOpen")


def settled(pg):
    """The share once the layout stopped changing (fonts, the strip's rows arriving)."""
    last = None
    for _ in range(40):
        a = pg.evaluate(AREA)
        if last and abs(a["share"] - last["share"]) < 0.01:
            return a
        last = a
        pg.wait_for_timeout(250)
    return last


@pytest.mark.parametrize("lang,theme", [("en", "light"), ("he", "light"), ("en", "dark"), ("he", "dark")])
def test_the_plots_take_the_window(pg, lang, theme):
    ardupilot_demo(pg)
    pg.evaluate(f"window.__sv.setState({{ lang: '{lang}', theme: '{theme}' }})")
    pg.wait_for_function(f"document.documentElement.dir === '{'rtl' if lang == 'he' else 'ltr'}'")
    a = settled(pg)
    assert a["n"] == 3
    assert a["share"] >= MIN_SHARE, a
    assert a["top"] <= TOP_MAX, a
    # the head and the legend share one row: each card's head is one line high
    heads = pg.eval_on_selector_all(".plot .plot-head", "els => els.map((e) => e.getBoundingClientRect().height)")
    assert all(h <= 30 for h in heads), heads
    assert pg.locator(".plot-eyebrow, .pe-active").count() == 0          # no "PLOT n · ACTIVE"; the ring says it
    assert pg.locator(".plot.active").count() == 1


def test_a_plot_with_one_line_says_its_name_once(pg):
    open_files(pg, "run_a.csv")
    assert pg.locator(".plot-title").first.inner_text() == "Plot 1"      # an empty plot keeps its name
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .chip")
    assert pg.locator(".plot .plot-title").count() == 0                  # the chip says "Speed"; no "Plot 1" beside it
    sig(pg, "RPM").click()
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 2")
    assert pg.locator(".plot-title").first.inner_text() == "Plot 1"
    pg.locator(".plot .chip .rm").last.click()                           # back to one line: rename it from the menu
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 1")
    pg.locator(".plot .plot-more").first.click()
    pg.locator(".menu.ctx button", has_text="Rename the plot").click()
    pg.fill(".plot-head input", "Engine"); pg.press(".plot-head input", "Enter")
    assert pg.locator(".plot-title").first.inner_text() == "Engine"      # a name the user gave is shown
    assert S(pg, "s.ws.tabs[0].plots[0].title") == "Engine"


ROWS = """() => { const vis = (e) => e && e.getBoundingClientRect().height > 0;
  const tops = [...document.querySelectorAll('.demo-guide, .ov-strip .ov-head, .ov-strip .ov-track.ov-row, .ov-strip .ov-rows > .ov-track.ov-flags, .stage > .tab-band .band-row')]
    .filter(vis).map((e) => Math.round(e.getBoundingClientRect().top / 6));
  return new Set(tops).size; }"""


def test_two_rows_above_the_plots_and_the_demo_line_moves_on(pg):
    ardupilot_demo(pg)
    pg.wait_for_selector(".ov-strip .ov-track.ov-row")
    a = settled(pg)
    assert a["top"] <= TOP_MAX, a
    assert pg.evaluate(ROWS) == 2                                        # the demo's line + one track
    # the flags are on the mode lane, not on a row of their own - and still a click away
    assert pg.locator(".ov-row .ov-flags.over .ov-flag").count() > 0
    assert pg.locator(".ov-rows > .ov-flags").count() == 0
    pg.locator(".ov-flags.over .ov-flag").last.click()
    pg.wait_for_function("window.__sv.state().cursor.on")
    pg.locator(".ov-row .ov-phase", has_text="AUTO").click()             # the lane's own stretches too
    pg.wait_for_function("!!window.__sv.state().stripSel")
    pg.keyboard.press("Escape")
    # its button pressed: the line no longer offers it; the run at a glance has its row back
    assert pg.locator(".demo-guide button", has_text="Open Checks").count() == 1
    pg.locator(".demo-guide button", has_text="Open Checks").click()
    pg.wait_for_function("window.__sv.state().panel === 'log'")
    # UX5.4: the line moves on to the next step (the report) - it never offers again what was just done
    pg.wait_for_selector(".demo-guide[data-step='2'] .demo-next:has-text('Write the report')")
    assert pg.locator("button", has_text="Open Checks").count() == 0
    pg.click(".demo-guide button[aria-label='Close']")
    pg.wait_for_function("!document.querySelector('.demo-guide')")
    pg.wait_for_selector(".ov-strip .ov-head .ov-gl")
    assert pg.evaluate(ROWS) == 2                                        # the glance + one track
    assert settled(pg)["top"] <= TOP_MAX


def test_a_demo_line_with_a_next_step_changes_to_it(pg):
    pg.locator(".examples-line button", has_text="Find out what went wrong").click()
    pg.wait_for_selector(".demo-guide[data-demo='investigate'] .btn.primary", timeout=30000)
    before = pg.locator(".demo-guide .demo-text").inner_text()
    pg.click(".demo-guide .btn.primary")
    pg.wait_for_function("window.__sv.state().cursor.dual")
    pg.wait_for_selector(".demo-guide[data-step='2']")
    assert pg.locator(".demo-guide .btn.primary").inner_text() == "What changed?"   # not the same click again
    assert pg.locator(".demo-guide .demo-text").inner_text() != before   # ... the line says what comes next
    pg.click(".demo-guide .btn.primary")                                 # UX5.4: its second step asks the question
    pg.wait_for_selector(".demo-guide[data-step='done']")
    pg.wait_for_function("!!window.__sv.state().whatChanged")


def test_a_plain_file_and_a_session_with_two_lanes_keep_their_rows(pg):
    """Old sessions open unchanged: the strip's saved rows are all shown; a file with no lane keeps the flags' row."""
    open_files(pg, "run_a.csv")
    pg.wait_for_selector(".ov-strip")
    assert pg.locator(".ov-flags.over").count() == 0
    pg.evaluate("window.__sv.state().commit((w) => { w.overviewRows = [{ kind: 'state', name: 'Gear' }, { kind: 'state', name: 'Gear' }]; return w; })")
    pg.wait_for_function("document.querySelectorAll('.ov-strip .ov-track.ov-row').length === 2")
    assert pg.locator(".ov-row .ov-flags.over").count() == 1             # on the first lane only
