"""Background jobs: long operations with progress and cancel."""

import os

from fastapi import APIRouter
from pydantic import BaseModel

from app import report as reports
from app.atomic import write_text as _write_text
from app.common import atomic_path, fail, open_paths
from app.jobs import JobCancelled, jobs
from app.routes.compare import CompareAllRequest, compare_table
from app.routes.export import ReportRequest, _check_target
from app.store import LoadError, store

router = APIRouter()




# =============================================================================
# BACKGROUND JOBS (phase 5): progress + cancel for long operations
# =============================================================================

class JobRequest(BaseModel):
    kind: str                         # open | report | compareAll | exportCsv
    body: dict = {}
    label: str = ""



@router.post("/api/jobs")
def start_job(req: JobRequest):
    b = req.body
    if req.kind == "open":
        paths, settings = list(b.get("paths") or []), b.get("settings")

        def work(job):
            # P4: several at once within the memory budget; each file its share of the bar
            opened, errors = open_paths(paths, settings, job.report, job.cancelled)
            if job.cancelled():
                raise JobCancelled()
            return {"opened": opened, "errors": errors}
    elif req.kind == "report":
        rr = ReportRequest(**b)
        ext = {"html": ".html", "pdf": ".pdf", "docx": ".docx"}.get(rr.format)
        if not ext:
            fail(400, "Unknown report format.")
        path = _check_target(rr.path, ext)

        def work(job):
            body = rr.model_dump()
            job.report(0.05, "prepare")
            with atomic_path(path) as tmp:     # O3: the old report stays until the new one is complete
                if rr.format == "html":
                    _write_text(tmp, reports.build_html(store, body, progress=job.report))
                elif rr.format == "pdf":
                    reports.build_pdf(store, body, tmp, progress=job.report)
                else:
                    reports.build_docx(store, body, tmp, progress=job.report)
            return {"path": path, "size": os.path.getsize(path)}
    elif req.kind == "reloadAll":
        def work(job):
            res = store.reload_all(progress=lambda f, name: job.report(f, name), cancelled=job.cancelled)
            job.report(1.0, "read")
            return res
    elif req.kind == "reload":
        # one file read again from the disk, in the background with progress (a big log used to be
        # one long request: the page waited without a sign of life and could give up on it)
        rid = str(b.get("id") or "")
        if rid not in store.runs:
            fail(404, "File is not open.")

        def work(job):
            try:
                lr = store.reload(rid)
            except KeyError:
                raise LoadError("This file is no longer open.") from None
            job.report(1.0, "read")
            return store.describe(lr)
    elif req.kind == "timeAxis":
        # another time column / unit for one file: it is read again (a big file takes a while)
        rid = str(b.get("id") or "")
        if rid not in store.runs:
            fail(404, "File is not open.")
        try:
            scale, own, offset = float(b.get("scale", 1.0)), float(b.get("ownScale", 1.0)), float(b.get("offset", 0.0))
        except (TypeError, ValueError):
            fail(400, "The scale and the offset must be numbers.")
        column = b.get("column") or None
        # positions on the old axis, in the page's order (not numbers -> None in the answer)
        times = [float(t) if isinstance(t, (int, float)) else float("nan") for t in (b.get("times") or [])]

        def work(job):
            try:
                res = store.set_time_axis(rid, column, scale, own, offset, times)
            except KeyError:
                raise LoadError("This file is no longer open.") from None
            job.report(1.0, "read")
            return res
    elif req.kind == "compareAll":
        ca = CompareAllRequest(**b)

        def work(job):
            return {"signals": compare_table(ca, job.report)}
    else:
        fail(400, f"Unknown job: {req.kind}")
    job = jobs.start(req.kind, req.label or req.kind, work)
    return job.to_dict()



@router.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        fail(404, "Unknown job.")
    return job.to_dict()



@router.post("/api/jobs/{job_id}/cancel")
def job_cancel(job_id: str):
    return {"cancelled": jobs.cancel(job_id)}
