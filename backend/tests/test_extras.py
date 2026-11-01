"""T59: with `pip install signalviewer` (no extras) an optional reader or report says which
extra brings it, instead of a stack trace or "damaged file". The modules are hidden with
sys.modules[name] = None (import then raises ImportError, as when the package is missing)."""
import os

import pytest

from app.store import LoadError, Store

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


@pytest.fixture(autouse=True)
def lite(monkeypatch):
    """As installed with `pip install signalviewer-lite` (T62): the messages name its extras."""
    import svcore.extras as ex
    monkeypatch.setattr(ex, "_lite", lambda: True)


def test_full_install_or_source_says_reinstall(monkeypatch):
    import svcore.extras as ex
    monkeypatch.setattr(ex, "_lite", lambda: False)
    m = ex.missing("Reading Parquet", "parquet")
    assert "pip install signalviewer " in m and "requirements.txt" in m and "lite" not in m


def hide(monkeypatch, *mods):
    for m in mods:
        monkeypatch.setitem(__import__("sys").modules, m, None)


def test_parquet_names_its_extra(tmp_path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq
    p = tmp_path / "t.parquet"
    pq.write_table(pa.table({"time": [0.0, 1.0], "x": [1.0, 2.0]}), str(p))
    hide(monkeypatch, "pyarrow", "pyarrow.parquet")
    with pytest.raises(LoadError, match=r'signalviewer-lite\[parquet\]'):
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
    with pytest.raises(LoadError, match=r'signalviewer-lite\[mavlink\]'):
        Store().open_file(str(p))


def test_mat73_names_its_extra(tmp_path, monkeypatch):
    p = tmp_path / "v73.mat"
    p.write_bytes(b"MATLAB 7.3 MAT-file, Platform: GLNXA64" + b" " * 90 + b"\x00" * 512)
    hide(monkeypatch, "h5py")
    with pytest.raises(LoadError, match=r'signalviewer-lite\[hdf5\]'):
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
    with pytest.raises(report.ReportNeedsExtra, match=r'signalviewer-lite\[reports\]'):
        report.build_docx(st, body, str(tmp_path / "r.docx"))
    with pytest.raises(report.ReportNeedsExtra, match=r'signalviewer-lite\[reports\]'):
        report.build_pdf(st, body, str(tmp_path / "r.pdf"))
    assert "<html" in report.build_html(st, body).lower()         # HTML of time plots needs neither


def test_extras_cover_requirements():
    """Every package extras.py names is in requirements.txt (the full install keeps everything)."""
    from svcore.extras import EXTRAS
    import re
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    req = "".join(open(os.path.join(root, f), encoding="utf-8").read() for f in ("requirements.txt",))
    names = {re.split(r"[<>=!~ ]", line.split("#")[0].strip())[0] for line in req.splitlines() if line.split("#")[0].strip()}
    assert {p for ps in EXTRAS.values() for p in ps} <= names


def test_scikit_learn_in_the_full_package_an_extra_in_lite():
    """Owner's choice 2026-11-01: Kriging in every full install; lite keeps it as the extra sweeps-opt."""
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "make_pypi.py")
    spec = importlib.util.spec_from_file_location("make_pypi", path)
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    req, extra = mp.requirements()
    assert extra["sweeps-opt"][0].startswith("scikit-learn")
    deps, opt = mp.flavour_metadata("signalviewer", req, extra)
    assert "scikit-learn>=1.3" in deps and "sweeps-opt" not in opt
    deps, opt = mp.flavour_metadata("signalviewer-lite", req, extra)
    assert not any(d.startswith("scikit-learn") for d in deps) and "scikit-learn>=1.3" in opt["sweeps-opt"]
