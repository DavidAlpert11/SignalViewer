"""W17: Launcher mode (svcore/launcher.py, svcore/placeholders.py, `study submit / wait / loop`,
tools/launcher_mock.py): the placeholder engine, the submit runner (no shell), results found by run_id and by
values, failure markers, the timeout, local_workers, many small result files, and the drone example converging
through the mock launcher with `study loop`."""
import json
import os
import shutil
import sys
import time

import pandas as pd
import pytest

from signalviewer.study import main as study_cli
from svcore import launcher as L
from svcore import placeholders as ph
from svcore import study as S
from svcore import sweeps_common as C
from svcore import sweeps_next as N

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MOCK = os.path.join(ROOT, "tools", "launcher_mock.py")
sys.path.insert(0, os.path.dirname(__file__))
from test_sweeps_next import _fine_optimum, _study  # noqa: E402


# ------------------------------------------------------------------ placeholders

def test_xml_and_json_escaping_and_raw():
    v = {"name": 'a<b & "c"', "Kp": 1.5, "n": 3, "on": True}
    assert ph.render("<p n='{{name}}'>{{ Kp }}</p>", v, "xml") == "<p n='a&lt;b &amp; &quot;c&quot;'>1.5</p>"
    assert json.loads(ph.render('{"name": "{{name}}", "Kp": {{Kp}}, "n": {{n}}, "on": {{on}}}', v, "json")) == \
        {"name": 'a<b & "c"', "Kp": 1.5, "n": 3, "on": True}
    assert ph.render("Kp={{Kp}} name={{name}}", v, "raw") == 'Kp=1.5 name=a<b & "c"'
    assert ph.fmt_for("x.XML") == "xml" and ph.fmt_for("p.json") == "json" and ph.fmt_for("p.ini") == "raw"
    with pytest.raises(ph.PlaceholderError, match="nan cannot be written"):
        ph.render("{{x}}", {"x": float("nan")}, "json")


def test_an_unknown_placeholder_is_named():
    with pytest.raises(ph.PlaceholderError) as e:
        ph.render("<Kp>{{Kp}}</Kp><Kq>{{ Kq }}</Kq>", {"Kp": 1}, "xml", "table A")
    assert "{{Kq}}" in str(e.value) and "table A" in str(e.value) and "Kp" in str(e.value)


def test_a_list_placeholder_becomes_several_arguments():
    args = ph.render_args(["{{study_cli}}", "demo-sim", "{{params_file}}", "--tag=r{{round}}"],
                          {"params_file": "a b;c.json", "round": 2}, {"study_cli": ["py", "-m", "x"]})
    assert args == ["py", "-m", "x", "demo-sim", "a b;c.json", "--tag=r2"]


# ------------------------------------------------------------------ a study with a launcher block

def _launcher_study(tmp, submit, mode="round", template=None, per_table=None, **extra):
    path = _study(str(tmp), batch=3)
    d = json.load(open(path))
    d["launcher"] = {"submit": submit, "submit_mode": mode,
                     "params_template": template or "<run><id>{{run_id}}</id><table>{{table}}</table><Kp>{{Kp}}</Kp>"
                                                    "<Ki>{{Ki}}</Ki><Kd>{{Kd}}</Kd></run>",
                     "results": {"glob": "results/{{table}}/{{run_id}}.csv"},
                     "status": {"failed_glob": "results/{{table}}/{{run_id}}.failed"}, **extra}
    for t in d["tables"]:
        t["paths"].append("next/round_*/collected_" + t["id"] + ".csv")
        if per_table and t["id"] in per_table:
            t["params_template"] = per_table[t["id"]]
    json.dump(d, open(path, "w"))
    N.next_runs(S.load(path), write=True)
    return path


SCEN_TPL = {
    "A": '{"run_id": "{{run_id}}", "table": "A", "Kp": {{Kp}}, "Ki": {{Ki}}, "Kd": {{Kd}}, "wind": {{wind}}}',
    "B": '{"run_id": "{{run_id}}", "table": "B", "Kp": {{Kp}}, "Ki": {{Ki}}, "Kd": {{Kd}}, "mass": {{mass}}, "wind": {{wind}}}',
    "C": '{"run_id": "{{run_id}}", "table": "C", "Kp": {{Kp}}, "Ki": {{Ki}}, "Kd": {{Kd}}, "wind": {{wind}}, "filter_hz": {{filter_hz}}}',
}
MOCK_SUBMIT = [sys.executable, MOCK, "--list", "{{params_files}}", "--results", "{{study_dir}}/results/{table}"]


def test_per_table_templates_are_written_one_file_per_run(tmp_path):
    path = _launcher_study(tmp_path, MOCK_SUBMIT, per_table=SCEN_TPL)
    s = S.load(path)
    out = L.submit(s, dry_run=True)
    assert out["submitted"] == len(s.history[-1].proposals) and out["needs_confirm"] is False
    assert out["command"][:2] == [sys.executable, MOCK] and out["command"][3].endswith("params_files_A.txt")
    rdir = L.round_dir(s, s.history[-1])
    p = next(x for x in s.history[-1].proposals if x.table == "B")
    d = json.load(open(os.path.join(rdir, "B", p.run_id + ".json")))
    assert d["mass"] == p.values["mass"] and d["run_id"] == p.run_id
    assert len(open(os.path.join(rdir, "params_files_C.txt")).read().split()) == sum(1 for x in s.history[-1].proposals if x.table == "C")


def test_round_mode_runs_one_command_per_table_and_results_come_back(tmp_path):
    path = _launcher_study(tmp_path, MOCK_SUBMIT, per_table=SCEN_TPL)
    s = S.load(path)
    r = L.submit(s, wait=True)
    assert r["exit_code"] == 0
    rdir = L.round_dir(s, s.history[-1])
    rec = json.load(open(os.path.join(rdir, "submit.json")))
    assert len(rec["commands"]) == 3 and set(rec["exit_codes"]) == {"A", "B", "C"}
    assert "launcher_mock: " in open(os.path.join(rdir, "submit.log")).read()
    code, st = L.wait(S.load(path), timeout=30)
    assert code == 0 and st["counts"]["done"] == len(s.history[-1].proposals) and st["finished"]
    assert all(p.state == "done" for p in S.load(path).history[-1].proposals)
    col = pd.read_csv(os.path.join(rdir, "collected_C.csv"))
    assert {"Kp", "filter_hz", "phase_margin", "run_id"} <= set(col.columns)
    assert not any(c.endswith(".1") for c in col.columns)               # the echoed inputs not added twice
    # the collected rows are part of the tables now
    before = sum(len(C.read_table_files(S.load(path).table_files(t))) for t in S.load(path).tables)
    assert before >= len(s.history[-1].proposals)


def test_xml_template_through_the_mock_and_failure_markers(tmp_path):
    tpl = "<run><param name='run_id'>{{run_id}}</param><param name='table'>{{table}}</param>" \
          "<param name='Kp' value='{{Kp}}'/><param name='Ki' value='{{Ki}}'/><param name='Kd' value='{{Kd}}'/>{{scen}}</run>"
    per = {t: tpl.replace("{{scen}}", "".join(f"<param name='{c}' value='{{{{{c}}}}}'/>" for c in cols))
           for t, cols in {"A": ["wind"], "B": ["mass", "wind"], "C": ["wind", "filter_hz"]}.items()}
    path = _launcher_study(tmp_path, MOCK_SUBMIT + ["--fail-rate", "0.3"], per_table=per)
    L.submit(S.load(path), wait=True)
    code, st = L.wait(S.load(path), timeout=30)
    assert code == 4 and st["counts"]["failed"] > 0 and st["counts"]["done"] > 0
    assert st["counts"]["failed"] + st["counts"]["done"] == len(st["runs"])
    states = {p.run_id: p.state for p in S.load(path).history[-1].proposals}
    assert {x["run_id"] for x in st["runs"] if x["state"] == "failed"} == {k for k, v in states.items() if v == "failed"}


def test_no_shell_and_the_exit_code_is_recorded(tmp_path):
    script = tmp_path / "fail.py"
    script.write_text("import sys; open(sys.argv[1], 'w').write(' '.join(sys.argv[2:])); sys.exit(7)\n")
    out = tmp_path / "args.txt"
    path = _launcher_study(tmp_path, [sys.executable, str(script), str(out), "a;b", "$(x)", "{{table}}"])
    r = L.submit(S.load(path), wait=True)
    assert r["exit_code"] == 7
    assert out.read_text() == "a;b $(x) C"                       # passed literally, last table's command
    st = L.status(S.load(path))
    assert st["counts"]["done"] == 0


def test_found_by_values_when_the_launcher_names_results_its_own_way(tmp_path):
    path = _launcher_study(tmp_path, [sys.executable, "-c", "pass"])
    s = S.load(path)
    L.submit(s, wait=True)
    s = S.load(path)
    p = next(x for x in s.history[-1].proposals if x.table == "A")
    os.makedirs(tmp_path / "results" / "A")
    row = {**p.values, "overshoot": 1.0, "settling_time": 2.0}
    pd.DataFrame([row, row]).to_csv(tmp_path / "results" / "A" / "whatever_name.csv", index=False)   # twice: a duplicate
    st = L.status(s)
    assert next(x for x in st["runs"] if x["run_id"] == p.run_id)["state"] == "done"
    assert st["duplicates"] == 1
    col = pd.read_csv(os.path.join(L.round_dir(s, s.history[-1]), "collected_A.csv"))
    assert col["run_id"].tolist() == [p.run_id] and col["settling_time"].tolist() == [2.0]


def test_a_round_times_out(tmp_path):
    path = _launcher_study(tmp_path, [sys.executable, "-c", "pass"], status={"timeout_s": 0.2})
    s = S.load(path)
    L.submit(s, wait=True)
    rdir = L.round_dir(s, s.history[-1])
    rec = json.load(open(os.path.join(rdir, "submit.json")))
    rec["finished"] = None                                         # still running, as a farm job would be
    json.dump(rec, open(os.path.join(rdir, "submit.json"), "w"))
    time.sleep(0.3)
    code, st = L.wait(S.load(path), timeout=5)
    assert code == 5 and st["timed_out"] and st["counts"]["missing"] == len(st["runs"])


def test_local_workers_run_the_command_per_run(tmp_path):
    path = _launcher_study(tmp_path, [sys.executable, MOCK, "--list", "{{params_file}}.lst", "--results", "{{study_dir}}/results/{table}"],
                           mode="run", per_table=SCEN_TPL, local_workers=2)
    s = S.load(path)
    for p, f in [x for v in L.write_params(s, s.history[-1]).values() for x in v]:   # the mock wants a list file
        open(f + ".lst", "w").write(f + "\n")
    r = L.submit(s, wait=True)
    assert r["mode"] == "run"
    code, st = L.wait(S.load(path), timeout=60)
    assert code == 0 and st["counts"]["done"] == len(st["runs"])
    assert len(json.load(open(os.path.join(L.round_dir(s, s.history[-1]), "submit.json")))["exit_codes"]) == len(st["runs"])


def test_5000_small_result_files_are_read_fast(tmp_path):
    files = []
    for i in range(5000):
        f = tmp_path / f"{i:05d}.csv"
        f.write_text(f"Kp,Ki,run_id,y\n{i * 0.1},{i % 7},r{i:05d},{i * 2.5}\n")
        files.append(str(f))
    t0 = time.perf_counter()
    df = L.read_small_csvs(files)
    took = time.perf_counter() - t0
    print(f"5000 result files: {took:.3f} s on {os.cpu_count()} CPUs")
    assert len(df) == 5000 and df["y"].iloc[-1] == 4999 * 2.5 and took < 2.0


def test_the_drone_example_converges_through_the_mock_launcher_with_study_loop(tmp_path, capsys):
    path = _launcher_study(tmp_path, MOCK_SUBMIT, per_table=SCEN_TPL)
    d = json.load(open(path))
    d["next"]["batch"] = 20
    d["history"] = []                                              # the loop proposes from round 1
    json.dump(d, open(path, "w"))
    shutil.rmtree(tmp_path / "next")
    assert study_cli(["loop", path, "--max-rounds", "4"]) == 0
    opt, at = _fine_optimum()
    best = next(x for x in C.rank(S.load(path))["rows"] if x["feasible"])
    assert best["score"] == pytest.approx(opt, rel=1e-6), (best, at)
    assert "Round 4: done" in capsys.readouterr().out


def test_submit_asks_unless_yes(tmp_path, capsys, monkeypatch):
    path = _launcher_study(tmp_path, [sys.executable, "-c", "pass"])
    monkeypatch.setattr("sys.stdin", open(os.devnull))
    assert study_cli(["submit", path]) == 1                        # not a terminal, no --yes: nothing runs
    assert "Not run" in capsys.readouterr().err
    assert study_cli(["submit", path, "--yes"]) == 0
    assert study_cli(["wait", path, "--timeout", "1"]) == 5          # submitted, no result yet: a farm still running
