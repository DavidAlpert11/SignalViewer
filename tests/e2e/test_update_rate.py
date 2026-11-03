"""Create signals: a derivative / integral of a signal that updates slower than it is logged
(owner, 2026-11-03) - its own rate, or a 0 / 1 flag that marks its updates."""
import math
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def _write(folder):
    rows = ["time,Slow,Updated"]
    for i in range(400):                                          # logged at 100 Hz, computed at 10 Hz
        t = i / 100
        held = math.sin(math.pi * (i // 10) / 10)
        rows.append(f"{t:.2f},{held:.6f},{1 if i % 10 == 0 else 0}")
    with open(os.path.join(folder, "slow_signal.csv"), "w") as f:
        f.write("\n".join(rows) + "\n")


@pytest.mark.parametrize("mode", ["hz", "flag"])
def test_derivative_of_the_updates(pg, mode):
    _write(pg.env["data"])
    open_files(pg, "slow_signal.csv")
    sig(pg, "Slow").click()
    pg.click("[aria-label='Create signals']")
    pg.locator(".analysis .afield select").first.select_option("derivative")
    box = pg.locator(".upd-field")
    box.locator("select[aria-label='Updates of the signal']").select_option(mode)
    if mode == "hz":
        box.locator("input[aria-label='Its rate (Hz)']").fill("10")
    else:
        box.locator(".picker-btn").click(); pg.keyboard.type("Updated"); pg.keyboard.press("Enter")
    before = S(pg, "s.runs.flatMap(r => r.signals).length")
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function(f"window.__sv.state().runs.flatMap(r => r.signals).length > {before}")
    name = S(pg, "s.runs.find(r => r.format === 'derived').signals.slice(-1)[0].name")
    assert "derivative" in name.lower() and ("10 Hz" in name or "when Updated" in name), name
