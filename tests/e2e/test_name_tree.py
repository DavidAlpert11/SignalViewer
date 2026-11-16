"""N1: the signal list nests names by "." and "/" always and at any depth - the round's 19-signal
fixture (phys / nav / gps) and a three-level .mat struct; inside a group only the rest of the name
shows, the full name stays in the tooltip, in search and in drag and drop.

    python -m pytest tests/e2e/test_name_tree.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, menu_item, open_files, pg, S, settled, sig  # noqa: E402,F401

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
    """D2: the panel head counts the open signals; a big file gets quick chips under the search while it
    is in use - the groups the tab uses first - one click filters to that group, a second click shows all again."""
    from test_template_tabs import open_ardupilot_example
    open_ardupilot_example(pg)
    assert pg.locator(".quick-chips").count() == 0                  # only while the search is in use
    pg.locator(".filter input").focus()
    pg.wait_for_selector(".quick-chips .chipbtn[data-group]")
    n = S(pg, "s.runs.reduce((a, r) => a + r.signals.length, 0)")
    assert pg.locator(".side-head .ph-count").inner_text().replace(",", "") in (f"{n} signals", str(n))     # RV3: says what it counts (the word goes when narrow)
    used = S(pg, "[...new Set(s.ws.tabs.find((t) => t.id === s.ws.activeTab).plots.flatMap((p) => p.signals.map((x) => x.sig.split('/')[1].split('.')[0])))]")
    first = pg.locator(".quick-chips .chipbtn[data-group]").first     # the groups' chips (pinned searches come first)
    assert first.inner_text() in used
    g = first.inner_text()
    first.click()
    assert pg.locator(".filter input").input_value() == g + "."
    assert first.get_attribute("aria-pressed") == "true"
    first.click()
    assert pg.locator(".filter input").input_value() == ""
    pg.evaluate("document.activeElement.blur()")                    # the search left (empty): the chips go
    pg.wait_for_selector(".quick-chips", state="detached")


def test_pinned_searches_as_chips(pg):
    """D14 (2): *Pin this search* beside the search box keeps the text as a chip (in the session, with
    Undo); a click on the chip types it into the search, a second click clears it; its ✕ unpins it."""
    open_files(pg, "three_objects.csv")
    box = pg.locator(".filter input")
    box.fill("nav")
    pg.locator(".filter .pin-search").click()
    pg.wait_for_function("window.__sv.state().ws.searches?.some((x) => x.q === 'nav')")
    assert pg.locator(".filter .pin-search").count() == 0           # pinned already: no second pin
    box.fill("")
    box.focus()
    chip = pg.locator('.quick-chips .chipbtn[data-pinned="nav"]')
    chip.wait_for()
    assert chip.inner_text() == "nav"
    chip.click()
    assert box.input_value() == "nav"
    assert chip.get_attribute("aria-pressed") == "true"
    chip.click()
    assert box.input_value() == ""
    pg.locator('.quick-chips .pin-chip').filter(has=pg.locator('[data-pinned="nav"]')).locator(".iconbtn").click()
    pg.wait_for_function("!(window.__sv.state().ws.searches ?? []).length")
    pg.evaluate("document.activeElement.blur()")
    pg.keyboard.press("Control+z")                                   # through commit: Undo brings it back
    pg.wait_for_function("window.__sv.state().ws.searches?.some((x) => x.q === 'nav')")


# FR12: from the owner's notes of 2026-11-03 (1.20; the file was test_owner_notes_1_20.py)
def test_made_signal_renamed_deleted_and_grouped_from_the_list(pg):
    open_files(pg, "run_a.csv")
    rid = S(pg, "s.runs[0].id")
    r = pg.evaluate("""async (rid) => { const r = await fetch('/api/derived', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'expr', sources: [rid + '/Speed'], params: {expr: '2*v0', text: '2*{Speed}'}, name: 'twice'})}); return r.status; }""", rid)
    assert r == 200
    pg.evaluate("""async () => { const r = await fetch('/api/derived', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'expr', sources: ['derived/twice'], params: {expr: 'v0+1', text: '{twice}+1'}, name: 'plus'})}); }""")
    pg.reload(); pg.wait_for_selector(".app")
    pg.wait_for_function("window.__sv.state().runs.some((r) => r.format === 'derived') && !!window.__sv.state().ws.tabs[0].plots[0]")
    settled(pg)                                                    # the session put back first
    pg.evaluate("() => window.__sv.state().commit((ws) => { ws.tabs[0].plots[0].signals = [{sig: 'derived/twice', color: '#3D8BFD', width: 1.5, scale: 1, offset: 0}]; return ws; })")
    # rename: the plot follows
    sig(pg, "twice").click(button="right")
    menu_item(pg, "Rename")
    pg.locator(".dialog input").first.fill("doubled"); pg.keyboard.press("Enter")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals[0].sig === 'derived/doubled'")
    # a group, nested by its name
    sig(pg, "doubled").click(button="right")
    pg.locator(".menu.ctx button", has_text="Add to a group").first.hover()
    menu_item(pg, "New group")
    pg.locator(".dialog input").first.fill("Speeds/Made"); pg.keyboard.press("Enter")
    pg.wait_for_selector(".ugroups-head")
    assert [x.split("\n")[0] for x in pg.locator(".grp-head.ugroup").all_inner_texts()] == ["Speeds", "Made"]
    # delete with Del: what was made from it is asked about, both go, one Undo puts them back
    sig(pg, "doubled").focus(); pg.keyboard.press("Delete")
    pg.wait_for_selector(".dialog:has-text('plus')")
    pg.locator(".dialog-foot .btn").last.click()
    pg.wait_for_function("!window.__sv.state().runs.some((r) => r.format === 'derived' && r.signals.length)")
    assert S(pg, "s.ws.tabs[0].plots[0].signals.length") == 0
    pg.locator(".toast button:has-text('Undo')").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    assert S(pg, "s.runs.find((r) => r.format === 'derived').signals.map((x) => x.name).join()") == "doubled,plus"
