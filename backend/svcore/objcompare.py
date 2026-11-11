"""
L12: a comparison of map objects on arrays - the same maths, in the same order, as the app's *Compare
objects…* (L8): positions placed on Earth by the "frame" op (NED / ENU through their origin, ECEF), the
differences and errors by the "relate" op, the statistics by compute_signal_stats - the functions the app's
derived signals call. Used by the Python API (signalviewer.compare_objects), the command line
(compare-objects) and the REST endpoint (/api/objects/compare), so all four give the same numbers.

    from svcore.objcompare import compare
    res = compare(sig, objects, reference="POS", others=["XKF1[0]"], what=("position",), frame="ned")
    res["stats"]       # [{object, qty, comp, rms, mean, max_abs, p95_abs, t_max_abs, samples}]

`sig(id) -> (t, y)` reads a signal; `objects` are candidates of svcore.objects.detect (or dicts with the
same picks / pos / origin). Attitudes: an object's own angles only (one with none, or a quaternion, is left
out of the attitude comparison - said in `left_out`), the unit by the app's Automatic rule (angle_units).
"""
import re
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore.analysis import compute
from svcore.ops import compute_signal_stats

Series = Tuple[np.ndarray, np.ndarray]
AXES = {"ned": ("north", "east", "down"), "enu": ("east", "north", "up"), "ecef": ("x", "y", "z"),
        "lla": ("north", "east", "up"), "track": ("along", "cross", "up")}
QUANTITIES = ("position", "velocity", "attitude")


def angle_units(raw: Dict[str, tuple]) -> Dict[str, Tuple[str, str]]:
    """{role: (unit, why)} for an object's angle signals {role: (sig_id, t, values)} - what the app's
    "Automatic" takes them to be (26.A5). why: "name" - the name says it ("... [rad]", "_deg"); else all the
    object's angles together - "beyond" (one goes beyond 2 pi: degrees) or "within" (radians)."""
    beyond = any(len(v[2]) and np.nanmax(np.abs(np.asarray(v[2], dtype=np.float64))) > 2 * np.pi + 0.05 for v in raw.values())
    out: Dict[str, Tuple[str, str]] = {}
    for role, (sid, _ts, _vs) in raw.items():
        name = sid.split("/", 1)[-1].lower()
        if re.search(r"(\[rad\]|\brad\b|_rad\b|\(rad\))", name):
            out[role] = ("rad", "name")
        elif re.search(r"(\[deg\]|\bdeg\b|_deg\b|\(deg\)|°)", name):
            out[role] = ("deg", "name")
        else:
            out[role] = ("deg", "beyond") if beyond else ("rad", "within")
    return out


def _pick(o: Dict, role: str) -> Optional[str]:
    p = (o.get("picks") or {}).get(role)
    return p["id"] if p else None


def position(sig: Callable[[str], Series], o: Dict) -> List[Series]:
    """lat, lon (and alt) of an object: recorded, or its position in metres through the frame op as the app
    adds it (NED / ENU: from its origin's first valid sample, ECEF: by itself)."""
    if o["pos"] == "lla":
        return [sig(i) for i in (_pick(o, "lat"), _pick(o, "lon"), _pick(o, "alt")) if i]
    vec = [sig(_pick(o, r)) for r in ("px", "py", "pz")]
    if o["pos"] == "ecef":
        params = {"qty": "position", "src": "ecef", "dst": "lla"}
        srcs = vec
    else:
        if not o.get("origin"):
            raise ValueError(f"{o['name']} has no origin: its {o['pos'].upper()} position cannot be placed on Earth.")
        params = {"qty": "position", "src": o["pos"], "dst": "lla", "ref": "signals"}
        srcs = vec + [sig(i) for i in o["origin"]["ids"]]
    return [compute("frame", srcs, {**params, "axis": k}) for k in range(3)]


def layout(sig: Callable[[str], Series], o: Dict, with_vel: bool) -> Tuple[List[Series], Dict]:
    """The relate op's sources and layout for one object - as the app's relation.ts layout()."""
    pos = position(sig, o)
    att_ids = [_pick(o, r) for r in ("roll", "pitch", "yaw")]
    att = o.get("attitude") == "angles" and all(att_ids)
    unit = "deg"
    if att:
        raw = {r: (i, *sig(i)) for r, i in zip(("roll", "pitch", "yaw"), att_ids)}
        unit = angle_units({"yaw": raw["yaw"], "pitch": raw["pitch"], "roll": raw["roll"]})["yaw"][0]
    vel_ids = [i for i in (_pick(o, "vn"), _pick(o, "ve"), _pick(o, "vd")) if i] if with_vel and _pick(o, "vn") and _pick(o, "ve") else []
    src = pos + ([sig(i) for i in att_ids] if att else []) + [sig(i) for i in vel_ids]
    lay: Dict = {"alt": len(pos) == 3, "att": att, "unit": unit}
    if vel_ids:
        lay["vel"] = len(vel_ids)
    return src, lay


def _relate(sig, P, S, what: str, with_vel: bool, **extra) -> Series:
    ps, pl = layout(sig, P, with_vel)
    ss, sl = layout(sig, S, with_vel)
    return compute("relate", ps + ss, {"what": what, "p": pl, "s": sl, **extra})


def comparable(P: Dict, others: Sequence[Dict]) -> Dict[str, Dict]:
    """What each quantity can compare: {"reason"} when the reference cannot, and the objects left out with why."""
    def has_vel(o):
        return bool(_pick(o, "vn") and _pick(o, "ve"))

    def euler(o):
        return o.get("attitude") == "angles" and all(_pick(o, r) for r in ("roll", "pitch", "yaw"))
    out: Dict[str, Dict] = {"position": {"left_out": []}, "velocity": {"left_out": []}, "attitude": {"left_out": []}}
    if not has_vel(P):
        out["velocity"]["reason"] = f"{P['name']} has no velocity"
    else:
        out["velocity"]["left_out"] = [{"object": o["name"], "why": f"{o['name']} has no velocity"} for o in others if not has_vel(o)]
    if not euler(P):
        out["attitude"]["reason"] = f"{P['name']} has no attitude of its own in angles"
    else:
        out["attitude"]["left_out"] = [{"object": o["name"], "why": f"{o['name']} has no attitude of its own in angles"} for o in others if not euler(o)]
    for o in others:
        if o["pos"] in ("ned", "enu") and not o.get("origin"):
            out["position"]["left_out"].append({"object": o["name"], "why": f"{o['name']} has no origin"})
    return out


def stats_row(obj: str, qty: str, comp: str, t: np.ndarray, e: np.ndarray) -> Dict:
    s = compute_signal_stats(t, e) or {}
    return {"object": obj, "qty": qty, "comp": comp, "rms": s.get("rms"), "mean": s.get("mean"), "max_abs": s.get("abs_max"),
            "p95_abs": s.get("p95_abs"), "t_max_abs": s.get("t_abs_max"), "samples": s.get("samples")}


def compare(sig: Callable[[str], Series], objects: Sequence[Dict], reference: str, others: Optional[Sequence[str]] = None,
            what: Sequence[str] = QUANTITIES, frame: str = "ned") -> Dict:
    """values: {qty: {object: {comp: (t, y)}}}; errors: {qty: {object: {comp: (t, y)}}}; stats: one row per
    object and error component (the app's statistics table); left_out / reasons: what could not be compared."""
    if frame not in AXES:
        raise ValueError(f"frame is one of {', '.join(AXES)}")
    bad = [w for w in what if w not in QUANTITIES]
    if bad:
        raise ValueError(f"what is any of {', '.join(QUANTITIES)} (not {', '.join(bad)})")
    by = {o["name"]: o for o in objects}
    if reference not in by:
        raise KeyError(f"No object named {reference!r} (found: {', '.join(by)})")
    P = by[reference]
    names = [n for n in (others if others is not None else [o["name"] for o in objects]) if n != reference]
    missing = [n for n in names if n not in by]
    if missing:
        raise KeyError(f"No object named {', '.join(map(repr, missing))} (found: {', '.join(by)})")
    S_all = [by[n] for n in names]
    can = comparable(P, S_all)
    L = AXES[frame]
    values: Dict[str, Dict] = {}
    errors: Dict[str, Dict] = {}
    stats: List[Dict] = []
    for q in what:
        if can[q].get("reason"):
            continue
        out = {x["object"] for x in can[q]["left_out"]}
        S_list = [o for o in S_all if o["name"] not in out]
        errors[q], values[q] = {}, {}
        for S in S_list:
            e: Dict[str, Series] = {}
            if q == "position":
                for k, lbl in enumerate(L):
                    e[f"Δ{lbl}"] = _relate(sig, P, S, "diff", False, frame=frame, axis=k)
                for w, lbl in (("err_horiz", "horizontal error"), ("err_vert", "vertical error"), ("err_3d", "3D error")):
                    e[lbl] = _relate(sig, P, S, w, False)
            elif q == "velocity":
                for k, lbl in enumerate(L):
                    e[f"Δv {lbl}"] = _relate(sig, P, S, "vdiff", True, frame=frame, axis=k)
                e["speed error (m/s)"] = _relate(sig, P, S, "err_speed", True)
            else:
                for w, lbl in (("err_roll", "Δroll"), ("err_pitch", "Δpitch"), ("err_hdg", "Δyaw")):
                    e[lbl] = _relate(sig, P, S, w, False)
            errors[q][S["name"]] = e
            stats += [stats_row(S["name"], q, comp, *ts) for comp, ts in e.items()]
        for o in [P] + S_list:                                       # the values: as recorded / converted
            if q == "position":
                pos = position(sig, o)
                values[q][o["name"]] = dict(zip(("lat", "lon", "alt"), pos))
            elif q == "velocity":
                values[q][o["name"]] = {f"v {a}": sig(i) for a, i in zip(("north", "east", "down"), (_pick(o, "vn"), _pick(o, "ve"), _pick(o, "vd"))) if i}
            else:
                values[q][o["name"]] = {r: sig(_pick(o, r)) for r in ("roll", "pitch", "yaw")}
    return {"reference": reference, "frame": frame, "values": values, "errors": errors, "stats": stats,
            "reasons": {q: can[q]["reason"] for q in what if can[q].get("reason")},
            "left_out": {q: can[q]["left_out"] for q in what if can[q]["left_out"]}}
