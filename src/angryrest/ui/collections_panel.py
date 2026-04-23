from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from angryrest.models.collection import Collection, RequestDef


COLLECTION_ROLE = Qt.UserRole
REQUEST_ROLE = Qt.UserRole + 1
METHOD_ROLE = Qt.UserRole + 2

METHOD_COLORS = {
    "GET": "#4ec9b0",
    "POST": "#569cd6",
    "PUT": "#dcdcaa",
    "DELETE": "#f44747",
    "OPTIONS": "#808080",
    "PATCH": "#2d8e6e",
    "HEAD": "#5a5a5a",
}


class CollectionDelegate(QStyledItemDelegate):
    """Renders method badges for request items and a ⋮ button for hovered collection items."""

    def __init__(self, tree: QTreeWidget, dots_callback, parent=None):
        super().__init__(parent)
        self._tree = tree
        self._dots_callback = dots_callback
        self._hovered_index = QModelIndex()

    def set_hovered_index(self, index: QModelIndex) -> None:
        self._hovered_index = index

    def _dots_rect(self, item_rect: QRect) -> QRect:
        return QRect(item_rect.right() - 21, item_rect.top(), 22, item_rect.height())

    def paint(self, painter, option, index) -> None:
        item = self._tree.itemFromIndex(index)
        is_request = item is not None and item.parent() is not None

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        is_selected = bool(option.state & QStyle.State_Selected)

        if is_request:
            method = item.data(0, METHOD_ROLE) or ""
            name = index.data(Qt.DisplayRole) or ""

            painter.save()
            fm = painter.fontMetrics()
            badge_w = fm.horizontalAdvance("OPTIONS") + 4

            bold_font = painter.font()
            bold_font.setBold(True)
            painter.setFont(bold_font)
            painter.setPen(QColor(METHOD_COLORS.get(method, "#d4d4d4")))
            badge_rect = QRect(
                option.rect.left() + 4, option.rect.top(), badge_w, option.rect.height()
            )
            painter.drawText(badge_rect, Qt.AlignVCenter | Qt.AlignLeft, method)

            regular_font = painter.font()
            regular_font.setBold(False)
            painter.setFont(regular_font)
            name_color = "#ffffff" if is_selected else "#d4d4d4"
            painter.setPen(QColor(name_color))
            name_rect = QRect(
                option.rect.left() + badge_w + 10,
                option.rect.top(),
                option.rect.width() - badge_w - 14,
                option.rect.height(),
            )
            elided = painter.fontMetrics().elidedText(name, Qt.ElideRight, name_rect.width())
            painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

            painter.restore()

        else:
            name = index.data(Qt.DisplayRole) or ""
            is_hovered = index == self._hovered_index

            painter.save()
            bold_font = painter.font()
            bold_font.setBold(True)
            painter.setFont(bold_font)
            name_color = "#ffffff" if is_selected else "#cccccc"
            painter.setPen(QColor(name_color))
            right_margin = 26 if is_hovered else 4
            name_rect = QRect(
                option.rect.left() + 4,
                option.rect.top(),
                option.rect.width() - right_margin - 4,
                option.rect.height(),
            )
            painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, name)

            if is_hovered:
                dots_rect = self._dots_rect(option.rect)
                regular_font = painter.font()
                regular_font.setBold(False)
                painter.setFont(regular_font)
                painter.setPen(QColor("#888888"))
                painter.drawText(dots_rect, Qt.AlignVCenter | Qt.AlignCenter, "⋮")

            painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            item = self._tree.itemFromIndex(index)
            if item is not None and item.parent() is None:
                dots_rect = self._dots_rect(option.rect)
                click_pos = event.position().toPoint()
                if dots_rect.contains(click_pos):
                    global_pos = self._tree.viewport().mapToGlobal(click_pos)
                    self._dots_callback(item, global_pos)
                    return True
        return super().editorEvent(event, model, option, index)


class CollectionsPanel(QWidget):
    request_selected = Signal(object, object)  # (Collection, RequestDef)
    data_changed = Signal()

    def __init__(self, collections: list[Collection], parent: QWidget | None = None):
        super().__init__(parent)
        self.collections = collections

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toolbar
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(4, 4, 4, 0)

        add_collection_btn = QPushButton("+ Collection")
        add_collection_btn.clicked.connect(self._new_collection)
        btn_layout.addWidget(add_collection_btn)

        add_request_btn = QPushButton("+ Request")
        add_request_btn.clicked.connect(self._new_request)
        btn_layout.addWidget(add_request_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.model().rowsMoved.connect(self._on_reorder)
        self.tree.setMouseTracking(True)
        self.tree.viewport().setMouseTracking(True)
        self._delegate = CollectionDelegate(self.tree, self._on_dots_clicked)
        self.tree.setItemDelegate(self._delegate)
        self.tree.entered.connect(self._on_item_entered)
        self.tree.viewport().installEventFilter(self)
        layout.addWidget(self.tree)

        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        self.tree.clear()
        for coll in self.collections:
            coll_item = QTreeWidgetItem([coll.name])
            coll_item.setData(0, COLLECTION_ROLE, coll.id)
            coll_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
            )
            self.tree.addTopLevelItem(coll_item)

            for req in coll.requests:
                req_item = QTreeWidgetItem([req.name])
                req_item.setData(0, COLLECTION_ROLE, coll.id)
                req_item.setData(0, REQUEST_ROLE, req.id)
                req_item.setData(0, METHOD_ROLE, req.method)
                req_item.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
                )
                coll_item.addChild(req_item)

            coll_item.setExpanded(True)

    def refresh_request_label(self, collection: Collection, request: RequestDef) -> None:
        for i in range(self.tree.topLevelItemCount()):
            coll_item = self.tree.topLevelItem(i)
            if coll_item.data(0, COLLECTION_ROLE) == collection.id:
                for j in range(coll_item.childCount()):
                    req_item = coll_item.child(j)
                    if req_item.data(0, REQUEST_ROLE) == request.id:
                        req_item.setText(0, request.name)
                        req_item.setData(0, METHOD_ROLE, request.method)
                        return

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        req_id = item.data(0, REQUEST_ROLE)
        coll_id = item.data(0, COLLECTION_ROLE)
        if req_id and coll_id:
            coll = self._find_collection(coll_id)
            req = self._find_request(coll, req_id) if coll else None
            if coll and req:
                self.request_selected.emit(coll, req)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.tree.viewport() and event.type() == QEvent.Type.Leave:
            self._delegate.set_hovered_index(QModelIndex())
            self.tree.viewport().update()
        return super().eventFilter(obj, event)

    def _on_item_entered(self, index: QModelIndex) -> None:
        self._delegate.set_hovered_index(index)
        self.tree.viewport().update()

    def _on_dots_clicked(self, item: QTreeWidgetItem, global_pos) -> None:
        menu = QMenu(self)
        rename_action = menu.addAction("Rename Collection")
        rename_action.triggered.connect(lambda: self._rename_collection(item))
        add_req_action = menu.addAction("Add Request")
        add_req_action.triggered.connect(lambda: self._new_request_in(item))
        del_action = menu.addAction("Delete Collection")
        del_action.triggered.connect(lambda: self._delete_collection(item))
        menu.exec(global_pos)

    def _on_reorder(self) -> None:
        # Sync model order from the tree
        new_collections_order: list[str] = []
        for i in range(self.tree.topLevelItemCount()):
            coll_item = self.tree.topLevelItem(i)
            coll_id = coll_item.data(0, COLLECTION_ROLE)
            new_collections_order.append(coll_id)

            coll = self._find_collection(coll_id)
            if coll:
                new_request_order: list[str] = []
                for j in range(coll_item.childCount()):
                    req_item = coll_item.child(j)
                    rid = req_item.data(0, REQUEST_ROLE)
                    if rid:
                        new_request_order.append(rid)

                req_map = {r.id: r for r in coll.requests}
                coll.requests = [req_map[rid] for rid in new_request_order if rid in req_map]

        # Reorder collections list
        coll_map = {c.id: c for c in self.collections}
        self.collections[:] = [coll_map[cid] for cid in new_collections_order if cid in coll_map]
        self.data_changed.emit()

    def _show_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            action = menu.addAction("New Collection")
            action.triggered.connect(self._new_collection)
        elif item.data(0, REQUEST_ROLE):
            # Request item
            rename_action = menu.addAction("Rename Request")
            rename_action.triggered.connect(lambda: self._rename_request(item))
            dup_action = menu.addAction("Duplicate Request")
            dup_action.triggered.connect(lambda: self._duplicate_request(item))
            del_action = menu.addAction("Delete Request")
            del_action.triggered.connect(lambda: self._delete_request(item))
        else:
            # Collection item
            rename_action = menu.addAction("Rename Collection")
            rename_action.triggered.connect(lambda: self._rename_collection(item))
            add_req_action = menu.addAction("Add Request")
            add_req_action.triggered.connect(lambda: self._new_request_in(item))
            del_action = menu.addAction("Delete Collection")
            del_action.triggered.connect(lambda: self._delete_collection(item))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _new_collection(self) -> None:
        name, ok = QInputDialog.getText(self, "New Collection", "Collection name:")
        if ok and name.strip():
            coll = Collection(name=name.strip())
            self.collections.append(coll)
            self._rebuild_tree()
            self.data_changed.emit()

    def _new_request(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            if self.collections:
                coll = self.collections[0]
            else:
                return
        else:
            coll_id = item.data(0, COLLECTION_ROLE)
            coll = self._find_collection(coll_id)
            if not coll:
                return

        name, ok = QInputDialog.getText(self, "New Request", "Request name:")
        if ok and name.strip():
            req = RequestDef(name=name.strip())
            coll.requests.append(req)
            self._rebuild_tree()
            self.data_changed.emit()

    def _new_request_in(self, coll_item: QTreeWidgetItem) -> None:
        coll_id = coll_item.data(0, COLLECTION_ROLE)
        coll = self._find_collection(coll_id)
        if not coll:
            return
        name, ok = QInputDialog.getText(self, "New Request", "Request name:")
        if ok and name.strip():
            req = RequestDef(name=name.strip())
            coll.requests.append(req)
            self._rebuild_tree()
            self.data_changed.emit()

    def _rename_collection(self, item: QTreeWidgetItem) -> None:
        coll_id = item.data(0, COLLECTION_ROLE)
        coll = self._find_collection(coll_id)
        if not coll:
            return
        name, ok = QInputDialog.getText(self, "Rename Collection", "Name:", text=coll.name)
        if ok and name.strip():
            coll.name = name.strip()
            item.setText(0, coll.name)
            self.data_changed.emit()

    def _delete_collection(self, item: QTreeWidgetItem) -> None:
        coll_id = item.data(0, COLLECTION_ROLE)
        coll = self._find_collection(coll_id)
        if not coll:
            return
        reply = QMessageBox.question(
            self, "Delete Collection",
            f"Delete collection '{coll.name}' and all its requests?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.collections.remove(coll)
            self._rebuild_tree()
            self.data_changed.emit()

    def _rename_request(self, item: QTreeWidgetItem) -> None:
        coll_id = item.data(0, COLLECTION_ROLE)
        req_id = item.data(0, REQUEST_ROLE)
        coll = self._find_collection(coll_id)
        req = self._find_request(coll, req_id) if coll else None
        if not req:
            return
        name, ok = QInputDialog.getText(self, "Rename Request", "Name:", text=req.name)
        if ok and name.strip():
            req.name = name.strip()
            item.setText(0, req.name)
            self.data_changed.emit()

    def _duplicate_request(self, item: QTreeWidgetItem) -> None:
        coll_id = item.data(0, COLLECTION_ROLE)
        req_id = item.data(0, REQUEST_ROLE)
        coll = self._find_collection(coll_id)
        req = self._find_request(coll, req_id) if coll else None
        if not coll or not req:
            return
        new_req = RequestDef.from_dict(req.to_dict())
        import uuid
        new_req.id = str(uuid.uuid4())
        new_req.name = f"{req.name} (copy)"
        idx = coll.requests.index(req)
        coll.requests.insert(idx + 1, new_req)
        self._rebuild_tree()
        self.data_changed.emit()

    def _delete_request(self, item: QTreeWidgetItem) -> None:
        coll_id = item.data(0, COLLECTION_ROLE)
        req_id = item.data(0, REQUEST_ROLE)
        coll = self._find_collection(coll_id)
        req = self._find_request(coll, req_id) if coll else None
        if not coll or not req:
            return
        reply = QMessageBox.question(
            self, "Delete Request",
            f"Delete request '{req.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            coll.requests.remove(req)
            self._rebuild_tree()
            self.data_changed.emit()

    def _find_collection(self, coll_id: str) -> Collection | None:
        for c in self.collections:
            if c.id == coll_id:
                return c
        return None

    def _find_request(self, coll: Collection, req_id: str) -> RequestDef | None:
        for r in coll.requests:
            if r.id == req_id:
                return r
        return None
