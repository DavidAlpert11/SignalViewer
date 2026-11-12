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
