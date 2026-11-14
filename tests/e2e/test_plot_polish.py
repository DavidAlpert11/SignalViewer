"""L7 (2026-11-13): W7 the two cursors' bar in the plot's head, W9 the views badge / a flight log's dimmed
message part, W13.2 the first draw-in (once per tab), T49 item 10 the cursors next to the zoom."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg, sig  # noqa: E402,F401


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
    order = pg.eval_on_selector_all(".stage-bar > *", "els => els.map((e) => e.className)")
    z = next(i for i, c in enumerate(order) if "zoom" in c or c == "pick-wrap" and i > 3)
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
    """F2 (lane L3): the legend shows, on demand, the shown window's min · mean · max - the same numbers as
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
