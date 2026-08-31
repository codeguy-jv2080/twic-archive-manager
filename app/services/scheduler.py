"""Small Windows Task Scheduler wrapper for saved TWIC setups."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import re
import subprocess


TASK_PREFIX = "TWIC Archive Manager - "
WEEKDAYS = {
    "monday": ("Monday", "MON"),
    "tuesday": ("Tuesday", "TUE"),
    "wednesday": ("Wednesday", "WED"),
    "thursday": ("Thursday", "THU"),
    "friday": ("Friday", "FRI"),
    "saturday": ("Saturday", "SAT"),
    "sunday": ("Sunday", "SUN"),
}
DAILY_SCHEDULE_PATTERN = re.compile(
    r"^daily\s+([01]\d|2[0-3]):([0-5]\d)$", re.IGNORECASE
)
WEEKLY_SCHEDULE_PATTERN = re.compile(
    r"^weekly\s+([a-z]+)\s+([01]\d|2[0-3]):([0-5]\d)$", re.IGNORECASE
)
MONTHLY_SCHEDULE_PATTERN = re.compile(
    r"^monthly\s+(0?[1-9]|[12]\d|3[01])\s+([01]\d|2[0-3]):([0-5]\d)$",
    re.IGNORECASE,
)

TaskRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class SchedulerError(RuntimeError):
    """Windows Task Scheduler could not complete the requested action."""


class InvalidSchedule(ValueError):
    """A Saved Setup's schedule text is not supported."""


@dataclass(frozen=True, slots=True)
class ScheduleSpec:
    """Normalized values needed by Windows Task Scheduler."""

    frequency: str
    start_time: str
    normalized_text: str
    day: str | None = None


@dataclass(frozen=True, slots=True)
class ScheduledTaskInfo:
    """The small amount of schedule state the desktop window needs to show."""

    profile_name: str
    task_name: str
    exists: bool
    schedule_text: str | None = None
    command: str | None = None
    details: str = ""


def parse_schedule(schedule_text: str) -> ScheduleSpec:
    """Validate and normalize a daily, weekly, or monthly schedule."""

    text = schedule_text.strip()
    daily = DAILY_SCHEDULE_PATTERN.fullmatch(text)
    if daily:
        time = f"{daily.group(1)}:{daily.group(2)}"
        return ScheduleSpec("DAILY", time, f"daily {time}")

    weekly = WEEKLY_SCHEDULE_PATTERN.fullmatch(text)
    weekday = WEEKDAYS.get(weekly.group(1).casefold()) if weekly else None
    if weekly and weekday:
        time = f"{weekly.group(2)}:{weekly.group(3)}"
        return ScheduleSpec(
            "WEEKLY", time, f"weekly {weekday[0]} {time}", weekday[1]
        )

    monthly = MONTHLY_SCHEDULE_PATTERN.fullmatch(text)
    if monthly:
        day = str(int(monthly.group(1)))
        time = f"{monthly.group(2)}:{monthly.group(3)}"
        return ScheduleSpec("MONTHLY", time, f"monthly {day} {time}", day)

    raise InvalidSchedule("Choose Daily, Weekly, or Monthly and enter its required values.")


def task_name_for_profile(profile_name: str) -> str:
    """Return the stable Windows task name for one Saved Setup."""

    name = _validate_profile_name(profile_name)
    return f"{TASK_PREFIX}{name}"


def build_sync_command(
    profile_name: str, *, executable: str | Sequence[str] = "twic-archive-manager"
) -> str:
    """Build the command Task Scheduler should run without using a shell."""

    name = _validate_profile_name(profile_name)
    executable_parts = [executable] if isinstance(executable, str) else list(executable)
    if not executable_parts or not all(str(part).strip() for part in executable_parts):
        raise ValueError("A command to launch the headless sync is required.")
    return subprocess.list2cmdline([*map(str, executable_parts), "sync", "--profile", name])


def build_create_command(
    profile_name: str,
    schedule_text: str,
    *,
    executable: str | Sequence[str] = "twic-archive-manager",
) -> list[str]:
    """Build, but do not execute, the schtasks command for a sync."""

    schedule = parse_schedule(schedule_text)
    task_name = task_name_for_profile(profile_name)
    command = build_sync_command(profile_name, executable=executable)
    result = [
        "schtasks.exe",
        "/Create",
        "/F",
        "/SC",
        schedule.frequency,
    ]
    if schedule.day is not None:
        result.extend(["/D", schedule.day])
    result.extend(["/ST", schedule.start_time, "/TN", task_name, "/TR", command])
    return result


def create_or_update_task(
    profile_name: str,
    schedule_text: str,
    *,
    executable: str | Sequence[str] = "twic-archive-manager",
    runner: TaskRunner | None = None,
) -> ScheduledTaskInfo:
    """Create or replace the profile's headless-sync task."""

    command = build_create_command(profile_name, schedule_text, executable=executable)
    _run(command, operation="create or update", runner=runner)
    schedule = parse_schedule(schedule_text)
    name = _validate_profile_name(profile_name)
    return ScheduledTaskInfo(
        profile_name=name,
        task_name=task_name_for_profile(name),
        exists=True,
        schedule_text=schedule.normalized_text,
        command=build_sync_command(name, executable=executable),
    )


def inspect_task(
    profile_name: str, *, runner: TaskRunner | None = None
) -> ScheduledTaskInfo:
    """Check whether a Saved Setup's Windows task exists.

    ``schtasks`` does not provide a stable, locale-independent format for all
    of its detailed fields, so this deliberately returns existence plus the
    command's own output rather than attempting a brittle parse.
    """

    name = _validate_profile_name(profile_name)
    task_name = task_name_for_profile(name)
    command = ["schtasks.exe", "/Query", "/TN", task_name, "/FO", "LIST"]
    result = _invoke(command, runner=runner)
    if result.returncode == 0:
        return ScheduledTaskInfo(
            profile_name=name,
            task_name=task_name,
            exists=True,
            details=_result_text(result),
        )
    if _task_is_missing(result):
        return ScheduledTaskInfo(profile_name=name, task_name=task_name, exists=False)
    _raise_command_error("inspect", task_name, result)


def remove_task(profile_name: str, *, runner: TaskRunner | None = None) -> bool:
    """Remove the profile's task, returning ``False`` when it was not present."""

    name = _validate_profile_name(profile_name)
    task_name = task_name_for_profile(name)
    result = _invoke(
        ["schtasks.exe", "/Delete", "/F", "/TN", task_name], runner=runner
    )
    if result.returncode == 0:
        return True
    if _task_is_missing(result):
        return False
    _raise_command_error("remove", task_name, result)


def set_schedule(
    profile_name: str,
    schedule_text: str,
    *,
    executable: str | Sequence[str] = "twic-archive-manager",
    runner: TaskRunner | None = None,
) -> ScheduledTaskInfo:
    """Apply an optional schedule; an empty value removes the existing task."""

    if not schedule_text.strip():
        name = _validate_profile_name(profile_name)
        remove_task(name, runner=runner)
        return ScheduledTaskInfo(
            profile_name=name,
            task_name=task_name_for_profile(name),
            exists=False,
        )
    return create_or_update_task(
        profile_name, schedule_text, executable=executable, runner=runner
    )


def _validate_profile_name(profile_name: str) -> str:
    name = str(profile_name).strip()
    if not name:
        raise ValueError("A Saved Setup name is required for scheduling.")
    if "\x00" in name or "\r" in name or "\n" in name:
        raise ValueError("Saved Setup names for scheduling cannot contain line breaks.")
    if "\\" in name:
        raise ValueError("Saved Setup names for scheduling cannot contain backslashes.")
    return name


def _default_runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )


def _invoke(
    command: Sequence[str], *, runner: TaskRunner | None
) -> subprocess.CompletedProcess[str]:
    try:
        return (runner or _default_runner)(command)
    except OSError as error:
        raise SchedulerError(
            "Windows Task Scheduler (schtasks.exe) could not be started: "
            f"{error}"
        ) from error


def _run(
    command: Sequence[str], *, operation: str, runner: TaskRunner | None
) -> subprocess.CompletedProcess[str]:
    result = _invoke(command, runner=runner)
    if result.returncode != 0:
        task_name = _argument_value(command, "/TN") or "the Saved Setup task"
        _raise_command_error(operation, task_name, result)
    return result


def _argument_value(command: Sequence[str], option: str) -> str | None:
    try:
        index = list(command).index(option)
    except ValueError:
        return None
    return str(command[index + 1]) if index + 1 < len(command) else None


def _result_text(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        text.strip() for text in (result.stdout, result.stderr) if text and text.strip()
    )


def _task_is_missing(result: subprocess.CompletedProcess[str]) -> bool:
    message = _result_text(result).lower()
    return any(
        marker in message
        for marker in (
            "cannot find the file",
            "cannot find the specified task",
            "does not exist",
            "not found",
            "0x80070002",
        )
    )


def _raise_command_error(
    operation: str, task_name: str, result: subprocess.CompletedProcess[str]
) -> None:
    detail = _result_text(result) or f"schtasks.exe exited with code {result.returncode}."
    raise SchedulerError(
        f"Windows Task Scheduler could not {operation} task '{task_name}': {detail}"
    )
