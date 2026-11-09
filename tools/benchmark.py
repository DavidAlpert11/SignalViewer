"""
Signal Viewer - performance benchmark against the targets in the requirements
document (section 6). Writes a Markdown report.

    python tools/benchmark.py FILE.csv [--signals 4] [--out benchmark.md]
    python tools/benchmark.py --synthetic [--samples 5000000] [--out bench26.md] [--json bench26.json]

Each measurement that depends on a cold start runs in a fresh process.

--synthetic (P5, round of 2026-11-08) needs no file: it builds its own data and measures what that
round changed - a plot request with and without a run time offset, 30 signals x N samples on a zoom
step, a pan burst (each step waited for, and only the last one - what cancelling the older ones
gives), the memory of a large ArduPilot log with changed signals against the memory cache's budget,
and a live append on a wide CSV. Each row has a target; --json writes the numbers for CI (T3).
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
    c = TestClient(app, base_url="http://127.0.0.1")     # the server answers only requests to localhost
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


def synthetic(samples: int, cache: str) -> dict:
    """P5: the round's benchmarks on generated data (runs inside a fresh process)."""
    os.environ["SV_CACHE_DIR"] = cache
    sys.path.insert(0, BACKEND)
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    from svcore.memcache import CACHE
    from svcore.models import Run, Signal
    c0 = TestClient(app, base_url="http://127.0.0.1")    # the server answers only requests to localhost

    class Checked:                                       # a refused request must not be timed as fast
        def post(self, url, **kw):
            r = c0.post(url, **kw)
            assert r.status_code == 200, (url, r.status_code, r.text[:200])
            return r

        def get(self, url, **kw):
            r = c0.get(url, **kw)
            assert r.status_code == 200, (url, r.status_code, r.text[:200])
            return r
    c = Checked()
    out: dict = {"samples": samples}

    def med(fn, n=7):
        fn()
        ts = []
        for _ in range(n):
            t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
        return sorted(ts)[n // 2]

    def run_of(name, k, n):
        t = np.arange(n) / 1000.0
        r = Run(file_path=name, csv_display_name=name, time=t)
        for i in range(k):
            r.signals[f"s{i}"] = Signal(name=f"s{i}", data=np.sin(t * (1 + i / 10)).astype(np.float32), time=t)
        r.compute_metadata()
        return store.add_pushed(name, r)[0], n / 1000.0

    # 1. one signal, a zoomed window, without and with a run time offset (P1)
    lr, span = run_of("offset", 1, samples)
    body = {"signals": [f"{lr.id}/s0"], "x0": span * .5, "x1": span * .501, "points": 3200, "format": "bin"}
    out["data_no_offset_s"] = med(lambda: c.post("/api/data", json=body))
    store.set_time_offset(lr.id, 12.5)
    out["data_offset_s"] = med(lambda: c.post("/api/data", json=body))
    store.remove(lr.id)
    # 2. 30 signals on a zoom step (P3: binary answer)
    lr, span = run_of("thirty", 30, samples)
    ids = [f"{lr.id}/s{i}" for i in range(30)]
    zoom = {"signals": ids, "x0": span * .4, "x1": span * .41, "points": 3200, "format": "bin"}
    out["zoom30_s"] = med(lambda: c.post("/api/data", json=zoom), 5)
    out["zoom30_kb"] = len(c.post("/api/data", json=zoom).content) / 1024
    # 3. a pan burst of 10 steps: every step waited for, against only the last (the older ones cancelled)
    w = span * .01
    steps = [{**zoom, "x0": span * .4 + k * w * .2, "x1": span * .4 + k * w * .2 + w} for k in range(10)]
    t0 = time.perf_counter()
    for s in steps:
        c.post("/api/data", json=s)
    out["pan_all_s"] = time.perf_counter() - t0
    out["pan_last_s"] = med(lambda: c.post("/api/data", json=steps[-1]), 5)
    store.remove(lr.id)
    # 4. a large ArduPilot log with 10 changed signals: memory against the cache's budget (P2)
    log = os.path.join(cache, "big.bin")
    os.makedirs(cache, exist_ok=True)
    subprocess.check_call([sys.executable, os.path.join(HERE, "make_test_bin.py"), log, "--seconds", "1800", "--imu-hz", "400"])
    before = rss_mb()
    r = c.post("/api/files/open", json={"paths": [log]}).json()["opened"][0]
    out["bin_mb"] = os.path.getsize(log) / 1048576
    out["bin_open_rss_mb"] = rss_mb() - before
    sigs = [s["id"] for s in r["signals"] if s["id"].split("/", 1)[1].startswith("IMU")][:10]
    c.post("/api/transforms", json={"signals": sigs, "transform": {"scale": 2.0}})
    for sid in sigs:
        c.post("/api/stats", json={"signals": [sid]})
    out["bin_transforms_rss_mb"] = rss_mb() - before
    out["memcache_mb"] = CACHE.info()["bytes"] / 1048576
    out["memcache_limit_mb"] = CACHE.limit / 1048576
    for rid in list(store.order):
        store.remove(rid)
    # 5. live append on a wide CSV (300 columns): 1,000 new rows until readable
    wide = os.path.join(cache, "wide.csv")
    k, n0 = 300, 20000
    with open(wide, "w") as f:
        f.write("time," + ",".join(f"c{i}" for i in range(k)) + "\n")
        f.writelines(f"{i / 100:.2f}," + ",".join("0.5" for _ in range(k)) + "\n" for i in range(n0))
    c.post("/api/files/open", json={"paths": [wide]})
    c.post("/api/stream/start", json={})
    c.post("/api/stream/poll")
    with open(wide, "a") as f:
        f.writelines(f"{(n0 + i) / 100:.2f}," + ",".join("0.5" for _ in range(k)) + "\n" for i in range(1000))
    t0 = time.perf_counter()
    c.post("/api/stream/poll")
    out["live_wide_s"] = time.perf_counter() - t0
    out["live_wide_rows"] = c.get("/api/runs").json()[0]["samples"] - n0
    c.post("/api/stream/stop", json={})
    return out


# P5: (key, label, target text, pass test) - the targets T3 checks in CI (with a tolerance there)
SYNTH_ROWS = [
    ("offset_ratio", "Plot request with a run time offset / without (one signal, zoomed)", "≤ 2×", lambda v: v <= 2),
    ("zoom30_s", "Zoom step, 30 signals (server, binary answer)", "< 500 ms", lambda v: v < .5),
    ("zoom30_kb", "Data sent for that step", "≤ 2 MB", lambda v: v <= 2048),
    ("pan_last_s", "Pan burst of 10 steps: the last answer (older ones cancelled)", "< 300 ms", lambda v: v < .3),
    ("pan_all_s", "... every step waited for (before cancelling)", "—", None),
    ("cache_vs_limit", "Large .bin with 10 changed signals: memory cache / its budget", "≤ 1", lambda v: v <= 1),
    ("live_wide_s", "Live append, 300-column CSV: 1,000 rows readable", "< 1 s", lambda v: v < 1),
]


# T3: what a slower machine (CI) may stretch - times by the slack given, a ratio of two times by half of
# it (both slow down), sizes not at all (they do not depend on the machine)
TIMES, RATIOS = {"zoom30_s", "pan_last_s", "live_wide_s"}, {"offset_ratio"}
LIMITS = {"offset_ratio": 2.0, "zoom30_s": 0.5, "zoom30_kb": 2048.0, "pan_last_s": 0.3, "cache_vs_limit": 1.0, "live_wide_s": 1.0}


def derived(r: dict) -> dict:
    r = dict(r)
    r["offset_ratio"] = r["data_offset_s"] / max(r["data_no_offset_s"], 1e-6)
    r["cache_vs_limit"] = r["memcache_mb"] / max(r["memcache_limit_mb"], 1e-6)
    return r


def misses(r: dict, slack: float) -> list:
    """T3: the rows outside their target, each stretched by the slack for its kind."""
    r = derived(r)
    out = []
    for key, lim in LIMITS.items():
        f = slack if key in TIMES else max(1.0, slack / 2) if key in RATIOS else 1.0
        if not r[key] <= lim * f:
            out.append(f"{key} = {r[key]:.4g} (target {lim:g}, allowed {lim * f:.4g} with --check {slack:g})")
    return out


def synthetic_report(r: dict) -> str:
    r = derived(r)
    shown = {"offset_ratio": f"{r['offset_ratio']:.2f}× ({r['data_offset_s'] * 1000:.1f} / {r['data_no_offset_s'] * 1000:.1f} ms)",
             "zoom30_s": f"{r['zoom30_s'] * 1000:.0f} ms", "zoom30_kb": f"{r['zoom30_kb']:.0f} KB",
             "pan_last_s": f"{r['pan_last_s'] * 1000:.0f} ms", "pan_all_s": f"{r['pan_all_s'] * 1000:.0f} ms",
             "cache_vs_limit": f"{r['memcache_mb']:.0f} / {r['memcache_limit_mb']:.0f} MB (the log: {r['bin_mb']:.0f} MB on disk, "
                               f"+{r['bin_open_rss_mb']:.0f} MB open, +{r['bin_transforms_rss_mb']:.0f} MB with the changes)",
             "live_wide_s": f"{r['live_wide_s'] * 1000:.0f} ms ({r['live_wide_rows']} rows)"}
    lines = [f"# Benchmark — round of 2026-11-08 (synthetic, {r['samples']:,} samples per signal)", "",
             f"{os.cpu_count()} CPU · Python {sys.version.split()[0]}", "",
             "| Measurement | Target | Result | |", "|---|---|---|---|"]
    for key, label, target, ok in SYNTH_ROWS:
        lines.append(f"| {label} | {target} | {shown[key]} | {'' if ok is None else ('pass' if ok(r[key]) else 'MISS')} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--synthetic", action="store_true", help="the round of 2026-11-08's benchmarks on generated data")
    ap.add_argument("--samples", type=int, default=5_000_000)
    ap.add_argument("--json", default=None, help="--synthetic: also write the numbers as JSON (for CI)")
    ap.add_argument("--signals", type=int, default=4)
    ap.add_argument("--out", default="benchmark.md")
    ap.add_argument("--child", default=None)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--check", type=float, default=None, metavar="SLACK",
                    help="--synthetic: exit 1 when a target is missed - times may be SLACK times the target (a CI machine), sizes not")
    a = ap.parse_args()
    if a.child == "synthetic":
        print(json.dumps(synthetic(a.samples, a.cache)))
        return
    if a.child:
        print(json.dumps(child(a.child, a.file, a.cache, a.signals)))
        return
    if a.synthetic:
        work = tempfile.mkdtemp(prefix="svbench26_")
        try:
            res = json.loads(subprocess.check_output([sys.executable, __file__, "--child", "synthetic", "--cache", work,
                                                      "--samples", str(a.samples)]).decode().strip().splitlines()[-1])
        finally:
            shutil.rmtree(work, ignore_errors=True)
        text = synthetic_report(res)
        out = a.out if a.out != "benchmark.md" else "bench26.md"
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        if a.json:
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=1)
        print(text)
        if a.check is not None:
            bad = misses(res, a.check)
            for b in bad:
                print("MISS", b)
            if bad:
                sys.exit(1)
            print(f"every target met (slack {a.check:g} for times)")
        return
    if not a.file:
        ap.error("give a FILE, or --synthetic")
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
