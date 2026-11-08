"""26.A5: the app's guesses are visible and can be corrected - whether a numeric signal is a state
(held between samples) or a value (interpolated), and the unit of an object's angles on the map / 3D."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.models import Run, Signal  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def run():
    t = np.arange(0, 40, 0.01)
    r = Run(file_path="h", csv_display_name="h", time=t)
    r.signals["Gear"] = Signal(name="Gear", data=np.floor(t / 10), time=t)            # 0..3: looks like a state
    r.signals["Count"] = Signal(name="Count", data=np.floor(t / 13) * 2, time=t)       # a counter, also whole numbers
    r.signals["X"] = Signal(name="X", data=np.sin(t), time=t)
    r.signals["Xh"] = Signal(name="Xh", data=np.sin(t), time=t + 0.005)              # between Count's samples
    r.signals["Yaw"] = Signal(name="Yaw", data=170 * np.sin(t / 5), time=t)           # degrees, no unit in the name
    r.signals["Roll"] = Signal(name="Roll", data=0.05 * np.sin(t), time=t)
    r.signals["Lat"] = Signal(name="Lat", data=32 + t * 1e-5, time=t)
    r.signals["Lon"] = Signal(name="Lon", data=34.8 + t * 1e-5, time=t)
    r.compute_metadata()
    lr = store.add_pushed("heuristics", r)[0]
    yield lr.id
    client.post("/api/read_as", json={"names": {}})
    store.remove(lr.id)


def test_why_a_signal_is_read_as_a_state_and_the_correction(run):
    d = client.get("/api/discrete", params={"sig": f"{run}/Count"}).json()
    assert d["discrete"] is True and d["detected"] is True and d["levels"] == 4 and d["readAs"] is None
    r = client.post("/api/read_as", json={"names": {"Count": "value"}}).json()     # by name: every file
    assert next(s for x in r["runs"] if x["id"] == run for s in x["signals"] if s["name"] == "Count")["discrete"] is False
    assert store.is_state(f"{run}/Count") is False
    v = client.post("/api/cursor", json={"signals": [f"{run}/Count"], "t": 12.995}).json()["values"]
    assert v[f"{run}/Count"] == pytest.approx(1.0)              # halfway from 0 to 2: interpolated (held: 0)
    d = client.get("/api/discrete", params={"sig": f"{run}/Count"}).json()
    assert d["discrete"] is False and d["detected"] is True and d["readAs"] == "value"
    client.post("/api/read_as", json={"names": {"X": "state"}})
    assert store.is_state(f"{run}/X") is True and store.is_state(f"{run}/Count") is True    # Count back to automatic


def test_a_derived_signal_follows_the_correction(run):
    nm = store.add_derived("expr", [f"{run}/Xh", f"{run}/Count"], {"expr": "v1"}, "a5_held").name
    try:
        _, held = store.signal(f"derived/{nm}")
        assert set(np.unique(held[np.isfinite(held)])) <= {0.0, 2.0, 4.0, 6.0}     # a state: held
        client.post("/api/read_as", json={"names": {"Count": "value"}})
        _, y = store.signal(f"derived/{nm}")                       # computed again (its version changed)
        assert 1.0 in set(np.round(y[np.isfinite(y)], 6))          # a value: interpolated between samples
    finally:
        store.remove_derived(nm)


def test_angle_units_say_why(run):
    body = {"yaw": f"{run}/Yaw", "roll": f"{run}/Roll"}
    u = client.post("/api/angle_units", json=body).json()["units"]
    assert u["yaw"] == {"unit": "deg", "why": "beyond"} and u["roll"] == {"unit": "deg", "why": "beyond"}
    u = client.post("/api/angle_units", json={"roll": f"{run}/Roll"}).json()["units"]
    assert u["roll"] == {"unit": "rad", "why": "within"}             # alone, 0.05 looks like radians
    tr = client.post("/api/object_track", json={"lat": f"{run}/Lat", "lon": f"{run}/Lon", **body}).json()
    assert tr["units"] == {"yaw": "deg", "roll": "deg"} and tr["unitWhy"] == {"yaw": "beyond", "roll": "beyond"}
