"""Z1 (owner, 2026-11-22: "I still cannot zoom on the y axis, only x - fix it everywhere"): in the app, an XY plot and
an FFT zoom both axes - a box (its direction picks the axes), the wheel (XY: both around the pointer; FFT: the
frequency, over the value axis the level), a double click shows everything. (A time plot zooms its values already:
test_features' drag tests.)"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

SC = "(i) => { const u = document.querySelectorAll('.plot .uplot')[i].svPlot; return [u.scales.x.min, u.scales.x.max, u.scales.y.min, u.scales.y.max]; }"


def _mode(pg, mode, x=None):
    pg.evaluate("""([mode, x]) => window.__sv.state().commit(ws => { const p = ws.tabs[0].plots[0]; p.mode = mode;
        if (x) p.xSignal = x; return ws; })""", [mode, x])


def test_xy_and_fft_zoom_both_axes_in_the_app(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    rpm = S(pg, "s.runs[0].signals.find(x => x.name === 'RPM').id")
    for mode in ("xy", "fft"):
        _mode(pg, mode, rpm if mode == "xy" else None)
        pg.wait_for_function("() => { const r = document.querySelector('.plot .uplot'); return r && r.svPlot && r.svPlot.scales.x.max > r.svPlot.scales.x.min; }", timeout=20000)
        pg.wait_for_timeout(500)
        full = pg.evaluate(SC, 0)
        box = pg.locator(".plot .u-over").first.bounding_box()
        # a box: both axes
        pg.mouse.move(box["x"] + box["width"] * 0.2, box["y"] + box["height"] * 0.2)
        pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] * 0.6, box["y"] + box["height"] * 0.6, steps=8); pg.mouse.up()
        pg.wait_for_timeout(200)
        z = pg.evaluate(SC, 0)
        assert z[1] - z[0] < 0.7 * (full[1] - full[0]) and z[3] - z[2] < 0.9 * (full[3] - full[2]), (mode, full, z)
        # up / down: the values only (the x as zoomed)
        pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.2)
        pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.6, steps=8); pg.mouse.up()
        pg.wait_for_timeout(200)
        y = pg.evaluate(SC, 0)
        assert y[0:2] == pytest.approx(z[0:2]) and y[3] - y[2] < z[3] - z[2], (mode, z, y)
        # the wheel over the value axis: the values only
        pg.mouse.move(box["x"] - 15, box["y"] + box["height"] * 0.5)
        pg.mouse.wheel(0, 120)
        pg.wait_for_timeout(200)
        w = pg.evaluate(SC, 0)
        assert w[0:2] == pytest.approx(y[0:2]) and w[3] - w[2] > y[3] - y[2], (mode, y, w)
        # a double click: everything
        pg.mouse.dblclick(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        pg.wait_for_timeout(300)
        assert pg.evaluate(SC, 0) == pytest.approx(full, rel=1e-6), mode
