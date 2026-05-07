from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QCompleter, QPlainTextEdit

SCRIPT_BUILTINS = [
    "env",
    "request",
    "response",
    "assert_status",
    "assert_equals",
    "assert_true",
    "assert_contains",
    "json",
    "re",
    "base64",
    "hashlib",
    "uuid",
    "print",
    "True",
    "False",
    "None",
    "if",
    "else",
    "elif",
    "for",
    "while",
    "in",
    "not",
    "and",
    "or",
    "def",
    "return",
    "import",
    "from",
    "try",
    "except",
    "finally",
    "raise",
    "with",
    "as",
    "lambda",
]


class PythonHighlighter(QSyntaxHighlighter):
    KEYWORDS = {
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else",
        "except", "finally", "for", "from", "global", "if", "import",
        "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
        "return", "try", "while", "with", "yield",
    }

    def __init__(self, document):
        super().__init__(document)

        self._keyword_fmt = QTextCharFormat()
        self._keyword_fmt.setForeground(QColor("#569cd6"))
        self._keyword_fmt.setFontWeight(QFont.Bold)

        self._string_fmt = QTextCharFormat()
        self._string_fmt.setForeground(QColor("#ce9178"))

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#6a9955"))

        self._builtin_fmt = QTextCharFormat()
        self._builtin_fmt.setForeground(QColor("#dcdcaa"))

        self._number_fmt = QTextCharFormat()
        self._number_fmt.setForeground(QColor("#b5cea8"))

    def highlightBlock(self, text: str) -> None:
        # Keywords
        for match in re.finditer(r"\b(" + "|".join(self.KEYWORDS) + r")\b", text):
            self.setFormat(match.start(), match.end() - match.start(), self._keyword_fmt)

        # Script builtins (env, response, assert_*)
        api_names = [
            "env", "request", "response", "assert_status", "assert_equals",
            "assert_true", "assert_contains",
        ]
        for match in re.finditer(r"\b(" + "|".join(api_names) + r")\b", text):
            self.setFormat(match.start(), match.end() - match.start(), self._builtin_fmt)

        # Numbers
        for match in re.finditer(r"\b\d+(\.\d+)?\b", text):
            self.setFormat(match.start(), match.end() - match.start(), self._number_fmt)

        # Strings (single and double quoted)
        for match in re.finditer(r'(\".*?\"|\'.*?\')', text):
            self.setFormat(match.start(), match.end() - match.start(), self._string_fmt)

        # Comments
        for match in re.finditer(r"#.*$", text):
            self.setFormat(match.start(), match.end() - match.start(), self._comment_fmt)


class ScriptEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas, Courier New, monospace", 10)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setPlaceholderText("# Write your script here\n# Available: env, request/response, assert_*")

        self._highlighter = PythonHighlighter(self.document())

        self._completer = QCompleter(SCRIPT_BUILTINS, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.activated.connect(self._insert_completion)

    def _insert_completion(self, completion: str) -> None:
        tc = self.textCursor()
        extra = len(completion) - len(self._completer.completionPrefix())
        tc.movePosition(tc.Left)
        tc.movePosition(tc.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def keyPressEvent(self, event) -> None:
        ctrl_space = (
            event.key() == Qt.Key.Key_Space
            and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        )

        popup = self._completer.popup()
        if popup is not None and popup.isVisible():
            if event.key() == Qt.Key.Key_Escape:
                popup.hide()
                return
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab):
                event.ignore()
                return

        if not ctrl_space:
            super().keyPressEvent(event)

        # Trigger completion
        tc = self.textCursor()
        tc.select(tc.SelectionType.WordUnderCursor)
        prefix = tc.selectedText()
        if ctrl_space or len(prefix) >= 2:
            self._completer.setCompletionPrefix(prefix)
            # Re-fetch popup — it may be created lazily on first setCompletionPrefix call
            popup = self._completer.popup()
            if popup is None:
                return
            cr = self.cursorRect()
            cr.setWidth(
                popup.sizeHintForColumn(0)
                + popup.verticalScrollBar().sizeHint().width()
            )
            self._completer.complete(cr)
        else:
            popup = self._completer.popup()
            if popup is not None:
                popup.hide()
