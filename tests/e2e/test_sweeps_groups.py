"""MF00: groups of sets in the Sweeps area - the brush saved as a group (live / frozen), its count,
colour by group, the eye, the table's status and chips, and a study saved without groups opening
with the automatic groups only."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _bar_menu, _fresh, _step, _the_goal  # noqa: E402


def _rows(pg):
    return pg.locator(".sw-table-wrap .sw-table tbody tr").count()


def _brush(pg):
    b = pg.locator(".pp canvas").bounding_box()
    x = b["x"] + 56
    pg.mouse.move(x, b["y"] + 50); pg.mouse.down(); pg.mouse.move(x, b["y"] + 150, steps=5); pg.mouse.up()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 1 filters')")


def test_old_study_opens_with_automatic_groups_only(pg):
    _fresh(pg)
    _the_goal(pg)
    _bar_menu(pg, "Study", "Save the study")
    save_as(pg, "nogroups.svsweep")
    pg.wait_for_selector(".toast:has-text('Saved')")
    _bar_menu(pg, "Open", "Open a saved study")
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .fs-row", has_text="nogroups.svsweep").click(); pg.click(".dialog-foot .btn.primary")
    # the study opens a moment later and shows its saved step: a click before that is undone by it,
    # so go to the results until they stay (the end state), not once
    for _ in range(20):
        pg.locator(".sw-area-btn[data-area='explore']").click()
        if pg.locator(".sw-step-btn[data-step='results']").count():
            break
        pg.wait_for_timeout(500)
    _step(pg, "results")
    pg.wait_for_selector(".sw-groups .sw-group[data-group='all']")
    assert pg.locator(".sw-groups .sw-group:not(.auto)").count() == 0
    holds = pg.locator(".sw-group[data-group='holds'] .sw-group-n").inner_text()
    assert int(holds.replace(",", "")) == int(pg.locator(".sw-answer-n").inner_text().split()[0].replace(",", ""))


def test_brush_to_group_colour_eye_and_table(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table tbody tr")
    total = _rows(pg)
    _brush(pg)
    kept = _rows(pg)
    assert 0 < kept < total
    pg.locator(".sw-groups .btn", has_text="Save as group").click()
    g = pg.locator(".sw-groups .sw-group:not(.auto)").first
    g.wait_for()
    assert int(g.locator(".sw-group-n").inner_text().replace(",", "")) == kept
    assert "❄" not in g.locator(".sw-group-name").inner_text()                 # live by default
    # the brush is cleared, the plot coloured by group, the table shows the group's chips
    pg.wait_for_function(f"document.querySelectorAll('.sw-table-wrap .sw-table tbody tr').length === {total}")
    assert pg.locator(".sw-colour-key").inner_text().find("Groups") >= 0
    assert pg.locator(".sw-chips .sw-chip").count() > 0
    # every row has a status
    assert pg.locator(".sw-sets-table tbody tr[data-status]").count() == total
    # the eye takes the group's sets off the table
    g.locator("button[aria-label='Hide from the plots and the table']").click()
    pg.wait_for_function(f"document.querySelectorAll('.sw-table-wrap .sw-table tbody tr').length === {total - kept}")
    g.locator("button[aria-label='Show in the plots and the table']").click()
    pg.wait_for_function(f"document.querySelectorAll('.sw-table-wrap .sw-table tbody tr').length === {total}")
    # Shift saves the sets of now, frozen; undo takes it back
    _brush(pg)
    pg.locator(".sw-groups .btn", has_text="Save as group").click(modifiers=["Shift"])
    pg.wait_for_function("document.querySelectorAll('.sw-groups .sw-group:not(.auto)').length === 2")
    assert "❄" in pg.locator(".sw-groups .sw-group:not(.auto)").nth(1).inner_text()
    pg.keyboard.press("Control+z")
    pg.wait_for_function("document.querySelectorAll('.sw-groups .sw-group:not(.auto)').length === 1")
