"""
Signal Viewer Pro - Canonical Naming
=====================================
Single source of truth for all display names.

Format rules:
- Signal label: "signal_name — csv_display_name"
- Derived: "signal_name — Derived"
- CSV with duplicate filename: "parent/filename.csv"
"""

import os
from typing import List, Optional


def get_csv_display_name(filepath: str, all_paths: List[str]) -> str:
    """
    Get display name for a CSV file.
    
    CANONICAL RULES (task_add.md fix):
    - If filename is unique: "filename.csv"
    - If filename is duplicate: "parent_folder/filename.csv"
    - NEVER show internal paths like "Downloads/signals/"
    
    Args:
        filepath: Full path to CSV file
        all_paths: List of all loaded CSV paths
        
    Returns:
        Display name string (just filename or parent/filename)
    """
    basename = os.path.basename(filepath)
    basenames = [os.path.basename(p) for p in all_paths]
    
    # Only add parent folder if the FILENAME (not full path) is duplicated
    if basenames.count(basename) > 1:
        # Get immediate parent folder name only (not full path)
        parent = os.path.basename(os.path.dirname(filepath))
        if parent and parent not in [".", ""]:
            return f"{parent}/{basename}"
    
    # Default: just the filename
    return basename


def get_csv_short_name(filepath: str, all_paths: List[str]) -> str:
    """Get CSV display name without extension"""
    display = get_csv_display_name(filepath, all_paths)
    return os.path.splitext(display)[0]


def get_signal_label(
    run_idx: int,
    signal_name: str,
    run_paths: List[str],
    display_name: Optional[str] = None,
) -> str:
    """
    Get canonical display label for a signal.
    
    Format: "signal_name — csv_display_name"
    Derived: "signal_name — Derived"
    
    Args:
        run_idx: Index of run (-1 for derived)
        signal_name: Signal name
        run_paths: List of all CSV paths
        display_name: Optional custom display name
        
    Returns:
        Formatted label string
    """
    name = display_name or signal_name
    
    if run_idx == -1:
        return f"{name} — Derived"
    
    if 0 <= run_idx < len(run_paths):
        csv_name = get_csv_short_name(run_paths[run_idx], run_paths)
        return f"{name} — {csv_name}"
    
    return f"{name} — Run{run_idx + 1}"


def get_derived_name(operation: str, *source_names: str) -> str:
    """
    Generate name for a derived signal.
    
    Unary: "derivative(signal)"
    Binary: "A + B"
    Multi: "norm(s1, s2, s3)"
    
    Note: Uses ASCII operators only (+, -, *, /) to avoid issues with
    Dash pattern matching callbacks that can have problems with Unicode.
    """
    if len(source_names) == 1:
        return f"{operation}({source_names[0]})"
    elif len(source_names) == 2 and operation in ['+', '-', '*', '/']:
        return f"{source_names[0]} {operation} {source_names[1]}"
    else:
        signals_str = ", ".join(source_names)
        return f"{operation}({signals_str})"

