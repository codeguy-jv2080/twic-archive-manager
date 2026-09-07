"""Let the Windows installer detect a running desktop or scheduled process."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes


RUNNING_MUTEX = "Global\\TWICArchiveManager.Running"


@contextmanager
def application_running():
    # This is a presence marker, not a single-instance restriction. Multiple
    # app processes may share it; the archive lock controls concurrent writes.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateMutexW
    create.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    handle = create(None, False, RUNNING_MUTEX)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        close(handle)
