# TWIC Archive Manager — Build Handoff

## Product

Build a portable Windows desktop application named TWIC Archive Manager using Python, PySide6, and SQLite.

It is a standalone desktop window for manual use. It does not use a browser, FastAPI, HTTP, or a localhost server. Keep it portable until the application is finished.

## What it does

Manage archives from [The Week in Chess](https://theweekinchess.com/twic):

- Download PGN ZIPs, CBV ZIPs, or both.
- Choose an inclusive issue range, a starting issue through newest, or the latest N issues.
- Extract ZIPs when selected.
- Keep ZIPs after extraction by default, with an option to delete them after extraction.
- Store Saved Setups and schedules in SQLite.
- Combine extracted PGNs into `twic-all.pgn` for ChessBase or SCID import.
- Work with local folders, mapped drives, and UNC paths.
- Run from the desktop window or headlessly through Windows Task Scheduler.

## Saved Setups and storage

Store SQLite data in the current user's local application-data folder, not in an archive root or network share.

Saved Setups have no fixed limit. Each stores:

- Name and archive root
- PGN/CBV selection
- Extract setting
- Keep-ZIPs setting
- Default selection mode and value
- Combine-after-sync setting
- Schedule settings

Use this archive layout:

```text
<ArchiveRoot>/
  Downloads/
    PGN/
    CBV/
  Extracted/
    PGN/
    CBV/
  Combined/
    twic-all.pgn
  .twic-archive-manager/
    logs/
```

## Catalog, download, and extraction

Read the official TWIC archive page and capture the issue number, publication date, PGN URL, CBV URL, and game count when available.

Download selected ZIPs directly into the matching Downloads folder. Extract ZIPs when selected. When Keep ZIPs is off, delete the ZIP after extraction.

## Desktop window

Provide:

- Folder selection plus an editable UNC path
- Saved Setup creation, editing, and deletion
- PGN/CBV, extraction, and Keep-ZIPs controls
- From/To, From-through-newest, and Latest N selection
- Latest 1 as the default selection
- Progress, cancellation, logs, and clear errors
- Progress, activity messages, and a manual PGN-combine action
- Schedule creation, viewing, and removal

## Headless CLI

The scheduler must run headlessly: no browser and no desktop window.

Provide:

```text
twic-archive-manager sync --profile <name>
twic-archive-manager combine --profile <name>
```

Use these exit codes:

```text
0  completed successfully or nothing needed
1  one or more requested files failed
2  invalid profile or configuration
3  archive root unavailable
4  canceled
```

## PGN combination

PGN combination is optional and off by default. The user can combine PGNs manually or enable Combine-after-sync for a Saved Setup.

Combine extracted PGNs in ascending issue order into `twic-all.pgn`. Keep CBV files separate.

## Project layout

```text
app/
  main.py
  launcher.py
  cli.py
  database.py
  services/
  ui/
tests/
docs/
scripts/
pyproject.toml
```

## Completion checks

- Test catalog parsing, selection modes, SQLite persistence, PGN ordering, CLI exit codes, and schedule command generation.
- Run a real small TWIC download.
- Build a portable Windows executable and state its artifact path.
