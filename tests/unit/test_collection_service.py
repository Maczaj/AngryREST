from __future__ import annotations

from pathlib import Path
import tempfile

from angryrest.application.services.collection_service import CollectionService
from angryrest.infrastructure.storage.json_storage import JsonStorageAdapter


class TestCollectionService:
    def test_create_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)

            c1 = service.create("API v1")
            c2 = service.create("API v2")

            all_cols = service.load_all()
            assert len(all_cols) == 2
            assert {c.name for c in all_cols} == {"API v1", "API v2"}

    def test_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)

            col = service.create("Old")
            service.rename(col, "New")

            loaded = service.load_all()
            assert loaded[0].name == "New"

    def test_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)

            c1 = service.create("Keep")
            c2 = service.create("Delete")
            service.delete(c2)

            remaining = service.load_all()
            assert len(remaining) == 1
            assert remaining[0].id == c1.id

    def test_add_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)

            col = service.create("My API")
            result = service.add_request(col, "List Users")

            assert len(result.requests) == 1
            assert result.requests[0].name == "List Users"

            loaded = service.load_all()
            assert len(loaded[0].requests) == 1

    def test_save_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorageAdapter(base_dir=Path(tmp))
            service = CollectionService(storage)

            c1 = service.create("A")
            c2 = service.create("B")
            c3 = service.create("C")

            service.save_order([c3, c1, c2])
            loaded = service.load_all()
            assert [c.id for c in loaded] == [c3.id, c1.id, c2.id]
