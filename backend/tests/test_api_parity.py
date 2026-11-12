"""L12: the whole process - find the objects, compare them, the statistics - through Python (signalviewer),
the command line (a subprocess), REST (/api/objects/*), and the app's own dialog path (the derived signals the
dialog makes through /api/derived, measured by /api/stats): the four give the same statistics (1e-9)."""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "backend"))
from fastapi.testclient import TestClient  # noqa: E402

import signalviewer as sv  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.csv_loader import load_csv  # noqa: E402

EX = os.path.join(ROOT, "examples", "ardupilot_lanes.csv")
client = TestClient(app)
REF, OBJS, WHAT = "POS", ["XKF1[0]", "XKF1[1]", "GPS[0]"], ["position", "attitude"]


def _key(rows):
    return {(r["object"], r["comp"]): r for r in rows}


def _close(a, b, keys=("rms", "mean", "max_abs", "p95_abs", "t_max_abs")):
    assert set(a) == set(b)
    for k in a:
        for f in keys:
            x, y = a[k][f], b[k][f]
            assert (x is None and y is None) or abs(x - y) <= 1e-9 * max(1.0, abs(x)), (k, f, x, y)


@pytest.fixture(scope="module")
def py_stats():
    rec = sv.load(EX)
    return _key(sv.compare_objects(rec, reference=REF, objects=OBJS, what=WHAT).raw["stats"])


@pytest.fixture(scope="module")
def rid():
    r = store.add_pushed("ardupilot_lanes", load_csv(EX, [EX]))[0]
    before = set(store.derived)
    yield r.id
    for name in set(store.derived) - before:            # the dialog path's signals: the store is shared by the tests
        store.remove_derived(name)
    store.remove(r.id)


def test_python_gives_the_fixture_numbers(py_stats):
    assert abs(py_stats[("XKF1[1]", "Δnorth")]["rms"] - 1.5) < 0.01 and py_stats[("XKF1[0]", "Δnorth")]["rms"] < 0.01
    assert abs(py_stats[("XKF1[1]", "Δyaw")]["rms"] - 0.5) < 1e-6
    assert ("GPS[0]", "Δyaw") not in py_stats                                  # no attitude of its own: left out


def test_cli_same_as_python(py_stats, tmp_path):
    out = subprocess.run([sys.executable, os.path.join(ROOT, "cli.py"), "compare-objects", EX, "--ref", REF, "--objects", ",".join(OBJS),
                          "--what", ",".join(WHAT), "--json", "--stats", str(tmp_path / "s.csv"), "--tolerance", "position=1m"],
                         capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert out.returncode == 1, out.stderr                                     # lane 1 is 1.5 m off: a failed tolerance
    doc = json.loads(out.stdout)
    _close(_key(doc["stats"]), py_stats)
    assert [c["status"] for c in doc["checks"]] == ["pass", "fail", "fail"]   # XKF1[0], XKF1[1], GPS[0] (noise)
    assert (tmp_path / "s.csv").read_text(encoding="utf-8-sig").startswith("object,qty,comp,rms")


def test_rest_same_as_python(py_stats, rid):
    d = client.post("/api/objects/detect", json={"runs": [rid]}).json()
    assert [o["name"] for o in d["files"][0]["objects"]] == ["POS", "XKF1[0]", "XKF1[1]", "GPS[0]"]
    r = client.post("/api/objects/compare", json={"runs": [rid], "reference": REF, "objects": OBJS, "what": WHAT, "points": 100})
    assert r.status_code == 200, r.text
    doc = r.json()
    _close(_key(doc["stats"]), py_stats)
    assert len(doc["errors"]["position"]["XKF1[1]"]["Δnorth"]["t"]) <= 100
    fam = client.post("/api/objects/similar", json={"run": rid}).json()["families"]
    assert any(f["leaf"] == "XKF1[*].Yaw" for f in fam)
    assert client.post("/api/objects/compare", json={"runs": [rid], "reference": "nope"}).status_code == 404


def test_the_dialogs_path_same_as_python(py_stats, rid):
    """What the dialog does: Add all (frame groups for the lanes, ref "signals"), then for each pair the relate
    signals (makeGroup) and /api/stats on them."""
    from svcore.objects import detect
    cands = {c["name"]: c for c in detect([(f"{rid}/{n}", n) for n in store.get(rid).run.signals], rid, "f")["candidates"]}

    def derived(op, sources, params):
        r = client.post("/api/derived", json={"op": op, "sources": sources, "params": params, "name": None})
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def lla(c):
        if c["pos"] == "lla":
            return [c["picks"][r]["id"] for r in ("lat", "lon", "alt") if r in c["picks"]]
        src = [c["picks"][r]["id"] for r in ("px", "py", "pz")] + c["origin"]["ids"]
        return [derived("frame", src, {"qty": "position", "src": c["pos"], "dst": "lla", "ref": "signals", "axis": k}) for k in range(3)]

    def layout(c):
        pos = lla(c)
        att = c["attitude"] == "angles"
        src = pos + ([c["picks"][r]["id"] for r in ("roll", "pitch", "yaw")] if att else [])
        unit = "deg"
        if att:
            u = client.post("/api/angle_units", json={r: c["picks"][r]["id"] for r in ("yaw", "pitch", "roll")}).json()
            unit = u["units"]["yaw"]["unit"]
        return src, {"alt": len(pos) == 3, "att": att, "unit": unit}
    P = layout(cands[REF])
    rows = []
    for name in OBJS:
        S = layout(cands[name])
        items = [(f"Δ{l}", {"what": "diff", "frame": "ned", "axis": k}) for k, l in enumerate(("north", "east", "down"))] + \
                [("horizontal error", {"what": "err_horiz"}), ("vertical error", {"what": "err_vert"}), ("3D error", {"what": "err_3d"})]
        if P[1]["att"] and S[1]["att"]:
            items += [("Δroll", {"what": "err_roll"}), ("Δpitch", {"what": "err_pitch"}), ("Δyaw", {"what": "err_hdg"})]
        for comp, params in items:
            sid = derived("relate", P[0] + S[0], {**params, "p": P[1], "s": S[1]})
            st = client.post("/api/stats", json={"signals": [sid]}).json()["stats"][sid]
            rows.append({"object": name, "comp": comp, "rms": st["rms"], "mean": st["mean"], "max_abs": st["abs_max"],
                         "p95_abs": st["p95_abs"], "t_max_abs": st["t_abs_max"]})
    _close(_key(rows), py_stats)
