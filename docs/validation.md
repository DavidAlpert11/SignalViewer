# Validation

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
| V01 | **Spectrum** – FFT amplitude of a sine (Hann window, on a frequency bin) | a sine of amplitude A shows as A | 2 | 2 | 0.002 | ✓ |
| V02 | **Spectrum** – FFT amplitude of the smaller of two tones (1.0 at 12 Hz, 0.25 at 55 Hz) | each tone keeps its own amplitude | 0.25 | 0.25 | 0.001 | ✓ |
| V03 | **Spectrum** – FFT peak frequency of a 37 Hz tone with a 2 s logging pause | the tone's frequency; resolution 1/20 s = 0.05 Hz | 37 Hz | 37 Hz | 0.05 Hz | ✓ |
| V04 | **Spectrum** – Welch PSD of white noise (sigma = 1.5, fs = 1000 Hz): mean level | one-sided white noise: 2 sigma^2 / fs | 0.0045 unit^2/Hz | 0.0044936 unit^2/Hz | 0.000135 unit^2/Hz | ✓ |
| V05 | **Spectrum** – Welch PSD integrated over frequency (a sine of amplitude 2) | Parseval: the variance, A^2 / 2 = 2 | 2 | 2.0001 | 0.01 | ✓ |
| V06 | **Filter** – Low-pass gain at the cut-off (10 Hz, fs = 200 Hz) | half power: 1/sqrt(2) (-3 dB) | 0.70711 | 0.70711 | 0.005 | ✓ |
| V07 | **Filter** – High-pass gain at the cut-off (10 Hz, fs = 200 Hz) | half power: 1/sqrt(2) (-3 dB) | 0.70711 | 0.70711 | 0.005 | ✓ |
| V08 | **Filter** – Low-pass roll-off between 4x and 8x the cut-off | 4th-order Butterworth run twice: 2 x 24 = 48 dB per octave | 48 dB | 49.282 dB | 2 dB | ✓ |
| V09 | **Filter** – Delay of a filtered step (5 Hz low-pass) | zero phase: the 50 % crossing stays at the step (resolution one sample, 5 ms) | 10 s | 10 s | 0.005 s | ✓ |
| V10 | **Calculus** – Derivative of sin(2 pi 0.5 t) on jittered time: largest error | the analytic derivative pi cos(pi t) | 0 | 8.4315e-06 | 0.001 | ✓ |
| V11 | **Calculus** – Integral of cos(pi t) on jittered time: largest error | the analytic integral sin(pi t) / pi | 0 | 3.3945e-07 | 1e-06 | ✓ |
| V12 | **Statistics** – RMS of a sine of amplitude 3 (whole periods) | A / sqrt(2) | 2.1213 | 2.1213 | 1e-09 | ✓ |
| V13 | **Statistics** – Mean of variable-step output (10 for 1 s in 1 ms steps, then 0 for 98 s in 1 s steps) | the time average of the drawn curve (trapezoid) | 0.10096 | 0.10096 | 1e-09 | ✓ |
| V14 | **Display** – Decimation keeps a one-sample spike in 5 million samples | the spike's value, 99 | 99 | 99 | exact | ✓ |
| V15 | **Compare** – RMS difference of two runs that differ by 0.3 sin(...) | 0.3 / sqrt(2) | 0.21213 | 0.21213 | 1e-09 | ✓ |
| V16 | **Compare** – Correlation of sin and cos over whole periods | orthogonal: 0 | 0 | 0 | 1e-09 | ✓ |
| V17 | **Compare** – Difference of headings 359 deg and 1 deg | around the circle: 2 deg | 2 deg | 2 deg | 1e-09 deg | ✓ |
| V18 | **Compare** – Automatic time alignment: shift found for a run whose data is 1.234 s late | -1.234 s (move it back); the search grid is 20 Hz, refined between samples | -1.234 s | -1.2386 s | 0.01 s | ✓ |
| V19 | **Frames** – LLA -> ECEF of the North Pole (height 0): z | WGS84 semi-minor axis b = 6 356 752.3142 m | 6 356 752.3142 m | 6 356 752.3142 m | 0.001 m | ✓ |
| V20 | **Frames** – LLA -> ECEF of lat 0, lon 90, height 100 m: y | WGS84 semi-major axis a + 100 = 6 378 237 m | 6 378 237.0000 m | 6 378 237.0000 m | 1e-06 m | ✓ |
| V21 | **Frames** – ECEF -> LLA round trip at the Sea of Galilee (32.8 N, 35.6 E, -212 m): height | the starting height; sub-millimetre | -212 m | -212 m | 0.001 m | ✓ |
| V22 | **Frames** – Body -> NED: the nose (body X) at pitch 30 deg, yaw 90 deg: Down component | nose up 30 deg: D = -sin 30 = -0.5 | -0.5 | -0.5 | 1e-12 | ✓ |
| V23 | **Frames** – Body -> NED: the nose at pitch 30 deg, yaw 90 deg: East component | heading east: E = cos 30 = 0.8660 | 0.86603 | 0.86603 | 1e-12 | ✓ |

**23 of 23 cases within tolerance** (Signal Viewer 1.10.0).

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
