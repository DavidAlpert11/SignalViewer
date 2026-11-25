"""RE2: the report's ready-made parts - each finds its signals by name, computes on every sample, and writes Markdown
that the page, the PDF and Word draw like any other text. The numbers are checked on signals whose answers are
known; the demo recordings (examples/report_demo) are checked end to end."""
import json
import os

import numpy as np
import pandas as pd
import pytest

from app.reportdoc import build_doc_docx, build_doc_html, build_doc_pdf, resolve
from app.reportparts import expand_all, options, PartError, scan
from app.store import Store
from svcore import reportparts as rp

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, "..", "..", "examples", "report_demo")


def test_the_shared_pair_cases():
    cases = json.load(open(os.path.join(HERE, "data", "setpoint_cases.json"), encoding="utf-8"))["cases"]
    for c in cases:
        got = [[p["setpoint"][2:], p["measured"][2:]] for p in rp.setpoint_pairs(["a/" + n for n in c["names"]])]
        assert got == c["pairs"], c["why"]
    assert rp.setpoint_pairs(["a/ATT.DesRoll", "b/ATT.Roll"]) == []          # never across files


def test_tracking_a_known_step_response():
    # a first-order follower (tau 0.5 s) of a 0 -> 10 step at 5 s, delayed by 0.2 s: no overshoot, settles in about
    # 3 tau = 1.5 s (5 %) after the delay; the error's largest is the step itself, at the step
    t = np.arange(0, 20, 0.001)
    cmd = np.where(t >= 5, 10.0, 0.0)
    y = np.where(t >= 5.2, 10 * (1 - np.exp(-(t - 5.2) / 0.5)), 0.0)
    r = rp.tracking((t, cmd), (t, y), "x", tol=1.0)
    assert r["steps"] == 1 and r["overshoot"] == pytest.approx(0, abs=0.01)
    assert r["settling"] == pytest.approx(0.2 + 0.5 * np.log(20), abs=0.02)
    assert r["max"] == pytest.approx(10, abs=0.01) and r["tmax"] == pytest.approx(5.0, abs=0.002)
    assert r["outside"] == pytest.approx((0.2 + 0.5 * np.log(10)) / 20 * 100, abs=0.05)
    # an overshoot of 20 %: a second-order response, zeta from 20 % = exp(-pi z / sqrt(1 - z^2))
    z = -np.log(0.2) / np.sqrt(np.pi ** 2 + np.log(0.2) ** 2)
    wn = 4.0
    wd = wn * np.sqrt(1 - z * z)
    s = np.clip(t - 5, 0, None)
    y2 = np.where(t >= 5, 10 * (1 - np.exp(-z * wn * s) * (np.cos(wd * s) + z / np.sqrt(1 - z * z) * np.sin(wd * s))), 0.0)
    assert rp.tracking((t, cmd), (t, y2), "x")["overshoot"] == pytest.approx(20, abs=0.3)


def test_the_needle_is_the_reported_maximum():
    # one sample in two million: the error's maximum, never a thinned line's
    t = np.arange(2_000_000) * 0.001
    cmd = np.sin(t / 50)
    y = cmd.copy()
    y[1_234_567] += 42.0
    r = rp.tracking((t, cmd), (t, y), "x")
    assert r["max"] == pytest.approx(42.0) and r["tmax"] == pytest.approx(1234.567)


def test_a_difference_in_one_region_is_found_there():
    t = np.arange(0, 100, 0.01)
    a = np.sin(t / 3)
    b = a.copy()
    m = (t >= 40) & (t < 50)
    b[m] += 0.5 * np.sin((t[m] - 40) / 10 * np.pi)
    d = rp.difference((t, a), (t, b), "x")
    assert d["region"][0] == pytest.approx(40, abs=2) and d["region"][1] == pytest.approx(50, abs=2)
    assert d["first"] == pytest.approx(40, abs=1.0)
    assert d["peak"] > 4 * d["overall"]                       # mostly the same, one region different
    assert rp.level(d) == "large"
    same = rp.difference((t, a), (t, a + 1e-6), "x")
    assert rp.level(same) == "same" and same["first"] is None
    reg = rp.region([dict(d, name="x")])
    assert reg["a"] == pytest.approx(40, abs=3) and reg["b"] == pytest.approx(50, abs=3) and reg["firstName"] == "x"


def test_options_are_checked():
    assert options("tracking", ["top 3", "tol 2", "outside 1%", "skip yaw", "table"]) == {"top": 3, "tol": 2.0, "outside": 0.01, "skip": ["yaw"], "table": True}
    assert options("navigation", ["ref GPS", "position"]) == {"ref": "GPS", "what": ["position"]}
    with pytest.raises(PartError):
        options("tracking", ["bogus"])


@pytest.fixture(scope="module")
def demo():
    s = Store()
    a = s.open_file(os.path.join(DEMO, "mission_ref.csv")).id
    b = s.open_file(os.path.join(DEMO, "mission_gust.csv")).id
    return s, a, b


def parts(s, runs, *names, lang="en", opts=None):
    items = [{"kind": "part", "part": n, "arg": "", "opts": (opts or {}).get(n, []), "runs": runs} for n in names]
    text = "\n\n".join("⟦%d⟧" % k for k in range(len(items)))
    out, extra = expand_all(s, text, items, lang)
    return out, items, extra


def test_the_demo_is_found(demo):
    s, a, b = demo
    sc = scan(s, [a])
    assert {(p["setpoint"], p["measured"]) for p in sc["pairs"]} == {
        ("ctrl.alt_cmd [m]", "ctrl.alt [m]"), ("ctrl.speed_cmd [m/s]", "ctrl.speed [m/s]"),
        ("ctrl.roll_cmd [deg]", "ctrl.roll [deg]"), ("ctrl.pitch_cmd [deg]", "ctrl.pitch [deg]")}
    assert {o["name"] for o in sc["objects"]} == {"sim", "nav", "gps"} and sc["reference"] == "sim"
    assert [x["name"] for x in sc["states"]][0] == "mission.phase"


def test_the_demo_differences_point_at_the_gust(demo):
    s, a, b = demo
    md, items, _ = parts(s, [a, b], "differences")
    assert "The central region of the change: 14" in md                # 140-171 s: the gust and the lost receiver
    assert "First to diverge: **sim.att.roll [deg]** at 140.9 s" in md
    assert "gps.status - mission_ref.csv: OK; mission_gust.csv: OK → LOST → OK" in md
    plots = [it for it in items if it.get("kind") == "plots"]
    zoom = [p["plots"][0] for p in plots if p["plots"][0].get("range")]
    assert zoom and all(140 - 30 <= p["range"][0] and p["range"][1] <= 171 + 30 for p in zoom)


def test_the_demo_parts_in_hebrew_and_the_summary_first(demo):
    s, a, b = demo
    md, items, _ = parts(s, [a, b], "summary", "tracking", "navigation", "states", "trajectory", "moments", "differences", lang="he")
    assert md.index("על מה להסתכל") < md.index("זוגות פקודה / ביצוע")
    assert "| mission_gust.csv | ctrl.roll_cmd | ctrl.roll |" in md and "שגיאות ניווט מול mission_ref.csv: sim" in md
    assert "TAKEOFF" in md and "gps.status: OK → LOST" in md          # the moments: a state change of the receiver
    assert not [it for it in items if it.get("kind") == "error"]


def test_a_part_that_finds_nothing_says_so_and_a_bad_option_says_why(demo):
    s, a, b = demo
    md, items, _ = parts(s, [a], "differences")
    assert "One file is open" in md
    md, items, _ = parts(s, [a], "tracking", opts={"tracking": ["bogus"]})
    assert items[0]["kind"] == "error" and '"bogus"' in items[0]["error"] and "top N" in items[0]["error"]
    md, items, _ = parts(s, [a], "navigation", opts={"navigation": ["ref nothing"]})
    assert items[0]["kind"] == "error" and "nothing" in items[0]["error"]


def test_the_parts_go_into_every_format(demo, tmp_path):
    s, a, b = demo
    items = [{"kind": "part", "part": n, "arg": "", "opts": [], "runs": [a, b]} for n in ("summary", "tracking", "differences")]
    req = {"text": "# Demo\n\n⟦0⟧\n\n## Tracking\n\n⟦1⟧\n\n## Files\n\n⟦2⟧", "items": items, "lang": "en"}
    page = build_doc_html(s, dict(req))
    assert "What to look at" in page and "The central region of the change" in page and page.count('class="plot') >= 3
    build_doc_pdf(s, dict(req), str(tmp_path / "r.pdf"))
    build_doc_docx(s, dict(req), str(tmp_path / "r.docx"))
    assert (tmp_path / "r.pdf").stat().st_size > 20000 and (tmp_path / "r.docx").stat().st_size > 20000


def test_a_picture_kept_in_the_session(demo, tmp_path):
    import base64
    import io
    import zipfile
    from PIL import Image
    s, a, b = demo
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), (200, 30, 30)).save(buf, "PNG")
    data = base64.b64encode(buf.getvalue()).decode()
    req = {"text": "# Pictures\n\n![the rig](asset:ab12)\n\nafter", "items": [], "lang": "en",
           "assets": {"ab12": {"name": "rig", "mime": "image/png", "data": data, "w": 40, "h": 20}}}
    assert "data:image/png;base64," + data[:20] in build_doc_html(s, dict(req))
    build_doc_docx(s, dict(req), str(tmp_path / "p.docx"))
    with zipfile.ZipFile(tmp_path / "p.docx") as z:
        assert any(n.startswith("word/media/") for n in z.namelist())
    build_doc_pdf(s, dict(req), str(tmp_path / "p.pdf"))
    assert (tmp_path / "p.pdf").stat().st_size > 1000


def test_a_long_appendix_table_goes_on_over_pages(tmp_path):
    s = Store()
    req = {"text": "# Long\n\n" + "| a | b |\n|---|---|\n" + "\n".join("| %d | x |" % i for i in range(150)), "items": [], "lang": "en"}
    build_doc_pdf(s, req, str(tmp_path / "long.pdf"))
    from pypdf import PdfReader
    assert len(PdfReader(str(tmp_path / "long.pdf")).pages) >= 3


def test_the_overview_fits_any_recording(tmp_path):
    # not a flight log: a bench run with a needle, missing values and a text state - the overview finds them all
    t = np.arange(0, 100, 0.01)
    pressure = np.sin(t)
    pressure[7777] = 99.0
    temp = 20 + t / 10
    temp[100:150] = np.nan
    pd.DataFrame({"Time": t, "Pressure": pressure, "Temp": temp, "Valve": np.where(t < 50, "OPEN", "SHUT")}).to_csv(tmp_path / "bench.csv", index=False)
    s = Store()
    rid = s.open_file(str(tmp_path / "bench.csv")).id
    md, items, _ = parts(s, [rid], "overview", "summary")
    assert "**bench.csv** - 3 signals" in md and "about 100 samples a second" in md
    assert "| Pressure | -1 | 99 |" in md and "| 77.8 |" in md                 # the needle, on every sample
    assert "Temp (missing values)" in md and "Valve (2)" in md
    assert "data-quality problems" in md                                     # in What to look at
    assert sum(1 for it in items if it.get("kind") == "plots") == 2         # Pressure and Temp, one plot each


def test_what_to_look_at_puts_a_flag_before_changes_of_state(tmp_path):
    # review 2026-11-25 (C11): a log's boot messages (changes of a text state) filled What to look at, ahead of the
    # recording's own flags; a change of state is a moment, a signal flat at its limit is something to look at
    t = np.arange(0, 60, 0.01)
    motor = 1500 + 300 * np.sin(t)
    motor[2000:2600] = 2000.0                                                   # flat at its limit for 6 s
    msgs = np.array(["boot %d" % min(int(x // 5), 9) for x in t])            # ten changes of a text state
    pd.DataFrame({"Time": t, "Motor": motor, "Message": msgs}).to_csv(tmp_path / "run.csv", index=False)
    s = Store()
    rid = s.open_file(str(tmp_path / "run.csv")).id
    md, _, _ = parts(s, [rid], "moments", "summary")
    look = md[md.index("What to look at"):].split("\n\n")[1]
    assert "Motor" in look.splitlines()[0]                                     # the flag first
    assert "boot" not in look                                                  # the changes of state: not "to look at"
    assert "boot 3" in md                                                      # but still moments in the table
