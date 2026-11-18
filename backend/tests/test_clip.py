"""CP1 (owner, 2026-11-18): a plot or a tab copied for a Confluence page. The interactive copy (for the HTML
macro) must stay small - a 4 MB page brought his Confluence editor down - yet keep every extreme (min/max), sit
in a frame of its own, and carry the statistics and the notes; the static copy has no script at all."""
import base64
import html
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app import report  # noqa: E402

client = TestClient(app)


def _page(fragment):
    m = re.search(r'srcdoc="([^"]*)"', fragment)
    assert m, "the copy is a frame"
    return html.unescape(m.group(1))


def _data(page):
    m = re.search(r'<script type="application/json" id="sv-data">(.*?)</script>', page, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_clip_is_small_keeps_the_needle_and_carries_table_and_notes(tmp_path):
    n = 400_000                                                   # 3 lines x 400k points: ~10 MB as the report's page
    t = np.arange(n) * 0.01
    rng = np.random.default_rng(1)
    a, b, c = rng.normal(0, 1, n), np.sin(t), rng.normal(5, 0.1, n)
    a[123_457] = 99.0                                             # the needle: one sample far above the rest
    path = tmp_path / "big.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write("time,a,b,c\n")
        np.savetxt(f, np.column_stack([t, a, b, c]), delimiter=",", fmt="%.6f")
    run = client.post("/api/files/open", json={"paths": [str(path)]}).json()["opened"][0]
    try:
        sig = lambda name, col: {"id": f"{run['id']}/{name}", "label": name, "color": col, "width": 1.5, "scale": 1, "offset": 0}
        body = {"title": "Bench run", "lang": "en", "notes": [{"t": 12.5, "text": "valve opens"}],
                "tabs": [{"name": "Tab", "plots": [{"mode": "time", "title": "Three", "signals": [sig("a", "#e33"), sig("b", "#33e"), sig("c", "#3a3")]}]}]}
        r = client.post("/api/export/clip", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        live, static = out["html"], out["static"]
        assert out["size"] == len(live.encode("utf-8"))
        assert out["size"] < 600_000, out["size"]                # well under what broke his editor (4 MB)
        assert live.startswith('<div class="sv-clip"><iframe') and "<script>" in live
        page = _page(live)
        assert "@font-face" not in page                          # the page's own fonts, not 80 kB of embedded ones
        assert "Min" in page and "valve opens" in page           # the statistics table and the notes
        d = _data(page)
        levels = d["tabs"][0]["plots"][0]["signals"][0]["levels"]
        assert len(levels) == 1 and levels[0]["n"] <= report.clip_points(body)
        y = np.frombuffer(base64.b64decode(levels[0]["y"]), dtype=np.float32)
        assert np.isclose(y.max(), 99.0)                         # min/max: the needle is drawn
        # the static copy: the picture, the table, the notes - and no script
        assert "<script" not in static and "data:image/png;base64," in static
        assert "valve opens" in static and ">Max<" in static and "99" in static
    finally:
        client.delete(f"/api/runs/{run['id']}")


def test_clip_points_shared_with_a_floor():
    one = {"tabs": [{"plots": [{"mode": "time", "signals": [{}]}]}]}
    many = {"tabs": [{"plots": [{"mode": "time", "signals": [{}] * 40}]}]}
    assert report.clip_points(one) == report.CLIP_POINTS
    assert report.clip_points(many) == report.CLIP_MIN_POINTS


def test_clip_hebrew_static_is_rtl_and_empty_is_refused():
    assert client.post("/api/export/clip", json={"tabs": [{"plots": []}]}).status_code == 400
    frag = report.build_clip_static(None, {"lang": "he", "tabs": [], "notes": [{"t": 1, "text": "הערה"}]})
    assert 'dir="rtl"' in frag and "הערות" in frag
