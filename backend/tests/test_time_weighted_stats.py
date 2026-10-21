"""A3: mean, RMS and std are time statistics on uneven sampling; evenly sampled signals unchanged."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.ops import compute_signal_stats, time_weights  # noqa: E402


def test_even_sampling_gives_exactly_the_sample_statistics():
    t = np.arange(0, 10, 0.01)
    y = np.sin(2 * np.pi * 0.7 * t) + 0.3
    s = compute_signal_stats(t, y)
    assert "weighting" not in s
    assert s["mean"] == np.mean(y) and s["rms"] == np.sqrt(np.mean(y * y)) and s["std"] == np.std(y)


def test_small_jitter_is_still_even():
    rng = np.random.default_rng(0)
    t = np.arange(0, 10, 0.01) + rng.uniform(-0.002, 0.002, 1000)
    assert time_weights(np.sort(t))[0] is None


def test_variable_step_output_is_weighted_by_time():
    # a solver: 1000 small steps in the first second (value 10), then 99 one-second steps (value 0)
    t = np.concatenate([np.arange(0, 1, 0.001), np.arange(1, 100, 1.0)])
    y = np.where(t < 1, 10.0, 0.0)
    s = compute_signal_stats(t, y)
    assert s["weighting"] == "time" and s["gaps"] == 0      # long steps in a row are not gaps
    assert s["mean"] == pytest.approx(0.1, abs=0.01)        # sample mean: 9.1
    assert s["rms"] == pytest.approx(np.sqrt(1.0), abs=0.05)
    assert s["min"] == 0 and s["max"] == 10 and s["samples"] == len(t)


def test_a_dropout_does_not_give_its_time_to_two_samples():
    # 10 Hz telemetry, a 30 s radio dropout; the two samples around it are outliers
    t = np.concatenate([np.arange(0, 10, 0.1), np.arange(40, 50, 0.1)])
    y = np.ones_like(t)
    y[99], y[100] = 100.0, 100.0
    s = compute_signal_stats(t, y)
    assert s["weighting"] == "time" and s["gaps"] == 1
    # each outlier stands for one regular step, as the other samples: ~ the sample mean
    assert s["mean"] == pytest.approx(np.mean(y), rel=0.02)


def test_nan_samples_are_left_out_and_their_time_bridged():
    t = np.linspace(0, 10, 1001)
    y = np.full_like(t, 2.0)
    y[200:300] = np.nan
    s = compute_signal_stats(t, y)
    assert s["mean"] == pytest.approx(2.0) and s["samples"] == 901


def test_a_region_and_a_mask():
    t = np.concatenate([np.arange(0, 1, 0.001), np.arange(1, 100, 1.0)])
    y = np.where(t < 1, 10.0, 0.0)
    assert compute_signal_stats(t, y, 50, 99)["mean"] == 0.0
    # only while a state holds: two stretches far apart; the time between them is not a gap
    m = (t < 0.5) | ((t >= 50) & (t <= 60))
    s = compute_signal_stats(t, y, mask=m)
    assert s["samples"] == int(m.sum())
    # 0.5 s of 10 against ~11 s of 0
    assert s["mean"] == pytest.approx(10 * 0.5 / 11.5, rel=0.1)


def test_masked_stats_are_not_served_from_the_unmasked_cache():
    t = np.arange(0, 10, 0.01)
    y = t.copy()
    full = compute_signal_stats(t, y)
    half = compute_signal_stats(t, y, mask=t < 5)
    assert half["max"] < 5 <= full["max"]
