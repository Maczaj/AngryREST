from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import Property, QObject, QUrl, QTimer
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from angryrest.application.services.collection_service import CollectionService
from angryrest.application.viewmodels.collections_viewmodel import (
    CollectionsViewModel,
)
from angryrest.infrastructure.storage.json_storage import JsonStorageAdapter


class _TestTheme(QObject):
    bgPrimary = Property(str, lambda self: "#1e1e1e", constant=True)
    bgSecondary = Property(str, lambda self: "#252526", constant=True)
    bgInput = Property(str, lambda self: "#2d2d2d", constant=True)
    textPrimary = Property(str, lambda self: "#d4d4d4", constant=True)
    textSecondary = Property(str, lambda self: "#cccccc", constant=True)
    textMuted = Property(str, lambda self: "#666666", constant=True)
    textStatusBar = Property(str, lambda self: "#969696", constant=True)
    borderDefault = Property(str, lambda self: "#3c3c3c", constant=True)
    borderButton = Property(str, lambda self: "#4a4a4a", constant=True)
    accentFocus = Property(str, lambda self: "#007acc", constant=True)
    accentSelection = Property(str, lambda self: "#264f78", constant=True)
    accentSelected = Property(str, lambda self: "#094771", constant=True)
    buttonDefault = Property(str, lambda self: "#3c3c3c", constant=True)
    buttonHover = Property(str, lambda self: "#4a4a4a", constant=True)
    buttonPressed = Property(str, lambda self: "#555555", constant=True)
    buttonDisabled = Property(str, lambda self: "#2d2d2d", constant=True)
    buttonText = Property(str, lambda self: "#cccccc", constant=True)
    buttonTextDisabled = Property(str, lambda self: "#666666", constant=True)
    treeHover = Property(str, lambda self: "#2a3d52", constant=True)
    methodGet = Property(str, lambda self: "#4ec9b0", constant=True)
    methodPost = Property(str, lambda self: "#569cd6", constant=True)
    methodPut = Property(str, lambda self: "#dcdcaa", constant=True)
    methodPatch = Property(str, lambda self: "#2d8e6e", constant=True)
    methodDelete = Property(str, lambda self: "#f44747", constant=True)
    methodHead = Property(str, lambda self: "#5a5a5a", constant=True)
    methodOptions = Property(str, lambda self: "#808080", constant=True)
    status2xx = Property(str, lambda self: "#4ec9b0", constant=True)
    status3xx = Property(str, lambda self: "#569cd6", constant=True)
    status4xx = Property(str, lambda self: "#dcdcaa", constant=True)
    status5xx = Property(str, lambda self: "#f44747", constant=True)
    paramResolvedFg = Property(str, lambda self: "#4ec9b0", constant=True)
    paramResolvedBg = Property(str, lambda self: "#1e3a2f", constant=True)
    paramUnresolvedFg = Property(str, lambda self: "#f44747", constant=True)
    paramUnresolvedBg = Property(str, lambda self: "#3a1e1e", constant=True)


QML_DIR = (Path(__file__).parent.parent.parent / "src" / "angryrest" / "ui" / "qml").resolve()


def _find_item_by_text(parent: QQuickItem, text: str) -> QQuickItem | None:
    return _find_nested_by_text(parent, text)


def _find_nested_by_text(item: QQuickItem, text: str) -> QQuickItem | None:
    item_text = item.property("text")
    if isinstance(item_text, str) and item_text == text:
        return item
    for child in item.findChildren(QQuickItem):
        result = _find_nested_by_text(child, text)
        if result is not None:
            return result
    return None


def _find_list_view(parent: QQuickItem) -> QQuickItem | None:
    for child in parent.findChildren(QQuickItem):
        class_name = child.metaObject().className()
        if "ListView" in class_name or "TreeView" in class_name:
            return child
    return None


def _find_text_containing(parent: QQuickItem, substring: str) -> bool:
    for child in parent.findChildren(QQuickItem):
        text = child.property("text")
        if isinstance(text, str) and substring in text:
            return True
    return False


def _load_main_window(qtbot, theme: QObject, vm: CollectionsViewModel) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    theme.setParent(engine)
    vm.setParent(engine)
    engine.addImportPath(str(QML_DIR))
    engine.rootContext().setContextProperty("collectionsVM", vm)
    engine.rootContext().setContextProperty("theme", theme)
    engine.load(str(QML_DIR / "MainWindow.qml"))

    if not engine.rootObjects():
        raise RuntimeError("MainWindow.qml failed to load")

    return engine


def _cleanup_engine(engine: QQmlApplicationEngine) -> None:
    engine.clearComponentCache()
    engine.deleteLater()


@pytest.fixture
def theme():
    return _TestTheme()


@pytest.fixture
def vm_and_storage():
    tmp = tempfile.TemporaryDirectory()
    storage = JsonStorageAdapter(base_dir=Path(tmp.name))
    service = CollectionService(storage)
    vm = CollectionsViewModel(service)
    vm.load()
    yield vm
    tmp.cleanup()


@pytest.mark.skipif(
    os.environ.get("QT_QPA_PLATFORM", "") != "offscreen",
    reason="Requires QT_QPA_PLATFORM=offscreen",
)
class TestCollectionsPanelViaMainWindow:
    """Test CollectionsPanel by loading MainWindow and inspecting the embedded panel."""

    def test_collections_list_responds_to_model(self, qtbot, theme, vm_and_storage) -> None:
        vm = vm_and_storage
        engine = _load_main_window(qtbot, theme, vm)

        assert vm.rowCount() == 0

        root = engine.rootObjects()[0]
        list_view = _find_list_view(root)
        assert list_view is not None, "ListView should be embedded in MainWindow"

        vm.create_collection("API v1")
        assert vm.rowCount() == 1

        vm.create_collection("API v2")
        assert vm.rowCount() == 2

        _cleanup_engine(engine)

    def test_add_request_button_disabled_when_empty(self, qtbot, theme, vm_and_storage) -> None:
        vm = vm_and_storage
        engine = _load_main_window(qtbot, theme, vm)

        root = engine.rootObjects()[0]
        add_req_btn = _find_item_by_text(root, "+ Request")
        assert add_req_btn is not None, "Add Request button should be present"
        assert add_req_btn.property("enabled") is False, (
            "Button should be disabled when model is empty"
        )

        vm.create_collection("Test")
        assert add_req_btn.property("enabled") is True, (
            "Button should become enabled after adding a collection"
        )

        _cleanup_engine(engine)

    def test_add_collection_button_present(self, qtbot, theme, vm_and_storage) -> None:
        engine = _load_main_window(qtbot, theme, vm_and_storage)

        root = engine.rootObjects()[0]
        add_btn = _find_item_by_text(root, "+ Collection")
        assert add_btn is not None, "Add Collection button should be present"

        _cleanup_engine(engine)


@pytest.mark.skipif(
    os.environ.get("QT_QPA_PLATFORM", "") != "offscreen",
    reason="Requires QT_QPA_PLATFORM=offscreen",
)
class TestMainWindowQML:
    def test_main_window_renders_title_and_theme(self, qtbot, theme, vm_and_storage) -> None:
        engine = _load_main_window(qtbot, theme, vm_and_storage)
        root = engine.rootObjects()[0]

        assert root.property("title") == "AngryREST"

        bg_color = root.property("color")
        assert bg_color.name() == "#1e1e1e", f"Expected #1e1e1e, got {bg_color.name()}"

        _cleanup_engine(engine)

    def test_empty_state_placeholder_rendered(self, qtbot, theme, vm_and_storage) -> None:
        engine = _load_main_window(qtbot, theme, vm_and_storage)
        root = engine.rootObjects()[0]

        assert _find_text_containing(root, "Select a request"), (
            "Empty state text should be rendered"
        )
        _cleanup_engine(engine)

    def test_status_bar_shows_version(self, qtbot, theme, vm_and_storage) -> None:
        engine = _load_main_window(qtbot, theme, vm_and_storage)
        root = engine.rootObjects()[0]

        assert _find_text_containing(root, "AngryREST v"), (
            "Status bar version should be rendered"
        )
        _cleanup_engine(engine)

    def test_logs_button_rendered(self, qtbot, theme, vm_and_storage) -> None:
        engine = _load_main_window(qtbot, theme, vm_and_storage)
        root = engine.rootObjects()[0]

        logs_btn = _find_item_by_text(root, "Logs")
        assert logs_btn is not None, "Logs button should be rendered"
        _cleanup_engine(engine)

    def test_renders_without_critical_qml_errors(self, qtbot, theme, vm_and_storage) -> None:
        engine = _load_main_window(qtbot, theme, vm_and_storage)
        root_objects = engine.rootObjects()
        assert len(root_objects) >= 1, "At least one root object expected"
        _cleanup_engine(engine)