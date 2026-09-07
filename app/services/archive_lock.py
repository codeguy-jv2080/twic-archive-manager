"""Coordinate archive writers across desktop and scheduled Windows processes."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from hashlib import sha256
from pathlib import Path


class ArchiveBusy(RuntimeError):
    """Another process is already using the selected archive folder."""


@contextmanager
def archive_operation(archive_root: str | Path):
    """Hold a named Windows object for the operation; no lock files are needed.

    Only the process that creates the object may proceed. Windows destroys the
    object when its final handle closes, including when a process exits.
    """

    root = Path(archive_root).expanduser().resolve()
    # This identifies the folder, not the contents of any downloaded file.
    identity = sha256(str(root).casefold().encode("utf-8")).hexdigest()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateMutexW
    create.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL

    handle = create(None, False, f"Global\\TWICArchiveManager.Archive.{identity}")
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    try:
        if error == 183:  # ERROR_ALREADY_EXISTS
            raise ArchiveBusy(f"Another operation is already using archive folder: {root}")
        yield
    finally:
        close(handle)
