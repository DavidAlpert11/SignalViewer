"""F4: live instruments - the value in force at a time (never interpolated), its age, and the object's
attitude in degrees, heading, altitude and ground speed - for any file."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store
from svcore.instruments import ground_speed, last_sample, quat_to_euler

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def test_last_sample_holds_and_skips_nan():
    t = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([10.0, 20.0, np.nan, 40.0])
    assert last_sample(t, y, 1.5) == (20.0, 1.0)           # the older sample, not 25
    assert last_sample(t, y, 2.5) == (20.0, 1.0)           # NaN skipped
    assert last_sample(t, y, 99) == (40.0, 3.0)
    assert last_sample(t, y, -1) is None
    assert last_sample(t, np.full(4, np.nan), 3) is None


def test_quaternion_and_ground_speed():
    e = quat_to_euler(np.cos(np.radians(15)), np.sin(np.radians(15)), 0, 0)    # 30 deg roll
    assert e is not None and e["roll"] == pytest.approx(30) and e["pitch"] == pytest.approx(0, abs=1e-9)
    assert quat_to_euler(0, 0, 0, 0) is None
    t = np.arange(0, 10, 0.1)
    lat = 32.0 + t * (5.0 / 111_195.0)                 # 5 m/s north (1 deg = 111.195 km on R = 6371 km)
    lon = np.full_like(t, 35.0)
    assert ground_speed(t, lat, lon, 9.9) == pytest.approx(5.0, rel=1e-3)
    assert ground_speed(t, lat, lon, 0.0) is None      # one position only


def test_endpoint_any_file(tmp_path):
    p = tmp_path / "rig.csv"
    t = np.arange(0, 20, 0.5)
    roll = np.radians(10) * np.ones_like(t)           # radians: the Automatic rule takes them so
    yaw = np.full_like(t, -1.5708)                    # -90 deg: heading 270
    lat = 32.0 + t * (2.0 / 111_195.0)
    lon = np.full_like(t, 35.0)
    alt = 100 + t
    temp = 20 + t
    np.savetxt(p, np.column_stack([t, temp, roll, yaw, lat, lon, alt, (t > 10).astype(int)]), delimiter=",",
               header="Time,Engine.Temp [degC],roll,yaw,lat,lon,alt,Step", comments="", fmt="%.9g")
    rid = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]["id"]
    store.set_time_offset(rid, 5.0)
    body = {"t": 5.0 + 3.2, "items": [{"name": "Oil.Temp|Engine.Temp"}, {"name": "Nope"}, {"name": "Step"}],
            "object": {"roll": f"{rid}/roll", "yaw": f"{rid}/yaw", "lat": f"{rid}/lat", "lon": f"{rid}/lon", "alt": f"{rid}/alt"}}
    r = client.post(f"/api/runs/{rid}/instruments", json=body).json()
    a, missing, step = r["items"]
    assert a["sig"] == f"{rid}/Engine.Temp [degC]" and a["unit"] == "degC"
    assert a["value"] == pytest.approx(23.0) and a["at"] == pytest.approx(8.0) and a["age"] == pytest.approx(0.2)
    assert missing["sig"] is None and missing["value"] is None          # said, not hidden
    assert step["value"] == 0 and step["state"] is True and a["state"] is False
    assert a["step"] == pytest.approx(0.5)                              # what "late" means for this signal
    o = r["object"]
    assert o["roll"] == pytest.approx(10, abs=1e-4) and o["pitch"] is None
    assert o["yaw"] == pytest.approx(270, abs=1e-3)
    assert o["alt"] == pytest.approx(103) and o["gs"] == pytest.approx(2.0, rel=1e-3)
    # before the file starts: nothing, not the first value
    r0 = client.post(f"/api/runs/{rid}/instruments", json={**body, "t": 1.0}).json()
    assert r0["items"][0]["value"] is None and r0["object"]["roll"] is None
    assert client.post("/api/runs/gone/instruments", json=body).status_code == 404


def test_saved_template_keeps_its_instruments(tmp_path, monkeypatch):
    from app import prefs
    monkeypatch.setattr(prefs, "TEMPLATE_DIR", str(tmp_path))
    tpl = {"version": 2, "id": "", "name": "Bench", "slots": [{"id": "main", "name": "File"}],
           "tabs": [{"name": "A", "rows": 1, "cols": 1, "plots": []}],
           "instruments": ["Engine.Temp", "  ", 3, "Engine.Temp", "Rpm|Engine.Rpm"]}
    assert prefs.save_template(tpl)["instruments"] == ["Engine.Temp", "Rpm|Engine.Rpm"]
    old = prefs.save_template({k: v for k, v in tpl.items() if k != "instruments"})
    assert "instruments" not in old                                         # an old template stays as it was
