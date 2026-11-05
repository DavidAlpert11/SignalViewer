"""
ArduPilot's gyro filters from a log's parameters - what ArduPilot's Filter Review web tool shows:
the harmonic notch filters (INS_HNTCH_*, INS_HNTC2_*) at the centre frequencies they had in the
flight (FTN / FTNS / FCN messages, else from their mode), and the gyro low-pass (INS_GYRO_FILTER).

    filter_setup(params, signals_of, t0, t1) -> {"notches": [...], "lpf": Hz | None}
    response(setup, f, fs) -> gain (0..1) at each frequency f: what the filters let through

The response is the product of the filters' magnitudes, each a biquad with ArduPilot's own
coefficients (NotchFilter.cpp, LowPassFilter2p.cpp), so a spectrum of the gyro BEFORE the filters
times the response estimates the spectrum after them.
"""
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

# INS_HNTCH_MODE
MODES = {0: "fixed", 1: "throttle", 2: "RPM sensor", 3: "ESC telemetry", 4: "in-flight FFT", 5: "RPM sensor 2"}


def _harmonics(mask: int) -> List[int]:
    return [k + 1 for k in range(16) if mask & (1 << k)]


def _notch_q(center: float, bw: float) -> float:
    """NotchFilter::calculate_A_and_Q: Q from the centre and the bandwidth."""
    if center <= 0.5 * bw:
        return 0.0
    octaves = np.log2(center / (center - bw / 2.0)) * 2.0
    return float(np.sqrt(2 ** octaves) / (2 ** octaves - 1.0))


def _biquad_gain(b: Tuple[float, float, float], a: Tuple[float, float], f: np.ndarray, fs: float) -> np.ndarray:
    z = np.exp(-2j * np.pi * f / fs)
    num = b[0] + b[1] * z + b[2] * z * z
    den = 1.0 + a[0] * z + a[1] * z * z
    return np.abs(num / den)


def notch_gain(f: np.ndarray, fs: float, center: float, bw: float, att_db: float) -> np.ndarray:
    """|H(f)| of ArduPilot's notch biquad (NotchFilter::init_with_A_and_Q)."""
    q = _notch_q(center, bw)
    if not (center > 0 and center < 0.5 * fs and q > 0):
        return np.ones_like(f)
    A = 10 ** (-att_db / 40.0)
    omega = 2 * np.pi * center / fs
    alpha = np.sin(omega) / (2 * q)
    b0, b1, b2 = 1 + alpha * A * A, -2 * np.cos(omega), 1 - alpha * A * A
    a0, a1, a2 = 1 + alpha, -2 * np.cos(omega), 1 - alpha
    return _biquad_gain((b0 / a0, b1 / a0, b2 / a0), (a1 / a0, a2 / a0), f, fs)


def lpf2p_gain(f: np.ndarray, fs: float, cutoff: float) -> np.ndarray:
    """|H(f)| of ArduPilot's second-order low-pass (LowPassFilter2p, a Butterworth biquad)."""
    if not (cutoff > 0 and cutoff < 0.5 * fs):
        return np.ones_like(f)
    fr = fs / cutoff
    ohm = np.tan(np.pi / fr)
    c = 1.0 + 2.0 * np.cos(np.pi / 4.0) * ohm + ohm * ohm
    b0 = ohm * ohm / c
    a1 = 2.0 * (ohm * ohm - 1.0) / c
    a2 = (1.0 - 2.0 * np.cos(np.pi / 4.0) * ohm + ohm * ohm) / c
    return _biquad_gain((b0, 2 * b0, b0), (a1, a2), f, fs)


def _centres(signals_of: Callable[[str], Optional[Tuple[np.ndarray, np.ndarray]]], inst: int,
             t0: Optional[float], t1: Optional[float]) -> List[float]:
    """The notch's base frequencies over [t0, t1] as the log has them: per motor (FTN NF1..), one
    (FTNS NF), or the 1st-harmonic centres (FCN CF1.. / FCNS CF). The median of each source."""
    def cut(tv):
        t, y = np.asarray(tv[0], dtype=np.float64), np.asarray(tv[1], dtype=np.float64)
        sel = np.isfinite(y) & (y > 0)
        if t0 is not None and t1 is not None:
            sel &= (t >= min(t0, t1)) & (t <= max(t0, t1))
        return y[sel]
    n_on = signals_of(f"FTN[{inst}].NDn")
    count = None
    if n_on is not None:
        v = cut(n_on)
        if len(v):
            count = int(np.median(v))
    for msg, field in (("FTN", "NF"), ("FCN", "CF")):
        out = []
        for k in range(1, 13):
            tv = signals_of(f"{msg}[{inst}].{field}{k}")
            if tv is None:
                break
            v = cut(tv)
            if len(v):
                out.append(float(np.median(v)))
        if out:
            return out[:count] if count else out
    for msg, field in (("FTNS", "NF"), ("FCNS", "CF")):
        tv = signals_of(f"{msg}[{inst}].{field}")
        if tv is not None:
            v = cut(tv)
            if len(v):
                return [float(np.median(v))]
    return []


def filter_setup(params: Dict[str, float], signals_of: Callable[[str], Optional[Tuple[np.ndarray, np.ndarray]]],
                 t0: Optional[float] = None, t1: Optional[float] = None) -> Dict:
    notches = []
    for inst, pre in enumerate(("INS_HNTCH_", "INS_HNTC2_")):
        if not params.get(pre + "ENABLE"):
            continue
        freq, bw = float(params.get(pre + "FREQ", 80) or 0), float(params.get(pre + "BW", 40) or 0)
        att = float(params.get(pre + "ATT", 40) or 40)
        mode = int(params.get(pre + "MODE", 0) or 0)
        harm = _harmonics(int(params.get(pre + "HMNCS", 3) or 0))
        opts = int(params.get(pre + "OPTS", 0) or 0)
        base = _centres(signals_of, inst, t0, t1)
        source = "log"
        if not base:
            base, source = [freq], "parameter"
        # the bandwidth keeps its ratio to the frequency (a fixed Q) across harmonics and sources
        ratio = bw / freq if freq > 0 else 0.5
        lines = sorted({round(k * f0, 2) for f0 in base for k in harm})
        notches.append({"name": pre.rstrip("_"), "instance": inst, "mode": MODES.get(mode, str(mode)), "base": base,
                        "baseFrom": source, "harmonics": harm, "lines": lines, "ratio": ratio, "att": att,
                        "composite": 3 if opts & 16 and not opts & 1 else 2 if opts & 1 else 1})
    lpf = params.get("INS_GYRO_FILTER")
    return {"notches": notches, "lpf": float(lpf) if lpf else None}


def response(setup: Dict, f: np.ndarray, fs: float) -> np.ndarray:
    f = np.asarray(f, dtype=np.float64)
    g = np.ones_like(f)
    for n in setup["notches"]:
        for c in n["lines"]:
            bw = n["ratio"] * c
            # double / triple notch: ArduPilot spreads the copies around the centre; modelled as the
            # same notch applied that many times (the depth adds up, as theirs does near the centre)
            g = g * notch_gain(f, fs, c, bw, n["att"]) ** n["composite"]
    if setup.get("lpf"):
        g = g * lpf2p_gain(f, fs, setup["lpf"])
    return g
