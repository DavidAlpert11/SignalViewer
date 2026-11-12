"""W17 / W18: hand a study's runs to the user's launcher application, and the smart-sweep demo.
Owned by lane L4; the shapes are the W0 contract (tests/fixtures/sweeps/)."""
from typing import Optional

from fastapi import APIRouter

from app.routes.sweeps_common import StudyReq, _fixture

router = APIRouter()


class SubmitReq(StudyReq):
    round: Optional[int] = None            # default: the last round
    confirmed: bool = False                # the user saw the exact command this session


class DemoReq(StudyReq):
    action: str = "next"                   # "next" | "run" (until converged) | "reset"
    max_rounds: Optional[int] = None


@router.post("/api/sweeps/launcher/submit")
def launcher_submit(req: SubmitReq):
    return _fixture("launcher_submit.json")


@router.get("/api/sweeps/launcher/status")
def launcher_status(study_path: str, round: Optional[int] = None):
    return _fixture("launcher_status.json")


@router.post("/api/sweeps/demo/step")
def demo_step(req: DemoReq):
    return _fixture("demo_step.json")


@router.get("/api/sweeps/demo/progress")
def demo_progress(study_path: str):
    return _fixture("demo_progress.json")
