"""N6: an easy map - the controls (+ / − / fit / follow), a drag while following (Back to following),
the map's own keys while it has the focus, the one-line hint (remembered once closed), and the time
moving the objects without re-rendering the panels.

    python -m pytest tests/e2e/test_map_smooth.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _view(pg):
    z, cx, cy = (float(x) for x in pg.locator(".plot-canvas.geo").get_attribute("data-view").split(","))
    return z, cx, cy


def _settled(pg):
    """The view stops changing (animations and glides over)."""
    pg.wait_for_timeout(60)
    pg.evaluate("window.__lastView = undefined")
    pg.wait_for_function("""(() => { const e = document.querySelector('.plot-canvas.geo'); const v = e && e.dataset.view;
        const w = window.__lastView; window.__lastView = v; return v && v === w; })""", polling=250)


@pytest.fixture()
def three(pg):
    shutil.copy(os.path.join(ROOT, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_selector(".plot-canvas.geo[data-view]")
    _settled(pg)
    return pg


def test_zoom_buttons_and_fit(three):
    pg = three
    z0, cx0, cy0 = _view(pg)
    pg.locator(".geo-zoom-in").click(); _settled(pg)
    z1, _, _ = _view(pg)
    assert abs(z1 - z0 - 1) < 1e-3                                    # one step, animated to its end
    pg.locator(".geo-zoom-out").click(); pg.locator(".geo-zoom-out").click(); _settled(pg)
    assert abs(_view(pg)[0] - (z0 - 1)) < 1e-3
    pg.locator(".geo-fit").click(); _settled(pg)
    z, cx, cy = _view(pg)
    assert abs(z - z0) < 1e-3 and abs(cx - cx0) < 1e-9 and abs(cy - cy0) < 1e-9


def test_keys_only_while_the_map_has_focus(three):
    pg = three
    pg.locator(".plot-canvas.geo").focus()
    z0, cx0, cy0 = _view(pg)
    pg.keyboard.press("ArrowRight"); _settled(pg)
    assert _view(pg)[1] > cx0                                         # the map moved (east)
    pg.keyboard.press("+"); _settled(pg)
    assert abs(_view(pg)[0] - z0 - 1) < 1e-3
    pg.keyboard.press("0"); _settled(pg)
    assert abs(_view(pg)[0] - z0) < 1e-3
    pg.keyboard.press("f")
    assert S(pg, "s.ws.tabs[0].plots.find((p) => p.mode === 'geo').followObject") is not None
    pg.keyboard.press("f")
    assert S(pg, "s.ws.tabs[0].plots.find((p) => p.mode === 'geo').followObject") is None
    # Shift+arrow still steps the cursor (the timeline's key), the map does not move
    pg.keyboard.press("Home")
    t0 = S(pg, "s.cursor.t1")
    v = _view(pg)
    pg.keyboard.press("Shift+ArrowRight")
    pg.wait_for_function(f"window.__sv.state().cursor.t1 > {t0}")
    assert _view(pg) == v


def test_drag_while_following_offsets_and_back(three):
    pg = three
    pg.locator(".geo-follow").select_option(label="nav")
    pg.keyboard.press("Home")
    _settled(pg)
    box = pg.locator(".plot-canvas.geo canvas").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    pg.mouse.move(cx, cy); pg.mouse.down()
    for i in range(1, 11):
        pg.mouse.move(cx + 8 * i, cy, steps=1)
    pg.wait_for_timeout(120)                                          # no glide: the drag ends at rest
    pg.mouse.up()
    _settled(pg)
    assert S(pg, "s.ws.tabs[0].plots.find((p) => p.mode === 'geo').followObject")    # still following
    back = pg.locator(".geo-back")
    assert back.inner_text() == "Back to following"
    off = _view(pg)
    pg.keyboard.press("End")                                          # the time moves: the offset is kept
    _settled(pg)
    moved = _view(pg)
    assert moved != off
    back.click(); _settled(pg)
    assert pg.locator(".geo-back").count() == 0


def test_hint_once_and_remembered(three):
    pg = three
    hint = pg.locator(".geo-hint")
    assert "drag to move" in hint.inner_text()
    hint.locator("button").click()
    pg.wait_for_selector(".geo-hint", state="detached")
    pg.wait_for_timeout(600)                                          # the setting reaches the app
    pg.reload()
    pg.wait_for_selector(".plot-canvas.geo[data-view]")
    assert pg.locator(".geo-hint").count() == 0


def test_playback_redraws_the_map_without_the_panels(three):
    """N6: during playback the panels and the plot's head are not rendered again each frame."""
    pg = three
    pg.evaluate("window.__sv.setState({ playSpeed: 10, cursor: { ...window.__sv.state().cursor, on: true } })")
    pg.keyboard.press("Home")
    pg.evaluate("window.__svRenders = {}")
    pg.evaluate("window.__sv.setState({ playing: true })")
    pg.wait_for_timeout(1000)
    pg.evaluate("window.__sv.setState({ playing: false })")
    r = pg.evaluate("window.__svRenders")
    pg.evaluate("window.__svRenders = undefined")
    assert r.get("Timeline", 0) > 20                                  # the time did move, every frame
    for k in ("App", "DataPanel", "PlotView", "GeoChart", "StageBar", "TemplateStrip", "Inspector"):
        assert r.get(k, 0) <= 3, (k, r)
