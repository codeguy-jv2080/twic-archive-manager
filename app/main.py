from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .database import create_profile, initialize_database, list_profiles


STATIC_DIRECTORY = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="TWIC Archive Manager", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")


class ProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    archive_root: str = Field(min_length=1, max_length=2048)
    download_pgn: bool = True
    download_cbv: bool = False
    extract_archives: bool = True
    keep_zip_files: bool = True
    combine_after_sync: bool = False


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIRECTORY / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "windows-local"}


@app.get("/api/profiles")
def profiles() -> list[dict[str, object]]:
    return list_profiles()


@app.post("/api/profiles", status_code=status.HTTP_201_CREATED)
def add_profile(profile: ProfileRequest) -> dict[str, object]:
    if not (profile.download_pgn or profile.download_cbv):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select PGN, CBV, or both.",
        )
    try:
        return create_profile(**profile.model_dump())
    except sqlite3.IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile with that name already exists.",
        ) from error
