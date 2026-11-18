"""RE1: the report the user writes - Markdown with plots and values. The values are computed on every sample
(a needle in five million is found), formulas / conditions / variables work, a bad field says why and never
stops the rest; the same document makes the page, a PDF and a Word file."""
import zipfile

import numpy as np
import pytest

from app.reportdoc import build_doc_docx, build_doc_html, build_doc_pdf, parse, parse_inline, resolve
from app.store import Store
from svcore.docfields import format_value


@pytest.fixture()
def st(tmp_path):
    n = 5_000_000
    t = np.arange(n) * 0.001
    roll = np.sin(t / 10.0)
    roll[3_333_333] = 42.0                                  # the needle: one sample in five million
    des = np.zeros(n)
    mode = (t > 1000).astype(float)                         # "Auto" from 1000 s on
    p = tmp_path / "flight.parquet"
    import pandas as pd
    pd.DataFrame({"Time": t, "Roll": roll, "RollDes": des, "Mode": mode}).to_parquet(p)
    s = Store()
    s.rid = s.open_file(str(p)).id
    return s


def val(expr, sources, **kw):
    return {"kind": "value", "expr": expr, "sources": sources, **kw}


def plot_spec(rid):
    return {"title": "Roll", "caption": "the roll", "mode": "time", "range": None,
            "signals": [{"id": f"{rid}/Roll", "label": "Roll", "color": "#3D8BFD", "width": 1.5, "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}


def test_values_on_all_the_data(st):
    r = f"{st.rid}/Roll"
    req = {"text": "max ⟦0⟧ at ⟦1⟧ s; rms of the error while auto ⟦2⟧; ⟦3⟧⟦4⟧; n=⟦5⟧ held ⟦6⟧ s; ⟦7⟧",
           "items": [val("max(v0)", [r]), val("tmax(v0)", [r]),
                     val('rms(v0 - v1, when="Auto")', [r, f"{st.rid}/RollDes"], conds={"Auto": {"text": "{Mode} > 0.5"}}),
                     val("max(v0, 0, 100)", [r], assign="early"), val("early * 2", [], fmt=".2f"),
                     val('stretches("Auto")', []), val('holds("Auto", v0)', [r], conds={}), val("nope(v0)", [r])]}
    req["items"][5]["conds"] = req["items"][6]["conds"] = {"Auto": {"text": "{Mode} > 0.5"}}
    _, items = resolve(st, req)
    assert items[0]["text"] == "42"                         # every sample, not a decimated line
    assert items[1]["value"] == pytest.approx(3333.333, abs=1e-3) and items[1]["text"] == "3333"
    t = np.arange(5_000_000) * 0.001
    roll = np.sin(t / 10.0); roll[3_333_333] = 42.0
    m = t > 1000
    assert items[2]["value"] == pytest.approx(np.sqrt(np.mean(roll[m] ** 2)), rel=1e-3)
    assert items[3]["text"] == "" and items[4]["text"] == "2.00"                # max over 0..100 s is 1
    assert items[5]["text"] == "1" and items[6]["value"] == pytest.approx(4000.0 - 0.001, abs=0.01)
    assert "Unknown function nope()" in items[7]["error"]


def test_field_errors_are_words(st):
    r = f"{st.rid}/Roll"
    _, items = resolve(st, {"text": "", "items": [
        val("v0", [r], names={"v0": "Roll"}), val("max(v0)", ["zz/Roll"]), val("peak", []), val('mean(v0, when="X")', [r]),
        val("max(v0, 10)", [r]), val("max(v0) :.2f", [r])]})
    assert "take one: max(Roll)" in items[0]["error"]
    assert "not open" in items[1]["error"]
    assert 'Define it first' in items[2]["error"]
    assert 'no condition named "X"' in items[3]["error"]
    assert "time window" in items[4]["error"]
    assert items[5].get("error")


def test_format_value():
    assert format_value(12.3456) == "12.35" and format_value(0.012345) == "0.01235" and format_value(123456.7) == "123457"
    assert format_value(5_000_000) == "5,000,000" and format_value(3.0) == "3" and format_value(1e-7) == "1e-07"
    assert format_value(2.5, ".1f") == "2.5"


def test_markdown_subset():
    b = parse("# T\n\nA **b** and *i*\nnext\n\n- one\n  - two\n1. three\n\n| a | b |\n|---|--:|\n| 1 | 2 |\n\n"
              "> [!WARNING] careful\n> more\n\n```\ncode *x*\n```\n$$x^2$$\n---\n\\newpage\n⟦0⟧")
    kinds = [x["t"] for x in b]
    assert kinds == ["heading", "para", "list", "list", "table", "quote", "code", "math", "hr", "pagebreak", "para"]
    assert b[1]["text"] == "A **b** and *i* next" and b[2]["items"][1]["depth"] == 1
    assert b[4]["align"] == ["", "right"] and b[5]["kind"] == "WARNING"
    nodes = parse_inline("x **b** *i* `c` $a_1$ [l](http://x) ⟦3⟧ snake_case_name 5$")
    assert [n[0] for n in nodes if n[0] != "text"] == ["b", "i", "code", "math", "link", "field"]
    assert "snake_case_name 5$" in nodes[-1][1]


def test_the_page_pdf_and_word(st, tmp_path):
    r = f"{st.rid}/Roll"
    text = ("# דוח טיסה 12\n\nהגלגול הגיע ל-⟦0⟧ מעלות.\n\n⟦1⟧\n\n⟦2⟧\n\n## Math\n$$\\omega = \\sqrt{k/m}$$\n\n"
            "| what | value |\n|---|---|\n| max | ⟦0⟧ |\n\n> [!FINDING] a finding\n\n⟦3⟧\n\n⟦4⟧")
    req = {"text": text, "lang": "he", "words": {"calloutFINDING": "ממצא"}, "items": [
        val("max(v0)", [r]), {"kind": "plots", "plots": [plot_spec(st.rid)]},
        {"kind": "plots", "plots": [plot_spec(st.rid)], "table": "only"},
        {"kind": "notes", "notes": [{"t": 12.5, "text": "gust"}]}, {"kind": "error", "error": "There is no tab Nav."}]}
    page = build_doc_html(st, req)
    assert "<title>דוח טיסה 12</title>" in page and '<span class="val"' in page and ">42<" in page
    assert page.count('class="plot"') == 1 and "tableonly" in page and "gust" in page and "There is no tab Nav." in page
    assert '<svg class="math"' in page and "ממצא" in page
    build_doc_pdf(st, req, str(tmp_path / "r.pdf"))
    assert (tmp_path / "r.pdf").stat().st_size > 5000
    build_doc_docx(st, req, str(tmp_path / "r.docx"))
    xml = zipfile.ZipFile(tmp_path / "r.docx").read("word/document.xml").decode()
    assert "42" in xml and "gust" in xml and "w:bidi" in xml and len(zipfile.ZipFile(tmp_path / "r.docx").namelist()) > 5


def test_markup_is_escaped(st):
    page = build_doc_html(st, {"text": "<script>alert(1)</script> [x](javascript:alert(1))", "items": []})
    assert "<script>alert(1)" not in page and "javascript:" not in page


def test_a_plot_whose_signals_are_not_open_is_said(st):
    spec = plot_spec(st.rid)
    spec["signals"][0]["id"] = "gone/Roll"                           # a session being reopened: the file not back yet
    page = build_doc_html(st, {"text": "⟦0⟧", "items": [{"kind": "plots", "plots": [spec]}]})
    assert "its signals are not open" in page and 'class="plot"' not in page


def test_hebrew_is_ordered_once(monkeypatch):
    """Matplotlib with libraqm (3.11+) orders Hebrew itself: reordering it again printed every Hebrew line of
    the PDF reports backwards."""
    import app.report as R
    monkeypatch.setattr(R, "_NATIVE_BIDI", True)
    assert R._bidi("דוח 12") == "דוח 12"
    monkeypatch.setattr(R, "_NATIVE_BIDI", False)
    pytest.importorskip("bidi")
    assert R._bidi("דוח 12") != "דוח 12"
