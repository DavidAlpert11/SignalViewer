# E2E map

## Round of 2026-11-14 (the redesign; plan §7.0 – one block per lane, add lines only inside yours)

<!-- 1114 lane L1 -->
- A1 ran `test_calm_screen.py`, `test_settings.py` (no change to them) (L1)
- A2 ran `test_plot_polish.py`, `test_first_minute.py` (no change) (L1)
- A3 ran `test_calm_screen.py`, `test_welcome_cards.py`, `test_plot_menus.py` (no change) (L1)
- A4 ran `test_findings_report.py`, `test_live_report.py` (no change) (L1)
- D11 ran `test_welcome_cards.py`, `test_fresh_user.py`, `test_first_minute.py`, `test_calm_screen.py`, `test_features.py -k "welcome or recent or session …"` (no change) (L1)
- D12 ran `test_settings.py`, `test_file_help_menus.py`, `test_template_tabs.py`, `test_templates_recent_badfiles.py`, `test_tour.py`, `test_calm_screen.py`, `test_features.py -k "not (map or globe or 3d)"` (no change) (L1)
- D13 ran `test_features.py`, `test_move_plots_tabs.py`, `test_welcome_cards.py`, `test_calm_screen.py` -k "palette or command or move or welcome or card or calm" (no change) (L1)

<!-- 1114 lane L2 -->
- `tests/e2e/test_sweeps_workspace.py` – C6 (results first: Set up filled; start from nothing: Set up typed, Undo) (L2); C7 the navigator: Set up / table clicks, a demo round opened from it; C11 adds the rest of the walkthroughs
- `tests/e2e/test_sweeps_workspace.py`, `test_study_common.py` – C8: the Run column (round 1 ready / missing; folds and stays folded after a reload); *Suggest next runs* is the column's *Only write the files* (`.sw-run .rc-write`) (L2)
- `tests/e2e/test_study_common.py`, `test_study_loop.py` – C9: *Run them* in the Run column (`.sw-run .rc-send`, disabled without a command), the ranking's head only *Export CSV*; the demo's explanation behind the navigator's About (`[data-nav=about]`) (L2)
- `tests/e2e/test_sweeps_workspace.py` (`test_one_open_menu_and_each_command_once`), `test_study_common.py` – C10: one Open ▾ (four items, no submenu), the study's Undo in `.areabar`, the palette's Sweeps commands once, the status line (L2)
- `backend/tests/test_study_report.py` (new), `tests/e2e/test_sweeps_workspace.py` – C10b: the study's report (HTML: the same counts as the panel, a column per table, RTL in Hebrew, no script) and its one menu item (L2)
- `tests/e2e/test_sweeps_charts.py`, `test_study_demo.py`, `test_sweeps_groups.py` – B7: the Sweeps charts' colours (no assertion changed) (L2)
- `tests/e2e/test_sweeps_workspace.py` – C11a: a demo round opened from the navigator reads as its study table (roles, goal), a limit + Ctrl+Z; a 1.27 study file opens (L2)
- `tests/e2e/test_sweeps_flow.py`, `test_sweeps_data_columns.py` – C7: the table list, merge and export are in the navigator (`.sw-nav`); *Continue with* is a click on a table (`.sw-table-item.used`) (L2)

<!-- 1114 lane L3 -->
- B1 ran `test_plot_menus`, `test_plot_polish`, `test_move_plots`, `test_one_per_plot`, `test_aligned_plots`, `test_owner_notes_1_20`, `test_flat_line_solo` (no change to them) (L3)
- B2 ran `test_plot_polish`, `test_plot_style`, `test_replay`, `test_workflows` (`.chip .val` still the bare number) (no change) (L3)
- B3 ran `test_tab_band`, `test_state_lanes`, `test_less_clutter`, `test_features -k state` (`.tab-band` now inside the top card; no change to the files) (L3)
- B4 ran `test_perf_budget` (0.7–1.0 s, before 0.72–1.02 s), `test_plot_polish`, `test_aligned_plots` (no change) (L3)
- B5 ran `test_timeline`, `test_overview_strip` (no change) (L3)
- F2 (legend): `test_plot_polish.py::test_window_statistics_in_the_legend` new (= the CSV's numbers over the window, follows a zoom) (L3)
- D2: `test_name_tree.py::test_quick_chips_and_the_count_for_a_big_file` new; ran `test_name_tree`, `test_templates_recent_badfiles`, `test_workflows -k small_window` (the head still fits at 1100 px) (L3)
- D1: selectors `.areabar` → `.area-tools` (Recordings tools) / `.stage-bar .more-tabs` in `test_features`, `test_file_help_menus` (Live now in the top row's area tools, gone in another area - asserted), `test_object_templates`, `test_one_per_plot`, `test_templates_recent_badfiles`, `test_workflows`; ran those + `test_plot_polish`, `test_move_plots_tabs`, `test_template_tabs`, `test_calm_screen`, `test_first_minute`, `test_globe3d`, `test_map_smooth`, `test_less_clutter`, `test_tab_band`, `test_unsaved_close` (views that gain space) (L3)
- D8: `test_plot_polish.py::test_pin_a_statistic_to_the_run_at_a_glance` new; ran `test_plot_polish`, `test_plot_style`, `test_timeline`, `test_range_notes`, `test_less_clutter`, `test_features` + `test_workflows` (whole files) (L3)
- D14 (2) pinned searches: `test_name_tree.py::test_pinned_searches_as_chips` new, the quick-chips test's selector `[data-group]`; ran `test_name_tree`, `test_less_clutter` (L3)
- D14 (1) + D7 the strip's numbers and Checks count: `test_plot_polish.py::test_the_run_at_a_glance_shows_its_numbers_and_the_checks` new; `test_less_clutter` counts `.ov-gl-go` as data; ran `test_plot_polish`, `test_less_clutter`, `test_overview_strip`, `test_tab_band`, `test_flat_line_solo` (L3)
- B1 fix (the head does not move when a plot becomes active): `test_live_report::test_one_map` green again (no test change); L3's end-of-lane union: 30 files, 272 green (L3)

<!-- 1114 lane L4 -->
`test_offline_map.py` – M2 (L4): `test_satellite_with_roads_is_one_layer` new.
`test_offline_map.py` – M1 / M3 / M4 (L4): the layer chosen in the picker (`.map-layers-btn`, `.ml-card[data-base=…]`) instead of the plot head's select; new `test_the_background_picker_is_one_place_and_downloads_nothing`, `test_my_maps_an_mbtiles_file_draws_offline`, `test_keep_this_area_offline_refuses_what_the_terms_forbid`.
`test_live_report.py`, `test_globe3d.py`, `test_map_smooth.py` – M6 (L4): the cameras by their `.g3-cam-free/-top/-centre/-chase` classes and new names; Track up = Behind it; the object picker only with a following camera.
`test_map_objects.py`, `test_map_smooth.py`, `test_globe3d.py`, `test_object_relations.py`, `test_live_report.py` – B6 (L4): run, no change (the map chrome moved into `styles/map.css` + docks; selectors kept).

`test_offline_map.py`, `test_map_smooth.py`, `test_round_1112.py` – M5 (L4): run, no change.

`test_height_profile.py` – F5 (L4): new.

`test_map_vectors.py` – F6 (L4): new.

<!-- 1114 lane L5 -->
- `tests/e2e/test_checks_view.py` – D7 + F1 + F3 screens (L5, new)
- `tests/e2e/test_features.py::test_checks_panel_for_any_file_and_a_logs_events` – D7 (L5): renamed; a CSV now enables the panel
- `tests/e2e/test_navigation.py`, `test_event_navigation.py`, `test_release_1_21.py` – D7 (L5): the rail button is *Checks* (label / title)
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
- `tests/e2e/test_replay.py`, `test_findings_report.py`, `test_judge_a_run.py`, `test_live_report.py`, `test_features.py -k report/caption/preview` – D6 the Report panel (selectors unchanged; run them) (L5)
- `tests/e2e/test_what_changed.py`, `test_conditions.py`, `test_occurrences.py`, `test_runs_matrix.py` – D5 the verdict card, the onset times, `table.data` (selectors unchanged; run them) (L5)
- `tests/e2e/test_compare_params.py` – D4 the parameters that differ from the baseline, per file (new); test_compare_diff / test_compare_tolerances / test_judge_a_run / test_compare_similar unchanged (run); test_features: the sync toast says *same run* (L5)
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
- `tests/e2e/test_what_changed.py` – What changed at a glance (run it; the Fleet area and `test_fleet.py` were dropped in FL1)

## Milestone 34 (2026-11-16)

- `test_plot_room.py` – FR1: the plots' share of the window on the ArduPilot demo (>= 35 %, en / he / dark), the one-row head, a lone line's title not repeated; FR2: two rows above the plots, the first curve within 200 px, the flags on the first lane, a demo's line goes / changes after its button, a session's two lanes kept.
- `test_tab_band.py` – FR2: `test_one_mode_row_with_cursors_and_hover` closes the demo's line before the strip's × (the head is folded while the line is up).
- `test_cursor_labels.py` – FR3: the cursor labels' boxes (the layer's `data-flags`) are under the plot area in the investigate demo and with one cursor; a double-click on a signal leaves one chip, a single click as before.
