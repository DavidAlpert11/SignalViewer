"""Video synchronised to the timeline (T15): the local video file, served in byte ranges so the
player can seek. Ranges are handled here (not left to FileResponse) because older Starlette
versions answer a Range request with the whole file, and the player then cannot seek."""
import os
import re

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from app.common import fail

router = APIRouter()

VIDEO_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
               ".webm": "video/webm", ".ogv": "video/ogg", ".mkv": "video/x-matroska"}
CHUNK = 1 << 20


def _read(path: str, start: int, end: int):
    with open(path, "rb") as f:
        f.seek(start)
        left = end - start + 1
        while left > 0:
            b = f.read(min(CHUNK, left))
            if not b:
                break
            left -= len(b)
            yield b


@router.get("/api/video")
def video(path: str, request: Request):
    ext = os.path.splitext(path)[1].lower()
    if ext not in VIDEO_TYPES:
        fail(400, f"Not a video this app plays: {os.path.basename(path)} (use mp4, webm, mov, m4v, ogv or mkv).")
    if not os.path.isfile(path):
        fail(404, f"Video not found: {path}")
    size = os.path.getsize(path)
    head = {"Accept-Ranges": "bytes", "Cache-Control": "no-store"}
    rng = request.headers.get("range")
    if not rng:
        return StreamingResponse(_read(path, 0, size - 1), media_type=VIDEO_TYPES[ext],
                                 headers={**head, "Content-Length": str(size)})
    m = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", rng)
    if m and m.group(1):
        start, end = int(m.group(1)), (int(m.group(2)) if m.group(2) else size - 1)
    elif m and m.group(2):                        # "bytes=-N": the last N bytes
        start, end = max(0, size - int(m.group(2))), size - 1
    else:
        start, end = 1, 0                         # malformed: not satisfiable
    end = min(end, size - 1)
    if start >= size or start > end:
        return Response(status_code=416, headers={**head, "Content-Range": f"bytes */{size}"})
    return StreamingResponse(_read(path, start, end), status_code=206, media_type=VIDEO_TYPES[ext],
                             headers={**head, "Content-Range": f"bytes {start}-{end}/{size}",
                                      "Content-Length": str(end - start + 1)})
