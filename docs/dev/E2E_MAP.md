# E2E map – round of 2026-11-13

Which e2e files each task wrote or whose selectors it changed, so FINAL runs exactly those (never the whole
suite during a lane). One line per file: `<file> – <task> (<lane>)[ – selector change by Lx]`. Add lines only,
inside your lane's block.

<!-- lane W0 -->
- `tests/e2e/test_sweeps_flow.py` – W11: sleeps replaced by `window.__svSweeps.idle()` / `.saved()` (run 10×)
- `tests/e2e/test_settings.py` – W11: `test_line_defaults_and_apply_to_all` waits on the legend, the file, the toast (run 10×)

<!-- lane L1 -->
- `tests/e2e/test_welcome_cards.py` – W1 (L1)
- `tests/e2e/test_fresh_user.py`, `test_compare_diff.py`, `test_compare_tolerances.py` – W1 changed the cards (titles kept as text; run unchanged) (L1)

<!-- lane L2 -->

<!-- lane L3 -->

<!-- lane L4 -->

<!-- lane L5 -->

<!-- lane L6 -->
- `tests/e2e/test_unsaved_close.py` – W10 (browser prompt, window dialog, setting), W8 (palette) (L6)
- `tests/e2e/test_settings.py` – W10 adds a Settings row; existing tests unchanged (run it) (L6)
- `tests/e2e/test_workflows.py` – W8 palette rendering changed; its palette lines unchanged (run it) (L6)

<!-- lane L7 -->

<!-- lane L8 -->

<!-- lane FINAL -->
