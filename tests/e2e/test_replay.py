"""1.25 (R1 - R3): a replay page made from the Report panel - it opens on the moment, one click moves the
cursor in every plot, Play advances it; Δ between two cursors in the chips; the timeline's window on the
recording - dragged to move what the plots show, one Backspace back.

    python -m pytest tests/e2e/test_replay.py -q
"""
import json
import os
import re

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, frames, open_files, pg, save_as, set_layout, sig  # noqa: E402,F401


def plot_two(pg):
    open_files(pg, "run_a.csv")
    set_layout(pg, 2, 1)
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.locator(".plot").nth(1).click(position={"x": 60, "y": 12})        # the second plot active
    sig(pg, "RPM").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.filter(p => p.signals.length).length === 2")


def test_delta_chips_and_timeline_window(pg):
    plot_two(pg)
    key = S(pg, "s.ws.tabs[0].id")
    # zoomed to 10..16 s, two cursors at 11 and 14: each chip shows its change between them
    pg.evaluate(f"""() => window.__sv.setState({{ ranges: {{ ...window.__sv.state().ranges, {json.dumps(key)}: [10, 16] }},
        cursor: {{ on: true, dual: true, t1: 11, t2: 14, active: 1 }} }})""")
    pg.wait_for_function("document.querySelectorAll('.chip .dlt').length === 2")
    d = pg.locator(".chip .dlt").first.inner_text()
    assert re.match(r"^Δ [+−±]\d", d), d
    # the window on the timeline: dragged, what the plots show moves (same width); Backspace: back
    win = pg.locator(".tl-view")
    win.wait_for()
    assert pg.locator(".tl-env path").count() == 1                    # the active line along the track
    b = win.bounding_box()
    pg.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    pg.mouse.down(); pg.mouse.move(b["x"] + b["width"] / 2 + 60, b["y"] + b["height"] / 2, steps=6); pg.mouse.up()
    r = S(pg, f"s.ranges[{json.dumps(key)}]")
    assert r[0] > 10.5 and abs((r[1] - r[0]) - 6) < 1e-6, r
    pg.locator(".plot").first.click(position={"x": 60, "y": 12})
    pg.keyboard.press("Backspace")
    pg.wait_for_function(f"(() => {{ const r = window.__sv.state().ranges[{json.dumps(key)}]; return r && Math.abs(r[0] - 10) < 1e-6; }})()")


def test_replay_page(pg):
    plot_two(pg)
    pg.evaluate("() => window.__sv.setState({ cursor: { on: true, dual: false, t1: 12.5, t2: null, active: 1 } })")
    pg.click(".rail [aria-label='Report'], .rail button:has-text('Report')")
    pg.locator(".replay-card .replay-make").click()
    save_as(pg, "run_a-replay.html")
    toast = pg.locator(".toast", has_text="run_a-replay.html")
    toast.wait_for(timeout=40000)
    assert toast.locator("button", has_text="Open it").count() == 1
    path = os.path.join(pg.env["out"], "run_a-replay.html")
    page = pg.context.new_page()
    try:
        page.goto("file://" + path)
        page.wait_for_function("window.__replay && document.querySelectorAll('.plot .u-over').length === 2")
        assert abs(page.evaluate("window.__replay.t") - 12.5) < 1e-6         # opens on the moment
        assert "Made with Signal Viewer" in page.inner_text("footer")
        # one click on the second plot moves the first plot's value too (one time for the page)
        before = page.locator(".plot").first.locator(".legend .val").inner_text()
        o = page.locator(".plot .u-over").nth(1).bounding_box()
        page.mouse.click(o["x"] + o["width"] * 0.8, o["y"] + o["height"] / 2)
        page.wait_for_function("window.__replay.t > 20")
        assert page.locator(".plot").first.locator(".legend .val").inner_text() != before
        assert re.search(r"#t=2\d\.", page.evaluate("location.hash"))
        # Play advances the time
        page.locator("#rp-start").click()
        page.keyboard.press("Space")
        page.wait_for_function("window.__replay.playing && window.__replay.t > window.__replay.lo + 0.3")
        page.keyboard.press("Space")
        page.wait_for_function("!window.__replay.playing")
    finally:
        page.close()
