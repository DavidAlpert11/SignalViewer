"""L3 / L6 (round of 2026-11-10): an object found from a position in metres is placed on the map by the
existing "frame" op through its origin ("signals": the origin's first valid sample). Checked on the
fixtures of tools/make_local_objects_fixture.py: EKF lane 0 lands on POS, lane 1 is 1.5 m north of it,
and every generic local object of local_frames.csv lands where the script put it."""
import os

import numpy as np

from svcore.analysis import _ecef_to_ned, compute, lla_to_ecef
from svcore.csv_loader import load_csv

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def _run(name):
    path = os.path.join(EX, name)
    run = load_csv(path, [path])
    assert run is not None
    return run


def _sig(run, name):
    s = run.signals[name]
    t = s.time if getattr(s, "time", None) is not None else run.time
    return np.asarray(t, float), np.asarray(s.data, float)


def _to_lla(run, vec, origin, src="ned"):
    sigs = [_sig(run, n) for n in vec + origin]
    params = {"qty": "position", "src": src, "dst": "lla", "ref": "signals"}
    t = compute("frame", sigs, {**params, "axis": 0})[0]
    return t, np.vstack([compute("frame", sigs, {**params, "axis": k})[1] for k in range(3)])


def _ned_of(lla, ref):
    """NED (m) of lat / lon / alt rows from a reference point - to measure distances in metres."""
    e = lla_to_ecef(*lla)
    return _ecef_to_ned(ref[0], ref[1]) @ (e - lla_to_ecef(*ref)[:, None])


ORGN = ["ORGN[0].Lat [deg]", "ORGN[0].Lng [deg]", "ORGN[0].Alt [m]"]
POS = ["POS.Lat [deg]", "POS.Lng [deg]", "POS.Alt [m]"]


def test_ekf_lanes_land_on_pos_through_the_ekf_origin():
    run = _run("ardupilot_lanes.csv")
    ref = [float(_sig(run, n)[1][0]) for n in ORGN]
    pos = np.vstack([_sig(run, n)[1] for n in POS])
    for k, north in ((0, 0.0), (1, 1.5)):
        _, lla = _to_lla(run, [f"XKF1[{k}].{f} [m]" for f in ("PN", "PE", "PD")], ORGN)
        d = _ned_of(lla, ref) - _ned_of(pos, ref)
        assert np.max(np.abs(d[0] - north)) < 0.05, f"lane {k} north"
        assert np.max(np.abs(d[1:])) < 0.05, f"lane {k} east / down"


def test_generic_local_objects_land_where_the_script_put_them():
    run = _run("local_frames.csv")
    origin = ["origin.lat", "origin.lon", "origin.alt"]
    ref = [float(_sig(run, n)[1][0]) for n in origin]
    tgt = np.vstack([_sig(run, f"tgt.ned.{a}")[1] for a in "xyz"])
    for vec, src, shift in ((["boat.pos.east", "boat.pos.north", "boat.pos.up"], "enu", (-200.0, 0.0)),
                            (["rov.pos.n", "rov.pos.e", "rov.pos.d"], "ned", (-400.0, 0.0))):
        _, lla = _to_lla(run, vec, origin, src)
        ned = _ned_of(lla, ref)
        assert np.max(np.abs(ned[0] - (tgt[0] + shift[0]))) < 0.05, vec[0]
        assert np.max(np.abs(ned[1] - tgt[1])) < 0.05, vec[0]
        assert np.max(np.abs(ned[2] - (0.0 if src == "enu" else 10.0))) < 0.05, vec[0]
    sigs = [_sig(run, f"ship.ecef_{a}") for a in "xyz"]
    lla = np.vstack([compute("frame", sigs, {"qty": "position", "src": "ecef", "dst": "lla", "axis": k})[1] for k in range(3)])
    ned = _ned_of(lla, ref)
    assert np.max(np.abs(ned[0] - (tgt[0] + 200.0))) < 0.05
    assert np.max(np.abs(ned[2])) < 0.05                    # on the origin's level


def test_relation_between_lanes_shows_the_fixture_offset():
    """L6: N7's relation of two lanes placed through ORGN - lane 1 - lane 0 is the +1.5 m north of the
    fixture in NED, and its heading error the +0.5 deg (relate on the converted positions, as the app does)."""
    run = _run("ardupilot_lanes.csv")
    rows = []
    for k in (0, 1):
        t, lla = _to_lla(run, [f"XKF1[{k}].{f} [m]" for f in ("PN", "PE", "PD")], ORGN)
        rows += [(t, lla[0]), (t, lla[1]), (t, lla[2])] + [_sig(run, f"XKF1[{k}].{a} [deg]") for a in ("Roll", "Pitch", "Yaw")]
    lay = {"alt": True, "att": True, "unit": "deg"}
    north = compute("relate", rows, {"what": "diff", "frame": "ned", "axis": 0, "p": lay, "s": lay})[1]
    down = compute("relate", rows, {"what": "diff", "frame": "ned", "axis": 2, "p": lay, "s": lay})[1]
    hdg = compute("relate", rows, {"what": "err_hdg", "p": lay, "s": lay})[1]
    assert np.nanmax(np.abs(north - 1.5)) < 0.05 and np.nanmax(np.abs(down)) < 0.05
    assert np.nanmax(np.abs(hdg - 0.5)) < 0.01


def test_comparison_statistics_match_numpy():
    """L8: the statistics of an error signal (RMS, mean, max |error|, its time, 95th percentile of |error|)
    are compute_signal_stats on the full-resolution data - checked against numpy on lane 1 vs lane 0."""
    from svcore.ops import compute_signal_stats
    run = _run("ardupilot_lanes.csv")
    rows = []
    for k in (0, 1):
        t, lla = _to_lla(run, [f"XKF1[{k}].{f} [m]" for f in ("PN", "PE", "PD")], ORGN)
        rows += [(t, lla[0]), (t, lla[1]), (t, lla[2])]
    lay = {"alt": True}
    t, e = compute("relate", rows, {"what": "err_horiz", "p": lay, "s": lay})
    st = compute_signal_stats(t, e)
    a = np.abs(e[np.isfinite(e)])
    assert abs(st["rms"] - np.sqrt(np.mean(a ** 2))) < 1e-9 and abs(st["mean"] - np.mean(e)) < 1e-9
    assert st["abs_max"] == a.max() and st["t_abs_max"] == t[np.isfinite(e)][np.argmax(a)]
    assert abs(st["p95_abs"] - np.percentile(a, 95)) < 1e-12
    assert abs(st["rms"] - 1.5) < 0.05                                     # the fixture's 1.5 m


def test_speed_error():
    """L8: err_speed is |v| of the secondary - |v| of the primary (here the same velocity: zero)."""
    run = _run("ardupilot_lanes.csv")
    rows = []
    for k in (0, 1):
        t, lla = _to_lla(run, [f"XKF1[{k}].{f} [m]" for f in ("PN", "PE", "PD")], ORGN)
        rows += [(t, lla[0]), (t, lla[1]), (t, lla[2])] + [_sig(run, f"XKF1[{k}].{v} [m/s]") for v in ("VN", "VE", "VD")]
    lay = {"alt": True, "vel": 3}
    out = compute("relate", rows, {"what": "err_speed", "p": lay, "s": lay})[1]
    assert np.nanmax(np.abs(out)) < 1e-9
    rows2 = rows[:3] + [(rows[3][0], rows[3][1] * 0)] + rows[4:]           # P's north velocity zeroed
    out2 = compute("relate", rows2, {"what": "err_speed", "p": lay, "s": lay})[1]
    assert np.nanmin(out2) >= -1e-9 and np.nanmax(out2) > 1
