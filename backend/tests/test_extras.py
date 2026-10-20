"""T59: with `pip install signalviewer` (no extras) an optional reader or report says which
extra brings it, instead of a stack trace or "damaged file". The modules are hidden with
sys.modules[name] = None (import then raises ImportError, as when the package is missing)."""
import os

import pytest

from app.store import LoadError, Store

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def hide(monkeypatch, *mods):
    for m in mods:
        monkeypatch.setitem(__import__("sys").modules, m, None)


def test_parquet_names_its_extra(tmp_path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq
    p = tmp_path / "t.parquet"
    pq.write_table(pa.table({"time": [0.0, 1.0], "x": [1.0, 2.0]}), str(p))
    hide(monkeypatch, "pyarrow", "pyarrow.parquet")
    with pytest.raises(LoadError, match=r'signalviewer\[parquet\]'):
        Store().open_file(str(p))


def test_tlog_names_its_extra(tmp_path, monkeypatch):
    import subprocess
    import sys
    import svcore.tlog_loader as tl
    p = tmp_path / "t.tlog"
    tool = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "make_test_tlog.py")
    subprocess.run([sys.executable, tool, str(p), "--seconds", "2"], check=True, capture_output=True)
    monkeypatch.setattr(tl, "_MAV", None)
    hide(monkeypatch, "pymavlink", "pymavlink.dialects", "pymavlink.dialects.v20",
         "pymavlink.dialects.v20.ardupilotmega")
    with pytest.raises(LoadError, match=r'signalviewer\[mavlink\]'):
        Store().open_file(str(p))


def test_mat73_names_its_extra(tmp_path, monkeypatch):
    p = tmp_path / "v73.mat"
    p.write_bytes(b"MATLAB 7.3 MAT-file, Platform: GLNXA64" + b" " * 90 + b"\x00" * 512)
    hide(monkeypatch, "h5py")
    with pytest.raises(LoadError, match=r'signalviewer\[hdf5\]'):
        Store().open_file(str(p))


def test_reports_name_their_extra(tmp_path, monkeypatch):
    from app import report
    hide(monkeypatch, "docx", "matplotlib", "matplotlib.pyplot")
    st = Store()
    lr = st.open_file(os.path.join(EX, "run_012.csv"))
    body = {"title": "t", "lang": "en", "theme": "light", "notes": [], "intro": "", "summary": "",
            "tabs": [{"name": "A", "plots": [{"title": "", "caption": "", "mode": "time", "xSignal": None, "xLabel": "",
                      "range": None, "signals": [{"id": f"{lr.id}/RPM", "label": "RPM", "color": "#3D8BFD", "width": 1.5,
                                                  "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}]}]}
    with pytest.raises(report.ReportNeedsExtra, match=r'signalviewer\[reports\]'):
        report.build_docx(st, body, str(tmp_path / "r.docx"))
    with pytest.raises(report.ReportNeedsExtra, match=r'signalviewer\[reports\]'):
        report.build_pdf(st, body, str(tmp_path / "r.pdf"))
    assert "<html" in report.build_html(st, body).lower()         # HTML of time plots needs neither


def test_extras_cover_requirements():
    """Every package extras.py names is in requirements.txt (the full install keeps everything)."""
    from svcore.extras import EXTRAS
    import re
    req = open(os.path.join(os.path.dirname(__file__), "..", "..", "requirements.txt"), encoding="utf-8").read()
    names = {re.split(r"[<>=!~ ]", line.split("#")[0].strip())[0] for line in req.splitlines() if line.split("#")[0].strip()}
    assert {p for ps in EXTRAS.values() for p in ps} <= names
