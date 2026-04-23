from __future__ import annotations

import re
from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from angryrest.ui.widgets.parameter_highlighter import ParameterHighlighter


class ParamValueEdit(QPlainTextEdit):
    """Single-line value editor with <param> color highlighting and tooltip."""

    text_changed_signal = Signal()

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMaximumHeight(28)
        self.setMinimumHeight(28)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self.highlighter = ParameterHighlighter(self.document())
        if text:
            self.setPlainText(text)
        self.textChanged.connect(self.text_changed_signal.emit)
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)

    def set_env_getter(self, getter: Callable[[], dict[str, str]]) -> None:
        self.highlighter.set_env_getter(getter)

    def get_text(self) -> str:
        return self.toPlainText().replace("\n", "")

    def set_text(self, text: str) -> None:
        self.setPlainText(text)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.viewport() and event.type() == QEvent.Type.MouseMove:
            mouse_event = cast(QMouseEvent, event)
            cursor = self.cursorForPosition(mouse_event.pos())
            pos = cursor.position()
            text = self.toPlainText()
            env = self.highlighter.get_env()
            for match in re.finditer(r"<([^>]+)>", text):
                if match.start() <= pos <= match.end():
                    param_name = match.group(1)
                    val = env.get(param_name)
                    tip = f"{param_name} = {val}" if val is not None else f"{param_name} (not defined)"
                    QToolTip.showText(mouse_event.globalPosition().toPoint(), tip, self)
                    return False
            QToolTip.hideText()
            return False
        return super().eventFilter(obj, event)


class KeyValueEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._env_getter: Callable[[], dict[str, str]] | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "Key", "Value", ""])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().resizeSection(0, 30)
        self.table.horizontalHeader().resizeSection(3, 30)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.table)

        add_btn = QPushButton("+ Add")
        add_btn.setFixedWidth(80)
        add_btn.clicked.connect(lambda: self._add_row())
        layout.addWidget(add_btn)

    def _add_row(
        self, enabled: bool = True, key: str = "", value: str = ""
    ) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)

        cb = QCheckBox()
        cb.setChecked(enabled)
        cb.stateChanged.connect(lambda: self.changed.emit())
        self.table.setCellWidget(row, 0, cb)

        key_edit = QLineEdit(key)
        key_edit.setPlaceholderText("Key")
        key_edit.textChanged.connect(lambda: self.changed.emit())
        key_edit.installEventFilter(self)
        self.table.setCellWidget(row, 1, key_edit)

        val_edit = ParamValueEdit(value)
        val_edit.setPlaceholderText("Value")
        val_edit.text_changed_signal.connect(lambda: self.changed.emit())
        val_edit.installEventFilter(self)
        if self._env_getter is not None:
            val_edit.set_env_getter(self._env_getter)
        self.table.setCellWidget(row, 2, val_edit)

        del_btn = QPushButton("×")
        del_btn.setFixedWidth(28)
        del_btn.clicked.connect(lambda checked=False, r=row: self._remove_row(r))
        self.table.setCellWidget(row, 3, del_btn)

        return row

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            if key_event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                forward = key_event.key() == Qt.Key.Key_Tab
                self._navigate_tab(cast(QWidget, obj), forward)
                return True
        return super().eventFilter(obj, event)

    def _navigate_tab(self, current: QWidget, forward: bool) -> None:
        inputs: list[QWidget] = []
        for row in range(self.table.rowCount()):
            ke = self.table.cellWidget(row, 1)
            ve = self.table.cellWidget(row, 2)
            if ke:
                inputs.append(ke)
            if ve:
                inputs.append(ve)
        if not inputs:
            return
        # current may be the viewport of a QPlainTextEdit
        widget = current if current in inputs else cast(QWidget, current.parent())
        if widget not in inputs:
            return
        idx = inputs.index(widget)
        target = inputs[(idx + 1 if forward else idx - 1) % len(inputs)]
        target.setFocus()

    def _remove_row(self, row: int) -> None:
        # Defer the actual removal so Qt finishes dispatching the button's clicked
        # signal before the button's C++ object is destroyed (delete-sender-in-slot
        # is undefined behaviour in Qt and causes random segfaults in PySide6).
        QTimer.singleShot(0, lambda: self._execute_remove_row(row))

    def _execute_remove_row(self, row: int) -> None:
        self.table.removeRow(row)
        # Re-wire delete buttons with correct row indices
        for r in range(self.table.rowCount()):
            del_btn = QPushButton("×")
            del_btn.setFixedWidth(28)
            del_btn.clicked.connect(lambda checked=False, r=r: self._remove_row(r))
            self.table.setCellWidget(r, 3, del_btn)
        self.changed.emit()

    def set_env_getter(self, getter: Callable[[], dict[str, str]]) -> None:
        self._env_getter = getter
        for row in range(self.table.rowCount()):
            val_edit = self.table.cellWidget(row, 2)
            if isinstance(val_edit, ParamValueEdit):
                val_edit.set_env_getter(getter)

    def get_items(self) -> list[tuple[bool, str, str]]:
        items: list[tuple[bool, str, str]] = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            key_edit = self.table.cellWidget(row, 1)
            val_edit = self.table.cellWidget(row, 2)
            if isinstance(cb, QCheckBox) and isinstance(key_edit, QLineEdit) and isinstance(val_edit, ParamValueEdit):
                items.append((cb.isChecked(), key_edit.text(), val_edit.get_text()))
        return items

    def set_items(self, items: list[tuple[bool, str, str]]) -> None:
        self.table.setRowCount(0)
        for enabled, key, value in items:
            self._add_row(enabled, key, value)

    def get_enabled_dict(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for enabled, key, value in self.get_items():
            if enabled and key:
                result[key] = value
        return result
