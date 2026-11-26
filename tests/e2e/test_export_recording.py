"""
E1: Export recording… - a part of a recording as a new file (TopBar, beside Save; Ctrl+K): the signals on
screen at a chosen rate, as Parquet - and the file opens again in the app with the same signals.
"""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, file_menu, open_files, pg, save_as, sig  # noqa: E402,F401


def test_export_part_at_a_rate_and_open_it_again(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    sig(pg, "Gear").click()
    file_menu(pg, "Export recording…")
    dlg = pg.locator(".xr-dialog")
    dlg.wait_for()
    assert "(2)" in dlg.locator("label", has_text="In the plots on screen").inner_text()
    dlg.locator("label", has_text="One time base at").locator("input[type=radio]").check()
    dlg.locator(".xr-hz").fill("20")
    dlg.locator(".xr-go").click()
    save_as(pg, "part.parquet")
    pg.wait_for_selector(".toast:has-text('part.parquet')")
    out = os.path.join(pg.env["out"], "part.parquet")
    import pandas as pd
    df = pd.read_parquet(out)
    assert list(df.columns) == ["Time", "Speed", "Gear"] and len(df) == 600   # 0 .. 29.95 s at 20 Hz
    assert set(df["Gear"].unique()) <= {0.0, 1.0, 2.0, 3.0, 4.0}                      # held, never between
    assert os.path.exists(os.path.join(pg.env["out"], "part.export.json"))
    # Ctrl+K reaches the same dialog
    pg.keyboard.press("Control+k"); pg.keyboard.type("Export recording"); pg.keyboard.press("Enter")
    pg.locator(".xr-dialog").wait_for()
    pg.keyboard.press("Escape")
    pg.locator(".xr-dialog").wait_for(state="detached")
