"""CC20: the Compare difference against the baseline's own noise (svcore.compare.sample_noise, metrics noiseRatio)."""
import numpy as np
import pytest


def test_the_difference_against_the_baselines_own_noise():
    """CC20: noiseRatio = RMS difference / the baseline's sample-to-sample noise - about 1.4 for two runs that differ
    by their noise only (each its own noise: sqrt(2)), far above for a real change; none for a noiseless signal."""
    from svcore.compare import metrics, sample_noise
    rng = np.random.default_rng(3)
    t = np.linspace(0, 10, 5001)
    shape = np.sin(t)
    a = shape + rng.normal(0, 0.01, len(t))
    b = shape + rng.normal(0, 0.01, len(t))
    assert sample_noise(a) == pytest.approx(0.01, rel=0.1)
    assert metrics(a, b, None, None)["noiseRatio"] == pytest.approx(np.sqrt(2), rel=0.15)
    assert metrics(a, b + 0.2, None, None)["noiseRatio"] > 10
    assert "noiseRatio" not in metrics(np.zeros(100), np.ones(100), None, None)
