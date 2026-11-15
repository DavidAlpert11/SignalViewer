"""Memory of an e2e run over time (2026-11-16: the whole suite died with MemoryError on the owner's Windows PC).

Runs pytest on the given e2e files and samples, every few seconds, the memory of pytest itself, of the app's
servers it started and of the browsers (every process under pytest, grouped by name):

    python tools/measure_e2e_memory.py tests/e2e/test_globe3d.py tests/e2e/test_map_objects.py
    python tools/measure_e2e_memory.py --every 10 tests/e2e            # the whole suite

The peak and the last sample per group are printed at the end; --csv keeps every sample.
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_maps import children, rss_mb  # noqa: E402


def names(pids):
    out = {}
    for p in pids:
        try:
            import psutil
            out[p] = psutil.Process(p).name()
            continue
        except ImportError:
            pass
        except Exception:
            continue
        try:
            with open(f"/proc/{p}/comm") as f:
                out[p] = f.read().strip()
        except OSError:
            pass
    return out


def group(name):
    if re.search(r"chrom|msedge|headless", name, re.I):
        return "browser"
    if re.search(r"python|pytest", name, re.I):
        return "python"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--every", type=float, default=5.0, help="seconds between samples")
    ap.add_argument("--csv")
    ap.add_argument("pytest_args", nargs="+")
    a = ap.parse_args()
    proc = subprocess.Popen([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *a.pytest_args])
    rows, t0 = [], time.time()
    while proc.poll() is None:
        kids = children(proc.pid)
        by = {"pytest": rss_mb([proc.pid]) or 0.0, "browser": 0.0, "python": 0.0, "other": 0.0}
        for p, n in names(kids).items():
            by[group(n)] += rss_mb([p]) or 0.0
        rows.append({"t": round(time.time() - t0), **{k: round(v) for k, v in by.items()}})
        print(f"{rows[-1]['t']:>6}s  pytest {rows[-1]['pytest']:>6} MB  servers/python {rows[-1]['python']:>6} MB  "
              f"browser {rows[-1]['browser']:>6} MB  other {rows[-1]['other']:>5} MB", flush=True)
        time.sleep(a.every)
    if rows:
        for k in ("pytest", "python", "browser"):
            print(f"{k:>8}: first {rows[0][k]} MB, peak {max(r[k] for r in rows)} MB, last {rows[-1][k]} MB")
    if a.csv and rows:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
