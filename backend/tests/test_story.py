"""P10: Story mode's moments (svcore/story.py) on the Mount Tabor flight that tools/make_live_report_media.py
builds - truth, nav drifting 6 m north by the end, gps."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
from svcore.story import WORDS, moments  # noqa: E402

EVENTS = [{"t": 62.0, "text": "GPS: 9 satellites", "level": "warning"}, {"t": 150.0, "text": "nav drifts north", "level": "note"},
          {"t": 231.0, "text": "EKF variance", "level": "error"}]


@pytest.fixture(scope="module")
def tabor(tmp_path_factory):
    import csv as _csv

    import make_live_report_media as media
    path = str(tmp_path_factory.mktemp("story") / "tabor.csv")
    media.flight_csv(path)
    with open(path) as f:
        rows = list(_csv.reader(f))
    head, data = rows[0], np.array(rows[1:], dtype=float)
    col = {k: data[:, i] for i, k in enumerate(head)}
    t = col["time"]
    ground = np.full(len(t), 250.0)
    return [{"name": n, "t": t, "lat": col[f"{n}.lat"], "lon": col[f"{n}.lon"], "alt": col[f"{n}.alt"], "ground": ground,
             "roll": col.get(f"{n}.att.roll")} for n in ("truth", "nav", "gps")]


def test_tabor_moments(tabor):
    ms = moments(tabor, EVENTS, {"primary": "truth", "secondary": "nav"})
    kinds = [m["kind"] for m in ms]
    assert len(ms) <= 12
    assert all(b["t"] - a["t"] >= 3 for a, b in zip(ms, ms[1:]))          # never two within 3 s, sorted
    err = next(m for m in ms if m["kind"] == "largest_error")
    assert err["t"] > 250 and "6." in err["text"] and "north" in err["text"] and err["object"] == "nav"
    assert "highest" in kinds and "fastest" in kinds
    assert [m["text"] for m in ms if m["kind"] == "event"] == ["GPS: 9 satellites", "nav drifts north", "EKF variance"]
    assert {m["level"] for m in ms if m["kind"] == "event"} == {"warning", "note", "error"}


def test_two_vehicles_closest_and_farthest(tabor):
    far = dict(tabor[2], name="other", lat=tabor[2]["lat"] + 0.01)           # ~1.1 km north: another vehicle
    ms = moments([tabor[0], far], [], {"primary": "truth", "secondary": "other"})
    kinds = [m["kind"] for m in ms]
    assert "closest" in kinds and "farthest" in kinds and "largest_error" not in kinds


def test_takeoff_landing_places_and_limits():
    t = np.arange(0, 200, 0.5)
    agl = np.clip(np.minimum(t - 20, 170 - t) * 5, 0, 1000)
    lat, lon = 32 + t * 1e-5, np.full(len(t), 35.0)
    o = {"name": "uav", "t": t, "lat": lat, "lon": lon, "alt": 100 + agl, "ground": np.full(len(t), 100.0), "roll": 40 * np.sin(t / 10)}
    pl = [{"name": "Runway 27", "lat": 32 + 100 * 1e-5, "lon": 35.0}]
    ms = moments([o], [{"t": 1.0 * k, "text": f"e{k}", "level": "note"} for k in range(0, 200, 4)], places=pl)
    assert len(ms) == 12                                                          # at most 12, the strongest first
    ms = moments([o], [], places=pl, units="imperial")
    kinds = {m["kind"]: m for m in ms}
    assert kinds["takeoff"]["t"] == pytest.approx(21, abs=1.5) and kinds["landing"]["t"] == pytest.approx(169, abs=1.5)
    assert kinds["place"]["title"] == "Over Runway 27"
    assert kinds["steepest"]["text"].startswith("uav banks 40°")
    assert "ft" in kinds["highest"]["text"]


def test_hebrew_for_every_kind(tabor):
    en, he = WORDS["en"], WORDS["he"]
    assert set(en) == set(he)
    ms = moments(tabor, EVENTS, {"primary": "truth", "secondary": "nav"}, lang="he")
    err = next(m for m in ms if m["kind"] == "largest_error")
    assert "צפונית" in err["text"] and err["title"] == "השגיאה הכי גדולה"


def test_reports_have_the_flight_in_moments(tmp_path):
    """P10: a live report's replay carries the Story per tab; PDF / Word open with "The flight in N moments"."""
    import json
    import re

    import make_live_report_media as media
    import signalviewer as sv
    from app import report
    csv = str(tmp_path / "tabor.csv")
    media.flight_csv(csv)
    rec = sv.load(csv)
    scene = sv._scene_spec(rec, ["truth", "nav", "gps"], cursor=150.0)
    req = {"format": "html", "title": "T", "lang": "en", "tabs": [{"name": "F", "plots": [{**scene, "title": "Map"}]}, {"name": "G", "plots": []}],
           "replay": {"t": 0, "extent": [0, 299.9], "events": EVENTS, "storyLength": 45}}
    html = report.build_html(rec._store, req)
    data = json.loads(re.search(r'id="data"[^>]*>(.*?)</script>', html, re.S).group(1)) if 'id="data"' in html else None
    assert '"storyLength":45' in html.replace(" ", "") and "largest_error" in html
    if data:
        assert len(data["replay"]["story"]) == 2 and not [m for m in data["replay"]["story"][1] if m["kind"] != "event"]
    secs, pics = report._story_parts(rec._store, {"lang": "en", "tabs": req["tabs"], "notes": []})
    assert secs[0]["title"].startswith("The flight in ") and secs[0]["table"]["rows"] and 1 <= len(pics) <= 4
    pdf = str(tmp_path / "r.pdf")
    report.build_pdf(rec._store, {**req, "format": "pdf"}, pdf)
    assert os.path.getsize(pdf) > 50_000
