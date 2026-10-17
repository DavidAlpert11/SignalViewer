"""T34: low-pass / high-pass are real Butterworth filters, zero phase, and never hand back the raw
signal in silence (before T34: a moving average, and the raw data whenever it could not filter)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.analysis import OpError, compute  # noqa: E402
from svcore.ops import FilterError, apply_filter  # noqa: E402

FS = 200.0
T = np.arange(0, 20, 1 / FS)
SLOW = np.sin(2 * np.pi * 1.0 * T)          # 1 Hz: the signal
FAST = 0.5 * np.sin(2 * np.pi * 40.0 * T)   # 40 Hz: the vibration


def _mid(x):                                 # away from the edges
    return x[len(x) // 4: -len(x) // 4]


def test_lowpass_keeps_the_signal_and_removes_the_vibration():
    y = apply_filter(T, SLOW + FAST, "lowpass", 10.0)
    assert np.max(np.abs(_mid(y - SLOW))) < 0.01            # 40 Hz down by > 30 dB, 1 Hz untouched


def test_highpass_keeps_the_vibration_and_removes_the_offset():
    y = apply_filter(T, 3.0 + SLOW + FAST, "highpass", 10.0)
    assert np.max(np.abs(_mid(y - FAST))) < 0.02


def test_zero_phase_a_step_stays_where_it_was():
    step = (T >= 10).astype(float)
    y = apply_filter(T, step, "lowpass", 5.0)
    crossing = T[np.argmax(y >= 0.5)]
    assert abs(crossing - 10.0) <= 1 / FS                    # a one-way filter would be late


def test_nan_samples_stay_nan_and_do_not_spread():
    y = SLOW.copy()
    y[1000:1010] = np.nan
    out = apply_filter(T, y, "lowpass", 10.0)
    assert np.isnan(out[1000:1010]).all()
    assert np.isfinite(out[:1000]).all() and np.isfinite(out[1010:]).all()


def test_jittery_time_uses_the_typical_sample_rate():
    rng = np.random.default_rng(0)
    tj = T + rng.uniform(-0.1, 0.1, len(T)) / FS              # logging jitter
    y = apply_filter(tj, SLOW + FAST, "lowpass", 10.0)
    assert np.max(np.abs(_mid(y - SLOW))) < 0.05


@pytest.mark.parametrize("cutoff", [0, -1, 101, 150])
def test_cutoff_outside_the_band_is_an_error_not_the_raw_signal(cutoff):
    with pytest.raises(FilterError, match="half the sample rate"):
        apply_filter(T, SLOW, "lowpass", cutoff)


def test_time_that_does_not_increase_is_an_error():
    with pytest.raises(FilterError, match="sample rate is unknown"):
        apply_filter(np.zeros(100), np.ones(100), "lowpass", 1.0)


def test_very_short_signal_still_filters():
    out = apply_filter(T[:5], SLOW[:5], "lowpass", 10.0)
    assert out.shape == (5,) and np.isfinite(out).all()


def test_create_signals_reports_the_reason():
    with pytest.raises(OpError, match="below half the sample rate"):
        compute("lowpass", [(T, SLOW)], {"cutoff": 500})


def test_formula_reports_the_reason():
    with pytest.raises(OpError, match="lowpass\\(\\).*half the sample rate"):
        compute("expr", [(T, SLOW)], {"expr": "lowpass(v0, 500)"})


def test_formula_filter_matches_the_operation():
    t1, a = compute("lowpass", [(T, SLOW + FAST)], {"cutoff": 10})
    t2, b = compute("expr", [(T, SLOW + FAST)], {"expr": "lowpass(v0, 10)"})
    assert np.allclose(a, b, equal_nan=True)


def test_api_says_why(tmp_path):
    client = TestClient(app)
    p = tmp_path / "v.csv"
    p.write_text("t,v\n" + "".join(f"{x},{y}\n" for x, y in zip(T[:400], SLOW[:400])))
    run = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    sid = run["signals"][0]["id"]
    r = client.post("/api/derived", json={"op": "lowpass", "sources": [sid], "params": {"cutoff": 1000}})
    assert r.status_code == 400 and "half the sample rate" in r.json()["detail"]
    for rid in list(store.order):
        store.remove(rid)
