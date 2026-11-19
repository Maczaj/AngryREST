from __future__ import annotations

import json
from pathlib import Path

from angryrest.domain.models.collection import Collection
from angryrest.domain.models.environment import Environment


class JsonStorageAdapter:
    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path.home() / ".angryrest"
        self.base_dir = Path(base_dir)
        self.collections_dir = self.base_dir / "collections"
        self.environments_file = self.base_dir / "environments.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.collections_dir.mkdir(parents=True, exist_ok=True)

    def load_collections(self) -> list[Collection]:
        collections: list[Collection] = []
        order_file = self.collections_dir / "_order.json"
        order: list[str] = []
        if order_file.exists():
            order = json.loads(order_file.read_text(encoding="utf-8"))

        files_by_id: dict[str, Path] = {}
        for path in self.collections_dir.glob("*.json"):
            if path.name == "_order.json":
                continue
            files_by_id[path.stem] = path

        loaded_ids: set[str] = set()
        for cid in order:
            if cid in files_by_id:
                data = json.loads(files_by_id[cid].read_text(encoding="utf-8"))
                collections.append(Collection.from_dict(data))
                loaded_ids.add(cid)
        for cid, path in files_by_id.items():
            if cid not in loaded_ids:
                data = json.loads(path.read_text(encoding="utf-8"))
                collections.append(Collection.from_dict(data))

        return collections

    def save_collection(self, collection: Collection) -> None:
        path = self.collections_dir / f"{collection.id}.json"
        path.write_text(
            json.dumps(collection.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def delete_collection(self, collection_id: str) -> None:
        path = self.collections_dir / f"{collection_id}.json"
        if path.exists():
            path.unlink()

    def save_collection_order(self, collection_ids: list[str]) -> None:
        order_file = self.collections_dir / "_order.json"
        order_file.write_text(
            json.dumps(collection_ids, indent=2), encoding="utf-8"
        )

    def load_environments(self) -> list[Environment]:
        if not self.environments_file.exists():
            return []
        data = json.loads(self.environments_file.read_text(encoding="utf-8"))
        return [Environment.from_dict(e) for e in data]

    def save_environments(self, environments: list[Environment]) -> None:
        self.environments_file.write_text(
            json.dumps(
                [e.to_dict() for e in environments], indent=2, ensure_ascii=False
            ),
            encoding="utf-8",
        )