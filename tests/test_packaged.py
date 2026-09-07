"""Optional background smoke test of the canonical Windows executable."""

import os
from pathlib import Path
import subprocess

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
