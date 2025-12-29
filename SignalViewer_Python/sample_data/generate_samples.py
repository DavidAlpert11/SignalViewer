"""
Generate sample CSV files for testing and demos.

Creates small, realistic signal data for quick testing of the app.
"""

import pandas as pd
import numpy as np
import os


def generate_sine_wave_csv(
    filename: str, duration: float = 10.0, sample_rate: float = 100.0
):
    """Generate a CSV with sine waves at different frequencies."""
    t = np.arange(0, duration, 1 / sample_rate)
    data = {
        "Time": t,
        "Signal_1Hz": np.sin(2 * np.pi * 1 * t),
        "Signal_2Hz": np.sin(2 * np.pi * 2 * t),
        "Signal_5Hz": np.sin(2 * np.pi * 5 * t),
        "Noise": np.random.normal(0, 0.1, len(t)),
    }
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"✅ Generated {filename} ({len(df)} rows)")


def generate_large_csv(filename: str, num_rows: int = 100000):
    """Generate a larger CSV for testing chunked loading and performance."""
    t = np.linspace(0, 100, num_rows)
    data = {
        "Time": t,
        "Acceleration_X": np.sin(t) + np.random.normal(0, 0.05, num_rows),
        "Acceleration_Y": np.cos(t) + np.random.normal(0, 0.05, num_rows),
        "Acceleration_Z": np.sin(2 * t) + np.random.normal(0, 0.05, num_rows),
        "Temperature": 20 + 5 * np.sin(t / 10) + np.random.normal(0, 0.2, num_rows),
        "Pressure": 1013 + 10 * np.cos(t / 15) + np.random.normal(0, 0.5, num_rows),
    }
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"✅ Generated {filename} ({len(df)} rows)")


def generate_multi_signal_csv(filename: str):
    """Generate a CSV with multiple signals for multi-tab testing."""
    t = np.linspace(0, 20, 2000)
    data = {
        "Time": t,
        "Voltage_CH1": 5 * np.sin(2 * np.pi * 0.5 * t),
        "Voltage_CH2": 3 * np.cos(2 * np.pi * 0.8 * t),
        "Current_CH1": 2 * np.sin(2 * np.pi * 1.0 * t),
        "Current_CH2": 1.5 * np.cos(2 * np.pi * 1.2 * t),
        "Power": 10 + 5 * np.sin(2 * np.pi * 0.1 * t),
    }
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"✅ Generated {filename} ({len(df)} rows)")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Generate sample files
    generate_sine_wave_csv(os.path.join(base_dir, "sample_sines.csv"))
    generate_large_csv(os.path.join(base_dir, "sample_large.csv"), num_rows=100000)
    generate_multi_signal_csv(os.path.join(base_dir, "sample_multi.csv"))

    print("\n✅ All sample CSV files generated in sample_data/")
