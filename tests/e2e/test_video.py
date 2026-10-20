"""T15: a plot in video mode plays a local video with the timeline (needs ffmpeg to make the test
video; skipped without it). data time = video time + offset."""
import os
import shutil
import subprocess

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg  # noqa: E402,F401

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not FFMPEG, reason="ffmpeg makes the test video")


@pytest.fixture(scope="module")
def clip(env):
    p = os.path.join(env["data"], "test_clip.webm")
    if not os.path.exists(p):                     # 10 s, VP8 (plays in Playwright's Chromium), a key frame every 5
        subprocess.run([FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=10:size=320x240:rate=25",
                        "-c:v", "libvpx", "-g", "5", "-b:v", "300k", p], check=True)
    return p


def video_time(pg):
    return pg.evaluate("document.querySelector('.video-stage video').currentTime")


def cursor_t(pg):
    return pg.evaluate("window.__sv.state().cursor.t1")


def set_cursor(pg, t):
    pg.evaluate(f"window.__sv.setState({{ cursor: {{ on: true, dual: false, t1: {t}, t2: null, active: 1 }} }})")


def wait_close(pg, js, want, tol=0.1):
    pg.wait_for_function(f"Math.abs(({js}) - {want}) < {tol}", timeout=8000)


def test_video_follows_the_cursor_lines_up_and_moves_the_cursor(pg, clip):
    open_files(pg, "run_a.csv")
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Video").click()
    pg.wait_for_selector(".video-bar button:has-text('Choose a video…')")   # empty state (loaded lazily)
    # (the built-in file browser is tested elsewhere: give the plot its video directly)
    pg.evaluate("""p => { const s = window.__sv.state(); s.commit(ws => {
        ws.tabs.forEach(t => t.plots.forEach(pl => { if (pl.mode === 'video') pl.video = { path: p, offset: 0 }; }));
        return ws; }); }""", clip)
    pg.wait_for_function("document.querySelector('.video-stage video')?.readyState >= 1", timeout=10000)

    vt = "document.querySelector('.video-stage video').currentTime"
    set_cursor(pg, 4)                                                   # locked, offset 0: the cursor moves the video
    wait_close(pg, vt, 4)

    pg.click("button:has-text('Line up…')")                             # unlock: they move separately
    assert pg.is_visible(".video-lining")
    pg.evaluate("document.querySelector('.video-stage video').currentTime = 2")   # the event in the video
    set_cursor(pg, 7)                                                   # the same event in the data
    pg.wait_for_timeout(300)
    assert abs(video_time(pg) - 2) < 0.1 and abs(cursor_t(pg) - 7) < 1e-9          # nothing dragged the other
    pg.click("button:has-text('Lock here')")
    pg.wait_for_selector("text=Video lined up")
    off = pg.evaluate("window.__sv.state().ws.tabs[0].plots.find(p => p.mode === 'video').video.offset")
    assert abs(off - 5) < 0.05                                          # data = video + 5 s

    set_cursor(pg, 9)                                                   # locked again: video at 9 - 5 = 4
    wait_close(pg, vt, 4)
    pg.evaluate("document.querySelector('.video-stage video').currentTime = 6")   # the user seeks the video...
    wait_close(pg, "window.__sv.state().cursor.t1", 11)                         # ...the cursor follows (6 + 5)
    set_cursor(pg, 30)                                                  # 30 - 5 = 25 s: after the 10 s clip
    pg.wait_for_selector(".video-outside")

    pg.keyboard.press("Control+z")                                      # the offset is part of undo
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.find(p => p.mode === 'video').video.offset === 0")
