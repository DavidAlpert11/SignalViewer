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
- `tests/e2e/test_first_minute.py` – W3, W4, W5, W6, W13.5 (L2)
- `tests/e2e/test_flat_line_solo.py` – W3: the two Quick-look tests now check the empty plot (the start card no longer offers it) (L2)
- `tests/e2e/test_templates_recent_badfiles.py` – W3 selector change by L2
- `tests/e2e/test_workflows.py` – W3 selector change by L2 (`.tpl-strip .chipbtn` → `.tpl-chips .chipbtn`)
- `tests/e2e/test_object_templates.py` – W3 selector change by L2
- `tests/e2e/test_template_tabs.py` – W3 selector change by L2
- `tests/e2e/test_one_per_plot.py` – W3: the strip shows only once something is plotted (run it) (L2)
- `tests/e2e/test_settings.py` – W5 adds a Settings row (run it) (L2)

<!-- lane L3 -->

<!-- lane L4 -->

<!-- lane L5 -->
- `tests/e2e/test_study_common.py` – W14 card → panel → best value → runs; edit + undo; W15 Suggest next runs (L5)
- `tests/e2e/test_study_demo.py` – W18 card → Next round twice → two points, run counter (L5)

<!-- lane L6 -->
- `tests/e2e/test_unsaved_close.py` – W10 (browser prompt, window dialog, setting), W8 (palette) (L6)
- `tests/e2e/test_settings.py` – W10 adds a Settings row; existing tests unchanged (run it) (L6)
- `tests/e2e/test_workflows.py` – W8 palette rendering changed; its palette lines unchanged (run it) (L6)

<!-- lane L7 -->
- `tests/e2e/test_plot_polish.py` – W7, W9, W13.2, T49 item 10 (L7)
- `tests/e2e/test_perf_budget.py` – W13.9 (L7; FINAL sets the threshold)
- `tests/e2e/test_tab_band.py`, `test_timeline.py`, `test_plot_style.py`, `test_globe3d.py` – touched areas (stage bar order, plot head, 3D labels): run them (L7)

<!-- lane L8 -->
- `tests/e2e/test_calm_screen.py` – W16, T50, W13.7 (L8)
- `tests/e2e/test_tour.py` – W13.8 (L8)
- `tests/e2e/test_features.py` – W16 selector change by L8 (`test_V06_link_x_and_y`: Link Y from the More menu); also run for the stage bar / status bar changes (W16, L7)
- `tests/e2e/test_sweeps_data_columns.py` – W16 selector change by L8 (Open a saved study from Open ▾)
- `tests/e2e/test_settings.py`, `test_file_help_menus.py`, `test_less_clutter.py` – Settings fold, Help menu entry, moved controls: run them (L8)

<!-- lane FINAL -->
- `tests/e2e/test_study_loop.py` – the loop from the app, the demo explained / copied (owner's notes 2026-11-13)
- `tests/e2e/test_round_1112.py` – `test_story_keeps_a_chosen_camera` (owner's notes 2026-11-13)
- `tests/e2e/test_fleet.py`, `test_what_changed.py` – the Fleet summary / questions, What changed at a glance (run them)
