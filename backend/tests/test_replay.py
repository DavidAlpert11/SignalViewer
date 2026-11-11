"""R1: the replay page - the HTML report of one tab with one time for the whole page (report.build_html with
`replay`). On the fixture ardupilot_lanes.csv: the page carries the moment, the span and the marks, its map
hides its own time row and follows the page, and a report without `replay` is unchanged."""
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app import report  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.csv_loader import load_csv  # noqa: E402

client = TestClient(app)
EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "ardupilot_lanes.csv")


@pytest.fixture(scope="module")
def rid():
    os.environ["SV_OFFLINE"] = "1"
    r = load_csv(EX, [EX])
    run = store.add_pushed("ardupilot_lanes_replay", r)[0]
    yield run.id
    store.remove(run.id)


def body(rid, path="", replay=True, **extra):
    time_plot = {"mode": "time", "title": "Altitude", "signals": [
        {"id": f"{rid}/POS.Alt [m]", "label": "POS.Alt", "color": "#e5677a", "scale": 1, "offset": 0}]}
    geo = {"mode": "geo", "title": "Map", "signals": [], "geo": {
        "objects": [{"name": "POS", "color": "#e5677a", "lat": f"{rid}/POS.Lat [deg]", "lon": f"{rid}/POS.Lng [deg]"}],
        "base": "offline", "cursor": 100.0}}
    b = {"path": path, "format": "html", "title": "Flight", "lang": "en", "theme": "dark",
         "tabs": [{"name": "Flight", "plots": [geo, time_plot]}], **extra}
    if replay:
        b["replay"] = {"t": 100.0, "extent": [0, 200], "events": [
            {"t": 50, "text": "GPS glitch", "level": "warning"}, {"t": 120, "text": "<b>x</b>", "level": "bogus"},
            {"t": float("nan"), "text": "no time"}]}
    return b


def payload(text):
    m = re.search(r'<script type="application/json" id="sv-data">(.*?)</script>', text, re.S)
    return json.loads(m.group(1))


def test_replay_page_carries_moment_span_and_marks(rid):
    text = report.build_html(store, body(rid))
    p = payload(text)
    assert p["replay"]["t"] == 100.0 and p["replay"]["extent"] == [0.0, 200.0]
    # marks: a time is needed; an unknown level is a note; the text stays text (escaped by the page, not here)
    assert [(e["t"], e["level"]) for e in p["replay"]["events"]] == [(50.0, "warning"), (120.0, "note")]
    assert '<body class="replay">' in text and 'id="rp-track"' in text and 'id="rp-play"' in text
    assert "Made with Signal Viewer" in text and report.REPLAY_URL in text      # where it came from
    assert "iframe class=\"mapframe\"" in text                                  # the map, in the same page


def test_replay_marks_are_bounded_and_checked():
    r = report._replay({"t": "x", "extent": [5, 1], "events": [{"t": i, "text": "a" * 500} for i in range(800)]})
    assert r["t"] is None and r["extent"] is None
    assert len(r["events"]) == 500 and len(r["events"][0]["text"]) == 200
    assert report._replay(None) is None and report._replay("no") is None


def test_report_without_replay_is_unchanged(rid):
    text = report.build_html(store, body(rid, replay=False))
    assert "replay" not in payload(text) and 'id="rp-track"' not in text and '<body>' in text
    assert "<footer>Signal Viewer</footer>" in text


def test_map_follows_the_page():
    """The map's own page listens for the replay's time and hides its slider there (one time control)."""
    with open(os.path.join(os.path.dirname(report.__file__), "report_assets", "map.html"), encoding="utf-8") as f:
        page = f.read()
    assert 'm.sv !== "replay"' in page and "hideTime" in page and "#time[hidden]" in page


def test_replay_through_the_route(rid, tmp_path):
    path = str(tmp_path / "flight-replay.html")
    b = body(rid, path)
    b["replay"]["events"] = b["replay"]["events"][:2]          # JSON has no NaN (the check above covers it)
    r = client.post("/api/report", json=b)
    assert r.status_code == 200, r.text
    with open(path, encoding="utf-8") as f:
        assert payload(f.read())["replay"]["t"] == 100.0


def test_open_page_html_only(tmp_path, monkeypatch):
    import webbrowser
    seen = []
    monkeypatch.setattr(webbrowser, "open", lambda url, new=0: seen.append(url) or True)
    page = tmp_path / "r.html"
    page.write_text("<p>x</p>", encoding="utf-8")
    assert client.post("/api/export/open", json={"path": str(page)}).json() == {"opened": True}
    assert seen and seen[0].startswith("file://") and seen[0].endswith("r.html")
    other = tmp_path / "r.exe"
    other.write_text("x")
    assert client.post("/api/export/open", json={"path": str(other)}).status_code == 400
    assert client.post("/api/export/open", json={"path": str(tmp_path / "none.html")}).status_code == 400
    assert len(seen) == 1
