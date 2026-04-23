from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from angryrest.services import app_logger


_CATEGORY_MAP: dict[str, str] = {
    "angryrest": "APP",
    "angryrest.http": "HTTP",
    "angryrest.scripts": "SCRIPTS",
}


def _category(name: str) -> str:
    return _CATEGORY_MAP.get(name, name.rsplit(".", 1)[-1].upper())


def _level_color(levelno: int) -> QColor | None:
    if levelno >= logging.ERROR:
        return QColor("#f48771")
    if levelno >= logging.WARNING:
        return QColor("#cca700")
    if levelno == logging.DEBUG:
        return QColor("#808080")
    return None


class LogsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Logs")
        self.resize(860, 520)

        # --- Left: record list ---
        self._list = QListWidget()
        self._list.setMinimumWidth(280)
        self._list.currentRowChanged.connect(self._on_row_changed)

        # --- Right: detail view ---
        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._list)
        splitter.addWidget(self._detail)
        splitter.setSizes([290, 570])

        # --- Bottom bar ---
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self._clear_logs)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addWidget(clear_btn)
        bottom.addStretch()
        bottom.addWidget(close_box)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
        layout.addLayout(bottom)

        self._populate_list()

    def _populate_list(self) -> None:
        self._list.clear()
        records = app_logger.get_records()
        for record in records:
            ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            category = _category(record.name)
            first_line = record.getMessage().split("\n")[0]
            label = f"[{ts}] {record.levelname:<8}  {category:<8}  {first_line}"
            item = QListWidgetItem(label)
            color = _level_color(record.levelno)
            if color:
                item.setForeground(color)
            self._list.addItem(item)

        if records:
            self._list.setCurrentRow(len(records) - 1)

    def _on_row_changed(self, row: int) -> None:
        records = app_logger.get_records()
        if 0 <= row < len(records):
            record = records[row]
            ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
            category = _category(record.name)
            header = f"[{ts}]  {record.levelname}  {category}  ({record.name})"
            self._detail.setPlainText(f"{header}\n\n{record.getMessage()}")
        else:
            self._detail.clear()

    def _clear_logs(self) -> None:
        app_logger.clear_records()
        self._list.clear()
        self._detail.clear()

