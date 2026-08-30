# TWIC Archive Manager

Windows-local TWIC archive manager starter using **FastAPI + SQLite**.

The finished Windows package will download and validate TWIC PGN and/or CBV ZIP archives, extract them, optionally keep the ZIPs, track status in SQLite, combine managed PGNs, and schedule unattended runs through Windows Task Scheduler.

The finished packaged app must not require .NET or Python to be installed by its user.

## Current state

This repository is a starter and build handoff, not a finished downloader. It currently provides a FastAPI local shell, SQLite initialization, profile storage, and a plain HTML/CSS/JavaScript starter UI.

The complete requirements are in [CODEX_BUILD_HANDOFF.md](CODEX_BUILD_HANDOFF.md).

## Scope

This app manages only TWIC archives. Arbitrary-PGN splitting, resizing, editing, conversion, and organization belong in the separate PGN Archive and File-Management Utility.
