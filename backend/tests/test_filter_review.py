"""1.21: ArduPilot's IMU batch sampler (ISBH / ISBD) and its gyro filters (Filter Review): the samples
at the sensor's rate, before / after the filters, a spectrum averaged over the bursts, the notch and
low-pass responses with ArduPilot's own coefficients."""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.analysis import burst_spectrum  # noqa: E402
from svcore.bin_loader import load_bin  # noqa: E402
from svcore.filters import filter_setup, lpf2p_gain, notch_gain, response  # noqa: E402


def _fmt(typ, name, f, cols):
    sizes = {"Q": "Q", "H": "H", "B": "B", "f": "f", "a": "64s", "Z": "64s", "N": "16s", "n": "4s", "b": "b"}
    size = 3 + struct.calcsize("<" + "".join(sizes[c] for c in f))
    return struct.pack("<BBBBB4s16s64s", 0xA3, 0x95, 128, typ, size, name.encode(), f.encode(), cols.encode())


def _batch_log(path, tone=87.0, rate=2000.0, n_batches=6, cnt=1024, gyros=3, opt=4, params=None):
    """Gyro / accel batches of IMU 0, before (instance 0) and after (instance 0 + 3 IMUs) the filters,
    a tone of `tone` Hz on gyro X (after the filters at a tenth of its size)."""
    out = [_fmt(128, "FMT", "BBnNZ", "Type,Length,Name,Format,Columns"),
           _fmt(150, "ISBH", "QHBBHHQf", "TimeUS,N,type,instance,mul,smp_cnt,SampleUS,smp_rate"),
           _fmt(151, "ISBD", "QHHaaa", "TimeUS,N,seqno,x,y,z"),
           _fmt(152, "PARM", "QNf", "TimeUS,Name,Value"),
           _fmt(131, "MSG", "QZ", "TimeUS,Message")]
    out.append(struct.pack("<BBBQ64s", 0xA3, 0x95, 131, 1_000_000, b"ArduCopter V4.5.5 (142aece2)"))
    plist = [("INS_LOG_BAT_OPT", opt), ("INS_GYR_ID", 1), ("INS_GYR2_ID", 2), ("INS_GYR3_ID", 3)][:gyros + 1]
    for name, v in plist + list((params or {}).items()):
        out.append(struct.pack("<BBBQ16sf", 0xA3, 0x95, 152, 500_000, name.encode(), float(v)))
    mul = int(32767 / np.radians(2000))
    n = 0
    t0 = 2.0
    for b in range(n_batches):
        for post in (False, True):
            for typ in (0, 1):
                sus = int((t0 + b * 2.0 + (0.8 if post else 0.0) + typ * 0.0) * 1e6)
                k = np.arange(cnt)
                amp = 0.5 if not post else 0.05
                x = amp * np.sin(2 * np.pi * tone * (sus * 1e-6 + k / rate)) if typ == 1 else np.zeros(cnt)
                raw = np.clip(np.round(x * mul), -32767, 32767).astype("<i2")
                inst = 0 + (gyros if post else 0)
                out.append(struct.pack("<BBBQHBBHHQf", 0xA3, 0x95, 150, sus, n, typ, inst, mul, cnt, sus, rate))
                for s in range(cnt // 32):
                    chunk = raw[s * 32:(s + 1) * 32].tobytes()
                    out.append(struct.pack("<BBBQHH", 0xA3, 0x95, 151, sus + s, n, s) + chunk + bytes(64) + bytes(64))
                n += 1
    with open(path, "wb") as f:
        f.write(b"".join(out))


def test_batch_samples_before_and_after_the_filters(tmp_path):
    p = tmp_path / "isb.bin"
    _batch_log(p)
    r = load_bin(str(p), "isb.bin")
    r = r[0] if isinstance(r, tuple) else r
    names = set(r.signals)
    assert {"ISBD[0].GyrX [rad/s]", "ISBD[0].GyrXPost [rad/s]", "ISBD[0].AccZ [m/s/s]"} <= names
    assert not any(n.startswith(("ISBH.", "ISBD.")) for n in names)      # no sequence numbers as signals
    t, y = r.get_signal_data("ISBD[0].GyrX [rad/s]")
    assert len(t) == 6 * 1024 and abs(np.max(np.abs(y)) - 0.5) < 0.01       # the multiplier undone
    assert abs(np.median(np.diff(t)) - 1 / 2000) < 1e-9
    _tp, yp = r.get_signal_data("ISBD[0].GyrXPost [rad/s]")
    assert abs(np.max(np.abs(yp)) - 0.05) < 0.01
    # the spectrum: each burst alone, averaged - the tone where it is, not smeared by the pauses
    how: dict = {}
    f, m = burst_spectrum(np.asarray(t), np.asarray(y), "hanning", "fft", how)
    assert how["bursts"] == 6 and abs(f[np.argmax(m)] - 87.0) < 2.0 and 0.4 < m.max() <= 0.51   # Hann: up to 15 % lower between bins


def test_notch_and_low_pass_as_ardupilot():
    f = np.array([10.0, 35.0, 70.0, 140.0, 300.0])
    g = notch_gain(f, 2000.0, 70.0, 35.0, 40.0)
    assert abs(g[2] - 10 ** (-40 / 20)) < 1e-3 and g[0] > 0.99 and g[4] > 0.99          # -40 dB at the centre
    lp = lpf2p_gain(np.array([0.0, 20.0, 200.0]), 2000.0, 20.0)
    assert abs(lp[0] - 1) < 1e-9 and abs(lp[1] - 2 ** -0.5) < 1e-3 and lp[2] < 0.02       # -3 dB at the cutoff


def test_filter_setup_uses_the_logged_notch_centres():
    params = {"INS_HNTCH_ENABLE": 1, "INS_HNTCH_FREQ": 80, "INS_HNTCH_BW": 40, "INS_HNTCH_ATT": 40,
              "INS_HNTCH_HMNCS": 3, "INS_HNTCH_MODE": 1, "INS_GYRO_FILTER": 40}
    t = np.linspace(0, 100, 101)
    logged = {"FTNS[0].NF": (t, np.where(t < 10, 0, 92.0))}
    s = filter_setup(params, lambda n: logged.get(n), 20, 80)
    n = s["notches"][0]
    assert n["base"] == [92.0] and n["lines"] == [92.0, 184.0] and n["baseFrom"] == "log" and n["mode"] == "throttle"
    g = response(s, np.array([92.0, 184.0, 5.0]), 1000.0)
    assert g[0] < 0.02 and g[1] < 0.02 and g[2] > 0.95
    s2 = filter_setup(params, lambda n: None)
    assert s2["notches"][0]["base"] == [80.0] and s2["notches"][0]["baseFrom"] == "parameter" and s2["lpf"] == 40


def test_step_response_of_a_known_loop():
    """A second-order loop (wn 40 rad/s, damping 0.5, 10 ms delay) driven by pilot-like steps: the
    estimate matches the true step response (overshoot about 16 %)."""
    from scipy.signal import cont2discrete, dlsim, lfilter
    from svcore.stepresp import step_response
    fs = 400
    t = np.arange(0, 60, 1 / fs)
    rng = np.random.default_rng(1)
    sp = np.repeat(rng.normal(0, 30, 240), fs // 4)[:len(t)]
    a = np.exp(-1 / (fs * 0.02))
    sp = lfilter([1 - a], [1, -a], sp)
    dn, dd, _ = cont2discrete(([1600.0], [1, 40.0, 1600.0]), 1 / fs)
    _, y = dlsim((dn.ravel(), dd, 1 / fs), sp)
    d = int(0.01 * fs)
    y = np.r_[np.zeros(d), y.ravel()[:-d]] + rng.normal(0, 0.5, len(t))
    r = step_response(t, sp, t, y)
    _, true = dlsim((dn.ravel(), dd, 1 / fs), np.ones(int(0.5 * fs)))
    true = np.r_[np.zeros(d), true.ravel()[:-d]]
    assert np.max(np.abs(r["step"] - true)) < 0.05
    assert 10 < r["overshoot"] < 22 and 0.02 < r["rise"] < 0.07 and abs(r["final"] - 1) < 0.05
    assert step_response(t[::20], sp[::20], t[::20], y[::20])["error"] == "rate"      # 20 Hz: too slow
    flat = np.zeros(len(t))
    assert "error" in step_response(t, flat, t, y)
