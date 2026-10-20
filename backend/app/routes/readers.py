"""T60: the user's own file readers - list, folder, example (app/userreaders.py)."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import userreaders
from app.common import fail

router = APIRouter()


@router.get("/api/readers")
def readers_list():
    return userreaders.listing()


class FolderReq(BaseModel):
    path: Optional[str] = None


@router.post("/api/readers/folder")
def readers_folder(req: FolderReq):
    try:
        userreaders.set_folder(req.path)
    except ValueError as e:
        fail(400, str(e))
    return userreaders.listing()


@router.post("/api/readers/example")
def readers_example():
    try:
        path = userreaders.write_example()
    except OSError as e:
        fail(400, f"Could not write the example: {e}")
    return {**userreaders.listing(), "example": path}
