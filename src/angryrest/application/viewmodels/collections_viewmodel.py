from __future__ import annotations

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, Qt, Signal, Slot

from angryrest.application.services.collection_service import CollectionService
from angryrest.domain.models.collection import Collection


class CollectionsViewModel(QAbstractListModel):
    NameRole = Qt.ItemDataRole.UserRole + 1
    IdRole = Qt.ItemDataRole.UserRole + 2
    RequestCountRole = Qt.ItemDataRole.UserRole + 3

    selected_index_changed = Signal()
    count_changed = Signal()

    def __init__(
        self,
        collection_service: CollectionService,
        parent: QAbstractListModel | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = collection_service
        self._collections: list[Collection] = []
        self._selected_index: int = -1

    @Property(int, notify=count_changed)
    def count(self) -> int:
        return len(self._collections)

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.NameRole: b"name",
            self.IdRole: b"collectionId",
            self.RequestCountRole: b"requestCount",
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._collections)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._collections):
            return None
        collection = self._collections[index.row()]
        if role == self.NameRole:
            return collection.name
        if role == self.IdRole:
            return collection.id
        if role == self.RequestCountRole:
            return len(collection.requests)
        return None

    @property
    def collections(self) -> list[Collection]:
        return list(self._collections)

    @property
    def selected_index(self) -> int:
        return self._selected_index

    def collection_at(self, index: int) -> Collection | None:
        if 0 <= index < len(self._collections):
            return self._collections[index]
        return None

    def load(self) -> None:
        self.set_collections(self._service.load_all())

    @Slot()
    def set_collections(self, collections: list[Collection]) -> None:
        self.beginResetModel()
        self._collections = list(collections)
        self.endResetModel()
        self.count_changed.emit()

    @Slot(int)
    def select_index(self, index: int) -> None:
        if index != self._selected_index:
            self._selected_index = index
            self.selected_index_changed.emit()

    @Slot(str, result=bool)
    def create_collection(self, name: str) -> bool:
        collection = self._service.create(name)
        row = len(self._collections)
        self.beginInsertRows(QModelIndex(), row, row)
        self._collections.append(collection)
        self.endInsertRows()
        self.count_changed.emit()
        return True

    @Slot(int, str)
    def rename_collection(self, row: int, name: str) -> None:
        if 0 <= row < len(self._collections):
            collection = self._collections[row]
            self._service.rename(collection, name)
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.NameRole])

    @Slot(int)
    def delete_collection(self, row: int) -> None:
        if 0 <= row < len(self._collections):
            collection = self._collections[row]
            self._service.delete(collection)
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._collections[row]
            self.endRemoveRows()
            if self._selected_index == row:
                self._selected_index = -1
                self.selected_index_changed.emit()
            elif self._selected_index > row:
                self._selected_index -= 1
            self.count_changed.emit()