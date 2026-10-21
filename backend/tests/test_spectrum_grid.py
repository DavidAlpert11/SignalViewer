"""A1: spectra of signals that are not evenly sampled (logger pauses, lost packets, NaN, jitter).

An FFT takes sample k to be at k*dt. Before A1 dt was the MEAN interval of the record, so one pause
moved every frequency: a 37 Hz tone in a 20 s record with a 2 s pause was shown at 33.3 Hz."""
import numpy as np
import pytest

from svcore.analysis import fft_for, spectrogram
from svcore.ops import compute_fft, compute_welch, uniform_samples

FS, F0, AMP = 400.0, 37.0, 2.0


def _tone(t):
    return AMP * np.sin(2 * np.pi * F0 * t) + 0.5


def _peak(f, m):
    return float(f[int(np.argmax(m))])


@pytest.fixture
def even():
    t = np.arange(0, 20, 1 / FS)
    return t, _tone(t)


def test_even_sampling_is_used_as_is(even):
    t, y = even
    dt, yy, info = uniform_samples(t, y)
    assert not info["resampled"] and info["gaps"] == 0
    assert yy is not None and len(yy) == len(y)
    f, m = compute_fft(t, y)
    assert _peak(f, m) == pytest.approx(F0, abs=0.05)
    assert m.max() == pytest.approx(AMP, rel=1e-3)          # amplitude scaling unchanged


@pytest.mark.parametrize("method", ["fft", "welch"])
def test_a_pause_does_not_move_the_frequency(even, method):
    t, y = even
    keep = ~((t > 8) & (t < 10))                             # a 2 s logger pause
    info: dict = {}
    f, m = (compute_welch if method == "welch" else compute_fft)(t[keep], y[keep], "hanning", info)
    df = FS / 256 if method == "welch" else 0.05
    assert _peak(f, m) == pytest.approx(F0, abs=df)          # was 33.3 Hz
    assert info["resampled"] and info["gaps"] == 1
    assert info["fs"] == pytest.approx(FS)
    assert info["gapTime"] == pytest.approx(2.0, abs=2 / FS)


def test_many_dropped_packets(even):
    t, y = even
    rng = np.random.default_rng(1)
    keep = rng.random(len(t)) > 0.2                          # 20 % of the samples lost
    f, m = compute_fft(t[keep], y[keep])
    assert _peak(f, m) == pytest.approx(F0, abs=0.05)


def test_small_timestamp_jitter_keeps_the_samples(even):
    t, y = even
    rng = np.random.default_rng(2)
    tj = t + rng.uniform(-0.05 / FS, 0.05 / FS, len(t))
    yj = _tone(tj)
    _, _, info = uniform_samples(tj, yj)
    assert not info["resampled"]
    f, m = compute_fft(tj, yj)
    assert _peak(f, m) == pytest.approx(F0, abs=0.05)
    assert m.max() == pytest.approx(AMP, rel=0.01)


def test_nan_samples_are_bridged_in_time(even):
    t, y = even
    y = y.copy()
    y[1000:1400] = np.nan
    info: dict = {}
    f, m = compute_fft(t, y, "hanning", info)
    assert info["resampled"]
    assert _peak(f, m) == pytest.approx(F0, abs=0.05)


def test_repeated_time_stamps(even):
    t, y = even
    t2 = np.insert(t, 500, t[500])                           # one sample logged twice
    y2 = np.insert(y, 500, y[500])
    f, m = compute_fft(t2, y2)
    assert _peak(f, m) == pytest.approx(F0, abs=0.05)


def test_unusable_time_gives_an_empty_spectrum():
    f, m = compute_fft(np.zeros(100), np.ones(100))
    assert len(f) == 0 and len(m) == 0


def test_fft_for_reports_the_grid_also_from_the_cache(even):
    t, y = even
    keep = ~((t > 8) & (t < 10))
    for _ in range(2):                                       # second call is a cache hit
        info: dict = {}
        f, _m = fft_for("a1/0", 1, t[keep], y[keep], "hanning", None, None, "fft", info)
        assert info["resampled"] and info["gaps"] == 1 and len(f)


def test_spectrogram_puts_the_tone_at_its_frequency_across_a_pause(even):
    t, y = even
    keep = ~((t > 8) & (t < 10))
    out = spectrogram(t[keep], y[keep], nfft=512)
    row = int(np.argmax(out["img"].astype(float).mean(axis=1)))
    assert out["f"][row] == pytest.approx(F0, abs=2 * out["df"])
    assert out["t"][-1] <= t[keep][-1] + 1e-9


def test_sparse_sampling_is_resampled_but_not_reported_as_gaps():
    # A3 shares the gap rule: long steps in a row (a solver's steady state) are not gaps
    t = np.concatenate([np.arange(0, 1, 0.001), np.arange(1, 100, 1.0)])
    _, _, info = uniform_samples(t, np.sin(t))
    assert info["resampled"] and info["gaps"] == 0 and info["gapTime"] == 0
