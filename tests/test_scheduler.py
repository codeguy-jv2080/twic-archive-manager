from __future__ import annotations

import subprocess

import pytest

from app.services.scheduler import (
    InvalidSchedule,
    SchedulerError,
    build_create_command,
    build_sync_command,
    create_or_update_task,
    inspect_task,
    parse_schedule,
    remove_task,
    set_schedule,
    task_name_for_profile,
)


class FakeRunner:
    def __init__(self, *responses: subprocess.CompletedProcess[str]) -> None:
        self.responses = list(responses)
        self.commands: list[list[str]] = []

    def __call__(self, command) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        return self.responses.pop(0)


def completed(
    returncode: int = 0, *, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["schtasks.exe"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_schedule_formats_are_normalized() -> None:
    daily = parse_schedule(" daily 09:30 ")
    weekly = parse_schedule("weekly monday 07:05")
    monthly = parse_schedule("monthly 01 21:15")

    assert (daily.frequency, daily.start_time, daily.day, daily.normalized_text) == (
        "DAILY",
        "09:30",
        None,
        "daily 09:30",
    )
    assert (weekly.frequency, weekly.day, weekly.normalized_text) == (
        "WEEKLY",
        "MON",
        "weekly Monday 07:05",
    )
    assert (monthly.frequency, monthly.day, monthly.normalized_text) == (
        "MONTHLY",
        "1",
        "monthly 1 21:15",
    )

    with pytest.raises(InvalidSchedule, match="Choose Daily, Weekly, or Monthly"):
        parse_schedule("weekly 09:00")


def test_build_command_quotes_saved_setup_name() -> None:
    assert task_name_for_profile("Weekend games") == "TWIC Archive Manager - Weekend games"
    assert (
        build_sync_command("Weekend games")
        == 'twic-archive-manager sync --profile "Weekend games"'
    )
    assert build_create_command("Weekend games", "weekly Saturday 07:05") == [
        "schtasks.exe",
        "/Create",
        "/F",
        "/SC",
        "WEEKLY",
        "/D",
        "SAT",
        "/ST",
        "07:05",
        "/TN",
        "TWIC Archive Manager - Weekend games",
        "/TR",
        'twic-archive-manager sync --profile "Weekend games"',
    ]


def test_create_or_update_uses_schtasks_only_through_injected_runner() -> None:
    runner = FakeRunner(completed(stdout="SUCCESS: The scheduled task has been created."))

    info = create_or_update_task("Main", "monthly 15 21:15", runner=runner)

    assert info.exists is True
    assert info.schedule_text == "monthly 15 21:15"
    assert info.command == "twic-archive-manager sync --profile Main"
    assert runner.commands == [
        [
            "schtasks.exe",
            "/Create",
            "/F",
            "/SC",
            "MONTHLY",
            "/D",
            "15",
            "/ST",
            "21:15",
            "/TN",
            "TWIC Archive Manager - Main",
            "/TR",
            "twic-archive-manager sync --profile Main",
        ]
    ]


def test_inspect_and_remove_missing_task_do_not_raise() -> None:
    missing = completed(
        1, stderr="ERROR: The system cannot find the file specified."
    )
    runner = FakeRunner(missing, missing)

    assert inspect_task("Main", runner=runner).exists is False
    assert remove_task("Main", runner=runner) is False


def test_empty_schedule_removes_task() -> None:
    runner = FakeRunner(completed(stdout="SUCCESS: The scheduled task was deleted."))

    info = set_schedule("Main", "", runner=runner)

    assert info.exists is False
    assert runner.commands == [
        ["schtasks.exe", "/Delete", "/F", "/TN", "TWIC Archive Manager - Main"]
    ]


def test_scheduler_error_includes_schtasks_output() -> None:
    runner = FakeRunner(completed(1, stderr="ERROR: Access is denied."))

    with pytest.raises(SchedulerError, match="Access is denied"):
        create_or_update_task("Main", "weekly Friday 08:00", runner=runner)
