"""W17 / W18: hand a study's runs to the user's launcher application, and the smart-sweep demo.
Owned by lane L4; the shapes are the W0 contract (tests/fixtures/sweeps/)."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.common import fail
from app.routes.sweeps_common import StudyReq, study_of
from svcore import demo, launcher, loop, sweeps_common
from svcore import study as studies

router = APIRouter()


class SubmitReq(StudyReq):
    round: Optional[int] = None            # default: the last round
    confirmed: bool = False                # the user saw the exact command this session (the panel asks once)
    dry_run: bool = False


class DemoReq(StudyReq):
    action: str = "next"                   # "next" | "run" (until converged) | "reset" | "stop"
    max_rounds: Optional[int] = None


@router.post("/api/sweeps/launcher/submit")
def launcher_submit(req: SubmitReq):
    """Write the round's parameter files and run the launcher command from the SAVED study (never from a
    table or a result). Not confirmed yet: the exact command comes back with needs_confirm, nothing runs."""
    if req.study is not None:
        fail(400, "The launcher runs only a saved study: save it, then send study_path.")
    s = study_of(req)
    try:
        if req.dry_run or not req.confirmed:
            out = launcher.submit(s, req.round, dry_run=True)
            out["needs_confirm"] = not req.dry_run
            return out
        return launcher.submit(s, req.round, wait=False)
    except launcher.LauncherError as e:
        fail(409, str(e))


@router.get("/api/sweeps/launcher/status")
def launcher_status(study_path: str, round: Optional[int] = None):
    s = study_of(StudyReq(study_path=study_path))
    try:
        return launcher.status(s, round)
    except launcher.LauncherError as e:
        fail(409, str(e))


def _demo_study(req_path: Optional[str], reset: bool = False) -> studies.Study:
    if not req_path:
        fail(400, "No demo study: send study_path.")
    try:
        return demo.prepare(req_path, reset=reset)
    except (OSError, ValueError, launcher.LauncherError) as e:
        fail(409, str(e))


def _progress(s: studies.Study) -> dict:
    try:
        return demo.progress(s)
    except (launcher.LauncherError, sweeps_common.StudyError) as e:
        fail(409, str(e))


@router.post("/api/sweeps/demo/step")
def demo_step(req: DemoReq):
    """Next round / Run until converged (in the background; poll /progress), Reset, Stop."""
    s = _demo_study(req.study_path, reset=req.action == "reset")
    try:
        if req.action in ("next", "run"):
            demo.start_background(s, req.action, req.max_rounds)
        elif req.action == "stop":
            loop.stop(s)
        elif req.action != "reset":
            fail(400, f"Unknown demo action '{req.action}' (next, run, reset, stop).")
    except launcher.LauncherError as e:
        fail(409, str(e))
    return _progress(s)


@router.get("/api/sweeps/demo/progress")
def demo_progress(study_path: str):
    return _progress(_demo_study(study_path))


# ------------------------------------------------------------------ the loop for any study (owner, 2026-11-13)

class LoopReq(StudyReq):
    action: str = "run"                    # "next" (one round) | "run" (until converged) | "stop" | "reset"
    max_rounds: Optional[int] = None


@router.post("/api/sweeps/loop")
def loop_step(req: LoopReq):
    """Signal Viewer as the manager of the runs: propose -> run (your program or launcher) -> wait for the results
    in their folder -> rank -> propose ..., in the background; poll /api/sweeps/loop/progress."""
    if req.study is not None:
        fail(400, "The loop runs a saved study: save it, then send study_path.")
    s = study_of(req)
    try:
        if req.action in ("next", "run"):
            loop.start_background(s, req.action, req.max_rounds)
        elif req.action == "stop":
            loop.stop(s)
        elif req.action == "reset":
            if loop.busy(s):
                fail(409, "A round is running: stop the loop and wait for the round to finish first.")
            loop.reset(s)
        else:
            fail(400, f"Unknown loop action '{req.action}' (next, run, stop, reset).")
    except launcher.LauncherError as e:
        fail(409, str(e))
    return loop.progress(studies.load(s.path))


@router.get("/api/sweeps/loop/progress")
def loop_progress(study_path: str):
    s = study_of(StudyReq(study_path=study_path))
    return loop.progress(s)


class CopyDemoReq(BaseModel):
    study_path: str                        # the demo study (the examples' one)
    folder: str                            # a new or empty folder


@router.post("/api/sweeps/demo/copy")
def demo_copy(req: CopyDemoReq):
    """Make the demo your own: its study and program copied into a folder, ready to change and run."""
    try:
        return {"path": demo.copy_to(req.study_path, req.folder)}
    except (OSError, launcher.LauncherError) as e:
        fail(409, str(e))
