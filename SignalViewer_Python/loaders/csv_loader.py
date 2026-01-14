"""
Signal Viewer Pro - Flexible CSV Loader
========================================
Handles various CSV formats: headers, delimiters, time columns.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from core.models import Run, Signal
from core.naming import get_csv_display_name


@dataclass
class CSVImportSettings:
    """Settings for CSV import"""
    has_header: bool = True
    header_row: int = 0  # 0-based row index for header
    skip_rows: int = 0  # Rows to skip at start (before header)
    delimiter: Optional[str] = None  # None = auto-detect
    time_column: str = "Time"  # Name or index
    encoding: str = "utf-8"


def detect_delimiter(filepath: str, num_lines: int = 5) -> str:
    """
    Auto-detect CSV delimiter.
    
    Args:
        filepath: Path to CSV file
        num_lines: Number of lines to sample
        
    Returns:
        Detected delimiter character
    """
    delimiters = [',', ';', '\t', '|', ' ']
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(num_lines)]
        
        # Count occurrences of each delimiter
        scores = {}
        for delim in delimiters:
            counts = [line.count(delim) for line in lines if line.strip()]
            if counts:
                # Consistent count across lines = likely delimiter
                if len(set(counts)) == 1 and counts[0] > 0:
                    scores[delim] = counts[0]
                elif counts:
                    scores[delim] = min(counts) if min(counts) > 0 else 0
        
        if scores:
            return max(scores, key=scores.get)
        return ','
        
    except Exception:
        return ','


def preview_csv(
    filepath: str,
    settings: Optional[CSVImportSettings] = None,
    max_rows: int = 20,
) -> Tuple[List[List[str]], List[str]]:
    """
    Preview CSV file without full loading.
    
    Args:
        filepath: Path to CSV file
        settings: Import settings (optional)
        max_rows: Maximum rows to preview
        
    Returns:
        Tuple of (rows as list of lists, column names)
    """
    settings = settings or CSVImportSettings()
    delimiter = settings.delimiter or detect_delimiter(filepath)
    
    try:
        # Read raw lines
        with open(filepath, 'r', encoding=settings.encoding, errors='ignore') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= settings.skip_rows + max_rows:
                    break
                if i >= settings.skip_rows:
                    lines.append(line.strip().split(delimiter))
        
        if not lines:
            return [], []
        
        # Extract header
        if settings.has_header:
            header_idx = settings.header_row - settings.skip_rows
            if 0 <= header_idx < len(lines):
                columns = lines[header_idx]
                data = lines[header_idx + 1:]
            else:
                columns = [f"Col{i}" for i in range(len(lines[0]))]
                data = lines
        else:
            columns = [f"Col{i}" for i in range(len(lines[0]))]
            data = lines
        
        return data, columns
        
    except Exception as e:
        print(f"[ERROR] Preview failed: {e}")
        return [], []


def load_csv(
    filepath: str,
    all_paths: List[str],
    settings: Optional[CSVImportSettings] = None,
) -> Optional[Run]:
    """
    Load CSV file into a Run object.
    
    Args:
        filepath: Path to CSV file
        all_paths: All loaded paths (for display name)
        settings: Import settings
        
    Returns:
        Run object or None if failed
    """
    if not os.path.isfile(filepath):
        print(f"[ERROR] File not found: {filepath}")
        return None
    
    settings = settings or CSVImportSettings()
    
    try:
        # Detect delimiter if not specified
        delimiter = settings.delimiter or detect_delimiter(filepath)
        
        # Calculate skiprows
        skiprows = list(range(settings.skip_rows))
        if settings.has_header and settings.header_row > 0:
            # Skip rows before header
            skiprows.extend(range(settings.skip_rows, settings.skip_rows + settings.header_row))
        
        # Read CSV
        header = 0 if settings.has_header else None
        df = pd.read_csv(
            filepath,
            delimiter=delimiter,
            header=header,
            skiprows=skiprows if skiprows else None,
            encoding=settings.encoding,
            low_memory=False,
            on_bad_lines='skip',
        )
        
        if df.empty:
            print(f"[ERROR] Empty CSV: {filepath}")
            return None
        
        # Generate column names if no header
        if not settings.has_header:
            df.columns = [f"Col{i}" for i in range(len(df.columns))]
        
        # Find/rename time column
        time_col = settings.time_column
        if time_col not in df.columns:
            # Try to find time-like column
            time_candidates = [c for c in df.columns if c.lower() in ['time', 't', 'timestamp', 'datetime']]
            if time_candidates:
                time_col = time_candidates[0]
            else:
                # Use first column
                time_col = df.columns[0]
        
        # Rename to "Time" if needed
        if time_col != "Time":
            df.rename(columns={time_col: "Time"}, inplace=True)
        
        # Ensure Time is numeric
        df["Time"] = pd.to_numeric(df["Time"], errors='coerce')
        df.dropna(subset=["Time"], inplace=True)
        
        if df.empty:
            print(f"[ERROR] No valid time data: {filepath}")
            return None
        
        # Create Run object
        csv_display_name = get_csv_display_name(filepath, all_paths)
        time_array = df["Time"].values.astype(np.float64)
        
        run = Run(
            file_path=filepath,
            csv_display_name=csv_display_name,
            time=time_array,
        )
        
        # Add signals
        for col in df.columns:
            if col == "Time":
                continue
            
            try:
                data = pd.to_numeric(df[col], errors='coerce').values.astype(np.float64)
                run.signals[col] = Signal(name=col, data=data)
            except Exception:
                continue
        
        # Compute metadata
        run.compute_metadata()
        
        print(f"[OK] Loaded {csv_display_name}: {run.sample_count:,} samples, {len(run.signals)} signals")
        return run
        
    except Exception as e:
        print(f"[ERROR] Failed to load {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return None


def reload_csv(run: Run, all_paths: List[str]) -> Optional[Run]:
    """
    Reload a run from disk.
    
    Args:
        run: Existing run to reload
        all_paths: All loaded paths
        
    Returns:
        Updated Run or None if failed
    """
    settings = CSVImportSettings()  # Use defaults for reload
    return load_csv(run.file_path, all_paths, settings)

