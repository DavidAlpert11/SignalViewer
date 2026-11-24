"""W1 (2026-11-13): the welcome screen's example cards show a picture (per theme, language-neutral), the title
and line under it; 3 columns on a wide window, 2 at 1280, 1 on a narrow one; a missing picture falls back to the
icon card; the pictures are files (not inlined), loaded lazily, their place reserved."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg, open_example  # noqa: E402,F401


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
    assert pg.locator(".examples-line button", has_text="Find out what went wrong").count() == 1


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
    pg.route("**/examples/twoFlights.*.webp", lambda r: r.fulfill(status=404, body=""))
    pg.reload()
    pg.wait_for_selector(".ex-card[data-example='twoFlights']")
    pg.wait_for_selector(".ex-card[data-example='twoFlights']:not(.pic) > svg")
    assert pg.locator(".ex-card[data-example='ardupilot'].pic img").count() == 1


def test_the_picture_space_is_reserved(pg):
    pg.wait_for_selector(".ex-card.pic .ex-pic")
    h = pg.eval_on_selector(".ex-card.pic .ex-pic", "e => { const r = e.getBoundingClientRect(); return r.height / r.width; }")
    assert abs(h - 9 / 16) < 0.02


def test_every_area_has_its_demo(pg):
    """Review (owner, 2026-11-13: a clear demo for everything): the cards grouped by area; the sweep card opens
    the table with its question answered. FR11 (owner, 2026-11-16): six cards, one of them Sweeps'; the others in
    Help -> Examples."""
    pg.wait_for_selector(".examples-group")
    groups = pg.locator(".examples-group").evaluate_all("els => els.map((g) => [...g.querySelectorAll('.ex-card')].map((c) => c.dataset.example))")
    assert groups == [["ardupilot", "investigate", "simVsFlight", "twoFlights", "folderOfFlights"], ["smartSweepDemo"]], groups
    assert "Help → Examples" in pg.locator(".examples-more").inner_text()
    pg.locator(".topbar .menubar-btn", has_text="Help").click()          # every example is there, the six too
    pg.locator(".menu.ctx button", has_text="Examples").click()
    assert pg.locator(".menu.ctx.sub button").count() == 15                # 1.32.0: + the serial link (MSG1), messages to signals, raw NMEA (MSG2)
    pg.keyboard.press("Escape")
    open_example(pg, "sweepTable")
    pg.wait_for_function("window.__sv.state().area === 'sweeps'")
    pg.wait_for_selector(".sw-step-btn[data-step='results']")
    pg.wait_for_function("window.__svSweeps.idle() && window.__svSweeps.doc()?.view.step === 'results'")
    pg.locator(".status", has_text="12 of 45 sets hold").wait_for()                   # the question came with it


def test_the_start_page_opens_over_open_files(pg):
    """Owner (2026-11-16): after one example was open there was no way back to the others. The brand (and Ctrl+K)
    opens the start page over the open files; Back returns to them; an example opened from it replaces the page."""
    open_example(pg, "car")
    pg.wait_for_function("window.__sv.state().runs.length > 0")
    pg.wait_for_selector(".ex-card", state="detached")
    pg.click(".topbar .brand")
    pg.wait_for_selector(".ex-card[data-example='ardupilot']")
    pg.click(".welcome-back")
    pg.wait_for_selector(".ex-card", state="detached")
    assert pg.evaluate("window.__sv.state().runs.length") > 0          # the files stayed open
    pg.click(".topbar .brand")
    open_example(pg, "bench")
    pg.wait_for_selector(".ex-card", state="detached")
    pg.wait_for_function("window.__sv.state().startOpen === false")


def _open_demo(pg, ex):
    open_example(pg, ex)
    pg.wait_for_selector(f".demo-guide[data-demo='{ex}']", timeout=30000)


def test_each_demo_opens_what_its_card_promises(pg):
    """RV5 (review 2026-11-16, B4 / B5 / §4.4 / §4.8): each demo opens what its card says, with one line of what to do
    next and the click that does it."""
    # the plain CSV flight: its own position on the map, not a view made for another format's logs
    _open_demo(pg, "flight")
    tabs = pg.evaluate("window.__sv.state().ws.tabs.map((t) => t.name)")
    assert not any("ArduPilot" in n for n in tabs), tabs
    assert pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].mode") == "geo"
    pg.click(".demo-guide button[aria-label='Close']")
    assert pg.locator(".demo-guide").count() == 0
    # two flights: both tracks on one map, the first tab; then Compare
    _close_all(pg)
    _open_demo(pg, "twoFlights")
    first = pg.evaluate("(() => { const t = window.__sv.state().ws.tabs[0]; return { mode: t.plots[0].mode, n: (t.plots[0].objects || []).length,"
                        " runs: [...new Set(t.plots[0].objects.map((o) => o.lat.split('/')[0]))].length }; })()")
    assert first == {"mode": "geo", "n": 2, "runs": 2}, first
    pg.click(".demo-guide .btn.primary")
    pg.wait_for_function("window.__sv.state().panel === 'compare'")


def test_sim_demo_aligns_in_one_click_and_investigate_puts_the_cursors(pg):
    _open_demo(pg, "simVsFlight")
    pg.click(".demo-guide .btn.primary")                        # Align time
    pg.wait_for_function("window.__sv.state().runs.some((r) => Math.abs((r.timeOffset || 0) + 104.37) < 0.05)", timeout=30000)
    pg.locator(".demo-guide", has_text="Aligned").wait_for()
    _close_all(pg)
    _open_demo(pg, "investigate")
    pg.click(".demo-guide .btn.primary")                        # the cursors around the first bump
    c = pg.evaluate("window.__sv.state().cursor")
    assert c["on"] and c["dual"] and (c["t1"], c["t2"]) == (38.4, 39.3)
    pg.locator(".inv-wc").wait_for()                            # What changed? is one click away


def _close_all(pg):
    pg.evaluate("""async () => { for (const r of await (await fetch('/api/runs')).json())
      if (r.format !== 'derived') await fetch('/api/runs/' + r.id, { method: 'DELETE' });
      window.__sv.setState({ runs: [] }); }""")
    pg.wait_for_selector(".ex-card[data-example='ardupilot']")


def test_a_demo_leads_on_to_its_report(pg):
    """UX5.4 (owner, 2026-11-23: load, then lead the user): the car demo's steps - Compare, then the report the app
    writes from the parts that fit; *Show the result* does what is left, and the line ends on the Report's page."""
    _open_demo(pg, "car")
    assert pg.locator(".demo-guide .demo-count").inner_text() == "1/2"
    pg.click(".demo-guide .demo-next")                                  # Rank the differences
    pg.wait_for_function("window.__sv.state().panel === 'compare'")
    pg.wait_for_selector(".demo-guide[data-step='2'] .demo-next")
    pg.click(".demo-guide .demo-next")                                  # Write the report
    pg.wait_for_function("window.__sv.state().panel === 'report' && !!window.__sv.state().ws.report?.doc?.text")
    pg.wait_for_selector(".rd .demo-guide[data-step='done']")
    pg.evaluate("window.__sv.setState({ panel: null })")
    _close_all(pg)
    _open_demo(pg, "flight")
    assert pg.locator(".demo-guide .demo-count").inner_text() == "1/3"
    pg.click(".demo-guide .demo-finish")                                # Show the result: every step left
    pg.wait_for_selector(".rd .demo-guide[data-step='done']", timeout=30000)
    assert not pg.evaluate("window.__sv.state().playing")


def test_a_step_done_by_hand_moves_the_line_on(pg):
    """Review 2026-11-24 (#4): the line never offers what is already done - Checks opened from the rail moves the
    ArduPilot demo's line to its next step (the report), as its own button would."""
    _open_demo(pg, "ardupilot")
    assert pg.locator(".demo-guide .demo-next").inner_text() == "Open Checks"
    pg.click("nav.rail button[aria-label='Checks']")
    pg.wait_for_selector(".demo-guide[data-step='2'] .demo-next:has-text('Write the report')")
    pg.click("nav.rail button[aria-label='Report']")                   # the Report opened by hand, nothing written yet:
    pg.wait_for_selector(".rd .demo-guide[data-step='2'] .demo-next")  # ... its button still writes the report
    pg.click(".rd .demo-guide .demo-next")
    pg.wait_for_selector(".rd .demo-guide[data-step='done']")
