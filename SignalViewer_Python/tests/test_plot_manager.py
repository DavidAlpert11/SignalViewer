"""
Unit tests for plot_manager.py

Tests tab creation, signal assignment, subplot settings, and HTML generation.
"""

import unittest
from unittest.mock import Mock
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plot_manager import PlotManager


class MockApp:
    """Mock app for testing PlotManager."""

    def __init__(self):
        self.data_manager = Mock()
        self.data_manager.data_tables = []
        self.signal_operations = Mock()


class TestPlotManager(unittest.TestCase):
    """Test suite for PlotManager."""

    def setUp(self):
        """Create a PlotManager instance for testing."""
        self.app = MockApp()
        self.plot_manager = PlotManager(self.app)
        self.plot_manager.initialize()

    def test_initialize_creates_default_tab(self):
        """Test that initialization creates a default 1x1 tab."""
        self.assertEqual(len(self.plot_manager.plot_tabs), 1)
        self.assertEqual(len(self.plot_manager.assigned_signals), 1)
        self.assertEqual(len(self.plot_manager.tab_layouts), 1)

    def test_create_tab(self):
        """Test creating a new tab with specified rows/cols."""
        self.plot_manager.create_tab(rows=2, cols=2)
        self.assertEqual(len(self.plot_manager.plot_tabs), 2)
        layout = self.plot_manager.tab_layouts[1]
        self.assertEqual(layout["rows"], 2)
        self.assertEqual(layout["cols"], 2)

    def test_assign_signal(self):
        """Test assigning a signal to a subplot."""
        sig_info = {"csv_idx": 0, "signal": "TestSignal", "color": "#FF0000"}
        self.plot_manager.assign_signal(0, 0, sig_info)
        signals = self.plot_manager.get_subplot_signals(0, 0)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["signal"], "TestSignal")

    def test_remove_signal(self):
        """Test removing a signal from a subplot."""
        sig_info = {"csv_idx": 0, "signal": "TestSignal", "color": "#FF0000"}
        self.plot_manager.assign_signal(0, 0, sig_info)
        self.plot_manager.remove_signal(0, 0, sig_info)
        signals = self.plot_manager.get_subplot_signals(0, 0)
        self.assertEqual(len(signals), 0)

    def test_clear_subplot(self):
        """Test clearing all signals from a subplot."""
        sig1 = {"csv_idx": 0, "signal": "Signal1", "color": "#FF0000"}
        sig2 = {"csv_idx": 0, "signal": "Signal2", "color": "#00FF00"}
        self.plot_manager.assign_signal(0, 0, sig1)
        self.plot_manager.assign_signal(0, 0, sig2)
        self.plot_manager.clear_subplot(0, 0)
        signals = self.plot_manager.get_subplot_signals(0, 0)
        self.assertEqual(len(signals), 0)

    def test_remove_tab(self):
        """Test removing a tab."""
        self.plot_manager.create_tab(rows=1, cols=1)
        self.assertEqual(len(self.plot_manager.plot_tabs), 2)
        self.plot_manager.remove_tab(1)
        self.assertEqual(len(self.plot_manager.plot_tabs), 1)

    def test_move_tab(self):
        """Test moving a tab from one position to another."""
        self.plot_manager.create_tab(rows=2, cols=1)
        self.plot_manager.create_tab(rows=1, cols=2)
        # Move tab 2 to position 0
        self.plot_manager.move_tab(2, 0)
        layout_at_0 = self.plot_manager.tab_layouts[0]
        # After move, the 1x2 tab should be at position 0
        self.assertEqual(layout_at_0.get("cols"), 2)

    def test_insert_tab(self):
        """Test inserting a tab at a specific index."""
        self.plot_manager.create_tab(rows=1, cols=1)
        self.plot_manager.insert_tab(1, rows=3, cols=1)
        self.assertEqual(len(self.plot_manager.plot_tabs), 3)
        layout_at_1 = self.plot_manager.tab_layouts[1]
        self.assertEqual(layout_at_1["rows"], 3)

    def test_set_subplot_title(self):
        """Test setting a subplot title."""
        self.plot_manager.set_subplot_title(0, 0, "My Subplot")
        title = self.plot_manager.get_subplot_title(0, 0)
        self.assertEqual(title, "My Subplot")

    def test_set_axis_signal(self):
        """Test setting the X-axis signal for a subplot."""
        self.plot_manager.set_axis_signal(0, 0, "CustomSignal")
        signal = self.plot_manager.get_axis_signal(0, 0)
        self.assertEqual(signal, "CustomSignal")

    def test_get_axis_signal_default(self):
        """Test that default X-axis signal is 'Time'."""
        signal = self.plot_manager.get_axis_signal(0, 0)
        self.assertEqual(signal, "Time")

    def test_get_tab_html(self):
        """Test HTML generation for a single tab."""
        html = self.plot_manager.get_tab_html(0)
        # Should return a non-empty string
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 0)

    def test_get_all_tabs_html(self):
        """Test HTML generation for all tabs."""
        self.plot_manager.create_tab(rows=1, cols=1)
        html = self.plot_manager.get_all_tabs_html()
        # Should return a non-empty HTML string with tab UI
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 0)
        # Should contain tab button markup
        self.assertIn("Tab 1", html)
        self.assertIn("Tab 2", html)

    def test_downsample_data(self):
        """Test data downsampling."""
        x_data = list(range(100000))
        y_data = list(range(100000))
        x_down, y_down = self.plot_manager.downsample_data(x_data, y_data, 1000)
        self.assertEqual(len(x_down), 1000)
        self.assertEqual(len(y_down), 1000)

    def test_no_downsampling_for_small_data(self):
        """Test that small datasets are not downsampled."""
        x_data = list(range(100))
        y_data = list(range(100))
        x_result, y_result = self.plot_manager.downsample_data(x_data, y_data, 1000)
        self.assertEqual(len(x_result), 100)
        self.assertEqual(len(y_result), 100)


if __name__ == "__main__":
    unittest.main()
