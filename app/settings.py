from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "TWIC Archive Manager"


def state_directory() -> Path:
    """Return the local Windows application-state directory.

    The database deliberately stays off an archive root so a UNC or mapped
    drive never has to host SQLite lock/journal files.
    """

    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    path = base / APP_NAME / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return state_directory() / "twic-archive-manager.db"
