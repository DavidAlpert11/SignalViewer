"""Opening a file in a folder that has remembered CSV import settings: every format still opens
without an error (a flight log there used to open AND report "Unexpected error", because the code
read the import report from the Run - only the CSV loader puts one there):
    python -m pytest backend/tests/test_open_remembered.py"""
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
from fastapi.testclient import TestClient  # noqa: E402

import app.prefs as prefs  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402

client = TestClient(app)
ROOT = os.path.join(HERE, "..", "..")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path / "home"))
    os.makedirs(tmp_path / "home")
    yield
    for rid in list(store.order):
        store.remove(rid)


def test_other_formats_open_in_a_folder_with_remembered_settings(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    np.savetxt(d / "semi.csv", np.column_stack([np.arange(10.0), np.arange(10.0)]), delimiter=";", header="t;v", comments="", fmt="%g")
    r = client.post("/api/files/open", json={"paths": [str(d / "semi.csv")], "settings": {"delimiter": ";", "time_column": "t"}}).json()
    assert r["opened"] and prefs.import_for(str(d / "semi.csv"))          # remembered for the folder
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_test_bin.py"), str(d / "f.bin"), "--seconds", "5"],
                   check=True, capture_output=True)
    np.savetxt(d / "plain.csv", np.column_stack([np.arange(10.0), np.arange(10.0)]), delimiter=",", header="Time,x", comments="", fmt="%g")
    for name in ("f.bin", "plain.csv"):
        r = client.post("/api/files/open", json={"paths": [str(d / name)]}).json()
        assert r["errors"] == [] and len(r["opened"]) == 1, (name, r["errors"])
