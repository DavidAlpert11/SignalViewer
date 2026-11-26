"""FL1 (owner, 2026-11-16): a folder of recordings summed up as one Sweeps table - a row per recording, the same
measures in each, parameters from the names - and the rows' recordings opened together in Recordings. Two ways in:
the welcome card (examples/folder_of_flights with its measures.json) and Sweeps > Data > From a folder of
recordings (no measures.json: the first recording opens with the Runs matrix to define them on it)."""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, open_example  # noqa: E402,F401

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "folder_of_flights")


def test_the_card_sums_up_the_folder_and_opens_ticked_rows_together(pg):
    pg.wait_for_selector(".ex-card")
    open_example(pg, "folderOfFlights")                                             # CC16: Help -> Examples, Many runs
    pg.wait_for_function("window.__sv.state().area === 'sweeps'", timeout=60000)
    rows = pg.locator(".sw-raw tbody tr")
    rows.nth(9).wait_for(timeout=60000)
    assert [h.strip() for h in pg.locator(".sw-raw thead th").all_inner_texts()][1:] == \
        ["recording", "vehicle", "date", "vibration_max", "battery_min_V"]
    assert rows.nth(0).locator("td").nth(1).inner_text() == "X8-A_2026-09-02.bin"  # the file's name, its folder in the tooltip
    assert pg.locator(".sw-open-ticked").is_disabled()
    rows.nth(0).locator("input[type=checkbox]").check()
    rows.nth(5).locator("input[type=checkbox]").check()                              # X8-A's last flight: vibration 67
    assert pg.locator(".sw-open-ticked").inner_text() == "Open 2 in Recordings"
    pg.click(".sw-open-ticked")
    pg.wait_for_function("window.__sv.state().area === 'recordings' && window.__sv.state().runs.length === 2", timeout=60000)
    names = pg.evaluate("window.__sv.state().runs.map((r) => r.name)")
    assert sorted(names) == ["X8-A_2026-09-02.bin", "X8-A_2026-10-07.bin"], names


def test_a_folder_without_measures_is_defined_on_its_first_recording(pg, tmp_path):
    d = tmp_path / "flights"
    d.mkdir()
    for n in ("X8-B_2026-09-05.bin", "X8-B_2026-10-17.bin"):
        shutil.copy(os.path.join(EXAMPLE, n), d / n)
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.locator(".topbar .file-menu-btn").click()                             # W16: folders open from Open ▾
    pg.locator(".menu.ctx button", has_text="From a folder of recordings").click()
    goto_folder(pg, str(d))
    pg.click(".dialog button:has-text('Use this folder')")
    pg.wait_for_selector(".mx-folder-step", timeout=60000)                           # the step it waits on, said
    assert "flights" in pg.locator(".mx-folder-step").inner_text()
    assert pg.evaluate("window.__sv.state().runs.map((r) => r.name)") == ["X8-B_2026-09-05.bin"]
    pg.locator(".mx-add-measure").click()
    pg.fill(".mx-sig", "BAT[0].Volt")
    pg.select_option(".mx-op", "min")
    pg.press(".mx-sig", "Enter")
    pg.locator(".mx-sum-folder", has_text="Summarize flights").click()               # no folder asked again
    pg.wait_for_function("window.__sv.state().area === 'sweeps'", timeout=60000)
    rows = pg.locator(".sw-raw tbody tr")
    rows.nth(1).wait_for(timeout=60000)
    assert rows.count() == 2
    assert float(rows.nth(1).locator("td").last.inner_text()) < 14                  # the worn battery's flight


@pytest.mark.parametrize("lang", ["en", "he"])
def test_a_folder_of_recordings_reads_as_recordings(pg, lang):
    """M34 FR5: steps Data -> Columns -> Limits -> Results; no Send runs, no Next runs, no "sets hold"; the status
    line counts recordings; the demo's line names the copter and its one button shows it."""
    import re
    pg.wait_for_selector(".ex-card")
    open_example(pg, "folderOfFlights")                                             # (Help -> Examples, in English)
    if lang == "he":
        pg.evaluate("window.__sv.setState({ lang: 'he' })")
    pg.wait_for_selector(".sw-raw tbody tr:nth-child(10)", timeout=60000)
    guide = pg.locator(".demo-guide[data-demo='folderOfFlights']")
    guide.wait_for(timeout=30000)
    assert "X8-A" in guide.inner_text()                                     # the line names the copter
    assert pg.eval_on_selector_all(".sw-steps .sw-step-btn", "els => els.map((e) => e.dataset.flow)") == ["data", "columns", "goal", "results"]
    assert pg.locator(".sw-nav [data-nav='setup']").count() == 0            # no Send runs
    status = pg.locator(".app > .status, footer.status").last.inner_text()
    assert ("10 recordings" if lang == "en" else "10 הקלטות") in status
    words = re.compile(r"\bsets?\b|send runs|next runs|sets hold" if lang == "en" else r"סטים|לשלוח ריצות|הריצות הבאות")

    def no_words():
        txt = pg.locator(".app").inner_text()
        assert not words.search(txt.lower()), words.search(txt.lower())

    no_words()
    guide.locator(".btn.primary").click()                                   # its one button shows X8-A's six flights
    pg.wait_for_function("document.querySelectorAll('.sw-raw tbody input:checked').length === 6")
    first = [r.split("\t") for r in pg.locator(".sw-raw tbody tr").all_inner_texts()[:6]]
    assert all("X8-A" in r[2] for r in first), first                        # sorted by vibration: X8-A's six on top
    assert pg.locator(".sw-open-ticked").inner_text() == ("Open 6 in Recordings" if lang == "en" else pg.locator(".sw-open-ticked").inner_text())
    assert pg.locator(".demo-guide .btn.primary").count() == 0              # not offered again
    no_words()
    pg.click(".sw-step-btn[data-flow='results']")
    pg.wait_for_timeout(800)
    no_words()


def test_a_results_table_still_has_its_five_steps(pg):
    open_example(pg, "sweepTable")
    pg.wait_for_function("document.querySelectorAll('.sw-steps .sw-step-btn').length === 5", timeout=60000)
    pg.click(".sw-step-btn[data-flow='data']")                              # the tables list (Data): Send runs, as before
    pg.wait_for_selector(".sw-nav [data-nav='setup']", timeout=30000)
    assert pg.locator(".sw-step-btn[data-flow='goal'] b").inner_text() == "Goal"
