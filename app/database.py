from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from .settings import database_path


PROFILE_FIELDS: Final = """
    id, name, archive_root, download_pgn, download_cbv, extract_archives,
    keep_zip_files, default_selection_mode, default_selection_value,
    combine_after_sync, schedule_text, created_at, updated_at
"""

SCHEMA: Final = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    archive_root TEXT NOT NULL,
    download_pgn INTEGER NOT NULL DEFAULT 1 CHECK (download_pgn IN (0, 1)),
    download_cbv INTEGER NOT NULL DEFAULT 0 CHECK (download_cbv IN (0, 1)),
    extract_archives INTEGER NOT NULL DEFAULT 1 CHECK (extract_archives IN (0, 1)),
    keep_zip_files INTEGER NOT NULL DEFAULT 1 CHECK (keep_zip_files IN (0, 1)),
    default_selection_mode TEXT NOT NULL DEFAULT 'latest_n',
    default_selection_value TEXT NOT NULL DEFAULT '1',
    combine_after_sync INTEGER NOT NULL DEFAULT 0 CHECK (combine_after_sync IN (0, 1)),
    schedule_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# The starter database predates these Saved Setup fields. These additions keep
# an existing local database usable without removing any of its data.
PROFILE_COLUMN_ADDITIONS: Final = {
    "default_selection_mode": "TEXT NOT NULL DEFAULT 'latest_n'",
    "default_selection_value": "TEXT NOT NULL DEFAULT '1'",
    "schedule_text": "TEXT NOT NULL DEFAULT ''",
}

_UNSET: Final = object()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    database = path or database_path()
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(path: Path | str | None = None) -> None:
    with connection(path) as conn:
        conn.executescript(SCHEMA)
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()
        }
        for column, definition in PROFILE_COLUMN_ADDITIONS.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE profiles ADD COLUMN {column} {definition}")
        conn.execute("DROP TABLE IF EXISTS artifacts")


def _profile_from_row(row: sqlite3.Row) -> dict[str, object]:
    profile = dict(row)
    for field in (
        "download_pgn",
        "download_cbv",
        "extract_archives",
        "keep_zip_files",
        "combine_after_sync",
    ):
        profile[field] = bool(profile[field])
    return profile


def _profile_row(
    conn: sqlite3.Connection, identifier: str | int
) -> sqlite3.Row | None:
    if isinstance(identifier, int):
        return conn.execute(
            f"SELECT {PROFILE_FIELDS} FROM profiles WHERE id = ?", (identifier,)
        ).fetchone()
    return conn.execute(
        f"SELECT {PROFILE_FIELDS} FROM profiles WHERE name = ? COLLATE NOCASE",
        (identifier,),
    ).fetchone()


def list_profiles(path: Path | str | None = None) -> list[dict[str, object]]:
    with connection(path) as conn:
        rows = conn.execute(
            f"SELECT {PROFILE_FIELDS} FROM profiles ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [_profile_from_row(row) for row in rows]


def get_profile(
    identifier: str | int, path: Path | str | None = None
) -> dict[str, object] | None:
    with connection(path) as conn:
        row = _profile_row(conn, identifier)
    return _profile_from_row(row) if row is not None else None


def create_profile(
    *,
    name: str,
    archive_root: str,
    download_pgn: bool = True,
    download_cbv: bool = False,
    extract_archives: bool = True,
    keep_zip_files: bool = True,
    default_selection_mode: str = "latest_n",
    default_selection_value: str = "1",
    combine_after_sync: bool = False,
    schedule_text: str = "",
    path: Path | str | None = None,
) -> dict[str, object]:
    now = _timestamp()
    with connection(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO profiles (
                name, archive_root, download_pgn, download_cbv,
                extract_archives, keep_zip_files, default_selection_mode,
                default_selection_value, combine_after_sync, schedule_text,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                archive_root,
                download_pgn,
                download_cbv,
                extract_archives,
                keep_zip_files,
                default_selection_mode,
                default_selection_value,
                combine_after_sync,
                schedule_text,
                now,
                now,
            ),
        )
        row = _profile_row(conn, int(cursor.lastrowid))
    assert row is not None
    return _profile_from_row(row)


def update_profile(
    identifier: str | int,
    *,
    name: str | object = _UNSET,
    archive_root: str | object = _UNSET,
    download_pgn: bool | object = _UNSET,
    download_cbv: bool | object = _UNSET,
    extract_archives: bool | object = _UNSET,
    keep_zip_files: bool | object = _UNSET,
    default_selection_mode: str | object = _UNSET,
    default_selection_value: str | object = _UNSET,
    combine_after_sync: bool | object = _UNSET,
    schedule_text: str | object = _UNSET,
    path: Path | str | None = None,
) -> dict[str, object] | None:
    values = {
        "name": name,
        "archive_root": archive_root,
        "download_pgn": download_pgn,
        "download_cbv": download_cbv,
        "extract_archives": extract_archives,
        "keep_zip_files": keep_zip_files,
        "default_selection_mode": default_selection_mode,
        "default_selection_value": default_selection_value,
        "combine_after_sync": combine_after_sync,
        "schedule_text": schedule_text,
    }
    changes = {field: value for field, value in values.items() if value is not _UNSET}

    with connection(path) as conn:
        existing = _profile_row(conn, identifier)
        if existing is None:
            return None
        if changes:
            assignments = ", ".join(f"{field} = ?" for field in changes)
            conn.execute(
                f"UPDATE profiles SET {assignments}, updated_at = ? WHERE id = ?",
                (*changes.values(), _timestamp(), existing["id"]),
            )
        row = _profile_row(conn, int(existing["id"]))
    assert row is not None
    return _profile_from_row(row)


def delete_profile(identifier: str | int, path: Path | str | None = None) -> bool:
    with connection(path) as conn:
        existing = _profile_row(conn, identifier)
        if existing is None:
            return False
        conn.execute("DELETE FROM profiles WHERE id = ?", (existing["id"],))
    return True
