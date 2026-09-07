from pathlib import Path
import subprocess
import sys

import pytest

from app.services.archive_lock import ArchiveBusy, archive_operation
from app.services.sync import Selection, combine_profile, sync_profile


def run_child(code: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code, str(root)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def test_same_archive_is_blocked_across_processes_and_released(tmp_path: Path) -> None:
    code = """
import sys
from app.services.archive_lock import ArchiveBusy, archive_operation
try:
    with archive_operation(sys.argv[1]):
        pass
except ArchiveBusy:
    sys.exit(42)
"""
    root = tmp_path / "archive"
    with archive_operation(root):
        blocked = run_child(code, root)
        assert blocked.returncode == 42, blocked.stderr
        different = run_child(code, tmp_path / "other")
        assert different.returncode == 0, different.stderr
        with pytest.raises(ArchiveBusy):
            with archive_operation(str(root).upper()):
                pytest.fail("Case changes must not bypass the archive lock")

    released = run_child(code, root)
    assert released.returncode == 0, released.stderr
    assert not root.exists()  # No persistent lock file or directory.


def test_process_exit_releases_archive_without_cleanup(tmp_path: Path) -> None:
    result = run_child("""
import os, sys
from app.services.archive_lock import archive_operation
with archive_operation(sys.argv[1]):
    os._exit(0)
""", tmp_path)
    assert result.returncode == 0, result.stderr
    with archive_operation(tmp_path):
        pass


def test_sync_and_combine_share_the_archive_lock(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    root = tmp_path / "archive"
    profile = {"name": "Main", "archive_root": str(root), "download_pgn": True}
    with archive_operation(root):
        with pytest.raises(ArchiveBusy):
            sync_profile(profile, newest_issue_loader=lambda: pytest.fail("Must not read newest issue"))
        with pytest.raises(ArchiveBusy):
            combine_profile(profile)
    assert not root.exists()


def test_sync_exception_releases_archive(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    profile = {"name": "Main", "archive_root": str(tmp_path / "archive"), "download_pgn": True}

    def failed_newest_lookup():
        raise OSError("Test newest-issue failure")

    with pytest.raises(OSError, match="Test newest-issue failure"):
        sync_profile(profile, newest_issue_loader=failed_newest_lookup)
    result = sync_profile(
        profile,
        selection=Selection.issue_range(970, 970),
        newest_issue_loader=lambda: pytest.fail("A fixed range must not read the page"),
        is_cancelled=lambda: True,
    )
    assert result.cancelled
