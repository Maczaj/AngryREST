from __future__ import annotations

import importlib.metadata
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
)

from angryrest.models.collection import Collection, RequestDef
from angryrest.models.environment import Environment
from angryrest.services.http_client import ErrorResult, HttpClient, ResponseData
from angryrest.services.script_engine import ScriptEngine, ScriptResult
from angryrest.services.storage import StorageService
from angryrest.ui.collection_runner import CollectionRunnerDialog
from angryrest.ui.collections_panel import CollectionsPanel
from angryrest.ui.environment_dialog import EnvironmentDialog
from angryrest.ui.logs_dialog import LogsDialog
from angryrest.ui.request_panel import RequestPanel
from angryrest.ui.response_panel import ResponsePanel
from angryrest.ui.widgets.wayland_combo_box import WaylandComboBox
from angryrest.services import app_logger


class _RequestWorker(QThread):
    # Named `result_ready` (not `finished`) to avoid shadowing QThread.finished,
    # which is needed for safe thread-lifetime management.
    result_ready = Signal(object, object, object)  # response, pre_result, post_result

    def __init__(
        self,
        http_client: HttpClient,
        script_engine: ScriptEngine,
        method: str,
        url: str,
        headers: dict[str, str],
        query_params: dict[str, str],
        body: str | None,
        body_type: str,
        form_data: dict[str, str] | None,
        file_fields: list[tuple[str, str]] | None,
        env_vars: dict[str, str],
        pre_script: str,
        post_script: str,
    ):
        super().__init__()
        self.http_client = http_client
        self.script_engine = script_engine
        self.method = method
        self.url = url
        self.headers = headers
        self.query_params = query_params
        self.body = body
        self.body_type = body_type
        self.form_data = form_data
        self.file_fields = file_fields
        self.env_vars = dict(env_vars)
        self.pre_script = pre_script
        self.post_script = post_script

    def run(self) -> None:
        env = dict(self.env_vars)
        pre_result = None
        post_result = None

        # Pre-script
        if self.pre_script.strip():
            request_info: dict[str, Any] = {
                "method": self.method,
                "url": self.url,
                "headers": dict(self.headers),
            }
            pre_result = self.script_engine.run_pre_script(
                self.pre_script, env, request_info
            )
            env = pre_result.env
            if not pre_result.success:
                self.finished.emit(None, pre_result, None)
                return

        response = self.http_client.send(
            method=self.method,
            url=self.url,
            headers=self.headers,
            query_params=self.query_params,
            body=self.body,
            body_type=self.body_type,
            form_data=self.form_data,
            file_fields=self.file_fields,
            env_vars=env,
        )

        # Post-script
        if self.post_script.strip() and isinstance(response, ResponseData):
            post_result = self.script_engine.run_post_script(
                self.post_script, env, response
            )
            env = post_result.env

        self.result_ready.emit(response, pre_result, post_result)
        # Store updated env for caller to pick up
        self.env_vars = env


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AngryREST")
        self.resize(1400, 900)

        # Services
        self.storage = StorageService()
        self.http_client = HttpClient()
        self.script_engine = ScriptEngine()

        # Data
        self.collections = self.storage.load_collections()
        self.environments = self.storage.load_environments()
        self._current_env: Environment | None = None
        self._worker: _RequestWorker | None = None

        # --- Toolbar ---
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Environment selector
        toolbar.addWidget(QLabel("  Environment: "))
        self.env_combo = WaylandComboBox()
        self.env_combo.setMinimumWidth(180)
        self.env_combo.currentIndexChanged.connect(self._on_env_changed)
        toolbar.addWidget(self.env_combo)

        manage_env_btn = QPushButton("Manage...")
        manage_env_btn.clicked.connect(self._open_env_dialog)
        toolbar.addWidget(manage_env_btn)

        toolbar.addSeparator()

        run_collection_btn = QPushButton("▶ Run Collection")
        run_collection_btn.clicked.connect(self._run_collection)
        toolbar.addWidget(run_collection_btn)

        # --- Panels ---
        self.collections_panel = CollectionsPanel(self.collections)
        self.collections_panel.request_selected.connect(self._on_request_selected)
        self.collections_panel.data_changed.connect(self._save_all)

        self.request_panel = RequestPanel()
        self.request_panel.send_requested.connect(self._on_send_request)
        self.request_panel.request_changed.connect(self._on_request_data_changed)
        self.request_panel.set_env_getter(self._get_env_vars)

        self.response_panel = ResponsePanel()

        # --- Layout ---
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.request_panel)
        right_splitter.addWidget(self.response_panel)
        right_splitter.setSizes([500, 400])

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.collections_panel)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([300, 1100])

        self.setCentralWidget(main_splitter)

        self._refresh_env_combo()

        # --- Status bar ---
        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        self.setStatusBar(status_bar)

        try:
            version = importlib.metadata.version("angryrest")
        except importlib.metadata.PackageNotFoundError:
            version = "dev"
        app_label = QLabel(f"AngryREST v{version}")
        app_label.setObjectName("statusAppLabel")
        status_bar.addWidget(app_label)

        self._logs_btn = QPushButton("Logs")
        self._logs_btn.setObjectName("statusLogsButton")
        self._logs_btn.setFlat(True)
        self._logs_btn.clicked.connect(self._open_logs)
        status_bar.addPermanentWidget(self._logs_btn)

    # --- Environment ---

    def _refresh_env_combo(self) -> None:
        self.env_combo.blockSignals(True)
        current_id = self._current_env.id if self._current_env else None
        self.env_combo.clear()
        self.env_combo.addItem("No Environment", "")
        select_idx = 0
        for i, env in enumerate(self.environments):
            self.env_combo.addItem(env.name, env.id)
            if env.id == current_id:
                select_idx = i + 1
        self.env_combo.setCurrentIndex(select_idx)
        self.env_combo.blockSignals(False)

    def _on_env_changed(self, index: int) -> None:
        env_id = self.env_combo.currentData()
        self._current_env = None
        if env_id:
            for env in self.environments:
                if env.id == env_id:
                    self._current_env = env
                    break
        # Re-highlight URL parameters
        self.request_panel.rehighlight_params()

    def _get_env_vars(self) -> dict[str, str]:
        if self._current_env:
            return dict(self._current_env.variables)
        return {}

    def _open_env_dialog(self) -> None:
        dlg = EnvironmentDialog(self.environments, self)
        dlg.environments_changed.connect(self._on_environments_modified)
        dlg.exec()
        self._refresh_env_combo()
        self.storage.save_environments(self.environments)

    def _on_environments_modified(self) -> None:
        self._refresh_env_combo()
        self.request_panel.rehighlight_params()

    # --- Request handling ---

    def _on_request_selected(self, collection: Collection, request: RequestDef) -> None:
        self.request_panel.load_request(collection, request)

    def _on_request_data_changed(self) -> None:
        coll, req = self.request_panel.get_current_request()
        if coll and req:
            self.collections_panel.refresh_request_label(coll, req)
            self.storage.save_collection(coll)

    def _on_send_request(self) -> None:
        _, req = self.request_panel.get_current_request()
        if not req:
            return

        self.request_panel.save_to_request()
        self.response_panel.show_loading()
        self.request_panel.send_btn.setEnabled(False)

        headers = {
            kv.key: kv.value for kv in req.headers if kv.enabled and kv.key
        }
        query_params = {
            kv.key: kv.value for kv in req.query_params if kv.enabled and kv.key
        }

        body = req.body_content if req.body_type in ("json", "graphql") else None
        form_data = None
        file_fields = None
        if req.body_type == "form":
            form_data = {
                kv.key: kv.value for kv in req.body_form if kv.enabled and kv.key
            }
        elif req.body_type == "graphql" and req.graphql_variables:
            form_data = {"__graphql_variables__": req.graphql_variables}
        elif req.body_type == "multipart":
            form_data = {
                kv.key: kv.value for kv in req.body_form if kv.enabled and kv.key
            }
            file_fields = [
                (kv.key, kv.value)
                for kv in req.body_files
                if kv.enabled and kv.key and kv.value
            ]

        env_vars = self._get_env_vars()

        self._worker = _RequestWorker(
            http_client=self.http_client,
            script_engine=self.script_engine,
            method=req.method,
            url=req.url,
            headers=headers,
            query_params=query_params,
            body=body,
            body_type=req.body_type,
            form_data=form_data,
            file_fields=file_fields,
            env_vars=env_vars,
            pre_script=req.pre_script,
            post_script=req.post_script,
        )
        self._worker.result_ready.connect(self._on_request_finished)
        # Keep the QThread alive until it finishes, then schedule C++ cleanup.
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_request_finished(
        self,
        response: ResponseData | ErrorResult | None,
        pre_result: ScriptResult | None,
        post_result: ScriptResult | None,
    ) -> None:
        self.request_panel.send_btn.setEnabled(True)

        # Update environment from scripts
        if self._worker and self._current_env:
            self._current_env.variables.update(self._worker.env_vars)
            self.storage.save_environments(self.environments)

        if response is None and pre_result and not pre_result.success:
            # Pre-script failed
            error = ErrorResult("other", f"Pre-script error: {pre_result.error}")
            self.response_panel.show_error(error)
        elif isinstance(response, ErrorResult):
            self.response_panel.show_error(response)
        elif isinstance(response, ResponseData):
            self.response_panel.show_response(response)

        self.response_panel.show_script_output(pre_result, post_result)

        self._update_logs_btn()

    # --- Logs ---

    def _update_logs_btn(self) -> None:
        errors = app_logger.error_count()
        total = app_logger.total_count()
        if errors:
            self._logs_btn.setText(f"Logs ({errors} error{'s' if errors != 1 else ''}!)")
        elif total:
            self._logs_btn.setText(f"Logs ({total})")
        else:
            self._logs_btn.setText("Logs")

    def _open_logs(self) -> None:
        dlg = LogsDialog(self)
        dlg.exec()
        self._update_logs_btn()

    # --- Collection runner ---

    def _run_collection(self) -> None:
        coll, _ = self.request_panel.get_current_request()
        if not coll:
            if self.collections:
                coll = self.collections[0]
            else:
                return

        env_vars = self._get_env_vars()
        dlg = CollectionRunnerDialog(
            coll, env_vars, self.http_client, self.script_engine, self
        )
        dlg.exec()

    # --- Persistence ---

    def _save_all(self) -> None:
        for coll in self.collections:
            self.storage.save_collection(coll)
        self.storage.save_collection_order([c.id for c in self.collections])
        self.storage.save_environments(self.environments)

    def closeEvent(self, event: QCloseEvent) -> None:
        # Disconnect in-flight worker signals so the thread cannot call slots on
        # this (about-to-be-destroyed) window after we return.
        if self._worker is not None:
            try:
                self._worker.result_ready.disconnect()
            except RuntimeError:
                pass
        self._save_all()
        super().closeEvent(event)
