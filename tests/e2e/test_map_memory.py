"""2026-11-16 (Out of Memory and "Fragment shader failed to compile" on the owner's PC): a closed map gives its
WebGL context back, opening and closing a map many times keeps the page's memory flat, and a failed render of
the 3D view falls back to its light mode, then to the flat map - never Cesium's dead dialog.

    python -m pytest tests/e2e/test_map_memory.py -q
Measured with tools/measure_maps.py (its probe counts the contexts and widgets in the page).
"""
import os
import sys
import time

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env  # noqa: E402,F401

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
from measure_maps import HARDWARE_GL, PROBE  # noqa: E402

DRAW_BUDGET_S = 90          # software WebGL on a busy CI machine; ~2-5 s here, 1-2 s with a graphics card


def _page(env, gl_browser, full):
    ctx = gl_browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    ctx.add_init_script(PROBE)
    if full:
        ctx.add_init_script(HARDWARE_GL)
    for f in ("autosave.json", "ui_settings.json"):
        p = os.path.join(env["home"], ".signalviewer", f)
        if os.path.exists(p):
            os.remove(p)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(env["url"])
    pg.wait_for_selector(".ex-card[data-example='flight']")
    return ctx, pg, errors


def _close_files(pg):
    pg.evaluate("""async () => { for (const r of await (await fetch('/api/runs')).json())
      if (r.format !== 'derived') await fetch('/api/runs/' + r.id, { method: 'DELETE' });
      window.__sv.setState({ runs: [] }); }""")
    pg.wait_for_selector(".ex-card[data-example='flight']")


def _open_map(pg, ex):
    t0 = time.time()
    pg.locator(f".ex-card[data-example='{ex}']").click()
    pg.wait_for_function("() => { const g = window.__svGlobe; return !!g && !g.widget.isDestroyed() && g.widget.scene.globe.tilesLoaded; }",
                         timeout=DRAW_BUDGET_S * 1000, polling=200)
    return time.time() - t0


def _heap_mb(cdp):
    cdp.send("HeapProfiler.collectGarbage")
    return next(m["value"] for m in cdp.send("Performance.getMetrics")["metrics"] if m["name"] == "JSHeapUsedSize") / 2**20


@pytest.mark.parametrize("full", [False, True], ids=["light", "full"])
def test_opening_and_closing_a_map_keeps_memory_flat(env, gl_browser, full):
    """Six openings of the maps: each closed map's WebGL context is lost at once (before the fix every one stayed
    alive until the browser's limit of 16 - ~50 MB each in software, framebuffers and shadow maps on a GPU)."""
    ctx, pg, errors = _page(env, gl_browser, full)
    cdp = ctx.new_cdp_session(pg)
    cdp.send("Performance.enable")
    heaps = []
    for i, ex in enumerate(["flight", "ardupilot", "flight", "ardupilot", "flight", "ardupilot"]):
        took = _open_map(pg, ex)
        assert took < DRAW_BUDGET_S
        on = pg.evaluate("window.__svProbe()")
        assert on["widgets"] == 1 and on["post"] <= 3, on          # one view; its postRender listeners do not pile up
        if full and i == 0:
            assert pg.evaluate("window.__svGlobe.widget.scene.globe.enableLighting")   # the full mode really ran
        _close_files(pg)
        heaps.append(_heap_mb(cdp))
        after = pg.evaluate("window.__svProbe()")
        assert after["widgets"] == 0 and after["gl"] == 0, after    # no context left alive once the map is closed
    assert heaps[-1] - heaps[1] < 8, heaps                          # the JS heap flat after the first opening
    assert not errors, errors
    ctx.close()


BREAK_RENDER = """() => { const w = window.__svGlobe.widget;     // a primitive whose update throws: Cesium's render fails
  w.scene.primitives.add({ update() { throw new Error('Fragment shader failed to compile (test)'); }, isDestroyed: () => false, destroy() {} });
  w.scene.requestRender(); }"""


def test_a_failed_render_falls_back_to_light_then_flat(env, gl_browser):
    """Full mode fails -> the 3D view is made again in the light mode (the badge says so); the light mode fails ->
    the map is drawn flat with its note. Cesium's error panel is never shown, the old view's context is lost."""
    ctx, pg, errors = _page(env, gl_browser, True)
    _open_map(pg, "flight")
    assert pg.evaluate("window.__svGlobe.widget.scene.globe.enableLighting")          # full mode
    pg.evaluate(BREAK_RENDER)
    pg.wait_for_function("() => { const g = window.__svGlobe; return !!g && !g.widget.isDestroyed() && !g.widget.scene.globe.enableLighting; }",
                         timeout=DRAW_BUDGET_S * 1000)
    pg.wait_for_selector(".globe3d-light")
    assert pg.locator(".cesium-widget-errorPanel").count() == 0
    assert pg.evaluate("window.__svProbe()")["widgets"] == 1
    pg.evaluate(BREAK_RENDER)
    pg.wait_for_selector(".map-flat-note", timeout=30000)
    pg.wait_for_selector(".plot-canvas.geo canvas")
    assert pg.locator(".cesium-widget-errorPanel").count() == 0
    assert pg.evaluate("window.__svProbe()")["gl"] == 0                               # both 3D views' contexts given back
    assert not errors, errors
    ctx.close()
