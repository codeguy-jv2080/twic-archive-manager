"""Optional background smoke test of the canonical Windows executable."""

import os
from pathlib import Path
import subprocess
import sqlite3

import pytest

from app.database import create_profile, initialize_database
from app.services.archive import ArchiveLayout
from app.services.archive_lock import archive_operation


@pytest.mark.skipif(not os.environ.get("TWIC_PACKAGED_EXE"), reason="Requires a built Windows executable")
def test_packaged_combine_and_archive_contention(tmp_path: Path, monkeypatch) -> None:
    executable = Path(os.environ["TWIC_PACKAGED_EXE"]).resolve(strict=True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    initialize_database()
    root = tmp_path / "archive"
    create_profile(name="Package test", archive_root=str(root))
    layout = ArchiveLayout.create(root)
    extracted = layout.extraction_directory("pgn")
    (extracted / "twic10.pgn").write_text('[Event "ten"]\n', encoding="utf-8")
    (extracted / "twic20.pgn").write_text('[Event "twenty"]\n', encoding="utf-8")

    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(executable), *arguments], capture_output=True, text=True,
            timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    help_result = run("--help")
    assert help_result.returncode == 0, help_result.stderr
    combined = run("combine", "--profile", "Package test")
    assert combined.returncode == 0, combined.stderr
    expected = '[Event "ten"]\n\n\n[Event "twenty"]\n'
    assert layout.combined_pgn_path.read_text(encoding="utf-8") == expected

    with archive_operation(root):
        for command in ("combine", "sync"):
            blocked = run(command, "--profile", "Package test")
            assert blocked.returncode == 1, blocked.stderr
    assert layout.combined_pgn_path.read_text(encoding="utf-8") == expected
    released = run("combine", "--profile", "Package test")
    assert released.returncode == 0, released.stderr


@pytest.mark.skipif(not os.environ.get("TWIC_INSTALLED_EXE"), reason="Requires the installed Windows executable")
def test_installed_executable_uses_empty_separate_settings(tmp_path, monkeypatch):
    executable = Path(os.environ["TWIC_INSTALLED_EXE"]).resolve(strict=True)
    assert (executable.parent / "twic-installed.flag").is_file()
    appdata = tmp_path / "clean-user-data"
    monkeypatch.setenv("LOCALAPPDATA", str(appdata))
    initialize_database()
    portable_root = tmp_path / "portable-archive"
    portable = create_profile(name="Portable fixture", archive_root=str(portable_root))
    portable_db = appdata / "TWIC Archive Manager" / "state" / "twic-archive-manager.db"
    before = portable_db.read_bytes()

    def run():
        return subprocess.run(
            [str(executable), "combine", "--profile", "Portable fixture"],
            capture_output=True, text=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    fresh = run()
    assert fresh.returncode == 2, fresh.stderr
    assert "Saved Setup not found" in fresh.stderr
    installed_db = appdata / "TWIC Archive Manager" / "installed-state" / "twic-archive-manager.db"
    with sqlite3.connect(installed_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM app_settings").fetchone()[0] == 0
    assert portable_db.read_bytes() == before

    installed_root = tmp_path / "installed-archive"
    layout = ArchiveLayout.create(installed_root)
    (layout.extraction_directory("pgn") / "twic1.pgn").write_text('[Event "installed"]\n')
    create_profile(name=portable["name"], archive_root=str(installed_root), path=installed_db)
    for _ in range(2):
        result = run()
        assert result.returncode == 0, result.stderr
        assert str(layout.combined_pgn_path) in result.stdout.replace("\\\\", "\\")
    assert layout.combined_pgn_path.read_text() == '[Event "installed"]\n'
    assert not portable_root.exists()
    assert portable_db.read_bytes() == before
