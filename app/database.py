from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .settings import database_path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    archive_root TEXT NOT NULL,
    download_pgn INTEGER NOT NULL DEFAULT 1 CHECK (download_pgn IN (0, 1)),
    download_cbv INTEGER NOT NULL DEFAULT 0 CHECK (download_cbv IN (0, 1)),
    extract_archives INTEGER NOT NULL DEFAULT 1 CHECK (extract_archives IN (0, 1)),
    keep_zip_files INTEGER NOT NULL DEFAULT 1 CHECK (keep_zip_files IN (0, 1)),
    combine_after_sync INTEGER NOT NULL DEFAULT 0 CHECK (combine_after_sync IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    issue_number INTEGER NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('pgn', 'cbv')),
    source_url TEXT,
    zip_relative_path TEXT,
    zip_size INTEGER,
    zip_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    extracted INTEGER NOT NULL DEFAULT 0 CHECK (extracted IN (0, 1)),
    extracted_relative_path TEXT,
    last_error TEXT,
    downloaded_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE (profile_id, issue_number, format)
);
"""


@contextmanager
def connection(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    database = path or database_path()
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(path: Path | None = None) -> None:
    with connection(path) as conn:
        conn.executescript(SCHEMA)


def list_profiles() -> list[dict[str, object]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, archive_root, download_pgn, download_cbv,
                   extract_archives, keep_zip_files, combine_after_sync
            FROM profiles
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()
    return [
        {
            **dict(row),
            "download_pgn": bool(row["download_pgn"]),
            "download_cbv": bool(row["download_cbv"]),
            "extract_archives": bool(row["extract_archives"]),
            "keep_zip_files": bool(row["keep_zip_files"]),
            "combine_after_sync": bool(row["combine_after_sync"]),
        }
        for row in rows
    ]


def create_profile(
    *,
    name: str,
    archive_root: str,
    download_pgn: bool,
    download_cbv: bool,
    extract_archives: bool,
    keep_zip_files: bool,
    combine_after_sync: bool,
) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO profiles (
                name, archive_root, download_pgn, download_cbv,
                extract_archives, keep_zip_files, combine_after_sync,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                archive_root,
                download_pgn,
                download_cbv,
                extract_archives,
                keep_zip_files,
                combine_after_sync,
                now,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id, name, archive_root, download_pgn, download_cbv,
                   extract_archives, keep_zip_files, combine_after_sync
            FROM profiles WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
    assert row is not None
    return {
        **dict(row),
        "download_pgn": bool(row["download_pgn"]),
        "download_cbv": bool(row["download_cbv"]),
        "extract_archives": bool(row["extract_archives"]),
        "keep_zip_files": bool(row["keep_zip_files"]),
        "combine_after_sync": bool(row["combine_after_sync"]),
    }
