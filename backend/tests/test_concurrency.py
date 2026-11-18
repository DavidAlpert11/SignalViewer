"""Many requests at once on big files (owner, 2026-11-18: "can it crash?"). A stress test with 48 threads found
two things: listing the signals while another request made one failed ("dictionary changed size during
iteration", a 500), and heavy computations all at once took the server past 9 GB until the system killed it."""
import asyncio
import os
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import common  # noqa: E402
from app.store import Store  # noqa: E402


def test_heavy_computations_run_a_few_at_a_time():
    running, most = 0, 0
    lock = threading.Lock()

    def job(_i):
        nonlocal running, most
        with lock:
            running += 1
            most = max(most, running)
        time.sleep(0.02)
        with lock:
            running -= 1
        return _i

    async def main():
        return await asyncio.gather(*(common.heavy(job, i) for i in range(30)))

    assert asyncio.run(main()) == list(range(30))                  # every one done, in order
    assert most == common.HEAVY_JOBS and 2 <= common.HEAVY_JOBS <= 4  # never more at once


def test_the_list_holds_while_signals_are_made(tmp_path):
    st = Store()
    f = tmp_path / "r.csv"
    t = np.arange(2000) / 100
    f.write_text("time,a\n" + "".join(f"{x},{np.sin(x)}\n" for x in t))
    rid = st.open_file(str(f)).id
    errors = []

    def make():
        for _ in range(60):
            try:
                st.add_derived("abs", [f"{rid}/a"], {})
            except Exception as e:                   # noqa: BLE001 - any failure is the finding
                errors.append(e)

    def read():
        for _ in range(300):
            try:
                st.list()
            except Exception as e:                   # noqa: BLE001
                errors.append(e)

    ts = [threading.Thread(target=make) for _ in range(3)] + [threading.Thread(target=read) for _ in range(3)]
    for x in ts:
        x.start()
    for x in ts:
        x.join()
    assert errors == []
    assert len(st.list()[-1]["signals"]) == 180
