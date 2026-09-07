from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import re
from typing import Literal

from ..database import get_profile, initialize_database
from .archive import (
    ArchiveLayout,
    ArchiveRootUnavailable,
    CombineResult,
    DownloadCancelled,
    NoExtractedPgns,
    combine_extracted_pgns,
    download_file,
    extract_zip,
)
from .archive_lock import archive_operation
from .catalog import CatalogError, TwicIssue, fetch_latest_issue, numbered_issue


SelectionMode = Literal["range", "from-through-newest", "latest"]
EventCallback = Callable[["SyncEvent"], None]
CancelledCallback = Callable[[], bool]
NewestIssueLoader = Callable[[], int]


class ConfigurationError(ValueError):
    """A profile has settings which cannot be used for a sync."""


class UnknownProfile(ConfigurationError):
    """The requested saved setup does not exist."""


class SyncCancelled(RuntimeError):
    """Kept as a public marker for callers that need to signal cancellation."""


@dataclass(frozen=True, slots=True)
class Selection:
    """A saved TWIC issue selection."""

    mode: SelectionMode = "latest"
    start_issue: int | None = None
    end_issue: int | None = None
    latest_count: int | None = 1

    @classmethod
    def latest(cls, count: int = 1) -> "Selection":
        return cls(mode="latest", latest_count=count)

    @classmethod
    def issue_range(cls, start_issue: int, end_issue: int) -> "Selection":
        return cls(mode="range", start_issue=start_issue, end_issue=end_issue, latest_count=None)

    @classmethod
    def through_newest(cls, start_issue: int) -> "Selection":
        return cls(mode="from-through-newest", start_issue=start_issue, latest_count=None)

@dataclass(frozen=True, slots=True)
class SyncEvent:
    kind: Literal["info", "download", "extract", "failure", "complete", "canceled"]
    message: str
    issue_number: int | None = None
    archive_format: str | None = None
    completed: int = 0
    total: int = 0


@dataclass(slots=True)
class SyncResult:
    profile_name: str
    selected_issues: tuple[int, ...]
    downloaded: int = 0
    skipped: int = 0
    extracted: int = 0
    failures: list[str] = field(default_factory=list)
    cancelled: bool = False
    combined: CombineResult | None = None

    @property
    def succeeded(self) -> bool:
        return not self.cancelled and not self.failures


@dataclass(slots=True)
class ExtractResult:
    profile_name: str
    total: int = 0
    extracted: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)
    cancelled: bool = False


def _normalise_mode(value: object) -> SelectionMode:
    mode = str(value or "latest").strip().lower().replace("_", "-")
    aliases: dict[str, SelectionMode] = {
        "range": "range",
        "from": "from-through-newest",
        "from-through-newest": "from-through-newest",
        "through-newest": "from-through-newest",
        "latest": "latest",
        "latest-n": "latest",
    }
    try:
        return aliases[mode]
    except KeyError as error:
        raise ConfigurationError(f"Unknown default selection mode: {value!r}") from error


def selection_from_profile(profile: dict[str, object]) -> Selection:
    """Read the compact saved selection convention used by a Saved Setup."""

    mode = _normalise_mode(profile.get("default_selection_mode"))
    raw_value = profile.get("default_selection_value")
    value = str(raw_value).strip() if raw_value is not None else ""

    if mode == "latest":
        if not value:
            return Selection.latest(1)
        try:
            return Selection.latest(int(value))
        except ValueError as error:
            raise ConfigurationError("Latest N must be a whole number.") from error

    if mode == "from-through-newest":
        try:
            return Selection.through_newest(int(value))
        except ValueError as error:
            raise ConfigurationError("From issue must be a whole number.") from error

    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", value)
    if not match:
        raise ConfigurationError("Issue range must look like 1234-1240.")
    return Selection.issue_range(int(match.group(1)), int(match.group(2)))


def _validate_selection(selection: Selection) -> None:
    if selection.mode == "latest":
        if selection.latest_count is None or selection.latest_count < 1:
            raise ConfigurationError("Latest N must be at least 1.")
    elif selection.mode == "from-through-newest":
        if selection.start_issue is None or selection.start_issue < 1:
            raise ConfigurationError("From issue must be at least 1.")
    elif selection.mode == "range":
        if selection.start_issue is None or selection.end_issue is None:
            raise ConfigurationError("An issue range needs both a start and an end.")
        if selection.start_issue < 1 or selection.end_issue < 1:
            raise ConfigurationError("Issue numbers must be at least 1.")
        if selection.start_issue > selection.end_issue:
            raise ConfigurationError("The first issue cannot be after the last issue.")
    else:
        raise ConfigurationError(f"Unknown selection mode: {selection.mode!r}")


def select_issues(newest_issue: int | None, selection: Selection) -> list[TwicIssue]:
    """Generate every requested issue number, whether or not a page lists it."""

    _validate_selection(selection)
    if selection.mode == "range":
        assert selection.start_issue is not None and selection.end_issue is not None
        start, end = selection.start_issue, selection.end_issue
    else:
        if newest_issue is None or newest_issue < 1:
            raise CatalogError("Could not determine the newest TWIC issue.")
        end = newest_issue
        if selection.mode == "latest":
            assert selection.latest_count is not None
            start = max(1, end - selection.latest_count + 1)
        else:
            assert selection.start_issue is not None
            start = selection.start_issue
    return [numbered_issue(number) for number in range(start, end + 1)]


def _as_bool(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _resolve_profile(profile_identifier: str | int | dict[str, object]) -> dict[str, object]:
    if isinstance(profile_identifier, dict):
        return profile_identifier
    profile = get_profile(profile_identifier)
    if profile is None:
        raise UnknownProfile(f"Saved Setup not found: {profile_identifier}")
    return profile


def _emit(callback: EventCallback | None, event: SyncEvent) -> None:
    if callback:
        callback(event)


def sync_profile(
    profile_identifier: str | int | dict[str, object],
    *,
    selection: Selection | None = None,
    newest_issue_loader: NewestIssueLoader = fetch_latest_issue,
    on_event: EventCallback | None = None,
    is_cancelled: CancelledCallback | None = None,
) -> SyncResult:
    """Synchronize the profile's selected PGN and/or CBV ZIPs.

    Files are written straight to the configured Downloads folder.  This
    intentionally does not add retry, hash, staging, or repair behavior.
    """

    initialize_database()
    profile = _resolve_profile(profile_identifier)
    archive_root = str(profile.get("archive_root") or "").strip()
    if not archive_root:
        raise ConfigurationError("Saved Setup has no archive location.")

    with archive_operation(archive_root):
        return _sync_profile(
            profile,
            archive_root,
            selection=selection,
            newest_issue_loader=newest_issue_loader,
            on_event=on_event,
            is_cancelled=is_cancelled,
        )


def _sync_profile(
    profile: dict[str, object],
    archive_root: str,
    *,
    selection: Selection | None,
    newest_issue_loader: NewestIssueLoader,
    on_event: EventCallback | None,
    is_cancelled: CancelledCallback | None,
) -> SyncResult:
    profile_name = str(profile["name"])
    formats = [
        archive_format
        for archive_format, enabled in (
            ("pgn", _as_bool(profile.get("download_pgn"))),
            ("cbv", _as_bool(profile.get("download_cbv"))),
        )
        if enabled
    ]
    if not formats:
        raise ConfigurationError("Select PGN, CBV, or both for this Saved Setup.")

    requested_selection = selection or selection_from_profile(profile)
    _validate_selection(requested_selection)
    newest_issue = None if requested_selection.mode == "range" else newest_issue_loader()
    selected = select_issues(newest_issue, requested_selection)
    layout = ArchiveLayout.create(archive_root)
    result = SyncResult(profile_name=profile_name, selected_issues=tuple(entry.issue_number for entry in selected))
    total = len(selected) * len(formats)
    completed = 0
    extract_archives = _as_bool(profile.get("extract_archives"))
    keep_zips = _as_bool(profile.get("keep_zip_files"))

    for issue in selected:
        for archive_format in formats:
            if is_cancelled and is_cancelled():
                result.cancelled = True
                _emit(
                    on_event,
                    SyncEvent("canceled", "Sync canceled.", completed=completed, total=total),
                )
                return result

            source_url = issue.pgn_url if archive_format == "pgn" else issue.cbv_url
            if not source_url:
                completed += 1
                _emit(
                    on_event,
                    SyncEvent(
                        "info",
                        f"TWIC {issue.issue_number} has no {archive_format.upper()} download.",
                        issue.issue_number,
                        archive_format,
                        completed,
                        total,
                    ),
                )
                continue

            zip_path = layout.download_path(archive_format, issue.issue_number, source_url)
            extraction_path = layout.extraction_directory(archive_format)
            try:
                already_extracted = extract_archives and layout.has_extracted_issue(
                    archive_format, issue.issue_number
                )
                if already_extracted and (not keep_zips or zip_path.exists()):
                    removed_zip = not keep_zips and zip_path.exists()
                    if removed_zip:
                        zip_path.unlink()
                    result.skipped += 1
                    message = f"TWIC {issue.issue_number} {archive_format.upper()} is already extracted."
                    if removed_zip:
                        message += " Removed ZIP because Keep ZIP files is off."
                    _emit(
                        on_event,
                        SyncEvent("info", message, issue.issue_number, archive_format, completed, total),
                    )
                    continue

                if zip_path.exists():
                    result.skipped += 1
                    _emit(
                        on_event,
                        SyncEvent(
                            "info",
                            f"TWIC {issue.issue_number} {archive_format.upper()} ZIP already exists.",
                            issue.issue_number,
                            archive_format,
                            completed,
                            total,
                        ),
                    )
                else:
                    _emit(
                        on_event,
                        SyncEvent(
                            "download",
                            f"Downloading TWIC {issue.issue_number} {archive_format.upper()} ZIP.",
                            issue.issue_number,
                            archive_format,
                            completed,
                            total,
                        ),
                    )
                    download_file(source_url, zip_path, is_cancelled=is_cancelled)
                    result.downloaded += 1

                if extract_archives and not already_extracted:
                    _emit(
                        on_event,
                        SyncEvent(
                            "extract",
                            f"Extracting TWIC {issue.issue_number} {archive_format.upper()}.",
                            issue.issue_number,
                            archive_format,
                            completed,
                            total,
                        ),
                    )
                    extract_zip(zip_path, extraction_path)
                    result.extracted += 1
                    if not keep_zips:
                        zip_path.unlink(missing_ok=True)
            except DownloadCancelled:
                result.cancelled = True
                _emit(
                    on_event,
                    SyncEvent("canceled", "Sync canceled.", completed=completed, total=total),
                )
                return result
            except Exception as error:  # Report the visible failure, then continue other issues.
                message = f"TWIC {issue.issue_number} {archive_format.upper()}: {error}"
                result.failures.append(message)
                _emit(
                    on_event,
                    SyncEvent(
                        "failure",
                        message,
                        issue.issue_number,
                        archive_format,
                        completed,
                        total,
                    ),
                )
            finally:
                completed += 1

    # An unavailable ZIP must not prevent combining the PGNs already extracted.
    # Keep any download failures in the result and Activity; cancellation exits above.
    if _as_bool(profile.get("combine_after_sync")) and _as_bool(
        profile.get("download_pgn")
    ):
        try:
            result.combined = combine_extracted_pgns(layout)
        except NoExtractedPgns as error:
            message = str(error)
            result.failures.append(message)
            _emit(on_event, SyncEvent("failure", message, completed=completed, total=total))
        else:
            _emit(
                on_event,
                SyncEvent(
                    "complete",
                    f"Combined {result.combined.pgn_files} PGN file(s).",
                    completed=completed,
                    total=total,
                ),
            )
    elif result.succeeded:
        _emit(on_event, SyncEvent("complete", "Sync complete.", completed=completed, total=total))
    return result


def extract_profile(
    profile_identifier: str | int | dict[str, object],
    *,
    on_event: EventCallback | None = None,
    is_cancelled: CancelledCallback | None = None,
) -> ExtractResult:
    """Extract existing TWIC ZIPs only, without looking up or downloading issues."""

    initialize_database()
    profile = _resolve_profile(profile_identifier)
    archive_root = str(profile.get("archive_root") or "").strip()
    if not archive_root:
        raise ConfigurationError("Saved Setup has no archive location.")
    formats = [
        archive_format for archive_format in ("pgn", "cbv")
        if _as_bool(profile.get(f"download_{archive_format}"))
    ]
    if not formats:
        raise ConfigurationError("Select PGN, CBV, or both for this Saved Setup.")

    with archive_operation(archive_root):
        layout = ArchiveLayout.create(archive_root)
        archives = []
        for archive_format in formats:
            for zip_path in layout.downloads(archive_format).iterdir():
                if not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
                    continue
                match = re.match(r"^twic\D*(\d+)", zip_path.stem, re.IGNORECASE)
                if match and int(match.group(1)) > 0:
                    archives.append((int(match.group(1)), archive_format, zip_path))
        archives.sort(key=lambda item: (item[0], item[1] == "cbv", item[2].name.lower()))
        result = ExtractResult(profile_name=str(profile["name"]), total=len(archives))
        keep_zips = _as_bool(profile.get("keep_zip_files"))

        for completed, (issue_number, archive_format, zip_path) in enumerate(archives):
            if is_cancelled and is_cancelled():
                result.cancelled = True
                _emit(on_event, SyncEvent(
                    "canceled", "Extraction canceled.", completed=completed, total=result.total,
                ))
                return result
            try:
                if layout.has_extracted_issue(archive_format, issue_number):
                    result.skipped += 1
                    message = f"TWIC {issue_number} {archive_format.upper()} is already extracted."
                    if not keep_zips:
                        zip_path.unlink()
                        message += " Removed ZIP because Keep ZIP files is off."
                    _emit(on_event, SyncEvent(
                        "info", message, issue_number, archive_format, completed + 1, result.total,
                    ))
                    continue

                _emit(on_event, SyncEvent(
                    "extract", f"Extracting TWIC {issue_number} {archive_format.upper()} from {zip_path.name}.",
                    issue_number, archive_format, completed, result.total,
                ))
                extract_zip(zip_path, layout.extraction_directory(archive_format))
                result.extracted += 1
                if not keep_zips:
                    zip_path.unlink()
            except Exception as error:
                message = f"TWIC {issue_number} {archive_format.upper()}: {error}"
                result.failures.append(message)
                _emit(on_event, SyncEvent(
                    "failure", message, issue_number, archive_format, completed + 1, result.total,
                ))
        return result


def combine_profile(profile_identifier: str | int | dict[str, object]) -> CombineResult:
    """Manually combine a Saved Setup's extracted PGNs."""

    initialize_database()
    profile = _resolve_profile(profile_identifier)
    archive_root = str(profile.get("archive_root") or "").strip()
    if not archive_root:
        raise ConfigurationError("Saved Setup has no archive location.")
    with archive_operation(archive_root):
        return combine_extracted_pgns(ArchiveLayout.create(archive_root))
