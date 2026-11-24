from __future__ import annotations

import os

import pytest

from angryrest.application.viewmodels.collections_viewmodel import (
    CollectionsViewModel,
)

from tests.integration.conftest import (
    cleanup_engine,
    find_item_by_text,
    find_list_view,
    load_qml_engine,
)


@pytest.mark.skipif(
    os.environ.get("QT_QPA_PLATFORM", "") != "offscreen",
    reason="Requires QT_QPA_PLATFORM=offscreen",
)
class TestCollectionsPanel:
    """Test the CollectionsPanel QML component in isolation."""

    def test_collections_list_responds_to_model(self, qtbot, theme, vm_and_storage) -> None:
        vm: CollectionsViewModel = vm_and_storage
        engine = load_qml_engine(theme, vm, "CollectionsPanel.qml")

        assert vm.rowCount() == 0

        root = engine.rootObjects()[0]
        list_view = find_list_view(root)
        assert list_view is not None, "ListView should be present in CollectionsPanel"

        vm.create_collection("API v1")
        assert vm.rowCount() == 1

        vm.create_collection("API v2")
        assert vm.rowCount() == 2

        cleanup_engine(engine)

    def test_add_request_button_disabled_when_empty(self, qtbot, theme, vm_and_storage) -> None:
        vm: CollectionsViewModel = vm_and_storage
        engine = load_qml_engine(theme, vm, "CollectionsPanel.qml")

        root = engine.rootObjects()[0]
        add_req_btn = find_item_by_text(root, "+ Request")
        assert add_req_btn is not None, "Add Request button should be present"
        assert add_req_btn.property("enabled") is False, (
            "Button should be disabled when model is empty"
        )

        vm.create_collection("Test")
        assert add_req_btn.property("enabled") is True, (
            "Button should become enabled after adding a collection"
        )

        cleanup_engine(engine)

    def test_add_collection_button_present(self, qtbot, theme, vm_and_storage) -> None:
        engine = load_qml_engine(theme, vm_and_storage, "CollectionsPanel.qml")

        root = engine.rootObjects()[0]
        add_btn = find_item_by_text(root, "+ Collection")
        assert add_btn is not None, "Add Collection button should be present"

        cleanup_engine(engine)
