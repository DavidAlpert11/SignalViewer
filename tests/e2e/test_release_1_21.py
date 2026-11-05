"""1.21: Filter review (the IMU batch sampler, the harmonic notches and the gyro low-pass on an FFT
plot), the Step response plot, the Log panel's Hardware tab and the Compare panel's time tolerance.

    python -m pytest tests/e2e/test_release_1_21.py -q
"""
import os
import sys

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, _csv, open_files, pg, env  # noqa: E402,F401

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "backend", "tests"))
from test_filter_review import _batch_log  # noqa: E402

NOTCH = {"INS_HNTCH_ENABLE": 1, "INS_HNTCH_FREQ": 43.5, "INS_HNTCH_BW": 20, "INS_HNTCH_ATT": 40,
         "INS_HNTCH_HMNCS": 3, "INS_HNTCH_MODE": 0, "INS_GYRO_FILTER": 20, "INS_GYR_ID": 3408146,
         "FRAME_CLASS": 1, "FRAME_TYPE": 1}


def _plot(pg, names, **opts):
    """The first plot of the first tab: these signals of the open .bin / .csv, and these plot options."""
    pg.evaluate("""([names, opts]) => { const st = window.__sv.state();
        const ids = names.map((n) => st.runs.flatMap((r) => r.signals).find((s) => s.name === n).id);
        const colors = ['#3D8BFD', '#E5534B', '#2FBF9F', '#F2A93B'];
        st.commit((ws) => { Object.assign(ws.tabs[0].plots[0], opts);
          ws.tabs[0].plots[0].signals = ids.map((id, i) => ({ sig: id, color: colors[i % 4], width: 1.5, scale: 1, offset: 0 }));
          return ws; }); }""", [names, opts])


def test_filter_review_and_hardware(pg):
    p = os.path.join(pg.env["data"], "batch.bin")
    if not os.path.exists(p):
        _batch_log(p, params=NOTCH)
    open_files(pg, "batch.bin")
    _plot(pg, ["ISBD[0].GyrX [rad/s]", "ISBD[0].GyrXPost [rad/s]"], mode="fft", fftMethod="welch")
    # the spectrum of a burst-recorded signal: per burst, averaged
    pg.wait_for_selector(".fft-bursts:has-text('averaged over 6 bursts')")
    # Filters: the notch lines (43.5 Hz x harmonics 1, 2) and the low-pass, said in the note
    pg.locator(".plot-head .btn", has_text="Filters").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].fftFilters === true")
    pg.wait_for_selector(".plot-canvas[data-notches='43.5,87']")
    note = pg.locator(".fft-filters-note").inner_text()
    assert "HNTCH: fixed, 43.5 Hz × 1, 2, 40 dB" in note and "low-pass 20 Hz" in note
    # off again: no lines
    pg.locator(".plot-head .btn", has_text="Filters").click()
    pg.wait_for_selector(".plot-canvas[data-notches]", state="detached")
    # Log panel > Hardware: the frame and the IMU from its device id
    pg.locator(".rail button[aria-label='Flight log']").click()
    pg.locator(".log-tabs [role=tab]", has_text="Hardware").click()
    hw = pg.locator(".log-hw").inner_text()
    assert "Quad X" in hw and "ICM42688 (SPI 2, address 0x01)" in hw


def test_step_response_plot(pg):
    p = os.path.join(pg.env["data"], "loop.csv")
    if not os.path.exists(p):
        from scipy.signal import cont2discrete, dlsim, lfilter
        fs = 200
        t = np.arange(0, 40, 1 / fs)
        rng = np.random.default_rng(3)
        a = np.exp(-1 / (fs * 0.02))
        sp = lfilter([1 - a], [1, -a], np.repeat(rng.normal(0, 30, 160), fs // 4)[:len(t)])
        dn, dd, _ = cont2discrete(([1600.0], [1, 40.0, 1600.0]), 1 / fs)
        _, y = dlsim((dn.ravel(), dd, 1 / fs), sp)
        _csv(p, ["Time", "RDes", "R"], [t, sp, y.ravel()])
    open_files(pg, "loop.csv")
    _plot(pg, ["RDes", "R"], mode="step")
    pg.wait_for_selector(".plot-canvas[data-step]")
    rise = float(pg.locator(".plot-canvas[data-step]").get_attribute("data-step").split(",")[0])
    assert 0.02 < rise < 0.07                                   # wn 40 rad/s, damping 0.5: about 45 ms
    note = pg.locator(".step-note").inner_text()
    assert "overshoot" in note and "windows" in note
    # one signal only: it asks for the pair
    _plot(pg, ["RDes"], mode="step")
    pg.wait_for_selector(".plot-empty:has-text('Signals in pairs')")


def test_compare_time_tolerance(pg):
    for name, late in (("sq_a.csv", 0.0), ("sq_b.csv", 0.05)):
        p = os.path.join(pg.env["data"], name)
        if not os.path.exists(p):
            t = np.arange(0, 10, 0.01)
            _csv(p, ["Time", "Sq"], [t, np.where((np.maximum(t - late, 0) % 2) < 1, 0.0, 5.0)])
    open_files(pg, "sq_a.csv", "sq_b.csv")
    pg.locator(".rail button[aria-label='Compare runs']").click()
    side = pg.locator("aside.side")
    side.locator("button", has_text="Tolerance and alignment").click()
    side.get_by_label("Tolerance (±)").fill("0.1")
    pg.wait_for_selector(".sim-name:has-text('Sq') .sim-fail")          # 50 ms late: fails a value band
    side.get_by_label("Time tolerance (s)").fill("0.1")
    pg.wait_for_selector(".sim-name:has-text('Sq') .sim-fail", state="detached")
    assert S(pg, "true")
