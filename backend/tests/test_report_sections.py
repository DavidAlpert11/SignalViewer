"""Investigation step 6: text sections in reports (findings, analysis steps, conditions, how to
reproduce) in HTML, PDF and Word."""

from app.report import _section_lines, _sections_html, build_html
from app.store import Store

SECS = [{"title": "Findings", "text": "Two of them.", "table": {"head": ["When", "What", "Status"], "rows": [["38.5 s", "Motor 3 at its limit <b>", "fault"]]}},
        {"title": "Steps", "items": ["Condition Roll error: 3 stretches", "Wind first, then Vibe_Z"]}]


def test_html_sections_escape_and_order():
    h = _sections_html(SECS)
    assert h.index("Findings") < h.index("Steps") and "&lt;b&gt;" in h and "<li>Wind first" in h
    lines = _section_lines(SECS[0])
    assert lines[0] == "Two of them." and lines[-1].startswith("38.5 s | Motor 3")


def test_report_carries_the_sections(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("Time,A\n0,1\n1,2\n2,3\n")
    st = Store()
    rid = st.open_file(str(p)).id
    req = {"title": "T", "lang": "en", "sections": SECS, "notes": [], "tabs": [{"name": "Tab", "plots": [
        {"title": "", "caption": "", "mode": "time", "range": None, "signals": [{"id": f"{rid}/A", "label": "A", "color": "#000", "width": 1, "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}]}]}
    assert "Motor 3 at its limit" in build_html(st, req)
    from app.report import build_pdf
    build_pdf(st, req, str(tmp_path / "r.pdf"))
    assert (tmp_path / "r.pdf").stat().st_size > 1000
    try:
        from app.report import build_docx
        build_docx(st, req, str(tmp_path / "r.docx"))
    except Exception as e:                       # python-docx is optional
        if "Word" not in str(e):
            raise
