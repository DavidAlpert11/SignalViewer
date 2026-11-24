"""CP1 (owner, 2026-11-18): a plot or a tab for a Confluence page, every sample interactive. The page with all the
data is saved (attached to the Confluence page); the HTML macro gets only a few lines that fetch it - a 4 MB page in
the macro brought his editor down. The static copy (picture, statistics, notes) has no script at all."""
import base64
import html
import json
import os
import re
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app import report, report_clip  # noqa: E402

client = TestClient(app)


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
        r = client.post("/api/export/clip", json={**body, "path": str(tmp_path / "bench")})
        assert r.status_code == 200, r.text
        out = r.json()
        macro, static = out["macro"], out["static"]
        assert out["name"] == "bench.html" and os.path.isfile(tmp_path / "bench.html")
        page = (tmp_path / "bench.html").read_text(encoding="utf-8")
        assert out["size"] == len(page.encode("utf-8"))
        # the macro: small, a frame, the attachment of the page it is on, by name
        assert len(macro) < 4000 and "<iframe" in macro and "/download/attachments/" in macro and '"bench.html"' in macro
        assert "Min" in page and "valve opens" in page           # the statistics table and the notes
        d = _data(page)
        levels = d["tabs"][0]["plots"][0]["signals"][0]["levels"]
        assert levels[-1]["n"] == n                              # every sample: the finest level is the recording
        assert all(lv["n"] < n for lv in levels[:-1])            # the coarser ones draw it until zoomed in
        y = np.frombuffer(base64.b64decode(levels[-1]["y"]), dtype=np.float32)
        assert np.allclose(y, a.astype(np.float32), atol=1e-5)
        for lv in levels[:-1]:                                   # min/max: the needle is in every level
            assert np.isclose(np.frombuffer(base64.b64decode(lv["y"]), dtype=np.float32).max(), 99.0)
        # the static copy: the picture, the table, the notes - and no script
        assert "<script" not in static and "data:image/png;base64," in static
        assert "valve opens" in static and ">Max<" in static and "99" in static
    finally:
        client.delete(f"/api/runs/{run['id']}")


def test_clip_macro_words_and_no_closing_script_inside():
    m = report_clip.build_clip_macro({"lang": "he", "tabs": []}, "a</script>.html")
    assert "גררו את הקובץ" in m and m.count("</script>") == 1


def test_clip_hebrew_static_is_rtl_and_empty_is_refused():
    assert client.post("/api/export/clip", json={"path": "x", "tabs": [{"plots": []}]}).status_code == 400
    frag = report_clip.build_clip_static(None, {"lang": "he", "tabs": [], "notes": [{"t": 1, "text": "הערה"}]})
    assert 'dir="rtl"' in frag and "הערות" in frag


def test_user_macro_template_is_velocity_safe_and_the_copy_is_its_markup(tmp_path):
    """CP3 (owner, 2026-11-22): Confluence Data Center keeps the HTML macro off - the Signal Viewer user macro an
    administrator installs once. Its template is Velocity: the script must carry no "$" or "#" of its own; the
    attachment's name, the page and the height come from Confluence, HTML-encoded."""
    t = client.get("/api/export/clip/user-macro").json()
    assert t["name"] == "signalviewer"
    tpl = t["template"]
    assert "## @param file:" in tpl and "## @param height:" in tpl
    body = "\n".join(ln for ln in tpl.splitlines() if not ln.startswith("##"))
    script = body.split("<script>", 1)[1].split("</script>", 1)[0]
    assert "$" not in script and "#" not in script
    assert 'data-name="$!generalUtil.htmlEncode($!paramfile)"' in body and 'data-page="$!content.id"' in body
    assert body.count("</script>") == 1
    # the copy: the markup, not the HTML macro's lines; a name the markup cannot carry is refused
    path = tmp_path / "s.csv"
    path.write_text("time,a\n0,1\n1,2\n2,3\n", encoding="utf-8")
    run = client.post("/api/files/open", json={"paths": [str(path)]}).json()["opened"][0]
    try:
        plot = {"mode": "time", "title": "A", "signals": [{"id": f"{run['id']}/a", "label": "a", "color": "#e33", "width": 1.5,
                                                         "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}
        r = client.post("/api/export/clip", json={"path": str(tmp_path / "run 1.html"), "macro": "user", "tabs": [{"name": "", "plots": [plot]}]})
        assert r.status_code == 200, r.text
        assert re.fullmatch(r"\{signalviewer:file=run 1\.html\|height=\d+\}", r.json()["macro"])
        bad = client.post("/api/export/clip", json={"path": str(tmp_path / "a|b.html"), "macro": "user", "tabs": [{"name": "", "plots": [plot]}]})
        assert bad.status_code == 400 and "|" in bad.json()["detail"]
    finally:
        client.delete(f"/api/runs/{run['id']}")


def test_a_plot_dragged_out_is_its_page(tmp_path):
    """CP5 (owner, 2026-11-22: "drag the plot or the tab out - HTML by default"): the page says what it drags (a random
    token), the system fetches the link at the drop - the report's page of it, every sample, as a file."""
    path = tmp_path / "s.csv"
    path.write_text("time,a\n" + "".join("%g,%g\n" % (i * 0.1, i % 5) for i in range(100)), encoding="utf-8")
    run = client.post("/api/files/open", json={"paths": [str(path)]}).json()["opened"][0]
    try:
        plot = {"mode": "time", "title": "A", "signals": [{"id": f"{run['id']}/a", "label": "a", "color": "#e33", "width": 1.5,
                                                         "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}
        tok = "0b9e2c34-5d1f-4c8e-9a77-1f2e3d4c5b6a"
        assert client.post("/api/export/drag", json={"token": "x", "tabs": []}).status_code == 400
        assert client.post("/api/export/drag", json={"token": tok, "title": "Speed A", "tabs": [{"name": "", "plots": [plot]}]}).json()["ok"]
        r = client.get(f"/api/export/drag/{tok}/Speed%20A.html")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
        assert "attachment" in r.headers["content-disposition"] and "Speed%20A.html" in r.headers["content-disposition"]
        assert 'id="sv-data"' in r.text and "<title>Speed A</title>" in r.text
        assert client.get("/api/export/drag/0b9e2c34-0000-0000-0000-000000000000/x.html").status_code == 404
    finally:
        client.delete(f"/api/runs/{run['id']}")


def test_copied_pictures_at_high_resolution(tmp_path):
    """CP7 (owner, 2026-11-22: "a copy as a high-resolution picture"): the plot drawn again at 2 / 3 times the pixels
    for the clipboard; the static copy's picture too."""
    import io
    from PIL import Image
    path = tmp_path / "s.csv"
    path.write_text("time,a\n" + "".join("%g,%g\n" % (i * 0.1, i % 5) for i in range(100)), encoding="utf-8")
    run = client.post("/api/files/open", json={"paths": [str(path)]}).json()["opened"][0]
    try:
        plot = {"mode": "time", "title": "A", "signals": [{"id": f"{run['id']}/a", "label": "a", "color": "#e33", "width": 1.5,
                                                         "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}
        w = {}
        for sc in (1, 2, 3):
            r = client.post("/api/export/image-bytes", json={"plot": plot, "scale": sc})
            assert r.status_code == 200 and r.headers["content-type"] == "image/png"
            w[sc] = Image.open(io.BytesIO(r.content)).size[0]
        assert w[2] == pytest.approx(2 * w[1], rel=0.02) and w[3] == pytest.approx(3 * w[1], rel=0.02)
        s1 = report_clip.build_clip_static(report_store(), {"tabs": [{"plots": [plot]}], "scale": 1})
        s2 = report_clip.build_clip_static(report_store(), {"tabs": [{"plots": [plot]}], "scale": 2})
        assert len(s2) > 1.5 * len(s1) and 'width="800"' in s2           # more pixels, the same size on the page
    finally:
        client.delete(f"/api/runs/{run['id']}")


def report_store():
    from app.store import store
    return store
