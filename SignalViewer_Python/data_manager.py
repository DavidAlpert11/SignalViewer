"""
DataManager - Handles CSV loading, data management, and streaming
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import time


class DataManager:
    """Manages CSV data loading, signal management, and streaming"""
    
    def __init__(self, app):
        self.app = app
        self.signal_names = []
        self.data_tables = []  # List of DataFrames, one per CSV
        self.signal_scaling = {}  # Dict: signal_name -> scale_factor
        self.state_signals = {}  # Dict: signal_name -> is_state (bool)
        self.is_running = False
        self.data_count = 0
        self.update_counter = 0
        self.last_update_time = datetime.now()
        
        # Multi-CSV streaming properties
        self.csv_file_paths = []
        self.last_file_mod_times = []
        self.last_read_rows = []
        self.streaming_timers = []
        self.timeout_duration = 1.0
        self.update_rate = 0.1
        self.latest_data_rates = []
        self.streaming_enabled = False
        
        # Performance optimization
        self.signal_cache = {}
        self.cache_valid = False
    
    def load_data_once(self):
        """Load all CSV data once without streaming"""
        self.stop_streaming_all()
        
        num_csvs = len(self.csv_file_paths)
        if num_csvs == 0:
            return
        
        # Check total file sizes
        total_size_mb = 0
        for file_path in self.csv_file_paths:
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                total_size_mb += file_size
        
        # Warn for large files (simplified - just log)
        if total_size_mb > 500:
            print(f'Warning: Total file size is {total_size_mb:.1f} MB. Loading may take time.')
            # In a real implementation, this would show a dialog
            # For now, we'll just continue
        
        # Load all CSVs sequentially
        success_count = 0
        failed_count = 0
        
        for i, file_path in enumerate(self.csv_file_paths):
            try:
                filename = os.path.basename(file_path)
                print(f'📁 Loading CSV {i+1}/{num_csvs}: {filename}...')
                
                self.read_initial_data(i)
                
                if self.data_tables[i] is not None and not self.data_tables[i].empty:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                print(f'Error loading CSV {i+1}: {str(e)}')
                failed_count += 1
                self.data_tables[i] = None
        
        self.is_running = False
        total_rows = sum(len(df) for df in self.data_tables if df is not None and not df.empty)
        
        # Status messages - handled by Dash callbacks
        if failed_count == 0:
            print(f'✅ Loaded {success_count} CSV(s): {total_rows} rows, {len(self.signal_names)} signals')
        else:
            print(f'⚠️ Loaded {success_count}/{num_csvs} CSV(s): {total_rows} rows, {len(self.signal_names)} signals ({failed_count} failed)')
    
    def read_initial_data(self, idx: int):
        """Read initial data from CSV file"""
        file_path = self.csv_file_paths[idx]
        
        if not os.path.isfile(file_path):
            self.data_tables[idx] = None
            return
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            self.data_tables[idx] = None
            return
        
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > 100:
            print(f'⚠️ Loading large file ({file_size_mb:.1f} MB): {os.path.basename(file_path)}...')
        
        try:
            # For very large files, use chunked reading
            if file_size_mb > 200:
                df = self.read_large_csv_chunked(file_path)
            else:
                # Direct read for smaller files
                df = pd.read_csv(file_path)
            
            if df.empty:
                self.data_tables[idx] = None
                return
            
            # Validate CSV format
            if not self.validate_csv_format(df, file_path):
                self.data_tables[idx] = None
                filename = os.path.basename(file_path)
                print(f'❌ CSV format error: {filename} - header/data column mismatch')
                return
            
            # Set first column as Time
            if len(df.columns) > 0:
                df.rename(columns={df.columns[0]: 'Time'}, inplace=True)
            
            # Verify Time column exists
            if 'Time' not in df.columns:
                self.data_tables[idx] = None
                return
            
            self.data_tables[idx] = df
            self.last_read_rows[idx] = len(df)
            
            # Invalidate cache
            self.cache_valid = False
            self.signal_cache = {}
            
            # Update signal names
            self.update_signal_names()
            self.initialize_signal_maps()
            
            # Update UI - signal tree will update automatically via callback
            # No need to call build_signal_tree() or update_status() - handled by Dash callbacks
            self.last_update_time = datetime.now()
            
        except Exception as e:
            print(f'Error reading CSV {idx+1}: {str(e)}')
            import traceback
            traceback.print_exc()
            self.data_tables[idx] = None
    
    def read_large_csv_chunked(self, file_path: str) -> pd.DataFrame:
        """Read large CSV files in chunks"""
        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            # Adaptive chunk size
            if file_size_mb > 1000:
                chunk_size = 500000
            else:
                chunk_size = 200000
            
            chunks = []
            row_offset = 0
            
            # Read first chunk to get structure
            try:
                first_chunk = pd.read_csv(file_path, nrows=min(chunk_size, 10000))
                if first_chunk.empty:
                    return pd.DataFrame()
                
                first_chunk.rename(columns={first_chunk.columns[0]: 'Time'}, inplace=True)
                chunks.append(first_chunk)
                row_offset = len(first_chunk)
                
            except Exception as e:
                # Fallback to full read
                return pd.read_csv(file_path)
            
            # Continue reading chunks
            chunk_count = 1
            while True:
                try:
                    chunk = pd.read_csv(
                        file_path,
                        skiprows=row_offset + 1,  # +1 to skip header
                        nrows=chunk_size,
                        names=first_chunk.columns
                    )
                    
                    if chunk.empty:
                        break
                    
                    chunk.rename(columns={chunk.columns[0]: 'Time'}, inplace=True)
                    chunks.append(chunk)
                    row_offset += len(chunk)
                    chunk_count += 1
                    
                    # Update progress
                    if chunk_count % 10 == 0:
                        print(f'📊 Loading... {row_offset} rows loaded')
                    
                    if len(chunk) < chunk_size:
                        break
                        
                except Exception:
                    break
            
            # Concatenate all chunks
            if len(chunks) == 1:
                return chunks[0]
            else:
                return pd.concat(chunks, ignore_index=True)
                
        except Exception:
            # Final fallback
            return pd.read_csv(file_path)
    
    def validate_csv_format(self, df: pd.DataFrame, file_path: str) -> bool:
        """Validate CSV format"""
        try:
            if df.empty:
                return False
            
            # Read first line of file to check header
            with open(file_path, 'r') as f:
                header_line = f.readline().strip()
                data_line = f.readline().strip()
            
            # Count columns
            header_cols = len(header_line.split(','))
            data_cols = len(data_line.split(','))
            table_cols = len(df.columns)
            
            # Validate format
            return header_cols == data_cols == table_cols
            
        except Exception:
            return False
    
    def update_signal_names(self):
        """Update signal names from all data tables"""
        all_signals = set()
        for df in self.data_tables:
            if df is not None and not df.empty:
                signals = set(df.columns) - {'Time'}
                all_signals.update(signals)
        self.signal_names = sorted(list(all_signals))
    
    def initialize_signal_maps(self):
        """Initialize signal scaling and state maps"""
        for signal_name in self.signal_names:
            if signal_name not in self.signal_scaling:
                self.signal_scaling[signal_name] = 1.0
            if signal_name not in self.state_signals:
                self.state_signals[signal_name] = False
    
    def get_signal_data(self, csv_idx: int, signal_name: str) -> Tuple[np.ndarray, np.ndarray]:
        """Get signal data (time and values)"""
        try:
            if csv_idx < 0 or csv_idx >= len(self.data_tables):
                return np.array([]), np.array([])
            
            df = self.data_tables[csv_idx]
            if df is None or df.empty:
                return np.array([]), np.array([])
            
            if signal_name not in df.columns:
                return np.array([]), np.array([])
            
            time_data = df['Time'].values
            signal_data = df[signal_name].values
            
            # Apply scaling
            if signal_name in self.signal_scaling:
                signal_data = signal_data * self.signal_scaling[signal_name]
            
            # Remove NaN values
            valid_mask = ~(np.isnan(time_data) | np.isnan(signal_data))
            if not np.any(valid_mask):
                return np.array([]), np.array([])
            
            time_data = time_data[valid_mask]
            signal_data = signal_data[valid_mask]
            
            return time_data, signal_data
        except Exception as e:
            print(f"Error getting signal data for {signal_name} from CSV {csv_idx}: {e}")
            return np.array([]), np.array([])
    
    def clear_data(self):
        """Clear all data"""
        self.stop_streaming_all()
        self.data_tables = []
        self.signal_names = []
        self.csv_file_paths = []
        self.last_file_mod_times = []
        self.last_read_rows = []
        self.latest_data_rates = []
        self.signal_scaling = {}
        self.state_signals = {}
        self.is_running = False
        self.data_count = 0
        self.update_counter = 0
        self.last_update_time = datetime.now()
        self.signal_cache = {}
        self.cache_valid = False
    
    def stop_streaming_all(self):
        """Stop all streaming"""
        self.is_running = False
        for timer in self.streaming_timers:
            if timer:
                timer.cancel()
        self.streaming_timers = []
        print('⏹️ Stopped')

