"""T3: tools/benchmark.py --check - the targets a CI run must meet, with a slack for slower machines."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import benchmark  # noqa: E402

OK = {"data_offset_s": 0.003, "data_no_offset_s": 0.003, "zoom30_s": 0.2, "zoom30_kb": 900, "pan_last_s": 0.1,
      "memcache_mb": 500, "memcache_limit_mb": 1024, "live_wide_s": 0.4}


def test_slack_stretches_times_not_sizes():
    assert benchmark.misses(OK, 1) == []
    slow = {**OK, "zoom30_s": 1.2, "live_wide_s": 2.5}
    assert len(benchmark.misses(slow, 1)) == 2 and benchmark.misses(slow, 3) == []
    big = {**OK, "zoom30_kb": 4096}                      # a size is the same on any machine
    assert [m.split(" ")[0] for m in benchmark.misses(big, 10)] == ["zoom30_kb"]
    ratio = {**OK, "data_offset_s": 0.009}             # 3x: a ratio may stretch by half the slack
    assert benchmark.misses(ratio, 2) and not benchmark.misses(ratio, 3)
