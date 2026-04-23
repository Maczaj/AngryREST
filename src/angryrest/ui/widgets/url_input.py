from __future__ import annotations

import re
from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QPlainTextEdit, QToolTip

from angryrest.ui.widgets.parameter_highlighter import ParameterHighlighter


class UrlInput(QPlainTextEdit):
    """A single-line text input that supports parameter highlighting."""

    return_pressed = Signal()
    text_changed_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(30)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setTabChangesFocus(True)
        font = QFont("Consolas, Courier New, monospace", 10)
        self.setFont(font)
        self.setPlaceholderText("https://api.example.com/<param>/resource")

        self.highlighter = ParameterHighlighter(self.document())
        self.textChanged.connect(self.text_changed_signal.emit)
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)

    def set_env_getter(self, getter: Callable[[], dict[str, str]]) -> None:
        self.highlighter.set_env_getter(getter)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.return_pressed.emit()
            return
        super().keyPressEvent(event)

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
