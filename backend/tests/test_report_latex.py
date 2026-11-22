"""RE3: the report in LaTeX - a Markdown report written as a LaTeX project (.zip for Overleaf: main.tex, figures/ with
the plots as vector PDF, latexmkrc), typeset by this computer's LaTeX when it has one; a report written as a LaTeX
document (\\documentclass first) with [[plots]] and {{values}} in it, TeX's errors said at the line of the text; a
formula matplotlib cannot read drawn by TeX in the page. Every value on every sample, as in the other outputs."""
import zipfile

import numpy as np
import pytest

from app import reportlatex as RL
from app.reportdoc import build_doc, build_doc_html
from app.store import Store
from svcore import latex as TX

HAVE_TEX = bool(TX.best_engine())
tex = pytest.mark.skipif(not HAVE_TEX, reason="no LaTeX on this computer")


@pytest.fixture()
def st(tmp_path):
    n = 200_000
    t = np.arange(n) * 0.001
    roll = np.sin(t)
    roll[123_456] = 42.0                                     # one sample: the value must find it
    p = tmp_path / "flight.csv"
    np.savetxt(p, np.c_[t, roll], delimiter=",", header="Time,Roll", comments="", fmt="%.6f")
    s = Store()
    s.rid = s.open_file(str(p)).id
    return s


def items(rid):
    plot = {"title": "Roll & pitch_1", "caption": "50% of it", "mode": "time", "range": None,
            "signals": [{"id": f"{rid}/Roll", "label": "Roll", "color": "#3D8BFD", "width": 1.5, "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}
    return [{"kind": "value", "expr": "max(v0)", "sources": [f"{rid}/Roll"], "fmt": ".1f", "src": "max(Roll)"},
            {"kind": "plots", "plots": [plot], "tab": "T"}]


MD = """# Flight #12 & co

Roll peaked at **⟦0⟧ deg** - 100% $x_1^2$ under_score.

⟦1⟧

| a | b |
|---|--:|
| 1_x | $\\alpha$ |

> [!WARNING]
> careful

```latex
\\begin{tabular}{|l|r|}\\hline a & 1\\\\ \\hline\\end{tabular}
```

$$\\begin{align} a &= b \\\\ c &= d \\end{align}$$
"""


def test_markdown_to_a_latex_project_zip(st, tmp_path):
    z = tmp_path / "r.zip"
    build_doc(st, {"text": MD, "items": items(st.rid), "lang": "en", "words": {"calloutWARNING": "Warning"}}, "tex", str(z))
    with zipfile.ZipFile(z) as f:
        names = f.namelist()
        main = f.read("main.tex").decode("utf-8")
        assert "$pdf_mode = 5;" in f.read("latexmkrc").decode()          # XeLaTeX on Overleaf too
    assert any(n.startswith("figures/plot-") and n.endswith(".pdf") for n in names)
    assert "Flight \\#12 \\& co" in main and "\\textbf{42.0 deg}" in main  # escaped; the value on every sample
    assert "100\\% $x_1^2$ under\\_score" in main                         # text escaped, math as written
    assert "\\begin{tabular}{|l|r|}" in main and "\\begin{align} a &= b" in main   # LaTeX as written
    assert "\\begin{longtable}{lr}" in main and "1\\_x & $\\alpha$" in main
    assert "\\begin{svcallout}" in main and "\\caption{Roll \\& pitch\\_1 --- 50\\% of it}" in main
    assert "polyglossia" not in main                                     # no Hebrew: no bidi needed


def test_hebrew_report_marks_the_english_words():
    out = RL.to_latex("# דוח טיסה\n\nהגלגול Roll היה ⟦0⟧.", "he", {})
    assert "\\setdefaultlanguage{hebrew}" in out and "\\IfFontExistsTF{David CLM}" in out
    assert "⟦0⟧" in out                                                   # the page puts its reference back
    ctx = RL.Ctx("", "he", "xelatex", RL.R.STRINGS["he"], {})
    ctx.bidi = True
    assert ctx.text("הגלגול Roll rate היה") == "הגלגול \\textenglish{Roll rate} היה"


def test_latex_document_detected_and_converted():
    assert RL.is_latex_doc("% notes\n\\documentclass{article}\n") and not RL.is_latex_doc("# A\n\\documentclass")
    doc = RL.to_latex("# T\n\n## Part\n\n- a\n- b\n\n⟦3⟧\n\nx ⟦4⟧ y\n\n![p](asset:abc)\n", "en", {})
    assert doc.startswith("% Made by Signal Viewer") and RL.is_latex_doc(doc)
    assert "\\section{Part}" in doc and "\\begin{itemize}" in doc and "\n⟦3⟧\n" in doc and "x ⟦4⟧ y" in doc
    assert "\\includegraphics[width=\\linewidth]{asset:abc}" in doc


@tex
def test_typeset_by_latex_and_errors_at_the_line(st, tmp_path):
    pdf = tmp_path / "r.pdf"
    build_doc(st, {"text": MD, "items": items(st.rid), "lang": "en"}, "texpdf", str(pdf))
    assert pdf.read_bytes()[:5] == b"%PDF-" and pdf.stat().st_size > 5000
    doc = "\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}\nMax: ⟦0⟧.\n\n⟦1⟧\n\n\\textbf{oops\n\\end{document}\n"
    r = RL.preview(st, {"text": doc, "items": items(st.rid), "lang": "en"})
    assert r["pdf"] is None and r["line"] is not None and r["line"] >= 7 and "Line" in r["error"]
    ok = RL.preview(st, {"text": doc.replace("\\textbf{oops\n", "fine\n"), "items": items(st.rid), "lang": "en"})
    assert ok["error"] is None and open(RL.preview_pdf(ok["pdf"]), "rb").read(5) == b"%PDF-"


@tex
def test_a_formula_mathtext_cannot_read_is_drawn_by_tex(st):
    if not TX.status()["snippets"]:
        pytest.skip("nothing to turn TeX's output into a picture")
    page = build_doc_html(st, {"text": "$$\\begin{pmatrix}1&0\\\\0&1\\end{pmatrix}$$\n\n```latex\n\\fbox{boxed}\n```\n", "items": []})
    assert page.count('class="math tex') == 2 and 'class="field-err"' not in page


# ---- RE4: the app's built-in LaTeX (Tectonic + its small bundle) and MathML when there is no TeX at all

def _no_system_tex(monkeypatch):
    from app import reportdoc
    monkeypatch.setattr(reportdoc, "_math_cache", {})               # formulas drawn earlier by the computer's TeX
    monkeypatch.setattr(TX, "_cache", {})
    for e in TX.ENGINES + ("latex", "latexmk", "dvisvgm", "dvipng", "pdftoppm", "gs", "gswin64c", "mgs"):
        monkeypatch.setitem(TX._found, e, None)


builtin = pytest.mark.skipif(not TX.builtin(), reason="no built-in LaTeX here (tools/get_tectonic.py, tools/make_tex_bundle.py)")


@builtin
def test_builtin_tectonic_typesets_offline(st, tmp_path, monkeypatch):
    _no_system_tex(monkeypatch)
    monkeypatch.setenv("TECTONIC_CACHE_DIR", str(tmp_path / "cache"))
    assert TX.best_engine() == "tectonic" and TX.status()["builtin"]
    pdf = tmp_path / "r.pdf"
    build_doc(st, {"text": MD, "items": items(st.rid), "lang": "en"}, "texpdf", str(pdf))
    assert pdf.read_bytes()[:5] == b"%PDF-"
    doc = "\\documentclass[12pt]{report}\n\\usepackage{tikz,siunitx}\n\\begin{document}\nMax ⟦0⟧ \\SI{3}{\\metre}.\n\n⟦1⟧\n\n\\undefinedthing\n\\end{document}\n"
    r = RL.preview(st, {"text": doc, "items": items(st.rid), "lang": "en"})
    assert r["pdf"] is None and r["line"] == 8 and "Undefined control sequence" in r["error"]
    r = RL.preview(st, {"text": doc.replace("\\undefinedthing\n", ""), "items": items(st.rid), "lang": "en"})
    assert r["error"] is None and r["engine"] == "tectonic"
    r = RL.preview(st, {"text": "\\documentclass{article}\n\\usepackage{nosuchpkg}\n\\begin{document}x\\end{document}\n", "items": [], "lang": "en"})
    assert "not in the app's built-in LaTeX" in r["error"] and "nosuchpkg.sty" in r["error"]


def test_no_tex_at_all_formulas_as_mathml(monkeypatch):
    _no_system_tex(monkeypatch)
    from app.reportdoc import _aligned_as_array, mathml
    page = build_doc_html(Store(), {"text": "$$\\begin{pmatrix}1&0\\\\0&1\\end{pmatrix}$$\n\n$$\\begin{align} a&=b\\\\c&=d\\end{align}$$\n", "items": []})
    assert page.count('class="math mathml"') == 2 and 'class="field-err"' not in page
    assert _aligned_as_array("\\begin{align} a&=b\\\\c&=d\\end{align}") == "\\begin{array}{rl}a&=b\\\\c&=d\\end{array}"
    assert "<mtable>" in mathml("\\begin{aligned}a&=1\\\\b&=2\\end{aligned}", True)
