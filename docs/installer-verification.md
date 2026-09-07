# Installer verification — 2026-09-07

## Changes

- Setuptools discovers only `app` and `app.*`, excluding the top-level installer directory.
- The installed app uses its own initially empty `installed-state` database. It never imports portable Saved Setups or preferences. Existing portable storage remains unchanged.
- Installed and portable schedules have separate names. Uninstall removes only installed-version tasks pointing to that installed executable.
- Installer packaging rejects unexpected non-program files in the portable build input. The installer adds only a non-personal installation marker to that runtime payload.
- No interface, archive behavior, or GitHub workflow changes.

## Actual results

Test machine: Windows 11 Home, build 26200, x64. Python 3.10.6, PySide6 6.11.2; packaged with Nuitka 4.2 and Inno Setup 6.7.3.

| Check | Result |
| --- | --- |
| New virtual environment; normal `pip install ".[dev]"` | Passed; wheel built and installed without the flat-layout error. |
| Installed-wheel import outside the repository import path | Passed; only `app` appears in distribution top-level metadata; Qt imports succeed. |
| Editable `pip install -e ".[dev]"`, matching the workflow command | Passed. |
| Complete test suite with portable and installed executable tests enabled | **57 passed, 0 skipped.** |
| Actual existing installation upgraded in place | Passed; silent installer exit code 0. |
| Actual uninstall | Passed; installed executable removed, protected data unchanged. |
| Actual install after uninstall | Passed; restored the same installed location. |
| In-place upgrade after creating an installed test setup | Passed; test setup, theme, stored schedule setting and archive retained; packaged combine still works. |
| Clean installed data with existing portable settings present | Passed; installed database has zero Saved Setups and zero saved preferences. Portable database unchanged. |
| Real desktop callbacks/window with clean installed storage, offscreen | Passed; no portable setups or theme loaded; automatic combining remains off. |
| Existing local data and portable copy through each lifecycle stage | All **108 protected files** unchanged by checksum: **66 portable runtime files, 41 archive files, and one existing database**. No existing archive location was missing. |
| Uninstaller task selection | Passed with three disabled, triggerless fixtures: removed its installed task; preserved a portable task and an installed-prefixed task targeting the portable executable. All test tasks subsequently removed. |
| Installed runtime contents | All 66 runtime files match the canonical portable build; installer marker is separate. |
| Start menu shortcut and uninstall registration | Both target the established installed location. |

The installed executable tests used isolated test application-data folders with generated fixtures, not copied personal databases. Installer lifecycle checks ran against the actual installed program at its established location. Existing personal files were only read and compared; their contents were not copied into packages or test fixtures.

The application is left installed at its existing path. The canonical portable executable remains at its original path. No alternate application distribution or launcher was created.

## Limits — not claimed as tested

- No pristine Windows VM or new Windows account was available. Isolated application-data tests are not a substitute for a clean operating-system test.
- Interactive installer screens, desktop appearance, and SmartScreen prompts were not exercised. The installer remains unsigned.
- Python 3.12 and a new GitHub Actions run were not executed during these local checks; the available local Python was 3.10.6. The existing workflow still selects 3.12 and is unchanged.
- No pre-existing TWIC Windows tasks were present at the time of the lifecycle test; task preservation was verified with the disabled fixtures above.
- The tests did not perform live TWIC downloads or run scheduled downloads. Those features were not changed.

## Re-running packaged tests

After building and installing the app, from the repository folder in PowerShell:

```powershell
$env:TWIC_PACKAGED_EXE = (Resolve-Path '.\dist\TWIC Archive Manager\TWIC Archive Manager.exe').Path
$env:TWIC_INSTALLED_EXE = Join-Path $env:LOCALAPPDATA 'Programs\TWIC Archive Manager\TWIC Archive Manager.exe'
.\.venv\Scripts\python.exe -m pytest -q
```

Without these executable-path variables, the two packaged tests are skipped. The other tests use temporary storage and offscreen Qt windows.
