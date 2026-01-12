# Signal Viewer Pro v4.0 - Fresh Start Plan

## 📋 Executive Summary

A complete rewrite of Signal Viewer with focus on:
- **Simplicity**: Clean, modular architecture
- **Performance**: Fast loading for large CSV files (100MB+)
- **User Experience**: Modern, intuitive interface
- **Maintainability**: Easy to fix and extend

---

## 🎯 Core Features (Must Have)

### 1. Data Loading
- [ ] Load multiple CSV files
- [ ] Auto-detect delimiter (comma, semicolon, tab)
- [ ] Auto-detect header row
- [ ] Handle large files with chunked loading
- [ ] Native file browser dialog
- [ ] Drag & drop file loading
- [ ] Display file list with remove option

### 2. Signal Tree View
- [ ] Hierarchical tree showing CSVs → Signals
- [ ] Search/filter signals by name
- [ ] Checkbox to assign signals to plot
- [ ] Show signal type indicator (numeric, time)
- [ ] Collapsible CSV sections

### 3. Plot Visualization
- [ ] Single interactive Plotly graph
- [ ] Multi-subplot grid (1x1 to 4x4)
- [ ] Zoom, pan, reset controls
- [ ] Auto-scaling Y-axis per subplot
- [ ] Linked X-axis across subplots (optional)
- [ ] Dark/Light theme support

### 4. Signal Assignment
- [ ] Assign signals to specific subplots
- [ ] Visual indicator of assigned signals
- [ ] Remove signals from subplot
- [ ] Color auto-assignment
- [ ] Legend with signal names

### 5. Time Cursor
- [ ] Vertical cursor line on plot
- [ ] Drag to move cursor
- [ ] Display signal values at cursor
- [ ] Slider control for precise positioning
- [ ] Play/Stop animation

---

## 🚀 Advanced Features (Phase 2)

### 6. Multi-Tab Support
- [ ] Create/delete tabs
- [ ] Each tab has independent subplot layout
- [ ] Tab naming

### 7. Signal Customization
- [ ] Change signal color
- [ ] Change line width
- [ ] Display name override
- [ ] Scale factor
- [ ] Time offset

### 8. Derived Signals
- [ ] Derivative calculation
- [ ] Integral calculation
- [ ] Custom math expressions

### 9. X-Y Plot Mode
- [ ] Select X-axis signal (not time)
- [ ] Correlation analysis

### 10. Session Management
- [ ] Save session to JSON file
- [ ] Load session from file
- [ ] Auto-save on exit (optional)

### 11. Export
- [ ] Export plot as PNG/SVG
- [ ] Export data to CSV
- [ ] Export HTML report

### 12. Streaming Mode
- [ ] Monitor CSV for changes
- [ ] Auto-refresh on new data

---

## 🏗️ Architecture Design

### File Structure
```
signal_viewer_v4/
├── app.py              # Main entry point (~100 lines)
├── layout.py           # UI layout definition (~300 lines)
├── callbacks.py        # All Dash callbacks (~500 lines)
├── data_manager.py     # CSV loading & caching (~200 lines)
├── plot_builder.py     # Figure creation (~200 lines)
├── state.py            # Application state management (~100 lines)
├── config.py           # Configuration constants (~50 lines)
├── assets/
│   └── styles.css      # Custom CSS (~200 lines)
└── requirements.txt
```

### State Management (Simplified)
Only 6 core stores:
```python
dcc.Store(id="store-csv-data")      # {csv_id: {path, signals, data}}
dcc.Store(id="store-assignments")    # {subplot_id: [signal_keys]}
dcc.Store(id="store-layout")         # {rows, cols}
dcc.Store(id="store-cursor")         # {x, visible}
dcc.Store(id="store-settings")       # {theme, link_axes, ...}
dcc.Store(id="store-session")        # For save/load
```

### Callback Strategy
Target: ~15 callbacks total (vs 77 in current app)

| Callback | Trigger | Purpose |
|----------|---------|---------|
| load_csv | file dialog | Load CSV files |
| update_tree | csv data | Rebuild signal tree |
| assign_signal | checkbox click | Add/remove from plot |
| update_plot | assignments | Rebuild figure |
| update_cursor | slider/click | Move cursor |
| change_layout | dropdown | Change grid |
| toggle_theme | switch | Dark/light |
| save_session | button | Export state |
| load_session | button | Import state |

---

## 💅 UI Design Principles

### Layout (3-Panel)
```
┌─────────────────────────────────────────────────────┐
│  Header: Title | Theme | Save/Load | Settings       │
├────────────┬────────────────────────────────────────┤
│            │                                        │
│  Sidebar   │         Main Plot Area                 │
│  (300px)   │                                        │
│            │                                        │
│  - Files   │   [Plotly Graph with Subplots]         │
│  - Signals │                                        │
│  - Assign  │                                        │
│            │                                        │
│            ├────────────────────────────────────────┤
│            │  Cursor Bar: [====○====] T: 12.345     │
└────────────┴────────────────────────────────────────┘
```

### Color Palette (Dark Theme)
```css
--bg-primary: #1a1a2e;      /* Main background */
--bg-secondary: #16213e;    /* Cards, panels */
--bg-accent: #0f3460;       /* Highlights */
--text-primary: #e8e8e8;    /* Main text */
--text-secondary: #a0a0a0;  /* Muted text */
--accent-blue: #4ea8de;     /* Primary actions */
--accent-orange: #f4a261;   /* Warnings, secondary */
--success: #4ade80;         /* Success states */
--error: #f87171;           /* Error states */
```

### Typography
- Headers: Inter or Poppins (sans-serif)
- Code/Values: JetBrains Mono (monospace)
- Base size: 14px
- Clean, minimal with ample whitespace

---

## ⚡ Performance Optimizations

### 1. Lazy Loading
- Load CSV headers first, data on demand
- Only load visible portion of large files
- Use Parquet caching for repeat access

### 2. Virtual Scrolling
- Signal tree uses virtual list for 1000+ signals
- Only render visible items

### 3. Smart Caching
```python
# Simple hash-based cache
cache = {}
def get_figure(assignments, layout, theme):
    key = hash((tuple(assignments), layout, theme))
    if key in cache:
        return cache[key]
    fig = build_figure(...)
    cache[key] = fig
    return fig
```

### 4. Debounced Updates
- Cursor movement debounced (50ms)
- Search input debounced (200ms)

### 5. Efficient Data Format
- Use numpy arrays for signal data
- Downsampling for display (LTTB algorithm)

---

## 📱 Responsive Design

- Sidebar collapsible on mobile
- Minimum width: 1024px for full features
- Touch-friendly controls

---

## 🧪 Testing Strategy

- Unit tests for data_manager, plot_builder
- Integration tests for callbacks
- E2E tests with Selenium (optional)

---

## 📅 Implementation Phases

### Phase 1: Core (Week 1)
- [x] Project structure
- [ ] Basic layout
- [ ] CSV loading
- [ ] Signal tree
- [ ] Basic plot
- [ ] Signal assignment

### Phase 2: Interaction (Week 2)
- [ ] Time cursor
- [ ] Subplot grid
- [ ] Theme switching
- [ ] Zoom/pan

### Phase 3: Advanced (Week 3)
- [ ] Multi-tab
- [ ] Signal properties
- [ ] Session save/load
- [ ] Export

### Phase 4: Polish (Week 4)
- [ ] Streaming mode
- [ ] Derived signals
- [ ] X-Y mode
- [ ] Performance tuning

---

## 🔧 Technology Stack

| Component | Technology | Why |
|-----------|------------|-----|
| Framework | Dash 2.x | Mature, stable |
| UI Components | dash-bootstrap-components | Clean styling |
| Plotting | Plotly.js | Interactive, feature-rich |
| Data | Pandas + NumPy | Fast data processing |
| Styling | CSS + Bootstrap 5 | Modern, responsive |
| Build | PyInstaller | Standalone exe |

---

## ✅ Success Criteria

1. **Load Time**: < 2s for 10MB CSV
2. **Plot Update**: < 100ms for assignment changes
3. **Memory**: < 500MB for typical usage
4. **Code Size**: < 2000 lines total (vs 9000+ current)
5. **Callbacks**: < 20 total (vs 77 current)
6. **User Feedback**: Intuitive, no learning curve

---

## 🚦 Ready to Start Checklist

- [x] Features documented
- [x] Architecture planned
- [x] UI design defined
- [x] Performance strategy
- [x] Technology chosen
- [ ] **START CODING**


