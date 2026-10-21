"""A4: write docs/validation.md from the validation cases (backend/svcore/validation.py).

    python tools/make_validation_doc.py

The page shows what each case checks, the reference, the expected value, what this build measures
and the tolerance. A test (backend/tests/test_validation.py) fails when the page is out of date.
Numbers are rounded for the page, so re-running on another machine gives the same file.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

HEAD = """# Validation

Every number Signal Viewer computes for you – a spectrum, a filter, a derivative, a mean, a
comparison, a coordinate conversion – is checked against a reference that does **not** come from
the app: a closed-form result, a definition (WGS84) or an independent textbook computation.

The same cases run in the test suite on every change, and you can run them yourself on your own
machine and installation:

```bash
signalviewer-cli validate                  # a line per case; exit code 0 = all within tolerance
signalviewer-cli validate --junit v.xml    # the same as JUnit XML, for a qualification record
```

| | What is checked | Reference | Expected | Measured | Tolerance | |
|---|---|---|---|---|---|---|
"""

TAIL = """
*Measured* is what this version computes, rounded for the page. *Tolerance* is the largest allowed
|measured − expected|; where a case reads a spectrum or a time from samples, it is the resolution of
that grid.

## Notes on the conventions

- **FFT** shows the single-sided amplitude: a sine of amplitude *A* reads *A* when its frequency is on
  a frequency bin. Between bins the Hann window reads up to 1.4 dB (15 %) low (scalloping) – use
  Welch or a longer window when the exact amplitude of an off-bin tone matters. Signals with gaps
  are put on an even time grid first (V03); amplitudes then read low by about the share of time the
  gaps cover ([Known limitations](limitations.md)).
- **Welch** is a one-sided power spectral density in unit²/Hz: integrating it over frequency gives
  the variance (V05).
- **Low- / high-pass** filters are 4th-order Butterworth run forward and backward (zero phase, V09);
  the cut-off is the −3 dB point of the result (V06, V07). To reproduce a result in MATLAB or
  SciPy: `filtfilt(butter(4, fd/(fs/2)), x)` with `fd` ≈ 1.12 × the cut-off for a low-pass and
  0.90 × for a high-pass (exactly: `svcore.ops.zero_phase_design_cutoff`). A plain
  `filtfilt(butter(4, fc/(fs/2)), x)` is at −6 dB at `fc`.
- **Mean, RMS, std**: on evenly spaced samples, the plain sample statistics (std: population, as
  NumPy's default; MATLAB's `std` divides by N − 1). On uneven sampling they are weighted by time
  (V13), marked ⏱ in the Inspector.
- **Attitude**: Euler angles in aerospace order (yaw, then pitch, then roll), body → NED as
  ArduPilot and PX4 log it (V22, V23).
"""


def _num(v: float, unit: str) -> str:
    """5 significant digits, and round-off noise (< 1e-12) as 0, so the page is the same on every
    machine (BLAS and NumPy versions differ in the last bits)."""
    import math
    if not math.isfinite(v):
        return "–"
    if abs(v) < 1e-12:
        v = 0.0
    s = f"{v:.5g}" if abs(v) < 1e6 else f"{v:,.4f}".replace(",", " ")
    return f"{s} {unit}".strip()


def render() -> str:
    from svcore.validation import run_all
    from app.version import __version__
    rows = run_all()
    lines = []
    for r in rows:
        unit = r["unit"]
        tol = _num(r["tol"], unit) if r["tol"] else "exact"
        lines.append(f"| {r['id']} | **{r['area']}** – {r['title']} | {r['reference']} | "
                     f"{_num(r['expected'], unit)} | {_num(r['measured'], unit)} | {tol} | "
                     f"{'✓' if r['ok'] else '✗ **failed**'} |")
    n_ok = sum(r["ok"] for r in rows)
    summary = f"\n**{n_ok} of {len(rows)} cases within tolerance** (Signal Viewer {__version__}).\n"
    return HEAD + "\n".join(lines) + "\n" + summary + TAIL


if __name__ == "__main__":
    out = os.path.join(ROOT, "docs", "validation.md")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render())
    print(out)
