from __future__ import annotations

from typing import Protocol

from angryrest.domain.models.collection import Collection
from angryrest.domain.models.environment import Environment


class StoragePort(Protocol):
    def load_collections(self) -> list[Collection]: ...

    def save_collection(self, collection: Collection) -> None: ...

    def delete_collection(self, collection_id: str) -> None: ...

    def save_collection_order(self, collection_ids: list[str]) -> None: ...

    def load_environments(self) -> list[Environment]: ...

    def save_environments(self, environments: list[Environment]) -> None: ...