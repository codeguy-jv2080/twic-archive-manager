# Scheduling

The UI configures a profile. The CLI performs one noninteractive operation for that profile. The completed application creates and removes a Windows Task Scheduler task.

Use a UNC archive root such as `\\server\chess\TWIC` for scheduled runs when possible. Mapped drives often do not exist in a scheduled task session.

| Code | Meaning |
| --- | --- |
| 0 | Completed successfully or nothing needed |
| 1 | One or more requested files failed |
| 2 | Invalid profile or configuration |
| 3 | Archive root unavailable or locked |
| 4 | Canceled |
