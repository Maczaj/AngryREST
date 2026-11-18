# AGENTS.md — AngryREST

Cross-platform desktop REST/GraphQL client (Postman-like). Python 3.11+, PySide6 (Qt6), httpx, single `src/angryrest` package, active branch **`main`** (protected default branch).

---

## Working principles

=== SPECS: source of truth for behavior ===
Every functional change MUST update the relevant spec(s). Specs define *what* the app does — they are NOT implementation notes. The code implements the spec; the spec does not describe the code.

| Spec | Purpose | When to use |
|------|---------|-------------|
| `docs/PRODUCT_SPEC.md` | What the app does: features, user flows, behavior rules. | Adding/removing features, changing capabilities or flows. |
| `docs/UX_SPEC.md` | How it looks/feels: design tokens, layouts, interaction patterns. | Changing UI behavior, adding controls, updating tokens. |
| `docs/ARCHITECTURE.md` | How it's built: hexagonal layers, MVVM/QML, ports & adapters, DI, threading. | Structural changes, new services, layer-boundary changes. |

**When to update which spec:**
- User-facing behavior change → `PRODUCT_SPEC.md` + (if UI-visible) `UX_SPEC.md`
- Structural/architecture change → `ARCHITECTURE.md` (+ ADR if significant)
- Bug fix → check whether the spec already describes the correct behavior (the bug is implementation drift) — update specs only if the intended behavior itself changed

- **Learn from history.** Before any significant change, analyze past PRs/commits for the affected area. Use `codedev-mcp` (`git_log`, `git_blame`, `semantic_search`, `find_references`) to ground decisions in real history.
- **Check whether the problem is already solved.** Search the repo before writing new code.
- **KISS and YAGNI.** Write only what is needed now, structured for easy extension.
- **Clean code.** SOLID, DRY, defensive programming; handle errors and edge cases.
- **Document decisions.** Significant PRs include a rationale (ADR) explaining *why*.

---

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]          # editable install required — tests import from src/
```

Linux may need: `sudo apt install libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-keysyms1 libegl1`  
WSL2: needs WSLg (Win11) or VcXsrv + `export DISPLAY=...`

---

## Commands

```bash
# Run
python -m angryrest / angryrest / poe run

# Test
poe test           # pytest tests/ -v
poe test-fast      # pytest tests/ -x -q
pytest tests/test_http_client.py::TestHttpClientSend::test_successful_get
pytest -k "test_round_trip"

# SonarQube — generate coverage and scan against local http://localhost:9000
./scan-sonar.sh

# No linter, formatter, or type-checker is configured. No CI. Tests run manually only.

# Standalone build (spec file not yet committed — poe build will fail without it)
pip install pyinstaller && pyinstaller angryrest.spec
```

---

## Required after every change — MANDATORY ✅ GATE

**🚫 NEVER commit directly to `main`.** All work is done on a feature branch. Create one with `git checkout -b <branch-name>` before any editing. Commits on `main` are forbidden — if you accidentally commit to `main`, undo it immediately and create a branch.

You MUST complete ALL of the following before considering any change done:

1. **Update the relevant spec(s).** See the decision tree in "Working principles → SPECS". This is part of the change — untracked behavior change is incomplete change.
2. **Write tests for every changed component.** Every new function/method/module must have tests; every behavioral change adds/updates test cases. No exceptions — untested code is incomplete code.
3. **Run the full test suite** (`poe test`). Nothing must break.
4. **Run `./scan-sonar.sh`.** The Quality Gate must pass. If a condition fails — coverage, duplication, violations — resolve it before proceeding. Pre-existing failures in an untouched area may be documented in the PR body with justification.
5. **Create a pull request** using `gh pr create` (base `main`). This is the final step and MUST NOT be skipped. If a PR is already open for the branch, push to it instead.
6. **Follow-up changes after a PR is open** go to the same PR branch — commit and push; never leave deltas only in the working tree.

If any gate fails, fix it and re-run. Do not hand off incomplete work.

---

## Architecture (strict — enforce in all new code)

Target architecture (hexagonal + QML/MVVM) is defined in `docs/ARCHITECTURE.md`. The `models/`/`services/`/`ui/` rules below reflect the current QWidget MVP; these packages migrate into `domain/`/`application/`/`infrastructure/` per that spec.

**Layer import rules:**
- `models/` — zero Qt, zero UI logic. Serialization via `to_dict()` / `from_dict()` only.
- `services/` — no imports from `ui/`. Exception: `graphql_schema.py` and `openapi_schema.py` may use `QThread`/`Signal` (background wrappers), but must have zero `QWidget` references.
- `ui/` — all PySide6 code. Widgets emit signals; parents connect them. No direct sibling–panel coupling.

**QThread lifetime pattern** (copy from `main_window.py`):
- Connect `finished` → `deleteLater` for C++ cleanup.
- Connect `finished` → a slot that sets the Python reference to `None` *before* `deleteLater`.
- Disconnect all worker signals in `closeEvent` before `super()`.
- Name result signals `result_ready`, never `finished` — that would shadow `QThread.finished`.

**Qt enum scoping** — always use fully-scoped Qt6 forms:  
`Qt.Orientation.Vertical`, `Qt.AlignmentFlag.AlignCenter`, `Qt.ItemDataRole.UserRole`  
Never use Qt5 flat forms (`Qt.Vertical`, `Qt.AlignCenter`).

**Deferred actions** — use `QTimer.singleShot(0, ...)` when deleting a row from within that row's signal handler, or when forcing a popup closed.

**Loading data into widgets** — set `blockSignals(True)` to prevent recursive change signals. See `RequestPanel._loading` flag.

---

## Testing

- Tests cover `models/` and `services/` only — **zero Qt in the test suite**.
- `StorageService` tests pass `StorageService(base_dir=tmp_path)` — never touch `~/.angryrest/`.
- `HttpClient` tests mock `httpx.Client` via `unittest.mock.patch`.
- `ScriptEngine` tests call the engine directly with plain dicts.

---

## Python Conventions

- `from __future__ import annotations` in **every** module (no exceptions).
- `Callable` imported from `collections.abc` (not `typing`).
- `cast()` from `typing` for type-narrowing inside `eventFilter`.
- `closeEvent(self, event: QCloseEvent)` — import `QCloseEvent` from `PySide6.QtGui`.
- `pathlib.Path` everywhere — never `os.path`.
- No wildcard imports; always parameterise containers: `dict[str, Any]`, `list[str]`.

---

## Common Mistakes

- **Do not use `json` as a variable name** — it shadows the stdlib module injected into script namespaces.
- **Do not call `QWidget.show()` inside `__init__`** — caller controls visibility.
- **Do not store Qt widgets in dataclass models.**
- **`QCompleter.popup()` returns `QAbstractItemView | None`** — guard before use.
- **Accessing a worker after `deleteLater`** crashes — clear the Python reference in the `finished` slot first.
- **Deleting a Qt object synchronously inside its own signal handler** will crash — defer with `QTimer.singleShot(0, ...)`.

---

## Non-Obvious Quirks

- **`wayland_combo_box.py`** contains two unrelated classes: `WaylandComboBox` (QComboBox subclass that forces `hidePopup()` on Wayland) and `MethodButton` (a `QPushButton`-based HTTP verb selector using `QMenu` — used in `RequestPanel` to avoid cross-platform QComboBox styling issues).
- **`METHOD_COLORS` is intentionally defined twice** — in `collections_panel.py` and `wayland_combo_box.py` — to keep modules decoupled.
- **`styles.qss` uses `__RESOURCES__` placeholder** — `app.py` replaces it with the absolute resources path at startup so QSS `url()` refs resolve.
- **GraphQL variables travel through `form_data["__graphql_variables__"]`** — `HttpClient.send()` extracts this key when body type is `graphql`.
- **Collection runner breaks on first failure** — `_RunWorker.run()` stops the loop on the first `ErrorResult` or failed post-script.
- **`_response_cache` in `MainWindow`** replays the last response when switching requests, without a new network call.
- **`test_server.py`** is a standalone stdlib HTTP server (port 8765) for manual integration testing. Not a pytest file.
- **`src/angryrest.egg-info/`** is a build artifact from `pip install -e .` — do not edit; it is *not* gitignored.

---

## Data Persistence

```
~/.angryrest/collections/<uuid>.json   # one file per collection
~/.angryrest/collections/_order.json   # ordered list of collection IDs
~/.angryrest/environments.json         # all environments
```

Indented JSON, `ensure_ascii=False`. `StorageService` is synchronous (files are small).

---

## Script Engine Namespace

Scripts run via `exec()` — not a subprocess.

**Pre-script**: `env` (mutable dict copy), `request` (`{method, url, headers}`), `json`, `re`, `base64`, `hashlib`, `uuid`, `print`, `log`/`logging`

**Post-script**: everything above + `response` (`ResponseWrapper`: `.status_code`, `.headers`, `.elapsed_ms`, `.size_bytes`, `.text()`, `.json()`), `assert_status()`, `assert_equals()`, `assert_true()`, `assert_contains()`

Assertions raise `AssertionError` on failure; prior assertions in `ScriptResult.assertions` are preserved. `ScriptResult.success = False` on any failure.

---

## Key Entry Points

| Location | Role |
|---|---|
| `src/angryrest/app.py : main()` | `QApplication` setup; `angryrest` console script |
| `src/angryrest/ui/main_window.py : MainWindow` | Root window; owns all services and panels |
| `src/angryrest/services/http_client.py : HttpClient.send()` | All HTTP I/O |
| `src/angryrest/services/storage.py : StorageService` | All JSON persistence |
| `src/angryrest/services/script_engine.py : ScriptEngine` | Pre/post script execution |
| `.github/copilot-instructions.md` | Extended architecture + convention reference |
