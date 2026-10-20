"""F27: the wheel zooms in proportion to the step (a trackpad's many small steps no longer zoom 25 %
each), a sideways swipe moves along the time axis (it zoomed out), and one gesture is one step back."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

RANGE = "Object.values(s.ranges).find(r => r)"


def test_wheel_steps_swipe_and_history(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    b = pg.locator(".plot .u-over").first.bounding_box()
    pg.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    # a mouse notch: about 25 %
    pg.mouse.wheel(0, -100)
    pg.wait_for_function("Object.values(window.__sv.state().ranges).some(r => r)")
    lo, hi = S(pg, RANGE)
    assert 0.75 < (hi - lo) / 30 < 0.85, (lo, hi)                # run_a: 30 s
    pg.keyboard.press("r")
    pg.wait_for_function("Object.values(window.__sv.state().ranges).every(r => !r)")
    pg.wait_for_timeout(500)                                     # the plot shows everything again
    # a trackpad: ten small steps in one gesture - a small zoom, one step back
    h0 = S(pg, "Math.max(0, ...Object.values(s.zoomHistory).map(h => h.length))")
    for _ in range(10):
        pg.mouse.wheel(0, -4)
    pg.wait_for_timeout(300)
    lo, hi = S(pg, RANGE)
    assert 0.85 < (hi - lo) / 30 < 0.95, (lo, hi)                # was 0.8 ** 10 = 0.11
    assert S(pg, "Math.max(0, ...Object.values(s.zoomHistory).map(h => h.length))") == h0 + 1
    # sideways: the window moves, its width stays
    w = hi - lo
    pg.wait_for_timeout(500)
    pg.mouse.wheel(60, 0)
    pg.wait_for_timeout(300)
    lo2, hi2 = S(pg, RANGE)
    assert abs((hi2 - lo2) - w) < 1e-6 * w and lo2 > lo, (lo, hi, lo2, hi2)
