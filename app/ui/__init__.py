"""Desktop user-interface components for TWIC Archive Manager.

The window is intentionally independent from storage and download services.
``DesktopCallbacks`` in :mod:`app.ui.main_window` is the small adapter used by
the application layer to connect those services to the desktop controls.
"""

from .main_window import (
    DesktopCallbacks,
    OperationReporter,
    SavedSetup,
    SelectionMode,
    SelectionRequest,
    TwicArchiveManagerWindow,
    run_desktop,
)

__all__ = [
    "DesktopCallbacks",
    "OperationReporter",
    "SavedSetup",
    "SelectionMode",
    "SelectionRequest",
    "TwicArchiveManagerWindow",
    "run_desktop",
]
