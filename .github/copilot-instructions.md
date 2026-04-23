# AngryREST — Copilot Instructions

## Tech Stack

- **Language**: Python 3.11+ with `from __future__ import annotations`
- **UI Framework**: PySide6 (Qt for Python) — cross-platform (Windows/Linux/macOS)
- **HTTP**: httpx (sync client)
- **Packaging**: setuptools with `pyproject.toml`, editable install via `pip install -e .`
- **Standalone builds**: PyInstaller

## Project Structure

```
src/angryrest/
├── app.py                  # Entry point, QApplication setup
├── models/                 # Pure dataclasses, no Qt dependencies
│   ├── collection.py       # Collection, RequestDef, KeyValue
│   └── environment.py      # Environment
├── services/               # Business logic, no Qt UI imports
│   ├── storage.py          # JSON persistence (~/.angryrest/)
│   ├── http_client.py      # httpx wrapper, param substitution
│   └── script_engine.py    # Pre/post script execution, assertions
├── ui/                     # All PySide6 UI code
│   ├── main_window.py      # MainWindow, toolbar, splitter layout
│   ├── collections_panel.py
│   ├── request_panel.py
│   ├── response_panel.py
│   ├── environment_dialog.py
│   ├── collection_runner.py
│   └── widgets/            # Reusable widgets
│       ├── key_value_editor.py
│       ├── body_editor.py
│       ├── script_editor.py
│       ├── parameter_highlighter.py
│       └── url_input.py
└── resources/
    └── styles.qss          # Dark theme stylesheet
```

## Architecture Rules

1. **Models are plain dataclasses** — no Qt imports, no UI logic. Serialization via `to_dict()`/`from_dict()` class methods
2. **Services never import from `ui/`** — they operate on models and return results
3. **UI widgets emit signals** — parent panels connect signals to slots; avoid direct coupling between panels
4. **Long-running work on QThread** — HTTP requests and collection runs use `QThread` subclasses with signals reporting results; never block the UI thread
5. **Parameter substitution** uses `<paramName>` syntax (angle brackets). Regex: `r"<([^>]+)>"`

## Python Conventions

- Use type hints on all function signatures
- Use `from __future__ import annotations` in every module
- Prefer `dataclass` over plain classes for data containers
- Use `field(default_factory=...)` for mutable defaults, never mutable default arguments
- Use `pathlib.Path` for file system operations, not `os.path`
- String formatting: f-strings preferred
- Imports: stdlib → third-party → local, separated by blank lines
- No wildcard imports (`from x import *`)
- **Never use bare `dict` or `list` as a type annotation** — always parameterise: `dict[str, Any]`, `list[str]`, etc. Import `Any` from `typing` when the value type is genuinely unknown

## PySide6 / Qt Conventions

- Use `Signal` (not `pyqtSignal`) and `Slot` from `PySide6.QtCore`
- Set `objectName` on widgets that need QSS styling (e.g., `sendButton`)
- Use `QSplitter` for resizable panels — never fixed layouts for the main panel structure
- Use `blockSignals(True)` when programmatically updating widgets to avoid recursive signal loops
- Prefer `QPlainTextEdit` over `QTextEdit` for code/text content (better performance)
- Widgets that highlight `<param>` patterns must accept an `env_getter` callable so highlighting stays in sync with the active environment
- **Always use scoped PySide6 enums** — e.g. `Qt.Orientation.Vertical`, `Qt.AlignmentFlag.AlignCenter`, `Qt.ScrollBarPolicy.ScrollBarAlwaysOff`, `QPlainTextEdit.LineWrapMode.NoWrap`, `QHeaderView.ResizeMode.Stretch`, `QAbstractItemView.SelectionMode.NoSelection`. Never use the flat pre-Qt6 form (`Qt.Vertical`, `Qt.AlignCenter`, etc.)
- **Always type `eventFilter` overrides** with `(self, obj: QObject, event: QEvent) -> bool`; cast to the specific event subclass (`QMouseEvent`, `QKeyEvent`, etc.) inside the handler using `cast()` from `typing`
- **Always type `closeEvent` overrides** with `(self, event: QCloseEvent) -> None` (import `QCloseEvent` from `PySide6.QtGui`)
- **Never access protected attributes of other classes** — add a public accessor or method instead (e.g. `get_env()` on `ParameterHighlighter` rather than reading `_env_getter` from outside)
- **Type all `Callable` parameters explicitly** — env-getter callbacks must be typed as `Callable[[], dict[str, str]]` (import from `collections.abc`)

## Script Engine

Pre and post request scripts run via `exec()` in a restricted namespace. Available in the namespace:
- **Pre-script**: `env` (mutable dict), `request` (dict with method/url/headers), `json`, `re`, `base64`, `hashlib`, `uuid`, `print`
- **Post-script**: all the above plus `response` (wrapper with `.status_code`, `.headers`, `.text()`, `.json()`) and assertion functions: `assert_status()`, `assert_equals()`, `assert_true()`, `assert_contains()`

## Testing Approach

- Test models and services with unit tests (no Qt dependency)
- Test UI components only when behaviour is complex — prefer integration-level checks
- Use `pytest` as test runner

## Common Mistakes to Avoid

- Do not use `json` as a variable name — it shadows the stdlib module exposed in script namespaces
- Do not call `QWidget.show()` inside `__init__` — let the caller control visibility
- Do not store Qt widgets in dataclass models
- Do not read/write files on the main thread — use `StorageService` methods which are fast (small JSON files), but any future large-file work must be moved off-thread
- Do not shadow `QThread.finished` with a custom `Signal` — name custom result signals differently (e.g. `result_ready`); connect `finished` to `deleteLater` for safe C++ object cleanup
- Do not delete a Qt object synchronously inside its own signal handler (e.g. removing a row while inside the delete-button's `clicked` slot) — defer with `QTimer.singleShot(0, ...)`
- Do not close/destroy a dialog or window without disconnecting in-flight `QThread` worker signals first — add `closeEvent` overrides that call `worker.stop()` and `worker.<signal>.disconnect()`
- **`QThread` worker references become invalid after `deleteLater` is called** — always clear the Python reference to the worker (e.g. `self._worker = None`) in a slot connected to `finished` *before* `deleteLater` runs, so subsequent `isRunning()` calls do not crash on the deleted C++ object
- **`QCompleter.popup()` returns `QAbstractItemView | None`** — always guard: check `if popup is not None` before the first `super().keyPressEvent()` call, then add an `if popup is None: return` guard after the super call so the rest of the method operates on a non-None popup
