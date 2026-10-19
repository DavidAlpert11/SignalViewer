"""T54: files opened from outside (Explorer's "Open with", a double-click, `SignalViewer file.bin`)
go to the app that is already running, instead of starting a second one.

A start with file paths first offers them to the running app: run.py's push.json (T39) says where
it is and holds its token, and /api/open-external takes the paths (the page opens them as if they
were chosen in the file dialog). When Explorer starts one process per selected file and no app is
running yet, the first to take the start lock becomes the app; the others wait for it to answer and
hand their paths over. A start WITHOUT paths keeps today's behaviour (a window of its own)."""
import json
import os
import time
import urllib.request
from typing import List, Optional

from app import push

LOCK_NAME = "starting.lock"
WAIT = 30.0                         # how long a start waits for another one that is still starting


def _lock_path() -> str:
    return os.path.join(os.path.dirname(push.PUSH_FILE), LOCK_NAME)


def hand_over(paths: List[str], timeout: float = 3.0) -> bool:
    """Offer the paths to the running app. True when it took them."""
    try:
        with open(push.PUSH_FILE, encoding="utf-8") as f:
            info = json.load(f)
        url, token = str(info["url"]), str(info["token"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    req = urllib.request.Request(url.rstrip("/") + "/api/open-external", method="POST",
                                 data=json.dumps({"paths": paths}).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SV-Token": token})
    # never through a proxy: the app is on this computer (a company proxy setting would swallow it)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status == 200
    except (OSError, ValueError):       # not running any more (a stale push.json), or busy
        return False


def wait_or_lead(paths: List[str], wait: float = WAIT, step: float = 0.3) -> bool:
    """No app answered. True: one that was starting meanwhile took the paths (exit). False: this
    process takes the start lock and starts the app (release_lock() once it answers)."""
    lock = _lock_path()
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    deadline = time.time() + wait
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return False
        except FileExistsError:
            pass
        try:
            stale = time.time() - os.path.getmtime(lock) > wait     # left by a start that crashed
        except OSError:
            continue                                               # removed just now: try again
        if stale or time.time() > deadline:
            try:
                os.remove(lock)
            except OSError:
                pass
            continue
        if hand_over(paths):
            return True
        time.sleep(step)


def release_lock(path: Optional[str] = None) -> None:
    try:
        os.remove(path or _lock_path())
    except OSError:
        pass
