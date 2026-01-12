"""
Signal Viewer Pro v4.0 - Data Manager
=====================================
Efficient CSV loading and data management.
"""

import pandas as pd
import numpy as np
import os
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from config import CHUNK_SIZE, DOWNSAMPLE_THRESHOLD


class DataManager:
    """Manages CSV file loading and data access."""
    
    def __init__(self):
        self.csv_files: Dict[str, Dict] = {}  # {csv_id: file_info}
        self.data_cache: Dict[str, pd.DataFrame] = {}  # {csv_id: dataframe}
        self._signal_cache: Dict[str, np.ndarray] = {}  # {signal_key: data}
    
    def load_csv(self, filepath: str, csv_id: Optional[str] = None) -> Dict:
        """
        Load a CSV file and return its metadata.
        
        Args:
            filepath: Path to CSV file
            csv_id: Optional custom ID (uses hash if not provided)
            
        Returns:
            Dict with file info {id, path, name, signals, time_column, row_count}
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Generate ID if not provided
        if csv_id is None:
            csv_id = self._generate_id(filepath)
        
        # Detect format and load
        df = self._smart_load_csv(filepath)
        
        if df is None or df.empty:
            raise ValueError(f"Could not load CSV: {filepath}")
        
        # Get numeric columns (potential signals)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Detect time column
        time_col = self._detect_time_column(df)
        
        # Store data
        self.data_cache[csv_id] = df
        
        file_info = {
            "id": csv_id,
            "path": filepath,
            "name": os.path.basename(filepath),
            "signals": numeric_cols,
            "time_column": time_col,
            "row_count": len(df),
            "columns": df.columns.tolist(),
        }
        
        self.csv_files[csv_id] = file_info
        return file_info
    
    def _smart_load_csv(self, filepath: str) -> Optional[pd.DataFrame]:
        """Load CSV with automatic format detection."""
        
        # Try common delimiters
        delimiters = [',', ';', '\t', ' ']
        
        for delim in delimiters:
            try:
                # Read first few lines to check format
                df = pd.read_csv(
                    filepath,
                    delimiter=delim,
                    nrows=5,
                    encoding='utf-8',
                    on_bad_lines='skip'
                )
                
                # Check if we got reasonable columns
                if len(df.columns) > 1 or (len(df.columns) == 1 and delim == ','):
                    # Full load
                    df = pd.read_csv(
                        filepath,
                        delimiter=delim,
                        encoding='utf-8',
                        on_bad_lines='skip',
                        low_memory=False
                    )
                    return df
                    
            except Exception:
                continue
        
        # Fallback: try pandas auto-detection
        try:
            return pd.read_csv(filepath, on_bad_lines='skip')
        except Exception:
            return None
    
    def _detect_time_column(self, df: pd.DataFrame) -> Optional[str]:
        """Detect the time/X-axis column."""
        
        # Common time column names
        time_names = ['time', 't', 'timestamp', 'datetime', 'date', 'x', 'seconds', 'sec', 'ms']
        
        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in time_names:
                return col
        
        # If first column is numeric and monotonically increasing, use it
        first_col = df.columns[0]
        if pd.api.types.is_numeric_dtype(df[first_col]):
            if df[first_col].is_monotonic_increasing:
                return first_col
        
        return df.columns[0]  # Default to first column
    
    def _generate_id(self, filepath: str) -> str:
        """Generate a unique ID for a file."""
        return hashlib.md5(filepath.encode()).hexdigest()[:8]
    
    def get_signal_data(
        self, 
        csv_id: str, 
        signal_name: str,
        time_column: Optional[str] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get time and value arrays for a signal.
        
        Returns:
            Tuple of (time_array, value_array)
        """
        cache_key = f"{csv_id}:{signal_name}"
        
        if csv_id not in self.data_cache:
            raise KeyError(f"CSV not loaded: {csv_id}")
        
        df = self.data_cache[csv_id]
        
        if signal_name not in df.columns:
            raise KeyError(f"Signal not found: {signal_name}")
        
        # Get time column
        if time_column is None:
            time_column = self.csv_files[csv_id].get("time_column", df.columns[0])
        
        t = df[time_column].values.astype(float)
        y = df[signal_name].values.astype(float)
        
        return t, y
    
    def get_downsampled_data(
        self,
        csv_id: str,
        signal_name: str,
        max_points: int = 5000,
        time_column: Optional[str] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get downsampled signal data for display.
        Uses LTTB algorithm for visual fidelity.
        """
        t, y = self.get_signal_data(csv_id, signal_name, time_column)
        
        if len(t) <= max_points:
            return t, y
        
        # Simple nth-point downsampling (fast)
        # TODO: Implement LTTB for better visual quality
        step = len(t) // max_points
        indices = np.arange(0, len(t), step)
        
        return t[indices], y[indices]
    
    def remove_csv(self, csv_id: str) -> bool:
        """Remove a CSV from memory."""
        if csv_id in self.csv_files:
            del self.csv_files[csv_id]
        if csv_id in self.data_cache:
            del self.data_cache[csv_id]
        
        # Clear related signal cache entries
        keys_to_remove = [k for k in self._signal_cache if k.startswith(f"{csv_id}:")]
        for k in keys_to_remove:
            del self._signal_cache[k]
        
        return True
    
    def clear_all(self):
        """Clear all loaded data."""
        self.csv_files.clear()
        self.data_cache.clear()
        self._signal_cache.clear()
    
    def get_csv_list(self) -> List[Dict]:
        """Get list of loaded CSV files."""
        return list(self.csv_files.values())
    
    def get_all_signals(self) -> List[Dict]:
        """Get flat list of all signals from all CSVs."""
        signals = []
        for csv_id, info in self.csv_files.items():
            for sig_name in info.get("signals", []):
                signals.append({
                    "csv_id": csv_id,
                    "csv_name": info["name"],
                    "signal": sig_name,
                    "key": f"{csv_id}:{sig_name}"
                })
        return signals
    
    def get_time_range(self, csv_id: str) -> Tuple[float, float]:
        """Get time range for a CSV."""
        if csv_id not in self.csv_files:
            return 0, 100
        
        time_col = self.csv_files[csv_id].get("time_column")
        if time_col and csv_id in self.data_cache:
            t = self.data_cache[csv_id][time_col].values
            return float(np.nanmin(t)), float(np.nanmax(t))
        
        return 0, 100


# Global instance
data_manager = DataManager()

