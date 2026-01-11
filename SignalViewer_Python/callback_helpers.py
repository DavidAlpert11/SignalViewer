"""
Signal Viewer Pro - Optimized Callback Helpers
==============================================
Drop-in replacement functions for performance-critical callbacks.
"""

from dash import html, no_update, callback_context
import dash_bootstrap_components as dbc
from helpers import get_csv_display_name, make_signal_key, parse_signal_key
import time


class PerformanceCache:
    """Shared cache for performance optimizations"""
    
    def __init__(self):
        self.signal_tree_cache = {}
        self.highlighted_cache = {}
        self.last_update_time = {}
        self.figure_cache = {}  # Cache for figure hashes
        self.debounce_ms = 100  # Reduced for faster response
        self.figure_debounce_ms = 50  # Even faster for figure updates
        
    def should_debounce(self, callback_id, debounce_ms=None):
        """Check if callback should be debounced
        
        Args:
            callback_id: Unique identifier for this callback
            debounce_ms: Custom debounce time, or None for default
        
        Returns:
            True if should skip this callback, False if should proceed
        """
        current_time = time.time() * 1000
        last_time = self.last_update_time.get(callback_id, 0)
        threshold = debounce_ms if debounce_ms is not None else self.debounce_ms
        
        if current_time - last_time < threshold:
            return True
        
        self.last_update_time[callback_id] = current_time
        return False
    
    def get_figure_cache(self, cache_key):
        """Get cached figure by key"""
        return self.figure_cache.get(cache_key)
    
    def set_figure_cache(self, cache_key, figure):
        """Cache a figure
        
        Limits cache size to prevent memory issues
        """
        # Limit cache to 10 figures
        if len(self.figure_cache) > 10:
            # Remove oldest entry
            oldest = next(iter(self.figure_cache))
            del self.figure_cache[oldest]
        
        self.figure_cache[cache_key] = figure
    
    def clear(self):
        """Clear all caches"""
        self.signal_tree_cache.clear()
        self.highlighted_cache.clear()
        self.last_update_time.clear()
        self.figure_cache.clear()


# Global cache instance
perf_cache = PerformanceCache()


def create_optimized_signal_tree(
    csv_files,
    data_tables,
    assignments,
    current_tab,
    current_subplot,
    search_filters=None,
    max_signals_per_csv=50,
    max_expanded_csvs=2,
):
    """
    Optimized signal tree builder with:
    - Limited signals per CSV (default 50)
    - Only first N CSVs expanded
    - Highlighted signals always shown
    - Search filtering
    """
    
    # Build cache key
    cache_key = (
        tuple(csv_files),
        current_tab,
        current_subplot,
        tuple(search_filters or []),
    )
    
    # Check cache
    if cache_key in perf_cache.signal_tree_cache:
        return perf_cache.signal_tree_cache[cache_key]
    
    # Get highlighted signals
    highlighted = get_highlighted_signals(assignments, current_tab, current_subplot)
    
    tree_items = []
    search_lower = [f.lower() for f in (search_filters or [])]
    
    for csv_idx, csv_path in enumerate(csv_files):
        if csv_idx >= len(data_tables) or data_tables[csv_idx] is None:
            continue
        
        df = data_tables[csv_idx]
        csv_name = get_csv_display_name(csv_path, csv_files)
        all_signals = [c for c in df.columns if c.lower() != 'time']
        
        # Get highlighted signals for this CSV
        csv_highlighted = [
            parse_signal_key(s)[1] 
            for s in highlighted 
            if parse_signal_key(s)[0] == csv_idx
        ]
        
        # Apply search filter
        if search_lower:
            filtered = [
                sig for sig in all_signals 
                if any(term in sig.lower() for term in search_lower)
            ]
        else:
            filtered = all_signals
        
        # Prioritize highlighted signals, then others
        other_signals = [s for s in filtered if s not in csv_highlighted]
        
        # Limit total signals shown
        available_slots = max_signals_per_csv - len(csv_highlighted)
        display_signals = csv_highlighted + other_signals[:available_slots]
        
        # Build signal items
        signal_items = []
        for sig in display_signals:
            sig_key = make_signal_key(csv_idx, sig)
            is_highlighted = sig_key in highlighted
            
            signal_items.append(
                html.Div(
                    [
                        html.Input(
                            type="checkbox",
                            id={"type": "signal-check", "csv_idx": csv_idx, "signal": sig},
                            checked=is_highlighted,
                            style={"marginRight": "5px"},
                        ),
                        html.Label(
                            sig,
                            style={
                                "fontWeight": "bold" if is_highlighted else "normal",
                                "color": "#ffd700" if is_highlighted else "#e8e8e8",
                                "cursor": "pointer",
                            },
                            htmlFor={"type": "signal-check", "csv_idx": csv_idx, "signal": sig},
                        ),
                    ],
                    style={"marginLeft": "20px", "marginBottom": "2px"},
                )
            )
        
        # Add truncation notice
        total_signals = len(all_signals)
        shown_signals = len(display_signals)
        
        if shown_signals < total_signals:
            remaining = total_signals - shown_signals
            signal_items.append(
                html.Div(
                    f"... {remaining} more signals (use search)",
                    style={
                        "color": "#888",
                        "fontSize": "11px",
                        "fontStyle": "italic",
                        "marginLeft": "20px",
                        "marginTop": "5px",
                    },
                )
            )
        
        # CSV header
        is_expanded = csv_idx < max_expanded_csvs
        csv_header = html.Div(
            [
                html.I(
                    className="fas fa-folder-open" if is_expanded else "fas fa-folder",
                    style={"marginRight": "8px", "color": "#4ea8de", "fontSize": "14px"},
                ),
                html.Strong(csv_name, style={"color": "#e8e8e8"}),
                html.Small(
                    f" ({shown_signals}/{total_signals})",
                    style={"color": "#888", "marginLeft": "5px"},
                ),
            ],
            style={
                "cursor": "pointer",
                "padding": "6px 8px",
                "marginTop": "5px" if csv_idx > 0 else "0",
                "backgroundColor": "#16213e" if is_expanded else "transparent",
                "borderRadius": "4px",
                "transition": "background-color 0.2s",
            },
            id={"type": "csv-header", "index": csv_idx},
        )
        
        # Add to tree
        tree_items.append(csv_header)
        tree_items.append(
            dbc.Collapse(
                html.Div(
                    signal_items,
                    style={"marginBottom": "8px"},
                ),
                id={"type": "csv-collapse", "index": csv_idx},
                is_open=is_expanded,
            )
        )
    
    result = html.Div(
        tree_items,
        style={
            "overflowY": "auto",
            "maxHeight": "calc(100vh - 220px)",
            "paddingRight": "5px",
        },
    )
    
    # Cache result
    perf_cache.signal_tree_cache[cache_key] = result
    
    # Limit cache size
    if len(perf_cache.signal_tree_cache) > 20:
        # Remove oldest entry
        oldest_key = next(iter(perf_cache.signal_tree_cache))
        del perf_cache.signal_tree_cache[oldest_key]
    
    return result


def get_highlighted_signals(assignments, current_tab, current_subplot):
    """
    Fast extraction of highlighted signals with caching.
    Returns list of signal keys (csv_idx:signal_name).
    """
    cache_key = (current_tab, current_subplot, id(assignments))
    
    # Check cache
    if cache_key in perf_cache.highlighted_cache:
        return perf_cache.highlighted_cache[cache_key]
    
    highlighted = []
    tab_key = str(current_tab)
    subplot_key = str(current_subplot)
    
    if tab_key not in assignments:
        return highlighted
    
    if subplot_key not in assignments[tab_key]:
        return highlighted
    
    assignment = assignments[tab_key][subplot_key]
    
    # Handle time mode (list)
    if isinstance(assignment, list):
        for sig_info in assignment:
            if 'csv_idx' in sig_info and 'signal' in sig_info:
                sig_key = make_signal_key(sig_info['csv_idx'], sig_info['signal'])
                highlighted.append(sig_key)
    
    # Handle XY mode (dict)
    elif isinstance(assignment, dict):
        for axis in ['x', 'y']:
            if axis in assignment and assignment[axis]:
                sig_info = assignment[axis]
                if 'csv_idx' in sig_info and 'signal' in sig_info:
                    sig_key = make_signal_key(sig_info['csv_idx'], sig_info['signal'])
                    highlighted.append(sig_key)
    
    # Cache result
    perf_cache.highlighted_cache[cache_key] = highlighted
    
    # Limit cache size
    if len(perf_cache.highlighted_cache) > 100:
        oldest_key = next(iter(perf_cache.highlighted_cache))
        del perf_cache.highlighted_cache[oldest_key]
    
    return highlighted


def update_signal_tree_debounced(
    trigger,
    csv_files,
    data_tables,
    assignments,
    current_tab,
    current_subplot,
    search_filters,
):
    """
    Debounced signal tree update - prevents rapid-fire updates.
    
    Use this in your callback instead of directly building the tree.
    """
    callback_id = "signal_tree_update"
    
    # Check if we should debounce
    if perf_cache.should_debounce(callback_id):
        return no_update
    
    # Build optimized tree
    return create_optimized_signal_tree(
        csv_files,
        data_tables,
        assignments,
        current_tab,
        current_subplot,
        search_filters,
    )


def clear_performance_cache():
    """Call this when data changes to invalidate caches"""
    perf_cache.clear()

