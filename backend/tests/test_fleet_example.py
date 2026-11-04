"""The Fleet example (examples/fleet, tools/make_fleet_example.py): what it plants is what the index
finds - the worn motor's vibration growing to a warning, the GPS stretch, the worn battery."""
import os

import pytest

from app.fleet import index_file

FOLDER = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "fleet")


@pytest.mark.skipif(not os.path.isdir(FOLDER), reason="the example folder is not here")
def test_fleet_example_stories():
    rows = {n: index_file(os.path.join(FOLDER, n)) for n in sorted(os.listdir(FOLDER)) if n.endswith(".bin")}
    assert len(rows) == 10 and not any(r.get("error") for r in rows.values())
    a = [r["metrics"]["vibration.max"] for n, r in rows.items() if n.startswith("X8-A")]
    assert a == sorted(a) and a[-2] < 30 < a[-1]                        # grows, the last crosses
    codes = lambda n: {f["code"] for f in rows[n]["findings"] if f["level"] != "ok"}  # noqa: E731
    assert {"vibration", "clipping"} <= codes("X8-A_2026-10-07.bin")
    assert "gpsSats" in codes("X8-B_2026-09-19.bin")
    assert "battLow" in codes("X8-B_2026-10-17.bin")
    assert all(rows[n]["date_source"] == "gps" for n in rows)            # dates from the logs' GPS time
