# TWIC Archive Manager

This is the advanced/reference guide. New users: start with the separate [Beginner Guide](BEGINNER_GUIDE.md), including installer download and first-run instructions. Published setup files are listed under [GitHub Releases](https://github.com/codeguy-jv2080/twic-archive-manager/releases).

A standalone Windows desktop app for downloading and extracting The Week in Chess (TWIC) archives. Save different archive locations and issue selections, sync them manually or on a schedule, and optionally combine extracted PGNs into one file.

The interface uses Python and PySide6 (Qt). It does not require a browser, FastAPI server, or localhost connection. The packaged app includes its Python runtime, so a separate Python installation is not needed to use it. Internet access is needed to fetch the TWIC issue list and downloads; settings and archive files stay on your computer or your chosen network drive.

## Features

- Multiple named Saved Setups, each with its own archive folder, issue selection, download options, and optional schedule.
- Download PGN ZIPs, CBV ZIPs, or both.
- Select the latest number of issues, an inclusive issue range, or a starting issue through the newest available issue.
- Optional ZIP extraction and a choice to keep or delete ZIPs after extraction.
- Extract into shared PGN and CBV folders without adding per-issue subfolders.
- Create a combined `twic-all.pgn` manually or optionally after a successful sync. Automatic combining is off by default.
- Optional daily, weekly, or monthly Windows Task Scheduler runs. Scheduling is off by default.
- Visible Activity messages, progress, errors, cancellation during sync, and a Clear Activity button.
- Prevent simultaneous sync/combine operations from writing to the same archive folder on the same Windows computer.
- Light / Dark button with a remembered preference; the existing dark theme remains the default.
- Optional per-user Windows installer, alongside the unchanged portable launch method.

## Launch the app

Open this executable in the built project:

```text
dist\TWIC Archive Manager\TWIC Archive Manager.exe
```

Keep the executable together with the other files and folders inside `TWIC Archive Manager`. The portable build runs without an installer; the executable is not a single-file distribution. Build output is not committed to the repository.

### Optional installed version

`dist\TWIC-Archive-Manager-Setup.exe` packages the same portable build. It installs for the current Windows user under `%LOCALAPPDATA%\Programs\TWIC Archive Manager`, adds a Start menu shortcut, and offers an optional desktop shortcut. It does not require administrator privileges or install Python separately.

The installer does not move, delete, or replace the portable folder. Both launch methods share Saved Setups and the theme preference for the same Windows account. Apply a setup's schedule from whichever copy you want its task to launch; there is one Windows task per setup, not a separate task for each copy.

Upgrades reuse the installed location. Uninstall removes only installed program files and TWIC tasks whose executable path points to that installation; it preserves the SQLite settings database, archives, and portable copy. The installer asks for running app processes to be closed and does not force-close or restart them.

## Create a Saved Setup and sync

1. Click **New** under Saved Setups.
2. Enter a descriptive **Name** and choose an **Archive location**. This can be a local folder or an accessible network folder, such as `\\server\share\TWIC`.
3. Select **PGN**, **CBV**, or both. These choices download ZIP archives containing the selected format.
4. Choose whether to extract the ZIPs, keep them after extraction, and automatically create a combined PGN. Leave automatic combining unchecked unless you want it.
5. Under **What to Download**, choose the issues to include.
6. Click **Save Setup**, then **Sync**. Watch Activity for progress and the final result.

### What to Download

| Selection | What it includes |
| --- | --- |
| Latest number of issues | The newest N issues currently listed by TWIC. |
| Issue range | Available issues from the first number through the last number, including both endpoints. |
| From issue through newest | Available issues beginning at the chosen number and continuing through the newest listed issue. |

**Sync always follows the selected issue range or mode.** It does not replace that selection with a hidden "last downloaded issue" marker.

Manual Sync uses the current **What to Download** selection. Scheduled runs use the selection stored with **Save Setup**. Save changes to the archive location, formats, and extraction options before syncing; those settings are read from the saved setup.

### Manage Saved Setups

- Select a setup in the list to load its settings.
- To update it, keep its name, edit its settings, and click **Save Setup**.
- To add another, click **New** and use a different name. Saving a selected setup under a different name also creates another setup instead of replacing the original.
- **Delete** removes the selected setup after confirmation, along with its applied schedule. It does not delete downloaded ZIPs, extracted files, or combined PGNs.

## How Sync handles files

Sync fetches the current TWIC list, applies your selection, and checks the files already in the archive folder.

- With **Extract ZIP files** off, it downloads missing ZIPs and skips ZIPs already present. The ZIPs are kept regardless of the "keep after extraction" setting because no extraction takes place.
- With extraction on, it extracts existing ZIPs when the corresponding extracted issue is missing, downloading a ZIP first if needed.
- Already-extracted issues are not extracted again. With **Keep ZIP files after extraction** on, a missing ZIP is downloaded even if the extracted issue is present. With it off, an existing ZIP for an already-extracted issue is removed during Sync.
- Presence is determined from files and TWIC issue filenames, not from per-issue SQLite records. Sync does not remove older issues merely because they fall outside your current selection.

The completion counts refer to ZIP downloads, already-present issue/format items, and ZIPs extracted—not numbers of chess games.

Downloads are written directly to their final ZIP filenames. There is no automatic retry, resume, `.part` staging, file hashing, or repair. If a download is interrupted and leaves an incomplete ZIP, remove that affected ZIP before syncing again.

## Where archive files go

Inside each setup's **Archive location**:

```text
Your archive folder\
├── Downloads\
│   ├── PGN\                 PGN ZIP downloads
│   └── CBV\                 CBV ZIP downloads
├── Extracted\
│   ├── PGN\                 Extracted PGN files
│   └── CBV\                 Extracted CBV files
├── Combined\
│   └── twic-all.pgn         Created only when combining is requested
└── .twic-archive-manager\
    └── logs\               Currently created but not used for run history
```

The app keeps the download filenames supplied by TWIC and adds no per-issue extraction folders. The combined output is separate from the individual extracted PGNs.

## Create a combined PGN

Select a Saved Setup and click **Create Combined PGN**. This combines the TWIC-named `.pgn` files directly inside that setup's `Extracted\PGN` folder in ascending issue order and writes `Combined\twic-all.pgn`.

- It uses all matching extracted PGNs in that folder, not just the current **What to Download** selection.
- It rebuilds/replaces `twic-all.pgn`; it does not append another copy to the previous combined file. The individual source files remain unchanged.
- It does not extract ZIPs for you. Extract them with Sync first if needed.
- It joins the PGN contents without editing games or removing duplicate games.
- It does not combine CBV files or convert PGNs into ChessBase or Scid databases.

To run this automatically after successful syncs, check **Automatically create combined PGN after download/extraction** and click **Save Setup**. PGN downloading must also be enabled. Otherwise, combining happens only when you click its button.

## Automatic scheduling

1. Save and select the setup you want Windows to run.
2. Choose **Daily**, **Weekly**, or **Monthly** under **Automatic schedule**.
3. Set the time and, where applicable, the weekday or day of the month.
4. Click **Apply Schedule** to create or update the Windows task.

**Save Setup does not apply schedule changes.** Use **Apply Schedule** for that. To turn scheduling off, choose **No automatic schedule** and click **Apply Schedule**.

The desktop app does **not** need to stay open. Windows Task Scheduler launches the executable's background `sync` command using the saved setup. Keep the computer on and awake, with the required Windows user session and access to the archive folder and internet; the app does not configure wake-from-sleep or missed-run catch-up.

Click **View Windows Task** to see the task's actual Windows details, including its next run, last run time, and last result. For a completed app run, result `0` means success. This is the place to check a scheduled run; opening the app does not load its past Activity output.

If you move the portable application folder, open it from the new location and click **Apply Schedule** again for each scheduled setup so Windows uses the new executable path.

## Activity and Status

**Activity** is the large message area in the main window. It shows actions and errors from the current app session. **Status** is the short current-operation or completion message above it; the progress bar shows operation progress.

- **Clear Activity** clears the visible messages and resets Status/progress. It does not delete files, Saved Setups, or schedules. It is available when no operation is running.
- **Cancel Current Operation** requests cancellation of a running sync. A pending network operation may need to return or time out before cancellation takes effect. Completed downloads and extracted files are not rolled back.
- Activity is not saved as a persistent history and does not receive output from separate scheduled runs.

## Saved settings

Saved Setups, their options, their applied schedule settings, and the Light / Dark preference are stored in SQLite at:

```text
%LOCALAPPDATA%\TWIC Archive Manager\state\twic-archive-manager.db
```

Windows Task Scheduler stores the actual scheduled tasks separately. There is no per-issue download-tracking database or persistent last-downloaded marker.

The database stays in your Windows user profile, not in the portable application folder or a network archive folder. Moving the application folder alone does not transfer Saved Setups to another computer.

## Development

The application uses Python 3.10+, PySide6, the standard-library SQLite module, and Nuitka for the Windows build.

From the repository folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m app
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Close the app before rebuilding its existing portable distribution:

```powershell
.\scripts\build_portable.ps1
```

To build the installer, install [Inno Setup 6](https://jrsoftware.org/isdl.php) on the build machine, then run:

```powershell
.\scripts\build_installer.ps1
```

This rebuilds the canonical portable app and packages it as `dist\TWIC-Archive-Manager-Setup.exe`. Use `-SkipPortableBuild` to package an already-current portable build, or `-Compiler "C:\path\to\ISCC.exe"` for a nonstandard compiler location. The installer version comes from `pyproject.toml`. No GitHub workflow changes are required.

Publishing is separate from building: attach `TWIC-Archive-Manager-Setup.exe` to a GitHub Release so the beginner guide's download instructions have an installer asset to point to. No installer is uploaded by either build script.

The current installer is unsigned. The automated checks cover application behavior and installer configuration; the install/upgrade/uninstall lifecycle still needs an end-to-end check in a Windows test environment before public distribution.

For background/terminal use, the app also supports `sync --profile "Setup name"` and `combine --profile "Setup name"`. For example, from the repository folder:

```powershell
.\.venv\Scripts\python.exe -m app sync --profile "Main TWIC archive"
.\.venv\Scripts\python.exe -m app combine --profile "Main TWIC archive"
```

These commands use the saved setup and return an exit code: `0` for success, `1` for an operation failure, `2` for invalid configuration or no PGNs to combine, `3` for an unavailable archive folder, and `4` for cancellation.
