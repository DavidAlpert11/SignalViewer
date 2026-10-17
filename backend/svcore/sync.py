"""
Time alignment of two recordings of the same flight - typically the autopilot's own log (.bin /
.ulg, time = seconds since boot) and the ground station's telemetry log (.tlog, time = seconds since
its first packet). Three independent methods, so they can confirm each other:

  boot    the .tlog's messages carry the autopilot's boot clock (time_boot_ms): the offset between
          receive time and boot time IS the alignment. Spread = radio-link latency jitter.
  events  the same messages (MSG in .bin = STATUSTEXT in .tlog), mode changes, arm / disarm
          appear in both: the typical time difference of matching events.
  signal  cross-correlation of the same quantity in both (ATT.Roll ~ ATTITUDE.roll...), or of two
          signals the user picks. Units and scale do not matter (both are normalised).

Each candidate: {method, delta, offset, quality: high|medium|low, ...}. `delta` moves the other
file's time onto the reference's; `offset` is the other file's new time offset (its current one +
delta, and the reference's own offset), ready to apply.
"""
import logging
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger("signalviewer").getChild(__name__)

_NAME = re.compile(r"^([^.\[]+)(\[\d+\])?\.([^ ]+)(?: \[.*\])?$")

# the same quantity under its .bin / .ulg / .tlog names
PAIRS = [
    ("ATT.Roll", "ATTITUDE.roll"), ("ATT.Pitch", "ATTITUDE.pitch"),
    ("vehicle_attitude.q[0]", "ATTITUDE_QUATERNION.q1"),
    ("BAT.Volt", "SYS_STATUS.voltage_battery"), ("BATT.Volt", "SYS_STATUS.voltage_battery"),
    ("battery_status.voltage_v", "SYS_STATUS.voltage_battery"),
    ("GPS.Alt", "GPS_RAW_INT.alt"), ("BARO.Alt", "VFR_HUD.alt"), ("CTUN.Alt", "VFR_HUD.alt"),
    ("RCOU.C3", "SERVO_OUTPUT_RAW.servo3_raw"), ("RCIN.C3", "RC_CHANNELS.chan3_raw"),
    ("VIBE.VibeZ", "VIBRATION.vibration_z"),
]


def _find(run, bare: str) -> Optional[str]:
    """A signal of run by name without unit / instance ("ATT.Roll" -> "ATT.Roll [deg]")."""
    if bare in run.signals:
        return bare
    msg, _, field = bare.partition(".")
    hits = []
    for n in run.signals:
        m = _NAME.match(n)
        if m and m.group(1) == msg and m.group(3) == field and not (m.group(2) or "").startswith("[c"):
            hits.append(n)
    return sorted(hits)[0] if hits else None


def _boot_pairs(run):
    st = getattr(run, "_tlog", None)
    if st is None or not st.boot_t:
        return None
    return np.concatenate(st.boot_t), np.concatenate(st.boot_b)


def _range(run) -> Tuple[float, float]:
    return float(run.start_time or 0.0), float(run.end_time or 0.0)


def by_boot(ref, other) -> Optional[dict]:
    """One of the two is a .tlog with boot times, the other runs on the autopilot's boot clock."""
    for tl, ap, sign in ((other, ref, +1), (ref, other, -1)):
        pairs = _boot_pairs(tl)
        if pairs is None or getattr(ap, "_tlog", None) is not None:
            continue
        trecv, tboot = pairs
        d = tboot - trecv                             # receive time + d = boot time (minus latency)
        ok = np.isfinite(d) & (tboot > 0)
        if ok.sum() < 5:
            continue
        d = d[ok]
        # an autopilot reboot during the recording starts a new boot clock: keep the largest group
        r = np.round(d)
        vals, counts = np.unique(r, return_counts=True)
        main = vals[np.argmax(counts)]
        g = d[np.abs(d - np.median(d[r == main])) < 2.0]
        # the reader placed the messages that carry the boot clock at boot time - D: shifting by the
        # same D puts them EXACTLY on the autopilot log's time (no radio delay left in them)
        st_ = getattr(tl, "_tlog", None)
        Ds = st_.boot_D if st_ is not None and st_.boot_D else [float(np.median(g))]
        delta_tl = min(Ds, key=lambda x: abs(x - float(np.median(g))))
        spread = float(np.percentile(g, 90) - np.percentile(g, 10))
        a0, a1 = _range(ap)
        b0, b1 = float(np.min(tboot[ok])), float(np.max(tboot[ok]))
        overlap = max(0.0, min(a1, b1) - max(a0, b0)) / max(1e-9, min(a1 - a0, b1 - b0))
        quality = "high" if overlap > 0.5 and spread < 0.5 else "medium" if overlap > 0.1 else "low"
        return {"method": "boot", "delta": sign * delta_tl, "spread": spread, "pairs": int(len(g)),
                "overlap": round(overlap, 3), "reboots": int(len(vals) > 1 and (counts > counts.max() * 0.05).sum() > 1),
                "quality": quality}
    return None


def _norm_event(e) -> Optional[str]:
    if e["kind"] in ("msg", "mode"):
        return f'{e["kind"]}:{e["text"].strip().lower()}'
    if e["kind"] == "event" and e["text"] in ("ARMED", "DISARMED"):
        return "arm:" + e["text"]
    return None


def by_events(ref, other) -> Optional[dict]:
    fa, fb = getattr(ref, "_flightlog", None), getattr(other, "_flightlog", None)
    if fa is None or fb is None:
        return None
    ga: Dict[str, List[float]] = {}
    gb: Dict[str, List[float]] = {}
    for e in fa.events:
        k = _norm_event(e)
        if k:
            ga.setdefault(k, []).append(e["t"])
    for e in fb.events:
        k = _norm_event(e)
        if k:
            gb.setdefault(k, []).append(e["t"])
    diffs, names = [], []
    for k in set(ga) & set(gb):
        a, b = ga[k], gb[k]
        if len(a) > 30 or len(b) > 30:
            continue                                  # too common to pair reliably
        for x in a:                                   # every pairing: the true offset repeats, others scatter
            for y in b:
                diffs.append(x - y)
                names.append(k)
    if len(diffs) < 2:
        return None
    diffs = np.asarray(diffs)
    # the densest 1-second window of differences
    srt = np.sort(diffs)
    j = np.searchsorted(srt, srt + 1.0, side="right") - np.arange(len(srt))
    i = int(np.argmax(j))
    win = srt[i:i + j[i]]
    if len(win) < 2:
        return None
    delta = float(np.median(win))
    used = sorted({names[k] for k in np.flatnonzero(np.abs(diffs - delta) <= 0.5)})
    quality = "high" if len(win) >= 4 else "medium"
    return {"method": "events", "delta": delta, "matched": int(len(win)), "spread": float(win.max() - win.min()),
            "examples": [u.split(":", 1)[1] for u in used[:4]], "quality": quality}


def _xcorr_delta(ta, ya, tb, yb, max_lag: Optional[float] = None, rate: float = 20.0, center: float = 0.0):
    """Shift d so that yb(t - d) best matches ya(t): normalised cross-correlation on a common grid."""
    ok_a, ok_b = np.isfinite(ya), np.isfinite(yb)
    ta, ya, tb, yb = ta[ok_a], ya[ok_a], tb[ok_b], yb[ok_b]
    if len(ta) < 20 or len(tb) < 20:
        return None
    dur = max(ta[-1] - ta[0], tb[-1] - tb[0])
    rate = min(rate, 40000.0 / max(dur, 1e-6))
    ga = np.arange(ta[0], ta[-1], 1 / rate)
    gb = np.arange(tb[0], tb[-1], 1 / rate)
    if len(ga) < 20 or len(gb) < 20:
        return None
    a = np.interp(ga, ta, ya); b = np.interp(gb, tb, yb)
    a = (a - a.mean()) / (a.std() or 1); b = (b - b.mean()) / (b.std() or 1)
    n, m = len(a), len(b)
    # Pearson correlation of the overlapping parts at every lag L (a[i] against b[i - L]):
    # the sum of products by FFT, the sums and sums of squares of each overlap by cumulative sums,
    # so a partial overlap is judged on its own data (not inflated by the rest of the signal)
    nf = 1 << (n + m - 2).bit_length()
    c = np.fft.irfft(np.fft.rfft(a, nf) * np.conj(np.fft.rfft(b, nf)), nf)
    lags = np.arange(-(m - 1), n)
    sab = np.concatenate([c[-(m - 1):], c[:n]]) if m > 1 else c[:n]
    i0, i1 = np.maximum(0, lags), np.minimum(n, lags + m)
    cnt = (i1 - i0).astype(np.float64)
    ca, ca2 = np.r_[0, np.cumsum(a)], np.r_[0, np.cumsum(a * a)]
    cb, cb2 = np.r_[0, np.cumsum(b)], np.r_[0, np.cumsum(b * b)]
    sa, sa2 = ca[i1] - ca[i0], ca2[i1] - ca2[i0]
    sb, sb2 = cb[i1 - lags] - cb[i0 - lags], cb2[i1 - lags] - cb2[i0 - lags]
    with np.errstate(invalid="ignore", divide="ignore"):
        num = sab - sa * sb / cnt
        den = np.sqrt(np.maximum(sa2 - sa * sa / cnt, 0) * np.maximum(sb2 - sb * sb / cnt, 0))
        score = num / den
    good = (cnt >= max(20, 0.25 * min(n, m))) & np.isfinite(score)
    if max_lag is not None:
        d_all = ga[0] - gb[0] + lags / rate
        good &= np.abs(d_all - center) <= max_lag
    if not good.any():
        return None
    # over a short overlap two smooth signals look straight and correlate ~1 by chance: weigh the
    # correlation by how much of the shorter recording overlaps (the true shift overlaps it all)
    pearson = score
    score = np.where(good, pearson * np.sqrt(cnt / min(n, m)), -np.inf)
    k = int(np.argmax(score))
    frac = 0.0                                          # sub-sample peak: a parabola through the top three
    if 0 < k < len(score) - 1 and np.isfinite(score[k - 1]) and np.isfinite(score[k + 1]):
        den2 = score[k - 1] - 2 * score[k] + score[k + 1]
        if den2 < 0:
            frac = 0.5 * (score[k - 1] - score[k + 1]) / den2
    delta = ga[0] - gb[0] + (lags[k] + frac) / rate
    r = float(min(1.0, pearson[k]))
    return float(delta), (r if np.isfinite(r) else 0.0)


_UNIT = re.compile(r" \[([^\]]*)\]$")
_CONV = {("deg", "rad"): 57.29577951308232, ("rad", "deg"): 1 / 57.29577951308232, ("m", "mm"): 1e-3, ("mm", "m"): 1e3,
         ("m", "cm"): 1e-2, ("cm", "m"): 1e2, ("V", "mV"): 1e-3, ("mV", "V"): 1e3}


def _scale(na, nb, ya, yb) -> float:
    """Factor that puts the other signal in the reference's units (for the check plot): from the units
    when both are known, else from the spread of the values."""
    ua, ub = _UNIT.search(na), _UNIT.search(nb)
    if ua and ub:
        if ua.group(1) == ub.group(1):
            return 1.0
        f = _CONV.get((ua.group(1), ub.group(1)))
        if f:
            return f
    if "roll" in nb.lower() or "pitch" in nb.lower():
        if ub and ub.group(1) == "rad" and not ua:
            return 57.29577951308232                  # ArduPilot ATT is in degrees even without a unit tag
    sa, sb = float(np.nanstd(ya)) or 1.0, float(np.nanstd(yb)) or 1.0
    return sa / sb


def _same_names(ref, other) -> List[Tuple[str, str]]:
    """Signals with the same name in both files (any file type: CSV, MAT, logs) - the most varied first."""
    common = [n for n in ref.signals if n in other.signals and not re.search(r"(^|[._ ])(time|timestamp|t)($|[._ \[])", n, re.I)]
    scored = []
    for n in common[:400]:
        y = np.asarray(ref.signals[n].data, dtype=np.float64)
        if y.size < 20 or ref.signals[n].labels:
            continue
        sd = float(np.nanstd(y[:: max(1, y.size // 5000)]))
        if np.isfinite(sd) and sd > 0:
            scored.append((sd / (abs(float(np.nanmean(y))) + sd), n))
    return [(n, n) for _s, n in sorted(scored, reverse=True)[:4]]


def by_signal(ref, other, ref_sig: Optional[str] = None, other_sig: Optional[str] = None,
              near: Optional[float] = None, max_lag: Optional[float] = None) -> Optional[dict]:
    """Correlate a pair of the same quantity: the user's pair, else known flight-log pairs, else
    signals with the same name in both files. max_lag: search only within +-max_lag s of the current
    alignment (periodic signals, where correlation could lock onto the wrong cycle)."""
    pairs = [(ref_sig, other_sig)] if ref_sig and other_sig else []
    same = False
    if not pairs:
        for a, b in PAIRS:
            for x, y in ((a, b), (b, a)):
                na, nb = _find(ref, x), _find(other, y)
                if na and nb:
                    pairs.append((na, nb))
    if not pairs:
        pairs, same = _same_names(ref, other), True
    if near is None and max_lag is not None:
        near = float(other.time_offset or 0) - float(ref.time_offset or 0)     # the current alignment
    best = None
    for na, nb in pairs[:4]:
        if na not in ref.signals or nb not in other.signals:
            continue
        ta, ya = ref.get_signal_data(na)
        tb, yb = other.get_signal_data(nb)
        ta = np.asarray(ta, dtype=np.float64) - float(ref.time_offset or 0)
        tb = np.asarray(tb, dtype=np.float64) - float(other.time_offset or 0)
        r = _xcorr_delta(ta, np.asarray(ya, dtype=np.float64), tb, np.asarray(yb, dtype=np.float64),
                         max_lag=None if near is None else (max_lag or 30.0), center=near or 0.0)
        if near is not None and r is None:
            continue
        if r and (best is None or r[1] > best["corr"]):
            best = {"method": "signal", "delta": r[0], "corr": round(r[1], 3), "pair": [na, nb], "sameNames": same,
                    "scale": _scale(na, nb, ya, yb),
                    "quality": "high" if r[1] > 0.9 else "medium" if r[1] > 0.6 else "low"}
    return best


FEATURES = ("rise", "fall", "step", "change", "max", "min", "start")


def _pick(idx, occurrence: int):
    if not len(idx):
        return None
    if occurrence < 0:
        return idx[-1]
    return idx[occurrence - 1] if 0 < occurrence <= len(idx) else None


def feature_time(t: np.ndarray, y: np.ndarray, kind: str, level_pct: float = 50.0, occurrence: int = 1) -> Optional[float]:
    """The time of a recognisable moment in a signal, in its own time:
      rise / fall  crossing level_pct % of the signal's range upward / downward (interpolated)
      step         the biggest jump between two samples       change  the first change of value (states)
      max / min    the highest / lowest sample                 start   the first valid sample
    occurrence: 1 = first, 2 = second..., -1 = last (rise, fall, change)."""
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(y) & np.isfinite(t)
    t, y = t[ok], y[ok]
    if len(t) < 2:
        return None
    if kind == "start":
        return float(t[0])
    if kind in ("max", "min"):
        return float(t[int(np.argmax(y) if kind == "max" else np.argmin(y))])
    if kind == "step":
        k = int(np.argmax(np.abs(np.diff(y))))
        return float((t[k] + t[k + 1]) / 2)
    if kind == "change":
        k = _pick(np.flatnonzero(np.diff(y) != 0) + 1, occurrence)
        return None if k is None else float(t[k])
    lo, hi = float(np.min(y)), float(np.max(y))
    if hi <= lo:
        return None
    lev = lo + (hi - lo) * level_pct / 100.0
    a, b = y[:-1], y[1:]
    k = _pick(np.flatnonzero((a < lev) & (b >= lev) if kind == "rise" else (a > lev) & (b <= lev)), occurrence)
    if k is None:
        return None
    f = (lev - y[k]) / (y[k + 1] - y[k])
    return float(t[k] + f * (t[k + 1] - t[k]))


def by_feature(ref, other, ref_sig: str, other_sig: str, kind: str, level_pct: float = 50.0,
               occurrence: int = 1) -> Optional[dict]:
    """The same moment recognised in a signal of each file (a trigger, a power-on step, a launch...)."""
    if ref_sig not in ref.signals or other_sig not in other.signals or kind not in FEATURES:
        return None
    ta, ya = ref.get_signal_data(ref_sig)
    tb, yb = other.get_signal_data(other_sig)
    fa = feature_time(np.asarray(ta) - float(ref.time_offset or 0), ya, kind, level_pct, occurrence)
    fb = feature_time(np.asarray(tb) - float(other.time_offset or 0), yb, kind, level_pct, occurrence)
    if fa is None or fb is None:
        return {"method": "feature", "error": "notFound", "found": [fa is not None, fb is not None],
                "quality": "low", "delta": 0.0, "kind": kind}
    return {"method": "feature", "delta": fa - fb, "pair": [ref_sig, other_sig], "kind": kind,
            "at": [fa + float(ref.time_offset or 0), fb + float(other.time_offset or 0)],
            "quality": "medium", "scale": _scale(ref_sig, other_sig, ya, yb)}


def suggest(ref, other, ref_sig=None, other_sig=None, feature=None, max_lag=None) -> List[dict]:
    """All methods that apply, best first, each with the offset to apply to `other`."""
    cands = []
    if feature and ref_sig and other_sig:
        r = by_feature(ref, other, ref_sig, other_sig, feature.get("kind", "rise"), float(feature.get("levelPct", 50)),
                       int(feature.get("occurrence", 1)))
        if r:
            cands.append(r)
    elif ref_sig and other_sig:
        r = by_signal(ref, other, ref_sig, other_sig, max_lag=max_lag)
        if r:
            cands.append(r)
    else:
        for f in (by_boot, by_events, by_signal):
            try:
                r = f(ref, other)
            except Exception:           # one method failing must not hide the others' answers
                log.warning("alignment by %s failed", f.__name__, exc_info=True)
                r = None
            if r:
                cands.append(r)
    # what to plot to check an alignment by eye: a pair of the same quantity, and both flight modes
    own = next((c for c in cands if c.get("pair")), None)
    sig = own or (by_signal(ref, other) if cands else None)
    modes = [_find(r, n) for r, n in ((ref, "MODE.Mode"), (other, "HEARTBEAT.custom_mode"), (ref, "HEARTBEAT.custom_mode"),
                                      (other, "MODE.Mode"), (ref, "vehicle_status.nav_state"), (other, "vehicle_status.nav_state"))]
    check = {"pair": sig["pair"] if sig else None, "scale": sig.get("scale", 1.0) if sig else 1.0,
             "refMode": modes[0] or modes[2] or modes[4], "otherMode": modes[1] or modes[3] or modes[5]}
    base = float(ref.time_offset or 0.0)
    for c in cands:
        c["check"] = check
        c["offset"] = base + c["delta"]
        c["current"] = float(other.time_offset or 0.0)
    rank = {"high": 0, "medium": 1, "low": 2}
    order = {"boot": 0, "events": 1, "signal": 2, "feature": 3}
    cands.sort(key=lambda c: ("error" in c, rank[c["quality"]], order[c["method"]]))
    good = [c for c in cands if "error" not in c]
    for c in good[1:]:                                 # do the candidates agree? (within 0.5 s of the best one)
        c["agrees"] = abs(c["delta"] - good[0]["delta"]) < 0.5
    return cands
