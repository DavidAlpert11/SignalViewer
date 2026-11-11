"""Human-factors round (2026-11-11): a line that looks flat beside larger ones is offered the right
axis or a plot of its own (from the values - the file has no units); one plot at a time (M, the layout
button); the strip's how-to line only where there is something to click; the keys' list keeps its words.

    python -m pytest tests/e2e/test_flat_line_solo.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, frames, open_files, pg, set_layout, sig  # noqa: E402,F401


def lines(pg, plot=0):
    return S(pg, f"s.ws.tabs[0].plots[{plot}].signals.map(x => [x.sig.split('/')[1], x.axis || 'left'])")


def test_flat_line_is_offered_a_way_out(pg):
    open_files(pg, "run_a.csv")                       # Speed ~2..30 and RPM ~190..2850: no units in the file
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    frames(pg)
    assert pg.locator(".toast").count() == 0          # one line: nothing to say
    sig(pg, "RPM").click()
    toast = pg.locator(".toast", has_text="much larger")
    toast.wait_for()
    assert "RPM" in toast.inner_text()
    assert toast.locator("button", has_text="To its own plot").count() == 1
    toast.locator("button", has_text="To the right axis").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.some(x => x.axis === 'right')")
    assert lines(pg) == [["Speed", "left"], ["RPM", "right"]]
    # nothing moved by itself, and the move is one Undo
    pg.keyboard.press("Control+z")
    pg.wait_for_function("!window.__sv.state().ws.tabs[0].plots[0].signals.some(x => x.axis === 'right')")
    # asked once per plot and signal: adding it again does not nag
    pg.evaluate("window.__sv.state().commit((ws) => { const p = ws.tabs[0].plots[0]; p.signals = p.signals.slice(0, 1); return ws; })")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    sig(pg, "RPM").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 2")
    pg.wait_for_timeout(700)
    assert pg.locator(".toast", has_text="much larger").count() == 0


def test_own_plot_when_the_right_axis_is_taken(pg):
    open_files(pg, "run_a.csv")
    pg.evaluate("""window.__sv.state().commit((ws) => { const p = ws.tabs[0].plots[0]; const id = window.__sv.state().runs[0].id;
        const line = (n, axis) => ({ sig: id + '/' + n, color: '#888', width: 1.5, scale: 1, offset: 0, ...(axis ? { axis } : {}) });
        p.signals = [line('RPM'), line('Gear', 'right')]; return ws; })""")
    pg.wait_for_selector(".plot .chip >> nth=1")
    sig(pg, "Speed").click()
    toast = pg.locator(".toast", has_text="looks flat")
    toast.wait_for()
    assert toast.locator("button", has_text="To the right axis").count() == 0
    toast.locator("button", has_text="To its own plot").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.length === 2")
    assert [x[0] for x in lines(pg, 0)] == ["RPM", "Gear"] and [x[0] for x in lines(pg, 1)] == ["Speed"]


def test_like_ranges_share_the_axis_quietly(pg):
    open_files(pg, "run_a.csv", "run_b.csv", clear=False)
    pg.evaluate("window.__sv.state().commit((ws) => { ws.tabs[0].plots[0].signals = []; return ws; })")
    sig(pg, "Speed", 0).click()
    sig(pg, "Speed", 1).click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 2")
    pg.wait_for_timeout(900)
    assert pg.locator(".toast", has_text="flat").count() == 0


def test_one_plot_at_a_time(pg):
    open_files(pg, "run_a.csv")
    set_layout(pg, 3, 1)
    pg.wait_for_selector(".plot >> nth=2")
    sig(pg, "Speed").click()
    pg.keyboard.press("m")
    pg.wait_for_function("document.querySelectorAll('.plot').length === 1")
    assert pg.locator(".layout-btn").inner_text().strip() == "Plot 1 of 3"
    assert pg.locator(".layout-btn").get_attribute("aria-pressed") == "true"
    big = pg.locator(".plot").bounding_box()
    assert big["height"] > 500, big                       # the plot has the whole stage
    assert pg.locator(".plot .chip", has_text="Speed").count() == 1
    pg.keyboard.press("2")                                # 1 - 9 flip through the plots
    pg.wait_for_function("document.querySelector('.layout-btn').innerText.trim() === 'Plot 2 of 3'")
    assert pg.locator(".plot .chip").count() == 0
    assert S(pg, "[s.ws.tabs[0].rows, s.ws.tabs[0].cols, s.ws.tabs[0].plots.length]") == [3, 1, 3]   # the tab itself is untouched
    pg.keyboard.press("Escape")
    pg.wait_for_function("document.querySelectorAll('.plot').length === 3")
    assert pg.locator(".layout-btn").inner_text().strip() == "3 × 1"
    # the layout button's popover is the place; choosing a layout there leaves the mode
    pg.click(".stage-bar .layout-btn")
    pg.locator(".gridpick-solo").click()
    pg.wait_for_function("document.querySelectorAll('.plot').length === 1")
    set_layout(pg, 2, 1)
    pg.wait_for_function("document.querySelectorAll('.plot').length >= 2")
    assert S(pg, "s.soloPlot") is False
    # one plot in the tab: nothing to enlarge, nothing offered
    set_layout(pg, 1, 1)
    pg.click(".stage-bar .layout-btn")
    assert pg.locator(".gridpick-solo").count() == 0


def test_strip_hint_only_with_something_to_click(pg):
    open_files(pg, "semi.csv")                            # two sines: no flags, no state rows
    pg.wait_for_selector(".ov-strip")
    pg.wait_for_function("document.querySelector('.ov-strip .muted')?.innerText.includes('flags')")
    if pg.locator(".ov-flag").count() == 0 and pg.locator(".ov-row").count() == 0:
        assert pg.locator(".ov-hint").count() == 0


def test_keys_list_keeps_its_words(pg):
    pg.keyboard.press("?")
    pg.wait_for_selector(".help")
    assert pg.locator(".help td", has_text="One plot at a time").count() == 1
    # what a gesture does is not squeezed into a few words a line (it was ~100 px wide)
    w = pg.locator(".help table.keys").nth(1).locator("tr").first.locator("td").nth(1).bounding_box()["width"]
    assert w > 180, w


def test_quick_look_offered_when_no_template_fits(pg):
    """A plain file with no fitting template opened on an empty plot and no word on what to do: the
    start card offers the Quick look, and leaves by itself with the user's first own line."""
    open_files(pg, "semi.csv", clear=False)
    card = pg.locator(".start-card")
    card.wait_for()
    assert "Quick look" in card.inner_text() and "every signal in a plot of its own" in card.inner_text()
    sig(pg, "A").click()
    pg.wait_for_selector(".start-card", state="detached")
    # answered once: emptying the plot does not bring it back
    pg.evaluate("window.__sv.state().commit((ws) => { ws.tabs[0].plots[0].signals = []; return ws; })")
    pg.wait_for_timeout(400)
    assert pg.locator(".start-card").count() == 0


def test_quick_look_opens_from_the_card(pg):
    open_files(pg, "semi.csv", clear=False)
    pg.locator(".start-card .btn.primary").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.filter(p => p.signals.length).length === 2)")
    pg.wait_for_selector(".start-card", state="detached")


def test_comparison_lines_wear_their_object(pg):
    """After the merge with L8: in a comparison's tabs a line is named by its object and has the object's
    colour (the map's) in every plot; the statistics say their unit; the start card does not float on."""
    import os
    import shutil
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shutil.copy(os.path.join(root, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_selector(".rel-panel")
    objs = S(pg, "Object.fromEntries(s.ws.tabs[0].plots.find((p) => p.mode === 'geo').objects.map((o) => [o.name, o.color]))")
    pg.locator(".rel-panel .rel-compare-open").click()
    dlg = pg.locator(".cmpobj")
    box = dlg.locator(".cmpobj-grid").bounding_box(); outer = dlg.bounding_box()
    assert box["x"] - outer["x"] >= 10 and (outer["x"] + outer["width"]) - (box["x"] + box["width"]) >= 10   # not on the dialog's edges
    dlg.locator(".cmpobj-make").click()
    dlg.locator(".cmpobj-stats").wait_for()
    assert dlg.locator(".cmpobj-stats .unit").first.inner_text() == "[m]"
    assert dlg.locator(".cmpobj-stats td.obj").filter(has_text=re_any()).count() < dlg.locator(".cmpobj-stats tbody tr").count()   # a name once per block
    lines = S(pg, "s.ws.tabs.slice(1).flatMap((t) => t.plots.flatMap((p) => p.signals.map((x) => [x.label || '', x.color])))")
    assert lines and all(lbl.split(" · ")[0] in objs for lbl, _ in lines), lines
    assert all(color == objs[lbl.split(" · ")[0]] for lbl, color in lines), lines
    dlg.locator(".btn", has_text="Close").click()
    assert pg.locator(".start-card").count() == 0


def re_any():
    import re
    return re.compile(r"\S")


def test_second_pass_go_to_worst_menu_corner_lines_wording(pg):
    """The statistics' time of the largest error is a way there; the ⋯ button keeps the head's corner
    under a full row of chips; the lines select beside Compare… says what it chooses."""
    import os
    import shutil
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shutil.copy(os.path.join(root, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_selector(".rel-panel")
    assert pg.locator(".rel-panel .rel-lines option:checked").inner_text() == "Lines: the pair"
    head = pg.locator(".plot .plot-head").first.bounding_box()
    more = pg.locator(".plot .plot-more").first.bounding_box()
    assert more["y"] - head["y"] < 12 and (head["x"] + head["width"]) - (more["x"] + more["width"]) < 14, (head, more)
    pg.locator(".rel-panel .rel-compare-open").click()
    pg.locator(".cmpobj-make").click()
    pg.locator(".cmpobj-stats").wait_for()
    go = pg.locator(".cmpobj-goto").first
    t = float(go.inner_text())
    go.click()
    pg.wait_for_selector(".cmpobj", state="detached")
    cur = S(pg, "[s.cursor.on, s.cursor.t1]")
    assert cur[0] is True and abs(cur[1] - t) < 0.06, (cur, t)
