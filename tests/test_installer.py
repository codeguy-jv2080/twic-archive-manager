from pathlib import Path
import subprocess
import sys

from app.install_support import RUNNING_MUTEX, application_running


def test_running_marker_is_shared_and_released() -> None:
    # Read the marker from another process, as Inno Setup does.
    code = """
import ctypes, sys
from ctypes import wintypes
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel.OpenMutexW.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
handle = kernel.OpenMutexW(0x00100000, False, sys.argv[1])
if handle:
    kernel.CloseHandle(handle)
    sys.exit(42)
sys.exit(0)
"""
    def probe():
        return subprocess.run(
            [sys.executable, "-c", code, RUNNING_MUTEX],
            timeout=10, creationflags=subprocess.CREATE_NO_WINDOW,
        ).returncode

    with application_running():
        with application_running():
            assert probe() == 42
        assert probe() == 42
    assert probe() == 0


def test_installer_preserves_user_data_and_does_not_force_close_apps() -> None:
    script = (Path(__file__).parents[1] / "installer" / "TWIC Archive Manager.iss").read_text()
    assert "PrivilegesRequired=lowest" in script
    assert f"AppMutex={RUNNING_MUTEX}" in script
    assert "CloseApplications=no" in script
    assert "RestartApplications=no" in script
    assert "[UninstallDelete]" not in script
    assert "postinstall skipifsilent unchecked" in script
    assert "CompareText(TaskPath, ExpandConstant('{app}\\{#AppExe}')) = 0" in script
    assert "if TargetsThisInstallation(Task) then" in script
