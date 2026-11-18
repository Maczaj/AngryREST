from __future__ import annotations

import os
from pathlib import Path
import tempfile

import pytest

from PySide6.QtCore import Property, QObject
from PySide6.QtQml import QQmlApplicationEngine

from angryrest.application.services.collection_service import CollectionService
from angryrest.application.viewmodels.collections_viewmodel import CollectionsViewModel
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


@pytest.mark.skipif(
    os.environ.get("QT_QPA_PLATFORM", "") != "offscreen",
    reason="Requires QT_QPA_PLATFORM=offscreen",
)
class TestAppBootstrap:
    def test_app_initializes(self, qtbot) -> None:
        qml_dir = Path(__file__).parent.parent.parent / "src" / "angryrest" / "ui" / "qml"

        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            collection_service = CollectionService(storage)

            engine = QQmlApplicationEngine()
            vm = CollectionsViewModel(collection_service)
            vm.setParent(engine)
            engine.rootContext().setContextProperty(
                "collectionsVM", vm
            )
            theme = _TestTheme(parent=engine)
            engine.rootContext().setContextProperty("theme", theme)

            engine.addImportPath(str(qml_dir.resolve()))
            engine.load(str((qml_dir / "MainWindow.qml").resolve()))

            root_objects = engine.rootObjects()
            assert len(root_objects) > 0

    def test_create_collection(self, qtbot) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            assert vm.rowCount() == 0

            result = vm.create_collection("Test API")
            assert result is True
            assert vm.rowCount() == 1

            loaded = storage.load_collections()
            assert len(loaded) == 1
            assert loaded[0].name == "Test API"

    def test_rename_collection(self, qtbot) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("Old Name")
            vm.rename_collection(0, "New Name")

            assert vm.data(vm.index(0, 0), CollectionsViewModel.NameRole) == "New Name"

    def test_delete_collection(self, qtbot) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("To Delete")
            assert vm.rowCount() == 1

            vm.delete_collection(0)
            assert vm.rowCount() == 0