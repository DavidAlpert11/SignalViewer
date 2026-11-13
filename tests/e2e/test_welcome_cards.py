"""W1 (2026-11-13): the welcome screen's example cards show a picture (per theme, language-neutral), the title
and line under it; 3 columns on a wide window, 2 at 1280, 1 on a narrow one; a missing picture falls back to the
icon card; the pictures are files (not inlined), loaded lazily, their place reserved."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401


def _cols(pg):
    return pg.evaluate("getComputedStyle(document.querySelector('.examples-line')).gridTemplateColumns.split(' ').length")


def _pictures_loaded(pg):
    pg.wait_for_function("""[...document.querySelectorAll('.ex-card.pic img')].every((i) => i.complete && i.naturalWidth === 480)""")


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_cards_show_their_picture_in_each_theme(pg, theme):
    pg.evaluate(f"window.__sv.setState({{ theme: '{theme}' }})")
    pg.wait_for_selector(".ex-card.pic img")
    srcs = pg.eval_on_selector_all(".ex-card.pic img", "els => els.map((e) => e.getAttribute('src'))")
    assert srcs and all(s.startswith("examples/") and s.endswith(f".{theme}.webp") for s in srcs)   # files, not data: URIs
    for img in pg.locator(".ex-card.pic img").all():
        img.scroll_into_view_if_needed()
    _pictures_loaded(pg)
    assert all(pg.eval_on_selector_all(".ex-card.pic img", "els => els.map((e) => e.loading === 'lazy' && !!e.alt)"))
    # the title stays real text in the button (the other e2e files click the cards by it)
    assert pg.locator(".examples-line button", has_text="a drone flight").count() == 1


def test_columns_follow_the_window(pg):
    pg.set_viewport_size({"width": 1920, "height": 1080})
    pg.wait_for_selector(".ex-card.pic")
    assert _cols(pg) == 3
    pg.set_viewport_size({"width": 1280, "height": 720})
    pg.wait_for_function("getComputedStyle(document.querySelector('.examples-line')).gridTemplateColumns.split(' ').length === 2")
    pg.set_viewport_size({"width": 700, "height": 720})
    pg.wait_for_function("getComputedStyle(document.querySelector('.examples-line')).gridTemplateColumns.split(' ').length === 1")


def test_hebrew_is_mirrored_and_pictures_stay(pg):
    pg.evaluate("window.__sv.setState({ lang: 'he' })")
    pg.wait_for_function("document.documentElement.dir === 'rtl'")
    first = pg.locator(".ex-card").first.bounding_box()
    second = pg.locator(".ex-card").nth(1).bounding_box()
    assert first["x"] > second["x"]                                    # the first card on the right
    assert pg.locator(".ex-card.pic img").count() >= 6
    assert pg.eval_on_selector_all(".ex-card.pic img", "els => els.every((e) => /[\\u0590-\\u05FF]/.test(e.alt))")


def test_a_missing_picture_falls_back_to_the_icon_card(pg):
    pg.route("**/examples/flight.*.webp", lambda r: r.fulfill(status=404, body=""))
    pg.reload()
    pg.wait_for_selector(".ex-card[data-example='flight']")
    pg.wait_for_selector(".ex-card[data-example='flight']:not(.pic) > svg")
    assert pg.locator(".ex-card[data-example='car'].pic img").count() == 1


def test_the_picture_space_is_reserved(pg):
    pg.wait_for_selector(".ex-card.pic .ex-pic")
    h = pg.eval_on_selector(".ex-card.pic .ex-pic", "e => { const r = e.getBoundingClientRect(); return r.height / r.width; }")
    assert abs(h - 9 / 16) < 0.02


def test_every_area_has_its_demo(pg):
    """Review (owner, 2026-11-13: a clear demo for everything): the cards grouped by area; the sweep card opens
    the table with its question answered, the Fleet card the fleet on its vibration question."""
    pg.wait_for_selector(".examples-group")
    groups = pg.locator(".examples-group").evaluate_all("els => els.map((g) => [...g.querySelectorAll('.ex-card')].map((c) => c.dataset.example))")
    assert groups == [["flight", "twoFlights", "car", "ardupilot", "simVsFlight", "investigate"],
                      ["sweepTable", "commonGains", "smartSweepDemo"], ["fleet"]], groups
    pg.locator(".ex-card[data-example='sweepTable']").click()
    pg.wait_for_function("window.__sv.state().area === 'sweeps'")
    pg.wait_for_selector(".sw-step-btn[data-step='results']")
    pg.wait_for_function("window.__svSweeps.idle() && window.__svSweeps.doc()?.view.step === 'results'")
    pg.locator(".status", has_text="12 of 45 sets hold").wait_for()                   # the question came with it
    pg.click(".areas .area-btn:has-text('Recordings')")
    pg.locator(".ex-card[data-example='fleet']").click()
    pg.wait_for_function("window.__sv.state().area === 'fleet'")
    pg.wait_for_selector(".fleet-trend circle.over", timeout=60000)                 # the worn motor's flight, over the limit
