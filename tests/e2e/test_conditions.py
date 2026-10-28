"""Investigation step 2: named conditions - written, found from a selection, edited with a live
count, stepped through, combined, hidden, deleted with undo.

    python -m pytest tests/e2e/test_conditions.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, menu_item, open_files, pg, sig  # noqa: E402,F401


def _panel(pg):
    pg.click("nav.rail button[aria-label='Investigate']")
    pg.wait_for_selector(".investigate")


def _new(pg, name, text):
    pg.click(".cond-new")
    pg.fill(".cond-name-in", name)
    pg.fill(".cond-editor [aria-label='When']", text)
    pg.wait_for_function("/stretch/.test(document.querySelector('.cond-preview').textContent)")


def test_write_a_condition_and_step_to_it(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    _panel(pg)
    _new(pg, "Fast", "Speed > 30")
    assert "1 stretch" in pg.inner_text(".cond-preview")
    pg.click(".cond-save")
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).length === 1")
    pg.wait_for_function("Object.values(window.__sv.state().condResults).length === 1")
    assert pg.inner_text(".cond-count").strip() == "1"
    pg.click(".cond-name")                                             # the next stretch: cursors on it
    pg.wait_for_function("window.__sv.state().cursor.dual && window.__sv.state().condFocus !== null")
    c = S(pg, "s.cursor")
    assert 3 < c["t1"] < 7 and 17 < c["t2"] < 22


def test_find_similar_from_the_selection(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 1")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 8, t2: 12, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-find")
    pg.wait_for_selector(".cond-editor")
    text = pg.input_value(".cond-editor [aria-label='When']")
    assert text.startswith("Speed > ")
    pg.wait_for_function("/stretch/.test(document.querySelector('.cond-preview').textContent)")
    pg.click(".cond-save")
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).length === 1")


def test_edit_shows_the_change_and_why_it_never_holds(pg):
    open_files(pg, "run_a.csv")
    _panel(pg)
    _new(pg, "Fast", "Speed > 30")
    pg.click(".cond-save")
    pg.wait_for_function("Object.values(window.__sv.state().condResults).length === 1")
    pg.click(".cond-more"); menu_item(pg, "Edit")
    pg.fill(".cond-editor [aria-label='When']", "Speed > 99")
    pg.wait_for_function("/1 → 0/.test(document.querySelector('.cond-preview').textContent)")
    assert "Never holds" in pg.inner_text(".cond-preview") and "Speed" in pg.inner_text(".cond-preview")


def test_combine_hide_and_delete_with_undo(pg):
    open_files(pg, "run_a.csv")
    _panel(pg)
    _new(pg, "Fast", "Speed > 30"); pg.click(".cond-save")
    _new(pg, "High gear", "Gear >= 2"); pg.click(".cond-save")
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).length === 2")
    pg.locator(".cond-more").first.click(); menu_item(pg, "And with: High gear")
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).length === 3")
    pg.wait_for_function("(() => { const s = window.__sv.state(); const c = s.ws.conditions[2]; const r = s.condResults[c.id]; return r && Object.values(r)[0].count >= 1; })()")
    pg.locator(".cond-eye").first.click()
    pg.wait_for_function("window.__sv.state().ws.conditions[0].visible === false")
    pg.locator(".cond-more").first.click(); menu_item(pg, "Delete (and the 1 combined from it)")
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).length === 1")
    pg.locator(".toast", has_text="Condition deleted").locator("button", has_text="Undo").click()
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).length === 3")


def test_a_number_with_an_exponent_in_a_condition(pg):
    """Speed > 3e1 used to look for a signal called e3 / e1 ("missing")."""
    open_files(pg, "run_a.csv")
    _panel(pg)
    _new(pg, "Fast", "Speed > 3e1")
    assert "1 stretch." in pg.inner_text(".cond-preview")
