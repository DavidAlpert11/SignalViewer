"""M34 (the owner's review of 2026-11-16): the window back to the data.
FR1: the plots' own area (inside their axes, `.u-over`) as a share of the window, on the ArduPilot demo at
1440 x 900 with the Inspector closed - in English, in Hebrew and in dark; a plot with one line says its name once."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

# FR1 alone reaches 32 % (21 % before it); the rows above the plots are FR2's - with them the owner's 35 %
MIN_SHARE = 32.0

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
