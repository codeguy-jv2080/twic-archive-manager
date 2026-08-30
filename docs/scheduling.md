# Scheduling

The graphical application configures profiles. The command-line app performs a single noninteractive run. Native scheduling starts that CLI; the desktop app should not remain running in the background.

## Windows

Create a Task Scheduler task that starts the CLI for a named profile. Prefer UNC archive roots such as `\\server\chess\TWIC` because mapped drives commonly do not exist in scheduled-task sessions. Document the account used by the task and its access to the network share.

## Ubuntu

Create a user-level systemd service and timer that start the same CLI/profile. When the archive root is a network mount, add an appropriate mount-availability dependency/check. Document that the user may need lingering enabled for timers to run after logout.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Completed successfully or no work needed |
| 1 | One or more requested artifacts failed |
| 2 | Invalid profile or configuration |
| 3 | Archive root unavailable or locked |
| 4 | Canceled |
