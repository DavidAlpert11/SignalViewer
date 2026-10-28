"""Investigation step 3: the stretches of the condition in focus - the table, together in one plot,
what differs inside them.

    python -m pytest tests/e2e/test_occurrences.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_conditions import _new, _panel  # noqa: E402
from test_features import S, env, menu_item, open_files, pg, sig  # noqa: E402,F401


def _focused(pg, files=("run_a.csv",), text="Gear >= 2"):
    open_files(pg, *files)
    sig(pg, "Speed").click()
    _panel(pg)
    _new(pg, "High gear", text)
    pg.click(".cond-save")
    pg.wait_for_function("Object.values(window.__sv.state().condResults).length === 1")
    pg.click(".cond-name")
    pg.wait_for_selector(".occ-table tbody tr")


def test_table_sorts_and_goes_to_a_stretch(pg):
    _focused(pg, ("run_a.csv", "run_b.csv"))
    assert pg.locator(".occ-table tbody tr").count() == 2                # one stretch per file
    assert pg.locator(".occ-table th", has_text="File").count() == 1
    pg.select_option(".occ-sig", "Gear")
    pg.select_option(".occ-stat", "max")
    pg.wait_for_function("[...document.querySelectorAll('.occ-table tbody tr td:last-child')].every(td => td.textContent.trim() === '4')")
    pg.locator(".occ-table th button", has_text="length").click()
    pg.locator(".occ-table tbody tr").first.click()
    pg.wait_for_function("window.__sv.state().cursor.dual && window.__sv.state().cursor.t1 >= 12")


def test_together_in_a_new_tab(pg):
    _focused(pg)
    pg.click(".occ-overlay")
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2")
    p = S(pg, "s.ws.tabs[1].plots[0]")
    assert p["mode"] == "occ" and p["occ"]["align"] == "start" and p["signals"][0]["sig"].endswith("/Gear")
    pg.wait_for_selector(".occ-caption")
    assert "1 stretches" in pg.inner_text(".occ-caption")
    pg.locator(".occ-align", has_text="end").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[1].plots[0].occ.align === 'end'")


def test_what_differs_inside(pg):
    _focused(pg, text="Speed > 30")
    pg.click(".occ-differ")
    pg.wait_for_selector(".occ-differ-list li")
    top = pg.locator(".occ-differ-list li button").all_inner_texts()[:2]
    assert set(top) == {"Speed", "RPM"}
    # a click: RPM in a plot of its own (not squeezed into the active plot); Ctrl+click: into the active one
    pg.locator(".occ-differ-list li button", has_text="RPM").click()
    pg.wait_for_function("(() => { const tb = window.__sv.state().ws.tabs[0]; const p = tb.plots[tb.active];"
                         " return p.signals.length && p.signals.every(x => x.sig.endsWith('/RPM')); })()")
    pg.locator(".occ-differ-list li button", has_text="Speed").click(modifiers=["Control"])
    pg.wait_for_function("(() => { const tb = window.__sv.state().ws.tabs[0]; const p = tb.plots[tb.active];"
                         " return p.signals.some(x => x.sig.endsWith('/RPM')) && p.signals.some(x => x.sig.endsWith('/Speed')); })()")
