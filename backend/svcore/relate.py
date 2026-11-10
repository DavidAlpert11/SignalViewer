"""
N7: two map objects compared - the relation between a primary and a secondary object (Tacview-like),
the secondary's navigation errors against the primary, and their position difference in a chosen frame.

One derived operation, "relate", one output per derived signal (params.what, and params.axis for a
difference). Sources, in order: the primary's latitude, longitude, [altitude], [roll, pitch, yaw], then
the secondary's the same way (params.p / params.s: {"alt": bool, "att": bool, "unit": "deg" | "rad"}).

The result is on the primary's samples (its latitude's); the secondary is interpolated onto them (the
short way round for angles) and is missing outside its own time span - missing stays missing (C3).

Definitions (degrees and metres; the local frame is the primary's own NED at each sample):
  range      straight-line (slant) distance, m
  horiz      horizontal distance (north / east of the primary's NED), m
  dalt       secondary's altitude - primary's, m
  bearing    from the primary to the secondary, 0-360 from north
  relbearing the bearing less the primary's heading, -180..180 (+ = to its right)
  closure    the rate the range shrinks, m/s (positive when closing)
  tca        time to closest approach, s (only while closing, else missing)
  hdgdiff    the angle between the two headings, 0-180
  aspect     the angle at the secondary between its tail and the line to the primary, 0-180:
             0 = the primary is right behind it, 180 = head-on (nose to nose)
  err_horiz / err_vert / err_3d   the secondary's position error, m (vert: secondary - primary)
  err_hdg / err_roll / err_pitch  the secondary's angle - the primary's, wrapped to -180..180
  vdiff      the secondary's velocity - the primary's (N7), in `frame` as for diff (lla: as ned): each
             object's own north / east / down velocity turned to ECEF, the difference turned into the
             primary's local frame at each sample; needs "vel" (2: north / east, 3: with down) in both
             layouts - its sources follow the angles
  diff       the secondary's position - the primary's in `frame` (axis 0..2):
             ned / enu  in the primary's local frame AT EACH SAMPLE (the ECEF difference turned by
                        its latitude / longitude at that time - a fixed origin would tilt the error)
             ecef       x / y / z, m (no origin)
             lla        north / east (the latitude / longitude difference in metres) and up (Δalt)
             track      along-track / cross-track (+ = right) / up, along the primary's heading
A heading is the yaw when the object has angles, else its course over ground (from its positions).
"""
from typing import Dict, List, Tuple

import numpy as np

WHATS = ("range", "horiz", "dalt", "bearing", "relbearing", "closure", "tca", "hdgdiff", "aspect",
         "err_horiz", "err_vert", "err_3d", "err_hdg", "err_roll", "err_pitch", "diff", "vdiff")
DIFF_FRAMES = {"ned": ("north", "east", "down"), "enu": ("east", "north", "up"), "ecef": ("x", "y", "z"),
               "lla": ("north", "east", "up"), "track": ("along", "cross", "up")}


def _wrap(a):
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


def relate_sources(params: Dict) -> int:
    n = 0
    for k in ("p", "s"):
        o = params.get(k) or {}
        n += 2 + (1 if o.get("alt") else 0) + (3 if o.get("att") else 0) + int(o.get("vel") or 0)
    return n


def relate_name(n: List[str], p: Dict) -> str:
    what = str(p.get("what", ""))
    if what in ("diff", "vdiff"):
        lbl = DIFF_FRAMES.get(str(p.get("frame", "ned")), ("?", "?", "?"))[int(p.get("axis", 0)) % 3]
        what = f"Δ{'v' if what == 'vdiff' else ''}{lbl} {str(p.get('frame', 'ned')).upper()}"
    k = relate_sources({"p": p.get("p")}) if p.get("p") else 2
    sec = n[k] if len(n) > k else "?"
    return f"{what}({sec} vs {n[0] if n else '?'})"


def _course(t, lat, lon):
    """Course over ground, degrees, over a ~1 s baseline (as the map's)."""
    la, lo = np.radians(lat), np.radians(lon)
    if len(t) < 2:
        return np.full(len(t), np.nan)
    step = max(1, min(int(np.searchsorted(t, t[0] + 1.0)), len(t) // 4 or 1))
    i0 = np.clip(np.arange(len(t)) - step // 2, 0, len(t) - 1)
    i1 = np.clip(np.arange(len(t)) + (step - step // 2), 0, len(t) - 1)
    y = np.sin(lo[i1] - lo[i0]) * np.cos(la[i1])
    x = np.cos(la[i0]) * np.sin(la[i1]) - np.sin(la[i0]) * np.cos(la[i1]) * np.cos(lo[i1] - lo[i0])
    c = np.degrees(np.arctan2(y, x))
    c[(np.abs(x) + np.abs(y)) < 1e-12] = np.nan
    return c


def relate(signals: List[Tuple[np.ndarray, np.ndarray]], params: Dict, rep=None) -> Tuple[np.ndarray, np.ndarray]:
    from svcore.analysis import OpError, _ecef_to_ned, _f64, _note_interpolated, _unwrap, align_to, lla_to_ecef
    what = params.get("what")
    if what not in WHATS:
        raise OpError(f"Unknown relation \"{what}\": use one of {', '.join(WHATS)}.")
    if len(signals) != relate_sources(params):
        raise OpError("Choose the two objects' signals: latitude, longitude, altitude and angles of each.")
    how = params.get("alignment", "linear")
    rows = [(_f64(t), _f64(y)) for t, y in signals]
    t = rows[0][0]
    ok = np.isfinite(t)
    t = t[ok]
    if len(t) < 2:
        raise OpError("The primary object's latitude has no samples.")

    def take(i, angle=False, unit="deg"):
        ts, ys = rows[i]
        if angle:
            ys = _unwrap(ys, 2 * np.pi if unit == "rad" else 360.0)
        v = align_to(t, ts, ys, how)
        if i >= relate_sources({"p": params.get("p")}):
            _note_interpolated(rep, t, ts, i, how)              # 26.U6: the secondary, read between its samples
        if angle:
            v = _wrap(np.degrees(v) if unit == "rad" else v)
        return v

    def obj(k: str, start: int):
        o = params.get(k) or {}
        i = start
        lat, lon = take(i), take(i + 1, angle=True)
        i += 2
        alt = take(i) if o.get("alt") else np.zeros(len(t))
        has_alt = bool(o.get("alt"))
        i += 1 if o.get("alt") else 0
        att = None
        if o.get("att"):
            u = o.get("unit", "deg")
            att = [take(i + j, angle=True, unit=u) for j in range(3)]     # roll, pitch, yaw
            i += 3
        vel = None
        nv = int(o.get("vel") or 0)
        if nv:
            vel = [take(i + j) for j in range(nv)] + ([np.zeros(len(t))] if nv == 2 else [])
            i += nv
        if np.nanmax(np.abs(lat)) > 90 or np.nanmax(np.abs(lon)) > 180:  # 1e7 degrees (MAVLink integers)
            lat, lon = lat / 1e7, lon / 1e7
        lon = _wrap(lon)
        return {"lat": lat, "lon": lon, "alt": alt, "has_alt": has_alt, "att": att, "vel": vel, "vd": nv == 3}, i

    P, nxt = obj("p", 0)
    S, _ = obj("s", nxt)
    Ep, Es = lla_to_ecef(P["lat"], P["lon"], P["alt"]), lla_to_ecef(S["lat"], S["lon"], S["alt"])
    d = Es - Ep
    Rp = _ecef_to_ned(P["lat"], P["lon"])
    ned = np.einsum("ijn,jn->in", Rp, d)
    vert_ok = P["has_alt"] and S["has_alt"]
    if not vert_ok:
        ned[2] = np.nan                                     # no altitude: nothing vertical is known
    horiz = np.hypot(ned[0], ned[1])
    rng = np.linalg.norm(ned, axis=0) if vert_ok else horiz

    def heading(o):
        return o["att"][2] if o["att"] is not None else _course(t, o["lat"], o["lon"])

    axis = int(params.get("axis", 0))
    if what in ("range", "err_3d"):
        out = rng
    elif what in ("horiz", "err_horiz"):
        out = horiz
    elif what in ("dalt", "err_vert"):
        out = S["alt"] - P["alt"] if vert_ok else np.full(len(t), np.nan)
    elif what == "bearing":
        b = np.degrees(np.arctan2(ned[1], ned[0])) % 360.0
        out = np.where(b >= 360.0, 0.0, b)                    # -1e-15 % 360 is 360.0
    elif what == "relbearing":
        out = _wrap(np.degrees(np.arctan2(ned[1], ned[0])) - heading(P))
    elif what in ("closure", "tca"):
        with np.errstate(invalid="ignore", divide="ignore"):
            closure = -np.gradient(rng, t)
            if what == "closure":
                out = closure
            else:
                rel_v = np.vstack([np.gradient(d[k], t) for k in range(3)])
                v2 = np.einsum("in,in->n", rel_v, rel_v)
                tca = -np.einsum("in,in->n", d, rel_v) / v2
                out = np.where((closure > 0) & (tca >= 0), tca, np.nan)
    elif what == "hdgdiff":
        out = np.abs(_wrap(heading(S) - heading(P)))
    elif what == "aspect":
        Rs = _ecef_to_ned(S["lat"], S["lon"])
        to_p = np.einsum("ijn,jn->in", Rs, -d)                 # the line from the secondary to the primary
        brg_sp = np.degrees(np.arctan2(to_p[1], to_p[0]))
        out = np.abs(_wrap(brg_sp - (heading(S) + 180.0)))
    elif what in ("err_hdg", "err_roll", "err_pitch"):
        if P["att"] is None or S["att"] is None:
            if what != "err_hdg":
                raise OpError("Roll and pitch errors need the angles of both objects.")
            out = _wrap(heading(S) - heading(P))
        else:
            j = {"err_roll": 0, "err_pitch": 1, "err_hdg": 2}[what]
            out = _wrap(S["att"][j] - P["att"][j])
    elif what == "vdiff":
        frame = params.get("frame", "ned")
        if P["vel"] is None or S["vel"] is None:
            raise OpError("Velocity differences need both objects' velocities (north / east, and down).")
        if frame not in DIFF_FRAMES or axis not in (0, 1, 2):
            raise OpError("Choose the frame of the difference: NED, ENU, ECEF, LLA or track, and an axis 0-2.")
        # each velocity from its own local frame to ECEF (R is NED <- ECEF: its transpose turns back)
        Rs = _ecef_to_ned(S["lat"], S["lon"])
        ve = lambda R, v: np.einsum("jin,jn->in", R, np.vstack(v))
        dv = ve(Rs, S["vel"]) - ve(Rp, P["vel"])
        vn = np.einsum("ijn,jn->in", Rp, dv)
        if not (P["vd"] and S["vd"]):
            vn[2] = np.nan                                  # no down velocity: nothing vertical is known
            # (in ECEF the missing down is taken as 0 - x / y / z cannot leave the vertical out)
        if frame in ("ned", "lla"):
            v = vn
        elif frame == "enu":
            v = np.vstack([vn[1], vn[0], -vn[2]])
        elif frame == "ecef":
            v = dv
        else:
            h = np.radians(heading(P))
            v = np.vstack([vn[0] * np.cos(h) + vn[1] * np.sin(h), -vn[0] * np.sin(h) + vn[1] * np.cos(h), -vn[2]])
        out = v[axis]
    else:                                                    # diff
        frame = params.get("frame", "ned")
        if frame not in DIFF_FRAMES or axis not in (0, 1, 2):
            raise OpError("Choose the frame of the difference: NED, ENU, ECEF, LLA or track, and an axis 0-2.")
        if frame == "ned":
            v = ned
        elif frame == "enu":
            v = np.vstack([ned[1], ned[0], -ned[2]])
        elif frame == "ecef":
            v = d
        elif frame == "lla":
            # the latitude / longitude difference in metres (meridian and prime-vertical radii), and Δalt
            from svcore.analysis import WGS84_A, WGS84_E2
            la = np.radians(P["lat"])
            s2 = np.sin(la) ** 2
            m_rad = WGS84_A * (1 - WGS84_E2) / (1 - WGS84_E2 * s2) ** 1.5 + P["alt"]
            n_rad = WGS84_A / np.sqrt(1 - WGS84_E2 * s2) + P["alt"]
            v = np.vstack([np.radians(S["lat"] - P["lat"]) * m_rad, np.radians(_wrap(S["lon"] - P["lon"])) * n_rad * np.cos(la),
                           S["alt"] - P["alt"] if vert_ok else np.full(len(t), np.nan)])
        else:                                                # track: along the primary's heading
            h = np.radians(heading(P))
            v = np.vstack([ned[0] * np.cos(h) + ned[1] * np.sin(h), -ned[0] * np.sin(h) + ned[1] * np.cos(h), -ned[2]])
        out = v[axis]
    return t, np.asarray(out, dtype=np.float64)
