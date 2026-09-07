import sqlite3
from pathlib import Path

from app.database import (
    connection,
    create_profile,
    delete_profile,
    get_profile,
    get_app_setting,
    initialize_database,
    list_profiles,
    update_profile,
    set_app_setting,
)


def test_initialization_creates_setups_and_preferences_without_issue_tracking(tmp_path: Path) -> None:
    database = tmp_path / "state" / "test.db"
    initialize_database(database)

    with connection(database) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "profiles" in tables
    assert "app_settings" in tables
    assert "artifacts" not in tables


def test_saved_setup_defaults_and_lookup(tmp_path: Path) -> None:
    database = tmp_path / "state" / "test.db"
    initialize_database(database)

    profile = create_profile(name="Main", archive_root=r"C:\Chess\TWIC", path=database)

    assert profile["keep_zip_files"] is True
    assert profile["default_selection_mode"] == "latest_n"
    assert profile["default_selection_value"] == "1"
    assert profile["combine_after_sync"] is False
    assert profile["schedule_text"] == ""
    assert get_profile("main", database) == get_profile(profile["id"], database)
    assert list_profiles(database) == [profile]


def test_theme_preference_survives_reinitialization_without_changing_setups(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    initialize_database(database)
    setup = create_profile(name="Existing", archive_root=r"C:\Chess\TWIC", path=database)
    assert get_app_setting("theme", "dark", database) == "dark"
    set_app_setting("theme", "light", database)
    initialize_database(database)
    assert get_app_setting("theme", "dark", database) == "light"
    assert get_profile("Existing", database) == setup
    set_app_setting("theme", "dark", database)
    assert get_app_setting("theme", path=database) == "dark"


def test_saved_setup_can_be_updated_and_deleted(tmp_path: Path) -> None:
    database = tmp_path / "state" / "test.db"
    initialize_database(database)
    profile = create_profile(name="Main", archive_root=r"C:\Chess\TWIC", path=database)

    updated = update_profile(
        profile["id"],
        name="Weekly",
        download_cbv=True,
        keep_zip_files=False,
        default_selection_mode="range",
        default_selection_value="1234-1240",
        combine_after_sync=True,
        schedule_text="Every Sunday at 08:00",
        path=database,
    )

    assert updated is not None
    assert updated["name"] == "Weekly"
    assert updated["archive_root"] == r"C:\Chess\TWIC"
    assert updated["download_cbv"] is True
    assert updated["keep_zip_files"] is False
    assert updated["default_selection_mode"] == "range"
    assert updated["default_selection_value"] == "1234-1240"
    assert updated["combine_after_sync"] is True
    assert updated["schedule_text"] == "Every Sunday at 08:00"
    assert delete_profile("weekly", database) is True
    assert get_profile(profile["id"], database) is None
    assert delete_profile(profile["id"], database) is False


def test_initialization_removes_legacy_artifact_tracking(tmp_path: Path) -> None:
    database = tmp_path / "state" / "test.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE artifacts (id INTEGER PRIMARY KEY)")

    initialize_database(database)

    with connection(database) as conn:
        artifact_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'artifacts'"
        ).fetchone()
    assert artifact_table is None


def test_existing_starter_profile_database_gains_saved_setup_fields(tmp_path: Path) -> None:
    database = tmp_path / "state" / "test.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                archive_root TEXT NOT NULL,
                download_pgn INTEGER NOT NULL DEFAULT 1,
                download_cbv INTEGER NOT NULL DEFAULT 0,
                extract_archives INTEGER NOT NULL DEFAULT 1,
                keep_zip_files INTEGER NOT NULL DEFAULT 1,
                combine_after_sync INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO profiles (name, archive_root, created_at, updated_at)
            VALUES ('Existing', 'C:/Chess/TWIC', '2026-01-01', '2026-01-01')
            """
        )

    initialize_database(database)

    profile = get_profile("Existing", database)
    assert profile is not None
    assert profile["default_selection_mode"] == "latest_n"
    assert profile["default_selection_value"] == "1"
    assert profile["schedule_text"] == ""
