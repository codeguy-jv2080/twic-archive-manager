"""Headless layout checks using the same font as the desktop entry point."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QSplitter, QStyle, QStyleOptionButton, QStyleOptionFrame,
)

from app.ui.main_window import DesktopCallbacks, SavedSetup, TwicArchiveManagerWindow


@pytest.fixture
def desktop_application():
    application = QApplication.instance() or QApplication([])
    previous_font = application.font()
    # Qt's offscreen plugin does not discover Windows fonts automatically.
    # Load the actual production font so the assertions do not measure empty
    # fallback glyphs (which all have the same width).
    font_ids = []
    if os.name == "nt" and application.platformName() == "offscreen":
        fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(fonts / filename))
            assert font_id >= 0, f"Could not load test font: {filename}"
            font_ids.append(font_id)
    application.setFont(QFont("Segoe UI", 12))
    try:
        yield application
    finally:
        application.setFont(previous_font)
        application.processEvents()
        for font_id in font_ids:
            QFontDatabase.removeApplicationFont(font_id)


def _assert_checkbox_text_fits(window):
    checkbox = window.combine_after_sync_checkbox
    assert checkbox.text() == "Automatically create combined PGN\nafter download/extraction"
    option = QStyleOptionButton()
    checkbox.initStyleOption(option)
    content = checkbox.style().subElementRect(
        QStyle.SubElement.SE_CheckBoxContents, option, checkbox
    )
    metrics = checkbox.fontMetrics()
    lines = checkbox.text().splitlines()
    assert content.width() >= max(metrics.horizontalAdvance(line) for line in lines)
    text_bounds = metrics.boundingRect(
        QRect(0, 0, 10000, 10000), Qt.AlignmentFlag.AlignLeft, checkbox.text()
    )
    assert content.height() >= text_bounds.height()
    assert checkbox.width() >= checkbox.sizeHint().width()
    assert checkbox.height() >= checkbox.sizeHint().height()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_proportional_panels_keep_controls_and_checkbox_readable(desktop_application, theme):
    setup = SavedSetup(
        id=1, name="Example", archive_root=r"C:\Chess Archives\Weekly Downloads\Main collection\TWIC",
    )
    window = TwicArchiveManagerWindow(DesktopCallbacks(
        load_theme=lambda: theme, load_setups=lambda: [setup],
    ))
    try:
        window.show()  # The offscreen Qt platform never creates a desktop window.
        desktop_application.processEvents()
        assert not window.findChildren(QSplitter)
        left = window.setups_panel
        assert left.minimumWidth() == 540
        assert left.maximumWidth() > 540
        assert left.width() >= 540
        original_font = window.archive_root_edit.font()
        work = window.selection_group.parentWidget()
        widths = []

        for size in ((1180, 760), (1920, 1000), (900, 620)):
            window.resize(*size)
            desktop_application.processEvents()
            assert left.width() >= 540
            assert window.archive_root_edit.font() == original_font
            assert left.geometry().right() < work.geometry().left()
            assert window.centralWidget().rect().contains(left.geometry())
            assert window.centralWidget().rect().contains(work.geometry())
            _assert_checkbox_text_fits(window)

            for control in (
                window.setup_name_edit,
                window.archive_root_edit,
                window.schedule_type_combo,
                window.apply_schedule_button,
                window.view_schedule_button,
                window.save_setup_button,
                window.sync_button,
                window.combine_button,
                window.theme_button,
                window.clear_activity_button,
                window.cancel_button,
            ):
                assert control.isVisible()
                assert control.parentWidget().rect().contains(control.geometry())
                top_left = control.mapTo(window.centralWidget(), QPoint(0, 0))
                assert window.centralWidget().rect().contains(top_left)
                if left.isAncestorOf(control):
                    assert control.width() >= control.minimumSizeHint().width()
            assert window.archive_root_edit.width() >= 200
            widths.append((left.width(), work.width(), window.archive_root_edit.width()))

            if size[0] == 1920:
                assert left.width() / (left.width() + work.width()) == pytest.approx(0.4, abs=0.01)
                field = window.archive_root_edit
                option = QStyleOptionFrame()
                field.initStyleOption(option)
                content = field.style().subElementRect(
                    QStyle.SubElement.SE_LineEditContents, option, field
                )
                margins = field.textMargins()
                text_width = field.fontMetrics().horizontalAdvance(setup.archive_root)
                assert text_width <= content.width() - margins.left() - margins.right() - 4

        assert widths[1][0] >= widths[0][0] + 150
        assert widths[1][1] > widths[0][1]
        assert widths[1][2] >= widths[0][2] + 150
    finally:
        window.close()
        desktop_application.processEvents()


def test_theme_switch_keeps_layout_and_checkbox_behavior(desktop_application):
    saved_themes = []
    setup = SavedSetup(id=1, name="Example", archive_root=r"C:\Chess\TWIC")
    window = TwicArchiveManagerWindow(DesktopCallbacks(
        load_setups=lambda: [setup], save_theme=saved_themes.append,
    ))
    try:
        window.show()
        desktop_application.processEvents()
        initial_left = window.setups_panel.geometry()
        initial_font = window.combine_after_sync_checkbox.font()
        assert window._setup_from_form() == setup
        assert not window.combine_after_sync_checkbox.isChecked()

        for expected in ("light", "dark"):
            window.theme_button.click()
            desktop_application.processEvents()
            assert saved_themes[-1] == expected
            assert window.setups_panel.geometry() == initial_left
            assert window.combine_after_sync_checkbox.font() == initial_font
            assert window._setup_from_form() == setup
            _assert_checkbox_text_fits(window)

        window.combine_after_sync_checkbox.click()
        assert window._setup_from_form().combine_after_sync
        window.combine_after_sync_checkbox.click()
        assert window._setup_from_form() == setup
    finally:
        window.close()
        desktop_application.processEvents()
