# Changelog

All notable changes to Signal Viewer Pro are documented in this file.

## [5.0.0] - 2026-01-16

### Fixed
- **Ghost plots on startup**: App now starts with clean state, no cached signals or traces
- **Data loss during switching**: Tab and subplot switching now fully preserves all assignments
- **Cursor jump functionality**: Jump-to-time now finds nearest actual sample (not interpolated)
- **Cursor values panel sync**: Panel correctly shows all subplots for current tab
- **Auto-assignment removed**: CSV import no longer auto-assigns first signal
- **Import freshness**: New imports don't reload previously loaded CSVs
- **Tab numbering**: Tabs now show sequential numbers (Tab 1, Tab 2, ...)
- **Signal property apply**: Applying properties no longer removes signals from assignments
- **X-axis labels**: Time mode shows "Time", X-Y mode shows X signal name

### Added
- **Advanced multi-CSV compare**:
  - Compare 2+ CSVs simultaneously
  - Mean or specific run as baseline
  - Similarity metrics (RMS diff, correlation, percent deviation)
  - Generate delta signals for all common signals
- **Report scope selection**: Export current tab only or all tabs
- **Multi-line text inputs**: All report text fields support Enter/newlines
- **Per-subplot description**: Each subplot can have title, caption, and description
- **Complete session persistence**:
  - Derived signals saved and restored
  - Signal properties (colors, widths, scales) persist
  - All subplot metadata preserved
- **X-Y mode cursor**: Cursor shows X and Y signal values at cursor time

### Changed
- Session file version updated to 5.0 for new persistence features
- Compare panel redesigned for multi-run workflow
- Tab bar simplified to "Tab 1 × Tab 2 × +" format

### Removed
- Unused stores: `store-derived`, `store-signal-settings`, `store-compare-results`
- Legacy single-run compare interface replaced with multi-run

## [4.0.0] - 2026-01-10

### Added
- Signal properties modal (rename, color, line width, scale, offset)
- State signal visualization (vertical lines at transitions)
- Per-tab view state management
- Report builder with DOCX and HTML export
- RTL/Hebrew support in reports
- Smart incremental refresh
- Derived signals (operations panel)

### Fixed
- Subplot configuration preservation across layout changes
- Cursor slider range computation

## [3.0.0] - 2025-12-15

### Added
- Multi-file CSV import
- Tab system for multiple views
- Compare runs functionality
- Session save/load

### Changed
- Migrated to Dash 2.x
- New dark theme (Cyborg)

## [2.0.0] - 2025-10-01

### Added
- X-Y plotting mode
- Cursor inspector panel
- Signal tree with collapsible runs

### Fixed
- Memory optimization for large files

## [1.0.0] - 2025-08-01

### Initial Release
- Basic CSV signal visualization
- Single subplot display
- Time-series plotting

