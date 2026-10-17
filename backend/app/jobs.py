"""
Background jobs with progress and cancel (N-04).

Long operations (opening big files, reports, comparing all signals, exports) run in
a worker thread. The UI polls GET /api/jobs/{id} for progress and can cancel.
"""

import logging
import threading
import time
import uuid
from typing import Callable, Dict, Optional

from svcore.csv_loader import LoadCancelled, set_progress_context

log = logging.getLogger("signalviewer").getChild(__name__)


class JobCancelled(LoadCancelled):
    """One cancellation type end to end: the loader re-raises LoadCancelled untouched
    instead of treating it as a parse error (and falling back to the slow parser)."""


class Job:
    def __init__(self, kind: str, label: str):
        self.id = uuid.uuid4().hex[:10]
        self.kind, self.label = kind, label
        self.state = "running"          # running | done | error | cancelled
        self.progress = 0.0             # 0..1 overall
        self.phase = ""
        self.result = None
        self.error: Optional[str] = None
        self.started = time.time()
        self._cancel = threading.Event()

    # used by the work function
    def report(self, frac: float, phase: str = ""):
        self.progress = max(self.progress, min(1.0, frac))
        if phase:
            self.phase = phase
        if self._cancel.is_set():
            raise JobCancelled()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "label": self.label, "state": self.state,
                "progress": round(self.progress, 4), "phase": self.phase, "error": self.error,
                "result": self.result if self.state == "done" else None,
                "elapsed": round(time.time() - self.started, 2)}


class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, label: str, work: Callable[[Job], object]) -> Job:
        job = Job(kind, label)
        with self._lock:
            # keep the registry small: forget finished jobs older than 10 minutes
            now = time.time()
            for jid in [j.id for j in self.jobs.values() if j.state != "running" and now - j.started > 600]:
                self.jobs.pop(jid, None)
            self.jobs[job.id] = job

        def run():
            set_progress_context(job.report, job.cancelled)   # loaders report through this thread
            try:
                job.result = work(job)
                job.progress, job.state = 1.0, "done"
            except (JobCancelled, LoadCancelled):
                job.state = "cancelled"
            except Exception as e:  # surfaced to the UI as a readable message, the details to the log
                log.exception("job %s (%s) failed", job.id, kind)
                job.state, job.error = "error", str(e) or e.__class__.__name__
            finally:
                set_progress_context(None, None)

        threading.Thread(target=run, daemon=True, name=f"job-{kind}").start()
        return job

    def get(self, jid: str) -> Optional[Job]:
        return self.jobs.get(jid)

    def cancel(self, jid: str) -> bool:
        job = self.jobs.get(jid)
        if not job or job.state != "running":
            return False
        job._cancel.set()
        return True


jobs = JobManager()
