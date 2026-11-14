# E2E map

## Round of 2026-11-14 (the redesign; plan §7.0 – one block per lane, add lines only inside yours)

<!-- 1114 lane L1 -->
- A1 ran `test_calm_screen.py`, `test_settings.py` (no change to them) (L1)
- A2 ran `test_plot_polish.py`, `test_first_minute.py` (no change) (L1)
- A3 ran `test_calm_screen.py`, `test_welcome_cards.py`, `test_plot_menus.py` (no change) (L1)
- A4 ran `test_findings_report.py`, `test_live_report.py` (no change) (L1)

<!-- 1114 lane L2 -->

<!-- 1114 lane L3 -->
- B1 ran `test_plot_menus`, `test_plot_polish`, `test_move_plots`, `test_one_per_plot`, `test_aligned_plots`, `test_owner_notes_1_20`, `test_flat_line_solo` (no change to them) (L3)
- B2 ran `test_plot_polish`, `test_plot_style`, `test_replay`, `test_workflows` (`.chip .val` still the bare number) (no change) (L3)
- B3 ran `test_tab_band`, `test_state_lanes`, `test_less_clutter`, `test_features -k state` (`.tab-band` now inside the top card; no change to the files) (L3)
- B4 ran `test_perf_budget` (0.7–1.0 s, before 0.72–1.02 s), `test_plot_polish`, `test_aligned_plots` (no change) (L3)

<!-- 1114 lane L4 -->
`test_offline_map.py` – M2 (L4): `test_satellite_with_roads_is_one_layer` new.

<!-- 1114 lane L5 -->
- F2 (backend only): backend `tests/test_window_stats.py`; the legend's e2e is L3's (`test_plot_polish`, B2).
- F1 (backend only, no screen yet): backend `tests/test_file_structure.py`; the e2e comes with the panel (D7).
- F3 (backend only, no screen yet): backend `tests/test_run_parameters.py`; no e2e file (the screens come with D4 / D7).

<!-- 1114 lane Final -->

## Round of 2026-11-13

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
