from __future__ import annotations

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.main_window import DesktopCallbacks, SavedSetup, TwicArchiveManagerWindow


def test_commands_are_clearly_labeled_buttons() -> None:
    qt_app = QApplication.instance() or QApplication([])
    window = TwicArchiveManagerWindow()

    assert window.sync_button.text() == "Sync"
    assert window.combine_button.text() == "Create Combined PGN"
    assert window.sync_button.parent() is window.commands_group
    assert window.combine_button.parent() is window.commands_group
    assert window.sync_button.maximumWidth() == 240
    assert "QPushButton:pressed" in window.styleSheet()
    assert "color: #f4f4f4" in window.styleSheet()
    assert window.palette().color(window.palette().ColorRole.Window).name() == "#000000"
    assert window.setup_list.font().pointSize() == 14

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
