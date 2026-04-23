from __future__ import annotations

import json
from pathlib import Path

import pytest

from angryrest.models.collection import Collection, KeyValue, RequestDef
from angryrest.models.environment import Environment
from angryrest.services.storage import StorageService


@pytest.fixture
def storage(tmp_path: Path) -> StorageService:
    return StorageService(base_dir=tmp_path)


class TestCollectionStorage:
    def test_load_empty_returns_empty_list(self, storage: StorageService) -> None:
        assert storage.load_collections() == []

    def test_save_and_load_single_collection(self, storage: StorageService) -> None:
        col = Collection(name="My API")
        storage.save_collection(col)

        loaded = storage.load_collections()
        assert len(loaded) == 1
        assert loaded[0].id == col.id
        assert loaded[0].name == "My API"

    def test_save_preserves_requests(self, storage: StorageService) -> None:
        col = Collection(
            name="With Requests",
            requests=[
                RequestDef(name="List users", method="GET", url="https://api.example.com/users"),
            ],
        )
        storage.save_collection(col)

        loaded = storage.load_collections()[0]
        assert len(loaded.requests) == 1
        assert loaded.requests[0].name == "List users"

    def test_save_overwrites_existing(self, storage: StorageService) -> None:
        col = Collection(name="Original")
        storage.save_collection(col)

        col.name = "Updated"
        storage.save_collection(col)

        loaded = storage.load_collections()
        assert len(loaded) == 1
        assert loaded[0].name == "Updated"

    def test_delete_collection(self, storage: StorageService) -> None:
        col = Collection(name="To Delete")
        storage.save_collection(col)
        assert len(storage.load_collections()) == 1

        storage.delete_collection(col.id)
        assert storage.load_collections() == []

    def test_delete_nonexistent_is_silent(self, storage: StorageService) -> None:
        storage.delete_collection("nonexistent-id")  # must not raise

    def test_multiple_collections_loaded(self, storage: StorageService) -> None:
        cols = [Collection(name=f"Col {i}") for i in range(3)]
        for c in cols:
            storage.save_collection(c)

        loaded = storage.load_collections()
        assert len(loaded) == 3

    def test_collection_order_respected(self, storage: StorageService) -> None:
        cols = [Collection(name=f"Col {i}") for i in range(3)]
        for c in cols:
            storage.save_collection(c)

        # Save order reversed
        reversed_ids = [c.id for c in reversed(cols)]
        storage.save_collection_order(reversed_ids)

        loaded = storage.load_collections()
        assert [l.id for l in loaded] == reversed_ids

    def test_collections_not_in_order_file_appended(self, storage: StorageService) -> None:
        col_a = Collection(name="A")
        col_b = Collection(name="B")
        storage.save_collection(col_a)
        storage.save_collection(col_b)

        # Order file only mentions col_a
        storage.save_collection_order([col_a.id])

        loaded = storage.load_collections()
        assert loaded[0].id == col_a.id
        assert any(c.id == col_b.id for c in loaded)

    def test_collection_file_is_valid_json(self, storage: StorageService) -> None:
        col = Collection(name="JSON Test", requests=[RequestDef(name="Req")])
        storage.save_collection(col)

        col_file = storage.collections_dir / f"{col.id}.json"
        data = json.loads(col_file.read_text(encoding="utf-8"))
        assert data["name"] == "JSON Test"
        assert len(data["requests"]) == 1


class TestEnvironmentStorage:
    def test_load_empty_returns_empty_list(self, storage: StorageService) -> None:
        assert storage.load_environments() == []

    def test_save_and_load_environments(self, storage: StorageService) -> None:
        envs = [
            Environment(name="Dev", variables={"base_url": "http://localhost:8000"}),
            Environment(name="Prod", variables={"base_url": "https://api.example.com"}),
        ]
        storage.save_environments(envs)

        loaded = storage.load_environments()
        assert len(loaded) == 2
        assert loaded[0].name == "Dev"
        assert loaded[1].variables["base_url"] == "https://api.example.com"

    def test_save_overwrites_all_environments(self, storage: StorageService) -> None:
        storage.save_environments([Environment(name="Old")])
        storage.save_environments([Environment(name="New1"), Environment(name="New2")])

        loaded = storage.load_environments()
        assert len(loaded) == 2
        assert loaded[0].name == "New1"

    def test_save_empty_list_clears_file(self, storage: StorageService) -> None:
        storage.save_environments([Environment(name="Temp")])
        storage.save_environments([])
        assert storage.load_environments() == []

    def test_environment_round_trip_preserves_variables(self, storage: StorageService) -> None:
        env = Environment(name="Full", variables={"a": "1", "b": "2", "c": "3"})
        storage.save_environments([env])

        loaded = storage.load_environments()[0]
        assert loaded.variables == {"a": "1", "b": "2", "c": "3"}
