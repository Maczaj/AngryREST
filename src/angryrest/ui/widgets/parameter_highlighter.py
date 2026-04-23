from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class ParameterHighlighter(QSyntaxHighlighter):
    """Highlights <paramName> patterns in text.

    Parameters present in the active environment are shown in green;
    missing ones are shown in red.
    """

    PARAM_RE = re.compile(r"<([^>]+)>")

    def __init__(self, document, env_getter: Callable[[], dict[str, str]] | None = None):
        super().__init__(document)
        self._env_getter: Callable[[], dict[str, str]] = env_getter or (lambda: {})

    def set_env_getter(self, getter: Callable[[], dict[str, str]]) -> None:
        self._env_getter = getter
        self.rehighlight()

    def get_env(self) -> dict[str, str]:
        return self._env_getter()

    def highlightBlock(self, text: str) -> None:
        env = self.get_env()
        for match in self.PARAM_RE.finditer(text):
            param_name = match.group(1)
            start = match.start()
            length = match.end() - match.start()
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Bold)
            if param_name in env:
                fmt.setForeground(QColor("#4ec9b0"))  # green/teal
                fmt.setBackground(QColor("#1e3a2f"))
            else:
                fmt.setForeground(QColor("#f44747"))  # red
                fmt.setBackground(QColor("#3a1e1e"))
            self.setFormat(start, length, fmt)
