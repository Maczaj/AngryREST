from __future__ import annotations

from angryrest.domain.models.collection import Collection
from angryrest.domain.ports.storage_port import StoragePort


class CollectionService:
    def __init__(self, storage: StoragePort) -> None:
        self._storage = storage

    def load_all(self) -> list[Collection]:
        return self._storage.load_collections()

    def create(self, name: str) -> Collection:
        collection = Collection(name=name)
        self._storage.save_collection(collection)

        collections = self._storage.load_collections()
        order = [c.id for c in collections]
        self._storage.save_collection_order(order)

        return collection

    def rename(self, collection: Collection, new_name: str) -> None:
        collection.name = new_name
        self._storage.save_collection(collection)

    def delete(self, collection: Collection) -> None:
        self._storage.delete_collection(collection.id)
        collections = self._storage.load_collections()
        self._storage.save_collection_order([c.id for c in collections])

    def add_request(self, collection: Collection, name: str = "New Request") -> Collection:
        from angryrest.domain.models.collection import RequestDef

        request = RequestDef(name=name)
        collection.requests.append(request)
        self._storage.save_collection(collection)
        return collection

    def save_order(self, collections: list[Collection]) -> None:
        self._storage.save_collection_order([c.id for c in collections])