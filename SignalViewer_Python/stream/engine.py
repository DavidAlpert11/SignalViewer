"""
Signal Viewer Pro - Streaming Engine
=====================================
File watching and incremental data updates.
"""

import os
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from threading import Thread, Event

from core.models import Run, Signal


@dataclass
class StreamConfig:
    """Configuration for streaming"""
    enabled: bool = False
    update_interval: float = 0.5  # Seconds between checks
    time_span: Optional[float] = None  # Show last N seconds (None = all)
    freeze_display: bool = False  # Pause display updates
    append_mode: bool = True  # Append new rows vs full reload


@dataclass
class StreamState:
    """State for a streaming run"""
    run_idx: int
    file_path: str
    last_mod_time: float = 0.0
    last_row_count: int = 0
    last_file_size: int = 0
    accumulated_rows: int = 0
    update_count: int = 0


class StreamEngine:
    """
    Manages file watching and incremental updates for streaming mode.
    """
    
    def __init__(self):
        self.config = StreamConfig()
        self.states: Dict[int, StreamState] = {}
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._update_callback: Optional[Callable] = None
    
    def register_run(self, run_idx: int, file_path: str):
        """Register a run for streaming"""
        if not os.path.isfile(file_path):
            return
        
        stat = os.stat(file_path)
        self.states[run_idx] = StreamState(
            run_idx=run_idx,
            file_path=file_path,
            last_mod_time=stat.st_mtime,
            last_file_size=stat.st_size,
        )
    
    def unregister_run(self, run_idx: int):
        """Unregister a run from streaming"""
        if run_idx in self.states:
            del self.states[run_idx]
    
    def start(self, update_callback: Callable):
        """
        Start streaming.
        
        Args:
            update_callback: Called when updates detected, receives dict of updated run indices
        """
        if self._thread and self._thread.is_alive():
            return
        
        self.config.enabled = True
        self._update_callback = update_callback
        self._stop_event.clear()
        
        self._thread = Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        print("[STREAM] Started streaming")
    
    def stop(self):
        """Stop streaming"""
        self.config.enabled = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        print("[STREAM] Stopped streaming")
    
    def check_updates(self) -> Dict[int, Tuple[bool, int]]:
        """
        Check all registered files for updates.
        
        Returns:
            Dict mapping run_idx to (was_updated, new_row_count)
        """
        results = {}
        
        for run_idx, state in self.states.items():
            if not os.path.isfile(state.file_path):
                continue
            
            try:
                stat = os.stat(state.file_path)
                
                # Check if file changed
                if stat.st_mtime <= state.last_mod_time:
                    results[run_idx] = (False, state.last_row_count)
                    continue
                
                # File changed - count new rows
                new_size = stat.st_size
                size_delta = new_size - state.last_file_size
                
                if size_delta > 0:
                    # Estimate new rows (approximate)
                    if state.last_row_count > 0 and state.last_file_size > 0:
                        bytes_per_row = state.last_file_size / state.last_row_count
                        estimated_new_rows = int(size_delta / bytes_per_row) if bytes_per_row > 0 else 0
                    else:
                        estimated_new_rows = 0
                    
                    state.last_mod_time = stat.st_mtime
                    state.last_file_size = new_size
                    state.update_count += 1
                    
                    results[run_idx] = (True, estimated_new_rows)
                else:
                    results[run_idx] = (False, 0)
                    
            except Exception as e:
                print(f"[STREAM] Error checking file: {e}")
                results[run_idx] = (False, 0)
        
        return results
    
    def read_new_rows(
        self,
        state: StreamState,
        max_rows: int = 10000,
    ) -> Optional[pd.DataFrame]:
        """
        Read only new rows from a file.
        
        Args:
            state: Stream state for the run
            max_rows: Maximum rows to read
            
        Returns:
            DataFrame with new rows, or None
        """
        try:
            # Count current rows
            with open(state.file_path, 'r') as f:
                current_row_count = sum(1 for _ in f)
            
            if current_row_count <= state.last_row_count:
                return None
            
            new_row_count = current_row_count - state.last_row_count
            skip_rows = state.last_row_count
            
            # Read new rows
            df = pd.read_csv(
                state.file_path,
                skiprows=range(1, skip_rows + 1),  # Skip header + old rows
                nrows=min(new_row_count, max_rows),
            )
            
            state.last_row_count = current_row_count
            state.accumulated_rows += len(df)
            
            return df
            
        except Exception as e:
            print(f"[STREAM] Error reading new rows: {e}")
            return None
    
    def _watch_loop(self):
        """Background thread for file watching"""
        while not self._stop_event.is_set():
            if not self.config.enabled or self.config.freeze_display:
                time.sleep(self.config.update_interval)
                continue
            
            try:
                updates = self.check_updates()
                
                # Notify if any updates
                updated_runs = {idx: count for idx, (changed, count) in updates.items() if changed}
                
                if updated_runs and self._update_callback:
                    self._update_callback(updated_runs)
                    
            except Exception as e:
                print(f"[STREAM] Watch loop error: {e}")
            
            time.sleep(self.config.update_interval)
    
    def get_time_window(self, time_data: np.ndarray) -> Tuple[float, float]:
        """
        Get time window based on time_span config.
        
        Returns:
            (start_time, end_time) tuple
        """
        if len(time_data) == 0:
            return 0.0, 0.0
        
        end_time = float(time_data[-1])
        
        if self.config.time_span is not None:
            start_time = end_time - self.config.time_span
        else:
            start_time = float(time_data[0])
        
        return start_time, end_time

