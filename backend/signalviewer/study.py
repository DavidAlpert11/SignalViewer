"""The study command line (W14, W15, W17, W18): the same study file the Sweeps panel saves, without the app.

    python -m signalviewer.study rank   drones.svstudy.json [--json] [--csv ranking.csv]
    python -m signalviewer.study next   drones.svstudy.json [--json]          # writes the round, updates history
    python -m signalviewer.study status drones.svstudy.json [--json]
    python -m signalviewer.study submit drones.svstudy.json [--round K] [--yes]
    python -m signalviewer.study wait   drones.svstudy.json [--round K] [--timeout S]
    python -m signalviewer.study loop   drones.svstudy.json [--max-rounds N] [--local]
    python -m signalviewer.study demo   examples/smart_sweep_demo/demo.svstudy.json [--max-rounds N]
    python -m signalviewer.study demo-sim params.json                          # one run of the demo simulator

    SignalViewer.exe study ...   - the same, headless, from the Portable (no Python needed)

`demo <study>` = `loop <study> --local` plus, per round, the gap to the full-grid optimum and the final
sentence (W18). `demo-sim` takes one run's parameters file (JSON), not a study file.

Exit codes: 0 done / ok, 1 an error (the message says what to do), 3 nothing left to propose at the smallest
step, 4 some runs failed, 5 timed out.
"""
import argparse
import json
import sys
from typing import Callable, Dict, List, Optional

EXIT_OK, EXIT_ERROR, EXIT_EXHAUSTED, EXIT_FAILED, EXIT_TIMEOUT = 0, 1, 3, 4, 5


def _not_implemented(name: str) -> Callable[[argparse.Namespace], int]:
    def run(a: argparse.Namespace) -> int:
        print(f"study {name}: not implemented", file=sys.stderr)
        return EXIT_ERROR
    return run


# each command's implementation (filled in by lanes L3: rank / next / status, L4: submit / wait / loop / demo / demo-sim)
COMMANDS: Dict[str, Callable[[argparse.Namespace], int]] = {
    n: _not_implemented(n) for n in ("rank", "next", "status", "submit", "wait", "loop", "demo", "demo-sim")}


# ------------------------------------------------------------------ L3: rank / next / status

def _load(path: str):
    from svcore import study as studies
    try:
        return studies.load(path)
    except (OSError, ValueError) as e:
        raise SystemExit(_err(f"The study '{path}' could not be read: {e}"))


def _err(msg: str) -> int:
    print(msg, file=sys.stderr)
    return EXIT_ERROR


def _fmt_values(v: dict) -> str:
    return ", ".join(f"{k}={x:g}" if isinstance(x, (int, float)) else f"{k}={x}" for k, x in v.items())


def cmd_rank(a: argparse.Namespace) -> int:
    from svcore.sweeps_common import StudyError, rank, to_csv_rows
    s = _load(a.study)
    try:
        r = rank(s)
    except StudyError as e:
        return _err(str(e))
    if a.csv:
        to_csv_rows(r).to_csv(a.csv, index=False, encoding="utf-8-sig")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=float))
        return EXIT_OK
    print(f"{s.name or a.study}: {r['counts']['feasible']} of {r['counts']['values']} values hold in every table "
          f"({'the worst table minimised' if r['mode'] == 'minworst' else 'Pareto front over the tables'}), {r['seconds']:.2f} s")
    for row in r["rows"][:10]:
        if not row["feasible"]:
            break
        per = "; ".join(f"{p['table']} {p['score']:.4g}" + (f" ({_fmt_values(p['local'])})" if p["local"] else "") for p in row["tables"])
        print(f"  {row['rank']:>3}{'*' if row['pareto'] and r['mode'] == 'pareto' else ' '} {_fmt_values(row['values'])}  ->  {per}")
    return EXIT_OK


def cmd_next(a: argparse.Namespace) -> int:
    from svcore.sweeps_common import StudyError
    from svcore.sweeps_next import next_runs
    s = _load(a.study)
    try:
        r = next_runs(s, write=True)
    except StudyError as e:
        return _err(str(e))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=float))
    elif r["exhausted"]:
        print("Nothing left to propose at the smallest step of the search space.")
    else:
        c = r["counts"]
        print(f"Round {r['round']}: {c['candidates']} candidate values -> {c['runs']} runs "
              f"(refine {c['refine']}, boundary {c['boundary']}, gap {c['gap']}); written: {', '.join(r['files'])}")
    return EXIT_EXHAUSTED if r["exhausted"] else EXIT_OK


def cmd_status(a: argparse.Namespace) -> int:
    from svcore import study as studies
    from svcore.sweeps_common import StudyError, rank
    from svcore.sweeps_next import mark_done
    s = _load(a.study)
    try:
        counts = mark_done(s)
        r = rank(s)
    except StudyError as e:
        return _err(str(e))
    if s.path and s.history:
        studies.save(s)
    best = next((x for x in r["rows"] if x["feasible"]), None)
    last = s.history[-1].round if s.history else 0
    out = {"study": s.name, "rounds": last, "proposals": counts, "values": r["counts"]["values"],
           "feasible": r["counts"]["feasible"], "best": best and {"values": best["values"], "score": best["score"]}}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, default=float))
        return EXIT_OK
    pend = counts.get("pending", 0) + counts.get("submitted", 0)
    print(f"{s.name or a.study}: {last} round(s); proposals " + (", ".join(f"{k} {v}" for k, v in counts.items()) or "none")
          + (f" - {pend} runs still to come from round {last}" if pend else ""))
    print(f"  {r['counts']['feasible']} of {r['counts']['values']} values hold in every table"
          + (f"; best: {_fmt_values(best['values'])} (score {best['score']:.4g})" if best else ""))
    return EXIT_OK


COMMANDS.update({"rank": cmd_rank, "next": cmd_next, "status": cmd_status})


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="study", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("rank", "next", "status", "submit", "wait", "loop", "demo"):
        p = sub.add_parser(name)
        p.add_argument("study", help="the .svstudy.json file")
        p.add_argument("--json", action="store_true", help="print JSON (the API's shape) instead of text")
        if name == "rank":
            p.add_argument("--csv", help="also write the ranking table to this CSV")
        if name in ("submit", "wait"):
            p.add_argument("--round", type=int, help="the round (default: the last)")
        if name == "submit":
            p.add_argument("--yes", action="store_true", help="run the launcher command without asking")
        if name in ("wait", "loop"):
            p.add_argument("--timeout", type=float, help="seconds per round (default: the study's status.timeout_s)")
        if name in ("loop", "demo"):
            p.add_argument("--max-rounds", type=int, help="stop after this many rounds")
        if name == "loop":
            p.add_argument("--local", action="store_true", help="run on this PC (local_workers), not the launcher")
    p = sub.add_parser("demo-sim")
    p.add_argument("params", help="one run's parameters file (JSON)")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    from .cli import _utf8_streams    # Windows consoles: UTF-8 output (the 1.26.0 CI failure)
    _utf8_streams()
    a = parser().parse_args(argv)
    return COMMANDS[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
