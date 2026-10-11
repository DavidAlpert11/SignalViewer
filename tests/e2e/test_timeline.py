"""The shared timeline: one bar for the whole recording whose handle is the cursor.

    python -m pytest tests/e2e/test_timeline.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

EXT = "(() => { const r = window.__sv.state().runs.filter(r => r.format !== 'derived'); return [Math.min(...r.map(x => x.start)), Math.max(...r.map(x => x.end))]; })()"


def _click_track(pg, f):
    box = pg.locator(".tl-track").bounding_box()
    pg.mouse.click(box["x"] + box["width"] * f, box["y"] + box["height"] / 2)


def test_timeline_spans_all_files_and_moves_the_cursor(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    pg.wait_for_selector(".timeline")
    assert pg.locator(".tl-cover").count() == 2                    # one row per file
    lo, hi = pg.evaluate(EXT)
    _click_track(pg, 0.25)
    c = S(pg, "s.cursor")
    assert c["on"] and abs(c["t1"] - (lo + (hi - lo) * 0.25)) < (hi - lo) * 0.02
    # dragging follows the pointer
    box = pg.locator(".tl-track").bounding_box()
    y = box["y"] + box["height"] / 2
    pg.mouse.move(box["x"] + box["width"] * 0.25, y); pg.mouse.down()
    pg.mouse.move(box["x"] + box["width"] * 0.75, y, steps=8); pg.mouse.up()
    assert abs(S(pg, "s.cursor.t1") - (lo + (hi - lo) * 0.75)) < (hi - lo) * 0.02
    assert pg.locator(".tl-handle").count() == 1


def test_home_end_and_playback_in_real_time(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    lo, hi = pg.evaluate(EXT)
    pg.keyboard.press("End")
    assert abs(S(pg, "s.cursor.t1") - hi) < 1e-6
    pg.keyboard.press("Home")
    assert abs(S(pg, "s.cursor.t1") - lo) < 1e-6
    pg.locator(".timeline select[aria-label='Playback speed (× real time)']").select_option("2")
    pg.locator(".tl-play").click()
    pg.wait_for_timeout(1000)
    pg.locator(".tl-play").click()
    moved = S(pg, "s.cursor.t1") - lo
    assert 1.0 < moved < 4.0                                        # ~2 s of recording per second
    # from near the end at ×60: stops at the end
    _click_track(pg, 0.97)
    pg.locator(".timeline select[aria-label='Playback speed (× real time)']").select_option("60")
    pg.locator(".tl-play").click()
    pg.wait_for_function("!window.__sv.state().playing", timeout=10000)
    assert abs(S(pg, "s.cursor.t1") - hi) < 1e-6


def test_window_mode_and_follow(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    lo, hi = pg.evaluate(EXT)
    pg.locator(".timeline select[aria-label='What the plots show']").select_option("window")
    box = pg.locator(".timeline input[aria-label='Window length (seconds)']")
    box.fill("2")
    assert S(pg, "s.windowSec") == 2 and S(pg, "s.playMode") == "window"
    assert pg.locator(".tl-shown").count() == 0                     # no time yet
    # a zoomed time plot follows the time when it leaves the window
    rk = S(pg, "s.ws.tabs[0].linkX ? s.ws.tabs[0].id : s.ws.tabs[0].plots[0].id")
    pg.evaluate(f"window.__sv.setState({{ ranges: {{ '{rk}': [{lo}, {lo + (hi - lo) * 0.1}] }} }})")
    pg.evaluate("document.activeElement.blur()")                    # (End inside the number box moves its caret)
    pg.keyboard.press("End")
    r = S(pg, f"s.ranges['{rk}']")
    assert r[0] <= hi <= r[1]
    assert pg.locator(".tl-shown").count() == 1                     # the window on the track


def test_note_mark_jumps_to_its_time_and_collapse(pg):
    open_files(pg, "run_a.csv")
    lo, hi = pg.evaluate(EXT)
    t = lo + (hi - lo) * 0.6
    pg.evaluate(f"window.__sv.setState({{ ws: {{ ...window.__sv.state().ws, notes: [{{ id: 'n1', t: {t}, text: 'Check here' }}] }} }})")
    mark = pg.locator(".tl-event.note")
    mark.wait_for()
    mark.click()
    assert abs(S(pg, "s.cursor.t1") - t) < 1e-6
    pg.locator(".timeline [aria-label='Make the timeline smaller']").click()
    pg.wait_for_selector(".timeline.slim")
    assert pg.locator(".timeline.slim .tl-track").count() == 1      # still usable when small
    pg.locator(".timeline [aria-label='Show the whole timeline']").click()
    pg.wait_for_selector(".timeline:not(.slim)")


def test_timeline_settings_saved_in_the_session(pg):
    open_files(pg, "run_a.csv")
    pg.evaluate("window.__sv.setState({ playMode: 'window', windowSec: 7, playSpeed: 5, timelineOpen: false })")
    # the autosave carries them: reload the page and restore it
    pg.wait_for_timeout(2500)
    pg.reload()
    pg.wait_for_selector(".app")
    pg.wait_for_function("window.__sv.state().runs.length > 0", timeout=20000)
    assert S(pg, "[s.playMode, s.windowSec, s.playSpeed, s.timelineOpen]") == ["window", 7, 5, False]
