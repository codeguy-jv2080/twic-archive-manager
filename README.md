# TWIC Archive Manager

This is the advanced/reference guide. New users: start with the separate [Beginner Guide](BEGINNER_GUIDE.md), including installer download and first-run instructions. Published setup files are listed under [GitHub Releases](https://github.com/codeguy-jv2080/twic-archive-manager/releases).

A standalone Windows desktop app for downloading and extracting The Week in Chess (TWIC) archives. Save different archive locations and issue selections, sync them manually or on a schedule, and optionally combine extracted PGNs into one file.

The interface uses Python and PySide6 (Qt). It does not require a browser, FastAPI server, or localhost connection. The packaged app includes its Python runtime, so a separate Python installation is not needed to use it. Internet access is needed for downloads and, when required by your selection, to identify the newest TWIC issue; settings and archive files stay on your computer or your chosen network drive.

## Features

- Multiple named Saved Setups, each with its own archive folder, issue selection, download options, and optional schedule.
- Download PGN ZIPs, CBV ZIPs, or both.
- Select the latest number of issues, an inclusive issue range, or a starting issue through the newest available issue.
- Optional ZIP extraction and a choice to keep or delete ZIPs after extraction.
- Manual **Extract ZIP** button for existing downloads, without another sync or download.
- Extract into shared PGN and CBV folders without adding per-issue subfolders.
- Create a combined `twic-all.pgn` manually or optionally after a sync. Automatic combining is off by default.
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

The installer does not move, delete, or replace the portable folder. The installed app has a separate settings database and starts with no Saved Setups; it does not import the portable app's data or theme choice. Each version manages its own schedules, including when setup names are identical.

Upgrades reuse the installed location and preserve that installed app's own settings. Uninstall removes only installed program files and installed-version TWIC tasks whose executable path points to that installation; it preserves both settings databases, archives, and the portable copy. The installer asks for running app processes to be closed and does not force-close or restart them.

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
| Latest number of issues | The newest N issue numbers, calculated from the newest issue. |
| Issue range | Every issue number from the first through the last, including both endpoints. No archive-page lookup is needed. |
| From issue through newest | Every issue number beginning at the chosen number and continuing through the newest issue. |

**Sync always follows the selected issue range or mode.** It does not replace that selection with a hidden "last downloaded issue" marker.

Manual Sync uses the current **What to Download** selection. Scheduled runs use the selection stored with **Save Setup**. Save changes to the archive location, formats, and extraction options before syncing; those settings are read from the saved setup.

### Manage Saved Setups

- Select a setup in the list to load its settings.
- To update it, keep its name, edit its settings, and click **Save Setup**.
- To add another, click **New** and use a different name. Saving a selected setup under a different name also creates another setup instead of replacing the original.
- **Delete** removes the selected setup after confirmation, along with its applied schedule. It does not delete downloaded ZIPs, extracted files, or combined PGNs.

## How Sync handles files

Sync constructs the numbered PGN and CBV ZIP download addresses for your selection and checks the files already in the archive folder. Issues do not have to appear on an archive page to be requested. Only **Latest number of issues** and **From issue through newest** read TWIC's main page to determine the newest issue number; splitting the archive listing across pages does not limit your range. An unavailable ZIP is reported in Activity, and Sync continues with the remaining downloads.

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

## Manually extract downloaded ZIPs

Select a Saved Setup and click **Extract ZIP**. It extracts the existing TWIC ZIPs in that setup's `Downloads\PGN` and/or `Downloads\CBV` folders, according to the setup's PGN/CBV choices, into the corresponding `Extracted` folders. Already-extracted issues are skipped. Save any changes to those choices or **Keep ZIP files after extraction** before clicking the button.

This action uses all existing TWIC ZIPs in the selected format folders, not the **What to Download** selection. It makes no website requests, downloads nothing, and does not combine PGNs. You do not need to turn on the **Extract ZIP files** option for this manual action; that option controls Sync. **Keep ZIP files after extraction** still applies. Activity shows progress and errors, and cancellation stops before the next ZIP. Other operations cannot run in the same window while extraction is running.

## Create a combined PGN

Select a Saved Setup and click **Create Combined PGN**. This combines the TWIC-named `.pgn` files directly inside that setup's `Extracted\PGN` folder in ascending issue order and writes `Combined\twic-all.pgn`.

- It uses all matching extracted PGNs in that folder, not just the current **What to Download** selection.
- It rebuilds/replaces `twic-all.pgn`; it does not append another copy to the previous combined file. The individual source files remain unchanged.
- It does not extract ZIPs for you. Extract them with Sync first if needed.
- It joins the PGN contents without editing games or removing duplicate games.
- It does not combine CBV files or convert PGNs into ChessBase or Scid databases.

To run this automatically after syncs, check **Automatically create combined PGN after download/extraction** and click **Save Setup**. PGN downloading must also be enabled. Available extracted PGNs are combined even if a requested ZIP is unavailable; download failures remain visible in Activity. Canceling a sync does not trigger automatic combining. Otherwise, combining happens only when you click its button.

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

Saved Setups, their options, their applied schedule settings, and the Light / Dark preference are stored separately in SQLite:

```text
Portable:  %LOCALAPPDATA%\TWIC Archive Manager\state\twic-archive-manager.db
Installed: %LOCALAPPDATA%\TWIC Archive Manager\installed-state\twic-archive-manager.db
```

Windows Task Scheduler stores the actual scheduled tasks separately. There is no per-issue download-tracking database or persistent last-downloaded marker.

The databases stay in your Windows user profile, not in an application folder or network archive folder. Moving an application folder alone does not transfer Saved Setups to another computer. The installer adds `twic-installed.flag` beside its executable to select installed storage; it contains no settings or personal data. The portable build does not contain this marker. Existing portable data is neither copied nor modified when installed storage is initialized.

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

Create the portable download from the same build:

```powershell
.\.venv\Scripts\python.exe scripts\package_portable.py
```

This writes `dist\TWIC-Archive-Manager-Portable.zip` in place, including the user guides and license documents. Packaging rejects unexpected files and checks bundled license documents against the source copies. Saved Setups, preferences, databases, logs, and archives must remain outside the distribution.

For a release, commit the source used for both packages and create a new version tag at that exact commit. Upload the portable ZIP and Setup.exe to that tag's release so its automatic **Source code** downloads match the binaries. Do not move an existing published tag to a different commit.

The current installer is unsigned. Background install, upgrade, uninstall, clean-settings, and data-preservation checks were completed on Windows 11; see the [verification report](docs/installer-verification.md) for actual results and limitations. A pristine Windows VM/new Windows account and interactive installer screens were not tested.

For background/terminal use, the app also supports `sync --profile "Setup name"` and `combine --profile "Setup name"`. For example, from the repository folder:

```powershell
.\.venv\Scripts\python.exe -m app sync --profile "Main TWIC archive"
.\.venv\Scripts\python.exe -m app combine --profile "Main TWIC archive"
```

These commands use the saved setup and return an exit code: `0` for success, `1` for an operation failure, `2` for invalid configuration or no PGNs to combine, `3` for an unavailable archive folder, and `4` for cancellation.

## License

TWIC Archive Manager is licensed under GPL-3.0-or-later. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
