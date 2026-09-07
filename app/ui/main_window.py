"""The standalone PySide6 window for TWIC Archive Manager.

This module owns widgets and interaction only.  It deliberately does not know
about SQLite, HTTP, TWIC parsing, or Task Scheduler.  The application layer
passes a :class:`DesktopCallbacks` instance when it creates the window.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, QThread, QTime, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


BUTTON_STYLE = """
QPushButton {
    background-color: #34373b;
    color: #f4f4f4;
    border: 1px solid #707378;
    border-bottom: 3px solid #121416;
    border-radius: 5px;
    padding: 7px 12px;
}
QPushButton:hover {
    background-color: #45494e;
    border-color: #969a9f;
}
QPushButton:pressed {
    background-color: #25282b;
    border: 1px solid #5d6165;
    border-top: 3px solid #121416;
    padding-top: 9px;
    padding-bottom: 5px;
}
QPushButton:disabled {
    background-color: #25272a;
    border-color: #3e4145;
    border-bottom-color: #17191b;
    color: #72767a;
}
QPushButton[runAction="true"] {
    background-color: #34373b;
    color: #ffffff;
    border-color: #8a8e92;
    border-bottom-color: #121416;
    font-weight: 600;
    min-height: 30px;
}
QPushButton[runAction="true"]:hover {
    background-color: #45494e;
}
QPushButton[runAction="true"]:pressed {
    background-color: #25282b;
    border-top-color: #121416;
}
QPushButton[runAction="true"]:disabled {
    background-color: #25272a;
    border-color: #3e4145;
    color: #72767a;
}
"""


def _button_style(theme: str) -> str:
    if theme != "light":
        return BUTTON_STYLE
    style = BUTTON_STYLE
    for dark, light in {
        "#34373b": "#c3c5c7", "#f4f4f4": "#202225", "#707378": "#85888c",
        "#121416": "#909398", "#45494e": "#d3d5d7", "#969a9f": "#6c7074",
        "#25282b": "#b7babd", "#5d6165": "#777b7f", "#25272a": "#c6c8ca",
        "#3e4145": "#a4a7aa", "#17191b": "#b1b4b7", "#72767a": "#666a6e",
        "#ffffff": "#202225", "#8a8e92": "#7b7f83",
    }.items():
        style = style.replace(dark, light)
    return style


def _apply_theme(application: QApplication, theme: str) -> None:
    application.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#000000"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f0f0f0"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#202225"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#292c2f"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#292c2f"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f0f0f0"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f0f0f0"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#34373b"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f4f4f4"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#c6a300"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#92969a"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#72767a"))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#72767a")
    )
    if theme == "light":
        for role, color in {
            QPalette.ColorRole.Window: "#d1d1d1",
            QPalette.ColorRole.WindowText: "#202225",
            QPalette.ColorRole.Base: "#e0e0e0",
            QPalette.ColorRole.AlternateBase: "#d6d8da",
            QPalette.ColorRole.ToolTipBase: "#e0e0e0",
            QPalette.ColorRole.ToolTipText: "#202225",
            QPalette.ColorRole.Text: "#202225",
            QPalette.ColorRole.Button: "#c3c5c7",
            QPalette.ColorRole.ButtonText: "#202225",
            QPalette.ColorRole.PlaceholderText: "#666a6e",
        }.items():
            palette.setColor(role, QColor(color))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#666a6e"))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#666a6e"))
    application.setPalette(palette)


class SelectionMode(str, Enum):
    """The three download-selection choices shown in the desktop window."""

    LATEST = "latest"
    RANGE = "range"
    FROM_THROUGH_NEWEST = "from-through-newest"


@dataclass(frozen=True, slots=True)
class SavedSetup:
    """A user-named archive setup, independent of its storage implementation."""

    name: str
    archive_root: str
    id: int | None = None
    download_pgn: bool = True
    download_cbv: bool = False
    extract_archives: bool = True
    keep_zip_files: bool = True
    combine_after_sync: bool = False
    default_selection_mode: SelectionMode = SelectionMode.LATEST
    # Stored compactly so the database can represent all three modes:
    # ``N`` for Latest N, ``first-last`` for a range, or ``first`` for
    # From-through-newest.
    default_selection_value: str = "1"
    schedule_text: str = ""

    @classmethod
    def from_value(cls, value: SavedSetup | Mapping[str, object]) -> SavedSetup:
        """Normalize database records and service DTOs for the UI.

        The existing starter database has no selection fields.  Missing fields
        therefore receive the visible default: Latest 1.
        """

        if isinstance(value, cls):
            return value

        raw_mode = str(value.get("default_selection_mode", SelectionMode.LATEST)).strip().lower()
        mode_aliases = {
            "latest": SelectionMode.LATEST,
            "latest_n": SelectionMode.LATEST,
            "latest-n": SelectionMode.LATEST,
            "range": SelectionMode.RANGE,
            "from": SelectionMode.FROM_THROUGH_NEWEST,
            "from-through-newest": SelectionMode.FROM_THROUGH_NEWEST,
            "through-newest": SelectionMode.FROM_THROUGH_NEWEST,
        }
        try:
            mode = mode_aliases[raw_mode]
        except KeyError:
            mode = SelectionMode.LATEST

        raw_id = value.get("id")
        return cls(
            id=int(raw_id) if raw_id is not None else None,
            name=str(value.get("name", "")),
            archive_root=str(value.get("archive_root", "")),
            download_pgn=bool(value.get("download_pgn", True)),
            download_cbv=bool(value.get("download_cbv", False)),
            extract_archives=bool(value.get("extract_archives", True)),
            keep_zip_files=bool(value.get("keep_zip_files", True)),
            combine_after_sync=bool(value.get("combine_after_sync", False)),
            default_selection_mode=mode,
            default_selection_value=str(value.get("default_selection_value", "1")),
            schedule_text=str(value.get("schedule_text", "")),
        )


@dataclass(frozen=True, slots=True)
class SelectionRequest:
    """The selection to use for one sync, rather than a persisted default."""

    mode: SelectionMode
    start_issue: int | None = None
    end_issue: int | None = None
    latest_count: int | None = None


class OperationCancelled(Exception):
    """Raised by a service that observes a user cancellation request."""


@dataclass(slots=True)
class OperationReporter:
    """Thread-safe progress and log functions handed to long-running actions.

    Service callbacks should periodically inspect ``cancelled`` and return
    promptly after it becomes true.  The UI never passes widgets into service
    code, so downloads and extraction remain independent from PySide6.
    """

    _progress_callback: Callable[[int, int, str], None]
    _log_callback: Callable[[str], None]
    _status_callback: Callable[[str], None]
    _cancel_event: Event

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def progress(self, completed: int, total: int, message: str = "") -> None:
        self._progress_callback(completed, total, message)

    def log(self, message: str) -> None:
        self._log_callback(message)

    def status(self, message: str) -> None:
        self._status_callback(message)

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise OperationCancelled("Canceled by user")


LoadSetups = Callable[[], Sequence[SavedSetup | Mapping[str, object]]]
SaveSetup = Callable[[SavedSetup], SavedSetup | Mapping[str, object] | None]
DeleteSetup = Callable[[SavedSetup], None]
SyncSetup = Callable[[SavedSetup, SelectionRequest, OperationReporter], object]
CombinePgns = Callable[[SavedSetup, OperationReporter], object]
ApplySchedule = Callable[[SavedSetup, str], object]
ViewSchedule = Callable[[SavedSetup], object]


def _no_setups() -> Sequence[SavedSetup]:
    return ()


def _service_not_connected(*_: object) -> None:
    raise NotImplementedError("This desktop action has not been connected to the application service yet.")


@dataclass(slots=True)
class DesktopCallbacks:
    """Small boundary between the desktop window and application services.

    ``sync`` and ``combine`` run in a worker thread.  The implementation may
    report progress through the supplied :class:`OperationReporter` and should
    not touch Qt widgets directly.
    """

    load_setups: LoadSetups = _no_setups
    save_setup: SaveSetup = _service_not_connected
    delete_setup: DeleteSetup = _service_not_connected
    sync: SyncSetup = _service_not_connected
    combine: CombinePgns = _service_not_connected
    apply_schedule: ApplySchedule = _service_not_connected
    view_schedule: ViewSchedule = _service_not_connected
    load_theme: Callable[[], str] = lambda: "dark"
    save_theme: Callable[[str], None] = _service_not_connected


class _OperationWorker(QObject):
    """Runs one service callback off the GUI thread."""

    progress_changed = Signal(int, int, str)
    log_emitted = Signal(str)
    status_changed = Signal(str)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, operation: Callable[[OperationReporter], object], cancel_event: Event) -> None:
        super().__init__()
        self._operation = operation
        self._cancel_event = cancel_event

    @Slot()
    def run(self) -> None:
        reporter = OperationReporter(
            _progress_callback=self.progress_changed.emit,
            _log_callback=self.log_emitted.emit,
            _status_callback=self.status_changed.emit,
            _cancel_event=self._cancel_event,
        )
        try:
            result = self._operation(reporter)
            if reporter.cancelled:
                self.cancelled.emit()
            else:
                self.completed.emit(result)
        except OperationCancelled:
            self.cancelled.emit()
        except Exception as error:  # Service failures belong in the visible log.
            self.failed.emit(str(error) or type(error).__name__)
        finally:
            self.finished.emit()


def _result_message(result: object) -> str:
    """Turn a service result into a short status line without prescribing a DTO."""

    if result is None:
        return "Completed."
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        message = result.get("message")
        if message:
            return str(message)
    return str(result)


class TwicArchiveManagerWindow(QMainWindow):
    """Normal Windows application window for manual TWIC archive management."""

    def __init__(self, callbacks: DesktopCallbacks | None = None) -> None:
        super().__init__()
        self._callbacks = callbacks or DesktopCallbacks()
        theme_error = None
        try:
            theme = self._callbacks.load_theme()
        except Exception as error:
            theme, theme_error = "dark", str(error)
        self._theme = theme if theme in {"light", "dark"} else "dark"
        self._setups: list[SavedSetup] = []
        self._operation_thread: QThread | None = None
        self._operation_worker: _OperationWorker | None = None
        self._operation_cancel: Event | None = None

        self.setWindowTitle("TWIC Archive Manager")
        self.resize(1180, 760)
        self.setMinimumSize(900, 620)
        self._build_ui()
        self._set_theme(self._theme)
        self.reload_setups()
        self.setMinimumSize(self.minimumSizeHint().expandedTo(self.minimumSize()))
        if theme_error:
            self._show_error(f"Could not load the saved theme: {theme_error}")

    def _set_theme(self, theme: str) -> None:
        self._theme = theme
        application = QApplication.instance()
        if application is not None:
            _apply_theme(application, theme)
        self.setStyleSheet(_button_style(theme))
        if application is not None:
            self.setPalette(application.palette())
        other = "light" if theme == "dark" else "dark"
        self.theme_button.setToolTip(f"Current theme: {theme.title()}. Switch to {other} mode.")
        self.theme_button.setAccessibleName(f"Switch to {other} mode")

    @Slot()
    def toggle_theme(self) -> None:
        theme = "light" if self._theme == "dark" else "dark"
        try:
            self._callbacks.save_theme(theme)
        except Exception as error:
            self._show_error(f"Could not save the theme: {error}")
            return
        self._set_theme(theme)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.addWidget(self._build_setups_panel(), 2)
        layout.addWidget(self._build_work_panel(), 3)

    def _build_setups_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setMinimumWidth(540)
        self.setups_panel = panel
        layout = QVBoxLayout(panel)

        list_group = QGroupBox("Saved Setups", panel)
        list_layout = QVBoxLayout(list_group)
        self.setup_list = QListWidget(list_group)
        self.setup_list.setFont(QFont("Segoe UI", 14))
        self.setup_list.setSpacing(5)
        self.setup_list.setMinimumHeight(170)
        self.setup_list.setMaximumHeight(240)
        self.setup_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setup_list.currentRowChanged.connect(self._load_selected_setup)
        list_layout.addWidget(self.setup_list)
        list_buttons = QHBoxLayout()
        self.new_setup_button = QPushButton("New", list_group)
        self.delete_setup_button = QPushButton("Delete", list_group)
        self.new_setup_button.clicked.connect(self.new_setup)
        self.delete_setup_button.clicked.connect(self.delete_selected_setup)
        self.new_setup_button.setFixedWidth(120)
        self.delete_setup_button.setFixedWidth(120)
        list_buttons.addStretch(1)
        list_buttons.addWidget(self.new_setup_button)
        list_buttons.addWidget(self.delete_setup_button)
        list_layout.addLayout(list_buttons)
        layout.addWidget(list_group)

        details_group = QGroupBox("Saved Setup Details", panel)
        details_layout = QVBoxLayout(details_group)
        form = QFormLayout()
        self.setup_name_edit = QLineEdit(details_group)
        self.setup_name_edit.setPlaceholderText("Example: Main TWIC archive")
        form.addRow("Name", self.setup_name_edit)

        self.archive_root_edit = QLineEdit(details_group)
        self.archive_root_edit.setPlaceholderText(r"C:\Chess\TWIC or \\server\share\TWIC")
        root_row = QWidget(details_group)
        root_layout = QHBoxLayout(root_row)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.archive_root_edit, 1)
        browse_button = QPushButton("Browse…", root_row)
        browse_button.clicked.connect(self.choose_archive_root)
        root_layout.addWidget(browse_button)
        form.addRow("Archive location", root_row)

        self.pgn_checkbox = QCheckBox("PGN", details_group)
        self.pgn_checkbox.setChecked(True)
        self.cbv_checkbox = QCheckBox("CBV", details_group)
        formats = QWidget(details_group)
        formats_layout = QHBoxLayout(formats)
        formats_layout.setContentsMargins(0, 0, 0, 0)
        formats_layout.addWidget(self.pgn_checkbox)
        formats_layout.addWidget(self.cbv_checkbox)
        formats_layout.addStretch(1)
        form.addRow("Download", formats)

        self.extract_checkbox = QCheckBox("Extract ZIP files", details_group)
        self.extract_checkbox.setChecked(True)
        self.keep_zips_checkbox = QCheckBox("Keep ZIP files after extraction", details_group)
        self.keep_zips_checkbox.setChecked(True)
        self.combine_after_sync_checkbox = QCheckBox(
            "Automatically create combined PGN\nafter download/extraction", details_group
        )
        options = QWidget(details_group)
        options_layout = QVBoxLayout(options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.addWidget(self.extract_checkbox)
        options_layout.addWidget(self.keep_zips_checkbox)
        options_layout.addWidget(self.combine_after_sync_checkbox)
        form.addRow("Options", options)

        self.schedule_type_combo = QComboBox(details_group)
        self.schedule_type_combo.addItem("No automatic schedule", "")
        self.schedule_type_combo.addItem("Daily", "daily")
        self.schedule_type_combo.addItem("Weekly", "weekly")
        self.schedule_type_combo.addItem("Monthly", "monthly")
        self.schedule_type_combo.currentIndexChanged.connect(self._schedule_type_changed)
        form.addRow("Automatic schedule", self.schedule_type_combo)

        self.schedule_stack = QStackedWidget(details_group)
        no_schedule_page = QWidget(self.schedule_stack)
        no_schedule_layout = QHBoxLayout(no_schedule_page)
        no_schedule_layout.setContentsMargins(0, 0, 0, 0)
        no_schedule_layout.addWidget(QLabel("Automatic syncing is off.", no_schedule_page))
        no_schedule_layout.addStretch(1)
        self.schedule_stack.addWidget(no_schedule_page)

        daily_page = QWidget(self.schedule_stack)
        daily_form = QFormLayout(daily_page)
        daily_form.setContentsMargins(0, 0, 0, 0)
        self.daily_time_edit = QTimeEdit(QTime(9, 0), daily_page)
        self.daily_time_edit.setDisplayFormat("h:mm AP")
        daily_form.addRow("Time", self.daily_time_edit)
        self.schedule_stack.addWidget(daily_page)

        weekly_page = QWidget(self.schedule_stack)
        weekly_form = QFormLayout(weekly_page)
        weekly_form.setContentsMargins(0, 0, 0, 0)
        self.weekly_day_combo = QComboBox(weekly_page)
        for weekday in (
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ):
            self.weekly_day_combo.addItem(weekday, weekday)
        self.weekly_time_edit = QTimeEdit(QTime(9, 0), weekly_page)
        self.weekly_time_edit.setDisplayFormat("h:mm AP")
        weekly_form.addRow("Day", self.weekly_day_combo)
        weekly_form.addRow("Time", self.weekly_time_edit)
        self.schedule_stack.addWidget(weekly_page)

        monthly_page = QWidget(self.schedule_stack)
        monthly_form = QFormLayout(monthly_page)
        monthly_form.setContentsMargins(0, 0, 0, 0)
        self.monthly_day_spin = QSpinBox(monthly_page)
        self.monthly_day_spin.setRange(1, 31)
        self.monthly_time_edit = QTimeEdit(QTime(9, 0), monthly_page)
        self.monthly_time_edit.setDisplayFormat("h:mm AP")
        monthly_form.addRow("Day of month", self.monthly_day_spin)
        monthly_form.addRow("Time", self.monthly_time_edit)
        self.schedule_stack.addWidget(monthly_page)
        form.addRow("When", self.schedule_stack)

        schedule_actions = QWidget(details_group)
        schedule_actions_layout = QHBoxLayout(schedule_actions)
        schedule_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_schedule_button = QPushButton("Apply Schedule", schedule_actions)
        self.view_schedule_button = QPushButton("View Windows Task", schedule_actions)
        self.apply_schedule_button.clicked.connect(self.apply_schedule)
        self.view_schedule_button.clicked.connect(self.view_schedule)
        self.apply_schedule_button.setFixedWidth(150)
        self.view_schedule_button.setFixedWidth(170)
        schedule_actions_layout.addStretch(1)
        schedule_actions_layout.addWidget(self.apply_schedule_button)
        schedule_actions_layout.addWidget(self.view_schedule_button)
        form.addRow("", schedule_actions)
        details_layout.addLayout(form)

        self.save_setup_button = QPushButton("Save Setup", details_group)
        self.save_setup_button.clicked.connect(self.save_setup)
        self.save_setup_button.setFixedWidth(150)
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(self.save_setup_button)
        details_layout.addLayout(save_row)
        layout.addWidget(details_group, 1)
        return panel

    def _build_work_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.addWidget(self._build_selection_group())
        layout.addWidget(self._build_commands_group())
        layout.addWidget(self._build_activity_group(), 1)
        return panel

    def _build_selection_group(self) -> QGroupBox:
        group = QGroupBox("What to Download", self)
        self.selection_group = group
        layout = QVBoxLayout(group)

        selector = QHBoxLayout()
        selector.addWidget(QLabel("Selection", group))
        self.selection_mode_combo = QComboBox(group)
        self.selection_mode_combo.addItem("Latest number of issues", SelectionMode.LATEST)
        self.selection_mode_combo.addItem("Issue range", SelectionMode.RANGE)
        self.selection_mode_combo.addItem("From issue through newest", SelectionMode.FROM_THROUGH_NEWEST)
        self.selection_mode_combo.currentIndexChanged.connect(self._selection_mode_changed)
        selector.addWidget(self.selection_mode_combo, 1)
        layout.addLayout(selector)

        self.selection_stack = QStackedWidget(group)
        self.selection_stack.addWidget(self._latest_selection_page())
        self.selection_stack.addWidget(self._range_selection_page())
        self.selection_stack.addWidget(self._from_newest_selection_page())
        layout.addWidget(self.selection_stack)

        return group

    def _latest_selection_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self.latest_count_spin = QSpinBox(page)
        self.latest_count_spin.setRange(1, 10000)
        self.latest_count_spin.setValue(1)
        form.addRow("Number of latest issues", self.latest_count_spin)
        return page

    def _range_selection_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self.range_start_spin = self._issue_spinbox(page)
        self.range_end_spin = self._issue_spinbox(page)
        form.addRow("From issue", self.range_start_spin)
        form.addRow("Through issue", self.range_end_spin)
        return page

    def _from_newest_selection_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self.from_issue_spin = self._issue_spinbox(page)
        form.addRow("Start at issue", self.from_issue_spin)
        form.addRow("End", QLabel("Newest available issue", page))
        return page

    @staticmethod
    def _issue_spinbox(parent: QWidget) -> QSpinBox:
        spin = QSpinBox(parent)
        spin.setRange(1, 100000)
        spin.setValue(1)
        return spin

    def _build_commands_group(self) -> QGroupBox:
        group = QGroupBox("Commands", self)
        self.commands_group = group
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        self.sync_button = QPushButton("Sync", group)
        self.combine_button = QPushButton("Create Combined PGN", group)

        for button in (
            self.sync_button,
            self.combine_button,
        ):
            button.setMinimumWidth(190)
            button.setMaximumWidth(240)

        self.sync_button.setProperty("runAction", True)
        self.combine_button.setProperty("runAction", True)
        self.sync_button.clicked.connect(self.start_sync)
        self.combine_button.clicked.connect(self.start_combine)

        layout.addWidget(self.sync_button, 0, 0)
        layout.addWidget(self.combine_button, 0, 1)
        layout.setColumnStretch(2, 1)
        self.theme_button = QPushButton("Light / Dark", group)
        self.theme_button.setFixedWidth(120)
        self.theme_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_button, 0, 3)
        return group

    def _build_activity_group(self) -> QGroupBox:
        group = QGroupBox("Activity", self)
        layout = QGridLayout(group)
        self.status_label = QLabel("Ready.", group)
        self.status_label.setWordWrap(True)
        self.progress_bar = QProgressBar(group)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        self.cancel_button = QPushButton("Cancel Current Operation", group)
        self.cancel_button.setProperty("runAction", True)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_operation)
        self.cancel_button.setFixedWidth(210)
        self.clear_activity_button = QPushButton("Clear Activity", group)
        self.clear_activity_button.clicked.connect(self.clear_activity)
        self.clear_activity_button.setFixedWidth(130)
        self.log_output = QPlainTextEdit(group)
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(220)
        self.log_output.document().setMaximumBlockCount(1000)
        layout.addWidget(QLabel("Status", group), 0, 0)
        layout.addWidget(self.status_label, 0, 1)
        layout.addWidget(self.clear_activity_button, 0, 2)
        layout.addWidget(self.cancel_button, 0, 3)
        layout.addWidget(self.progress_bar, 1, 0, 1, 4)
        layout.addWidget(self.log_output, 2, 0, 1, 4)
        return group

    def reload_setups(self, select_name: str | None = None) -> None:
        """Refresh the saved-setups list from the application callback."""

        try:
            self._setups = [SavedSetup.from_value(value) for value in self._callbacks.load_setups()]
        except Exception as error:
            self._setups = []
            self._set_status(f"Could not load Saved Setups: {error}")
            self._append_log(f"Could not load Saved Setups: {error}")

        self.setup_list.blockSignals(True)
        self.setup_list.clear()
        selected_row = -1
        for index, setup in enumerate(self._setups):
            item = QListWidgetItem(setup.name)
            item.setToolTip(setup.archive_root)
            self.setup_list.addItem(item)
            if setup.name.casefold() == (select_name or "").casefold():
                selected_row = index
        self.setup_list.blockSignals(False)
        if selected_row >= 0:
            self.setup_list.setCurrentRow(selected_row)
        elif self._setups:
            self.setup_list.setCurrentRow(0)
        else:
            self.new_setup()

    @Slot()
    def new_setup(self) -> None:
        self.setup_list.setCurrentRow(-1)
        self.setup_list.clearSelection()
        self.setup_name_edit.clear()
        self.archive_root_edit.clear()
        self.pgn_checkbox.setChecked(True)
        self.cbv_checkbox.setChecked(False)
        self.extract_checkbox.setChecked(True)
        self.keep_zips_checkbox.setChecked(True)
        self.combine_after_sync_checkbox.setChecked(False)
        self._set_schedule("")
        self._set_selection(SelectionMode.LATEST, "1")
        self.setup_name_edit.setFocus()

    @Slot(int)
    def _load_selected_setup(self, row: int) -> None:
        if row < 0 or row >= len(self._setups):
            return
        setup = self._setups[row]
        self.setup_name_edit.setText(setup.name)
        self.archive_root_edit.setText(setup.archive_root)
        self.pgn_checkbox.setChecked(setup.download_pgn)
        self.cbv_checkbox.setChecked(setup.download_cbv)
        self.extract_checkbox.setChecked(setup.extract_archives)
        self.keep_zips_checkbox.setChecked(setup.keep_zip_files)
        self.combine_after_sync_checkbox.setChecked(setup.combine_after_sync)
        self._set_schedule(setup.schedule_text)
        self._set_selection(setup.default_selection_mode, setup.default_selection_value)

    @Slot()
    def choose_archive_root(self) -> None:
        current = self.archive_root_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(self, "Choose archive folder", current)
        if chosen:
            self.archive_root_edit.setText(chosen)

    @Slot()
    def save_setup(self) -> None:
        setup = self._setup_from_form()
        selected = self._current_setup()
        if selected is not None and setup.name.casefold() != selected.name.casefold():
            setup = replace(setup, id=None)
        error = self._validate_setup(setup)
        if error:
            self._show_error(error)
            return
        try:
            result = self._callbacks.save_setup(setup)
            saved = SavedSetup.from_value(result) if result is not None else setup
        except Exception as error:
            self._show_error(f"Could not save Saved Setup: {error}")
            return
        schedule_needs_apply = setup.schedule_text != saved.schedule_text
        message = f'Saved Setup "{saved.name}".'
        if schedule_needs_apply:
            message += " Click Apply to change the automatic schedule."
        self._set_status(message)
        self._append_log(message)
        self.reload_setups(select_name=saved.name)
        if schedule_needs_apply:
            self._set_schedule(setup.schedule_text)

    @Slot()
    def apply_schedule(self) -> None:
        setup = self._selected_setup_or_error()
        if setup is None:
            return
        try:
            result = self._callbacks.apply_schedule(setup, self._schedule_text())
        except Exception as error:
            self._show_error(f"Could not apply schedule: {error}")
            return
        message = _result_message(result)
        self._set_status(message)
        self._append_log(message)
        self.reload_setups(select_name=setup.name)

    @Slot()
    def view_schedule(self) -> None:
        setup = self._selected_setup_or_error()
        if setup is None:
            return
        try:
            result = self._callbacks.view_schedule(setup)
        except Exception as error:
            self._show_error(f"Could not view schedule: {error}")
            return
        message = _result_message(result)
        self._set_status(message.splitlines()[0] if message else "Ready.")
        self._append_log(message)
        QMessageBox.information(self, "Schedule", message)

    @Slot()
    def delete_selected_setup(self) -> None:
        setup = self._current_setup()
        if setup is None:
            self._show_error("Select a Saved Setup to delete.")
            return
        confirmation = QMessageBox(self)
        confirmation.setIcon(QMessageBox.Icon.Warning)
        confirmation.setWindowTitle("Delete Saved Setup")
        confirmation.setText(
            f'Delete the Saved Setup "{setup.name}"? Archive files will not be deleted.'
        )
        delete_button = confirmation.addButton(
            "Delete", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = confirmation.addButton(QMessageBox.StandardButton.Cancel)
        confirmation.setDefaultButton(cancel_button)
        confirmation.exec()
        if confirmation.clickedButton() is not delete_button:
            return
        try:
            self._callbacks.delete_setup(setup)
        except Exception as error:
            self._show_error(f"Could not delete Saved Setup: {error}")
            return
        self._set_status(f'Deleted Saved Setup "{setup.name}".')
        self._append_log(f'Deleted Saved Setup "{setup.name}".')
        self.reload_setups()

    @Slot(int)
    def _selection_mode_changed(self, index: int) -> None:
        self.selection_stack.setCurrentIndex(index)

    @Slot(int)
    def _schedule_type_changed(self, index: int) -> None:
        self.schedule_stack.setCurrentIndex(max(index, 0))

    def _set_schedule(self, schedule_text: str) -> None:
        parts = schedule_text.strip().split()
        schedule_type = parts[0].casefold() if parts else ""
        index = self.schedule_type_combo.findData(schedule_type)
        self.schedule_type_combo.setCurrentIndex(max(index, 0))

        if schedule_type == "daily" and len(parts) == 2:
            self._set_time(self.daily_time_edit, parts[1])
        elif schedule_type == "weekly" and len(parts) == 3:
            day_index = self.weekly_day_combo.findData(parts[1].title())
            self.weekly_day_combo.setCurrentIndex(max(day_index, 0))
            self._set_time(self.weekly_time_edit, parts[2])
        elif schedule_type == "monthly" and len(parts) == 3:
            try:
                self.monthly_day_spin.setValue(int(parts[1]))
            except ValueError:
                self.monthly_day_spin.setValue(1)
            self._set_time(self.monthly_time_edit, parts[2])

    @staticmethod
    def _set_time(editor: QTimeEdit, text: str) -> None:
        value = QTime.fromString(text, "HH:mm")
        editor.setTime(value if value.isValid() else QTime(9, 0))

    def _schedule_text(self) -> str:
        schedule_type = str(self.schedule_type_combo.currentData() or "")
        if schedule_type == "daily":
            return f"daily {self.daily_time_edit.time().toString('HH:mm')}"
        if schedule_type == "weekly":
            return (
                f"weekly {self.weekly_day_combo.currentData()} "
                f"{self.weekly_time_edit.time().toString('HH:mm')}"
            )
        if schedule_type == "monthly":
            return (
                f"monthly {self.monthly_day_spin.value()} "
                f"{self.monthly_time_edit.time().toString('HH:mm')}"
            )
        return ""

    def _set_selection(self, mode: SelectionMode, value: str | int) -> None:
        index = self.selection_mode_combo.findData(mode)
        self.selection_mode_combo.setCurrentIndex(max(index, 0))
        raw_value = str(value).strip()
        if mode is SelectionMode.LATEST:
            self.latest_count_spin.setValue(self._positive_value(raw_value))
        elif mode is SelectionMode.RANGE:
            start, separator, end = raw_value.partition("-")
            self.range_start_spin.setValue(self._positive_value(start))
            self.range_end_spin.setValue(self._positive_value(end) if separator else self._positive_value(start))
        else:
            self.from_issue_spin.setValue(self._positive_value(raw_value))

    @staticmethod
    def _positive_value(value: str) -> int:
        try:
            return max(1, int(value))
        except ValueError:
            return 1

    def _selection_mode(self) -> SelectionMode:
        return SelectionMode(self.selection_mode_combo.currentData())

    def _selection_default_value(self) -> str:
        mode = self._selection_mode()
        if mode is SelectionMode.LATEST:
            return str(self.latest_count_spin.value())
        if mode is SelectionMode.RANGE:
            return f"{self.range_start_spin.value()}-{self.range_end_spin.value()}"
        return str(self.from_issue_spin.value())

    def _selection_request(self) -> SelectionRequest | None:
        mode = self._selection_mode()
        if mode is SelectionMode.LATEST:
            return SelectionRequest(mode=mode, latest_count=self.latest_count_spin.value())
        if mode is SelectionMode.RANGE:
            start = self.range_start_spin.value()
            end = self.range_end_spin.value()
            if end < start:
                self._show_error("The ending issue must be the same as or newer than the starting issue.")
                return None
            return SelectionRequest(mode=mode, start_issue=start, end_issue=end)
        return SelectionRequest(mode=mode, start_issue=self.from_issue_spin.value())

    @Slot()
    def start_sync(self) -> None:
        setup = self._selected_setup_or_error()
        request = self._selection_request()
        if setup is None or request is None:
            return
        self._start_operation(
            "Syncing…",
            lambda reporter: self._callbacks.sync(setup, request, reporter),
        )

    @Slot()
    def start_combine(self) -> None:
        setup = self._selected_setup_or_error()
        if setup is None:
            return
        self._start_operation(
            "Combining PGNs…",
            lambda reporter: self._callbacks.combine(setup, reporter),
            cancellable=False,
        )

    def _start_operation(
        self,
        initial_status: str,
        operation: Callable[[OperationReporter], object],
        *,
        cancellable: bool = True,
    ) -> None:
        if self._operation_thread is not None:
            self._show_error("An operation is already running.")
            return
        self._operation_cancel = Event()
        thread = QThread(self)
        worker = _OperationWorker(operation, self._operation_cancel)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress_changed.connect(self._update_progress)
        worker.log_emitted.connect(self._append_log)
        worker.status_changed.connect(self._set_status)
        worker.completed.connect(self._operation_completed)
        worker.failed.connect(self._operation_failed)
        worker.cancelled.connect(self._operation_cancelled)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._operation_thread_finished)
        self._operation_thread = thread
        self._operation_worker = worker
        self._set_operation_controls(True, cancellable=cancellable)
        self._set_status(initial_status)
        self._append_log(initial_status)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat(initial_status)
        thread.start()

    @Slot()
    def cancel_operation(self) -> None:
        if self._operation_cancel is None:
            return
        self._operation_cancel.set()
        self.cancel_button.setEnabled(False)
        self._set_status("Cancel requested…")
        self._append_log("Cancel requested.")

    @Slot()
    def clear_activity(self) -> None:
        self.log_output.clear()
        self._set_status("Ready.")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")

    @Slot(int, int, str)
    def _update_progress(self, completed: int, total: int, message: str) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(min(max(completed, 0), total))
            self.progress_bar.setFormat(f"%v / %m" if not message else f"%v / %m — {message}")
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat(message or "Working…")
        if message:
            self._set_status(message)

    @Slot(object)
    def _operation_completed(self, result: object) -> None:
        message = _result_message(result)
        self._set_status(message)
        self._append_log(message)

    @Slot(str)
    def _operation_failed(self, message: str) -> None:
        self._show_error(f"The operation failed: {message}")

    @Slot()
    def _operation_cancelled(self) -> None:
        self._set_status("Canceled.")
        self._append_log("Canceled.")

    @Slot()
    def _operation_thread_finished(self) -> None:
        self._operation_thread = None
        self._operation_worker = None
        self._operation_cancel = None
        self._set_operation_controls(False)
        self.progress_bar.setRange(0, 100)
        if self.progress_bar.value() != self.progress_bar.maximum():
            self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")

    def _set_operation_controls(self, running: bool, *, cancellable: bool = True) -> None:
        self.setups_panel.setEnabled(not running)
        self.selection_group.setEnabled(not running)
        self.sync_button.setEnabled(not running)
        self.combine_button.setEnabled(not running)
        self.apply_schedule_button.setEnabled(not running)
        self.view_schedule_button.setEnabled(not running)
        self.clear_activity_button.setEnabled(not running)
        self.cancel_button.setEnabled(running and cancellable)

    def _selected_setup_or_error(self) -> SavedSetup | None:
        setup = self._current_setup()
        if setup is None:
            self._show_error("Save and select a Saved Setup before running an action.")
            return None
        form_setup = self._setup_from_form()
        comparable_form = replace(form_setup, schedule_text=setup.schedule_text)
        if comparable_form != setup:
            self._show_error("Save your Saved Setup changes before running an action.")
            return None
        return setup

    def _current_setup(self) -> SavedSetup | None:
        row = self.setup_list.currentRow()
        return self._setups[row] if 0 <= row < len(self._setups) else None

    def _setup_from_form(self) -> SavedSetup:
        selected = self._current_setup()
        return SavedSetup(
            id=selected.id if selected else None,
            name=self.setup_name_edit.text().strip(),
            archive_root=self.archive_root_edit.text().strip(),
            download_pgn=self.pgn_checkbox.isChecked(),
            download_cbv=self.cbv_checkbox.isChecked(),
            extract_archives=self.extract_checkbox.isChecked(),
            keep_zip_files=self.keep_zips_checkbox.isChecked(),
            combine_after_sync=self.combine_after_sync_checkbox.isChecked(),
            default_selection_mode=self._selection_mode(),
            default_selection_value=self._selection_default_value(),
            schedule_text=self._schedule_text(),
        )

    @staticmethod
    def _setup_key(setup: SavedSetup) -> int | str:
        return setup.id if setup.id is not None else setup.name.casefold()

    @staticmethod
    def _validate_setup(setup: SavedSetup) -> str | None:
        if not setup.name:
            return "Enter a name for the Saved Setup."
        if not setup.archive_root:
            return "Choose or enter an archive location."
        if not (setup.download_pgn or setup.download_cbv):
            return "Select PGN, CBV, or both."
        return None

    @Slot(str)
    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    @Slot(str)
    def _append_log(self, message: str) -> None:
        if message:
            self.log_output.appendPlainText(message)

    def _show_error(self, message: str) -> None:
        self._set_status(message)
        self._append_log(message)
        QMessageBox.warning(self, "TWIC Archive Manager", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API spelling
        if self._operation_thread is not None:
            self.cancel_operation()
            QMessageBox.information(
                self,
                "Operation Running",
                "Cancellation was requested. Wait for the current operation to stop before closing the window.",
            )
            event.ignore()
            return
        event.accept()


def run_desktop(callbacks: DesktopCallbacks | None = None) -> int:
    """Run the desktop application and return the Qt process exit code."""

    qt_app = QApplication.instance() or QApplication([])
    qt_app.setFont(QFont("Segoe UI", 12))
    window = TwicArchiveManagerWindow(callbacks)
    window.show()
    return qt_app.exec()
