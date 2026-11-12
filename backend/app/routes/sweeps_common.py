"""W14 / W15: one parameter set for many sweep tables, and the next runs to try - the study file's
routes (svcore/study.py). Owned by lane L3; the shapes are the W0 contract (tests/fixtures/sweeps/,
backend/tests/test_study_contract.py)."""
import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.common import fail
from svcore import study as studies

router = APIRouter()
FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tests", "fixtures", "sweeps")


class StudyReq(BaseModel):
    study_path: Optional[str] = None       # a saved .svstudy.json
    study: Optional[Dict[str, Any]] = None  # or the panel's study as it is now (unsaved edits); relative paths
                                           # are then read against study_path's folder (or `folder`)
    folder: Optional[str] = None
    write: bool = False                    # next-runs: write the round's files and the history (as `study next`)


def study_of(req: StudyReq) -> studies.Study:
    """The study a request names: its dict (with the saved file's place for relative paths) or the file."""
    try:
        if req.study is not None:
            base = req.study_path or (os.path.join(req.folder, "study" + studies.STUDY_SUFFIX) if req.folder else "")
            return studies.loads(json.dumps(req.study), os.path.abspath(base) if base else "")
        if req.study_path:
            return studies.load(req.study_path)
    except (OSError, ValueError) as e:
        fail(400, f"The study could not be read: {e}")
    fail(400, "No study: send study_path or study.")


def _fixture(name: str) -> dict:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


@router.post("/api/sweeps/common")
def common(req: StudyReq):
    """W14: the ranked table of the shared values (fixture until L3 fills it in)."""
    return _fixture("common.json")


@router.post("/api/sweeps/next-runs")
def next_runs(req: StudyReq):
    """W15: the next batch of candidate values of S, expanded to their runs (fixture until L3)."""
    return _fixture("next_runs.json")
