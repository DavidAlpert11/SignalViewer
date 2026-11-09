"""N7: two objects compared (svcore/relate.py) - known geometry."""
import numpy as np
import pytest

from svcore.analysis import OpError, compute, ecef_to_lla, lla_to_ecef, _ecef_to_ned

R = 6378137.0


def _offset(lat, lon, alt, n, e, d=0.0):
    """The point n / e / d metres from (lat, lon, alt) in its local NED (exact, through ECEF)."""
    R_ = _ecef_to_ned(lat, lon)
    ecef = lla_to_ecef(lat, lon, alt) + R_.T @ np.array([n, e, d])
    return [float(x) for x in ecef_to_lla(*ecef)]


def _sig(t, *cols):
    return [(t, np.asarray(c, dtype=float)) for c in cols]


def run(what, P, S, t, p_att=False, s_att=False, **kw):
    params = {"what": what, "p": {"alt": True, "att": p_att}, "s": {"alt": True, "att": s_att}, **kw}
    return compute("relate", _sig(t, *P) + _sig(t, *S), params)[1]


def test_fixed_offset_north():
    t = np.arange(0, 10, 0.5)
    lat, lon, alt = 32.0, 35.0, 100.0
    la2, lo2, al2 = _offset(lat, lon, alt, 500.0, 0.0, -20.0)          # 500 m north, 20 m up
    P = [np.full_like(t, lat), np.full_like(t, lon), np.full_like(t, alt)]
    S = [np.full_like(t, la2), np.full_like(t, lo2), np.full_like(t, al2)]
    assert np.allclose(run("horiz", P, S, t), 500, atol=1e-3)
    assert np.allclose(run("range", P, S, t), np.hypot(500, 20), atol=1e-3)
    assert np.allclose(run("dalt", P, S, t), al2 - alt, atol=1e-6)            # 20 m + the curve of the earth over 500 m
    assert np.allclose((run("bearing", P, S, t) + 180) % 360 - 180, 0, atol=1e-4)      # north (0 or 359.99999...)
    north, east, down = (run("diff", P, S, t, frame="ned", axis=k) for k in range(3))
    assert np.allclose(north, 500, atol=1e-3) and np.allclose(east, 0, atol=1e-3) and np.allclose(down, -20, atol=1e-3)
    e, n, u = (run("diff", P, S, t, frame="enu", axis=k) for k in range(3))
    assert np.allclose([e, n, u], [0 * e, 500 + 0 * e, 20 + 0 * e], atol=1e-3)
    x, y, z = (run("diff", P, S, t, frame="ecef", axis=k) for k in range(3))
    assert np.allclose(np.sqrt(x * x + y * y + z * z), np.hypot(500, 20), atol=1e-3)
    assert np.allclose(run("diff", P, S, t, frame="lla", axis=0), 500, atol=0.05)
    # track frame along the primary's heading east (yaw 90): the secondary (north) is 500 m to its left
    Pa = P + [np.zeros_like(t), np.zeros_like(t), np.full_like(t, 90.0)]
    along, cross, up = (run("diff", Pa, S, t, p_att=True, frame="track", axis=k) for k in range(3))
    assert np.allclose(along, 0, atol=1e-3) and np.allclose(cross, -500, atol=1e-3) and np.allclose(up, 20, atol=1e-3)
    assert np.allclose(run("relbearing", Pa, S, t, p_att=True), -90, atol=1e-4)


def test_difference_in_ned_at_the_primary_far_from_the_start():
    """200 km of flight east: the secondary always 100 m north of the primary stays 100 m north - in the
    primary's NED at each sample (a NED fixed at the start would tilt it)."""
    t = np.arange(0, 2001, 10.0)
    pts = [_offset(32.0, 35.0, 3000.0, 0.0, 100.0 * k, 0.0) for k in range(len(t))]          # 100 m / s east
    P = [np.array(c) for c in zip(*pts)]
    sec = [_offset(la, lo, al, 100.0, 0.0, 0.0) for la, lo, al in pts]
    S = [np.array(c) for c in zip(*sec)]
    north, east, down = (run("diff", P, S, t, frame="ned", axis=k) for k in range(3))
    assert np.allclose(north, 100, atol=1e-3) and np.allclose(east, 0, atol=1e-3) and np.allclose(down, 0, atol=1e-3)
    along, cross, _ = (run("diff", P, S, t, frame="track", axis=k) for k in range(3))          # heading east by course
    assert np.allclose(along[1:-1], 0, atol=0.5) and np.allclose(cross[1:-1], -100, atol=0.5)


def test_head_on_closure_tca_and_aspect():
    """10 km apart, closing head-on at 50 + 50 m/s: closure 100 m/s, closest approach after 100 s,
    aspect 180 (nose to nose), headings 180 apart."""
    t = np.arange(0, 60, 0.5)
    P = [np.array(c) for c in zip(*[_offset(32.0, 35.0, 1000.0, 50.0 * x, 0.0) for x in t])]
    S = [np.array(c) for c in zip(*[_offset(32.0, 35.0, 1000.0, 10000.0 - 50.0 * x, 0.0) for x in t])]
    Pa = P + [np.zeros_like(t), np.zeros_like(t), np.zeros_like(t)]              # heading north
    Sa = S + [np.zeros_like(t), np.zeros_like(t), np.full_like(t, 180.0)]         # heading south
    assert np.allclose(run("closure", P, S, t)[2:-2], 100, atol=0.05)
    tca = run("tca", P, S, t)
    assert np.allclose(tca[2:-2], (10000 - 100 * t[2:-2]) / 100, atol=0.05)
    assert np.allclose(run("aspect", Pa, Sa, t, p_att=True, s_att=True), 180, atol=1e-3)
    assert np.allclose(run("hdgdiff", Pa, Sa, t, p_att=True, s_att=True), 180, atol=1e-6)
    # the primary right behind a secondary flying away north: aspect 0, opening (no closest approach ahead)
    S2 = [np.array(c) for c in zip(*[_offset(32.0, 35.0, 1000.0, 10000.0 + 80.0 * x, 0.0) for x in t])]
    S2a = S2 + [np.zeros_like(t), np.zeros_like(t), np.zeros_like(t)]
    assert np.allclose(run("aspect", Pa, S2a, t, p_att=True, s_att=True), 0, atol=1e-3)
    assert np.all(np.isnan(run("tca", P, S2, t)))


def test_heading_error_wraps_and_missing_stays_missing():
    t = np.arange(0, 10, 1.0)
    P = [np.full_like(t, 32.0), np.full_like(t, 35.0), np.full_like(t, 0.0), np.zeros_like(t), np.zeros_like(t), np.full_like(t, 359.0)]
    S = [np.full_like(t, 32.0), np.full_like(t, 35.0), np.full_like(t, 0.0), np.zeros_like(t), np.full_like(t, 3.0), np.full_like(t, 1.0)]
    assert np.allclose(run("err_hdg", P, S, t, p_att=True, s_att=True), 2.0)
    assert np.allclose(run("err_pitch", P, S, t, p_att=True, s_att=True), 3.0)
    # the secondary only for t 0..5: missing after, on the primary's samples
    ts = np.arange(0, 6, 1.0)
    params = {"what": "horiz", "p": {"alt": False}, "s": {"alt": False}}
    tt, h = compute("relate", [(t, P[0]), (t, P[1]), (ts, np.full_like(ts, 32.001)), (ts, np.full_like(ts, 35.0))], params)
    assert list(tt) == list(t) and np.all(np.isfinite(h[:6])) and np.all(np.isnan(h[6:]))
    assert np.all(np.isnan(compute("relate", [(t, P[0]), (t, P[1]), (t, P[0]), (t, P[1])], {**params, "what": "dalt"})[1]))


def test_bad_requests():
    t = np.arange(0, 5, 1.0)
    with pytest.raises(OpError):
        compute("relate", [(t, t)] * 4, {"what": "nope", "p": {}, "s": {}})
    with pytest.raises(OpError):
        compute("relate", [(t, t)] * 3, {"what": "range", "p": {}, "s": {}})
