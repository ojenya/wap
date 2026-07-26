"""Artifact gallery listing + file download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.auth import Viewer
from app.db import get_db
from app.models import Artifact, WorkflowRun
from app.schemas import ArtifactOut

router = APIRouter(prefix="/api", tags=["artifacts"])


@router.get("/runs/{run_id}/artifacts", response_model=list[ArtifactOut])
def list_run_artifacts(
    run_id: str, _: Viewer, db: Session = Depends(get_db)
) -> list[Artifact]:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return list(run.artifacts)


@router.get("/artifacts/{artifact_id}/content")
def download_artifact(artifact_id: str, _: Viewer, db: Session = Depends(get_db)):
    art = db.get(Artifact, artifact_id)
    if art is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = Path(art.content) if art.content else None
    if path and path.is_file() and path.exists():
        media = "application/octet-stream"
        suffix = path.suffix.lower()
        if suffix == ".png":
            media = "image/png"
        elif suffix in {".webm", ".mp4"}:
            media = "video/webm" if suffix == ".webm" else "video/mp4"
        elif suffix == ".zip":
            media = "application/zip"
        elif suffix in {".md", ".txt", ".log"}:
            media = "text/plain"
        return FileResponse(path, media_type=media, filename=art.name)
    # Inline textual content (reports/patches).
    return PlainTextResponse(art.content or "", media_type="text/plain")
