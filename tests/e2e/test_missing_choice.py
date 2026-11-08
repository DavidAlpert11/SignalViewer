"""C3b (owner, 2026-11-08): Create signals offers the missing-data choice for the several-signal
operations and the integral - a missing input keeps the result missing (default) or is left out, and a
signal made with "skip" is marked in the list of derived signals."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def _write(folder):
    rows = ["time,A,B"]
    for i in range(200):
        b = "" if 50 <= i < 60 else f"{i / 10:.1f}"            # B has a gap of 10 samples
        rows.append(f"{i / 100:.2f},1,{b}")
    with open(os.path.join(folder, "holes.csv"), "w") as f:
        f.write("\n".join(rows) + "\n")


def _derived(pg):
    return S(pg, "(s.runs.find(r => r.format === 'derived')?.signals ?? []).map(x => ({ name: x.name, nan: x.params?.nan, q: x.quality ?? null }))")


def test_sum_propagate_then_skip_is_marked(pg):
    _write(pg.env["data"])
    open_files(pg, "holes.csv")
    sig(pg, "A").click(); sig(pg, "B").click()
    pg.click("[aria-label='Create signals']")
    pg.click(".seg.wide button:has-text('Several')")
    pg.click(".msp-top .linklike:has-text('From the active plot')")
    pg.locator(".analysis .afield select").first.select_option("sum")
    box = pg.locator(".nan-field")
    assert box.locator("select").input_value() == "propagate"           # the default: nothing left out
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 1")
    box.locator("select").select_option("skip")
    assert "marked" in box.inner_text()
    pg.click(".msp-top .linklike:has-text('From the active plot')")
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 2")
    d = _derived(pg)
    assert [x["nan"] for x in d] == ["propagate", "skip"], d
    assert d[0]["q"] is None and d[1]["q"]["skipped"] == 10, d
    marks = pg.locator(".dsig .dsig-quality")
    assert marks.count() == 1 and "skipped" in marks.first.inner_text()
    assert "10 samples" in marks.first.get_attribute("title")


def test_integral_choice_only_where_it_applies(pg):
    _write(pg.env["data"])
    open_files(pg, "holes.csv")
    sig(pg, "B").click()
    pg.click("[aria-label='Create signals']")
    op = pg.locator(".analysis .afield select").first
    op.select_option("derivative")
    assert pg.locator(".nan-field").count() == 0                      # a derivative has no choice
    op.select_option("integral")
    pg.locator(".nan-field select").select_option("skip")
    assert "Bridge" in pg.locator(".nan-field select option:checked").inner_text()
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 1")
    d = _derived(pg)
    assert d[0]["nan"] == "skip" and len(d[0]["q"]["bridged"]) == 1, d
    assert "bridged" in pg.locator(".dsig .dsig-quality").inner_text()
    pg.click("button:has-text('Change this signal')")                    # in place: no choice (a transform)
    assert pg.locator(".nan-field").count() == 0
