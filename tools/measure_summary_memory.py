"""M2: is a folder summary flat in memory? `cli.py summarize`'s loop (read a file, measure it, close it) over N
large recordings, the process's resident memory after each file and the time per file.

    python tools/measure_summary_memory.py [--files 50] [--rows 2000000] [--folder /tmp/m2]
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))


def rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1024
    return float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=50)
    ap.add_argument("--rows", type=int, default=2_000_000)
    ap.add_argument("--folder", default="/tmp/m2")
    a = ap.parse_args()
    import pandas as pd
    os.makedirs(a.folder, exist_ok=True)
    src = os.path.join(a.folder, "src.parquet")
    if not os.path.exists(src):
        t = np.arange(a.rows) / 400.0
        rng = np.random.default_rng(0)
        pd.DataFrame({"Time": t, **{f"S{k}": np.sin(t * (k + 1)) + 0.1 * rng.standard_normal(a.rows) for k in range(8)}}).to_parquet(src)
    paths = []
    for i in range(a.files):              # hard links: N files to read, one copy on the disk
        p = os.path.join(a.folder, f"run_{i:03d}_kp_{0.1 * (i % 7):.1f}.parquet")
        if not os.path.exists(p):
            os.link(src, p)
        paths.append(p)
    import signalviewer as sv
    from svcore import summary
    measures = [{"name": "max S0", "signal": "S0", "op": "max"}, {"name": "rms S3", "signal": "S3", "op": "rms"},
                {"name": "mean S1 where", "signal": "S1", "op": "mean", "where": "S2 > 0.5"}]
    base = rss_mb()
    seen = []
    t0 = time.perf_counter()
    for i, p in enumerate(paths):
        tf = time.perf_counter()
        rec = sv.load(p)
        summary.summarize_run(rec._store, rec._id, measures, "run_{run}_kp_{kp}")
        rec._store.remove(rec._id)
        del rec
        seen.append(rss_mb())
        print(f"{i + 1:3d}  {seen[-1]:7.0f} MB  {time.perf_counter() - tf:5.2f} s", flush=True)
    first10, last10 = np.mean(seen[:10]), np.mean(seen[-10:])
    print(f"start {base:.0f} MB, peak {max(seen):.0f} MB, first 10 {first10:.0f} MB, last 10 {last10:.0f} MB, "
          f"{(time.perf_counter() - t0) / len(paths):.2f} s per file")
    print("FLAT" if last10 - first10 < 0.25 * max(first10 - base, 50) else "GROWS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
