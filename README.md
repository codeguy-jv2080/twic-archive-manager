# TWIC Archive Manager

Build handoff and starter domain code for a cross-platform desktop application that manages **The Week in Chess (TWIC)** archives.

The finished application will run on Windows 10/11 and Ubuntu, with a shared command-line interface for scheduled, unattended downloads. It will download TWIC PGN archives, ChessBase CBV archives, or both; safely extract them; retain a portable archive manifest; and rebuild a `twic-all.pgn` file for ChessBase or SCID imports.

This repository deliberately does **not** include general PGN management. Splitting, resizing, editing, converting, or deduplicating arbitrary PGNs belongs in the future separate PGN archive/file-management utility.

## What is here now

- `CODEX_BUILD_HANDOFF.md` — the complete implementation prompt for a coding agent.
- `docs/` — architecture, archive-layout, and scheduling decisions.
- `src/TwicArchiveManager.Core/` — an intentionally small, dependency-free starter domain model and sync planner.

The scaffold is not a shipped application yet. The handoff requires the coding agent to turn it into a tested .NET 10/Avalonia application, add the GUI, CLI, download/extraction infrastructure, schedules, packaging, CI, and release artifacts.

## Intended repository

`codeguy-jv2080/twic-archive-manager` (private)

## Key design choices

- C# / .NET 10 / Avalonia UI
- Windows and Ubuntu from one codebase
- GUI plus headless CLI, sharing the same core services
- JSON manifest and explicit archive lock for safer use on SMB/NFS network shares
- Atomic `.part` downloads, ZIP integrity checks, ZIP-slip protection, and atomic replacement
- PGNs rebuild deterministically in TWIC issue order; CBVs remain separate files

See [the build handoff](CODEX_BUILD_HANDOFF.md) for the complete definition of done.
