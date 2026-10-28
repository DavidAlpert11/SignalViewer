"""Investigation step 4 on the Investigate demo (examples/investigate, a known answer): what changed
first around the roll error, and the lag between motor 3 and the roll.

    python -m pytest tests/e2e/test_what_changed.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "investigate")


@pytest.fixture(autouse=True)
def _demo(pg):
    for f in ("heavy_payload.csv", "light_payload.csv"):
        dst = os.path.join(pg.env["data"], f)
        if not os.path.exists(dst):
            shutil.copy(os.path.join(DEMO, f), dst)
    yield


def _around_first_error(pg):
    open_files(pg, "heavy_payload.csv")
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()   # Roll, not DesRoll
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.some(x => x.sig.endsWith('/Roll'))")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-changed")
    pg.wait_for_selector(".wc-section")
    pg.select_option(".wc-scope", "all")
    pg.wait_for_selector(".wc-row")


def test_what_changed_first_finds_the_built_order(pg):
    _around_first_error(pg)
    names = [n.strip() for n in pg.locator(".wc-row .wc-name").all_inner_texts()]
    assert names[0] == "Wind" and names[1] == "Vibe_Z"
    assert names.index("Motor3") < names.index("Roll")
    assert "not proof of cause" in pg.inner_text(".wc-warn")
    assert S(pg, "Object.keys(s.changeMarks || {}).length") >= 4           # the dashed lines
    pg.locator(".wc-head .iconbtn").click()                                 # closing takes them away
    pg.wait_for_function("window.__sv.state().changeMarks === null")


def test_lag_motor3_to_roll_and_show_aligned(pg):
    _around_first_error(pg)
    pg.locator(".wc-row", has_text="Motor3").locator("input[type=checkbox]").check()
    pg.locator(".wc-row", has_text="Roll").first.locator("input[type=checkbox]").check()
    pg.click(".wc-lag")
    pg.wait_for_selector(".wc-lag-out p")
    text = pg.inner_text(".wc-lag-out p")
    assert "follows Motor3 by" in text
    ms = float(text.split("by ")[1].split(" ms")[0])
    assert 80 <= ms <= 180
    pg.click(".wc-align")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.some(x => x.sig.endsWith('/Roll') && x.tOffset < 0)")
    assert S(pg, "s.ws.tabs[0].plots[0].signals.some(x => x.sig.endsWith('/Motor3'))")


def test_by_default_every_signal_of_the_events_file_and_the_other_run_beside_it(pg):
    """Without choosing a scope: all of heavy_payload's signals (Wind is not on any plot), only
    that file in the list, and under each the same signal in the light run - Roll did not change there."""
    open_files(pg, "heavy_payload.csv", "light_payload.csv")
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).nth(1).click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 2")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-bar:not([hidden]) .sel-changed")
    pg.wait_for_selector(".wc-row")
    assert pg.input_value(".wc-scope") == "file" and "heavy_payload" in pg.locator(".wc-scope option").first.inner_text()
    names = [n.strip() for n in pg.locator(".wc-row .wc-name").all_inner_texts()]
    assert names[0] == "Wind" and names.index("Motor3") < names.index("Roll") and len(names) == len(set(names))
    pg.wait_for_selector(".wc-other")
    roll = pg.locator(".wc-row").filter(has=pg.locator(".wc-name", has_text="Roll")).first
    assert "light_payload" in roll.locator(".wc-other").inner_text() and roll.locator(".wc-other.same").count() == 1
    wind = pg.locator(".wc-row").filter(has=pg.locator(".wc-name", has_text="Wind")).first
    assert wind.locator(".wc-other.same").count() == 0                     # the gusts are in both runs


def test_find_similar_takes_the_signal_that_changed_not_the_active_plots(pg):
    from test_features import set_layout
    open_files(pg, "heavy_payload.csv")
    set_layout(pg, 2, 1)
    for i, n in ((0, "Alt"), (1, "Roll")):
        pg.locator(".plot").nth(i).click(position={"x": 200, "y": 10})
        pg.locator(".sig").filter(has=pg.get_by_text(n, exact=True)).first.click()
        pg.wait_for_function(f"window.__sv.state().ws.tabs[0].plots[{i}].signals.some(x => x.sig.endsWith('/{n}'))")
    pg.locator(".plot").nth(0).click(position={"x": 200, "y": 10})            # Alt's plot is the active one
    pg.wait_for_function("window.__sv.state().ws.tabs[0].active === 0")
    pg.locator(".ov-flag").first.click()                                   # the first flag: cursors around it, zoomed
    pg.wait_for_selector(".sel-bar:not([hidden])")
    assert S(pg, "s.ws.tabs[0].active") == 0 and S(pg, "s.ws.tabs[0].plots[0].signals.map(x => x.sig.split('/')[1])") == ["Alt"]
    pg.locator(".sel-bar:not([hidden]) .sel-find").first.click()
    pg.wait_for_selector(".cond-editor")
    pg.wait_for_function("/^Roll > /.test(document.querySelector(\".cond-editor [aria-label='When']\").value || document.querySelector(\".cond-editor [aria-label='When']\").textContent)")
    pg.wait_for_function("/3 stretches/.test(document.querySelector('.cond-preview').textContent)")


def test_a_long_list_filter_take_out_close_a_group(pg):
    """A flight log gives dozens of rows: a filter, rows and whole groups taken out (their dashed
    lines go too), a group closed - and everything brought back."""
    _around_first_error(pg)
    total = pg.locator(".wc-row").count()
    marks = S(pg, "Object.keys(s.changeMarks || {}).length")
    pg.fill(".wc-filter", "motor")
    pg.wait_for_function("[...document.querySelectorAll('.wc-row .wc-name')].every(n => /Motor/.test(n.textContent))")
    assert pg.locator(".wc-row").count() >= 2 and S(pg, "Object.keys(s.changeMarks || {}).length") == pg.locator(".wc-row").count()
    pg.fill(".wc-filter", "")
    pg.wait_for_function(f"document.querySelectorAll('.wc-row').length === {total}")
    pg.locator(".wc-row").filter(has=pg.locator(".wc-name", has_text="Wind")).first.locator(".wc-hide").click(force=True)
    pg.wait_for_function(f"document.querySelectorAll('.wc-row').length === {total - 1}")
    assert S(pg, "Object.keys(s.changeMarks || {}).length") == marks - 1
    head = pg.locator(".wc-ghead").first                                    # a group: closed, then taken out
    n = int(head.inner_text().split("▾")[1].split()[0])
    head.locator(".wc-gtoggle").click()
    pg.wait_for_function(f"document.querySelectorAll('.wc-row').length === {total - 1 - n}")
    head.locator(".wc-ghide").click()
    pg.wait_for_selector(".wc-unhide")
    pg.click(".wc-unhide")
    pg.wait_for_function(f"document.querySelectorAll('.wc-row').length >= {total - n}")
    assert S(pg, "Object.keys(s.changeMarks || {}).length") == marks


def test_a_click_on_a_candidate_opens_it_in_a_plot_of_its_own(pg):
    """Not squeezed into the active plot (Motor3 at 2000 beside a roll of 2 degrees): its own plot;
    Ctrl+click still adds it to the active one."""
    _around_first_error(pg)
    before = S(pg, "s.ws.tabs[0].plots.length")
    pg.locator(".wc-row .wc-name", has_text="Motor3").first.click()
    pg.wait_for_function(f"window.__sv.state().ws.tabs[0].plots.filter(p => p.signals.length).length === {before + 1}")
    p = S(pg, "s.ws.tabs[0].plots[s.ws.tabs[0].active].signals.map(x => x.sig.split('/')[1])")
    assert p == ["Motor3"]
    pg.locator(".wc-row .wc-name", has_text="Wind").first.click(modifiers=["Control"])
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[window.__sv.state().ws.tabs[0].active].signals.some(x => x.sig.endsWith('/Wind'))")
    assert S(pg, "s.ws.tabs[0].plots[s.ws.tabs[0].active].signals.length") == 2


def test_steps_so_far_grouped_by_kind_ticked_a_group_at_a_time(pg):
    from test_conditions import _new
    _around_first_error(pg)                                                 # a "what changed first" step
    pg.locator(".wc-head .iconbtn").click()
    _new(pg, "Roll error", "abs(Roll - DesRoll) > 5")
    pg.click(".cond-save")
    pg.wait_for_function("window.__sv.state().journal.length >= 2")
    pg.click(".jr-toggle")
    pg.wait_for_selector(".jr-group")
    kinds = pg.locator(".jr-group").evaluate_all("gs => gs.map(g => g.dataset.kind)")
    assert kinds == ["condition", "changed"]
    pg.locator(".jr-group[data-kind='changed'] .jr-ghead input").uncheck()  # the whole group out of the report
    pg.wait_for_function("window.__sv.state().journal.filter(j => j.kind === 'changed').every(j => !j.include)")
    assert S(pg, "s.journal.filter(j => j.kind === 'condition').every(j => j.include)")
    pg.locator(".jr-group[data-kind='condition'] .jr-gtoggle").click()     # closed: its steps hidden, still in
    assert pg.locator(".jr-group[data-kind='condition'] .jr-list").count() == 0
    pg.locator(".jr-group[data-kind='changed'] .jr-gremove").click()        # removed
    pg.wait_for_function("!window.__sv.state().journal.some(j => j.kind === 'changed')")


def test_a_long_span_reads_the_usual_level_inside_the_data_and_an_early_one_says_there_is_no_room(pg):
    open_files(pg, "heavy_payload.csv")
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 20, t2: 45, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-bar:not([hidden]) .sel-changed")
    pg.wait_for_selector(".wc-row")                                  # the first gust is found
    assert "-" not in pg.inner_text(".wc-section .hint").split("read from")[1].split("–")[0]
    pg.locator(".wc-head .iconbtn").click()
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 0, t2: 1, active: 1 } })")
    pg.click(".sel-bar:not([hidden]) .sel-changed")
    pg.wait_for_selector(".wc-noroom")
    assert pg.locator(".wc-row").count() == 0
