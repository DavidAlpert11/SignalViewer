"""P10 (2026-11-12): Story mode - the moments of a flight that matter, each as one plain sentence with its number.

``moments(objects, events, pair, places, units, lang)`` -> ``[{t, kind, title, text, object, level}]``:

- the marks the page already has (the log's errors and warnings, health findings, the user's notes) ->
  ``kind: "event"``;
- from the reference object's track: ``takeoff`` / ``landing`` (the height above the ground crossing 5 m and
  staying on that side for 3 s), ``highest``, ``fastest`` (ground speed over 1 s), ``steepest`` (the largest
  bank, when over 30°), passing within 200 m of a place (``place``);
- for the pair: ``largest_error`` when it is one vehicle (median distance under 20 m - truth and a navigation
  solution), else ``closest`` and ``farthest``.

Rules: a moment within 3 s of a stronger one is dropped (error > warning > finding > note > largest
error > closest > takeoff / landing > the rest); at most 12, the strongest kept; sorted by time. Every sentence
states only what was computed. English and Hebrew in the table below. Pure numpy."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

MAX_MOMENTS = 12
GAP_S = 3.0

# strength: lower is stronger
RANK = {"error": 0, "warning": 1, "finding": 2, "note": 3, "largest_error": 4, "closest": 5, "takeoff": 6, "landing": 6,
        "farthest": 7, "highest": 7, "fastest": 7, "steepest": 7, "place": 7}

WORDS: Dict[str, Dict[str, Any]] = {
    "en": {
        "takeoff": ("Takeoff", "{a} leaves the ground at {t}."),
        "landing": ("Landing", "{a} is back on the ground at {t}."),
        "highest": ("Highest", "{a} reaches {alt} above sea level ({agl} above the ground)."),
        "highest_noagl": ("Highest", "{a} reaches {alt} above sea level."),
        "fastest": ("Fastest", "{a} at {v} over the ground."),
        "steepest": ("Steepest bank", "{a} banks {roll}° to the {side}."),
        "largest_error": ("Largest error", "{b} is {d} {dir} of {a}."),
        "closest": ("Closest", "{a} and {b} are {d} apart."),
        "farthest": ("Farthest apart", "{a} and {b} are {d} apart."),
        "place": ("Over {p}", "{a} passes {d} from {p}."),
        "left": "left", "right": "right",
        "dirs": ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"],
    },
    "he": {
        "takeoff": ("המראה", "{a} עוזב את הקרקע ב-{t}."),
        "landing": ("נחיתה", "{a} חוזר לקרקע ב-{t}."),
        "highest": ("הכי גבוה", "{a} מגיע ל-{alt} מעל פני הים ({agl} מעל הקרקע)."),
        "highest_noagl": ("הכי גבוה", "{a} מגיע ל-{alt} מעל פני הים."),
        "fastest": ("הכי מהיר", "{a} במהירות {v} מעל הקרקע."),
        "steepest": ("הטיה הכי חדה", "{a} מוטה {roll}° {side}."),
        "largest_error": ("השגיאה הכי גדולה", "{b} נמצא {d} {dir} ל{a}."),
        "closest": ("הכי קרוב", "{a} ו{b} במרחק {d} זה מזה."),
        "farthest": ("הכי רחוק", "{a} ו{b} במרחק {d} זה מזה."),
        "place": ("מעל {p}", "{a} עובר במרחק {d} מ{p}."),
        "left": "שמאלה", "right": "ימינה",
        "dirs": ["צפונית", "צפון-מזרחית", "מזרחית", "דרום-מזרחית", "דרומית", "דרום-מערבית", "מערבית", "צפון-מערבית"],
    },
}


def fmt_dist(m: float, units: str = "metric") -> str:
    """The pages' and the app's formatter, in Python (relation.js svDist / mapDefaults.fmtDistance)."""
    a = abs(m)
    if units == "imperial":
        return f"{m / 1852:.2f} NM" if a >= 1852 else f"{m / 0.3048:.0f} ft"
    return f"{m / 1000:.{1 if a >= 10000 else 2}f} km" if a >= 1000 else f"{m:.{0 if a >= 100 else 1}f} m"


def fmt_speed(v: float, units: str = "metric") -> str:
    return f"{v * 1.943844:.0f} kt" if units == "imperial" else f"{v:.1f} m/s"


def fmt_clock(t: float, t0: float) -> str:
    s = max(0.0, t - t0)
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def _local(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float):
    k = math.pi / 180 * 6371008.8
    return (lon - lon0) * k * math.cos(math.radians(lat0)), (lat - lat0) * k


def _at(t: np.ndarray, v: np.ndarray, tq: np.ndarray) -> np.ndarray:
    ok = np.isfinite(v)
    if ok.sum() < 2:
        return np.full(len(tq), np.nan)
    out = np.interp(tq, t[ok], v[ok])
    out[(tq < t[ok][0]) | (tq > t[ok][-1])] = np.nan
    return out


def _speed(t: np.ndarray, e: np.ndarray, n: np.ndarray, window: float = 1.0) -> np.ndarray:
    """Ground speed over about `window` seconds around each sample."""
    if len(t) < 2:
        return np.full(len(t), np.nan)
    lo = np.searchsorted(t, t - window / 2)
    hi = np.minimum(len(t) - 1, np.searchsorted(t, t + window / 2, side="right") - 1)
    dt = t[hi] - t[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        v = np.hypot(e[hi] - e[lo], n[hi] - n[lo]) / dt
    v[~(dt > 0)] = np.nan
    return v


def _crossings(t: np.ndarray, agl: np.ndarray, level: float = 5.0, hold: float = 3.0) -> List[tuple]:
    """(t, "takeoff" | "landing") where the height above the ground crosses `level` and stays on its new
    side for `hold` seconds (a bounce on the runway is not a takeoff)."""
    out: List[tuple] = []
    ok = np.isfinite(agl)
    if ok.sum() < 3:
        return out
    above = agl > level
    state = None
    i = 0
    n = len(t)
    while i < n:
        if not ok[i]:
            i += 1
            continue
        if state is None:
            state = bool(above[i])
            i += 1
            continue
        if bool(above[i]) != state:
            j = i
            while j < n and (not ok[j] or bool(above[j]) != state) and t[j] - t[i] < hold:
                j += 1
            if j >= n or t[j] - t[i] >= hold:
                state = bool(above[i])
                out.append((float(t[i]), "takeoff" if state else "landing"))
                i = j
                continue
        i += 1
    return out


def moments(objects: Sequence[Dict], events: Sequence[Dict] = (), pair: Optional[Dict] = None, places: Sequence[Dict] = (),
            units: str = "metric", lang: str = "en") -> List[Dict]:
    """`objects`: [{name, t, lat, lon, alt (m above sea level, or None), ground (or None), roll (deg, or None)}];
    `events`: [{t, text, level}]; `pair`: {primary, secondary} by name (default: the first two objects);
    `places`: point places [{name, lat, lon}]."""
    W = WORDS["he" if lang == "he" else "en"]
    objs = [o for o in objects if o.get("t") is not None and len(o["t"]) > 1]
    out: List[Dict] = []
    t0 = min((float(np.nanmin(np.asarray(o["t"], dtype=float))) for o in objs), default=0.0)
    for e in events:
        try:
            te = float(e["t"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(te):
            continue
        lvl = str(e.get("level")) if e.get("level") in ("error", "warning", "finding", "note") else "note"
        text = str(e.get("text") or "")[:160]
        out.append({"t": te, "kind": "event", "title": text, "text": text, "object": (pair or {}).get("primary"), "level": lvl, "_rank": RANK[lvl]})

    names = [o["name"] for o in objs]
    pname = (pair or {}).get("primary") if (pair or {}).get("primary") in names else (names[0] if names else None)
    sname = (pair or {}).get("secondary") if (pair or {}).get("secondary") in names and (pair or {}).get("secondary") != pname else \
        next((n for n in names if n != pname), None)
    P = next((o for o in objs if o["name"] == pname), None)

    def make(at: float, kind: str, words: str, obj: Optional[str], **kw: Any) -> Dict:
        title, text = W[words]
        return {"t": float(at), "kind": kind, "title": title.format(**kw), "text": text.format(**kw), "object": obj,
                "level": "info", "_rank": RANK[kind]}

    def add(at: float, kind: str, words: str, obj: Optional[str], **kw: Any) -> None:
        out.append(make(at, kind, words, obj, **kw))

    def add_peak(v: np.ndarray, kind: str, words: str, obj: Optional[str], fmt) -> None:
        """An extreme, with its near-equal rivals (within 2 %, 5 s apart) as stand-ins when a stronger moment is
        within 3 s of it (a figure-eight is as fast at each crossing)."""
        ok = np.isfinite(v)
        if not ok.any():
            return
        order = np.argsort(-np.where(ok, v, -np.inf))
        top = float(v[order[0]])
        picks: List[int] = []
        for k in order[:2000]:
            if not ok[k] or v[k] < top - 0.02 * abs(top):
                break
            if all(abs(t[k] - t[j]) > 5 for j in picks):
                picks.append(int(k))
            if len(picks) >= 4:
                break
        ms = [make(t[k], kind, words, obj, **fmt(k)) for k in picks]
        ms[0]["_alts"] = ms[1:]
        out.append(ms[0])

    if P is not None:
        t = np.asarray(P["t"], dtype=float)
        lat, lon = np.asarray(P["lat"], dtype=float), np.asarray(P["lon"], dtype=float)
        good = np.isfinite(lat) & np.isfinite(lon)
        if good.sum() > 2:
            lat0, lon0 = float(np.nanmean(lat[good])), float(np.nanmean(lon[good]))
            e, n = _local(lat, lon, lat0, lon0)
            alt = np.asarray(P["alt"], dtype=float) if P.get("alt") is not None else None
            g = np.asarray(P["ground"], dtype=float) if P.get("ground") is not None else None
            agl = alt - g if alt is not None and g is not None else None
            if agl is not None:
                for tc, kind in _crossings(t, agl):
                    add(tc, kind, kind, pname, a=pname, t=fmt_clock(tc, t0))
            if alt is not None and np.isfinite(alt).any():
                with_agl = agl is not None and bool(np.isfinite(agl).any())
                add_peak(alt, "highest", "highest" if with_agl else "highest_noagl", pname,
                         lambda k: {"a": pname, "alt": fmt_dist(float(alt[k]), units), "agl": fmt_dist(float(agl[k]), units) if agl is not None else ""})
            v = _speed(t, e, n)
            add_peak(v, "fastest", "fastest", pname, lambda k: {"a": pname, "v": fmt_speed(float(v[k]), units)})
            if P.get("roll") is not None:
                roll = np.asarray(P["roll"], dtype=float)
                if np.isfinite(roll).any():
                    k = int(np.nanargmax(np.abs(np.where(np.isfinite(roll), roll, 0))))
                    if abs(roll[k]) > 30:
                        add(t[k], "steepest", "steepest", pname, a=pname, roll=f"{abs(roll[k]):.0f}", side=W["right"] if roll[k] > 0 else W["left"])
            for pl in places:
                try:
                    plat, plon = float(pl["lat"]), float(pl["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                pe, pn = _local(np.array([plat]), np.array([plon]), lat0, lon0)
                d = np.hypot(e - pe[0], n - pn[0])
                near = d < 200
                if near.any():
                    k = int(np.nanargmin(np.where(near, d, np.inf)))
                    add(t[k], "place", "place", pname, a=pname, p=str(pl.get("name") or ""), d=fmt_dist(float(d[k]), units))
            S = next((o for o in objs if o["name"] == sname), None)
            if S is not None:
                ts = np.asarray(S["t"], dtype=float)
                slat, slon = _at(ts, np.asarray(S["lat"], dtype=float), t), _at(ts, np.asarray(S["lon"], dtype=float), t)
                se, sn = _local(slat, slon, lat0, lon0)
                dz = np.zeros(len(t))
                if alt is not None and S.get("alt") is not None:
                    dz = _at(ts, np.asarray(S["alt"], dtype=float), t) - alt
                    dz = np.where(np.isfinite(dz), dz, 0.0)
                d = np.sqrt((se - e) ** 2 + (sn - n) ** 2 + dz ** 2)
                if np.isfinite(d).sum() > 2:
                    if float(np.nanmedian(d)) < 20:                 # one vehicle: the solution against the truth
                        k = int(np.nanargmax(d))
                        b = (math.degrees(math.atan2(se[k] - e[k], sn[k] - n[k])) + 360) % 360
                        add(t[k], "largest_error", "largest_error", sname, a=pname, b=sname, d=fmt_dist(float(d[k]), units),
                            dir=W["dirs"][int((b + 22.5) // 45) % 8])
                    else:
                        k = int(np.nanargmin(d))
                        add(t[k], "closest", "closest", sname, a=pname, b=sname, d=fmt_dist(float(d[k]), units))
                        k = int(np.nanargmax(d))
                        add(t[k], "farthest", "farthest", sname, a=pname, b=sname, d=fmt_dist(float(d[k]), units))

    # the strongest first: a weaker moment within GAP_S of a kept one is dropped; at most MAX_MOMENTS
    out.sort(key=lambda m: (m["_rank"], m["t"]))
    kept: List[Dict] = []
    for m in out:
        for c in [m] + m.pop("_alts", []):
            if not any(abs(c["t"] - k["t"]) < GAP_S for k in kept):    # kept ones are as strong or stronger
                kept.append(c)
                break
        if len(kept) >= MAX_MOMENTS:
            break
    kept.sort(key=lambda m: m["t"])
    for m in kept:
        m.pop("_rank", None)
        m.pop("_alts", None)
        m["t"] = round(m["t"], 3)
    return kept
