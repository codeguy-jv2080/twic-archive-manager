"""Headless commands for Windows Task Scheduler and terminal use."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .services.archive import ArchiveRootUnavailable, NoExtractedPgns
from .services.catalog import CatalogError
from .services.sync import (
    ConfigurationError,
    SyncCancelled,
    combine_profile,
    sync_profile,
)


EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INVALID_CONFIGURATION = 2
EXIT_ARCHIVE_ROOT_UNAVAILABLE = 3
EXIT_CANCELED = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="twic-archive-manager")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("sync", "combine"):
        command = commands.add_parser(name)
        command.add_argument("--profile", required=True, help="Saved Setup name")
    return parser


def _sync_payload(result) -> dict[str, object]:
    payload: dict[str, object] = {
        "profile": result.profile_name,
        "issues": list(result.selected_issues),
        "downloaded": result.downloaded,
        "skipped": result.skipped,
        "extracted": result.extracted,
        "failures": result.failures,
        "cancelled": result.cancelled,
    }
    if result.combined:
        payload["combined"] = {
            "path": str(result.combined.output_path),
            "issues": list(result.combined.issue_numbers),
            "pgn_files": result.combined.pgn_files,
        }
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "sync":
            result = sync_profile(args.profile)
            print(json.dumps(_sync_payload(result), indent=2))
            if result.cancelled:
                return EXIT_CANCELED
            return EXIT_OK if result.succeeded else EXIT_FAILED

        if args.command == "combine":
            result = combine_profile(args.profile)
            print(
                json.dumps(
                    {
                        "path": str(result.output_path),
                        "issues": list(result.issue_numbers),
                        "pgn_files": result.pgn_files,
                    },
                    indent=2,
                )
            )
            return EXIT_OK

    except (ConfigurationError, NoExtractedPgns) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return EXIT_INVALID_CONFIGURATION
    except ArchiveRootUnavailable as error:
        print(f"Archive root unavailable: {error}", file=sys.stderr)
        return EXIT_ARCHIVE_ROOT_UNAVAILABLE
    except SyncCancelled:
        print("Canceled.", file=sys.stderr)
        return EXIT_CANCELED
    except (CatalogError, OSError) as error:
        print(f"Sync failed: {error}", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_INVALID_CONFIGURATION


if __name__ == "__main__":
    raise SystemExit(main())
