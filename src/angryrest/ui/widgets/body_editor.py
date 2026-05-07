from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QEvent, QObject, Qt, QStringListModel, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QCompleter,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from angryrest.services import app_logger as _app_logger
from angryrest.services.graphql_schema import (
    AUTH_HEADER_NAMES,
    SchemaFetcher,
    build_schema_tree,
    extract_completions as extract_graphql_completions,
    get_cached_schema as get_cached_graphql_schema,
    get_completions_at_cursor,
    host_from_url,
)
from angryrest.services.http_client import substitute_params
from angryrest.services.openapi_schema import (
    OpenAPIFetcher,
    extract_completions as extract_openapi_completions,
    get_cached_schema as get_cached_openapi_schema,
)

_log = _app_logger.get_logger("schema.ui")
from angryrest.ui.widgets.key_value_editor import KeyValueEditor
from angryrest.ui.widgets.parameter_highlighter import ParameterHighlighter
from angryrest.ui.widgets.wayland_combo_box import WaylandComboBox


class GraphQLQueryEditor(QPlainTextEdit):
    """QPlainTextEdit with context-aware autocompletion powered by a QCompleter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._schema_tree: dict[str, Any] | None = None
        self._static_completions: list[str] = []

        self._completer = QCompleter(self)
        self._model = QStringListModel(self._completer)
        self._completer.setModel(self._model)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.activated.connect(self._insert_completion)

    def set_completions(self, words: list[str]) -> None:
        """Set a static completion list (used when no schema tree is available)."""
        self._static_completions = words
        self._model.setStringList(words)

    def set_schema_tree(self, schema_tree: dict[str, Any]) -> None:
        """Set the GraphQL schema tree for context-aware completions."""
        self._schema_tree = schema_tree

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _completion_prefix(self) -> str:
        """Return the identifier fragment directly before the cursor."""
        cursor = self.textCursor()
        text_before = cursor.block().text()[: cursor.positionInBlock()]
        match = re.search(r"[\w]+$", text_before)
        return match.group(0) if match else ""

    def _insert_completion(self, completion: str) -> None:
        prefix_len = len(self._completer.completionPrefix())
        cursor = self.textCursor()
        # Select the already-typed prefix chars so insertText replaces them cleanly
        if prefix_len > 0:
            cursor.movePosition(
                QTextCursor.MoveOperation.PreviousCharacter,
                QTextCursor.MoveMode.KeepAnchor,
                prefix_len,
            )
        cursor.insertText(completion)
        self.setTextCursor(cursor)

    def _show_completion_popup(self) -> None:
        """Compute context-aware completions and show the popup."""
        if self._schema_tree is not None:
            text = self.toPlainText()
            cursor_pos = self.textCursor().position()
            words = get_completions_at_cursor(self._schema_tree, text, cursor_pos)
        else:
            words = self._static_completions

        # Always rebuild the model so Qt sees a fresh state (fixes stale-popup bug)
        self._model.setStringList(words)

        prefix = self._completion_prefix()
        self._completer.setCompletionPrefix(prefix)

        popup = self._completer.popup()
        if popup is None:
            return

        if self._completer.completionCount() == 0:
            popup.hide()
            return

        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.setWidth(
            popup.sizeHintForColumn(0)
            + popup.verticalScrollBar().sizeHint().width()
        )
        self._completer.complete(rect)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        ctrl_space = (
            event.key() == Qt.Key.Key_Space
            and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        )

        popup = self._completer.popup()
        if popup is not None and popup.isVisible():
            if event.key() == Qt.Key.Key_Escape:
                popup.hide()
                return
            if event.key() in (
                Qt.Key.Key_Enter,
                Qt.Key.Key_Return,
                Qt.Key.Key_Tab,
                Qt.Key.Key_Backtab,
            ):
                event.ignore()
                return

        if ctrl_space:
            self._show_completion_popup()
            return

        super().keyPressEvent(event)

        # Hide popup on navigation or modifier combos
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier or event.key() in (
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        ):
            if popup is not None:
                popup.hide()
            return

        # Auto-trigger after typing 2+ identifier characters
        prefix = self._completion_prefix()
        if len(prefix) >= 2:
            self._show_completion_popup()
        else:
            if popup is not None:
                popup.hide()


class JsonBodyEditor(GraphQLQueryEditor):
    """JSON body editor with QCompleter-based property name autocompletion."""


class FileFieldsEditor(QWidget):
    """Table editor for multipart file fields: field name + file path + browse."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "Field Name", "File Path", ""])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().resizeSection(0, 30)
        self.table.horizontalHeader().resizeSection(1, 140)
        self.table.horizontalHeader().resizeSection(3, 36)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.table)

        add_btn = QPushButton("+ Add File")
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(lambda: self._add_row())
        layout.addWidget(add_btn)

    def _add_row(
        self, enabled: bool = True, field_name: str = "", file_path: str = ""
    ) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 28)

        cb = QCheckBox()
        cb.setChecked(enabled)
        cb.stateChanged.connect(self.changed.emit)
        cb_widget = QWidget()
        cb_layout = QHBoxLayout(cb_widget)
        cb_layout.addWidget(cb)
        cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, 0, cb_widget)

        name_edit = QLineEdit(field_name)
        name_edit.setPlaceholderText("field")
        name_edit.textChanged.connect(self.changed.emit)
        self.table.setCellWidget(row, 1, name_edit)

        path_edit = QLineEdit(file_path)
        path_edit.setReadOnly(True)
        path_edit.setPlaceholderText("(no file selected)")
        self.table.setCellWidget(row, 2, path_edit)

        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(36)
        browse_btn.clicked.connect(lambda: self._browse(row))
        self.table.setCellWidget(row, 3, browse_btn)

        self.changed.emit()
        return row

    def _browse(self, row: int) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if not path:
            return
        path_edit = self.table.cellWidget(row, 2)
        if isinstance(path_edit, QLineEdit):
            path_edit.setText(path)
            self.changed.emit()

    def _delete_row(self, row: int) -> None:
        self.table.removeRow(row)
        self.changed.emit()

    def get_items(self) -> list[tuple[bool, str, str]]:
        """Return [(enabled, field_name, file_path), ...]."""
        result: list[tuple[bool, str, str]] = []
        for row in range(self.table.rowCount()):
            cb_widget = self.table.cellWidget(row, 0)
            name_edit = self.table.cellWidget(row, 1)
            path_edit = self.table.cellWidget(row, 2)
            if not (isinstance(name_edit, QLineEdit) and isinstance(path_edit, QLineEdit)):
                continue
            enabled = False
            if isinstance(cb_widget, QWidget):
                cb = cb_widget.findChild(QCheckBox)
                if isinstance(cb, QCheckBox):
                    enabled = cb.isChecked()
            result.append((enabled, name_edit.text(), path_edit.text()))
        return result

    def set_items(self, items: list[tuple[bool, str, str]]) -> None:
        self.table.setRowCount(0)
        for enabled, name, path in items:
            self._add_row(enabled, name, path)


class BodyEditor(QWidget):
    changed = Signal()

    BODY_TYPES = ["None", "Form", "JSON", "GraphQL", "Multipart"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._env_getter: Callable[[], dict[str, str]] = lambda: {}
        self._url_getter: Callable[[], str] = lambda: ""
        self._headers_getter: Callable[[], list[tuple[bool, str, str]]] = lambda: []
        self._schema_fetcher: SchemaFetcher | None = None
        self._openapi_fetcher: OpenAPIFetcher | None = None
        self._fetch_btn_reset_timer = QTimer(self)
        self._fetch_btn_reset_timer.setSingleShot(True)
        self._fetch_btn_reset_timer.timeout.connect(self._reset_fetch_btn_text)
        self._fetch_json_btn_reset_timer = QTimer(self)
        self._fetch_json_btn_reset_timer.setSingleShot(True)
        self._fetch_json_btn_reset_timer.timeout.connect(self._reset_fetch_json_schema_btn_text)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.type_combo = WaylandComboBox()
        self.type_combo.addItems(self.BODY_TYPES)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo)

        self.stack = QStackedWidget()

        # Page 0: None
        none_label = QLabel("This request has no body")
        none_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        none_label.setStyleSheet("color: #666;")
        self.stack.addWidget(none_label)

        # Page 1: Form
        self.form_editor = KeyValueEditor()
        self.form_editor.changed.connect(self.changed.emit)
        self.stack.addWidget(self.form_editor)

        # Page 2: JSON
        json_widget = QWidget()
        json_layout = QVBoxLayout(json_widget)
        json_layout.setContentsMargins(0, 0, 0, 0)
        json_header = QHBoxLayout()
        json_header.addStretch()
        self._fetch_json_schema_btn = QPushButton("Fetch Schema")
        self._fetch_json_schema_btn.clicked.connect(lambda: self._trigger_openapi_fetch(silent=False))
        json_header.addWidget(self._fetch_json_schema_btn)
        self._format_json_btn = QPushButton("Format")
        self._format_json_btn.setFixedWidth(70)
        self._format_json_btn.clicked.connect(self._format_json)
        json_header.addWidget(self._format_json_btn)
        json_layout.addLayout(json_header)
        self.json_editor = JsonBodyEditor()
        self.json_editor.setPlaceholderText('{\n  "key": "value"\n}')
        self.json_editor.textChanged.connect(self.changed.emit)
        json_layout.addWidget(self.json_editor)
        self.stack.addWidget(json_widget)

        # Page 3: GraphQL
        graphql_widget = QWidget()
        gl = QVBoxLayout(graphql_widget)
        gl.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Vertical)
        query_container = QWidget()
        qc_layout = QVBoxLayout(query_container)
        qc_layout.setContentsMargins(0, 0, 0, 0)
        query_header = QHBoxLayout()
        query_header.addWidget(QLabel("Query"))
        query_header.addStretch()
        self._fetch_schema_btn = QPushButton("Fetch Schema")
        self._fetch_schema_btn.clicked.connect(lambda: self._trigger_schema_fetch(silent=False))
        query_header.addWidget(self._fetch_schema_btn)
        self._format_btn = QPushButton("Format")
        self._format_btn.setFixedWidth(70)
        self._format_btn.clicked.connect(self._format_graphql)
        query_header.addWidget(self._format_btn)
        qc_layout.addLayout(query_header)
        self.graphql_query = GraphQLQueryEditor()
        self.graphql_query.setPlaceholderText("query {\n  ...\n}")
        self.graphql_query.textChanged.connect(self.changed.emit)
        qc_layout.addWidget(self.graphql_query)
        splitter.addWidget(query_container)

        vars_container = QWidget()
        vc_layout = QVBoxLayout(vars_container)
        vc_layout.setContentsMargins(0, 0, 0, 0)
        vc_layout.addWidget(QLabel("Variables (JSON)"))
        self.graphql_vars = QPlainTextEdit()
        self.graphql_vars.setPlaceholderText("{}")
        self.graphql_vars.setMaximumHeight(120)
        self.graphql_vars.textChanged.connect(self.changed.emit)
        vc_layout.addWidget(self.graphql_vars)
        splitter.addWidget(vars_container)

        gl.addWidget(splitter)
        self.stack.addWidget(graphql_widget)

        # Page 4: Multipart
        multipart_widget = QWidget()
        mp_layout = QVBoxLayout(multipart_widget)
        mp_layout.setContentsMargins(0, 0, 0, 0)
        mp_splitter = QSplitter(Qt.Orientation.Vertical)

        text_container = QWidget()
        tc_layout = QVBoxLayout(text_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.addWidget(QLabel("Text Fields"))
        self.multipart_text_editor = KeyValueEditor()
        self.multipart_text_editor.changed.connect(self.changed.emit)
        tc_layout.addWidget(self.multipart_text_editor)
        mp_splitter.addWidget(text_container)

        file_container = QWidget()
        fc_layout = QVBoxLayout(file_container)
        fc_layout.setContentsMargins(0, 0, 0, 0)
        fc_layout.addWidget(QLabel("File Fields"))
        self.multipart_file_editor = FileFieldsEditor()
        self.multipart_file_editor.changed.connect(self.changed.emit)
        fc_layout.addWidget(self.multipart_file_editor)
        mp_splitter.addWidget(file_container)

        mp_layout.addWidget(mp_splitter)
        self.stack.addWidget(multipart_widget)

        # Parameter highlighting for text body editors
        self._json_highlighter = ParameterHighlighter(self.json_editor.document(), self._env_getter)
        self._graphql_highlighter = ParameterHighlighter(self.graphql_query.document(), self._env_getter)

        for editor in (self.json_editor, self.graphql_query):
            editor.viewport().setMouseTracking(True)
            editor.viewport().installEventFilter(self)

        layout.addWidget(self.stack)

    def set_env_getter(self, getter: Callable[[], dict[str, str]]) -> None:
        self._env_getter = getter
        self._json_highlighter.set_env_getter(getter)
        self._graphql_highlighter.set_env_getter(getter)

    def set_url_getter(self, getter: Callable[[], str]) -> None:
        self._url_getter = getter

    def set_headers_getter(self, getter: Callable[[], list[tuple[bool, str, str]]]) -> None:
        self._headers_getter = getter

    def rehighlight_body(self) -> None:
        self._json_highlighter.rehighlight()
        self._graphql_highlighter.rehighlight()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseMove:
            if obj is self.json_editor.viewport():
                editor = self.json_editor
            elif obj is self.graphql_query.viewport():
                editor = self.graphql_query
            else:
                return super().eventFilter(obj, event)
            mouse_event = cast(QMouseEvent, event)
            cursor = editor.cursorForPosition(mouse_event.pos())
            pos = cursor.position()
            text = editor.toPlainText()
            env = self._env_getter()
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

    def _format_json(self) -> None:
        import json

        raw = self.json_editor.toPlainText().strip()
        if not raw:
            return
        try:
            formatted = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "JSON Syntax Error", str(exc))
            return
        self.json_editor.setPlainText(formatted)

    def _format_graphql(self) -> None:
        from graphql import parse, print_ast
        from graphql.error import GraphQLError

        raw = self.graphql_query.toPlainText().strip()
        if not raw:
            return
        try:
            formatted = print_ast(parse(raw))
        except GraphQLError as exc:
            QMessageBox.warning(self, "GraphQL Syntax Error", str(exc))
            return
        self.graphql_query.setPlainText(formatted)

    def _trigger_schema_fetch(self, *, silent: bool) -> None:
        """Start a background introspection fetch. If *silent*, errors are only logged."""
        raw_url = self._url_getter()
        if not raw_url:
            if not silent:
                QMessageBox.warning(self, "Fetch Schema", "No URL is set for this request.")
            return
        url = substitute_params(raw_url, self._env_getter())
        if re.search(r"<[^>]+>", url):
            if not silent:
                QMessageBox.warning(
                    self,
                    "Fetch Schema",
                    "The URL still contains unresolved parameters.\n"
                    "Please select an environment first.",
                )
            return
        if self._schema_fetcher is not None and self._schema_fetcher.isRunning():
            return
        # Collect auth headers from the request that match well-known names
        env = self._env_getter()
        extra_headers: dict[str, str] = {}
        for enabled, key, value in self._headers_getter():
            if enabled and key.lower() in AUTH_HEADER_NAMES:
                extra_headers[key] = substitute_params(value, env)
        self._fetch_schema_btn.setEnabled(False)
        self._fetch_schema_btn.setText("Fetching…")
        fetcher = SchemaFetcher(url, extra_headers=extra_headers)
        fetcher.schema_ready.connect(self._on_schema_ready)
        if not silent:
            fetcher.fetch_error.connect(self._on_schema_error_dialog)
        fetcher.fetch_error.connect(self._on_schema_error_done)
        fetcher.finished.connect(self._on_fetcher_finished)
        fetcher.finished.connect(fetcher.deleteLater)
        self._schema_fetcher = fetcher
        fetcher.start()

    def _on_fetcher_finished(self) -> None:
        self._schema_fetcher = None

    def _reset_fetch_btn_text(self) -> None:
        self._fetch_schema_btn.setText("Fetch Schema")

    def _on_schema_ready(self, host: str, schema: dict[str, Any]) -> None:
        schema_tree = build_schema_tree(schema)
        self.graphql_query.set_schema_tree(schema_tree)
        completions = extract_graphql_completions(schema)
        _log.info(
            "Schema loaded for %s — %d completion(s) available",
            host,
            len(completions),
        )
        self._fetch_schema_btn.setEnabled(True)
        self._fetch_schema_btn.setText("✓ Schema ready")
        self._fetch_btn_reset_timer.start(3000)

    def _on_schema_error_done(self, _host: str, _msg: str) -> None:
        self._fetch_schema_btn.setEnabled(True)
        self._fetch_schema_btn.setText("✗ Failed")
        self._fetch_btn_reset_timer.start(3000)

    def _on_schema_error_dialog(self, _host: str, msg: str) -> None:
        QMessageBox.warning(self, "Schema Fetch Error", f"Failed to fetch schema:\n{msg}")

    def _auto_fetch_schema(self) -> None:
        """Load from cache if available, otherwise trigger a silent background fetch.

        Skipped when the URL still contains unresolved ``<param>`` placeholders
        (i.e. no environment has been selected yet).
        """
        raw_url = self._url_getter()
        if not raw_url:
            return
        url = substitute_params(raw_url, self._env_getter())
        if re.search(r"<[^>]+>", url):
            # URL has unresolved env params — wait for the user to pick an env
            return
        host = host_from_url(url)
        cached = get_cached_graphql_schema(host)
        if cached is not None:
            self.graphql_query.set_schema_tree(build_schema_tree(cached))
            return
        self._trigger_schema_fetch(silent=True)

    def _trigger_openapi_fetch(self, *, silent: bool) -> None:
        """Start a background OpenAPI/Swagger probe. If *silent*, errors are only logged."""
        raw_url = self._url_getter()
        if not raw_url:
            if not silent:
                QMessageBox.warning(self, "Fetch Schema", "No URL is set for this request.")
            return
        url = substitute_params(raw_url, self._env_getter())
        if re.search(r"<[^>]+>", url):
            if not silent:
                QMessageBox.warning(
                    self,
                    "Fetch Schema",
                    "The URL still contains unresolved parameters.\n"
                    "Please select an environment first.",
                )
            return
        if self._openapi_fetcher is not None and self._openapi_fetcher.isRunning():
            return
        env = self._env_getter()
        extra_headers: dict[str, str] = {}
        for enabled, key, value in self._headers_getter():
            if enabled and key.lower() in AUTH_HEADER_NAMES:
                extra_headers[key] = substitute_params(value, env)
        self._fetch_json_schema_btn.setEnabled(False)
        self._fetch_json_schema_btn.setText("Fetching…")
        fetcher = OpenAPIFetcher(url, extra_headers=extra_headers)
        fetcher.schema_ready.connect(self._on_openapi_ready)
        if not silent:
            fetcher.fetch_error.connect(self._on_openapi_error_dialog)
        fetcher.fetch_error.connect(self._on_openapi_error_done)
        fetcher.finished.connect(self._on_openapi_fetcher_finished)
        fetcher.finished.connect(fetcher.deleteLater)
        self._openapi_fetcher = fetcher
        fetcher.start()

    def _on_openapi_fetcher_finished(self) -> None:
        self._openapi_fetcher = None

    def _reset_fetch_json_schema_btn_text(self) -> None:
        self._fetch_json_schema_btn.setText("Fetch Schema")

    def _on_openapi_ready(self, host: str, spec: dict[str, Any]) -> None:
        completions = extract_openapi_completions(spec)
        self.json_editor.set_completions(completions)
        _log.info(
            "OpenAPI schema loaded for %s — %d completion(s) available",
            host,
            len(completions),
        )
        self._fetch_json_schema_btn.setEnabled(True)
        self._fetch_json_schema_btn.setText("✓ Schema ready")
        self._fetch_json_btn_reset_timer.start(3000)

    def _on_openapi_error_done(self, _host: str, _msg: str) -> None:
        self._fetch_json_schema_btn.setEnabled(True)
        self._fetch_json_schema_btn.setText("✗ Failed")
        self._fetch_json_btn_reset_timer.start(3000)

    def _on_openapi_error_dialog(self, _host: str, msg: str) -> None:
        QMessageBox.warning(self, "Schema Fetch Error", f"Failed to fetch schema:\n{msg}")

    def _auto_fetch_openapi(self) -> None:
        """Load from cache if available, otherwise trigger a silent background probe."""
        raw_url = self._url_getter()
        if not raw_url:
            return
        url = substitute_params(raw_url, self._env_getter())
        if re.search(r"<[^>]+>", url):
            return
        host = host_from_url(url)
        cached = get_cached_openapi_schema(host)
        if cached is not None:
            self.json_editor.set_completions(extract_openapi_completions(cached))
            return
        self._trigger_openapi_fetch(silent=True)

    def _on_type_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.changed.emit()
        if index == 2:  # JSON
            self._auto_fetch_openapi()
        elif index == 3:  # GraphQL
            self._auto_fetch_schema()

    def get_body_type(self) -> str:
        mapping = {0: "none", 1: "form", 2: "json", 3: "graphql", 4: "multipart"}
        return mapping.get(self.type_combo.currentIndex(), "none")

    def set_body_type(self, body_type: str) -> None:
        mapping = {"none": 0, "form": 1, "json": 2, "graphql": 3, "multipart": 4}
        self.type_combo.setCurrentIndex(mapping.get(body_type, 0))

    def on_request_loaded(self) -> None:
        """Must be called after a request is fully loaded into the editor.

        Re-applies schema-based completions from cache for the current body
        type even when the body-type combo index has not changed (which would
        suppress the normal ``currentIndexChanged`` signal).
        """
        index = self.type_combo.currentIndex()
        if index == 2:  # JSON
            self._auto_fetch_openapi()
        elif index == 3:  # GraphQL
            self._auto_fetch_schema()

    def get_body_content(self) -> str:
        bt = self.get_body_type()
        if bt == "json":
            return self.json_editor.toPlainText()
        elif bt == "graphql":
            return self.graphql_query.toPlainText()
        return ""

    def set_body_content(self, content: str) -> None:
        bt = self.get_body_type()
        if bt == "json":
            self.json_editor.setPlainText(content)
        elif bt == "graphql":
            self.graphql_query.setPlainText(content)

    def get_graphql_variables(self) -> str:
        return self.graphql_vars.toPlainText()

    def set_graphql_variables(self, variables: str) -> None:
        self.graphql_vars.setPlainText(variables)

    def get_form_items(self) -> list[tuple[bool, str, str]]:
        return self.form_editor.get_items()

    def set_form_items(self, items: list[tuple[bool, str, str]]) -> None:
        self.form_editor.set_items(items)

    def get_multipart_text_items(self) -> list[tuple[bool, str, str]]:
        return self.multipart_text_editor.get_items()

    def set_multipart_text_items(self, items: list[tuple[bool, str, str]]) -> None:
        self.multipart_text_editor.set_items(items)

    def get_multipart_file_items(self) -> list[tuple[bool, str, str]]:
        return self.multipart_file_editor.get_items()

    def set_multipart_file_items(self, items: list[tuple[bool, str, str]]) -> None:
        self.multipart_file_editor.set_items(items)
