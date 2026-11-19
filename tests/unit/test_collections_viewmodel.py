from __future__ import annotations

from pathlib import Path
import tempfile

from PySide6.QtCore import QModelIndex

from angryrest.application.services.collection_service import CollectionService
from angryrest.application.viewmodels.collections_viewmodel import (
    CollectionsViewModel,
)
from angryrest.domain.models.collection import Collection, RequestDef
from angryrest.infrastructure.storage.json_storage import JsonStorageAdapter


class TestCollectionsViewModel:
    def test_empty_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            assert vm.rowCount() == 0
            assert vm.selected_index == -1
            assert vm.collections == []

    def test_create_collection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            result = vm.create_collection("Test")
            assert result is True
            assert vm.rowCount() == 1
            assert vm.collection_at(0).name == "Test"

    def test_select_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("C1")
            vm.create_collection("C2")

            vm.select_index(0)
            assert vm.selected_index == 0

            vm.select_index(1)
            assert vm.selected_index == 1

    def test_rename_collection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("Old")
            vm.rename_collection(0, "New")

            assert vm.data(vm.index(0, 0), CollectionsViewModel.NameRole) == "New"
            assert vm.collection_at(0).name == "New"

    def test_delete_collection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("First")
            vm.create_collection("Second")
            vm.delete_collection(0)

            assert vm.rowCount() == 1
            assert vm.collection_at(0).name == "Second"

    def test_delete_selected_collection_resets_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("Solo")
            vm.select_index(0)
            vm.delete_collection(0)

            assert vm.rowCount() == 0
            assert vm.selected_index == -1

    def test_delete_updates_selected_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("A")
            vm.create_collection("B")
            vm.create_collection("C")

            vm.select_index(2)
            vm.delete_collection(1)

            assert vm.selected_index == 1

    def test_data_for_invalid_index_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            result = vm.data(QModelIndex(), CollectionsViewModel.NameRole)
            assert result is None

    def test_collection_at_out_of_range_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            assert vm.collection_at(-1) is None
            assert vm.collection_at(999) is None

    def test_data_id_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("DataTest")
            cid = vm.collection_at(0).id

            assert vm.data(vm.index(0, 0), CollectionsViewModel.IdRole) == cid

    def test_data_request_count_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("WithRequests")
            collection = vm.collection_at(0)
            collection.requests.append(RequestDef(name="Req1"))
            collection.requests.append(RequestDef(name="Req2"))

            count = vm.data(vm.index(0, 0), CollectionsViewModel.RequestCountRole)
            assert count == 2

    def test_rename_out_of_range_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.rename_collection(-1, "Bad")
            vm.rename_collection(999, "Bad")
            assert vm.rowCount() == 0

    def test_delete_out_of_range_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("Solo")
            vm.delete_collection(-1)
            vm.delete_collection(999)

            assert vm.rowCount() == 1

    def test_set_collections_replaces_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("Old")
            vm.set_collections([Collection(name="New1"), Collection(name="New2")])

            assert vm.rowCount() == 2
            assert vm.collection_at(0).name == "New1"
            assert vm.collection_at(1).name == "New2"

    def test_selected_index_changed_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            vm.create_collection("Signal")
            fired = []

            vm.selected_index_changed.connect(lambda: fired.append(True))
            vm.select_index(0)

            assert len(fired) == 1

    def test_count_changed_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)
            vm = CollectionsViewModel(service)
            vm.load()

            fired = []
            vm.count_changed.connect(lambda: fired.append(True))

            vm.create_collection("C1")
            vm.create_collection("C2")

            assert len(fired) == 2
