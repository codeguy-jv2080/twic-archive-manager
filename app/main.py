"""Application composition for the TWIC Archive Manager desktop window."""

from __future__ import annotations

import sys
from pathlib import Path

from .database import (
    create_profile,
    delete_profile,
    get_profile,
    get_app_setting,
    initialize_database,
    list_profiles,
    update_profile,
    set_app_setting,
)
from .services.scheduler import inspect_task, remove_task, set_schedule
from .services.sync import (
    Selection,
    SyncEvent,
    combine_profile,
    sync_profile,
)
from .ui.main_window import (
    DesktopCallbacks,
    OperationReporter,
    SavedSetup,
    SelectionRequest,
    run_desktop,
)


def _profile_identifier(setup: SavedSetup) -> int | str:
    return setup.id if setup.id is not None else setup.name


def _setup_fields(setup: SavedSetup) -> dict[str, object]:
    return {
        "name": setup.name,
        "archive_root": setup.archive_root,
        "download_pgn": setup.download_pgn,
        "download_cbv": setup.download_cbv,
        "extract_archives": setup.extract_archives,
        "keep_zip_files": setup.keep_zip_files,
        "default_selection_mode": setup.default_selection_mode.value,
        "default_selection_value": setup.default_selection_value,
        "combine_after_sync": setup.combine_after_sync,
    }


def _selection_from_request(request: SelectionRequest) -> Selection:
    if request.mode.value == "latest":
        return Selection.latest(request.latest_count or 1)
    if request.mode.value == "range":
        if request.start_issue is None or request.end_issue is None:
            raise ValueError("An issue range needs a first and last issue.")
        return Selection.issue_range(request.start_issue, request.end_issue)
    if request.start_issue is None:
        raise ValueError("Choose a starting issue.")
    return Selection.through_newest(request.start_issue)


def _report_sync_event(reporter: OperationReporter, event: SyncEvent) -> None:
    reporter.progress(event.completed, event.total, event.message)
    reporter.status(event.message)
    reporter.log(event.message)


def _sync_message(result: object) -> str:
    downloaded = int(getattr(result, "downloaded", 0))
    skipped = int(getattr(result, "skipped", 0))
    extracted = int(getattr(result, "extracted", 0))
    failures = list(getattr(result, "failures", []))
    if getattr(result, "cancelled", False):
        return "Sync canceled."
    if failures:
        return f"Sync finished with {len(failures)} failed file(s)."
    return (
        f"Sync complete: {downloaded} ZIP file(s) downloaded, "
        f"{skipped} already present, {extracted} extracted."
    )


def _scheduler_executable() -> str | tuple[str, ...]:
    """Return the command Windows Task Scheduler should invoke headlessly."""

    main_module = sys.modules.get("__main__")
    if (
        getattr(sys, "frozen", False)
        or "__compiled__" in globals()
        or hasattr(main_module, "__compiled__")
    ):
        launched_executable = Path(sys.argv[0])
        if launched_executable.suffix.casefold() == ".exe":
            return str(launched_executable.resolve())
        return sys.executable
    return (sys.executable, "-m", "app")


def create_desktop_callbacks() -> DesktopCallbacks:
    """Create the small set of application actions used by the Qt window."""

    def load_theme() -> str:
        initialize_database()
        return get_app_setting("theme", "dark")

    def save_theme(theme: str) -> None:
        if theme not in {"light", "dark"}:
            raise ValueError("Choose light or dark mode.")
        initialize_database()
        set_app_setting("theme", theme)

    def load_setups() -> list[dict[str, object]]:
        initialize_database()
        return list_profiles()

    def save_setup(setup: SavedSetup) -> dict[str, object]:
        initialize_database()
        fields = _setup_fields(setup)
        if setup.id is None:
            return create_profile(**fields)
        existing = get_profile(setup.id)
        if existing is None:
            raise ValueError("That Saved Setup no longer exists.")
        old_name = str(existing["name"])
        old_schedule = str(existing.get("schedule_text", "")).strip()
        if old_name.casefold() != setup.name.casefold():
            occupying = get_profile(setup.name)
            if occupying is not None and int(occupying["id"]) != setup.id:
                raise ValueError("A Saved Setup with that name already exists.")

        new_task_created = False
        old_task_removed = False
        if old_name.casefold() != setup.name.casefold() and old_schedule:
            set_schedule(
                setup.name,
                old_schedule,
                executable=_scheduler_executable(),
            )
            new_task_created = True
            try:
                old_task_removed = remove_task(old_name)
            except Exception:
                if new_task_created:
                    try:
                        remove_task(setup.name)
                    except Exception:
                        pass
                raise

        def rollback_renamed_schedule() -> None:
            if old_task_removed:
                try:
                    set_schedule(
                        old_name,
                        old_schedule,
                        executable=_scheduler_executable(),
                    )
                except Exception:
                    pass
            if new_task_created:
                try:
                    remove_task(setup.name)
                except Exception:
                    pass

        try:
            saved = update_profile(setup.id, **fields)
        except Exception:
            rollback_renamed_schedule()
            raise
        if saved is None:
            rollback_renamed_schedule()
            raise ValueError("That Saved Setup no longer exists.")
        return saved

    def delete_setup(setup: SavedSetup) -> None:
        initialize_database()
        existing = get_profile(_profile_identifier(setup))
        if existing is None:
            return
        name = str(existing["name"])
        schedule_text = str(existing.get("schedule_text", "")).strip()
        task_removed = remove_task(name) if schedule_text else False
        try:
            deleted = delete_profile(int(existing["id"]))
        except Exception:
            if task_removed:
                try:
                    set_schedule(
                        name,
                        schedule_text,
                        executable=_scheduler_executable(),
                    )
                except Exception:
                    pass
            raise
        if not deleted:
            if task_removed:
                try:
                    set_schedule(
                        name,
                        schedule_text,
                        executable=_scheduler_executable(),
                    )
                except Exception:
                    pass
            raise ValueError("That Saved Setup no longer exists.")

    def sync(setup: SavedSetup, request: SelectionRequest, reporter: OperationReporter) -> dict[str, str]:
        result = sync_profile(
            _profile_identifier(setup),
            selection=_selection_from_request(request),
            on_event=lambda event: _report_sync_event(reporter, event),
            is_cancelled=lambda: reporter.cancelled,
        )
        return {"message": _sync_message(result)}

    def combine(setup: SavedSetup, reporter: OperationReporter) -> dict[str, str]:
        reporter.status("Combining extracted PGNs…")
        result = combine_profile(_profile_identifier(setup))
        message = f"Combined {result.pgn_files} PGN file(s) into {result.output_path.name}."
        reporter.progress(1, 1, message)
        return {"message": message}

    def apply_schedule(setup: SavedSetup, schedule_text: str) -> dict[str, str]:
        info = set_schedule(
            setup.name,
            schedule_text,
            executable=_scheduler_executable(),
        )
        saved = update_profile(
            _profile_identifier(setup), schedule_text=info.schedule_text or ""
        )
        if saved is None:
            raise ValueError("That Saved Setup no longer exists.")
        if info.exists:
            return {"message": f'Schedule set for "{setup.name}": {info.schedule_text}.'}
        return {"message": f'Automatic schedule removed for "{setup.name}".'}

    def view_schedule(setup: SavedSetup) -> dict[str, str]:
        info = inspect_task(setup.name)
        if not info.exists:
            return {"message": f'No Windows schedule exists for "{setup.name}".'}
        details = info.details.strip()
        stored = setup.schedule_text or "automatic schedule"
        return {
            "message": (
                f'Schedule for "{setup.name}": {stored}.\n\n'
                f'{details or "Task exists."}\n\n'
                "If you move the portable app folder, click Apply Schedule again."
            )
        }

    return DesktopCallbacks(
        load_setups=load_setups,
        save_setup=save_setup,
        delete_setup=delete_setup,
        sync=sync,
        combine=combine,
        apply_schedule=apply_schedule,
        view_schedule=view_schedule,
        load_theme=load_theme,
        save_theme=save_theme,
    )


def run_desktop_app() -> int:
    initialize_database()
    return run_desktop(create_desktop_callbacks())


if __name__ == "__main__":
    raise SystemExit(run_desktop_app())
