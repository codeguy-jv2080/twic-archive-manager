# Codex Build Handoff — TWIC Archive Manager

You are building a finished, production-quality, cross-platform desktop application named **TWIC Archive Manager**.

Create and use the private GitHub repository:

```text
codeguy-jv2080/twic-archive-manager
```

Use **C#**, **.NET 10 LTS**, and **Avalonia UI**. Target Windows 10/11 x64 and Ubuntu Linux x64 from one codebase. Do not reuse, port, or modernize the old Electron/Synk code; this is a clean replacement for existing shell scripts.

This repository contains an early domain-model starter. You may refine it, but preserve the scope and safety guarantees below. Build the application fully; do not stop at mock screens or a design document.

## Product purpose and strict boundaries

The app manages only **The Week in Chess (TWIC)** archive downloads. It must:

- Download TWIC **PGN**, **ChessBase CBV**, or **both**.
- Download ZIP archives safely and extract them when requested.
- Let the user choose an inclusive issue range, a starting issue through latest, latest N issues, or missing/damaged files in a selected scope.
- Keep a manifest of every managed issue and format, including the most recent successful download.
- Rebuild extracted TWIC PGNs into one master PGN for import into ChessBase or SCID.
- Work with local folders, Windows UNC paths, mapped drives, and mounted Ubuntu SMB/NFS paths.
- Work interactively through a desktop UI and unattended through a shared headless CLI.
- Offer native scheduling through Windows Task Scheduler and Ubuntu user systemd timers.

It must **not** become a general PGN utility. Do not add arbitrary-PGN importing, PGN splitting/resizing, editing, conversion, duplicate-game detection, a general organizer, CBV merging, or CBV conversion. CBV files are downloaded, verified as archives, extracted, and retained **individually**.

Preserve TWIC attribution and its personal-use-only notice in the app About view and README.

## Deliverables

1. A complete .NET 10 solution using Avalonia MVVM.
2. Desktop app, shared core/infrastructure libraries, and noninteractive CLI.
3. Automated tests for the acceptance criteria below, all passing locally and in CI.
4. GitHub Actions that build and test on Windows and Ubuntu.
5. Self-contained publish/release artifacts for `win-x64` and `linux-x64`.
6. Thorough README and troubleshooting/scheduling documentation.
7. A clean initial commit history and a concise final report with repository URL, tests run, artifact paths, and remaining limitations.

## Recommended solution structure

```text
TwicArchiveManager.sln
Directory.Build.props
src/
  TwicArchiveManager.Core/
    Models/
    Planning/
    Services/
  TwicArchiveManager.Infrastructure/
    Catalog/
    Downloads/
    Extraction/
    Manifest/
    FileSystem/
    Scheduling/
    Logging/
  TwicArchiveManager.App/
    Views/
    ViewModels/
    Services/
    Assets/
  TwicArchiveManager.Cli/
tests/
  TwicArchiveManager.Core.Tests/
  TwicArchiveManager.Infrastructure.Tests/
  TwicArchiveManager.Cli.Tests/
docs/
scripts/
.github/workflows/
```

Keep domain and synchronization logic out of Avalonia views and view models. Prefer built-in .NET services (`HttpClient`, `System.IO.Compression`, `System.Security.Cryptography`, `System.Text.Json`) and use a maintained HTML parser such as AngleSharp for the catalog. Do not introduce Electron, Node, a browser runtime, or an always-running background service.

Use central package version management or explicit pinned compatible versions. Restore current stable versions that are compatible with .NET 10 at implementation time; do not copy old package versions from Synk.

## Official source catalog

Use the official TWIC archive page as the live catalog source:

```text
https://theweekinchess.com/twic
```

Parse the official archive table with a real HTML parser—not filename guessing or regex alone. Each catalog entry should capture:

- Issue number
- Publication date
- PGN ZIP URL when available
- CBV ZIP URL when available
- Game count when shown

Do not hard-code URL patterns such as `twic####g.zip`. Treat a missing issue or unavailable format as **unavailable**, not successfully synchronized. If the live catalog cannot be fetched or parsed, show a clear catalog error and never claim the archive is up to date.

## Profiles and user interface

The desktop app has named profiles. A profile stores:

- Archive-root folder
- Download format: PGN, CBV, or both
- Extract archives setting
- Keep ZIPs after extraction setting (default: keep)
- Default selection mode
- Combine PGNs after successful sync setting
- Schedule configuration

The main interface needs:

- A native folder browse button and an editable path field.
- Acceptance of manually entered UNC paths such as `\\server\chess\TWIC`.
- A write/rename/free-space test before a run.
- Selection modes: inclusive From/To, From through newest, Latest N, and missing/damaged within the selected scope.
- A review table before download with issue, date, game count, PGN status, CBV status, and selected state.
- File count and estimated download size before large historical plans when source metadata supports it.
- Default selection **Latest 1**. Never default to the whole historical archive.
- Per-issue/per-format progress, cancellation, clear failed/retry outcomes, and log access.
- Manifest/status view, manual **Combine all extracted TWIC PGNs** action, and buttons to open the archive and log folders.
- Schedule page that installs, views, and removes the native scheduled task/timer.

Keep the UI useful with keyboard navigation, clear error text, and no destructive default action.

## Managed archive layout

All files live below the selected archive root. Store relative paths—not machine-specific absolute paths—in the manifest.

```text
<ArchiveRoot>/
  Downloads/
    PGN/
    CBV/
  Extracted/
    PGN/
      1659/
    CBV/
      1659/
  Combined/
    twic-all.pgn
  .twic-archive-manager/
    manifest.json
    manifest.json.bak
    sync.lock
    logs/
```

Use a single `.twic-archive-manager/` directory per managed archive root. Keep ZIPs by default; extraction can be disabled per profile but the verified-download state must still be retained.

## Manifest and locking

Use a **JSON manifest**, not SQLite, because selected archive roots may be Windows/Linux network shares. Write it safely through a same-directory temporary file, atomic replacement, and a recoverable `.bak` copy. If recovery is required, make that visible in the log/status view.

Record at least the following per `(issue number, format)`:

- Issue number and publication date
- Source URL
- ZIP relative path, size, SHA-256
- Download status and timestamps
- Extraction status
- Extracted relative file path(s), size, and hash where practical
- Attempt count and last error
- Whether a successfully extracted PGN was included in the latest combined master

Statuses must distinguish at least `planned`, `downloading`, `verified`, `extracted`, `unavailable`, `failed`, and `canceled` (or an equivalent clear state machine). PGN and CBV are independent; a complete PGN does not imply a complete CBV.

Use a root-level lock so the GUI, CLI, scheduled job, or a second computer cannot mutate the same archive concurrently. The lock should identify host, process, start time, and operation. Do not silently override a lock; report it and return a nonzero CLI exit code.

## Safe download, extraction, repair

Implement each artifact lifecycle as follows:

1. Acquire the archive lock and revalidate the target root.
2. Download serially by default to a same-folder `.part` file using streamed I/O.
3. Use sensible timeouts, cancellation, and retry/backoff for temporary errors.
4. Verify nonzero length, ZIP structure/CRC, and that an expected `.pgn` or `.cbv` entry exists.
5. Compute SHA-256 and atomically rename the verified `.part` file to its final ZIP name.
6. Write the successful verified state to the manifest.
7. When extraction is selected, extract into a same-filesystem staging directory.
8. Reject ZIP-slip entries that resolve outside the archive root.
9. Validate expected extracted output and atomically place it in its final per-issue directory.
10. Update manifest extraction state only after that step succeeds.

Never treat a file’s existence alone as success. An artifact is missing/damaged when its manifest state is incomplete, its expected file is absent/zero-byte, its stored metadata conflicts materially, or ZIP verification fails. A rerun must select and repair it. Preserve corrupt material for diagnostics by renaming it with a clear `.corrupt-<timestamp>` suffix rather than overwriting it blindly.

Use same-filesystem staging for atomic rename behavior. Clear partial files on cancellation where safe, but never leave a false-complete manifest entry.

## PGN combination

The app combines only successfully extracted **TWIC PGNs that it manages**.

- Output: `<ArchiveRoot>/Combined/twic-all.pgn`
- Rebuild, do not append blindly.
- Stream source PGNs in ascending numeric TWIC issue order; never load the archive into memory.
- Ensure a valid newline boundary between input files.
- Write `<output>.part` and atomically replace the final master only after success.
- If a merge fails, preserve the prior `twic-all.pgn`.
- Update the manifest only after the new master is finalized.

CBVs remain individual archive/extracted files. Do not read their chess content, merge them, validate game records, or convert them.

## Network-drive behavior

Support local paths, Windows mapped drives, Windows UNC paths, and mounted Ubuntu SMB/NFS paths. Use the operating system’s existing authentication only; never store share credentials.

Before a run, confirm that the target root exists, is writable, has usable free space, and permits creation plus same-directory rename of a temporary file. Retry transient share failures, and describe an unavailable network path plainly.

For Windows scheduled runs, warn that mapped drive letters may not exist for Task Scheduler; recommend UNC paths. For Ubuntu systemd scheduling, require the network mount to be ready before the timer fires. Avoid locks or database modes that are unsafe on network file systems.

## CLI and scheduling

Create a noninteractive CLI sharing the same core libraries. At minimum:

```text
twic-archive-manager-cli sync --profile <name> [--dry-run]
twic-archive-manager-cli combine --profile <name>
twic-archive-manager-cli verify --profile <name>
twic-archive-manager-cli status --profile <name>
```

Use clear exit codes:

```text
0  completed successfully or nothing needed
1  one or more requested artifacts failed
2  invalid profile/configuration
3  archive root unavailable or locked
4  canceled
```

The GUI schedule page should create/remove:

- A Windows Task Scheduler job running the CLI for the selected profile.
- An Ubuntu user-level systemd service/timer running the CLI for the selected profile.

Do not implement a permanently running daemon. Document Windows task credentials/network access and Ubuntu user lingering requirements for timers that must run after logout.

## Automated acceptance criteria

Implement tests and run them. At minimum, cover:

### Catalog and planning

- Parse a saved official-TWIC-page fixture and discover issue number, date, PGN URL, CBV URL, and game count.
- Inclusive `1600–1602` selects all three issues.
- From `1600` through newest includes issue 1600 and the current catalog maximum.
- Latest 3 selects exactly three valid newest issues.
- Missing/removed issues are unavailable without crashing.
- PGN and CBV selection/status are independent.
- No selection mode defaults to the entire archive.

### Download and integrity

- Valid ZIPs use `.part`, verify, then atomically finalize.
- Corrupt/interrupted ZIPs never become complete artifacts.
- A damaged existing ZIP is selected for repair.
- Temporary errors retry correctly.
- ZIP-slip test fixtures cannot write outside the archive root.
- Extraction creates only intended managed files.

### Manifest and combination

- Manifest survives restart and stores relative paths.
- Failed/canceled actions do not mark artifacts completed.
- Concurrent sync attempts against the same archive root are blocked by the lock.
- PGNs combine in ascending issue order and handle inputs without trailing newlines.
- Rebuilding does not duplicate an issue.
- A failed merge preserves the previous master PGN.

### CLI, platform, and share handling

- CLI sync, combine, verify, and status run without GUI interaction and return the documented exit codes.
- Windows and Ubuntu builds pass in CI.
- Write/rename preflight checks work for representative UNC and mounted Linux-share paths (use controlled integration tests/mocks where a real share is unavailable).
- The generated Task Scheduler task and systemd timer invoke the CLI successfully in platform-appropriate integration/manual tests.

## Completion and reporting

Before reporting completion:

1. Run formatting, build, and all tests.
2. Verify a real, small TWIC download in a fresh temporary archive root if network access permits.
3. Publish test results and generated artifact paths.
4. State any unverified manual acceptance items honestly.

Do not silently reduce scope, replace source parsing with a guessed URL pattern, or declare success from files existing on disk.
