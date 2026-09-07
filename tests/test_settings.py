from pathlib import Path

from app import settings
from app.database import (
    create_profile, get_app_setting, initialize_database, list_profiles,
    set_app_setting,
)


def test_installed_starts_empty_without_modifying_portable_data(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    portable_exe = tmp_path / "portable" / "TWIC Archive Manager.exe"
    installed_exe = tmp_path / "installed" / "TWIC Archive Manager.exe"
    installed_exe.parent.mkdir()
    (installed_exe.parent / settings.INSTALLATION_MARKER).write_text("installed\n")

    monkeypatch.setattr(settings.sys, "argv", [str(portable_exe)])
    portable_db = settings.database_path()
    assert portable_db.parent.name == "state"
    initialize_database()
    setup = create_profile(name="Portable fixture", archive_root=str(tmp_path / "archive"))
    set_app_setting("theme", "light")
    original = portable_db.read_bytes()

    monkeypatch.setattr(settings.sys, "argv", [str(installed_exe)])
    installed_db = settings.database_path()
    assert installed_db.parent.name == "installed-state"
    assert installed_db != portable_db
    initialize_database()
    assert list_profiles() == []
    assert get_app_setting("theme", "dark") == "dark"
    assert portable_db.read_bytes() == original

    installed_setup = create_profile(name="Installed fixture", archive_root=str(tmp_path / "other"))
    set_app_setting("theme", "dark")
    initialize_database()  # An upgrade/restart retains this installation's choices.
    assert list_profiles() == [installed_setup]
    assert portable_db.read_bytes() == original

    monkeypatch.setattr(settings.sys, "argv", [str(portable_exe)])
    assert list_profiles() == [setup]
    assert get_app_setting("theme", "dark") == "light"


def test_marker_is_relative_to_executable_not_working_directory(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / settings.INSTALLATION_MARKER).write_text("installed\n")
    monkeypatch.chdir(work)
    monkeypatch.setattr(settings.sys, "argv", [str(tmp_path / "portable" / "app.exe")])
    assert not settings.is_installed()


def test_local_appdata_fallback_keeps_distribution_separation(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(settings, "is_installed", lambda: True)
    assert settings.database_path() == (
        tmp_path / "AppData" / "Local" / settings.APP_NAME
        / "installed-state" / "twic-archive-manager.db"
    )
