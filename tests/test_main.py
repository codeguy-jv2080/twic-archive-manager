from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from app import main
from app.services.scheduler import ScheduledTaskInfo
from app.ui.main_window import OperationReporter, SavedSetup, SelectionMode, SelectionRequest


def _reporter() -> OperationReporter:
    return OperationReporter(lambda *_: None, lambda _: None, lambda _: None, Event())


def test_desktop_callbacks_save_and_store_schedule(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "state" / "twic.db"
    monkeypatch.setattr("app.database.database_path", lambda: database)
    callbacks = main.create_desktop_callbacks()
    setup = SavedSetup(
        name="Main",
        archive_root=str(tmp_path / "archive"),
        default_selection_mode=SelectionMode.LATEST,
        default_selection_value="1",
    )

    saved = SavedSetup.from_value(callbacks.save_setup(setup))
    assert saved.id is not None

    scheduled: list[tuple[str, str]] = []
    removed: list[str] = []

    def set_schedule(profile_name: str, schedule_text: str, **_kwargs) -> ScheduledTaskInfo:
        scheduled.append((profile_name, schedule_text))
        return ScheduledTaskInfo(
            profile_name=profile_name,
            task_name=f"TWIC Archive Manager - {profile_name}",
            exists=True,
            schedule_text=schedule_text,
        )

    monkeypatch.setattr(main, "set_schedule", set_schedule)
    monkeypatch.setattr(main, "remove_task", lambda profile_name: removed.append(profile_name) or True)
    assert callbacks.apply_schedule(saved, "weekly Monday 09:00") == {
        "message": 'Schedule set for "Main": weekly Monday 09:00.'
    }
    scheduled_setup = SavedSetup.from_value(callbacks.load_setups()[0])
    assert scheduled_setup.schedule_text == "weekly Monday 09:00"

    renamed = SavedSetup.from_value(
        callbacks.save_setup(replace(scheduled_setup, name="Renamed"))
    )
    assert renamed.schedule_text == "weekly Monday 09:00"
    assert scheduled == [
        ("Main", "weekly Monday 09:00"),
        ("Renamed", "weekly Monday 09:00"),
    ]
    assert removed == ["Main"]

    callbacks.delete_setup(renamed)
    assert removed == ["Main", "Renamed"]
    assert callbacks.load_setups() == []


def test_save_does_not_claim_an_unapplied_schedule(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "state" / "twic.db"
    monkeypatch.setattr("app.database.database_path", lambda: database)
    callbacks = main.create_desktop_callbacks()

    saved = callbacks.save_setup(
        SavedSetup(
            name="Main",
            archive_root=str(tmp_path / "archive"),
            schedule_text="monthly 15 09:00",
        )
    )

    assert saved["schedule_text"] == ""


def test_scheduler_uses_the_packaged_executable_for_nuitka(monkeypatch) -> None:
    monkeypatch.setitem(main.__dict__, "__compiled__", object())
    monkeypatch.setattr(main.sys, "argv", [r"C:\portable\TWIC Archive Manager.exe"])
    monkeypatch.setattr(main.sys, "executable", r"C:\portable\python.exe")

    assert main._scheduler_executable() == r"C:\portable\TWIC Archive Manager.exe"


def test_theme_choice_is_remembered_across_callback_instances(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "test.db")
    callbacks = main.create_desktop_callbacks()
    assert callbacks.load_theme() == "dark"
    callbacks.save_theme("light")
    assert main.create_desktop_callbacks().load_theme() == "light"


@pytest.mark.parametrize("identifier", [7, "Example"])
def test_extract_callback_uses_saved_setup_and_reports_progress_once(monkeypatch, identifier):
    messages, statuses, progress = [], [], []
    cancel = Event()
    reporter = OperationReporter(
        lambda *values: progress.append(values), messages.append, statuses.append, cancel,
    )
    setup = SavedSetup(
        id=identifier if isinstance(identifier, int) else None,
        name="Example", archive_root=r"C:\Archive",
    )

    def extract(selected, *, on_event, is_cancelled):
        assert selected == identifier
        assert not is_cancelled()
        cancel.set()
        assert is_cancelled()
        cancel.clear()
        on_event(main.SyncEvent("extract", "Extracting TWIC 970 PGN.", completed=0, total=3))
        return SimpleNamespace(extracted=2, skipped=1, failures=[], cancelled=False, total=3)

    monkeypatch.setattr(main, "extract_profile", extract)
    result = main.create_desktop_callbacks().extract(setup, reporter)
    expected = "Extraction complete: 2 ZIP file(s) extracted, 1 already extracted, 0 failed."
    assert result == {"message": expected}
    assert messages == ["Extracting TWIC 970 PGN."]
    assert statuses == ["Extracting TWIC 970 PGN."]
    assert progress[-1] == (3, 3, expected)


@pytest.mark.parametrize("extracted,skipped,failures,cancelled,expected", [
    (0, 0, [], False, "Extraction complete: 0 ZIP file(s) extracted, 0 already extracted, 0 failed."),
    (2, 1, ["Bad ZIP"], False, "Extraction complete: 2 ZIP file(s) extracted, 1 already extracted, 1 failed."),
    (1, 0, [], True, "Extraction canceled."),
])
def test_extract_result_message(extracted, skipped, failures, cancelled, expected):
    result = SimpleNamespace(extracted=extracted, skipped=skipped, failures=failures, cancelled=cancelled)
    assert main._extract_message(result) == expected


def test_empty_extract_callback_reports_no_downloaded_zips(monkeypatch):
    result = SimpleNamespace(extracted=0, skipped=0, failures=[], cancelled=False, total=0)
    monkeypatch.setattr(main, "extract_profile", lambda *_args, **_kwargs: result)
    progress = []
    reporter = OperationReporter(lambda *args: progress.append(args), lambda _: None, lambda _: None, Event())
    final = main.create_desktop_callbacks().extract(SavedSetup(name="Example", archive_root=r"C:\Archive"), reporter)
    expected = "No downloaded TWIC ZIP files found for the selected formats."
    assert final == {"message": expected}
    assert progress == [(1, 1, expected)]
