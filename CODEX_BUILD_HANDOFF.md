# TWIC Archive Manager — Build Specification

## Product

Build a **Windows-local TWIC Archive Manager** using **FastAPI, SQLite, and plain HTML/CSS/JavaScript**.

The application runs only on the user's computer and listens only on `127.0.0.1`. Package the finished application as a Windows executable or installer that includes its runtime and dependencies.

## Purpose

Manage archives from [The Week in Chess](https://theweekinchess.com/twic):

- Download PGN ZIPs, CBV ZIPs, or both.
- Choose an inclusive issue range, a starting issue through newest, latest N issues, or missing/damaged files.
- Extract ZIPs when selected.
- Include a **Keep ZIPs after extraction** option, enabled by default.
- Track profiles, downloads, extraction, failures, and combined-PGN state in SQLite.
- Combine managed TWIC PGNs into `twic-all.pgn` for ChessBase or SCID import.
- Work with local folders, mapped drives, and UNC paths.
- Run manually through the local UI or unattended through a CLI launched by Windows Task Scheduler.

This app manages TWIC archives only. Do not add arbitrary-PGN splitting, resizing, editing, conversion, organization, deduplication, CBV merging, or CBV conversion.

## Storage

Store SQLite data in the current user's local application-data folder. Keep the database off archive roots and network shares.

Each profile stores:

- Profile name and archive root
- PGN/CBV selection
- Extract setting
- Keep-ZIPs setting
- Default selection mode
- Combine-after-sync setting
- Schedule settings

Archive files use this layout:

```text
<ArchiveRoot>/
  Downloads/
    PGN/
    CBV/
  Extracted/
    PGN/<issue>/
    CBV/<issue>/
  Combined/
    twic-all.pgn
  .twic-archive-manager/
    logs/
    sync.lock
```

## Catalog, download, and extraction

Read the official TWIC archive page with an HTML parser. Capture issue number, publication date, PGN URL, CBV URL, and game count when available. Do not guess URLs. If the catalog cannot be loaded or parsed, report that failure and do not say the archive is current.

For each file:

1. Download to a same-folder `.part` file.
2. Use timeouts, cancellation, and retry/backoff.
3. Verify nonzero size, ZIP structure/CRC, and the expected PGN or CBV entry.
4. Compute a hash and atomically rename the verified `.part` file to its final ZIP name.
5. Record the verified result in SQLite.
6. When extraction is selected, use a staging folder, reject ZIP-slip paths, validate output, and atomically move it into the final issue folder.
7. When Keep ZIPs is off, delete the ZIP only after successful verified extraction.

Detect damaged, partial, zero-byte, and metadata-mismatched files on later runs. Select them for repair. Preserve corrupt copies with a `.corrupt-<timestamp>` suffix.

Before a run, check that the archive root exists, is writable, has usable free space, and allows a temporary-file rename. For scheduled jobs, warn that a mapped drive may not exist and recommend a UNC path.

## UI and CLI

The UI needs:

- Folder selection plus editable UNC path
- Profiles
- PGN/CBV, extraction, and Keep-ZIPs controls
- From/To, From-through-newest, Latest N, and missing/damaged selection
- A review table with issue, date, game count, format status, and selected state
- Latest 1 as the default selection
- Progress, cancellation, retry, logs, and clear errors
- Status view and manual PGN combination
- Schedule creation, viewing, and removal

The CLI must provide:

```text
twic-archive-manager sync --profile <name>
twic-archive-manager combine --profile <name>
twic-archive-manager verify --profile <name>
twic-archive-manager status --profile <name>
```

Return these exit codes:

```text
0  completed successfully or nothing needed
1  one or more requested files failed
2  invalid profile or configuration
3  archive root unavailable or locked
4  canceled
```

## PGN combination

Combine only extracted PGNs managed by this application. Stream them in ascending issue order, write a temporary combined file, then atomically replace `twic-all.pgn` only after success. Preserve the prior combined file when rebuilding fails. Keep CBV files separate.

## Project layout

```text
app/
  main.py
  launcher.py
  database.py
  services/
  static/
tests/
docs/
scripts/
pyproject.toml
```

## Completion checks

- Test catalog parsing, all selection modes, ZIP verification, ZIP-slip rejection, damaged-file repair, SQLite persistence, PGN ordering, UNC preflight, CLI exit codes, and schedule command generation.
- Run a real small TWIC download before declaring the application complete.
- Build a Windows package and state its artifact path.
