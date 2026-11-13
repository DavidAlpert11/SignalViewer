# FINAL – round of 2026-11-13

Machine of every number below ("the CI machine" of this round): the cloud sandbox, **4 CPUs**, Linux,
headless Chromium 1243 (software WebGL).

| Step | State | Verification | Note |
|---|---|---|---|
| Branches | done | – | stacked (`SESSION: ALL`): `sv1113/release` = `l8` + FINAL; the owner pushed the round to `main` as `b463313`; the follow-up work is on `sv1113/continue` (pushing from the sandbox is refused – a patch). |
| W0 request | done | verified (pytest) | `w0_pending` removed; `test_every_example_ships_in_every_package` checks the drone and demo files again. |
| quick_check | done | verified | tsc, Vitest 173 (now 182 with declutter / unsaved), backend 1263 passed / 14 skipped, mypy clean (one annotation fixed). Re-run at the end: see the Log. |
| e2e of E2E_MAP | done | verified | all files of the map pass, after the fixes listed below. Two failures are not this round's: `test_less_clutter.py::test_what_does_not_apply_is_hidden` fails on `main` too (the 3D view's "Remove the 3D view" in this sandbox); `test_round_1112.py::test_export_the_flight_three_ways` failed once in a combined run and passed 3/3 alone and on the base (the folder picker loading late – the race `save_as` already works around). `test_globe3d.py` needed the sandbox's browser path (its own fixture ignores `SV_CHROMIUM`). |
| Fixes from the e2e | done | verified | the two-cursor bar's `order` (the legend has `order: 4`); W9's badge text in `test_template_tabs`; W6's wording in `test_less_clutter` and `test_features::test_V09`; the beforeunload test helper (a Playwright call to receive the dialog); L8's removed button in L2's test. |
| W11 10× | see the Log | verified | first 10×: settings 10/10, sweeps_flow 9/10 – the failing test (`test_one_place_for_each_control`, 2 of 5 in a second series) read the axes while an answer was still arriving; it now waits (`_idle`). The second 10× after the fix: in the Log. |
| W13.9 performance | done | verified | the largest example (sim vs flight) from its card to drawn plots: **0.65 s** on 4 CPUs; the budget stays 30 s (generous: CI machines vary). |
| W18 timing | done | verified | `study demo` ≈ 38–40 s, the full-grid optimum (0.5 %) in round 5 at 1 728 runs vs 111 132 – ≈ 64×. |
| W16 recount | done | verified | `tools/count_controls.py` on `main` vs the result: welcome 44 → 42, plotted 118 → 116, Settings 59 → 58, Sweeps 14 → 12. |
| Owner's notes after the round | done | verified (pytest + e2e) | the loop for any study, the demo explained / copied, What changed at a glance, the Fleet, the story's camera – see TASKS.md. |
| W2 pictures, gallery, dist, run.py | see the Log | | |
| Not verified (no means here) | – | – | the Portable (`SignalViewer.exe study …`), the pywebview close prompt, a real farm launcher, W13.3 (not shipped). |
