# Scheduling

The desktop window can create, view, or remove a Windows Task Scheduler task
for a Saved Setup. The task runs the headless sync command, so it does not open
a browser or desktop window.

Choose one schedule type in the desktop window:

- **No automatic schedule** — no task exists and nothing runs automatically.
- **Daily** — choose a time.
- **Weekly** — choose a weekday and time.
- **Monthly** — choose a day of the month and time.

Click **Apply** to create or update the Windows task. To turn scheduling off,
choose **No automatic schedule** and click **Apply**. A new Saved Setup starts
with automatic scheduling off.

If you move the portable application folder, click Apply Schedule again so
Windows Task Scheduler uses the new executable location.

Portable tasks use `TWIC Archive Manager - <name>`. Installed tasks use
`TWIC Archive Manager (Installed) - <name>`. Their settings and task names are
separate, so creating or deleting an installed schedule does not change a
portable schedule with the same setup name.

The headless commands are:

```text
twic-archive-manager sync --profile <name>
twic-archive-manager combine --profile <name>
```

Use a UNC archive root such as `\\server\chess\TWIC` for scheduled runs when possible. Mapped drives often do not exist in a scheduled task session.

| Code | Meaning |
| --- | --- |
| 0 | Completed successfully or nothing needed |
| 1 | One or more requested files failed |
| 2 | Invalid profile or configuration |
| 3 | Archive root unavailable |
| 4 | Canceled |
