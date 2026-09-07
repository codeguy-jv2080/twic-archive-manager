from __future__ import annotations

from app import cli
from app.services.archive_lock import ArchiveBusy
from app.services.sync import ConfigurationError, SyncResult


def test_sync_exit_code_is_zero_for_success(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "sync_profile",
        lambda profile: SyncResult(profile_name=profile, selected_issues=(1234,)),
    )

    assert cli.main(["sync", "--profile", "Main"]) == cli.EXIT_OK


def test_sync_exit_code_is_one_when_files_failed(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "sync_profile",
        lambda profile: SyncResult(
            profile_name=profile,
            selected_issues=(1234,),
            failures=["download failed"],
        ),
    )

    assert cli.main(["sync", "--profile", "Main"]) == cli.EXIT_FAILED


def test_unknown_or_invalid_profile_returns_code_two(monkeypatch) -> None:
    def fail(_: str):
        raise ConfigurationError("Saved Setup not found")

    monkeypatch.setattr(cli, "sync_profile", fail)

    assert cli.main(["sync", "--profile", "Missing"]) == cli.EXIT_INVALID_CONFIGURATION


def test_busy_archive_returns_failure_for_sync_and_combine(monkeypatch, capsys) -> None:
    def busy(_: str):
        raise ArchiveBusy("Another operation is already using archive folder: test")

    monkeypatch.setattr(cli, "sync_profile", busy)
    monkeypatch.setattr(cli, "combine_profile", busy)

    for command in ("sync", "combine"):
        assert cli.main([command, "--profile", "Main"]) == cli.EXIT_FAILED
        assert "Another operation is already using" in capsys.readouterr().err
