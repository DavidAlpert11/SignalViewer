"""N7: primary / secondary objects (Tacview-like) - the defaults by class, the relation box at the cursor
(equal to the backend's derived signals), swapping and cycling with the keys, and the over-time
actions: the relation, error signals, comparison in NED and ECEF.

    python -m pytest tests/e2e/test_object_relations.py -q
"""
import os
import re
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, menu_item, open_files, pg  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEO = "s.ws.tabs[0].plots.find((p) => p.mode === 'geo')"


@pytest.fixture()
def three(pg):
    shutil.copy(os.path.join(ROOT, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_selector(".rel-panel")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, t1: 60 } })")
    return pg


def _chip(pg, name):
    return pg.locator(".obj-chip", has_text=name)


def _derived(pg, name):
    return pg.evaluate(f"(window.__sv.state().runs.find((r) => r.format === 'derived')?.signals ?? []).find((s) => s.name === {name!r})?.id ?? null")


def _value_at(pg, sid, t):
    return pg.evaluate(f"fetch('/api/cursor', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ signals: [{sid!r}], t: {t} }}) }}).then(r => r.json()).then(r => r.values[{sid!r}])")


def test_defaults_swap_and_cycle(three):
    pg = three
    assert "primary" in _chip(pg, "phys").get_attribute("class") and "secondary" in _chip(pg, "nav").get_attribute("class")
    assert "nav" in pg.locator(".rel-head").inner_text() and "phys" in pg.locator(".rel-head").inner_text()
    pg.locator(".plot-canvas.geo").focus()
    pg.keyboard.press("x")                                                # swap
    pg.wait_for_function("document.querySelector('.obj-chip.primary')?.textContent.includes('nav')")
    assert "secondary" in _chip(pg, "phys").get_attribute("class")
    pg.keyboard.press("q")                                                # next primary
    pg.wait_for_function("document.querySelector('.obj-chip.primary')?.textContent.includes('gps')")
    pg.keyboard.press("Control+z"); pg.keyboard.press("Control+z")        # one undo each
    pg.wait_for_function("document.querySelector('.obj-chip.primary')?.textContent.includes('phys')")
    _chip(pg, "gps").click(button="right")                               # the chip's menu
    menu_item(pg, "Set as secondary")
    pg.wait_for_function("document.querySelector('.obj-chip.secondary')?.textContent.includes('gps')")
    geo = S(pg, GEO)
    gps = [o for o in geo["objects"] if o["name"] == "gps"][0]
    assert geo["relatedObjects"][0] == gps["id"]


def test_panel_equals_the_backend_and_plot_the_relation(three):
    pg = three
    pg.locator(".rel-plot").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2")
    tab = S(pg, "s.ws.tabs[1]")
    assert tab["name"] == "nav vs phys" and len(tab["plots"]) == 4
    rng, brg = _derived(pg, "nav_vs_phys.rel.range"), _derived(pg, "nav_vs_phys.rel.bearing")
    assert rng and brg and _derived(pg, "nav_vs_phys.rel.closure")
    pg.evaluate("window.__sv.setState({ ws: { ...window.__sv.state().ws, activeTab: window.__sv.state().ws.tabs[0].id } })")
    pg.wait_for_selector(".rel-panel .rel-body")
    txt = pg.locator(".rel-panel .rel-body").inner_text()
    shown = float(re.search(r"Range\s+([\d.,]+) m", txt).group(1))
    assert abs(shown - _value_at(pg, rng, 60)) <= 0.51                   # the box rounds to the metre
    shown_b = float(re.search(r"Bearing\s+([\d.,]+)°", txt).group(1).replace(",", ""))
    b = _value_at(pg, brg, 60)
    assert abs((shown_b - b + 180) % 360 - 180) < 0.6


def test_error_signals_and_compare_in_frames(three):
    pg = three
    pg.locator(".rel-errors").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2")
    for k in ("horiz", "vert", "3d", "hdg", "roll", "pitch"):
        assert _derived(pg, f"nav_vs_phys.err.{k}"), k
    # the receiver (attitude from motion): its heading error is against its course, and named so
    pg.evaluate("window.__sv.setState({ ws: { ...window.__sv.state().ws, activeTab: window.__sv.state().ws.tabs[0].id } })")
    _chip(pg, "gps").click(button="right")
    menu_item(pg, "Error signals")
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 3")
    assert _derived(pg, "gps_vs_phys.err.hdg_cog") and not _derived(pg, "gps_vs_phys.err.roll")
    pg.evaluate("window.__sv.setState({ ws: { ...window.__sv.state().ws, activeTab: window.__sv.state().ws.tabs[0].id } })")
    pg.locator(".rel-compare select").select_option("ned")
    pg.locator(".rel-compare-btn").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 4")
    tab = S(pg, "s.ws.tabs[3]")
    assert [p["title"].split(" ")[0] for p in tab["plots"][:3]] == ["Δnorth", "Δeast", "Δdown"]
    assert len(tab["plots"][0]["signals"]) == 2                          # nav and gps, each against phys
    # the velocities: nav and phys have vel.north / east (gps has none): their difference, one plot
    assert tab["plots"][4]["title"] == "Velocity difference (m/s, NED)" and len(tab["plots"][4]["signals"]) == 3
    assert abs(_value_at(pg, _derived(pg, "nav_vs_phys.dvned.north"), 60)) < 0.6     # 0.1 m/s of noise
    north = _derived(pg, "nav_vs_phys.dned.north")
    # the fixture's navigation drifts 0.02 m/s north (with 0.3 m of noise): about 1.2 m north at 60 s
    assert abs(_value_at(pg, north, 60) - 1.2) < 1.5
    pg.evaluate("window.__sv.setState({ ws: { ...window.__sv.state().ws, activeTab: window.__sv.state().ws.tabs[0].id } })")
    pg.locator(".rel-compare select").select_option("ecef")
    pg.locator(".rel-compare-btn").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 5")
    x, y, z = (_value_at(pg, _derived(pg, f"nav_vs_phys.decef.{a}"), 60) for a in "xyz")
    e = _value_at(pg, _derived(pg, "nav_vs_phys.err.3d"), 60)
    assert abs((x * x + y * y + z * z) ** 0.5 - e) < 1e-3                 # the same vector in another frame


def test_overlay_in_ned_shares_the_primary_origin(three):
    pg = three
    pg.locator(".rel-compare select").select_option("ned")
    pg.locator(".rel-overlay-btn").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2")
    tab = S(pg, "s.ws.tabs[1]")
    assert len(tab["plots"]) == 3 and len(tab["plots"][0]["signals"]) == 3          # phys, nav, gps on one plot
    sigs = pg.evaluate("Object.fromEntries((window.__sv.state().runs.find((r) => r.format === 'derived')?.signals ?? []).map((s) => [s.name, s.id]))")
    pn = [v for k, v in sigs.items() if k.startswith("phys_ned_from_phys") and k.endswith(".N")][0]
    nn = [v for k, v in sigs.items() if k.startswith("nav_ned_from_phys") and k.endswith(".N")][0]
    assert abs(_value_at(pg, pn, 0)) < 1e-6                                         # the origin: phys at its start
    assert abs(_value_at(pg, nn, 60) - _value_at(pg, pn, 60) - 1.2) < 1.5          # nav ~1.2 m north of phys
    pg.evaluate("window.__sv.setState({ ws: { ...window.__sv.state().ws, activeTab: window.__sv.state().ws.tabs[0].id } })")
    pg.locator(".rel-compare select").select_option("track")
    assert pg.locator(".rel-overlay-btn").is_disabled()                             # track: differences only


def test_compare_offer_after_add_all(three):
    pg = three
    offer = pg.locator(".obj-compare-offer")
    offer.locator("select").select_option("enu")
    offer.locator(".obj-compare-make").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2")
    assert [p["title"].split(" ")[0] for p in S(pg, "s.ws.tabs[1].plots")[:3]] == ["Δeast", "Δnorth", "Δup"]
    pg.wait_for_selector(".obj-compare-offer", state="detached")
