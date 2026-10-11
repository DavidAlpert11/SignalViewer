"""
Signal Viewer - performance benchmark against the targets in the requirements
document (section 6). Writes a Markdown report.

    python tools/benchmark.py FILE.csv [--signals 4] [--out benchmark.md]

Each measurement that depends on a cold start runs in a fresh process.
"""
import argparse, base64, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(HERE, "..", "backend")


def rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return float("nan")


def child(mode: str, path: str, cache: str, nsig: int) -> dict:
    """Runs inside a fresh process."""
    os.environ["SV_CACHE_DIR"] = cache
    os.environ["SV_CACHE_MIN_MB"] = "1"
    sys.path.insert(0, BACKEND)
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    out = {"runtime_mb": rss_mb()}     # Python + libraries, before any data
    t = time.perf_counter()
    r = c.post("/api/files/open", json={"paths": [path]}).json()
    out["open_s"] = time.perf_counter() - t
    run = r["opened"][0]
    out["samples"] = run["samples"]
    out["signals_in_file"] = len(run["signals"])
    data_bytes = (1 + len(run["signals"])) * run["samples"] * 8
    out["data_mb"] = data_bytes / 1048576
    sigs = [s["id"] for s in run["signals"][:nsig]]
    if mode == "warm":
        # touch the displayed data like the UI would, then measure resident memory
        c.post("/api/data", json={"signals": sigs, "points": 3200})
        out["rss_mb"] = rss_mb()
        lat = {}
        def timed(name, fn, n=5):
            ts = []
            for _ in range(n):
                t0 = time.perf_counter(); res = fn(); ts.append(time.perf_counter() - t0)
            lat[name] = sorted(ts)[n // 2]
            return res
        span = run["end"] - run["start"]
        full = timed("redraw_full", lambda: c.post("/api/data", json={"signals": sigs, "points": 3200}))
        out["payload_kb_per_signal"] = len(full.content) / 1024 / len(sigs)
        timed("redraw_zoom", lambda: c.post("/api/data", json={"signals": sigs, "x0": run["start"] + span * .4, "x1": run["start"] + span * .41, "points": 3200}))
        timed("redraw_deep_zoom", lambda: c.post("/api/data", json={"signals": sigs, "x0": run["start"] + span * .5, "x1": run["start"] + span * .5001, "points": 3200}))
        timed("cursor", lambda: c.post("/api/cursor", json={"signals": sigs, "t": run["start"] + span * .3}), 20)
        timed("stats_region", lambda: c.post("/api/stats", json={"signals": sigs, "t0": run["start"] + span * .2, "t1": run["start"] + span * .7}))
        out["latency_s"] = lat
        # live mode: append 1000 rows and measure until they are readable
        hdr = None
        with open(path, "rb") as f:              # last complete row (rows can be very long)
            size = f.seek(0, 2); back = 4096
            while True:
                f.seek(max(0, size - back)); lines = f.read().splitlines()
                if len(lines) >= 2 or back >= size:
                    break
                back *= 4
            last = lines[-1].decode()
        ncol = len(last.split(","))
        t_last = float(last.split(",")[0]); dt = span / max(1, run["samples"] - 1)
        rows = "".join(",".join([f"{t_last + (i + 1) * dt:.6f}"] + ["0"] * (ncol - 1)) + "\n" for i in range(1000))
        with open(path, "a") as f:
            f.write(rows)
        t0 = time.perf_counter(); p = c.post("/api/stream/poll").json(); out["stream_append_s"] = time.perf_counter() - t0
        out["stream_rows_seen"] = (c.get("/api/runs").json()[0]["samples"] - run["samples"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--signals", type=int, default=4)
    ap.add_argument("--out", default="benchmark.md")
    ap.add_argument("--child", default=None)
    ap.add_argument("--cache", default=None)
    a = ap.parse_args()
    if a.child:
        print(json.dumps(child(a.child, a.file, a.cache, a.signals)))
        return
    work = tempfile.mkdtemp(prefix="svbench_")
    src = os.path.join(work, os.path.basename(a.file))
    shutil.copy(a.file, src)          # the live-mode test appends rows; never touch the original
    cache = os.path.join(work, "cache")
    run = lambda mode: json.loads(subprocess.check_output([sys.executable, __file__, src, "--child", mode, "--cache", cache,
                                                            "--signals", str(a.signals)], stderr=subprocess.DEVNULL).decode().strip().splitlines()[-1])
    cold = run("cold")
    warm = run("warm")
    size_mb = os.path.getsize(a.file) / 1048576
    L = warm["latency_s"]
    ms = lambda s: f"{s * 1000:.0f} ms"
    rows = [
        ("Open, first time (incl. building the cache)", "< 5 s for 730 MB", f"{cold['open_s']:.2f} s", None),
        ("Open again (from cache)", "< 1 s", f"{warm['open_s']:.2f} s", warm["open_s"] < 1),
        ("Memory after reopening / binary data size", "≤ 1.2×", f"{warm['rss_mb']:.0f} MB / {warm['data_mb']:.0f} MB", None),
        (f"Redraw after zoom, {a.signals} signals (server)", "< 300 ms", ms(L["redraw_zoom"]), L["redraw_zoom"] < .3),
        ("Redraw, full range (server)", "< 300 ms", ms(L["redraw_full"]), L["redraw_full"] < .3),
        ("Redraw, deep zoom to raw samples (server)", "< 300 ms", ms(L["redraw_deep_zoom"]), L["redraw_deep_zoom"] < .3),
        ("Data sent per redraw", "≤ 1 MB per plot", f"{warm['payload_kb_per_signal']:.0f} KB per signal", warm["payload_kb_per_signal"] * a.signals < 1024),
        ("Cursor values (server)", "< 50 ms", ms(L["cursor"]), L["cursor"] < .05),
        ("Statistics for a region (server)", "—", ms(L["stats_region"]), None),
        ("Live mode: read 1,000 appended rows", "< 1 s end to end", f"{warm['stream_append_s'] * 1000:.0f} ms ({warm['stream_rows_seen']} rows)", warm["stream_append_s"] < 1),
    ]
    # target from the requirements: 5 s for the 730 MB reference file (5 M rows x 8 columns = 40 M values);
    # scaled by the number of values, which is what parsing time depends on (not bytes)
    values = cold["samples"] * (cold["signals_in_file"] + 1)
    first_target = 5 * values / 40e6
    rows[0] = (rows[0][0], f"< {first_target:.1f} s (5 s per 40 M values)", rows[0][2], cold["open_s"] < first_target)
    data_rss = warm["rss_mb"] - warm["runtime_mb"]
    mem_ratio = data_rss / max(1, warm["data_mb"])
    rows[2] = ("Memory for the data after reopening / binary data size", "≤ 1.2×",
               f"{data_rss:.0f} MB / {warm['data_mb']:.0f} MB = {mem_ratio:.2f}× (+ {warm['runtime_mb']:.0f} MB runtime)", mem_ratio <= 1.2)
    lines = [f"# Benchmark — {os.path.basename(a.file)}", "",
             f"{size_mb:.0f} MB · {cold['samples']:,} rows · {cold['signals_in_file']} signals · {os.cpu_count()} CPU · Python {sys.version.split()[0]}", "",
             "| Measurement | Target | Result | |", "|---|---|---|---|"]
    for name, target, result, ok in rows:
        lines.append(f"| {name} | {target} | {result} | {'' if ok is None else ('pass' if ok else 'MISS')} |")
    lines += ["", "Server times exclude browser rendering (measured separately in the browser tests).",
              "Opening speed scales with CPU cores: Arrow parses each 64 MB part in parallel.", ""]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
