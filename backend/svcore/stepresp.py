"""
Step response of a control loop estimated from flight data - what ArduPilot's PID Review web tool
and PID-Analyzer do: the setpoint (the rate the controller asked for) is the input, the measured
rate the output; over many short overlapping windows the system's impulse response is found by
Wiener deconvolution, integrated to a step response, and the windows with enough stick / controller
activity are averaged.

    step_response(t_in, x, t_out, y, t0=None, t1=None) -> dict
        {"t": [s], "step": [..], "windows": n, "fs": Hz, "rise": s, "overshoot": %, "settle": s,
         "final": value} - or {"error": "..."} when the data cannot give one.
"""
from typing import Any, Dict, Optional

import numpy as np

WINDOW_S = 2.0        # each piece of flight looked at
LENGTH_S = 0.5        # the response shown, after a step
MIN_RATE = 40.0       # Hz: below this the response (tens of ms) cannot be seen
MAX_RATE = 1000.0     # Hz: the grid is never finer than this (the loop runs at 400 Hz typically)


def step_response(t_in: np.ndarray, x: np.ndarray, t_out: np.ndarray, y: np.ndarray,
                  t0: Optional[float] = None, t1: Optional[float] = None, length: float = LENGTH_S) -> Dict[str, Any]:
    t_in, x = np.asarray(t_in, dtype=np.float64), np.asarray(x, dtype=np.float64)
    t_out, y = np.asarray(t_out, dtype=np.float64), np.asarray(y, dtype=np.float64)
    ka, kb = np.isfinite(t_in) & np.isfinite(x), np.isfinite(t_out) & np.isfinite(y)
    t_in, x, t_out, y = t_in[ka], x[ka], t_out[kb], y[kb]
    if len(t_in) < 20 or len(t_out) < 20:
        return {"error": "too few samples"}
    lo, hi = max(t_in[0], t_out[0]), min(t_in[-1], t_out[-1])
    if t0 is not None and t1 is not None:
        lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
    if hi - lo < WINDOW_S:
        return {"error": "less than 2 s of both signals"}
    steps = np.diff(t_out[(t_out >= lo) & (t_out <= hi)])
    steps = steps[steps > 0]
    if not len(steps):
        return {"error": "too few samples"}
    rate = 1.0 / float(np.median(steps))
    if rate < MIN_RATE:
        return {"error": "rate", "rate": round(rate, 1)}
    fs = min(rate, MAX_RATE)
    g = np.arange(lo, hi, 1.0 / fs)
    xi, yi = np.interp(g, t_in, x), np.interp(g, t_out, y)
    n = int(round(WINDOW_S * fs))
    hop = max(1, n // 4)
    m = int(round(length * fs))
    win = np.hanning(n)
    steps_all, weights = [], []
    for s in range(0, len(g) - n + 1, hop):
        a, b = xi[s:s + n], yi[s:s + n]
        if np.std(a) < 1e-6:
            continue
        A = np.fft.rfft((a - a.mean()) * win, 2 * n)
        B = np.fft.rfft((b - b.mean()) * win, 2 * n)
        # Wiener deconvolution: a little noise power keeps the frequencies the input does not excite
        # from blowing up (PID-Analyzer's choice of regularisation, relative to the input's power)
        pa = np.abs(A) ** 2
        reg = 1e-3 * float(np.mean(pa)) + 1e-30
        h = np.fft.irfft(B * np.conj(A) / (pa + reg), 2 * n)[:m]
        steps_all.append(np.cumsum(h))
        weights.append(float(np.std(a)))
    if not steps_all:
        return {"error": "no setpoint activity"}
    w = np.asarray(weights)
    # the windows where the setpoint moved most carry the response; quiet hover adds only noise
    keep = w >= np.percentile(w, 50) if len(w) >= 4 else np.ones(len(w), bool)
    st = np.average(np.vstack(steps_all)[keep], axis=0, weights=w[keep])
    tt = np.arange(m) / fs
    final = float(np.mean(st[int(m * 0.6):])) if m > 10 else float(st[-1])
    out: Dict[str, Any] = {"t": tt, "step": st, "windows": int(keep.sum()), "fs": fs, "final": final}
    if abs(final) > 1e-6:
        norm = st / final
        i10 = np.flatnonzero(norm >= 0.1)
        i90 = np.flatnonzero(norm >= 0.9)
        if len(i10) and len(i90):
            out["rise"] = float(tt[i90[0]] - tt[i10[0]])
        out["overshoot"] = float(max(0.0, (np.max(norm) - 1.0) * 100.0))
        outside = np.flatnonzero(np.abs(norm - 1.0) > 0.05)
        out["settle"] = float(tt[outside[-1]]) if len(outside) and outside[-1] < m - 1 else None
    return out
