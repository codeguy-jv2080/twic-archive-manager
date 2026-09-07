"""The non-UI services used by the desktop app and command-line runner."""

from .archive import NoExtractedPgns
from .catalog import CATALOG_URL, CatalogError, TwicIssue, fetch_latest_issue, numbered_issue, parse_latest_issue
from .sync import (
    ArchiveRootUnavailable,
    ConfigurationError,
    ExtractResult,
    Selection,
    SyncCancelled,
    SyncResult,
    UnknownProfile,
    combine_profile,
    extract_profile,
    select_issues,
    sync_profile,
)

__all__ = [
    "CATALOG_URL",
    "ArchiveRootUnavailable",
    "CatalogError",
    "ConfigurationError",
    "ExtractResult",
    "NoExtractedPgns",
    "Selection",
    "SyncCancelled",
    "SyncResult",
    "TwicIssue",
    "UnknownProfile",
    "combine_profile",
    "extract_profile",
    "fetch_latest_issue",
    "numbered_issue",
    "parse_latest_issue",
    "select_issues",
    "sync_profile",
]
