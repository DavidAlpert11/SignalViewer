"""
Flexible CSV Loader - Drop-in Replacement for DataManager
==========================================================

This module provides intelligent CSV loading that handles:
- CSVs with headers at any row (or no headers)
- Multiple delimiters (auto-detect)
- Skip rows (metadata, comments)
- Various time column names
- Different encodings

USAGE:
------
1. Copy this file to your project
2. In data_manager.py, add: from flexible_csv_loader import FlexibleCSVLoader
3. Replace pd.read_csv() calls with loader.load_csv()
"""

import pandas as pd
import numpy as np
import re
from typing import Tuple, Dict, List, Optional


class FlexibleCSVLoader:
    """
    Intelligent CSV loader with auto-detection and flexible parsing.
    """
    
    def __init__(self):
        self.supported_delimiters = [',', '\t', ';', '|', ' ']
        self.common_time_names = [
            'time', 't', 'timestamp', 'datetime', 'date', 
            'sec', 'seconds', 'ms', 'milliseconds',
            'sample', 'index', 'x'
        ]
    
    def load_csv(self, 
                 filepath: str, 
                 auto_detect: bool = True,
                 delimiter: Optional[str] = None,
                 header_row: Optional[int] = 0,
                 skiprows: int = 0,
                 encoding: str = 'utf-8',
                 preview_mode: bool = False) -> pd.DataFrame:
        """
        Load CSV with intelligent auto-detection.
        
        Args:
            filepath: Path to CSV file
            auto_detect: Auto-detect format (delimiter, headers, etc.)
            delimiter: Manual delimiter override (None = auto-detect)
            header_row: Row index containing headers (None = no headers, 0 = first row)
            skiprows: Number of rows to skip at beginning
            encoding: File encoding
            preview_mode: If True, only load first 100 rows
        
        Returns:
            pandas DataFrame
        """
        # Auto-detection phase
        if auto_detect:
            format_info = self.detect_format(filepath)
            
            if delimiter is None:
                delimiter = format_info['delimiter']
            
            if header_row == 0 and format_info['header_row'] >= 0:
                header_row = format_info['header_row']
            
            if skiprows == 0 and format_info['skip_rows'] > 0:
                skiprows = format_info['skip_rows']
        
        # Set default delimiter if still None
        if delimiter is None:
            delimiter = ','
        
        # Load CSV based on parameters
        try:
            if header_row is None or header_row < 0:
                # No headers - generate column names
                df = pd.read_csv(
                    filepath,
                    delimiter=delimiter,
                    header=None,
                    skiprows=skiprows,
                    encoding=encoding,
                    nrows=100 if preview_mode else None,
                    on_bad_lines='skip',
                )
                
                # Generate column names: Time, Signal_1, Signal_2, ...
                n_cols = len(df.columns)
                df.columns = ['Time'] + [f'Signal_{i}' for i in range(1, n_cols)]
            
            else:
                # Has headers
                df = pd.read_csv(
                    filepath,
                    delimiter=delimiter,
                    skiprows=skiprows,
                    encoding=encoding,
                    nrows=100 if preview_mode else None,
                    on_bad_lines='skip',
                )
            
            # Ensure Time column exists
            df = self._ensure_time_column(df)
            
            # Convert to numeric where possible
            df = self._convert_to_numeric(df)
            
            return df
            
        except Exception as e:
            raise ValueError(f"Failed to load CSV: {str(e)}")
    
    def detect_format(self, filepath: str) -> Dict:
        """
        Auto-detect CSV format by analyzing file contents.
        
        Returns:
            Dict with: delimiter, header_row, skip_rows, time_column_candidates, encoding
        """
        try:
            # Try UTF-8 first
            encoding = 'utf-8'
            with open(filepath, 'r', encoding=encoding, errors='ignore') as f:
                lines = [f.readline() for _ in range(min(50, sum(1 for _ in f) + 1))]
        except:
            # Fall back to latin-1
            encoding = 'latin-1'
            with open(filepath, 'r', encoding=encoding, errors='ignore') as f:
                lines = [f.readline() for _ in range(min(50, sum(1 for _ in f) + 1))]
        
        # Detect delimiter
        delimiter = self._detect_delimiter(lines)
        
        # Detect header row and skip rows
        header_row, skip_rows = self._detect_header_row(lines, delimiter)
        
        # Detect time column candidates
        time_candidates = []
        if header_row >= 0 and header_row < len(lines):
            time_candidates = self._detect_time_column(lines[header_row], delimiter)
        
        return {
            'delimiter': delimiter,
            'header_row': header_row,
            'skip_rows': skip_rows,
            'time_column_candidates': time_candidates,
            'encoding': encoding,
            'has_headers': header_row >= 0,
        }
    
    def get_preview(self, filepath: str, max_lines: int = 20) -> str:
        """
        Get raw text preview of CSV file.
        
        Returns:
            String with first N lines
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [f.readline() for _ in range(max_lines)]
            return ''.join(lines)
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    def _detect_delimiter(self, lines: List[str]) -> str:
        """
        Detect most likely delimiter.
        
        Strategy: Find delimiter with most consistent count across lines.
        """
        delimiter_scores = {}
        
        for delim in self.supported_delimiters:
            counts = [line.count(delim) for line in lines[:10] if line.strip()]
            
            if not counts or max(counts) == 0:
                continue
            
            # Score based on consistency and count
            non_zero = [c for c in counts if c > 0]
            if len(non_zero) < len(counts) * 0.5:  # Less than 50% have delimiter
                continue
            
            avg_count = np.mean(non_zero)
            std_count = np.std(non_zero)
            consistency = 1.0 / (std_count + 1)  # Higher = more consistent
            
            # Prefer delimiters with >= 2 fields and high consistency
            if avg_count >= 1:
                delimiter_scores[delim] = consistency * avg_count
        
        if not delimiter_scores:
            return ','  # Default to comma
        
        return max(delimiter_scores, key=delimiter_scores.get)
    
    def _detect_header_row(self, lines: List[str], delimiter: str) -> Tuple[int, int]:
        """
        Detect which row contains headers.
        
        Returns:
            (header_row, skip_rows) tuple
            header_row: -1 if no headers, else row index
            skip_rows: Number of rows to skip (metadata/comments)
        """
        for idx, line in enumerate(lines[:20]):
            if not line.strip():
                continue
            
            fields = [f.strip().strip('"\'') for f in line.split(delimiter)]
            
            # Skip if too few fields
            if len(fields) < 2:
                continue
            
            # Check if this looks like a header
            non_numeric = 0
            for field in fields:
                # Check if NOT a number
                if not self._is_numeric(field):
                    non_numeric += 1
            
            # If > 60% non-numeric, likely header
            if non_numeric / len(fields) > 0.6:
                return idx, idx  # Found header
        
        # No header found
        return -1, 0
    
    def _detect_time_column(self, header_line: str, delimiter: str) -> List[int]:
        """
        Detect which columns might be time.
        
        Returns:
            List of column indices that might contain time data
        """
        if not header_line:
            return [0]
        
        fields = [f.strip().strip('"\'').lower() for f in header_line.split(delimiter)]
        
        candidates = []
        for idx, field in enumerate(fields):
            # Check if field name contains common time keywords
            for time_name in self.common_time_names:
                if time_name in field:
                    candidates.append(idx)
                    break
        
        return candidates if candidates else [0]
    
    def _ensure_time_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure DataFrame has a 'Time' column.
        
        If no Time column exists, tries to find it or creates one.
        """
        # Check if Time already exists
        if 'Time' in df.columns:
            return df
        
        # Look for common time column names
        for col in df.columns:
            col_lower = str(col).lower()
            if any(name in col_lower for name in self.common_time_names):
                # Rename to 'Time'
                df = df.rename(columns={col: 'Time'})
                return df
        
        # No time column found - use first column or create index
        if len(df.columns) > 0:
            first_col = df.columns[0]
            df = df.rename(columns={first_col: 'Time'})
        else:
            # Create time index
            df['Time'] = np.arange(len(df))
        
        return df
    
    def _convert_to_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert columns to numeric where possible.
        """
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col], errors='ignore')
            except:
                pass
        
        return df
    
    @staticmethod
    def _is_numeric(value: str) -> bool:
        """Check if string represents a number."""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False


# ==============================================================================
# Integration with Existing DataManager
# ==============================================================================

def integrate_flexible_loader(data_manager_instance):
    """
    Add flexible CSV loading to existing DataManager.
    
    Usage:
        from flexible_csv_loader import integrate_flexible_loader
        
        # In DataManager.__init__ or app setup:
        integrate_flexible_loader(self.data_manager)
    """
    loader = FlexibleCSVLoader()
    
    # Store original load function
    data_manager_instance._original_load_csv = getattr(data_manager_instance, 'load_csv', None)
    
    # Replace with flexible loader
    data_manager_instance.flexible_loader = loader
    data_manager_instance.load_csv_flexible = loader.load_csv
    data_manager_instance.detect_csv_format = loader.detect_format
    data_manager_instance.get_csv_preview = loader.get_preview


# ==============================================================================
# Example Usage
# ==============================================================================

if __name__ == '__main__':
    loader = FlexibleCSVLoader()
    
    # Example 1: Auto-detect everything
    df1 = loader.load_csv('data.csv', auto_detect=True)
    print("Loaded with auto-detect:")
    print(df1.head())
    
    # Example 2: Manual parameters
    df2 = loader.load_csv(
        'data.csv',
        auto_detect=False,
        delimiter='\t',
        header_row=5,
        skiprows=3,
    )
    print("\nLoaded with manual params:")
    print(df2.head())
    
    # Example 3: Detect format first, then load
    format_info = loader.detect_format('data.csv')
    print(f"\nDetected format: {format_info}")
    
    # Example 4: Preview file
    preview = loader.get_preview('data.csv', max_lines=10)
    print(f"\nFile preview:\n{preview}")