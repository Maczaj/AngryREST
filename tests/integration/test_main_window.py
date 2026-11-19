from __future__ import annotations

import os

import pytest

from tests.integration.conftest import (
    cleanup_engine,
    find_item_by_text,
    find_text_containing,
    load_qml_engine,
)


@pytest.mark.skipif(
    os.environ.get("QT_QPA_PLATFORM", "") != "offscreen",
    reason="Requires QT_QPA_PLATFORM=offscreen",
)
class TestMainWindowQML:
    def test_main_window_renders_title_and_theme(self, qtbot, theme, vm_and_storage) -> None:
        engine = load_qml_engine(theme, vm_and_storage, "MainWindow.qml")
        root = engine.rootObjects()[0]

        assert root.property("title") == "AngryREST"

        bg_color = root.property("color")
        assert bg_color.name() == "#1e1e1e", f"Expected #1e1e1e, got {bg_color.name()}"

        cleanup_engine(engine)

    def test_empty_state_placeholder_rendered(self, qtbot, theme, vm_and_storage) -> None:
        engine = load_qml_engine(theme, vm_and_storage, "MainWindow.qml")
        root = engine.rootObjects()[0]

        assert find_text_containing(root, "Select a request"), (
            "Empty state text should be rendered"
        )
        cleanup_engine(engine)

    def test_status_bar_shows_version(self, qtbot, theme, vm_and_storage) -> None:
        engine = load_qml_engine(theme, vm_and_storage, "MainWindow.qml")
        root = engine.rootObjects()[0]

        assert find_text_containing(root, "AngryREST v"), (
            "Status bar version should be rendered"
        )
        cleanup_engine(engine)

    def test_logs_button_rendered(self, qtbot, theme, vm_and_storage) -> None:
        engine = load_qml_engine(theme, vm_and_storage, "MainWindow.qml")
        root = engine.rootObjects()[0]

        logs_btn = find_item_by_text(root, "Logs")
        assert logs_btn is not None, "Logs button should be rendered"
        cleanup_engine(engine)

    def test_renders_without_critical_qml_errors(self, qtbot, theme, vm_and_storage) -> None:
        engine = load_qml_engine(theme, vm_and_storage, "MainWindow.qml")
        root_objects = engine.rootObjects()
        assert len(root_objects) >= 1, "At least one root object expected"
        cleanup_engine(engine)
