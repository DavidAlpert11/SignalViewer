"""M34 FR3: the two cursors' labels sit in the time axis' margin, not on the curves; a double-click on a signal in
the list plots it once (it used to add and remove)."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

# every time plot: the label boxes its cursor layer drew (page px) and its plot area
BOXES = """() => [...document.querySelectorAll('.plot')].map((p) => {
  const layer = p.querySelector('.u-cursor-layer'), over = p.querySelector('.u-over');
  if (!layer || !over || !layer.dataset.flags) return null;
  const l = layer.getBoundingClientRect(), o = over.getBoundingClientRect();
  return { over: [o.left, o.top, o.right, o.bottom],
           flags: JSON.parse(layer.dataset.flags).map(([x, y, w, h]) => [l.left + x, l.top + y, l.left + x + w, l.top + y + h]) };
}).filter(Boolean)"""


def overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 0.5 and min(a[3], b[3]) - max(a[1], b[1]) > 0.5


def test_the_cursors_labels_are_off_the_plot_area(pg):
    pg.locator(".examples-line button", has_text="Find out what went wrong").click()
    pg.wait_for_selector(".demo-guide[data-demo='investigate'] .btn.primary", timeout=30000)
    pg.click(".demo-guide .btn.primary")                               # Put the cursors there
    pg.wait_for_function("window.__sv.state().cursor.dual")
    pg.wait_for_function("[...document.querySelectorAll('.plot .u-cursor-layer')].every((c) => c.dataset.flags && JSON.parse(c.dataset.flags).length === 2)")
    plots = pg.evaluate(BOXES)
    assert len(plots) >= 3
    for p in plots:
        one, two = p["flags"]
        assert not overlap(one, p["over"]) and not overlap(two, p["over"]), p     # not on the data at all
        assert one[1] >= p["over"][3] - 0.5 and two[1] >= p["over"][3] - 0.5       # under the plot, in the axis' margin
        assert not overlap(one, two)                                              # and not on one another
        assert one[2] <= two[0] + 0.5                                             # each on the outer side of its line


def test_one_cursor_label_is_in_the_margin_too(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: false, t1: 12, active: 1 } })")
    pg.wait_for_function("(() => { const c = document.querySelector('.plot .u-cursor-layer'); return c && c.dataset.flags && JSON.parse(c.dataset.flags).length === 1; })()")
    p = pg.evaluate(BOXES)[0]
    assert not overlap(p["flags"][0], p["over"])
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: false } })")   # off: no label left behind
    pg.wait_for_function("!document.querySelector('.plot .u-cursor-layer').dataset.flags")


def test_a_double_click_plots_a_signal_once(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").dblclick()
    pg.wait_for_selector(".plot .chip")
    pg.wait_for_timeout(300)
    assert pg.locator(".plot .chip").count() == 1                      # exactly one new chip (it added and removed)
    assert S(pg, "s.ws.tabs[0].plots[0].signals.length") == 1
    sig(pg, "RPM").click()                                             # a single click: as before - adds...
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 2")
    pg.wait_for_timeout(450)                                           # (not the second click of a double-click)
    sig(pg, "RPM").click()                                             # ... and a second single click removes
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 1")
    pg.wait_for_timeout(450)
    sig(pg, "Speed").dblclick()                                        # on a plotted signal: it stays plotted
    pg.wait_for_timeout(300)
    assert [c.strip() for c in pg.locator(".plot .chip .nm").all_inner_texts()] == ["Speed"]
