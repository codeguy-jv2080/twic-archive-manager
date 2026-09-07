# TWIC Archive Manager — Beginner Guide

TWIC Archive Manager downloads weekly chess-game archives from The Week in Chess (TWIC). You choose where to keep them and which issues you want. You can run a download yourself or set a schedule.

You do not need to install Python, use a terminal, or understand GitHub's source code to use the packaged app.

## 1. Get the Windows installer

Open the project's [Releases/downloads page](https://github.com/codeguy-jv2080/twic-archive-manager/releases). In a release's **Assets** section, choose **TWIC-Archive-Manager-Setup.exe**.

Do not choose **Source code (zip)** or **Source code (tar.gz)**. Those are for developers, not the ready-to-use app. If no release lists the setup file yet, the installer has not been published there yet.

1. Open the downloaded setup file.
2. Follow the installer and click **Install**. You can optionally request a desktop shortcut.
3. Open **TWIC Archive Manager** from the Windows Start menu, or your desktop shortcut if you chose one.

The installer is for the current Windows user. It installs the program files together and does not require a separate Python installation. Internet access is needed when downloading TWIC issues, not to open the app.

The current setup file is not digitally signed. Only use an installer obtained from this project's release page or your own trusted build.

### Already using the portable app?

You do not have to install anything. Keep opening **TWIC Archive Manager.exe** from your existing portable folder. Keep the other files in that folder with it.

The installer is an alternative, not a replacement for the portable app. Installing it does not move or delete your portable folder. The installed app starts with its own empty Saved Setups and default theme; it does not import your portable settings. Your existing portable setups and preferences remain available in the portable app.

## 2. Choose light or dark mode

Click **Light / Dark** in the Commands area to switch between the existing black-background theme and a softer gray light theme. The app remembers your choice the next time you open it.

## 3. Make your first Saved Setup

A **Saved Setup** is a name for your download choices: where the files go, which issues you want, and whether to extract them. You can have several setups.

1. Click **New** under Saved Setups.
2. Enter a name, such as **My TWIC games**.
3. Beside **Archive location**, click **Browse** and choose the folder where you want the chess files kept. Choose a data folder, not the application's installation folder.
4. Choose **PGN**, **CBV**, or both:
   - **PGN** downloads chess games in PGN format inside ZIP files.
   - **CBV** downloads ChessBase archives inside ZIP files.
5. Leave **Extract ZIP files** checked if you want the app to unpack the downloads for you.
6. Leave **Keep ZIP files after extraction** checked if you also want the original ZIPs. Uncheck it to remove the ZIPs after their contents are extracted.
7. Leave **Automatically create combined PGN** unchecked unless you want an additional file containing all your extracted TWIC PGNs.

Under **What to Download**, choose:

| Choice | Example |
| --- | --- |
| Latest number of issues | Enter **10** for the ten newest listed issues. |
| Issue range | Enter a first and last issue to download that range, including both ends. |
| From issue through newest | Enter **1365** to include available issues from 1365 through the newest. |

Click **Save Setup**. This saves your choices; it does not start a download.

## 4. Download your chess archives

Select your Saved Setup and click **Sync**.

Sync downloads the selected ZIPs and extracts them if you selected that option. It checks the files already in your archive folder so it can skip what is already present. It follows your issue selection; it does not secretly start from a stored "last issue" number.

Watch **Activity** for progress, completion messages, or errors. **Cancel Current Operation** requests that a running sync stop; a network operation may take a little time to respond.

After changing the archive folder, formats, or options, click **Save Setup** before the next Sync. A manual Sync uses the current issue selection on the right; automatic runs use the selection you saved.

### Where are the files?

Open the **Archive location** you chose:

| Folder | Contents |
| --- | --- |
| `Downloads\PGN` | Downloaded PGN ZIPs, if you keep them. |
| `Downloads\CBV` | Downloaded CBV ZIPs, if you keep them. |
| `Extracted\PGN` | Unpacked PGN files. |
| `Extracted\CBV` | Unpacked CBV files. |
| `Combined` | `twic-all.pgn`, only if you request combining. |

If **Extract ZIP files** is unchecked, you get ZIPs only. The app does not add separate extraction folders for every issue.

## 5. Optional: make one combined PGN

After extracting PGNs, click **Create Combined PGN**. The result is **Combined\twic-all.pgn** inside your archive folder.

This combines all TWIC PGNs in that setup's **Extracted\PGN** folder, in issue order—not just the issues currently selected for downloading. It replaces the previous combined file and leaves the individual PGNs alone. It does not remove duplicate games or combine CBV files.

You can leave this feature unused. It is not required for downloading or scheduling.

## 6. Optional: let Windows run Sync automatically

1. Save and select the setup you want to run.
2. Under **Automatic schedule**, choose **Weekly**, **Daily**, or **Monthly**.
3. Choose the day and time as appropriate.
4. Click **Apply Schedule**.

**Save Setup** saves your download choices. **Apply Schedule** is the button that changes the actual Windows schedule.

The app does **not** have to stay open. Keep the computer on and awake with the necessary Windows user session, internet connection, and access to your archive folder. The app does not wake a sleeping computer.

To switch automatic runs off, choose **No automatic schedule** and click **Apply Schedule**.

### How do I know a scheduled run happened?

Select the setup and click **View Windows Task**. Check its **Last Run Time**, **Last Result**, and **Next Run Time**. For a completed app run, result **0** means success.

Activity only shows the current open app session. It does not load a history of background scheduled runs when you open the app.

The installed and portable apps have separate setups and schedules. Create and schedule a setup in the version you want to use. An installed schedule does not replace a portable schedule with the same name. If you move the portable folder, use **Apply Schedule** in the portable app to update its executable location.

## Everyday controls

- **New:** start another Saved Setup with a different name.
- **Save Setup:** save changes to the selected setup. Saving under a different name creates another setup instead of replacing the original.
- **Delete:** remove the selected Saved Setup and its applied schedule after confirmation. Your downloaded and extracted files stay on disk.
- **Clear Activity:** clear the visible messages. It does not delete files, setups, or schedules.
- **Light / Dark:** change the appearance, without changing download settings.

## Updating or uninstalling

For an installed copy, close TWIC Archive Manager, then run the newer setup file. It updates the same installation and preserves your Saved Setups, theme choice, and archives. If the app is running, close it yourself when asked; the installer does not force it to close.

To uninstall, use Windows **Settings → Apps**, find **TWIC Archive Manager**, and choose **Uninstall**. Uninstall removes the installed app and schedules that point to that installed copy. It leaves your portable copy, Saved Setups, theme choice, and archive files alone.

## If something goes wrong

- **No extracted PGN files are available to combine:** run Sync with **PGN** and **Extract ZIP files** enabled first.
- **A download fails:** read its Activity error and check your internet connection and archive location. Downloads are not automatically retried. An interrupted download can leave an incomplete ZIP; remove that affected ZIP before trying Sync again.
- **Another operation is already using the archive folder:** let the other manual or scheduled operation finish before trying again.
- **A scheduled run did not happen:** check **View Windows Task**, the chosen day/time, and whether the computer and archive folder were available.

For technical details, command-line use, storage paths, and build instructions, see the [advanced README](README.md).
