"""L7 (2026-11-13): W7 the two cursors' bar in the plot's head, W9 the views badge / a flight log's dimmed
message part, W13.2 the first draw-in (once per tab), T49 item 10 the cursors next to the zoom."""
import numpy as np
import os
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, _csv, env, menu_item, open_files, pg, sig  # noqa: E402,F401


def test_two_cursors_bar_sits_in_the_plot_head(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("d")                                         # two cursors
    bar = pg.locator(".plot-head .sel-slot .sel-bar")
    pg.wait_for_function("(() => { const b = document.querySelector('.plot-head .sel-bar'); return b && !b.hidden; })()")
    head = pg.locator(".plot-head").first.bounding_box()
    b = bar.bounding_box()
    assert head["y"] <= b["y"] and b["y"] + b["height"] <= head["y"] + head["height"] + 1       # inside the head
    legend = pg.locator(".plot-head .legend").first.bounding_box()
    assert b["x"] >= legend["x"] + legend["width"] - 1                                        # right of the legend
    before = b["x"]
    pg.keyboard.press("ArrowRight")                                # the cursors move: the bar stays where it is
    assert abs(bar.bounding_box()["x"] - before) < 1


def test_cursor_buttons_next_to_the_zoom(pg):
    open_files(pg, "run_a.csv")
    # RV1: no zoom-mode button any more - the cursors sit next to Reset zoom
    order = pg.eval_on_selector_all(".stage-bar > *", "els => els.map((e) => e.className + ((e.title || '').startsWith('Reset zoom') ? ' zoom' : ''))")
    z = next(i for i, c in enumerate(order) if "zoom" in c)
    cur = next(i for i, c in enumerate(order) if "cursor-btn" in c)
    assert 0 < cur - z <= 4, order


def test_the_first_plot_draws_in_once_per_tab(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__svDrawIn === 1")
    pg.keyboard.press("r")                                         # a zoom reset: no second draw-in
    sig(pg, "RPM").click()
    pg.wait_for_timeout(600)
    assert pg.evaluate("window.__svDrawIn") == 1


def test_a_flight_logs_message_part_is_dimmed_in_a_flat_list(pg):
    pg.locator(".examples-line button", has_text="ArduPilot").click()
    pg.wait_for_function("window.__sv.state().runs.some((r) => r.format === 'bin')")
    pg.fill(".filter input", "ATT.DesRoll")                        # one match: listed flat, with its message
    pg.wait_for_selector(".sig .nm .nm-grp")
    assert pg.locator(".sig .nm .nm-grp").first.inner_text() == "ATT."


def test_window_statistics_in_the_legend(pg):
    """F2: the legend shows, on demand, the shown window's min · mean · max - the same numbers as
    numpy over the samples on screen, and they follow a zoom."""
    import csv
    import os
    from test_features import menu_item
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("(() => { const s = window.__sv.state(); const p = s.ws.tabs[0].plots[0]; return p.signals.length && s.xViews[p.id]; })()")
    pg.locator(".plot-more").first.click()
    pg.locator(".menu.ctx button", has_text="Legend").first.hover()
    menu_item(pg, "Statistics of the shown window")
    with open(os.path.join(pg.env["data"], "run_a.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    tcol = next(k for k in rows[0] if k.lower().startswith("t"))
    scol = next(k for k in rows[0] if k.startswith("Speed"))

    def check():
        pg.wait_for_selector(".chip .wstat b")
        a, b = pg.evaluate("(() => { const s = window.__sv.state(); return s.xViews[s.ws.tabs[0].plots[0].id]; })()")
        ys = [float(r[scol]) for r in rows if a <= float(r[tcol]) <= b]
        shown = [float(x.replace(",", "")) for x in pg.locator(".chip .wstat b").all_inner_texts()]
        ref = [min(ys), sum(ys) / len(ys), max(ys)]
        assert all(abs(s - r) <= 1e-3 * max(1.0, abs(r)) for s, r in zip(shown, ref)), (shown, ref)
        return shown

    whole = check()
    # zoomed to the first half: the numbers follow
    pg.evaluate("""(() => { const s = window.__sv.state(); const tb = s.ws.tabs[0], p = tb.plots[0], v = s.xViews[p.id];
        window.__sv.setState({ ranges: { ...s.ranges, [tb.linkX ? tb.id : p.id]: [v[0], (v[0] + v[1]) / 2] } }); })()""")
    pg.wait_for_function("(w) => { const t = [...document.querySelectorAll('.chip .wstat b')].map((e) => e.textContent).join('|'); return t && t !== w; }",
                         arg="|".join(pg.locator(".chip .wstat b").all_inner_texts()))
    assert check() != whole


def test_pin_a_statistic_to_the_run_at_a_glance(pg):
    """D8 + D14: the Inspector's statistics pin a line's number to the run at a glance, by the
    signal's name (Undo-able, saved with a template); a fifth is refused with a message."""
    from test_features import menu_item
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.evaluate("window.__sv.setState({ inspectorOpen: true })")
    row = pg.locator(".inspector table.stats tr.name-row").first
    row.wait_for()
    row.hover()
    row.locator(".stats-pin").click()
    menu_item(pg, "max")
    pg.wait_for_function("(window.__sv.state().ws.glance || []).some((g) => g.stat === 'max' && g.name.startsWith('Speed'))")
    assert pg.locator(".inspector table.stats td.num").count() >= 4          # the numbers in their mono column
    pg.keyboard.press("Control+z")
    pg.wait_for_function("!(window.__sv.state().ws.glance || []).length")


def test_the_run_at_a_glance_shows_its_numbers_and_the_checks(pg):
    """D14 (1) + D7: the strip's head shows the pinned numbers of the run (a missing signal is said, not
    dropped), a click on one goes to its time; a broken limit shows as the Checks count, which opens Checks; ⋯ unpins."""
    from test_features import menu_item
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length))")
    pg.evaluate("""window.__sv.state().commit((w) => { w.glance = [{ name: 'Speed', stat: 'max' }, { name: 'NoSuch', stat: 'min' }]; return w; })""")
    gls = pg.locator(".ov-head .ov-gl")
    pg.wait_for_function("document.querySelectorAll('.ov-head .ov-gl').length === 2 && !!document.querySelector('.ov-gl-none')")
    first = gls.nth(0).locator(".ov-gl-go")
    pg.wait_for_function("!document.querySelector('.ov-gl-go .ov-gl-val').textContent.includes('…')")
    assert "Max" in first.inner_text() or "max" in first.inner_text()
    assert "NoSuch" in (gls.nth(1).locator(".ov-gl-none").get_attribute("title") or "")      # said, not dropped
    first.click()
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.t1 !== null")
    # a limit nothing can meet: the Checks count says 1 failed and opens the Checks panel
    pg.evaluate("""window.__sv.state().commit((w) => { const p = w.tabs.flatMap((t) => t.plots).find((p) => p.signals.length);
      p.signals[0].limits = { lo: null, hi: -1e12 }; return w; })""")
    chk = pg.locator(".ov-head .ov-checks")
    chk.wait_for()
    pg.wait_for_function("+document.querySelector('.ov-checks').dataset.bad >= 1")
    chk.click()
    pg.wait_for_function("window.__sv.state().panel === 'log'")
    # ... on the strip's own run (it opened on the first log before), the request consumed
    pg.wait_for_function("""(() => { const s = window.__sv.state(); const sel = document.querySelector('.log-panel select, .side select');
      return s.checksRun === null && (!sel || sel.value === s.runs.find((r) => r.name.startsWith('run_a')).id); })()""")
    gls.nth(1).hover()
    gls.nth(1).locator(".ov-gl-more").click()
    menu_item(pg, "Unpin")
    pg.wait_for_function("(window.__sv.state().ws.glance || []).length === 1")


# FR12: from the owner's notes of 2026-11-03 (1.20; the file was test_owner_notes_1_20.py)
def _many(pg, n):
    p = os.path.join(pg.env["data"], f"many{n}.csv")
    if not os.path.exists(p):
        t = np.arange(0, 20, 0.02)
        # values whose printed length changes as the cursor moves (1.5, -0.25, 123.456...)
        _csv(p, ["Time"] + [f"Channel_{i:02d}_measured" for i in range(n)],
             [t] + [np.sin(t * (1 + i / 7)) * 10 ** (i % 4) for i in range(n)])
    return os.path.basename(p)


def _plot_all(pg, prefix, n):
    pg.evaluate("""([prefix, n]) => { const st = window.__sv.state(); const r = st.runs.find((x) => x.signals.some((y) => y.name.startsWith(prefix)));
        const sigs = r.signals.filter((y) => y.name.startsWith(prefix)).slice(0, n)
          .map((y, i) => ({ sig: y.id, color: ['#3D8BFD', '#F07B3F', '#2FBF9F'][i % 3], width: 1.5, scale: 1, offset: 0 }));
        st.commit((ws) => { ws.tabs[0].plots[0].signals = sigs; return ws; }); }""", [prefix, n])
    pg.wait_for_function(f"window.__sv.state().ws.tabs[0].plots[0].signals.length === {n}")


def test_legend_beside_when_many_and_still_while_hovering(pg):
    open_files(pg, _many(pg, 30))
    _plot_all(pg, "Channel_", 30)
    # many: a column beside the plot, the header one line
    pg.wait_for_selector(".legend-side .lrow")
    assert pg.locator(".legend-side .lrow").count() == 30
    assert pg.locator(".plot-head").first.bounding_box()["height"] < 40
    # the filter, and the line under the pointer in front
    pg.fill(".legend-filter", "Channel_07")
    assert pg.locator(".legend-side .lrow").count() == 1
    pg.locator(".legend-side .lrow").first.hover()
    assert S(pg, "s.legendFocus && s.legendFocus.sig.endsWith('Channel_07_measured')")
    pg.fill(".legend-filter", "")
    # above the plot (the menu), a few signals: the header never gets lower while the pointer moves
    pg.locator(".plot-more").first.click()
    pg.locator(".menu.ctx button", has_text="Legend").first.hover()
    menu_item(pg, "Above the plot")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].legend === 'top'")
    pg.evaluate("""() => { const st = window.__sv.state(); st.commit((ws) => { ws.tabs[0].plots[0].signals = ws.tabs[0].plots[0].signals.slice(0, 6); return ws; }); }""")
    box = pg.locator(".plot-body").first.bounding_box()
    hs = []
    for i in range(40):
        pg.mouse.move(box["x"] + 20 + i * (box["width"] - 40) / 40, box["y"] + box["height"] / 2)
        hs.append(round(pg.locator(".plot-head").first.bounding_box()["height"]))
    assert all(b >= a for a, b in zip(hs, hs[1:])), hs           # grows at most, never jumps back
    assert pg.locator(".plot-body .hover-t").count() == 1           # the time in the plot's corner
    # hidden: a button says how many and shows it again
    pg.evaluate("() => window.__sv.state().commit((ws) => { ws.tabs[0].plots[0].legend = 'off'; return ws; })")
    pg.locator(".legend-hidden").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].legend === undefined")
