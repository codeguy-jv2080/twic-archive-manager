from pathlib import Path

from app.database import connection, create_profile, initialize_database


def test_initialization_creates_profile_table(tmp_path: Path) -> None:
    database = tmp_path / "state" / "test.db"
    initialize_database(database)

    with connection(database) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'profiles'"
        ).fetchone()

    assert table is not None


def test_profiles_keep_zip_files_by_default(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "state" / "test.db"
    monkeypatch.setattr("app.database.database_path", lambda: database)
    initialize_database(database)

    profile = create_profile(
        name="Main",
        archive_root=r"C:\\Chess\\TWIC",
        download_pgn=True,
        download_cbv=False,
        extract_archives=True,
        keep_zip_files=True,
        combine_after_sync=False,
    )

    assert profile["keep_zip_files"] is True
