# Codex Build Handoff — TWIC Archive Manager

## Required stack

Build **TWIC Archive Manager** as a **Windows-local FastAPI + SQLite application**.

- Windows 10/11 x64 only.
- Python with FastAPI and standard-library SQLite.
- Plain HTML, CSS, and JavaScript served by FastAPI.
- Bind only to `127.0.0.1`; never expose a network service.
- Store SQLite under `%LOCALAPPDATA%\TWIC Archive Manager\`, never on a network share.
- Package the finished app as a Windows executable/installer that bundles Python and dependencies. The user must not need .NET or Python installed to use it.

Do not add C#, .NET, Avalonia, Electron, React, Ubuntu/Linux support, or a remote web service.

## Scope

This is a TWIC-only archive manager. It must:

- Download TWIC PGN ZIPs, ChessBase CBV ZIPs, or both.
- Support inclusive issue range, starting issue through newest, latest N issues, and missing/damaged issue selection.
- Extract ZIPs when selected.
- Offer **Keep ZIPs after extraction**, defaulting to **on**.
- Track profiles and managed artifacts in local SQLite.
- Combine successfully extracted TWIC PGNs into `twic-all.pgn` for ChessBase or SCID import.
- Support local folders, mapped drives, and Windows UNC paths.
- Provide a local UI and noninteractive CLI for Windows Task Scheduler.

Do not add arbitrary-PGN import, splitting, resizing, editing, conversion, deduplication, CBV merging, or CBV conversion. Those belong in the separate PGN Archive and File-Management Utility.

## Architecture

```text
app/
  main.py                 FastAPI routes and local UI
  launcher.py             packaged Windows entry point
  database.py             local SQLite initialization/connections
  services/
    catalog.py             official TWIC catalog parsing
    downloads.py           streamed download, verification, retry
    extraction.py          safe ZIP extraction
    sync.py                planning and synchronization
    combine.py             streamed PGN combination
    scheduler.py           Windows Task Scheduler integration
  static/
    index.html
    app.css
    app.js
tests/
docs/
scripts/
pyproject.toml
```

Use SQLite for profiles, issue/artifact state, timestamps, hashes, errors, and relative archive paths. Archive files live in the selected archive root:

```text
<ArchiveRoot>/
  Downloads/PGN/
  Downloads/CBV/
  Extracted/PGN/<issue>/
  Extracted/CBV/<issue>/
  Combined/twic-all.pgn
  .twic-archive-manager/
    logs/
    sync.lock
```

## Required behavior

Use the official catalog at `https://theweekinchess.com/twic`. Parse it with an HTML parser, not filename guessing. Capture issue number, date, PGN URL, CBV URL, and game count when available. If the catalog fails to load or parse, show an error; never claim the archive is current.

For each download:

1. Download serially by default to a same-folder `.part` file.
2. Use timeouts, cancellation, and retry/backoff.
3. Verify nonzero size, ZIP structure/CRC, and expected `.pgn` or `.cbv` member.
4. Hash the verified ZIP and atomically rename it to its final name.
5. Commit the verified state to SQLite only after that rename.
6. When extraction is selected, use staging, reject ZIP-slip paths, validate output, and atomically place it in the final issue folder.
7. Delete a ZIP only when **Keep ZIPs** is off and extraction succeeded.

Treat zero-byte, partial, corrupt, and metadata-mismatched files as damaged on later runs. Select them for repair and retain corrupt copies as `.corrupt-<timestamp>` rather than silently treating them as complete.

Before a run, test that the selected root exists, is writable, has free space, and supports creating and renaming a temporary file. For scheduled jobs, warn that mapped drives might not exist and recommend UNC paths. Use Windows share authentication only; never store credentials.

## UI, CLI, and packaging

The UI needs native folder selection, editable UNC paths, profiles, PGN/CBV/extract/keep-ZIPs settings, selection modes, a review table, progress, cancellation, retry, logs, status, PGN combination, and Windows Task Scheduler task creation/removal.

Default selection is Latest 1; never the entire archive.

The CLI must provide `sync`, `combine`, `verify`, and `status` for a named profile, with documented nonzero exit codes.

Rebuild combined PGNs in numeric TWIC issue order using a temporary output file and atomic replacement. Preserve the prior combined file when a rebuild fails. CBVs remain individual files.

Use a Windows-only GitHub Actions workflow. Test catalog parsing, inclusive ranges, ZIP validation, repair selection, ZIP-slip rejection, SQLite persistence, PGN ordering, UNC preflight behavior, CLI exit codes, and Task Scheduler command generation. Verify a real small TWIC download before declaring the app complete.
