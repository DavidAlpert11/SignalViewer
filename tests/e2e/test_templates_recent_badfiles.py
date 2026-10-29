"""Templates reachable for any file type, the template editor's tab picker, recent files while a
file is open, and clear messages for damaged / unsupported files.

    python -m pytest tests/e2e/test_templates_recent_badfiles.py -q
"""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, goto_folder, menu_item, open_files, pg, sig, toast_text  # noqa: E402,F401


def test_templates_in_file_panel_for_csv(pg):
    open_files(pg, "run_a.csv")
    # the flight-log panel is not needed: the file panel offers templates for a plain CSV
    strip = pg.locator(".tpl-strip")
    strip.wait_for()
    assert strip.locator(".chipbtn").count() >= 1               # at least "Quick look"
    strip.locator(".chipbtn").first.click(button="right")         # T48: right-click = the library on it
    pg.wait_for_selector(".tpl-lib .tpl-details")
    pg.keyboard.press("Escape")
    strip.locator(".chipbtn").first.click()                       # a click opens it at once (one file)
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => p.signals.length))")
    strip.locator(".linkbtn").click()                             # "All templates…"
    pg.wait_for_selector(".tpl-lib")


def test_top_bar_templates_menu(pg):
    open_files(pg, "run_a.csv")
    pg.click(".areabar [aria-label='Templates']")
    menu_item(pg, "Open a template or collection")
    pg.wait_for_selector(".tpl-lib")
    pg.keyboard.press("Escape")
    pg.click(".areabar [aria-label='Templates']")
    menu_item(pg, "New collection")
    pg.wait_for_selector(".tpl-editor select[aria-label='Include a template']")


def test_save_template_starts_with_current_tab_then_picks_others(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()                                      # tab 1: Speed (no name of its own)
    pg.click("[aria-label='New tab']")
    sig(pg, "RPM").click()                                        # tab 2: RPM
    pg.click("[aria-label='New tab']")
    sig(pg, "Gear").click()                                       # tab 3: Gear
    pg.locator(".tab").first.click()                              # current tab: the first
    pg.locator(".tpl-strip-save").click()
    pg.wait_for_selector(".tpl-editor")
    names = pg.locator(".tpl-edit-tab input").evaluate_all("els => els.map(e => e.value)")
    assert len(names) == 1 and "Speed" in names[0]               # only the current tab, named by what it shows
    picker = pg.locator(".tpl-editor select.tpl-add-tab")
    opts = picker.locator("option").all_inner_texts()
    assert any("Speed" in o and "added" in o for o in opts)       # already in: marked, cannot be added twice
    picker.select_option(label=[o for o in opts if "Gear" in o][0])
    names = pg.locator(".tpl-edit-tab input").evaluate_all("els => els.map(e => e.value)")
    assert len(names) == 2 and "Gear" in names[1]
    opts = picker.locator("option").all_inner_texts()
    assert not any("remaining" in o for o in opts)                # only RPM is left: no "all remaining"
    rpm = [o for o in opts if "RPM" in o][0]
    picker.select_option(label=rpm)
    assert pg.locator(".tpl-edit-tab").count() == 3
    assert picker.is_disabled()                                   # nothing left to add


def test_recent_files_in_open_dialog_while_a_file_is_open(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    rid = S(pg, "s.runs.find(r => r.name === 'run_b.csv').id")
    pg.evaluate(f"fetch('/api/runs/{rid}', {{method: 'DELETE'}})")
    pg.evaluate("window.__sv.setState({ runs: window.__sv.state().runs.filter(r => r.name !== 'run_b.csv') })")
    pg.keyboard.press("Control+o")
    rec = pg.locator(".fs-recent")
    rec.wait_for()
    assert rec.locator(".fs-row", has_text="run_b.csv").count() == 1
    assert rec.locator(".fs-row", has_text="run_a.csv").count() == 0    # open files are not offered
    rec.locator(".fs-row", has_text="run_b.csv").dblclick()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'run_b.csv')", timeout=20000)


def test_recent_menu_in_file_panel(pg):
    open_files(pg, "run_a.csv", "run_c.csv")
    rid = S(pg, "s.runs.find(r => r.name === 'run_c.csv').id")
    pg.evaluate(f"fetch('/api/runs/{rid}', {{method: 'DELETE'}})")
    pg.evaluate("window.__sv.setState({ runs: window.__sv.state().runs.filter(r => r.name !== 'run_c.csv') })")
    pg.click(".side-head .split-more")
    pg.locator(".menu.ctx button", has_text="run_c.csv").click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'run_c.csv')", timeout=20000)


def test_damaged_and_unsupported_files_get_clear_messages(pg):
    d = pg.env["out"]
    open(os.path.join(d, "broken.mat"), "wb").write(b"\x01\x02 not a mat file" * 50)
    open(os.path.join(d, "empty.csv"), "wb").write(b"")
    pg.keyboard.press("Control+o")
    goto_folder(pg, d)
    pg.locator(".dialog .dialog-body .fs-row", has_text="broken.mat").first.click()
    pg.locator(".dialog .dialog-body .fs-row", has_text="empty.csv").first.click(modifiers=["Control"])
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".toast:has-text('not a valid MATLAB')")
    pg.wait_for_selector(".toast:has-text('The file is empty')")
    assert "Unexpected error" not in toast_text(pg)


def test_file_slots_follow_the_tabs(pg):
    """The files a template uses are found from its tabs: one per source file (two CSV files are NOT
    merged), named after the file; nothing to add by hand; a file whose tabs are removed goes away."""
    files = lambda: [x.split("\n")[0].strip() for x in pg.locator(".tpl-used-files li").all_inner_texts()]
    open_files(pg, "run_a.csv", "run_b.csv")
    sig(pg, "Speed", run=0).click()                               # tab 1: run_a
    pg.click("[aria-label='New tab']")
    sig(pg, "RPM", run=1).click()                                 # tab 2: run_b
    pg.click("[aria-label='New tab']")
    sig(pg, "Gear", run=0).click()                                # tab 3: run_a again
    pg.locator(".tab").first.click()
    pg.locator(".tpl-strip-save").click()
    pg.wait_for_selector(".tpl-editor")
    assert pg.locator(".tpl-editor", has_text="Add a file slot").count() == 0
    assert files() == ["run_a.csv"]
    picker = pg.locator(".tpl-editor select.tpl-add-tab")
    opts = picker.locator("option").all_inner_texts()
    picker.select_option(label=[o for o in opts if "RPM" in o][0])          # from the other CSV file
    assert files() == ["run_a.csv", "run_b.csv"]
    opts = picker.locator("option").all_inner_texts()
    picker.select_option(label=[o for o in opts if "Gear" in o][0])         # same file as tab 1
    assert files() == ["run_a.csv", "run_b.csv"]                             # shares run_a's entry
    pg.locator(".tpl-edit-tab").nth(1).locator("[aria-label='Remove']").click()   # drop the run_b tab
    assert files() == ["run_a.csv"]


def test_template_files_are_found_from_tabs_and_matched_by_name(pg):
    # saved from run_a: the editor only LISTS the files used - no slot names to type, no "add a file slot"
    open_files(pg, "run_b.csv")
    open_files(pg, "run_a.csv", clear=False)
    pg.locator(".run-head", has_text="run_a.csv").first.wait_for()
    pg.locator(".sig", has_text="Speed").nth(1).click()           # Speed of run_a (the second file)
    pg.locator(".tpl-strip-save").click()
    pg.wait_for_selector(".tpl-editor")
    files = pg.locator(".tpl-used-files li").all_inner_texts()
    assert len(files) == 1 and files[0].startswith("run_a.csv")
    assert pg.locator(".tpl-editor .fmt-chips").count() == 0
    assert pg.locator(".tpl-editor input[aria-label='File slot name']").count() == 0
    assert pg.locator(".tpl-editor", has_text="Add a file slot").count() == 0
    pg.locator(".tpl-editor input").first.fill("Speed of A")
    pg.locator(".tpl-editor .btn.primary").click()
    pg.wait_for_selector(".tpl-details h3:has-text('Speed of A')")
    # opening it: the file with the same name is used, although run_b was opened first
    pg.wait_for_selector(".tpl-slot-note:has-text('same file as when saved')")   # the binding has arrived
    sel = pg.locator(".tpl-slot select").first
    assert sel.evaluate("e => e.options[e.selectedIndex].text") == "run_a.csv"
    pg.keyboard.press("Escape")
    # without run_a open: another file is suggested, and the original can be opened from here
    rid = S(pg, "s.runs.find(r => r.name === 'run_a.csv').id")
    pg.evaluate(f"fetch('/api/runs/{rid}', {{method: 'DELETE'}})")
    pg.evaluate("window.__sv.setState({ runs: window.__sv.state().runs.filter(r => r.name !== 'run_a.csv') })")
    pg.click(".areabar [aria-label='Templates']"); menu_item(pg, "Open a template")
    pg.locator(".tpl-item", has_text="Speed of A").click()
    pg.wait_for_selector(".tpl-slot-note:has-text('run_a.csv is not open')")
    assert pg.locator(".tpl-slot select").first.evaluate("e => e.options[e.selectedIndex].text") == "run_b.csv"
    pg.locator(".tpl-slot-note .linkbtn", has_text="Open run_a.csv").click()
    pg.wait_for_selector(".tpl-slot-note:has-text('same file as when saved')", timeout=20000)
    assert pg.locator(".tpl-slot select").first.evaluate("e => e.options[e.selectedIndex].text") == "run_a.csv"


def _save_tab_as(pg, name):
    pg.locator(".tpl-strip-save").click()
    pg.wait_for_selector(".tpl-editor")
    pg.locator(".tpl-editor input").first.fill(name)
    pg.locator(".tpl-editor .btn.primary").click()
    pg.wait_for_selector(f".tpl-details h3:has-text('{name}')")


def test_new_menu_closes_and_is_hidden_while_editing(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.click(".areabar [aria-label='Templates']"); menu_item(pg, "Open a template")
    pg.locator(".tpl-side-top .btn.primary").click()
    pg.wait_for_selector(".menu.ctx")
    pg.locator(".tpl-lib .dialog-head h2").click()                # a click elsewhere in the dialog closes it
    pg.wait_for_selector(".menu.ctx", state="detached")
    pg.locator(".tpl-side-top .btn.primary").click(); menu_item(pg, "From the current tab")
    pg.wait_for_selector(".tpl-editor")
    assert pg.locator(".tpl-side-top .btn.primary").count() == 0  # already making a new template


def test_delete_template_from_list_and_editor(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    _save_tab_as(pg, "To delete A")
    pg.keyboard.press("Escape")
    _save_tab_as(pg, "To delete B")
    row = pg.locator(".tpl-item-row", has_text="To delete A")
    row.hover(); row.locator(".tpl-item-del").click()
    pg.locator(".dialog-foot .btn.primary").last.click()          # confirm
    row.wait_for(state="detached")
    # from the editor of an existing template
    pg.locator(".tpl-item", has_text="To delete B").click()
    pg.locator(".tpl-actions .btn", has_text="Edit").click()
    pg.locator(".tpl-editor .btn.danger").click()
    pg.locator(".dialog-foot .btn.primary").last.click()
    pg.locator(".tpl-item", has_text="To delete B").wait_for(state="detached")
    # built-in templates have no delete button
    assert pg.locator(".tpl-item-row", has_text="Quick look").locator(".tpl-item-del").count() == 0


def test_choose_templates_folder(pg):
    folder = os.path.join(pg.env["out"], "team_templates"); os.makedirs(folder, exist_ok=True)
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    _save_tab_as(pg, "Before move")
    pg.locator(".tpl-foot .btn", has_text="Change folder").click()
    goto_folder(pg, folder)
    assert pg.locator(".dialog .dialog-body .fs-row", has_text=".csv").count() == 0   # folders only
    pg.locator(".dialog-foot .btn.primary", has_text="Use this folder").click()
    pg.wait_for_selector(".toast:has-text('Templates are now kept in')")
    pg.wait_for_selector(f".tpl-foot code:has-text('team_templates')")
    assert os.path.isfile(os.path.join(folder, "Before-move.json"))           # the existing ones came along
    pg.locator(".tpl-item", has_text="Before move").wait_for()
    pg.keyboard.press("Escape")
    _save_tab_as(pg, "Made there")
    assert os.path.isfile(os.path.join(folder, "Made-there.json"))
    pg.locator(".tpl-foot .btn", has_text="Default folder").click()          # back (other tests use the default)
    pg.wait_for_selector(".tpl-foot code:has-text('.signalviewer')")
