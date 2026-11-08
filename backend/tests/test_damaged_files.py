"""T33: files damaged the way field files are (cut off by a power loss, half copied, bits flipped,
a block of zeros, junk in the middle). Opening one must never hang and never fail with anything but
a LoadError (a clear message for the user) - and should keep whatever is still readable.

The mutations use fixed seeds, so a failure here is reproducible: the test id names the seed."""
import os
import random
import subprocess
import sys
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import LoadError, store  # noqa: E402

client = TestClient(app)
TOOLS = os.path.join(os.path.dirname(__file__), "..", "..", "tools")
SAMPLE_ULG = os.path.join(os.path.dirname(__file__), "data", "sample.ulg")
# Arrow prints the bad-row handler's own decode error before the repaired part is read again:
# expected noise, not a failure.
pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
SEEDS = 24                      # per format: fast enough for every CI run (~seconds)
KINDS = ("trunc", "flip", "zero", "garbage", "dup")
SLOW = 10.0                     # seconds: far above a normal open of these small files


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def mutate(data: bytes, rnd: random.Random, kind: str) -> bytes:
    b = bytearray(data)
    n = len(b)
    if kind == "trunc":                       # power loss / half-finished copy
        return bytes(b[:rnd.randrange(1, n)])
    if kind == "flip":                        # bad sectors, a flaky SD card
        for _ in range(rnd.randint(1, 30)):
            i = rnd.randrange(n)
            b[i] ^= 1 << rnd.randrange(8)
        return bytes(b)
    if kind == "zero":                        # the zero-padded tail / hole a power loss leaves
        i = rnd.randrange(n)
        L = rnd.randint(1, 4096)
        b[i:i + L] = bytes(len(b[i:i + L]))
        return bytes(b)
    if kind == "garbage":                     # junk spliced in
        i = rnd.randrange(n)
        b[i:i] = bytes(rnd.randrange(256) for _ in range(rnd.randint(1, 512)))
        return bytes(b)
    i, j = rnd.randrange(n), rnd.randrange(n)  # "dup": a block written twice
    b[i:i] = b[j:j + rnd.randint(1, 2000)]
    return bytes(b)


@pytest.fixture(scope="module")
def sources(tmp_path_factory):
    d = tmp_path_factory.mktemp("src")
    t = np.round(np.arange(0, 20, 0.05), 3)
    with open(d / "s.csv", "w") as f:
        f.write("Time,Speed,RPM,Mode\n")
        for x in t:
            f.write(f"{x},{10 + np.sin(x):.4f},{1500 + 100 * np.cos(x):.2f},{'AUTO' if x > 10 else 'MANUAL'}\n")
    import scipy.io as sio
    sio.savemat(d / "s.mat", {"t": t, "a": np.sin(t), "b": np.cos(t), "c": 2 * t})
    import h5py
    with h5py.File(d / "s73.mat", "w") as f:
        f.create_dataset("t", data=t)
        f.create_dataset("x", data=np.sin(t))
    for tool, name in (("make_test_bin.py", "s.bin"), ("make_test_tlog.py", "s.tlog")):
        subprocess.run([sys.executable, os.path.join(TOOLS, tool), str(d / name), "--seconds", "8"]
                       + (["--imu-hz", "50"] if name.endswith(".bin") else []), check=True, capture_output=True)
    from test_mcap_hdf5 import write_h5, write_ros2       # T27
    write_ros2(d / "s.mcap", seconds=2, chunk_size=8 * 1024)
    write_h5(d / "s.h5")
    from test_parquet import write_sample                  # T40
    write_sample(d / "s.parquet", n=400)
    return {ext: (d / f"s{ext}") for ext in (".csv", ".mat", ".bin", ".tlog", ".mcap", ".h5", ".parquet")} | {
        ".mat73": d / "s73.mat", ".ulg": SAMPLE_ULG}


CASES = [(fmt, seed) for fmt in (".csv", ".mat", ".mat73", ".bin", ".tlog", ".mcap", ".h5", ".parquet") for seed in range(SEEDS)] + \
        [(".ulg", seed) for seed in range(6)]          # the ULog sample is 4 MB: fewer cases


@pytest.mark.parametrize("fmt,seed", CASES, ids=[f"{f[1:]}-{s}" for f, s in CASES])
def test_damaged_file_opens_or_says_why(tmp_path, sources, fmt, seed):
    rnd = random.Random(seed)
    kind = KINDS[seed % len(KINDS)]
    ext = ".mat" if fmt == ".mat73" else fmt
    p = tmp_path / f"damaged{ext}"
    p.write_bytes(mutate(open(sources[fmt], "rb").read(), rnd, kind))
    t0 = time.monotonic()
    try:
        lr = store.open_file(str(p))
    except LoadError as e:
        assert str(e) and "Traceback" not in str(e)
    else:
        assert len(lr.run.time) > 0 and lr.run.signals    # what opened has data to plot
        desc = store.describe(lr)                        # and describes itself (sparklines, rates)
        assert desc["signals"]
    assert time.monotonic() - t0 < SLOW, f"{kind} took too long"


# ---- the specific damage the fuzzing found (each failed before T33) ----

def test_csv_with_an_invalid_byte_in_the_numbers_opens(tmp_path, sources):
    data = bytearray(open(sources[".csv"], "rb").read())
    i = data.index(b",", data.index(b"\n", len(data) // 2))   # a delimiter on a row in the middle
    data[i] = 0xAC        # not valid UTF-8 AND one column short: Arrow's bad-row handler itself failed,
                          # then pandas failed on the same byte - the whole file did not open
    p = tmp_path / "bad_byte.csv"
    p.write_bytes(bytes(data))
    r = client.post("/api/files/open", json={"paths": [str(p)]}).json()
    assert r["errors"] == [] and len(r["opened"]) == 1
    assert r["opened"][0]["report"].get("damagedText") is True


def test_csv_with_a_block_of_zeros_is_still_text(tmp_path, sources):
    data = bytearray(open(sources[".csv"], "rb").read())
    data[200:600] = bytes(400)                          # in the first 4 KB: was "binary file"
    p = tmp_path / "zeros.csv"
    p.write_bytes(bytes(data))
    r = client.post("/api/files/open", json={"paths": [str(p)]}).json()
    assert r["errors"] == [], r["errors"]
    assert len(r["opened"]) == 1


def test_real_binary_with_a_csv_name_is_still_refused(tmp_path):
    p = tmp_path / "random.csv"
    p.write_bytes(bytes(range(256)) * 50)
    r = client.post("/api/files/open", json={"paths": [str(p)]}).json()
    assert r["errors"][0]["code"] == "binaryText"


def test_cut_off_mat_keeps_the_complete_variables(tmp_path):
    import scipy.io as sio
    t = np.linspace(0, 10, 5000)
    src = tmp_path / "full.mat"
    sio.savemat(src, {"t": t, "a": np.sin(t), "b": np.cos(t), "c": 2 * t})
    data = open(src, "rb").read()
    p = tmp_path / "cut.mat"
    p.write_bytes(data[: int(len(data) * 0.8)])
    r = client.post("/api/files/open", json={"paths": [str(p)]}).json()
    assert r["errors"] == []
    o = r["opened"][0]
    assert o["report"].get("cutOff") is True
    names = {s["name"] for s in o["signals"]}
    assert {"a", "b"} <= names and "c" not in names


def test_mat_cut_before_any_complete_variable_says_so(tmp_path):
    import scipy.io as sio
    src = tmp_path / "full.mat"
    sio.savemat(src, {"t": np.linspace(0, 1, 5000), "a": np.zeros(5000)})
    p = tmp_path / "cut.mat"
    p.write_bytes(open(src, "rb").read()[:300])
    err = client.post("/api/files/open", json={"paths": [str(p)]}).json()["errors"][0]
    assert err["code"] == "badMat"


# ---- O2: damage must not become data (phantom signals), and a damaged .ulg opens what it can ----

EXAMPLE_BIN = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "copter_flight.bin")


def _names(path):
    lr = store.open_file(str(path))
    try:
        return set(lr.run.signals), dict(lr.load_report)
    finally:
        store.remove(lr.id)


def test_corrupt_bin_makes_no_phantom_signals(tmp_path):
    """tools/make_test_bin.py --corrupt: garbage that starts like an IMU message gave IMU[149].* (6 signals
    that are not in the log). The message before the damaged block is left out and counted."""
    good, bad = tmp_path / "good.bin", tmp_path / "bad.bin"
    for p, extra in ((good, []), (bad, ["--corrupt"])):
        subprocess.run([sys.executable, os.path.join(TOOLS, "make_test_bin.py"), str(p), "--seconds", "8",
                        "--imu-hz", "50"] + extra, check=True, capture_output=True)
    want, _ = _names(good)
    got, rep = _names(bad)
    assert got == want, sorted(got ^ want)
    assert rep["corruptBytes"] > 0 and rep["droppedMessages"] == 1


@pytest.mark.parametrize("seed", [12, 26, 36, 39, 52, 54])
def test_damaged_example_bin_has_only_its_own_signals(tmp_path, seed):
    """The ArduPilot example (73 signals) damaged by the fuzzer's seeds that made IMU[8] / IMU[190] /
    BARO[87] / VIBE[32] (an instance only the damage had): no signal beyond the 73."""
    data = open(EXAMPLE_BIN, "rb").read()
    want, _ = _names(EXAMPLE_BIN)
    p = tmp_path / f"d{seed}.bin"
    p.write_bytes(mutate(data, random.Random(seed), ("flip", "zero", "garbage", "dup")[seed % 4]))
    got, rep = _names(p)
    assert got <= want, sorted(got - want)
    assert rep.get("droppedMessages") or rep.get("phantomInstances")      # and it says so


def test_instance_rules_keep_real_instances():
    """A late or brief real instance (next to the others) and one read before (live mode) stay."""
    from svcore.bin_loader import DataFlash
    df = DataFlash()
    sel = lambda n: np.ones(n, bool)                                   # noqa: E731
    keep = df._real_instances("IMU", [(0, sel(5000)), (1, sel(4000)), (2, sel(2)), (149, sel(1))])
    assert [v for v, _ in keep] == [0, 1, 2] and df.phantom_instances == ["IMU[149]"]
    assert [v for v, _ in df._real_instances("IMU", [(0, sel(40)), (2, sel(1))])] == [0, 2]   # 2 known now
    assert [v for v, _ in df._real_instances("GPS", [(0, sel(3)), (1, sel(2))])] == [0, 1]    # all small: kept


def _damaged_ulg(tmp_path, seed, kind):
    p = tmp_path / f"d{seed}.ulg"
    p.write_bytes(mutate(open(SAMPLE_ULG, "rb").read(), random.Random(seed), kind))
    return p


def test_ulg_with_a_damaged_parameter_opens(tmp_path):
    """A flipped bit in the parameters: "could not convert string to float: b'\\x00...'" and the whole
    log failed (as an unexpected error). Now the parameter is left out and counted."""
    want, _ = _names(SAMPLE_ULG)
    got, rep = _names(_damaged_ulg(tmp_path, 16, "flip"))
    assert got == want and rep["damagedParams"] == 1


@pytest.mark.parametrize("seed", [1, 26])
def test_damaged_ulg_has_only_its_own_signals(tmp_path, seed):
    """A topic logged without time stamps gained one by a flipped bit: 2 / 35 one-sample signals that are
    not in the log. Time stamps only damage can make are left out and counted."""
    want, _ = _names(SAMPLE_ULG)
    got, rep = _names(_damaged_ulg(tmp_path, seed, "flip"))
    assert got == want, sorted(got - want)
    assert rep["badTimestamps"] >= 1


def test_undamaged_ulg_loses_nothing():
    """Topics stamped before logging started (a state published at boot) are real: none is dropped."""
    _, rep = _names(SAMPLE_ULG)
    assert "badTimestamps" not in rep and "damagedParams" not in rep


def test_truncated_ulg_keeps_what_was_written(tmp_path):
    data = open(SAMPLE_ULG, "rb").read()
    p = tmp_path / "cut.ulg"
    p.write_bytes(data[: len(data) // 2])
    got, _ = _names(p)
    assert len(got) > 100


def test_unexpected_loader_error_says_what_to_do(tmp_path, monkeypatch):
    import app.store as st
    def boom(path, name):
        raise ValueError("could not convert string to float: b'\\x00'")
    monkeypatch.setattr(st, "load_ulog", boom)
    r = client.post("/api/files/open", json={"paths": [SAMPLE_ULG]}).json()
    err = r["errors"][0]
    assert err["code"] == "unexpected" and "ValueError" in err["params"]["detail"]
    assert "damaged" in err["message"] and "Copy error details" in err["message"]
