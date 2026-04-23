from __future__ import annotations

from PySide6.QtCore import QPoint, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QLabel, QMenu, QPushButton, QWidgetAction, QWidget


class WaylandComboBox(QComboBox):
    """QComboBox subclass that works around Wayland popup dismiss bug.

    On Qt 6 with the Wayland platform plugin, selecting an item from the
    popup does not automatically close it. This subclass forces the popup
    closed after an item is activated.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.activated.connect(self._force_close_popup)

    def _force_close_popup(self) -> None:
        # Defer to next event-loop tick so the selection completes first
        QTimer.singleShot(0, self.hidePopup)


class MethodButton(QPushButton):
    """QPushButton-based HTTP method selector with built-in color coding.

    Drop-in replacement for WaylandComboBox as the method selector.
    QPushButton.setStyleSheet reliably applies color on all platforms.
    """

    METHOD_COLORS = {
        "GET": "#4ec9b0",
        "POST": "#569cd6",
        "PUT": "#dcdcaa",
        "DELETE": "#f44747",
        "OPTIONS": "#808080",
        "PATCH": "#2d8e6e",
        "HEAD": "#5a5a5a",
    }

    currentIndexChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[str] = []
        self._current_index: int = 0
        self.clicked.connect(self._show_menu)

    # ── QComboBox-compatible API ────────────────────────────────────────

    def addItems(self, items: list[str]) -> None:
        self._items = list(items)
        if self._items:
            self._current_index = 0
            self._refresh()

    def currentText(self) -> str:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return ""

    def currentIndex(self) -> int:
        return self._current_index

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._current_index = index
            self._refresh()

    def itemText(self, index: int) -> str:
        if 0 <= index < len(self._items):
            return self._items[index]
        return ""

    def setItemText(self, index: int, text: str) -> None:
        if 0 <= index < len(self._items):
            self._items[index] = text
            if index == self._current_index:
                self._refresh()

    def setInsertPolicy(self, policy: object) -> None:
        pass  # no-op for API compatibility

    # ── Internal ────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        text = self.currentText()
        self.setText(text)
        color = self.METHOD_COLORS.get(text, "#d4d4d4")
        self.setStyleSheet(f"QPushButton {{ color: {color}; font-weight: bold; }}")

    def _show_menu(self) -> None:
        menu = QMenu(self)
        for i, method in enumerate(self._items):
            label = QLabel(method)
            label.setContentsMargins(8, 4, 8, 4)
            color = self.METHOD_COLORS.get(method, "#d4d4d4")
            label.setStyleSheet(f"color: {color}; font-weight: bold; background: transparent;")
            wa = QWidgetAction(menu)
            wa.setDefaultWidget(label)
            wa.triggered.connect(lambda checked=False, idx=i: self._on_select(idx))
            menu.addAction(wa)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def _on_select(self, index: int) -> None:
        old = self._current_index
        self.setCurrentIndex(index)
        if old != index:
            self.currentIndexChanged.emit(index)

