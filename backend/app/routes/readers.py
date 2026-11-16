"""T60: the user's own file readers - the list (app/userreaders.py; the folder and the example: `signalviewer-cli readers`)."""
from fastapi import APIRouter

from app import userreaders

router = APIRouter()


@router.get("/api/readers")
def readers_list():
    return userreaders.listing()
