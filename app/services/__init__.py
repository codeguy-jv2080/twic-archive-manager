"""The non-UI services used by the desktop app and command-line runner."""

from .archive import NoExtractedPgns
from .catalog import CATALOG_URL, CatalogError, TwicIssue, fetch_catalog, parse_catalog
from .sync import (
    ArchiveRootUnavailable,
    ConfigurationError,
    Selection,
    SyncCancelled,
    SyncResult,
    UnknownProfile,
    combine_profile,
    select_issues,
    sync_profile,
)

__all__ = [
    "CATALOG_URL",
    "ArchiveRootUnavailable",
    "CatalogError",
    "ConfigurationError",
    "NoExtractedPgns",
    "Selection",
    "SyncCancelled",
    "SyncResult",
    "TwicIssue",
    "UnknownProfile",
    "combine_profile",
    "fetch_catalog",
    "parse_catalog",
    "select_issues",
    "sync_profile",
]
