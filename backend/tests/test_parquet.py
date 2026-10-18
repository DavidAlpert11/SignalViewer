"""T40: Parquet files - time from the pandas index / a time column / the user's choice."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import LoadError, store  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def opened(path, settings=None):
    lr = store.open_file(str(path), settings)
    return lr, {n: f"{lr.id}/{n}" for n in lr.run.signals}


def write_sample(path, n=50):
    df = pd.DataFrame({"speed": np.arange(n, dtype=float), "gear": np.arange(n) % 4,
                       "armed": np.arange(n) > 10, "mode": pd.Categorical(["idle"] * 10 + ["cruise"] * (n - 10)),
                       "note": ["x"] * n, "event_time": pd.date_range("2026-03-01", periods=n, freq="1s"),
                       "path": [[1, 2]] * n},
                      index=pd.date_range("2026-03-01 08:00", periods=n, freq="100ms", name="time"))
    df.to_parquet(path)


def test_pandas_time_index_and_column_types(tmp_path):
    p = tmp_path / "log.parquet"
    write_sample(p)
    lr, sig = opened(p)
    assert lr.run.import_settings["format"] == "parquet"
    t, y = store.signal(sig["speed"])
    assert t[0] == 0 and t[1] == pytest.approx(0.1) and y[5] == 5            # the index, in seconds from its start
    assert store.is_state(sig["mode"]) and store.is_state(sig["note"])
    assert set(store.signal(sig["armed"])[1]) == {0.0, 1.0}
    assert store.signal(sig["event_time"])[1][3] == pytest.approx(3.0)       # another date-time: seconds
    assert "time" not in sig and "path" not in sig
    assert any(s.startswith("path (") for s in lr.load_report["skipped"])


def test_time_column_by_name_unsorted_and_chosen(tmp_path):
    p = tmp_path / "sim.pq"
    pd.DataFrame({"t": [2.0, 0.0, 1.0], "x": [20.0, 0.0, 10.0], "y": [5.0, 6.0, 7.0]}).to_parquet(p)
    lr, sig = opened(p)
    t, x = store.signal(sig["x"])
    assert list(t) == [0, 1, 2] and list(x) == [0, 10, 20]                   # sorted by time
    lr2, sig2 = opened(p, {"time_column": "y"})                             # the user's choice wins
    assert "t" in sig2 and "y" not in sig2


def test_no_time_uses_sample_numbers(tmp_path):
    p = tmp_path / "plain.parquet"
    pd.DataFrame({"a": [1.0, 2.0, 3.0]}).to_parquet(p)
    lr, sig = opened(p)
    assert list(store.signal(sig["a"])[0]) == [0, 1, 2] and lr.load_report.get("noTime") is True


def test_through_the_api_and_wrong_extension(tmp_path):
    p = tmp_path / "log.parquet"
    write_sample(p)
    r = client.post("/api/files/open", json={"paths": [str(p)]}).json()
    assert r["errors"] == [] and r["opened"][0]["format"] == "parquet"
    q = tmp_path / "log.csv"
    q.write_bytes(p.read_bytes())
    err = client.post("/api/files/open", json={"paths": [str(q)]}).json()["errors"][0]
    assert err["code"] == "wrongExt" and ".parquet" in err["message"]


def test_damaged_parquet(tmp_path):
    p = tmp_path / "bad.parquet"
    p.write_bytes(b"PAR1" + os.urandom(3000))
    with pytest.raises(LoadError) as e:
        store.open_file(str(p))
    assert e.value.code == "badParquet"
