"""N1: the signal list nests names by "." and "/" always and at any depth - the round's 19-signal
fixture (phys / nav / gps) and a three-level .mat struct; inside a group only the rest of the name
shows, the full name stays in the tooltip, in search and in drag and drop.

    python -m pytest tests/e2e/test_name_tree.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg, S  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _files(pg):
    d = pg.env["data"]
    shutil.copy(os.path.join(ROOT, "examples", "three_objects.csv"), d)
    import numpy as np
    import scipy.io
    t = np.linspace(0, 10, 101)
    scipy.io.savemat(os.path.join(d, "deep.mat"), {"t": t, "sim": {
        "nav": {"pos": {"x": t, "y": t * 2}, "att": {"phi": t * 0, "theta": t * 0}},
        "truth": {"pos": {"x": t, "y": t * 2}}}})
    yield


def _rows(pg):
    """The list as (kind, label, indent) from the top - groups and signals."""
    return pg.evaluate("""[...document.querySelectorAll('.tree .vrow')].map(r => {
        const g = r.querySelector('.grp-head:not(.ugroup)'), s = r.querySelector('.sig');
        const el = g || s; if (!el) return null;
        return [g ? 'g' : 's', el.querySelector('.nm').textContent.trim(), parseFloat(getComputedStyle(el).paddingInlineStart)];
    }).filter(Boolean)""")


def test_fixture_nests_by_object(pg):
    open_files(pg, "three_objects.csv")
    pg.wait_for_selector(".grp-head")
    rows = _rows(pg)
    groups = [r[1] for r in rows if r[0] == "g"]
    assert groups == ["phys", "att", "vel", "nav", "att", "vel", "gps"]
    labels = [r[1] for r in rows if r[0] == "s"]
    assert labels[:3] == ["lat", "lon", "alt"] and "roll" in labels and "north" in labels
    # deeper rows are indented further (any depth, logical padding: LTR and RTL alike)
    pad = {r[1]: r[2] for r in rows}
    assert pad["att"] > pad["phys"] and pad["roll"] > pad["att"]
    # the full name stays in the tooltip and in search
    assert pg.locator(".sig", has_text="roll").first.get_attribute("title").startswith("phys.att.roll")
    pg.fill(".filter input", "nav.att.yaw")                 # one match: no group of one signal, the full name
    pg.wait_for_function("document.querySelectorAll('.sig').length === 1")
    assert pg.locator(".sig .nm").inner_text() == "nav.att.yaw"
    pg.fill(".filter input", "nav.att")                     # three: one open group, the chain folded
    pg.wait_for_function("document.querySelectorAll('.sig').length === 3")
    assert [r[1] for r in _rows(pg)] == ["nav.att", "roll", "pitch", "yaw"]


def test_fixture_signal_plots_by_full_id(pg):
    open_files(pg, "three_objects.csv")
    pg.wait_for_selector(".grp-head")
    pg.locator(".sig", has_text="pitch").first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    sid = S(pg, "s.ws.tabs[0].plots[0].signals[0].sig")
    names = pg.evaluate(f"window.__sv.state().runs.flatMap(r => r.signals).filter(x => x.id === {sid!r}).map(x => x.name)")
    assert names == ["phys.att.pitch"]


def test_mat_struct_three_levels(pg):
    open_files(pg, "deep.mat")
    pg.wait_for_selector(".grp-head")
    groups = [r[1] for r in _rows(pg) if r[0] == "g"]
    # sim > nav > pos / att; truth has only pos, so truth.pos is one row
    assert groups == ["sim", "nav", "pos", "att", "truth.pos"]


def test_quick_chips_and_the_count_for_a_big_file(pg):
    """D2 (lane L3): the panel head counts the open signals; a big file gets quick chips under the search while it
    is in use - the groups the tab uses first - one click filters to that group, a second click shows all again."""
    from test_template_tabs import open_ardupilot_example
    open_ardupilot_example(pg)
    assert pg.locator(".quick-chips").count() == 0                  # only while the search is in use
    pg.locator(".filter input").focus()
    pg.wait_for_selector(".quick-chips .chipbtn")
    n = S(pg, "s.runs.reduce((a, r) => a + r.signals.length, 0)")
    assert pg.locator(".side-head .ph-count").inner_text().replace(",", "") == str(n)
    used = S(pg, "[...new Set(s.ws.tabs.find((t) => t.id === s.ws.activeTab).plots.flatMap((p) => p.signals.map((x) => x.sig.split('/')[1].split('.')[0])))]")
    first = pg.locator(".quick-chips .chipbtn").first
    assert first.inner_text() in used
    g = first.inner_text()
    first.click()
    assert pg.locator(".filter input").input_value() == g + "."
    assert first.get_attribute("aria-pressed") == "true"
    first.click()
    assert pg.locator(".filter input").input_value() == ""
    pg.evaluate("document.activeElement.blur()")                    # the search left: the chips go
    pg.wait_for_selector(".quick-chips", state="detached")
