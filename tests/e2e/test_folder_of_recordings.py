"""FL1 (owner, 2026-11-16): a folder of recordings summed up as one Sweeps table - a row per recording, the same
measures in each, parameters from the names - and the rows' recordings opened together in Recordings. Two ways in:
the welcome card (examples/folder_of_flights with its measures.json) and Sweeps > Data > From a folder of
recordings (no measures.json: the first recording opens with the Runs matrix to define them on it)."""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg  # noqa: E402,F401

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "folder_of_flights")


def test_the_card_sums_up_the_folder_and_opens_ticked_rows_together(pg):
    pg.wait_for_selector(".examples-group")
    groups = pg.locator(".examples-group").evaluate_all("els => els.map((g) => [...g.querySelectorAll('.ex-card')].map((c) => c.dataset.example))")
    assert "folderOfFlights" in groups[0], groups                                   # a Recordings demo
    pg.locator(".ex-card[data-example='folderOfFlights']").click()
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
    pg.locator(".areabar .btn", has_text="Open").click()                             # W16: folders open from Open ▾
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
