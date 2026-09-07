from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "TWIC Archive Manager"
INSTALLATION_MARKER = "twic-installed.flag"


def is_installed() -> bool:
    """The installer adds this marker beside its executable, never to portable."""

    return (Path(sys.argv[0]).resolve().parent / INSTALLATION_MARKER).is_file()


def state_directory() -> Path:
    """Return this distribution's local Windows application-state directory.

    The database deliberately stays off an archive root so a UNC or mapped
    drive never has to host SQLite lock/journal files.
    """

    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    # Keep existing portable data in place. Installed runs never read or copy it.
    state_folder = "installed-state" if is_installed() else "state"
    path = base / APP_NAME / state_folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return state_directory() / "twic-archive-manager.db"
