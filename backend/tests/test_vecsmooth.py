"""Q102: a vector (position / velocity) smoothed over a window in seconds; Q101: a map object's
position from ECEF / NED goes through the existing "frame" conversion (checked here end to end)."""
import numpy as np
import pytest

from svcore.analysis import OpError, compute, lla_to_ecef, time_moving_average


def test_moving_average_is_centred_and_in_seconds():
    t = np.arange(0, 10, 0.01)                         # 100 Hz
    y = t.copy()                                       # a ramp: a centred mean leaves it as it is
    out = time_moving_average(t, y, 1.0)
    inner = (t > 0.6) & (t < 9.4)
    assert np.allclose(out[inner], y[inner], atol=1e-9)
    # the same window at another rate: the same smoothing
    t2 = np.arange(0, 10, 0.1)
    noise = np.sin(2 * np.pi * 20 * t)                 # fast wiggle: averaged away over 1 s
    assert np.abs(time_moving_average(t, noise, 1.0)[inner]).max() < 0.02
    assert len(time_moving_average(t2, t2, 1.0)) == len(t2)


def test_noise_goes_down():
    rng = np.random.default_rng(0)
    t = np.arange(0, 60, 0.1)
    truth = 5 * np.sin(2 * np.pi * t / 60)
    y = truth + rng.normal(0, 1.0, len(t))
    out = time_moving_average(t, y, 2.0)
    assert np.std(out - truth) < 0.35 * np.std(y - truth)


def test_a_gap_is_not_bridged_and_missing_stays_missing():
    t = np.r_[np.arange(0, 5, 0.1), np.arange(20, 25, 0.1)]
    y = np.r_[np.zeros(50), np.full(50, 100.0)]
    y[10] = np.nan
    out = time_moving_average(t, y, 4.0)
    assert np.nanmax(out[:50]) == 0 and np.nanmin(out[50:]) == 100   # nothing mixed across 5..20 s
    assert np.isnan(out[10]) and np.isfinite(out[11])


def test_window_longer_than_the_data_is_the_mean():
    t = np.arange(0, 1, 0.1)
    assert np.allclose(time_moving_average(t, t, 100.0), t.mean())


def _sig(t, y):
    return (np.asarray(t, float), np.asarray(y, float))


def test_vecsmooth_components_and_longitude_across_180():
    t = np.arange(0, 10, 0.1)
    lat = np.full(len(t), 10.0)
    lon = 179.9 + 0.02 * t                             # crosses +180 at t = 5 s
    lon = (lon + 180) % 360 - 180
    sigs = [_sig(t, lat), _sig(t, lon)]
    _, out = compute("vecsmooth", sigs, {"kind": "lla", "window": 1.0, "axis": 1})
    assert np.all(np.abs(out) > 179.0)                 # never averaged through 0
    _, la = compute("vecsmooth", sigs, {"kind": "lla", "window": 1.0, "axis": 0})
    assert np.allclose(la, 10.0)


def test_vecsmooth_refuses_bad_input():
    t = np.arange(0, 1, 0.1)
    s = [_sig(t, t)] * 3
    with pytest.raises(OpError):
        compute("vecsmooth", s, {"window": 0, "axis": 0})
    with pytest.raises(OpError):
        compute("vecsmooth", s, {"window": 1, "axis": 3})
    with pytest.raises(OpError):
        compute("vecsmooth", s[:1], {"kind": "lla", "window": 1, "axis": 0})
    with pytest.raises(OpError):
        compute("vecsmooth", s * 2, {"window": 1, "axis": 0})


def test_store_makes_and_names_them(tmp_path):
    from app.store import Store
    p = tmp_path / "v.csv"
    p.write_text("Time,vn,ve,vd\n" + "".join(f"{i * 0.1:.1f},{i % 2},{-(i % 2)},0\n" for i in range(50)))
    st = Store()
    rid = st.open_file(str(p)).id
    d = st.add_derived("vecsmooth", [f"{rid}/vn", f"{rid}/ve", f"{rid}/vd"], {"window": 1.0, "axis": 1}, "sm.E")
    t, y = st.signal(f"derived/{d.name}")
    assert np.allclose(y[10:-10], -0.5, atol=0.06)
    assert d.formula(st.short_name).startswith("smooth(ve, 1 s)")
    # the window is in seconds: a time-axis change lists it as computed against time
    assert "sm.E" in st.check_time_axis(rid, None)["timedDerived"]


def test_object_position_from_ecef_and_ned():
    """What the object dialog builds: frame position -> LLA (ECEF; NED from a typed reference)."""
    t = np.arange(0, 10, 1.0)
    lat = 32.0 + 0.001 * t
    lon = 35.0 + 0.002 * t
    alt = 100.0 + t
    x, y, z = lla_to_ecef(lat, lon, alt)
    ecef = [_sig(t, x), _sig(t, y), _sig(t, z)]
    for axis, want in ((0, lat), (1, lon), (2, alt)):
        _, got = compute("frame", ecef, {"qty": "position", "src": "ecef", "dst": "lla", "axis": axis})
        assert np.allclose(got, want, atol=1e-6)
    # NED from a typed origin: 100 m north, 50 m east, 10 m up
    ned = [_sig(t, np.full(10, 100.0)), _sig(t, np.full(10, 50.0)), _sig(t, np.full(10, -10.0))]
    ref = {"qty": "position", "src": "ned", "dst": "lla", "ref": "manual", "ref_lat": 32.0, "ref_lon": 35.0, "ref_alt": 0.0}
    _, la = compute("frame", ned, {**ref, "axis": 0})
    _, h = compute("frame", ned, {**ref, "axis": 2})
    assert la[0] == pytest.approx(32.0 + 100 / 111000, abs=2e-5) and h[0] == pytest.approx(10.0, abs=0.01)
