"""
Signal Viewer - numerical validation (A4).

Every number the app computes for an engineer - a spectrum, a filter, a derivative, a mean, a
comparison, a coordinate conversion - checked against a reference that does not come from the app:
a closed-form result, a definition (WGS84), or an independent textbook computation. Each case says
what it checks, the expected value, what the app gives, and the tolerance.

The same cases run three ways:
  * the test suite (backend/tests/test_validation.py) - any regression fails the build;
  * `signalviewer-cli validate` - anyone can re-run them on their own machine and installation
    (tool qualification: "show me that this build computes correctly here");
  * tools/make_validation_doc.py writes docs/validation.md with the measured numbers.

Cases use only the app's own functions (svcore) for the measured value; references are computed
here with plain NumPy or written down.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List

import numpy as np


@dataclass
class Result:
    expected: float
    measured: float
    tol: float              # absolute tolerance on |measured - expected|
    unit: str = ""

    @property
    def error(self) -> float:
        return abs(self.measured - self.expected)

    @property
    def ok(self) -> bool:
        return bool(np.isfinite(self.measured)) and self.error <= self.tol


@dataclass
class Case:
    id: str
    area: str
    title: str
    reference: str          # where the expected value comes from
    run: Callable[[], Result]


CASES: List[Case] = []


def case(id: str, area: str, title: str, reference: str):
    def deco(fn: Callable[[], Result]) -> Callable[[], Result]:
        CASES.append(Case(id, area, title, reference, fn))
        return fn
    return deco


def _peak(f: np.ndarray, m: np.ndarray):
    i = int(np.argmax(m))
    return float(f[i]), float(m[i])


def _amp_at(f: np.ndarray, m: np.ndarray, f0: float) -> float:
    return float(m[int(np.argmin(np.abs(f - f0)))])


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    """Trapezoid rule written out (np.trapezoid is NumPy 2 only; requirements allow 1.24)."""
    return float(np.sum(0.5 * (y[1:] + y[:-1]) * np.diff(x)))


def _mid(x: np.ndarray) -> np.ndarray:
    return x[len(x) // 4: -len(x) // 4]


# ------------------------------------------------------------------------------------- spectra

@case("V01", "Spectrum", "FFT amplitude of a sine (Hann window, on a frequency bin)",
      "a sine of amplitude A shows as A")
def _v01() -> Result:
    from svcore.ops import compute_fft
    t = np.arange(0, 20, 1 / 400)
    f, m = compute_fft(t, 2.0 * np.sin(2 * np.pi * 37 * t) + 0.5)
    return Result(2.0, _amp_at(f, m, 37.0), 2e-3)


@case("V02", "Spectrum", "FFT amplitude of the smaller of two tones (1.0 at 12 Hz, 0.25 at 55 Hz)",
      "each tone keeps its own amplitude")
def _v02() -> Result:
    from svcore.ops import compute_fft
    t = np.arange(0, 20, 1 / 400)
    y = np.sin(2 * np.pi * 12 * t) + 0.25 * np.sin(2 * np.pi * 55 * t + 1.0)
    f, m = compute_fft(t, y)
    return Result(0.25, _amp_at(f, m, 55.0), 1e-3)


@case("V03", "Spectrum", "FFT peak frequency of a 37 Hz tone with a 2 s logging pause",
      "the tone's frequency; resolution 1/20 s = 0.05 Hz")
def _v03() -> Result:
    from svcore.ops import compute_fft
    t = np.arange(0, 20, 1 / 400)
    keep = ~((t > 8) & (t < 10))
    f, m = compute_fft(t[keep], np.sin(2 * np.pi * 37 * t[keep]))
    return Result(37.0, _peak(f, m)[0], 0.05, "Hz")


@case("V04", "Spectrum", "Welch PSD of white noise (sigma = 1.5, fs = 1000 Hz): mean level",
      "one-sided white noise: 2 sigma^2 / fs")
def _v04() -> Result:
    from svcore.ops import compute_welch
    fs, sigma = 1000.0, 1.5
    rng = np.random.default_rng(4)
    t = np.arange(0, 120, 1 / fs)
    f, p = compute_welch(t, rng.normal(0, sigma, len(t)))
    band = (f > 0.05 * fs) & (f < 0.45 * fs)
    return Result(2 * sigma ** 2 / fs, float(np.mean(p[band])), 0.03 * 2 * sigma ** 2 / fs, "unit^2/Hz")


@case("V05", "Spectrum", "Welch PSD integrated over frequency (a sine of amplitude 2)",
      "Parseval: the variance, A^2 / 2 = 2")
def _v05() -> Result:
    from svcore.ops import compute_welch
    t = np.arange(0, 20, 1 / 400)
    f, p = compute_welch(t, 2.0 * np.sin(2 * np.pi * 37 * t))
    return Result(2.0, _trapz(p, f), 0.01)


# ------------------------------------------------------------------------------------- filters

def _gain(kind: str, fc: float, f: float, fs: float = 200.0) -> float:
    from svcore.ops import apply_filter
    t = np.arange(0, 40, 1 / fs)
    x = np.sin(2 * np.pi * f * t)
    return float(np.std(_mid(apply_filter(t, x, kind, fc))) / np.std(_mid(x)))


@case("V06", "Filter", "Low-pass gain at the cut-off (10 Hz, fs = 200 Hz)",
      "half power: 1/sqrt(2) (-3 dB)")
def _v06() -> Result:
    return Result(1 / np.sqrt(2), _gain("lowpass", 10.0, 10.0), 5e-3)


@case("V07", "Filter", "High-pass gain at the cut-off (10 Hz, fs = 200 Hz)",
      "half power: 1/sqrt(2) (-3 dB)")
def _v07() -> Result:
    return Result(1 / np.sqrt(2), _gain("highpass", 10.0, 10.0), 5e-3)


@case("V08", "Filter", "Low-pass roll-off between 4x and 8x the cut-off",
      "4th-order Butterworth run twice: 2 x 24 = 48 dB per octave")
def _v08() -> Result:
    g1, g2 = _gain("lowpass", 2.0, 8.0), _gain("lowpass", 2.0, 16.0)
    return Result(48.0, float(20 * np.log10(g1 / g2)), 2.0, "dB")


@case("V09", "Filter", "Delay of a filtered step (5 Hz low-pass)",
      "zero phase: the 50 % crossing stays at the step (resolution one sample, 5 ms)")
def _v09() -> Result:
    from svcore.ops import apply_filter
    t = np.arange(0, 20, 1 / 200)
    y = apply_filter(t, (t >= 10).astype(float), "lowpass", 5.0)
    return Result(10.0, float(t[int(np.argmax(y >= 0.5))]), 1 / 200, "s")


# ------------------------------------------------------------------------------------ calculus

def _jittered_time(n: int = 20000, dt: float = 0.001, seed: int = 9) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.sort(np.arange(n) * dt + rng.uniform(-0.3 * dt, 0.3 * dt, n))


@case("V10", "Calculus", "Derivative of sin(2 pi 0.5 t) on jittered time: largest error",
      "the analytic derivative pi cos(pi t)")
def _v10() -> Result:
    from svcore.analysis import compute
    t = _jittered_time()
    _, d = compute("derivative", [(t, np.sin(np.pi * t))], {})
    err = float(np.max(np.abs(d[1:-1] - np.pi * np.cos(np.pi * t[1:-1]))))
    return Result(0.0, err, 1e-3)


@case("V11", "Calculus", "Integral of cos(pi t) on jittered time: largest error",
      "the analytic integral sin(pi t) / pi")
def _v11() -> Result:
    from svcore.analysis import compute
    t = _jittered_time()
    _, i = compute("integral", [(t, np.cos(np.pi * t))], {})
    ref = (np.sin(np.pi * t) - np.sin(np.pi * t[0])) / np.pi
    return Result(0.0, float(np.max(np.abs(i - ref))), 1e-6)


# ---------------------------------------------------------------------------------- statistics

@case("V12", "Statistics", "RMS of a sine of amplitude 3 (whole periods)",
      "A / sqrt(2)")
def _v12() -> Result:
    from svcore.ops import compute_signal_stats
    t = np.arange(0, 10, 0.001)
    return Result(3 / np.sqrt(2), compute_signal_stats(t, 3 * np.sin(2 * np.pi * 2 * t))["rms"], 1e-9)


@case("V13", "Statistics", "Mean of variable-step output (10 for 1 s in 1 ms steps, then 0 for 98 s in 1 s steps)",
      "the time average of the drawn curve (trapezoid)")
def _v13() -> Result:
    from svcore.ops import compute_signal_stats
    t = np.concatenate([np.arange(0, 1, 0.001), np.arange(1, 100, 1.0)])
    y = np.where(t < 1, 10.0, 0.0)
    ref = _trapz(y, t) / float(t[-1] - t[0])
    return Result(ref, compute_signal_stats(t, y)["mean"], 1e-9)


# ----------------------------------------------------------------------------------- display

@case("V14", "Display", "Decimation keeps a one-sample spike in 5 million samples",
      "the spike's value, 99")
def _v14() -> Result:
    from svcore.decimate import minmax_decimate
    n = 5_000_000
    y = np.zeros(n)
    y[3_141_592] = 99.0
    _, dy = minmax_decimate(np.arange(n) / 1000.0, y, 4000)
    return Result(99.0, float(np.max(dy)), 0.0)


# ------------------------------------------------------------------------------------ compare

@case("V15", "Compare", "RMS difference of two runs that differ by 0.3 sin(...)",
      "0.3 / sqrt(2)")
def _v15() -> Result:
    from svcore.compare import metrics
    t = np.arange(0, 10, 0.001)
    b = 5 * np.sin(2 * np.pi * 0.2 * t)
    return Result(0.3 / np.sqrt(2), metrics(b, b + 0.3 * np.sin(2 * np.pi * 3 * t), None, None)["rmsDiff"], 1e-9)


@case("V16", "Compare", "Correlation of sin and cos over whole periods",
      "orthogonal: 0")
def _v16() -> Result:
    from svcore.compare import metrics
    t = np.arange(0, 10, 0.001)
    return Result(0.0, metrics(np.sin(2 * np.pi * t), np.cos(2 * np.pi * t), None, None)["correlation"], 1e-9)


@case("V17", "Compare", "Difference of headings 359 deg and 1 deg",
      "around the circle: 2 deg")
def _v17() -> Result:
    from svcore.compare import metrics
    return Result(2.0, metrics(np.full(10, 359.0), np.full(10, 1.0), None, None, period=360.0)["maxAbsDiff"], 1e-9, "deg")


@case("V18", "Compare", "Automatic time alignment: shift found for a run whose data is 1.234 s late",
      "-1.234 s (move it back); the search grid is 20 Hz, refined between samples")
def _v18() -> Result:
    from svcore.sync import _xcorr_delta
    rng = np.random.default_rng(18)
    t = np.arange(0, 60, 0.01)
    y = np.convolve(rng.normal(size=len(t)), np.ones(50) / 50, "same")      # broadband, smoothed
    late = np.interp(t - 1.234, t, y)                                     # the same data 1.234 s later
    res = _xcorr_delta(t, y, t, late)
    return Result(-1.234, float(res[0]) if res else float("nan"), 0.01, "s")


# ------------------------------------------------------------------------------------- frames

@case("V19", "Frames", "LLA -> ECEF of the North Pole (height 0): z",
      "WGS84 semi-minor axis b = 6 356 752.3142 m")
def _v19() -> Result:
    from svcore.analysis import lla_to_ecef
    return Result(6356752.314245, float(lla_to_ecef(90.0, 0.0, 0.0)[2]), 1e-3, "m")


@case("V20", "Frames", "LLA -> ECEF of lat 0, lon 90, height 100 m: y",
      "WGS84 semi-major axis a + 100 = 6 378 237 m")
def _v20() -> Result:
    from svcore.analysis import lla_to_ecef
    return Result(6378237.0, float(lla_to_ecef(0.0, 90.0, 100.0)[1]), 1e-6, "m")


@case("V21", "Frames", "ECEF -> LLA round trip at the Sea of Galilee (32.8 N, 35.6 E, -212 m): height",
      "the starting height; sub-millimetre")
def _v21() -> Result:
    from svcore.analysis import ecef_to_lla, lla_to_ecef
    x, y, z = lla_to_ecef(32.8, 35.6, -212.0)
    return Result(-212.0, float(ecef_to_lla(x, y, z)[2]), 1e-3, "m")


@case("V22", "Frames", "Body -> NED: the nose (body X) at pitch 30 deg, yaw 90 deg: Down component",
      "nose up 30 deg: D = -sin 30 = -0.5")
def _v22() -> Result:
    from svcore.analysis import compute
    t = np.arange(0, 1, 0.1)
    one, zero = np.ones_like(t), np.zeros_like(t)
    sig = [(t, one), (t, zero), (t, zero), (t, zero), (t, 30 * one), (t, 90 * one)]
    _, d = compute("frame", sig, {"qty": "vector", "src": "body", "dst": "ned", "att": "euler", "axis": 2})
    return Result(-0.5, float(d[0]), 1e-12)


@case("V23", "Frames", "Body -> NED: the nose at pitch 30 deg, yaw 90 deg: East component",
      "heading east: E = cos 30 = 0.8660")
def _v23() -> Result:
    from svcore.analysis import compute
    t = np.arange(0, 1, 0.1)
    one, zero = np.ones_like(t), np.zeros_like(t)
    sig = [(t, one), (t, zero), (t, zero), (t, zero), (t, 30 * one), (t, 90 * one)]
    _, e = compute("frame", sig, {"qty": "vector", "src": "body", "dst": "ned", "att": "euler", "axis": 1})
    return Result(float(np.cos(np.radians(30))), float(e[0]), 1e-12)


# ------------------------------------------------------------------ judging (C4, round of 2026-11-08)

@case("V24", "Compare", "A 5 ms violation (+5) in 2 million samples, tolerance 0.1: largest difference found (the verdict must be FAIL)",
      "every sample is judged: the excursion, 5")
def _v24() -> Result:
    from svcore.compare import compare
    t = np.arange(2_000_000) * 0.001
    g = np.sin(2 * np.pi * 0.01 * t)
    r = g.copy()
    r[1_234_567:1_234_572] += 5.0                    # 5 samples, between the points a thinned grid keeps
    row = compare([("g/X", t, g), ("n/X", t, r)], "g/X", "linear", 0.1, None, max_points=20_000)["rows"][0]
    return Result(5.0, float(row["maxAbsDiff"]) if row.get("pass") is False else 0.0, 1e-9)


@case("V25", "Compare", "A 10 Hz golden ramp against a 1 kHz run with a +2 violation between two golden samples: largest difference (must FAIL)",
      "the run's own samples are judged too: 2")
def _v25() -> Result:
    from svcore.compare import compare
    tg, tr = np.arange(0, 100, 0.1), np.arange(0, 100, 0.001)
    r = 0.01 * tr                                    # a ramp: the golden run's straight lines are exact
    r[(tr > 50.02) & (tr < 50.07)] += 2.0            # golden samples at 50.0 and 50.1
    row = compare([("g/X", tg, 0.01 * tg), ("n/X", tr, r)], "g/X", "linear", 0.1, None)["rows"][0]
    return Result(2.0, float(row["maxAbsDiff"]) if row.get("pass") is False else 0.0, 1e-9)


@case("V26", "Conditions", "Mode == 5 on a change-only mode signal (0 at 0 s, 2 at 10 s, 5 at 20 s, 3 at 30 s): start of the stretch",
      "the mode is in force from its change: 20 s (resolution one sample of the 100 Hz signal, 0.01 s)")
def _v26() -> Result:
    from svcore.analysis import align_to
    from svcore.conditions import evaluate_condition
    tf = np.arange(0, 35, 0.01)
    sig = {"X": (tf, np.sin(tf)), "Mode": (np.array([0.0, 10.0, 20.0, 30.0]), np.array([0.0, 2.0, 5.0, 3.0]))}
    r = evaluate_condition("{X} > -10 and {Mode} == 5", sig.get, lambda n: None,
                           lambda t, ts, ys: align_to(t, ts, ys, "nearest"), is_state=lambda n: n == "Mode")
    return Result(20.0, float(r["intervals"][0][0]), 0.01, "s")


@case("V27", "Formulas", "A formula of a state signal (10 x mode; modes 0, 2, 5, 3): values the state does not have",
      "the value in force, never an interpolation: 0")
def _v27() -> Result:
    from svcore.analysis import compute
    tf = np.arange(0, 35, 0.01)
    tm, m = np.array([0.0, 10.0, 20.0, 30.0]), np.array([0.0, 2.0, 5.0, 3.0])
    _, y = compute("expr", [(tf, np.sin(tf)), (tm, m)], {"expr": "10 * v1"}, [False, True])
    y = y[np.isfinite(y)]
    return Result(0.0, float(np.sum(~np.isin(y, 10 * m))), 0.0)


@case("V28", "Formulas", "Sum and norm of three signals with one missing input: values that are not missing at that sample",
      "a missing input makes the result missing: 0")
def _v28() -> Result:
    from svcore.analysis import compute
    t = np.arange(5.0)
    sig = [(t, np.ones(5)), (t, np.array([2, np.nan, 2, 2, 2.0])), (t, 3 * np.ones(5))]
    _, a = compute("sum", sig, {})
    _, b = compute("norm", sig, {})
    return Result(0.0, float(np.isfinite(a[1])) + float(np.isfinite(b[1])), 0.0)


# ------------------------------------------------------------------ performance (P1)

@case("V29", "Plots", "A plot request (a zoomed window of 5 million samples) on a run with a time offset: time relative to the same request without one",
      "the offset shifts the window and the drawn points, not the whole time vector: the offset adds less than a quarter of "
      "what shifting the whole vector costs on the same machine (the fastest of 9 requests each; reported as 1 when so, "
      "else the offset's cost in units of that shift - so the page does not change with the machine)")
def _v29() -> Result:
    # Requests of a zoomed window take ~0.2 ms: a ratio of two such times is noise on a busy CI machine (a
    # macOS runner read 2.5 x). What the case guards is that the offset is not applied to all 5 million
    # samples, so the yardstick is that very cost, measured here, and the fastest run of each is compared.
    import time as _time
    from svcore.decimate import view_shifted
    from svcore.models import Run, Signal
    t = np.arange(5_000_000) * 0.001
    run = Run(file_path="v29", csv_display_name="v29", time=t)
    run.signals["y"] = Signal(name="y", data=np.sin(t), time=t)

    def request() -> float:                          # what /api/data does for one signal
        a = _time.perf_counter()
        x, y, off = run.signal_parts("y")
        view_shifted(x, y, off, (2500.0, 2510.0), 4000)
        return _time.perf_counter() - a

    def fastest(offset: float) -> float:
        run.time_offset = offset
        request()                                    # warm
        return min(request() for _ in range(9))

    def whole_shift() -> float:
        a = _time.perf_counter()
        _ = t + 12.5
        return _time.perf_counter() - a
    base, shifted = fastest(0.0), fastest(12.5)
    full = min(whole_shift() for _ in range(3))
    extra = max(0.0, shifted - base) / max(full, 1e-6)
    return Result(1.0, 1.0 if extra < 0.25 else extra, 0.0, "x")


def run_all() -> List[Dict]:
    """Every case as a row: id, area, title, reference, expected, measured, error, tol, unit, ok
    (a case that raises is a failed row with the error as its reference note)."""
    rows = []
    for c in CASES:
        try:
            r = c.run()
            rows.append({"id": c.id, "area": c.area, "title": c.title, "reference": c.reference,
                         "expected": r.expected, "measured": r.measured, "error": r.error, "tol": r.tol,
                         "unit": r.unit, "ok": r.ok})
        except Exception as e:          # a broken case is a failure, never a silent skip
            rows.append({"id": c.id, "area": c.area, "title": c.title, "reference": f"error: {e}",
                         "expected": float("nan"), "measured": float("nan"), "error": float("nan"),
                         "tol": float("nan"), "unit": "", "ok": False})
    return rows
