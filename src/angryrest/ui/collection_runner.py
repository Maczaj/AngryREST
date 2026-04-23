from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from angryrest.models.collection import Collection, KeyValue
from angryrest.models.environment import Environment
from angryrest.services.http_client import ErrorResult, HttpClient, ResponseData
from angryrest.services.script_engine import ScriptEngine, ScriptResult


class _RunWorker(QThread):
    request_started = Signal(int, str)  # index, request name
    request_finished = Signal(int, bool, str)  # index, success, summary
    all_done = Signal(str)  # final summary

    def __init__(
        self,
        collection: Collection,
        env_vars: dict[str, str],
        http_client: HttpClient,
        script_engine: ScriptEngine,
    ):
        super().__init__()
        self.collection = collection
        self.env_vars = dict(env_vars)
        self.http_client = http_client
        self.script_engine = script_engine
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        passed = 0
        failed = 0
        env = dict(self.env_vars)

        for i, req in enumerate(self.collection.requests):
            if self._stop:
                break

            self.request_started.emit(i, req.name)

            # Pre-script
            if req.pre_script.strip():
                request_info = {"method": req.method, "url": req.url}
                pre_result = self.script_engine.run_pre_script(
                    req.pre_script, env, request_info
                )
                env = pre_result.env
                if not pre_result.success:
                    failed += 1
                    self.request_finished.emit(
                        i, False, f"Pre-script error: {pre_result.error}"
                    )
                    break

            # Build request parameters
            headers = {
                kv.key: kv.value for kv in req.headers if kv.enabled and kv.key
            }
            query_params = {
                kv.key: kv.value
                for kv in req.query_params
                if kv.enabled and kv.key
            }
            body = req.body_content if req.body_type in ("json", "graphql") else None
            form_data = None
            file_fields = None
            if req.body_type == "form":
                form_data = {
                    kv.key: kv.value
                    for kv in req.body_form
                    if kv.enabled and kv.key
                }
            elif req.body_type == "graphql" and req.graphql_variables:
                form_data = {"__graphql_variables__": req.graphql_variables}
            elif req.body_type == "multipart":
                form_data = {
                    kv.key: kv.value
                    for kv in req.body_form
                    if kv.enabled and kv.key
                }
                file_fields = [
                    (kv.key, kv.value)
                    for kv in req.body_files
                    if kv.enabled and kv.key and kv.value
                ]

            result = self.http_client.send(
                method=req.method,
                url=req.url,
                headers=headers,
                query_params=query_params,
                body=body,
                body_type=req.body_type,
                form_data=form_data,
                file_fields=file_fields,
                env_vars=env,
            )

            if isinstance(result, ErrorResult):
                failed += 1
                self.request_finished.emit(i, False, f"Error: {result.message}")
                break

            # Post-script
            if req.post_script.strip():
                post_result = self.script_engine.run_post_script(
                    req.post_script, env, result
                )
                env = post_result.env
                if not post_result.success:
                    failed += 1
                    summary_parts = []
                    if post_result.error:
                        summary_parts.append(f"Script error: {post_result.error}")
                    for a in post_result.assertions:
                        if not a.passed:
                            summary_parts.append(f"Assertion failed: {a.message}")
                    self.request_finished.emit(
                        i, False, "; ".join(summary_parts) or "Post-script failed"
                    )
                    break
                passed += 1
                self.request_finished.emit(
                    i, True, f"{result.status_code} ({result.elapsed_ms}ms)"
                )
            else:
                if 200 <= result.status_code < 400:
                    passed += 1
                    self.request_finished.emit(
                        i, True, f"{result.status_code} ({result.elapsed_ms}ms)"
                    )
                else:
                    failed += 1
                    self.request_finished.emit(
                        i, False,
                        f"{result.status_code} {result.reason_phrase} ({result.elapsed_ms}ms)",
                    )
                    break

        total = len(self.collection.requests)
        skipped = total - passed - failed
        self.all_done.emit(
            f"Done: {passed} passed, {failed} failed, {skipped} skipped out of {total}"
        )


class CollectionRunnerDialog(QDialog):
    def __init__(
        self,
        collection: Collection,
        env_vars: dict[str, str],
        http_client: HttpClient,
        script_engine: ScriptEngine,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Run Collection: {collection.name}")
        self.setMinimumSize(600, 400)
        self.collection = collection
        self._worker: _RunWorker | None = None

        layout = QVBoxLayout(self)

        # Request list
        self.request_list = QListWidget()
        for req in collection.requests:
            item = QListWidgetItem(f"⬜ {req.method}  {req.name}")
            self.request_list.addItem(item)
        layout.addWidget(self.request_list)

        # Progress
        self.progress = QProgressBar()
        self.progress.setMaximum(len(collection.requests))
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Summary
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(self.summary_label)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        layout.addWidget(self.log)

        # Buttons
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self._start_run)
        btn_layout.addWidget(self.run_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_run)
        btn_layout.addWidget(self.stop_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        self._http_client = http_client
        self._script_engine = script_engine
        self._env_vars = env_vars

    def closeEvent(self, event) -> None:
        # Stop the worker and disconnect its signals before the dialog is destroyed.
        # Without this, the thread can dispatch queued signals to already-deleted
        # slot objects, causing a segfault.
        if self._worker is not None:
            self._worker.stop()
            try:
                self._worker.request_started.disconnect()
                self._worker.request_finished.disconnect()
                self._worker.all_done.disconnect()
            except RuntimeError:
                pass
        super().closeEvent(event)

    def _start_run(self) -> None:
        # Reset state
        for i in range(self.request_list.count()):
            req = self.collection.requests[i]
            self.request_list.item(i).setText(f"⬜ {req.method}  {req.name}")
        self.progress.setValue(0)
        self.summary_label.setText("")
        self.log.clear()

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self._worker = _RunWorker(
            self.collection,
            self._env_vars,
            self._http_client,
            self._script_engine,
        )
        self._worker.request_started.connect(self._on_request_started)
        self._worker.request_finished.connect(self._on_request_finished)
        self._worker.all_done.connect(self._on_all_done)
        # Keep the QThread alive until it finishes, then schedule C++ cleanup.
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _stop_run(self) -> None:
        if self._worker:
            self._worker.stop()

    def _on_request_started(self, index: int, name: str) -> None:
        item = self.request_list.item(index)
        req = self.collection.requests[index]
        item.setText(f"🔄 {req.method}  {name}")
        self.log.append(f"Running: {name}...")

    def _on_request_finished(self, index: int, success: bool, summary: str) -> None:
        item = self.request_list.item(index)
        req = self.collection.requests[index]
        icon = "✅" if success else "❌"
        item.setText(f"{icon} {req.method}  {req.name}  —  {summary}")
        self.progress.setValue(index + 1)
        self.log.append(f"  {'PASS' if success else 'FAIL'}: {summary}")

    def _on_all_done(self, summary: str) -> None:
        self.summary_label.setText(summary)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log.append(f"\n{summary}")
        self._worker = None
