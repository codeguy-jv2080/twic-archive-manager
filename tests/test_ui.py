from __future__ import annotations

import os
from dataclasses import replace
from threading import Event
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.main_window import DesktopCallbacks, SavedSetup, TwicArchiveManagerWindow


def test_commands_are_clearly_labeled_buttons() -> None:
    qt_app = QApplication.instance() or QApplication([])
    window = TwicArchiveManagerWindow()

    assert window.sync_button.text() == "Sync"
    assert window.extract_button.text() == "Extract ZIP"
    assert window.combine_button.text() == "Create Combined PGN"
    assert window.sync_button.parent() is window.commands_group
    assert window.extract_button.parent() is window.commands_group
    assert window.combine_button.parent() is window.commands_group
    assert window.sync_button.maximumWidth() == 240
    assert window.extract_button.property("runAction") is True
    assert "QPushButton:pressed" in window.styleSheet()
    assert "color: #f4f4f4" in window.styleSheet()
    assert window.palette().color(window.palette().ColorRole.Window).name() == "#000000"
    assert window.setup_list.font().pointSize() == 14

    window.close()
    qt_app.processEvents()


def _wait_for_operation(window, qt_app) -> None:
    if window._operation_thread is not None:
        loop = QEventLoop()
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        window._operation_thread.finished.connect(loop.quit)
        timeout.start(5000)
        loop.exec()
        timeout.stop()
    qt_app.processEvents()
    assert window._operation_thread is None


def test_extract_button_runs_only_extraction_and_logs_completion_once(monkeypatch) -> None:
    qt_app = QApplication.instance() or QApplication([])
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    setup = SavedSetup(id=1, name="Extract fixture", archive_root=r"C:\Archive")
    calls = []
    release = Event()
    message = "Extraction complete: 2 ZIP file(s) extracted, 1 already extracted, 0 failed."

    def extract(selected, reporter):
        calls.append(selected)
        assert release.wait(5)
        reporter.log("Extracting TWIC 970 PGN.")
        reporter.progress(3, 3, message)
        return {"message": message}

    window = TwicArchiveManagerWindow(DesktopCallbacks(
        load_setups=lambda: [setup], extract=extract,
    ))
    try:
        window.extract_button.click()
        assert window._operation_thread is not None
        assert window.cancel_button.isEnabled()
        for control in (window.sync_button, window.extract_button, window.combine_button,
                        window.setups_panel, window.selection_group):
            assert not control.isEnabled()
        release.set()
        _wait_for_operation(window, qt_app)
        assert calls == [setup]
        assert messages == []
        assert window.status_label.text() == message
        assert window.log_output.toPlainText().count(message) == 1
        for control in (window.sync_button, window.extract_button, window.combine_button):
            assert control.isEnabled()
    finally:
        release.set()
        _wait_for_operation(window, qt_app)
        window.close()
        qt_app.processEvents()


def test_extract_can_be_cancelled_and_reenables_actions(monkeypatch) -> None:
    qt_app = QApplication.instance() or QApplication([])
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    release = Event()
    cancelled = []

    def extract(_setup, reporter):
        assert release.wait(5)
        cancelled.append(reporter.cancelled)
        return {"message": "Extraction canceled."}

    window = TwicArchiveManagerWindow(DesktopCallbacks(
        load_setups=lambda: [SavedSetup(id=1, name="Example", archive_root=r"C:\Archive")],
        extract=extract,
    ))
    try:
        window.extract_button.click()
        window.cancel_button.click()
        release.set()
        _wait_for_operation(window, qt_app)
        assert cancelled == [True]
        assert messages == []
        assert window.status_label.text() == "Canceled."
        assert window.extract_button.isEnabled()
        assert not window.cancel_button.isEnabled()
    finally:
        release.set()
        _wait_for_operation(window, qt_app)
        window.close()
        qt_app.processEvents()


def test_extract_requires_a_saved_unmodified_setup(monkeypatch) -> None:
    qt_app = QApplication.instance() or QApplication([])
    messages = []
    calls = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    setups = []
    window = TwicArchiveManagerWindow(DesktopCallbacks(
        load_setups=lambda: setups, extract=lambda *_: calls.append(True),
    ))
    try:
        window.extract_button.click()
        assert messages == ["Save and select a Saved Setup before running an action."]
        setups.append(SavedSetup(id=1, name="Example", archive_root=r"C:\Archive"))
        window.reload_setups()
        window.keep_zips_checkbox.setChecked(False)
        window.extract_button.click()
        assert messages[-1] == "Save your Saved Setup changes before running an action."
        assert not calls
        assert window._operation_thread is None
    finally:
        window.close()
        qt_app.processEvents()


def test_extract_button_disabled_for_every_operation() -> None:
    qt_app = QApplication.instance() or QApplication([])
    window = TwicArchiveManagerWindow()
    try:
        for cancellable in (True, False):
            window._set_operation_controls(True, cancellable=cancellable)
            assert not window.extract_button.isEnabled()
            window._set_operation_controls(False)
            assert window.extract_button.isEnabled()
    finally:
        window.close()
        qt_app.processEvents()


def test_extract_button_processes_saved_zip_without_network_or_combining(tmp_path, monkeypatch):
    from app.database import create_profile, initialize_database
    from app.main import create_desktop_callbacks
    from app.services.archive import ArchiveLayout

    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Manual Extract ZIP must not download, sync, or combine")

    for target in ("app.main.sync_profile", "app.main.combine_profile",
                   "app.services.sync.download_file", "app.services.sync.fetch_latest_issue",
                   "app.services.archive.urlopen", "app.services.catalog.urlopen"):
        monkeypatch.setattr(target, forbidden)
    initialize_database()
    setup = create_profile(
        name="Extract fixture", archive_root=str(tmp_path / "archive"),
        extract_archives=False, keep_zip_files=True, combine_after_sync=True,
    )
    layout = ArchiveLayout.create(setup["archive_root"])
    downloaded = layout.downloads("pgn") / "twic970g.zip"
    payload = '[Event "Fixture"]\n\n1. e4 e5 *\n'
    with zipfile.ZipFile(downloaded, "w") as archive:
        archive.writestr("twic970.pgn", payload)

    qt_app = QApplication.instance() or QApplication([])
    window = TwicArchiveManagerWindow(create_desktop_callbacks())
    try:
        assert not window.extract_checkbox.isChecked()
        window.extract_button.click()
        _wait_for_operation(window, qt_app)
        assert messages == []
        assert (layout.extracted_root("pgn") / "twic970.pgn").read_text() == payload
        assert downloaded.exists()
        assert not layout.combined_pgn_path.exists()
        final = "Extraction complete: 1 ZIP file(s) extracted, 0 already extracted, 0 failed."
        assert window.status_label.text() == final
        assert window.log_output.toPlainText().count(final) == 1
        assert window.extract_button.isEnabled()
    finally:
        _wait_for_operation(window, qt_app)
        window.close()
        qt_app.processEvents()


def test_fresh_installed_window_does_not_load_portable_choices(tmp_path, monkeypatch):
    from app import settings
    from app.database import create_profile, initialize_database, set_app_setting
    from app.main import create_desktop_callbacks

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(settings.sys, "argv", [str(tmp_path / "portable" / "app.exe")])
    initialize_database()
    create_profile(name="Portable fixture", archive_root=str(tmp_path / "archive"),
                   combine_after_sync=True, schedule_text="weekly Tuesday 20:00")
    set_app_setting("theme", "light")
    portable_db = settings.database_path()
    original = portable_db.read_bytes()

    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / settings.INSTALLATION_MARKER).write_text("installed\n")
    monkeypatch.setattr(settings.sys, "argv", [str(installed / "app.exe")])
    qt_app = QApplication.instance() or QApplication([])
    window = TwicArchiveManagerWindow(create_desktop_callbacks())
    try:
        assert window.setup_list.count() == 0
        assert not window.combine_after_sync_checkbox.isChecked()
        assert window.palette().color(window.palette().ColorRole.Window).name() == "#000000"
        assert portable_db.read_bytes() == original
    finally:
        window.close()
        qt_app.processEvents()


def test_theme_toggle_changes_colors_without_changing_content_or_fonts() -> None:
    qt_app = QApplication.instance() or QApplication([])
    saved = []
    window = TwicArchiveManagerWindow(DesktopCallbacks(save_theme=saved.append))
    window.setup_name_edit.setText("Unsaved draft")
    window.log_output.setPlainText("Existing activity")
    original_font = window.setup_list.font()
    assert window.theme_button.text() == "Light / Dark"

    window.theme_button.click()

    assert saved == ["light"]
    assert window.palette().color(window.palette().ColorRole.Window).name() == "#d1d1d1"
    assert window.palette().color(window.palette().ColorRole.Text).name() == "#202225"
    assert window.palette().color(window.palette().ColorRole.Highlight).name() == "#c6a300"
    assert window.palette().color(window.palette().ColorRole.HighlightedText).name() == "#ffffff"
    assert "color: #202225" in window.styleSheet()
    assert window.setup_list.font() == original_font
    assert window.setup_name_edit.text() == "Unsaved draft"
    assert window.log_output.toPlainText() == "Existing activity"

    window.theme_button.click()
    assert saved == ["light", "dark"]
    assert window.palette().color(window.palette().ColorRole.Window).name() == "#000000"
    assert "color: #f4f4f4" in window.styleSheet()
    window.close()
    qt_app.processEvents()


def test_theme_loaded_when_window_opens_and_invalid_preference_falls_back_to_dark() -> None:
    qt_app = QApplication.instance() or QApplication([])
    for stored, expected in [("light", "#d1d1d1"), ("invalid", "#000000")]:
        window = TwicArchiveManagerWindow(DesktopCallbacks(load_theme=lambda: stored))
        assert window.palette().color(window.palette().ColorRole.Window).name() == expected
        window.close()
    qt_app.processEvents()


def test_failed_theme_save_does_not_switch_modes(monkeypatch) -> None:
    qt_app = QApplication.instance() or QApplication([])
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))

    def fail(_: str):
        raise OSError("Cannot write settings")

    window = TwicArchiveManagerWindow(DesktopCallbacks(save_theme=fail))
    window.theme_button.click()
    assert window.palette().color(window.palette().ColorRole.Window).name() == "#000000"
    assert messages == ["Could not save the theme: Cannot write settings"]
    window.close()
    qt_app.processEvents()


def test_changing_a_selected_setup_name_creates_a_new_setup() -> None:
    qt_app = QApplication.instance() or QApplication([])
    original = SavedSetup(id=1, name="Original", archive_root=r"C:\Archive\One")
    saved_values: list[SavedSetup] = []

    def save_setup(setup: SavedSetup) -> SavedSetup:
        saved_values.append(setup)
        return replace(setup, id=2)

    window = TwicArchiveManagerWindow(
        DesktopCallbacks(load_setups=lambda: [original], save_setup=save_setup)
    )
    window.setup_name_edit.setText("Second")
    window.archive_root_edit.setText(r"C:\Archive\Two")

    window.save_setup()

    assert saved_values[0].id is None
    assert saved_values[0].name == "Second"
    window.close()
    qt_app.processEvents()


def test_clear_activity_clears_only_the_visible_activity() -> None:
    qt_app = QApplication.instance() or QApplication([])
    window = TwicArchiveManagerWindow()
    window.log_output.setPlainText("Previous activity")
    window.status_label.setText("Previous status")
    window.progress_bar.setValue(50)

    window.clear_activity()

    assert window.log_output.toPlainText() == ""
    assert window.status_label.text() == "Ready."
    assert window.progress_bar.value() == 0
    assert window.progress_bar.format() == "Ready"
    window.close()
    qt_app.processEvents()


def test_delete_button_deletes_the_selected_setup() -> None:
    qt_app = QApplication.instance() or QApplication([])
    setup = SavedSetup(id=1, name="Delete me", archive_root=r"C:\Archive")
    remaining = [setup]

    def delete_setup(selected: SavedSetup) -> None:
        assert selected == setup
        remaining.clear()

    window = TwicArchiveManagerWindow(
        DesktopCallbacks(load_setups=lambda: remaining, delete_setup=delete_setup)
    )

    def confirm_delete() -> None:
        for widget in qt_app.topLevelWidgets():
            if isinstance(widget, QMessageBox):
                for button in widget.buttons():
                    if button.text() == "Delete":
                        button.click()
                        return

    QTimer.singleShot(0, confirm_delete)
    window.delete_selected_setup()

    assert remaining == []
    assert window.setup_list.count() == 0
    window.close()
    qt_app.processEvents()


def test_operation_failure_is_logged_once(monkeypatch) -> None:
    qt_app = QApplication.instance() or QApplication([])
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    window = TwicArchiveManagerWindow()

    window._operation_failed("No extracted PGN files are available to combine.")

    expected = "The operation failed: No extracted PGN files are available to combine."
    assert window.log_output.toPlainText() == expected
    assert window.status_label.text() == expected
    assert messages == [expected]
    window.close()
    qt_app.processEvents()


def test_schedule_details_stay_in_activity_not_the_status_heading(monkeypatch) -> None:
    qt_app = QApplication.instance() or QApplication([])
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[-1]))
    setup = SavedSetup(id=1, name="Main", archive_root=r"C:\Archive")
    details = 'Schedule for "Main": weekly Monday 20:00.\n\nLast Run Time: 9/7/2026\nLast Result: 0'
    window = TwicArchiveManagerWindow(DesktopCallbacks(
        load_setups=lambda: [setup], view_schedule=lambda _: {"message": details},
    ))

    window.view_schedule()

    assert window.status_label.text() == details.splitlines()[0]
    assert window.log_output.toPlainText() == details
    assert messages == [details]
    window.close()
    qt_app.processEvents()
