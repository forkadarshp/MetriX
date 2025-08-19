import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response


router = APIRouter(prefix="/api", tags=["files"])


@router.get("/audio/{filename}")
async def serve_audio(filename: str):
    audio_path = f"storage/audio/{filename}"
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    mime = "audio/mpeg"
    if filename.lower().endswith(".wav"):
        mime = "audio/wav"
    with open(audio_path, "rb") as f:
        content = f.read()
    return Response(content=content, media_type=mime)


@router.get("/transcript/{filename}")
async def serve_transcript(filename: str):
    t_path = f"storage/transcripts/{filename}"
    if not os.path.exists(t_path):
        raise HTTPException(status_code=404, detail="Transcript file not found")
    with open(t_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="text/plain; charset=utf-8")


