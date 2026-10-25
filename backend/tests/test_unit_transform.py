"""A unit conversion is an in-place change with a unit: kept, saved with the values' change, and a
unit alone does not touch the values."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.store import normalize_transform, store  # noqa: E402


def test_unit_is_kept_and_cleaned():
    assert normalize_transform({"scale": 57.29, "unit": "  deg "}) == {"scale": 57.29, "unit": "deg"}
    assert normalize_transform({"unit": "km/h"}) == {"unit": "km/h"}
    assert normalize_transform({"unit": "", "scale": 1}) is None
    assert len(normalize_transform({"unit": "x" * 100})["unit"]) == 24


def test_conversion_values_and_unit_only(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("Time,Yaw [rad]\n" + "".join(f"{i * 0.1:.1f},{i * 0.01:.2f}\n" for i in range(50)))
    lr = store.open_file(str(p))
    sid = f"{lr.id}/Yaw [rad]"
    try:
        raw = store.signal(sid)[1].copy()
        store.set_transforms({sid: {"scale": 180 / np.pi, "unit": "deg"}})
        assert np.allclose(store.signal(sid)[1], raw * 180 / np.pi)
        info = next(s for s in store.describe(lr)["signals"] if s["name"] == "Yaw [rad]")
        assert info["transform"]["unit"] == "deg"
        store.set_transforms({sid: {"unit": "deg"}})                  # a label alone: same values
        assert np.array_equal(store.signal(sid)[1], raw)
    finally:
        store.remove(lr.id)
