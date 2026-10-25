"""Background jobs: long operations with progress and cancel."""

import os

from fastapi import APIRouter
from pydantic import BaseModel

from app import report as reports
from app.common import _load_error, fail, open_with_prefs
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
            opened, errors, n = [], [], max(1, len(paths))
            for i, p in enumerate(paths):
                # each file gets an equal share of the bar; the loader reports inside it
                def sub(frac, phase="", i=i):
                    job.report((i + frac) / n, phase)
                from svcore.csv_loader import set_progress_context
                set_progress_context(sub, job.cancelled)
                try:
                    lr = open_with_prefs(p, settings)
                    opened.append(store.describe(lr))
                except LoadError as e:
                    errors.append(_load_error(p, e))
                except JobCancelled:
                    raise
                except Exception as e:
                    if e.__class__.__name__ == "LoadCancelled":
                        raise
                    errors.append({"path": p, "message": f"Unexpected error while reading the file: {e}"})
                job.report((i + 1) / n, "read")
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
            if rr.format == "html":
                text = reports.build_html(store, body, progress=job.report)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            elif rr.format == "pdf":
                reports.build_pdf(store, body, path, progress=job.report)
            else:
                reports.build_docx(store, body, path, progress=job.report)
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
