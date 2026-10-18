"""T41: the fleet - index folders of flight logs, search by finding, trends (app/fleet.py)."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import fleet
from app.common import fail
from app.jobs import jobs

router = APIRouter()


class FolderReq(BaseModel):
    path: str


@router.get("/api/fleet")
def fleet_state():
    return {"folders": fleet.folders(), "keys": fleet.keys()}


def _scan_job(folder: str, label: str):
    def work(job):
        return fleet.scan(folder, progress=lambda f, name: job.report(f, name), cancelled=job.cancelled)
    return jobs.start("fleetScan", label, work).to_dict()


@router.post("/api/fleet/folder")
def fleet_add(req: FolderReq):
    """Add a folder and index it (a background job: progress and cancel like any long operation)."""
    import os
    if not os.path.isdir(req.path):
        fail(400, f"Not a folder: {req.path}")
    short = os.path.basename(req.path.rstrip("/\\")) or req.path     # (no backslash inside an f-string: Python < 3.12)
    return _scan_job(req.path, "Index " + short)


@router.post("/api/fleet/rescan")
def fleet_rescan():
    """Read what changed in every indexed folder (one job)."""
    folders = [f["folder"] for f in fleet.folders()]

    def work(job):
        out = []
        for i, d in enumerate(folders):
            out.append(fleet.scan(d, progress=lambda f, name, i=i: job.report((i + f) / max(1, len(folders)), name),
                                  cancelled=job.cancelled))
        return {"folders": out}
    return jobs.start("fleetScan", "Update the fleet", work).to_dict()


@router.post("/api/fleet/remove")
def fleet_remove(req: FolderReq):
    fleet.remove_folder(req.path)
    return {"folders": fleet.folders()}


@router.get("/api/fleet/logs")
def fleet_logs(text: str = "", level: str = "", code: str = "", key: str = "", above: Optional[float] = None,
               below: Optional[float] = None, mode: str = "", limit: int = 500):
    return {"logs": fleet.query(text, level, code, key, above, below, mode, limit)}


@router.get("/api/fleet/trend")
def fleet_trend(key: str):
    return {"key": key, "points": fleet.trend(key)}
