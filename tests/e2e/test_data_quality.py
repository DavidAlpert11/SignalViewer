"""
26.U7: a per-signal data-quality summary when a file opens - a note (with Show), a badge on the file,
a mark on its signals, and the dialog listing each signal's missing values, gaps, repeated or backwards
time stamps and rate changes; a clean file says nothing.
"""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def _write(folder):
    rows = ["time,Good,Holes,Mode"]
    t = 0.0
    for i in range(600):
        t = i * 0.01 if i < 300 else 3.0 + (i - 300) * 0.1 + (2.0 if i >= 450 else 0)   # 100 Hz, 10 Hz, a 2 s gap
        holes = "" if 100 <= i < 140 else f"{(i % 9) * 0.37:.3f}"
        rows.append(f"{t:.3f},{(i % 5) * 1.3:.2f},{holes},{1 if i < 200 else 2}")
    rows.append(rows[-1])                                         # a repeated last row: a repeated time
    with open(os.path.join(folder, "messy.csv"), "w") as f:
        f.write("\n".join(rows) + "\n")


def test_messy_file_is_summarised(pg):
    _write(pg.env["data"])
    open_files(pg, "messy.csv")
    pg.wait_for_function("(window.__sv.state().toasts || []).some(t => t.text.includes('need a look'))", timeout=20000)
    note = S(pg, "s.toasts.find(t => t.text.includes('need a look')).text")
    assert "messy.csv" in note and "2 of 3 signals" in note and "missing values (1)" in note and "gaps (2)" in note and "rate changes (2)" in note
    badge = pg.locator(".run-head .dq-badge")
    assert badge.inner_text().strip().startswith("!")
    assert sig(pg, "Holes").locator(".dq-sig").count() == 1 and sig(pg, "Mode").locator(".dq-sig").count() == 0   # a state: logged on change
    assert "40 samples missing" in sig(pg, "Holes").locator(".dq-sig").get_attribute("title")
    badge.click()
    dlg = pg.locator(".dq-dialog")
    dlg.wait_for()
    text = dlg.inner_text()
    assert "Holes" in text and "40 samples missing" in text and "rate changes from 100 to 10 Hz" in text
    assert "gap(s) with no data" in text and "same time as the one before" in text
    assert "Mode" not in dlg.locator("tbody").inner_text()                           # nothing to say about it
    dlg.locator("button", has_text="Every signal").click()
    assert "Mode" in dlg.locator("tbody").inner_text()
    dlg.locator("tbody button", has_text="Holes").click()                            # plot it
    pg.wait_for_selector(".dq-dialog", state="detached")
    assert any(x["sig"].endswith("/Holes") for x in S(pg, "s.ws.tabs[0].plots[0].signals"))


def test_a_clean_file_says_nothing_and_the_menu_opens_the_summary(pg):
    open_files(pg, "run_a.csv")
    pg.wait_for_function("Object.keys(window.__sv.state().quality).length === 1", timeout=20000)
    assert pg.locator(".run-head .dq-badge").count() == 0
    assert S(pg, "s.toasts.filter(t => t.text.includes('need a look')).length") == 0
    pg.locator(".run-head").first.click(button="right")
    pg.locator(".menu.ctx button", has_text="Data quality…").click()
    assert "Nothing to say" in pg.locator(".dq-dialog").inner_text()
