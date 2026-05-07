from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from angryrest.services.http_client import ErrorResult, ResponseData
from angryrest.services.script_engine import ScriptResult


class ResponsePanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Status bar
        self.status_bar = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Consolas", 11, QFont.Bold))
        self.status_bar.addWidget(self.status_label)

        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #888;")
        self.status_bar.addWidget(self.time_label)

        self.size_label = QLabel("")
        self.size_label.setStyleSheet("color: #888;")
        self.status_bar.addWidget(self.size_label)

        self.status_bar.addStretch()
        layout.addLayout(self.status_bar)

        # Tabs: Body | Headers | Script Output
        self.tabs = QTabWidget()

        self.body_view = QPlainTextEdit()
        self.body_view.setReadOnly(True)
        self.body_view.setFont(QFont("Consolas, Courier New, monospace", 10))
        self.tabs.addTab(self.body_view, "Body")

        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header", "Value"])
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.headers_table.verticalHeader().setVisible(False)
        self.headers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabs.addTab(self.headers_table, "Headers")

        self.script_output = QPlainTextEdit()
        self.script_output.setReadOnly(True)
        self.script_output.setFont(QFont("Consolas, Courier New, monospace", 10))
        self.tabs.addTab(self.script_output, "Script Output")

        layout.addWidget(self.tabs)

        # Error display
        self.error_widget = QWidget()
        error_layout = QVBoxLayout(self.error_widget)
        self.error_icon_label = QLabel()
        self.error_icon_label.setAlignment(Qt.AlignCenter)
        self.error_icon_label.setFont(QFont("Consolas", 14, QFont.Bold))
        error_layout.addWidget(self.error_icon_label)
        self.error_message_label = QLabel()
        self.error_message_label.setAlignment(Qt.AlignCenter)
        self.error_message_label.setWordWrap(True)
        self.error_message_label.setStyleSheet("color: #ccc; font-size: 12px;")
        error_layout.addWidget(self.error_message_label)
        layout.addWidget(self.error_widget)

        # Placeholder
        self._placeholder = QLabel("Send a request to see the response")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(self._placeholder)

        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.status_label.setVisible(False)
        self.time_label.setVisible(False)
        self.size_label.setVisible(False)
        self.tabs.setVisible(False)
        self.error_widget.setVisible(False)
        self._placeholder.setVisible(True)

    def clear(self) -> None:
        self._show_placeholder()
        self.body_view.setPlainText("")
        self.headers_table.setRowCount(0)
        self.script_output.setPlainText("")
        self.tabs.setTabText(2, "Script Output")

    def show_loading(self) -> None:
        self._placeholder.setVisible(False)
        self.error_widget.setVisible(False)
        self.tabs.setVisible(False)
        self.status_label.setVisible(True)
        self.status_label.setText("⏳ Sending...")
        self.status_label.setStyleSheet("color: #dcdcaa;")
        self.time_label.setVisible(False)
        self.size_label.setVisible(False)

    def show_response(self, response: ResponseData) -> None:
        self._placeholder.setVisible(False)
        self.error_widget.setVisible(False)
        self.tabs.setVisible(True)
        self.status_label.setVisible(True)
        self.time_label.setVisible(True)
        self.size_label.setVisible(True)

        # Status code coloring
        code = response.status_code
        if 200 <= code < 300:
            color = "#4ec9b0"  # green
        elif 300 <= code < 400:
            color = "#569cd6"  # blue
        elif 400 <= code < 500:
            color = "#dcdcaa"  # yellow
        else:
            color = "#f44747"  # red

        self.status_label.setText(f"{code} {response.reason_phrase}")
        self.status_label.setStyleSheet(f"color: {color};")
        self.time_label.setText(f"{response.elapsed_ms} ms")

        size = response.size_bytes
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        self.size_label.setText(size_str)

        # Body - try to pretty-print JSON
        content_type = response.headers.get("content-type", "")
        body_text = response.text()
        if "json" in content_type or "javascript" in content_type:
            try:
                parsed = json.loads(body_text)
                body_text = json.dumps(parsed, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                pass
        self.body_view.setPlainText(body_text)

        # Headers
        self.headers_table.setRowCount(0)
        for key, value in response.headers.items():
            row = self.headers_table.rowCount()
            self.headers_table.insertRow(row)
            self.headers_table.setItem(row, 0, QTableWidgetItem(key))
            self.headers_table.setItem(row, 1, QTableWidgetItem(value))

        self.tabs.setCurrentIndex(0)

    def show_error(self, error: ErrorResult) -> None:
        self._placeholder.setVisible(False)
        self.tabs.setVisible(False)
        self.error_widget.setVisible(True)
        self.status_label.setVisible(True)
        self.time_label.setVisible(False)
        self.size_label.setVisible(False)

        type_labels = {
            "connection": "🔌 CONNECTION ERROR",
            "timeout": "⏱ TIMEOUT",
            "dns": "🌐 DNS ERROR",
            "ssl": "🔒 SSL ERROR",
            "other": "⚠ ERROR",
        }
        label = type_labels.get(error.error_type, "⚠ ERROR")
        self.status_label.setText(label)
        self.status_label.setStyleSheet("color: #f44747;")
        self.error_icon_label.setText(label)
        self.error_icon_label.setStyleSheet("color: #f44747;")
        self.error_message_label.setText(error.message)

    def show_script_output(
        self,
        pre_result: ScriptResult | None,
        post_result: ScriptResult | None,
    ) -> None:
        parts: list[str] = []

        if pre_result:
            if pre_result.output:
                parts.append("=== Pre-Script Output ===")
                parts.append(pre_result.output)
            if pre_result.error:
                parts.append("=== Pre-Script Error ===")
                parts.append(pre_result.error)

        if post_result:
            if post_result.output:
                parts.append("=== Post-Script Output ===")
                parts.append(post_result.output)
            if post_result.error:
                parts.append("=== Post-Script Error ===")
                parts.append(post_result.error)
            if post_result.assertions:
                parts.append("=== Assertions ===")
                for a in post_result.assertions:
                    status = "✅ PASS" if a.passed else "❌ FAIL"
                    parts.append(f"  {status}: {a.message}")

        self.script_output.setPlainText("\n".join(parts))
        if parts:
            self.tabs.setTabText(2, f"Script Output ({len(parts)})")
        else:
            self.tabs.setTabText(2, "Script Output")
