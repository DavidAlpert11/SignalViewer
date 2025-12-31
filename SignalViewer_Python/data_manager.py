"""
DataManager - Enhanced CSV loading, data management, and caching
Version 2.0 - Performance optimized
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import time
from collections import OrderedDict

# Import flexible CSV loader
from flexible_csv_loader import FlexibleCSVLoader


class LRUCache:
    """Simple LRU cache with size limit"""

    def __init__(self, max_size=100):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self):
        self.cache.clear()

    def __len__(self):
        return len(self.cache)


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

        # Enhanced caching system
        self.memory_cache = LRUCache(max_size=200)  # LRU cache with size limit
        self.statistics_cache = {}  # Cache for signal statistics
        self.disk_cache_dirs = {}  # Track cache directories per CSV
        self.cache_hits = 0
        self.cache_misses = 0

        # Performance monitoring
        self.load_times = []  # Track loading performance
        self.last_cache_report = time.time()
        
        # Flexible CSV loader instance
        self.flexible_loader = FlexibleCSVLoader()
        self.csv_settings = {}  # Store per-CSV loading settings: {csv_idx: {delimiter, header_row, etc}}

    def invalidate_cache(self, csv_idx=None):
        """Clear cache when data changes"""
        if csv_idx is None:
            self.memory_cache.clear()
            self.statistics_cache.clear()
            print(
                f"📊 Cache cleared - Stats: {self.cache_hits} hits, {self.cache_misses} misses"
            )
            self.cache_hits = 0
            self.cache_misses = 0
        else:
            # Remove all cached data for this CSV
            keys_to_remove = []
            for key in list(self.memory_cache.cache.keys()):
                if isinstance(key, tuple) and key[0] == csv_idx:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.memory_cache.cache[key]

            # Clear statistics for this CSV
            stat_keys = [k for k in self.statistics_cache if k[0] == csv_idx]
            for key in stat_keys:
                del self.statistics_cache[key]

    def load_data_once(self, progress_callback=None):
        """Load all CSV data with progress tracking"""
        self.stop_streaming_all()

        num_csvs = len(self.csv_file_paths)
        if num_csvs == 0:
            return

        # Calculate total file size
        total_size_mb = 0
        file_sizes = []
        for file_path in self.csv_file_paths:
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                file_sizes.append(file_size)
                total_size_mb += file_size
            else:
                file_sizes.append(0)

        # Warn for large files
        if total_size_mb > 500:
            print(f"⚠️ Large dataset: {total_size_mb:.1f} MB total")

        # Load all CSVs with progress tracking
        success_count = 0
        failed_count = 0
        start_time = time.time()

        for i, file_path in enumerate(self.csv_file_paths):
            try:
                filename = os.path.basename(file_path)
                file_size_mb = file_sizes[i]

                if progress_callback:
                    progress_callback(i, num_csvs, filename)

                print(
                    f"📁 [{i+1}/{num_csvs}] Loading {filename} ({file_size_mb:.1f} MB)..."
                )

                load_start = time.time()
                self.read_initial_data(i)
                load_time = time.time() - load_start
                self.load_times.append(load_time)

                if self.data_tables[i] is not None and not self.data_tables[i].empty:
                    success_count += 1
                    rows = len(self.data_tables[i])
                    print(f"   ✅ Loaded {rows:,} rows in {load_time:.2f}s")
                else:
                    failed_count += 1
                    print(f"   ❌ Failed to load")

            except Exception as e:
                print(f"❌ Error loading CSV {i+1}: {str(e)}")
                failed_count += 1
                self.data_tables[i] = None

        self.is_running = False
        total_time = time.time() - start_time
        total_rows = sum(
            len(df) for df in self.data_tables if df is not None and not df.empty
        )

        # Summary
        if failed_count == 0:
            print(f"✅ SUCCESS: Loaded {success_count} CSV(s)")
        else:
            print(
                f"⚠️ PARTIAL: Loaded {success_count}/{num_csvs} CSV(s) ({failed_count} failed)"
            )

        print(
            f"📊 Total: {total_rows:,} rows, {len(self.signal_names)} signals in {total_time:.2f}s"
        )

        self.invalidate_cache()

    def read_initial_data(self, idx: int, csv_settings: Optional[Dict] = None):
        """Read initial data from CSV file using flexible loader
        
        Args:
            idx: CSV index
            csv_settings: Optional dict with settings:
                - delimiter: Column delimiter (None = auto-detect)
                - header_row: Row number for headers (0-based), or None for no header
                - skip_rows: Number of rows to skip at the beginning
                - encoding: File encoding (default: utf-8)
                - auto_detect: Auto-detect format (default: True)
        """
        file_path = self.csv_file_paths[idx]

        if not os.path.isfile(file_path):
            self.data_tables[idx] = None
            return

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            self.data_tables[idx] = None
            return

        file_size_mb = file_size / (1024 * 1024)
        
        # Get or create CSV settings
        if csv_settings is None:
            csv_settings = self.csv_settings.get(idx, {})
        else:
            # Store settings for this CSV
            self.csv_settings[idx] = csv_settings

        try:
            # Use flexible loader with auto-detection by default
            auto_detect = csv_settings.get('auto_detect', True)
            delimiter = csv_settings.get('delimiter', None)
            header_row = csv_settings.get('header_row', 0)
            skip_rows = csv_settings.get('skip_rows', 0)
            encoding = csv_settings.get('encoding', 'utf-8')
            
            # Determine if we should load full file or preview
            preview_mode = file_size_mb > 200
            
            if preview_mode:
                print(f"   🔍 Large file detected ({file_size_mb:.1f} MB), using chunked loading...")
                # For very large files, still use chunked loading
                df = self.read_large_csv_chunked(file_path, delimiter, header_row, skip_rows)
            else:
                # Use flexible loader for normal files
                df = self.flexible_loader.load_csv(
                    file_path,
                    auto_detect=auto_detect,
                    delimiter=delimiter,
                    header_row=header_row,
                    skiprows=skip_rows,
                    encoding=encoding,
                    preview_mode=False
                )

            if df is None or df.empty:
                self.data_tables[idx] = None
                return

            # Validate CSV format
            if not self.validate_csv_format(df, file_path):
                self.data_tables[idx] = None
                filename = os.path.basename(file_path)
                print(f"❌ Invalid CSV format: {filename}")
                return

            # Ensure Time column exists (flexible_loader should handle this, but double-check)
            if "Time" not in df.columns:
                # Try to find a time-like column
                time_candidates = [c for c in df.columns if c.lower() in ['time', 't', 'timestamp', 'datetime']]
                if time_candidates:
                    df.rename(columns={time_candidates[0]: 'Time'}, inplace=True)
                elif len(df.columns) > 0:
                    # Use first column as Time
                    df.rename(columns={df.columns[0]: 'Time'}, inplace=True)
                else:
                    self.data_tables[idx] = None
                    return

            # Store dataframe
            self.data_tables[idx] = df
            self.last_read_rows[idx] = len(df)

            # Setup disk cache directory
            self._setup_disk_cache(idx, file_path)

            # Update signal names
            self.update_signal_names()
            self.initialize_signal_maps()
            self.last_update_time = datetime.now()

        except Exception as e:
            print(f"❌ Error reading CSV {idx+1}: {str(e)}")
            import traceback
            traceback.print_exc()
            self.data_tables[idx] = None

    def _setup_disk_cache(self, csv_idx: int, file_path: str):
        """Setup disk cache directory for a CSV file"""
        cache_dir = f"{file_path}.lodcache"
        try:
            os.makedirs(cache_dir, exist_ok=True)
            self.disk_cache_dirs[csv_idx] = cache_dir
        except Exception as e:
            print(f"⚠️ Could not create cache directory: {e}")
            self.disk_cache_dirs[csv_idx] = None

    def read_large_csv_chunked(self, file_path: str, delimiter: str = None, 
                               header_row: int = 0, skip_rows: int = 0) -> pd.DataFrame:
        """Read large CSV files in chunks with progress
        
        Args:
            file_path: Path to CSV file
            header: Row number for header (0-based), or None for no header
        """
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        # Adaptive chunk size
        if file_size_mb > 1000:
            chunk_size = 500000
        elif file_size_mb > 500:
            chunk_size = 300000
        else:
            chunk_size = 200000

        chunks = []
        total_rows = 0

        try:
            # Read in chunks
            chunk_iter = pd.read_csv(file_path, chunksize=chunk_size, low_memory=False, header=header)

            for i, chunk in enumerate(chunk_iter):
                if i == 0 and header is not None:
                    # Rename Time column in first chunk
                    chunk.rename(columns={chunk.columns[0]: "Time"}, inplace=True)

                chunks.append(chunk)
                total_rows += len(chunk)

                # Progress update every 1M rows
                if total_rows % 1000000 == 0:
                    print(f"   📊 Read {total_rows:,} rows...")

            if chunks:
                print(f"   🔄 Concatenating {len(chunks)} chunks...")
                df = pd.concat(chunks, ignore_index=True)
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            print(f"⚠️ Chunked read failed, trying direct read: {e}")
            # Fallback to direct read
            return pd.read_csv(file_path, low_memory=False)

    def validate_csv_format(self, df: pd.DataFrame, file_path: str) -> bool:
        """Validate CSV file format"""
        try:
            if df.empty:
                return False

            # Must have at least 2 columns (Time + 1 signal)
            if len(df.columns) < 2:
                return False

            # Check for numeric data
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) < 1:
                return False

            return True

        except Exception as e:
            print(f"Validation error: {e}")
            return False

    def update_signal_names(self):
        """Update list of all signal names across all CSV files"""
        all_signals = set()

        for df in self.data_tables:
            if df is not None and not df.empty:
                # Get all columns except Time
                signals = [col for col in df.columns if col != "Time"]
                all_signals.update(signals)

        self.signal_names = sorted(list(all_signals))

    def initialize_signal_maps(self):
        """Initialize signal scaling and state maps"""
        for signal_name in self.signal_names:
            if signal_name not in self.signal_scaling:
                self.signal_scaling[signal_name] = 1.0
            if signal_name not in self.state_signals:
                self.state_signals[signal_name] = False

    def get_signal_data(
        self, csv_idx: int, signal_name: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Get signal data (backwards compatible)"""
        return self.get_signal_data_ext(csv_idx, signal_name)

    def get_signal_data_ext(
        self,
        csv_idx: int,
        signal_name: str,
        max_points: Optional[int] = None,
        start: Optional[float] = None,
        end: Optional[float] = None,
        use_cache: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Get signal data with advanced caching and decimation"""

        # Check memory cache first (only for full-range queries)
        if use_cache and start is None and end is None and max_points:
            cache_key = (csv_idx, signal_name, max_points)
            cached = self.memory_cache.get(cache_key)
            if cached is not None:
                self.cache_hits += 1
                self._maybe_report_cache_stats()
                return cached
            self.cache_misses += 1

        try:
            # Validate indices
            if csv_idx < 0 or csv_idx >= len(self.data_tables):
                return np.array([]), np.array([])

            df = self.data_tables[csv_idx]
            if df is None or df.empty:
                return np.array([]), np.array([])

            if signal_name not in df.columns:
                return np.array([]), np.array([])

            # Extract data
            time_data = df["Time"].values
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

            # Apply time range filter
            if start is not None or end is not None:
                time_data, signal_data = self._apply_time_range(
                    time_data, signal_data, start, end
                )

            # No decimation needed
            if not max_points or len(time_data) <= max_points:
                return time_data, signal_data

            # Check disk cache
            result = self._check_disk_cache(csv_idx, signal_name, max_points)
            if result is not None:
                # Store in memory cache
                if use_cache and start is None and end is None:
                    cache_key = (csv_idx, signal_name, max_points)
                    self.memory_cache.set(cache_key, result)
                return result

            # Compute decimation using LTTB algorithm
            decimated = self._decimate_lttb(time_data, signal_data, max_points)

            # Save to disk cache
            self._save_disk_cache(csv_idx, signal_name, max_points, decimated)

            # Save to memory cache
            if use_cache and start is None and end is None:
                cache_key = (csv_idx, signal_name, max_points)
                self.memory_cache.set(cache_key, decimated)

            return decimated

        except Exception as e:
            print(
                f"❌ Error getting signal data for {signal_name} from CSV {csv_idx}: {e}"
            )
            return np.array([]), np.array([])

    def _apply_time_range(
        self,
        time_data: np.ndarray,
        signal_data: np.ndarray,
        start: Optional[float],
        end: Optional[float],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Apply time range filter to data"""
        if start is None and end is None:
            return time_data, signal_data

        s_idx = 0
        e_idx = len(time_data)

        if start is not None:
            s_idx = int(np.searchsorted(time_data, start, side="left"))
        if end is not None:
            e_idx = int(np.searchsorted(time_data, end, side="right"))

        return time_data[s_idx:e_idx], signal_data[s_idx:e_idx]

    def _check_disk_cache(
        self, csv_idx: int, signal_name: str, max_points: int
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Check disk cache for decimated data"""
        cache_dir = self.disk_cache_dirs.get(csv_idx)
        if not cache_dir:
            return None

        # Create safe filename
        safe_sig = signal_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        cache_file = os.path.join(cache_dir, f"{safe_sig}_lod_{max_points}.npz")

        if os.path.exists(cache_file):
            try:
                data = np.load(cache_file)
                return (data["x"], data["y"])
            except Exception:
                pass

        return None

    def _save_disk_cache(
        self,
        csv_idx: int,
        signal_name: str,
        max_points: int,
        data: Tuple[np.ndarray, np.ndarray],
    ):
        """Save decimated data to disk cache"""
        cache_dir = self.disk_cache_dirs.get(csv_idx)
        if not cache_dir:
            return

        safe_sig = signal_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        cache_file = os.path.join(cache_dir, f"{safe_sig}_lod_{max_points}.npz")

        try:
            np.savez_compressed(cache_file, x=data[0], y=data[1])
        except Exception as e:
            print(f"⚠️ Cache write failed: {e}")

    def _decimate_lttb(
        self, x: np.ndarray, y: np.ndarray, max_points: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Largest Triangle Three Buckets (LTTB) downsampling algorithm
        Better than min/max for preserving visual appearance
        """
        n = len(x)
        if n <= max_points:
            return x, y

        if max_points < 3:
            max_points = 3

        # Output arrays
        out_x = np.zeros(max_points)
        out_y = np.zeros(max_points)

        # Always keep first and last points
        out_x[0] = x[0]
        out_y[0] = y[0]
        out_x[-1] = x[-1]
        out_y[-1] = y[-1]

        # Bucket size
        bucket_size = (n - 2) / (max_points - 2)

        a = 0  # Initially point a is first point
        for i in range(1, max_points - 1):
            # Calculate point average for next bucket
            avg_x = 0
            avg_y = 0
            avg_range_start = int(np.floor((i + 1) * bucket_size) + 1)
            avg_range_end = int(np.floor((i + 2) * bucket_size) + 1)
            avg_range_end = min(avg_range_end, n)

            avg_range_length = avg_range_end - avg_range_start

            for j in range(avg_range_start, avg_range_end):
                avg_x += x[j]
                avg_y += y[j]

            if avg_range_length > 0:
                avg_x /= avg_range_length
                avg_y /= avg_range_length

            # Get range for this bucket
            range_offs = int(np.floor(i * bucket_size) + 1)
            range_to = int(np.floor((i + 1) * bucket_size) + 1)

            # Point a
            point_a_x = x[a]
            point_a_y = y[a]

            max_area = -1
            max_area_point = range_offs

            for j in range(range_offs, range_to):
                # Calculate triangle area
                area = (
                    abs(
                        (point_a_x - avg_x) * (y[j] - point_a_y)
                        - (point_a_x - x[j]) * (avg_y - point_a_y)
                    )
                    * 0.5
                )

                if area > max_area:
                    max_area = area
                    max_area_point = j

            out_x[i] = x[max_area_point]
            out_y[i] = y[max_area_point]
            a = max_area_point

        return out_x, out_y

    def get_signal_statistics(
        self, csv_idx: int, signal_name: str, use_cache: bool = True
    ) -> Dict:
        """Get cached signal statistics"""
        cache_key = (csv_idx, signal_name)

        if use_cache and cache_key in self.statistics_cache:
            return self.statistics_cache[cache_key]

        try:
            time_data, signal_data = self.get_signal_data(csv_idx, signal_name)

            if len(signal_data) == 0:
                return {}

            valid_mask = ~np.isnan(signal_data)
            valid_data = signal_data[valid_mask]

            if len(valid_data) == 0:
                return {}

            stats = {
                "mean": float(np.mean(valid_data)),
                "std": float(np.std(valid_data)),
                "min": float(np.min(valid_data)),
                "max": float(np.max(valid_data)),
                "rms": float(np.sqrt(np.mean(valid_data**2))),
                "median": float(np.median(valid_data)),
                "count": int(len(valid_data)),
                "range": float(np.ptp(valid_data)),
            }

            if len(time_data) > 1:
                dt = np.diff(time_data)
                if len(dt) > 0 and np.mean(dt) > 0:
                    stats["sample_rate"] = float(1.0 / np.mean(dt))
                    stats["duration"] = float(time_data[-1] - time_data[0])

            if use_cache:
                self.statistics_cache[cache_key] = stats

            return stats

        except Exception as e:
            print(f"Error computing statistics: {e}")
            return {}

    def _maybe_report_cache_stats(self):
        """Periodically report cache statistics"""
        now = time.time()
        if now - self.last_cache_report > 30:  # Every 30 seconds
            total = self.cache_hits + self.cache_misses
            if total > 0:
                hit_rate = 100 * self.cache_hits / total
                print(
                    f"📊 Cache: {self.cache_hits}/{total} hits ({hit_rate:.1f}%), "
                    f"{len(self.memory_cache)} entries"
                )
            self.last_cache_report = now

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
        self.memory_cache.clear()
        self.statistics_cache.clear()
        self.disk_cache_dirs.clear()

    def stop_streaming_all(self):
        """Stop all streaming"""
        self.is_running = False
        for timer in self.streaming_timers:
            if timer:
                timer.cancel()
        self.streaming_timers = []

    def print_cache_stats(self):
        """Print detailed cache performance statistics"""
        total = self.cache_hits + self.cache_misses
        if total > 0:
            hit_rate = 100 * self.cache_hits / total
            print(f"\n{'='*60}")
            print(f"📊 CACHE PERFORMANCE REPORT")
            print(f"{'='*60}")
            print(f"Memory Cache:")
            print(f"  - Hits: {self.cache_hits:,}")
            print(f"  - Misses: {self.cache_misses:,}")
            print(f"  - Hit Rate: {hit_rate:.1f}%")
            print(f"  - Entries: {len(self.memory_cache)}")
            print(f"Statistics Cache:")
            print(f"  - Entries: {len(self.statistics_cache)}")
            print(f"Disk Cache:")
            print(f"  - Active directories: {len(self.disk_cache_dirs)}")

            if self.load_times:
                avg_load = np.mean(self.load_times)
                print(f"Load Performance:")
                print(f"  - Average load time: {avg_load:.2f}s")
                print(f"  - Files loaded: {len(self.load_times)}")
            print(f"{'='*60}\n")


    # =========================================================================
    # Efficient Incremental CSV Reading for Streaming
    # =========================================================================
    
    def check_csv_updated(self, csv_idx: int) -> bool:
        """
        Check if a CSV file has been updated since last read.
        
        Returns:
            True if file was modified, False otherwise
        """
        if csv_idx >= len(self.csv_file_paths):
            return False
        
        file_path = self.csv_file_paths[csv_idx]
        if not os.path.isfile(file_path):
            return False
        
        try:
            current_mod_time = os.path.getmtime(file_path)
            last_mod_time = self.last_file_mod_times[csv_idx] if csv_idx < len(self.last_file_mod_times) else 0
            
            return current_mod_time > last_mod_time
        except Exception as e:
            print(f"Error checking file modification: {e}")
            return False
    
    def read_csv_incremental(self, csv_idx: int) -> bool:
        """
        Read only NEW rows from CSV file (efficient for streaming).
        
        Strategy:
        1. Check file modification time
        2. If modified, read from last known row count
        3. Append new rows to existing DataFrame
        4. Update caches
        
        Returns:
            True if new data was read, False otherwise
        """
        if csv_idx >= len(self.csv_file_paths):
            return False
        
        file_path = self.csv_file_paths[csv_idx]
        
        if not os.path.isfile(file_path):
            return False
        
        try:
            # Check if file was modified
            if not self.check_csv_updated(csv_idx):
                return False
            
            # Get last known row count
            last_row_count = self.last_read_rows[csv_idx] if csv_idx < len(self.last_read_rows) else 0
            
            # Count current rows in file (fast - just count newlines)
            current_row_count = self._count_file_rows(file_path)
            
            if current_row_count <= last_row_count:
                # File might have been truncated or no new data
                # Update mod time anyway
                self.last_file_mod_times[csv_idx] = os.path.getmtime(file_path)
                return False
            
            # Calculate how many new rows
            new_rows = current_row_count - last_row_count
            
            print(f"📊 CSV {csv_idx}: {new_rows} new rows detected (was {last_row_count}, now {current_row_count})")
            
            # Get CSV settings for this file
            csv_settings = self.csv_settings.get(csv_idx, {})
            delimiter = csv_settings.get('delimiter', None)
            if delimiter == 'auto':
                delimiter = None
            
            # Read only new rows efficiently
            if new_rows < 1000:
                # Small update - read new rows directly
                new_data = self._read_csv_tail(
                    file_path, 
                    skip_rows=last_row_count,
                    nrows=new_rows,
                    delimiter=delimiter,
                    header_row=csv_settings.get('header_row', 0)
                )
                
                if new_data is not None and not new_data.empty:
                    # Get existing DataFrame
                    existing_df = self.data_tables[csv_idx]
                    
                    if existing_df is None:
                        # First read - use new data as is
                        self.data_tables[csv_idx] = new_data
                    else:
                        # Append new data
                        # Make sure columns match
                        if list(new_data.columns) == list(existing_df.columns):
                            self.data_tables[csv_idx] = pd.concat([existing_df, new_data], ignore_index=True)
                        else:
                            print(f"⚠️ Column mismatch in incremental read - doing full reload")
                            self.read_initial_data(csv_idx, csv_settings)
                            return True
                    
                    # Update row count
                    self.last_read_rows[csv_idx] = current_row_count
                    self.last_file_mod_times[csv_idx] = os.path.getmtime(file_path)
                    
                    # Invalidate cache for this CSV
                    self.invalidate_cache(csv_idx)
                    
                    self.update_counter += 1
                    return True
            else:
                # Large update - do full reload
                print(f"⚠️ Large update ({new_rows} rows) - doing full reload")
                self.read_initial_data(csv_idx, csv_settings)
                return True
                
        except Exception as e:
            print(f"❌ Error in incremental read: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return False
    
    def _count_file_rows(self, file_path: str) -> int:
        """
        Quickly count rows in a file.
        Much faster than reading entire file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except Exception as e:
            print(f"Error counting rows: {e}")
            return 0
    
    def _read_csv_tail(self, file_path: str, skip_rows: int, nrows: int, 
                       delimiter: str = None, header_row: int = 0) -> pd.DataFrame:
        """
        Read only the tail (last N rows) of a CSV file.
        
        Args:
            file_path: Path to CSV
            skip_rows: Number of rows to skip from start (including header)
            nrows: Number of rows to read
            delimiter: Column delimiter
            header_row: Which row has headers (used to get column names)
        
        Returns:
            DataFrame with new rows only
        """
        try:
            # First, read header to get column names
            header_df = self.flexible_loader.load_csv(
                file_path,
                auto_detect=(delimiter is None),
                delimiter=delimiter,
                header_row=header_row,
                preview_mode=True  # Just get structure
            )
            
            if header_df is None or header_df.empty:
                return None
            
            column_names = header_df.columns.tolist()
            
            # Now read just the new rows
            # Skip = header rows + rows we already have
            actual_skip = header_row + 1 + skip_rows
            
            if delimiter is None:
                # Auto-detect delimiter
                format_info = self.flexible_loader.detect_format(file_path)
                delimiter = format_info.get('delimiter', ',')
            
            # Read new rows
            df = pd.read_csv(
                file_path,
                delimiter=delimiter,
                skiprows=actual_skip,
                nrows=nrows,
                names=column_names,
                header=None,
                encoding='utf-8',
                on_bad_lines='skip'
            )
            
            return df
            
        except Exception as e:
            print(f"Error reading CSV tail: {e}")
            return None
    
    def start_streaming_all(self):
        """
        Start streaming all loaded CSVs with efficient incremental reading.
        """
        self.streaming_enabled = True
        self.is_running = True
        print(f"▶️ Started streaming {len(self.csv_file_paths)} CSV(s)")
        print(f"   Update rate: {self.update_rate}s")
        print(f"   Timeout: {self.timeout_duration}s of no updates")
    
    def stop_streaming_all(self):
        """Stop all streaming"""
        self.streaming_enabled = False
        self.is_running = False
        print("⏸️ Stopped streaming")
    
    def check_and_update_streaming(self) -> bool:
        """
        Check all CSVs for updates and read incrementally if needed.
        Call this periodically from the streaming callback.
        
        Returns:
            True if any CSV was updated
        """
        if not self.streaming_enabled:
            return False
        
        updated = False
        
        for csv_idx in range(len(self.csv_file_paths)):
            if self.read_csv_incremental(csv_idx):
                updated = True
        
        if updated:
            # Update signal names (in case new columns appeared)
            self.update_signal_names()
            self.last_update_time = datetime.now()
        
        return updated

    # =========================================================================
    # Flexible CSV Loading Helper Methods
    # =========================================================================
    
    def detect_csv_format(self, file_path: str) -> Dict:
        """
        Auto-detect CSV format using flexible loader.
        
        Returns:
            Dict with detected settings: delimiter, header_row, skip_rows, etc.
        """
        return self.flexible_loader.detect_format(file_path)
    
    def get_csv_preview(self, file_path: str, max_lines: int = 20) -> str:
        """
        Get raw text preview of CSV file.
        
        Returns:
            String with first N lines
        """
        return self.flexible_loader.get_preview(file_path, max_lines)
    
    def load_csv_with_settings(self, file_path: str, csv_idx: int = None, 
                               delimiter: str = None, header_row: int = 0,
                               skip_rows: int = 0, encoding: str = 'utf-8',
                               auto_detect: bool = True) -> bool:
        """
        Load a CSV file with specific settings using flexible loader.
        
        Args:
            file_path: Path to CSV file
            csv_idx: Index to store at (None = append new)
            delimiter: Column delimiter (None = auto-detect)
            header_row: Header row index (None = no headers)
            skip_rows: Rows to skip at start
            encoding: File encoding
            auto_detect: Auto-detect format settings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine index
            if csv_idx is None:
                csv_idx = len(self.csv_file_paths)
                self.csv_file_paths.append(file_path)
                self.data_tables.append(None)
                self.last_file_mod_times.append(0)
                self.last_read_rows.append(0)
            
            # Store settings for this CSV
            self.csv_settings[csv_idx] = {
                'delimiter': delimiter,
                'header_row': header_row,
                'skip_rows': skip_rows,
                'encoding': encoding,
                'auto_detect': auto_detect,
            }
            
            # Load the CSV
            self.read_initial_data(csv_idx, self.csv_settings[csv_idx])
            
            return self.data_tables[csv_idx] is not None
            
        except Exception as e:
            print(f"❌ Error loading CSV with settings: {str(e)}")
            return False
    
    def update_csv_settings(self, csv_idx: int, **settings):
        """
        Update settings for a CSV and reload it.
        
        Args:
            csv_idx: Index of CSV to update
            **settings: Settings to update (delimiter, header_row, skip_rows, etc.)
        """
        if csv_idx < 0 or csv_idx >= len(self.csv_file_paths):
            return False
        
        # Update stored settings
        if csv_idx not in self.csv_settings:
            self.csv_settings[csv_idx] = {}
        
        self.csv_settings[csv_idx].update(settings)
        
        # Reload the CSV
        self.read_initial_data(csv_idx, self.csv_settings[csv_idx])
        
        return self.data_tables[csv_idx] is not None