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


def _all_open(pg, order="time"):
    """Q130: the list is clusters, only the likeliest open: by time and every cluster open, so the rows
    read as the time-ordered list they were (names grouped by prefix are opened too)."""
    pg.select_option(".wc-order", order)
    for _ in range(60):
        closed = pg.locator(".wc-chead[aria-expanded='false'], .wc-ptoggle[aria-expanded='false']")
        if not closed.count():
            break
        closed.first.click()
    pg.wait_for_selector(".wc-row")


def _around_first_error(pg):
    open_files(pg, "heavy_payload.csv")
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()   # Roll, not DesRoll
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.some(x => x.sig.endsWith('/Roll'))")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-changed")
    pg.wait_for_selector(".wc-section")
    pg.select_option(".wc-scope", "all")
    pg.wait_for_selector(".wc-chead")
    _all_open(pg)


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
    pg.wait_for_selector(".wc-chead")
    _all_open(pg)
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
    head = pg.locator(".wc-cluster").first                                  # a cluster: closed, then taken out
    n = int(head.get_attribute("data-n"))
    head.locator(".wc-chead").click()
    pg.wait_for_function(f"document.querySelectorAll('.wc-row').length === {total - 1 - n}")
    head.locator(".wc-ghide").click()
    pg.wait_for_selector(".wc-unhide")
    pg.click(".wc-unhide")
    _all_open(pg)
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
    pg.wait_for_selector(".wc-cluster")                              # the first gust is found
    assert "-" not in pg.inner_text(".wc-section .hint").split("read from")[1].split("–")[0]
    pg.locator(".wc-head .iconbtn").click()
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 0, t2: 1, active: 1 } })")
    pg.click(".sel-bar:not([hidden]) .sel-changed")
    pg.wait_for_selector(".wc-noroom")
    assert pg.locator(".wc-row").count() == 0


def test_clusters_likeliest_first_a_plot_beside_each_and_a_tab(pg):
    """Q130-Q132: around the roll error the changes come as clusters, closed to one line each, the
    likeliest open; its plot has a line per signal; Open as a tab makes those signals' plots around the
    span; the keyboard walks the clusters; Add to the investigation writes a journal step."""
    open_files(pg, "heavy_payload.csv", "light_payload.csv")
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-bar:not([hidden]) .sel-changed")
    pg.wait_for_selector(".wc-cluster.open .wc-cplot svg")
    assert pg.locator(".wc-cluster").count() >= 2
    assert pg.locator(".wc-cluster.open").count() == 1
    first = pg.locator(".wc-cluster").first
    assert "Wind" in first.locator(".wc-chead").inner_text()                # the gust: likeliest, though both runs have it
    n = int(first.get_attribute("data-n"))
    assert int(first.locator(".wc-cplot svg").get_attribute("data-lines")) == n
    assert first.locator(".wc-why").first.get_attribute("title").count("\n") >= 5   # its parts
    # the keyboard: down to the next cluster, open it, Enter plots it
    first.locator(".wc-chead").focus()
    pg.keyboard.press("ArrowDown"); pg.keyboard.press("ArrowRight")
    pg.wait_for_function("document.querySelectorAll('.wc-cluster.open').length === 2")
    tabs = S(pg, "s.ws.tabs.length")
    first.locator(".wc-open-tab").click()
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length === {tabs + 1}")
    assert S(pg, "s.ws.tabs[s.ws.tabs.length - 1].plots.length") == n
    assert S(pg, "s.ws.tabs[s.ws.tabs.length - 1].plots[0].signals[0].sig").endswith("/Wind")
    assert S(pg, "s.cursor.t1") == 38.46 and S(pg, "s.cursor.t2") == 39.24        # the span
    r = S(pg, "Object.values(s.ranges).slice(-1)[0]")
    assert r[0] < 38.0 and r[1] > 39.24                                        # from before the gust
    journal = S(pg, "s.journal.length")
    first.locator(".wc-keep").click()
    pg.wait_for_function(f"window.__sv.state().journal.length === {journal + 1}")
    assert "Changes together" in S(pg, "s.journal[s.journal.length - 1].text")


def test_a_flight_log_leaves_out_the_clocks_and_constants_and_counts_them(pg):
    """Q133: in an ArduPilot .bin the GPS time and the constant signals tell nothing: out of the list,
    counted, and back on request; names grouped by their message (ATT.*)."""
    dst = os.path.join(pg.env["data"], "copter_flight.bin")
    if not os.path.exists(dst):
        shutil.copy(os.path.join(DEMO, "..", "copter_flight.bin"), dst)
    open_files(pg, "copter_flight.bin")
    pg.evaluate("""() => { const s = window.__sv.state(); const ws = structuredClone(s.ws);
        const id = s.runs.find(r => r.format !== 'derived').signals.find(x => x.id.endsWith('/ATT.Roll [deg]')).id;
        ws.tabs[0].plots[0].signals.push({ sig: id, color: '#3D8BFD', width: 1.5, scale: 1, offset: 0 });
        window.__sv.setState({ ws }); }""")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 120, t2: 121, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-bar:not([hidden]) .sel-changed")
    pg.wait_for_selector(".wc-skipped")
    text = pg.inner_text(".wc-skipped")
    assert "counters / clocks 1" in text and "constant" in text
    _all_open(pg)
    names = [n.strip() for n in pg.locator(".wc-row .wc-name").all_inner_texts()]
    assert "GPS[0].GMS [s]" not in names
    pg.click(".wc-skipped")
    pg.wait_for_selector(".wc-skiplist li")
    assert "GPS[0].GMS [s]" in pg.inner_text(".wc-skiplist")


def test_who_leads_whom_above_the_clusters(pg):
    """Q134: on the demo the chain says Motor3 leads Roll (the built delay, 80-180 ms) and Wind leads
    the others; a click on a node opens its cluster."""
    open_files(pg, "heavy_payload.csv", "light_payload.csv")
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-bar:not([hidden]) .sel-changed")
    pg.wait_for_selector(".wc-chain-list li")
    lines = pg.locator(".wc-chain-list li").all_inner_texts()
    m3 = next(x for x in lines if x.startswith("Motor3 → Roll"))
    s = float(m3.split("+")[1].split(" s")[0])
    assert 0.08 <= s <= 0.18 and "causes" not in " ".join(lines)
    assert any(x.startswith("Wind → ") for x in lines)
    before = pg.locator(".wc-cluster.open").count()
    pg.locator(".wc-chain-node").nth(2).click()                    # Motor3's node: its cluster opens
    pg.wait_for_function(f"document.querySelectorAll('.wc-cluster.open').length === {before + 1}")
    assert pg.locator(".wc-cluster.open .wc-chead", has_text="Motor3").count() == 1
