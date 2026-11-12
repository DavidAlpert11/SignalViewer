# E2E map – round of 2026-11-13

Which e2e files each task wrote or whose selectors it changed, so FINAL runs exactly those (never the whole
suite during a lane). One line per file: `<file> – <task> (<lane>)[ – selector change by Lx]`. Add lines only,
inside your lane's block.

<!-- lane W0 -->
- `tests/e2e/test_sweeps_flow.py` – W11: sleeps replaced by `window.__svSweeps.idle()` / `.saved()` (run 10×)
- `tests/e2e/test_settings.py` – W11: `test_line_defaults_and_apply_to_all` waits on the legend, the file, the toast (run 10×)

<!-- lane L1 -->

<!-- lane L2 -->

<!-- lane L3 -->

<!-- lane L4 -->

<!-- lane L5 -->

<!-- lane L6 -->

<!-- lane L7 -->

<!-- lane L8 -->

<!-- lane FINAL -->
