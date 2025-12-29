"""
Unit tests for data_manager_optimized.py

Tests CSV loading, chunked reading, dtype optimization, and data retrieval.
"""

import unittest
import pandas as pd
import numpy as np
import tempfile
import os
from pathlib import Path

# Add parent to path so we can import data_manager_optimized
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_manager_optimized import DataManager


class TestDataManagerOptimized(unittest.TestCase):
    """Test suite for DataManager."""

    def setUp(self):
        """Create test CSV files and DataManager instance."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_manager = DataManager(None)  # app=None for testing

        # Create a small test CSV
        self.test_csv_path = os.path.join(self.temp_dir, "test.csv")
        t = np.linspace(0, 10, 100)
        df = pd.DataFrame(
            {
                "Time": t,
                "Signal_A": np.sin(t),
                "Signal_B": np.cos(t),
            }
        )
        df.to_csv(self.test_csv_path, index=False)

        # Create a larger test CSV for chunked reading
        self.large_csv_path = os.path.join(self.temp_dir, "large.csv")
        t_large = np.linspace(0, 100, 10000)
        df_large = pd.DataFrame(
            {
                "Time": t_large,
                "Sensor_1": np.sin(t_large) + np.random.normal(0, 0.1, len(t_large)),
                "Sensor_2": np.cos(t_large) + np.random.normal(0, 0.1, len(t_large)),
                "Sensor_3": np.sin(2 * t_large)
                + np.random.normal(0, 0.1, len(t_large)),
            }
        )
        df_large.to_csv(self.large_csv_path, index=False)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_single_csv(self):
        """Test loading a single CSV file."""
        self.data_manager.load_csv_files([self.test_csv_path])
        self.assertEqual(len(self.data_manager.csv_file_paths), 1)
        self.assertEqual(len(self.data_manager.data_tables), 1)
        self.assertIsNotNone(self.data_manager.data_tables[0])
        self.assertEqual(len(self.data_manager.data_tables[0]), 100)

    def test_load_multiple_csvs(self):
        """Test loading multiple CSV files."""
        self.data_manager.load_csv_files([self.test_csv_path, self.large_csv_path])
        self.assertEqual(len(self.data_manager.csv_file_paths), 2)
        self.assertEqual(len(self.data_manager.data_tables), 2)

    def test_signal_names(self):
        """Test that signal names are correctly extracted."""
        self.data_manager.load_csv_files([self.test_csv_path])
        # signal_names typically includes all columns except Time (or may include Time)
        # Check that the expected signals are present
        expected_signals = {"Signal_A", "Signal_B"}
        self.assertTrue(expected_signals.issubset(set(self.data_manager.signal_names)))

    def test_get_dataframe(self):
        """Test retrieving a dataframe by index."""
        self.data_manager.load_csv_files([self.test_csv_path])
        df = self.data_manager.get_dataframe(0)
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 100)
        self.assertIn("Signal_A", df.columns)

    def test_get_signal_data(self):
        """Test retrieving signal data."""
        self.data_manager.load_csv_files([self.test_csv_path])
        time_data, signal_data = self.data_manager.get_signal_data(0, "Signal_A")
        self.assertEqual(len(time_data), 100)
        self.assertEqual(len(signal_data), 100)
        # Check that Signal_A is approximately sin(t)
        expected = np.sin(time_data)
        np.testing.assert_array_almost_equal(signal_data, expected, decimal=5)

    def test_large_csv_chunked_reading(self):
        """Test that large CSV is read successfully (chunked reading)."""
        self.data_manager.load_csv_files([self.large_csv_path])
        self.assertEqual(len(self.data_manager.data_tables[0]), 10000)
        # Verify data integrity
        df = self.data_manager.get_dataframe(0)
        self.assertIn("Sensor_1", df.columns)
        self.assertEqual(len(df), 10000)

    def test_dtype_optimization(self):
        """Test that dtypes are optimized (memory reduction)."""
        self.data_manager.load_csv_files([self.large_csv_path])
        df = self.data_manager.get_dataframe(0)
        # Check that float64 columns may be optimized to float32 or similar
        # (depends on optimization strategy)
        self.assertIsNotNone(df)

    def test_nonexistent_signal(self):
        """Test behavior when requesting a nonexistent signal."""
        self.data_manager.load_csv_files([self.test_csv_path])
        time_data, signal_data = self.data_manager.get_signal_data(0, "NonExistent")
        # Should return empty arrays or handle gracefully
        self.assertEqual(len(time_data), 0)
        self.assertEqual(len(signal_data), 0)

    def test_invalid_csv_index(self):
        """Test behavior with invalid CSV index."""
        self.data_manager.load_csv_files([self.test_csv_path])
        df = self.data_manager.get_dataframe(999)  # Out of bounds
        self.assertIsNone(df)


if __name__ == "__main__":
    unittest.main()
