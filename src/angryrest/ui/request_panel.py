from __future__ import annotations

import json
from collections.abc import Callable

import httpx
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from angryrest.models.collection import Collection, KeyValue, RequestDef
from angryrest.services.http_client import substitute_params
from angryrest.ui.widgets.body_editor import BodyEditor
from angryrest.ui.widgets.key_value_editor import KeyValueEditor, ParamValueEdit
from angryrest.ui.widgets.script_editor import ScriptEditor
from angryrest.ui.widgets.url_input import UrlInput
from angryrest.ui.widgets.wayland_combo_box import MethodButton


HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class RequestPanel(QWidget):
    send_requested = Signal()
    request_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_collection: Collection | None = None
        self._current_request: RequestDef | None = None
        self._loading = False  # flag to skip change signals during load
        self._custom_method_idx = len(HTTP_METHODS)  # index of the "Custom..." slot
        self._env_getter: Callable[[], dict[str, str]] = lambda: {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Request name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Request name")
        self.name_edit.textChanged.connect(self._on_changed)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Method + URL + Send
        url_layout = QHBoxLayout()

        self.method_combo = MethodButton()
        self.method_combo.addItems(HTTP_METHODS + ["Custom..."])
        self.method_combo.setFixedWidth(120)
        self.method_combo.setInsertPolicy(None)
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        url_layout.addWidget(self.method_combo)

        self.url_input = UrlInput()
        self.url_input.text_changed_signal.connect(self._on_changed)
        self.url_input.return_pressed.connect(self.send_requested.emit)
        url_layout.addWidget(self.url_input)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedWidth(80)
        self.send_btn.setObjectName("sendButton")
        self.send_btn.clicked.connect(self.send_requested.emit)
        url_layout.addWidget(self.send_btn)

        layout.addLayout(url_layout)

        # Tabs: Params | Headers | Body | Pre-Script | Post-Script
        self.tabs = QTabWidget()

        self.params_editor = KeyValueEditor()
        self.params_editor.changed.connect(self._on_changed)
        self.tabs.addTab(self.params_editor, "Query Params")

        self.headers_editor = KeyValueEditor()
        self.headers_editor.changed.connect(self._on_changed)
        self.tabs.addTab(self.headers_editor, "Headers")

        self.body_editor = BodyEditor()
        self.body_editor.changed.connect(self._on_changed)
        self.body_editor.set_url_getter(lambda: self.url_input.get_text())
        self.body_editor.set_headers_getter(lambda: self.headers_editor.get_items())
        self.tabs.addTab(self.body_editor, "Body")

        self.pre_script_editor = ScriptEditor()
        self.pre_script_editor.textChanged.connect(self._on_changed)
        self.tabs.addTab(self.pre_script_editor, "Pre-Script")

        self.post_script_editor = ScriptEditor()
        self.post_script_editor.textChanged.connect(self._on_changed)
        self.tabs.addTab(self.post_script_editor, "Post-Script")

        self.raw_view = QPlainTextEdit()
        self.raw_view.setReadOnly(True)
        self.raw_view.setObjectName("rawView")
        raw_font = self.raw_view.font()
        raw_font.setFamily("Monospace")
        self.raw_view.setFont(raw_font)
        self.tabs.addTab(self.raw_view, "Raw")

        layout.addWidget(self.tabs)

        # Placeholder
        self._placeholder = QLabel("Select a request from the collection panel")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(self._placeholder)

        self._set_editing_visible(False)

    def _set_editing_visible(self, visible: bool) -> None:
        self.name_edit.setVisible(visible)
        self.method_combo.setVisible(visible)
        self.url_input.setVisible(visible)
        self.send_btn.setVisible(visible)
        self.tabs.setVisible(visible)
        self._placeholder.setVisible(not visible)

    def set_env_getter(self, getter: Callable[[], dict[str, str]]) -> None:
        self._env_getter = getter
        self.url_input.set_env_getter(getter)
        self.params_editor.set_env_getter(getter)
        self.headers_editor.set_env_getter(getter)
        self.body_editor.set_env_getter(getter)

    def rehighlight_params(self) -> None:
        self.url_input.highlighter.rehighlight()
        for editor in (self.params_editor, self.headers_editor):
            for row in range(editor.table.rowCount()):
                val_edit = editor.table.cellWidget(row, 2)
                if isinstance(val_edit, ParamValueEdit):
                    val_edit.highlighter.rehighlight()
        self.body_editor.rehighlight_body()

    def load_request(self, collection: Collection, request: RequestDef) -> None:
        self._loading = True
        self._current_collection = collection
        self._current_request = request
        self._set_editing_visible(True)

        self.name_edit.setText(request.name)

        method_upper = request.method.upper()
        self.method_combo.blockSignals(True)
        if method_upper in HTTP_METHODS:
            self.method_combo.setCurrentIndex(HTTP_METHODS.index(method_upper))
            self.method_combo.setItemText(self._custom_method_idx, "Custom...")
        else:
            self.method_combo.setItemText(self._custom_method_idx, method_upper)
            self.method_combo.setCurrentIndex(self._custom_method_idx)
        self.method_combo.blockSignals(False)

        self.url_input.set_text(request.url)

        self.params_editor.set_items(
            [(kv.enabled, kv.key, kv.value) for kv in request.query_params]
        )
        self.headers_editor.set_items(
            [(kv.enabled, kv.key, kv.value) for kv in request.headers]
        )

        self.body_editor.set_body_type(request.body_type)
        if request.body_type == "form":
            self.body_editor.set_form_items(
                [(kv.enabled, kv.key, kv.value) for kv in request.body_form]
            )
        elif request.body_type == "json":
            self.body_editor.set_body_content(request.body_content)
        elif request.body_type == "graphql":
            self.body_editor.set_body_content(request.body_content)
            self.body_editor.set_graphql_variables(request.graphql_variables)
        elif request.body_type == "multipart":
            self.body_editor.set_multipart_text_items(
                [(kv.enabled, kv.key, kv.value) for kv in request.body_form]
            )
            self.body_editor.set_multipart_file_items(
                [(kv.enabled, kv.key, kv.value) for kv in request.body_files]
            )

        self.pre_script_editor.setPlainText(request.pre_script)
        self.post_script_editor.setPlainText(request.post_script)

        self._loading = False
        self._update_raw_view()
        self.body_editor.on_request_loaded()

    def save_to_request(self) -> RequestDef | None:
        if not self._current_request:
            return None
        req = self._current_request
        req.name = self.name_edit.text()
        method_text = self.method_combo.currentText().strip()
        req.method = method_text if method_text and method_text != "Custom..." else "GET"
        req.url = self.url_input.get_text()

        req.query_params = [
            KeyValue(key=k, value=v, enabled=e)
            for e, k, v in self.params_editor.get_items()
        ]
        req.headers = [
            KeyValue(key=k, value=v, enabled=e)
            for e, k, v in self.headers_editor.get_items()
        ]

        req.body_type = self.body_editor.get_body_type()
        if req.body_type == "form":
            req.body_form = [
                KeyValue(key=k, value=v, enabled=e)
                for e, k, v in self.body_editor.get_form_items()
            ]
        elif req.body_type in ("json", "graphql"):
            req.body_content = self.body_editor.get_body_content()
        if req.body_type == "graphql":
            req.graphql_variables = self.body_editor.get_graphql_variables()
        if req.body_type == "multipart":
            req.body_form = [
                KeyValue(key=k, value=v, enabled=e)
                for e, k, v in self.body_editor.get_multipart_text_items()
            ]
            req.body_files = [
                KeyValue(key=k, value=v, enabled=e)
                for e, k, v in self.body_editor.get_multipart_file_items()
            ]

        req.pre_script = self.pre_script_editor.toPlainText()
        req.post_script = self.post_script_editor.toPlainText()

        return req

    def clear_request(self) -> None:
        self._current_collection = None
        self._current_request = None
        self._set_editing_visible(False)

    def get_current_request(self) -> tuple[Collection | None, RequestDef | None]:
        return self._current_collection, self._current_request

    def _on_method_changed(self, index: int) -> None:
        if index == self._custom_method_idx:
            existing = self.method_combo.itemText(self._custom_method_idx)
            default_text = "" if existing == "Custom..." else existing
            method, ok = QInputDialog.getText(
                self, "Custom HTTP Method", "HTTP Method:", text=default_text
            )
            self.method_combo.blockSignals(True)
            if ok and method.strip():
                self.method_combo.setItemText(self._custom_method_idx, method.strip().upper())
            else:
                # Revert to GET on cancel
                self.method_combo.setCurrentIndex(0)
            self.method_combo.blockSignals(False)
        self._on_changed()

    def _update_raw_view(self) -> None:
        req = self._current_request
        if req is None:
            self.raw_view.setPlainText("")
            return

        env_vars = self._env_getter()

        user_headers = {kv.key: kv.value for kv in req.headers if kv.enabled and kv.key}
        query_params = {kv.key: kv.value for kv in req.query_params if kv.enabled and kv.key}

        resolved_url = substitute_params(req.url, env_vars)
        resolved_headers = {
            substitute_params(k, env_vars).title(): substitute_params(v, env_vars)
            for k, v in user_headers.items()
        }
        resolved_params = {
            substitute_params(k, env_vars): substitute_params(v, env_vars)
            for k, v in query_params.items()
        }

        resolved_headers.setdefault("User-Agent", "AngryREST/0.0.1")

        content: bytes | None = None
        data: dict[str, str] | None = None

        if req.body_type == "json" and req.body_content:
            resolved_body = substitute_params(req.body_content, env_vars)
            resolved_headers.setdefault("Content-Type", "application/json")
            content = resolved_body.encode("utf-8")
        elif req.body_type == "graphql" and req.body_content:
            resolved_query = substitute_params(req.body_content, env_vars)
            resolved_headers.setdefault("Content-Type", "application/graphql")
            if resolved_headers.get("Content-Type", "").lower() == "application/graphql":
                content = resolved_query.encode("utf-8")
            else:
                graphql_payload: dict[str, object] = {"query": resolved_query}
                if req.graphql_variables:
                    vars_str = substitute_params(req.graphql_variables, env_vars)
                    try:
                        graphql_payload["variables"] = json.loads(vars_str)
                    except (json.JSONDecodeError, ValueError):
                        pass
                content = json.dumps(graphql_payload).encode("utf-8")
        elif req.body_type == "form" and req.body_form:
            resolved_form = {
                substitute_params(kv.key, env_vars): substitute_params(kv.value, env_vars)
                for kv in req.body_form
                if kv.enabled and kv.key
            }
            data = resolved_form or None
        elif req.body_type == "multipart":
            resolved_form = {
                substitute_params(kv.key, env_vars): substitute_params(kv.value, env_vars)
                for kv in req.body_form
                if kv.enabled and kv.key
            }
            data = resolved_form or None

        try:
            if req.body_type == "multipart":
                # File contents are not loaded for the raw preview
                lines = [f"{req.method.upper()} {substitute_params(req.url, env_vars)} HTTP/1.1"]
                for k, v in resolved_headers.items():
                    lines.append(f"{k}: {v}")
                lines.append("")
                lines.append("Content-Type: multipart/form-data")
                for kv in req.body_form:
                    if kv.enabled and kv.key:
                        lines.append(f"  [text]  {kv.key} = {kv.value}")
                for kv in req.body_files:
                    if kv.enabled and kv.key:
                        lines.append(f"  [file]  {kv.key} → {kv.value or '(no file)'}")
                self.raw_view.setPlainText("\n".join(lines))
                return
            client = httpx.Client()
            built = client.build_request(
                method=req.method.upper(),
                url=resolved_url,
                headers=resolved_headers or None,
                params=resolved_params or None,
                content=content,
                data=data,
            )
            raw_path = built.url.raw_path.decode("ascii", errors="replace")
            lines = [f"{built.method} {raw_path} HTTP/1.1"]
            for key, value in built.headers.items():
                lines.append(f"{key}: {value}")
            lines.append("")
            if built.content:
                lines.append(built.content.decode("utf-8", errors="replace"))
            self.raw_view.setPlainText("\n".join(lines))
        except Exception as exc:
            self.raw_view.setPlainText(f"(Unable to build raw preview: {exc})")

    def _on_changed(self) -> None:
        if not self._loading:
            self.save_to_request()
            self._update_raw_view()
            self.request_changed.emit()
