# Scheduling

The graphical application configures profiles. The CLI performs a single noninteractive operation. The completed app creates a Windows Task Scheduler task for a named profile.

Prefer UNC archive roots such as `\\server\chess\TWIC`: mapped drives commonly do not exist in scheduled-task sessions. The task must run under an account that already has access to the selected share.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Completed successfully or nothing needed |
| 1 | One or more requested artifacts failed |
| 2 | Invalid profile/configuration |
| 3 | Archive root unavailable or locked |
| 4 | Canceled |
