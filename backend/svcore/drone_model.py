"""A closed-form toy model of a drone's attitude loop (W14 example, W15 tests, W18 demo).

Not a simulation of any real aircraft - a small set of formulas with the right *shape*: more gain is faster
until the motors saturate, too little damping overshoots, an integral term fights wind but costs damping and
phase, a slow filter costs phase. Everything is numpy-vectorised: the W18 reference evaluates a whole fine grid
(~10^4 gain sets x scenarios) in well under a second.

The plant: a second-order attitude loop  J θ'' = u - d  with  u = Kp e + Ki ∫e + Kd ė.

    ωn  = sqrt(Kp / J)                                  natural frequency
    ζ   = Kd / (2 sqrt(Kp J))                           damping of the PD loop
    ζi  = max(0.05, ζ - 0.35 Ki / sqrt(Kp))             the integral term costs damping
    overshoot [%]   = 100 exp(-π ζi / sqrt(1 - ζi²))  (0 for ζi >= 1)  +  0.4 wind / (1 + Ki)
    motor_sat [-]   = (0.5 Kp + 0.3 Kd ωn) m / T + 0.02 wind          share of the thrust used by the step
    settling_time [s] = 4 / (ζi ωn)          (ζi < 1)
                      = 4 / (ωn (ζi - sqrt(ζi² - 1)))    (ζi >= 1, overdamped: slower)
                      × (1 + 6 max(0, motor_sat - 0.6)²)  saturation slows the response
                      + 0.05 wind / max(Ki, 0.05)        the wind's steady error, removed by Ki
    energy [Wh]     = m (5 + 0.8 Kp + 0.3 Kd ωn)(1 + 0.05 wind) + 2 motor_sat²
    phase_margin [deg] = atan2(2ζ, sqrt(sqrt(1 + 4ζ⁴) - 2ζ²))  (the PD loop's margin)
                       - atan(ωc / (2π f_filter)) - atan(Ki / (Kp ωc / 2))   (filter lag, integral lag)
       with the crossover ωc = ωn sqrt(sqrt(1 + 4ζ⁴) - 2ζ²); no filter = no filter lag.
    With a filter, a wide one lets the D term's noise through: settling_time + 0.01 f Kd, energy + 0.002 m f Kd
    (so the filter is a real local choice: phase margin wants it wide, the settling time narrow).

The three drones of the example (J inertia [kg m²], m mass [kg], T max thrust [N]):

* A light quad  J 0.05, m 1.2, T 30     - wind 0 / 3 / 6 / 10 m/s
* B heavy hexa  J 0.12, m 2-5 (scenario), T 90 - wind 0 / 5 m/s
* C VTOL        J 0.08, m 2.5, T 45     - wind 0 / 4 / 8 m/s, a local filter 15 / 30 / 60 Hz
"""
from typing import Dict, Optional

import numpy as np

DRONES: Dict[str, Dict[str, float]] = {
    "A": {"J": 0.05, "m": 1.2, "T": 30.0},
    "B": {"J": 0.12, "m": 3.5, "T": 90.0},
    "C": {"J": 0.08, "m": 2.5, "T": 45.0},
}


def simulate(drone: str, Kp, Ki, Kd, wind=0.0, mass: Optional[object] = None, filter_hz: Optional[object] = None) -> Dict[str, np.ndarray]:
    """The outputs of one run (or of arrays of runs, broadcast together)."""
    d = DRONES[drone]
    Kp = np.maximum(np.asarray(Kp, dtype=float), 1e-6)
    Ki = np.asarray(Ki, dtype=float)
    Kd = np.asarray(Kd, dtype=float)
    wind = np.asarray(wind, dtype=float)
    m = np.asarray(d["m"] if mass is None else mass, dtype=float)
    J = d["J"] * m / d["m"]                                   # inertia grows with the mass carried
    wn = np.sqrt(Kp / J)
    z = Kd / (2 * np.sqrt(Kp * J))
    zi = np.maximum(0.05, z - 0.35 * Ki / np.sqrt(Kp))
    with np.errstate(all="ignore"):
        under = zi < 1
        os_ = np.where(under, 100 * np.exp(-np.pi * zi / np.sqrt(np.maximum(1 - zi ** 2, 1e-12))), 0.0)
        overshoot = os_ + 0.4 * wind / (1 + Ki)
        sat = (0.5 * Kp + 0.3 * Kd * wn) * m / d["T"] + 0.02 * wind
        ts = np.where(under, 4 / (zi * wn), 4 / (wn * (zi - np.sqrt(np.maximum(zi ** 2 - 1, 0)))))
        ts = ts * (1 + 6 * np.maximum(0, sat - 0.6) ** 2) + 0.05 * wind / np.maximum(Ki, 0.05)
        energy = m * (5 + 0.8 * Kp + 0.3 * Kd * wn) * (1 + 0.05 * wind) + 2 * sat ** 2
        g = np.sqrt(np.sqrt(1 + 4 * z ** 4) - 2 * z ** 2)
        wc = wn * g
        pm = np.degrees(np.arctan2(2 * z, g))
        if filter_hz is not None:
            fh = np.asarray(filter_hz, dtype=float)
            pm = pm - np.degrees(np.arctan(wc / (2 * np.pi * fh)))
            ts = ts + 0.01 * fh * Kd               # a wide filter lets the D term's noise through
            energy = energy + 0.002 * m * fh * Kd
        pm = pm - np.degrees(np.arctan(Ki / np.maximum(Kp * wc / 2, 1e-9)))
    shape = np.broadcast(Kp, Ki, Kd, wind, m, *(() if filter_hz is None else (np.asarray(filter_hz),))).shape
    out = {"overshoot": overshoot, "settling_time": ts, "motor_sat": sat, "energy": energy, "phase_margin": pm}
    return {k: np.broadcast_to(v, shape).astype(float) for k, v in out.items()}
