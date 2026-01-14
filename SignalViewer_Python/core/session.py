"""
Signal Viewer Pro - Session Management
=======================================
Save/load session state to JSON files.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import asdict

from core.models import ViewState, SubplotConfig, DerivedSignal, Tab


SESSION_VERSION = "4.0"


def save_session(
    filepath: str,
    run_paths: List[str],
    view_state: ViewState,
    derived_signals: Dict[str, DerivedSignal],
    signal_settings: Dict[str, Dict],
) -> bool:
    """
    Save session to JSON file.
    
    Args:
        filepath: Output file path
        run_paths: List of CSV file paths
        view_state: Current view state
        derived_signals: Dict of derived signals
        signal_settings: Per-signal display settings
        
    Returns:
        True if successful
    """
    try:
        session = {
            "version": SESSION_VERSION,
            "timestamp": datetime.now().isoformat(),
            "run_paths": run_paths,
            "view_state": {
                "layout_rows": view_state.layout_rows,
                "layout_cols": view_state.layout_cols,
                "active_subplot": view_state.active_subplot,
                "theme": view_state.theme,
                "cursor_time": view_state.cursor_time,
                "cursor_enabled": view_state.cursor_enabled,
                "cursor_show_all": view_state.cursor_show_all,
                "subplots": [
                    {
                        "index": sp.index,
                        "mode": sp.mode,
                        "assigned_signals": sp.assigned_signals,
                        "x_signal": sp.x_signal,
                        "y_signals": sp.y_signals,
                        "xy_alignment": sp.xy_alignment,
                        "title": sp.title,
                        "caption": sp.caption,
                        "description": sp.description,
                        "include_in_report": sp.include_in_report,
                    }
                    for sp in view_state.subplots
                ],
            },
            "derived_signals": {
                name: {
                    "name": ds.name,
                    "operation": ds.operation,
                    "source_signals": ds.source_signals,
                    "display_name": ds.display_name,
                    "color": ds.color,
                    "line_width": ds.line_width,
                }
                for name, ds in derived_signals.items()
            },
            "signal_settings": signal_settings,
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session, f, indent=2)
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to save session: {e}")
        return False


def load_session(filepath: str) -> Optional[Dict]:
    """
    Load session from JSON file.
    
    Args:
        filepath: Session file path
        
    Returns:
        Session dict or None if failed
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            session = json.load(f)
        
        # Version check
        version = session.get("version", "1.0")
        if version < "3.0":
            print(f"[WARN] Old session format (v{version}), some settings may not load")
        
        return session
        
    except Exception as e:
        print(f"[ERROR] Failed to load session: {e}")
        return None


def parse_view_state(session: Dict) -> ViewState:
    """Parse ViewState from session dict"""
    vs_data = session.get("view_state", {})
    
    subplots = []
    for sp_data in vs_data.get("subplots", []):
        subplots.append(SubplotConfig(
            index=sp_data.get("index", 0),
            mode=sp_data.get("mode", "time"),
            assigned_signals=sp_data.get("assigned_signals", []),
            x_signal=sp_data.get("x_signal"),
            y_signals=sp_data.get("y_signals", []),
            xy_alignment=sp_data.get("xy_alignment", "linear"),
            title=sp_data.get("title", ""),
            caption=sp_data.get("caption", ""),
            description=sp_data.get("description", ""),
            include_in_report=sp_data.get("include_in_report", True),
        ))
    
    return ViewState(
        layout_rows=vs_data.get("layout_rows", 1),
        layout_cols=vs_data.get("layout_cols", 1),
        subplots=subplots,
        active_subplot=vs_data.get("active_subplot", 0),
        theme=vs_data.get("theme", "dark"),
        cursor_time=vs_data.get("cursor_time"),
        cursor_enabled=vs_data.get("cursor_enabled", False),
        cursor_show_all=vs_data.get("cursor_show_all", True),
    )

