# Architecture

TWIC Archive Manager is a normal Windows desktop program. It does not start a
browser, local server, FastAPI process, or localhost listener.

```mermaid
flowchart TD
  Window["PySide6 desktop window"] --> Services["Shared app services"]
  CLI["Headless CLI / Task Scheduler"] --> Services
  Services --> DB["SQLite Saved Setups and schedules"]
  Services --> TWIC["Official TWIC archive page"]
  Services --> Files["Selected archive root"]
```

SQLite holds Saved Setups and schedules in the current user's local
application-data folder. The actual ZIPs and extracted files are the source of
truth for completed downloads and extractions.

Portable runs retain the existing `state` database. The installer adds a
non-personal `twic-installed.flag` beside its executable; installed runs use a
separate `installed-state` database. No setups or preferences are copied between
them. Installed and portable Windows task names are separate as well.

The window and the CLI call the same services. Starting the program with no
arguments opens the desktop window. Starting it with `sync` or `combine` stays
headless for Windows Task Scheduler.
