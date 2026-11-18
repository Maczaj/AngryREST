# ARCHITECTURE.md

# Architecture Overview

AngryREST is a cross-platform desktop REST/GraphQL client (Postman-like) built with
Python and Qt. It is an offline-first local tool: no backend, no accounts, no sync.
All data lives in `~/.angryrest/`.

The architecture prioritizes:

- strict separation of view from logic (QML + MVVM)
- maintainability
- testability (logic is testable with zero graphics environment)
- a non-blocking UI (no long-running work on the GUI thread)
- low operational complexity
- AI-assisted development

---

# Technology Stack

| Concern | Technology |
|---------|------------|
| Language | Python 3.11+ (`from __future__ import annotations` in every module) |
| UI framework | PySide6 — QML (QtQuick) + MVVM |
| HTTP client | httpx |
| GraphQL | graphql-core |
| Packaging | setuptools (`pyproject.toml`), editable install |
| Unit / VM tests | pytest + pytest-mock (QtCore-only, no GUI) |
| UI integration tests | pytest-qt (`qtbot`) + `QT_QPA_PLATFORM=offscreen` |
| Standalone builds | PyInstaller |

---

# Repository Structure

```text
src/angryrest/
  app.py                        # entry point: QGuiApplication + composition root
  domain/                       # pure logic — ZERO Qt, ZERO I/O
    models/                     #   dataclasses: Collection, RequestDef, KeyValue, Environment, ...
    services/                   #   substitution, assertion rules, runner rules
    ports/                      #   Protocol interfaces (abstract contracts)
  application/                  # orchestration + UI state
    services/                   #   use cases: SendRequest, RunCollection, FetchSchema, ...
    viewmodels/                 #   QObject view models (QtCore only)
  infrastructure/               # port implementations (adapters)
    storage/                    #   JSON persistence
    http/                       #   httpx adapter
    scripting/                  #   exec()-based script adapter
    schema/                     #   GraphQL + OpenAPI introspection adapters
  ui/                           # QML layer — render + capture intents only
    qml/                        #   .qml views
    bootstrap.py                #   QML engine setup, context wiring
  resources/

tests/
  unit/                         # domain, viewmodels, infrastructure — no GUI
  integration/                  # QML + viewmodels + fake ports via pytest-qt/qtbot
```

`models/`, `services/`, and `ui/` currently in the MVP are the QWidget-era layout.
They are migrated into the layer packages above; `domain/` becomes the only home
for models and pure services.

---

# Architectural Principles

## Separation of View and Logic

The QML layer renders state and captures user intent. It contains no business logic.

All logic lives in the domain and application layers. A QML view must never:

- compute a request body
- perform parameter substitution
- decide pass/fail for a collection run
- read or write files
- perform network I/O
- execute scripts

The view only binds to view-model properties and calls view-model slots/methods.

## Domain First

Business rules belong in the domain layer. Infrastructure, UI, and transport layers
must not contain business logic.

## Testability First

Domain, application, and infrastructure code must be testable without a graphics
environment:

- Domain: pure Python, zero Qt imports, plain pytest.
- Application / view models: QtCore only (`QObject`, `Property`, `Signal`, `Slot`),
  testable with `QCoreApplication` or no application instance at all.
- Infrastructure: mocked dependencies (`httpx` via `unittest.mock`, `tmp_path` storage).
- UI: the only layer that requires a graphics environment, exercised via
  `pytest-qt`/`qtbot` with `QT_QPA_PLATFORM=offscreen`.

## Non-Blocking UI

All long-running processes must run off the GUI thread:

- HTTP requests
- script execution (`exec()`)
- GraphQL / OpenAPI schema introspection
- any future large-file or bulk work

The GUI thread only renders and dispatches events.

## Dependency Direction

Allowed:

```text
UI (QML)
  -> Application (view models, use cases)
       -> Domain (services, models, ports)

Infrastructure implements Domain ports
```

Forbidden:

```text
Domain -> Qt (any module)
Domain -> httpx
Domain -> filesystem
Domain -> exec / subprocess
Domain -> Infrastructure
Application -> Infrastructure (only Domain ports, wired by DI)
UI -> Infrastructure
UI -> Domain
```

---

# Hexagonal Architecture

AngryREST uses ports-and-adapters (hexagonal) layering. The domain defines *ports*
(`typing.Protocol` interfaces). Infrastructure provides *adapters* that implement
those ports. The application layer depends only on port abstractions, never on
concrete adapters.

```text
                 ┌─────────────────────────────────────────────┐
                 │              UI layer (QML)                  │
                 │    renders state, captures user intent       │
                 └───────────────────┬─────────────────────────┘
                                     │ binds to / calls
                 ┌───────────────────▼─────────────────────────┐
                 │        Application layer                     │
                 │   view models (state) + use cases (flow)     │
                 └───────┬─────────────────────┬───────────────┘
                         │ calls               │ depends on
                         ▼                     ▼
                 ┌───────────────┐      ┌──────────────────────┐
                 │ Domain layer   │      │  Domain ports        │
                 │ models+services│      │  (Protocols)         │
                 └───────────────┘      └──────────▲───────────┘
                                                    │ implements
                 ┌──────────────────────────────────┴───────────┐
                 │        Infrastructure layer (adapters)        │
                 │  storage · http · scripting · schema          │
                 └───────────────────────────────────────────────┘
```

The composition root (entry point) instantiates adapters and injects them into the
application layer.

---

# MVVM (QML)

## View (QML)

- `.qml` files only.
- Declarative bindings to view-model properties.
- User actions call view-model slots/methods (or emit signals the view model handles).
- No `import` of domain/infrastructure modules from QML; only the exposed context
  properties.

## View Model (QObject)

- Subclass `QObject`, expose state via `Property` and change notifications via `Signal`.
- Expose commands/operations as `@Slot` methods.
- List/collection state is exposed via `QAbstractListModel` (QtCore) subclasses.
- **QtCore only.** Must never import `QtGui`, `QtWidgets`, `QtQuick`, or `QtQml`.
- Must never perform I/O directly — delegate to application services.
- Own the lifecycle of background workers (see Concurrency).

View models are the seam that keeps the UI dumb and the logic testable: they can be
instantiated in a plain `pytest`/`QCoreApplication` test with mocked application
services and asserted via property reads and `Signal` connections.

---

# Layer Responsibilities

## UI Layer

Responsible only for:

- rendering view-model state
- capturing and forwarding user intent

Must not contain:

- business rules
- calculations
- I/O
- orchestration

## Application Layer

Responsible for:

- use cases and orchestration (send request, run collection, fetch schema, save)
- holding UI state in view models
- mapping domain results to view-model properties
- marshalling background work and results

Must not contain:

- business rules (delegate to domain services)
- direct I/O (call ports)
- concrete infrastructure references (depend on ports only)

## Domain Layer

Responsible for:

- business rules
- calculations (parameter substitution, assertion evaluation, runner sequencing)
- state transitions and invariants
- data models and serialization
- port interface definitions

Must not contain:

- Qt imports
- I/O
- concrete adapters

## Infrastructure Layer

Responsible for:

- JSON persistence (`~/.angryrest/`)
- HTTP transport (httpx)
- script execution (`exec()` sandbox)
- GraphQL / OpenAPI introspection
- logging

Must not contain:

- business rules
- UI state
- QML/QWidget references (QtCore background wrappers are allowed)

---

# Dependency Injection

- Constructor injection only. No service locator, no global singletons, no mutable
  module-level state.
- Every application service receives its ports as constructor arguments.
- View models receive their application services as constructor arguments.
- The composition root (`app.py` / `ui/bootstrap.py`) builds the object graph:
  `infrastructure → application services → view models → QML context`.
- Every port must have a test double (fake/in-memory) used by unit and integration
  tests; production adapters are never instantiated in tests except for storage
  (via `tmp_path`) and mocked-httpx HTTP tests.

---

# Concurrency & Threading

Long-running work runs off the GUI thread. Use the `QThread` worker-object pattern:

- A worker `QObject` (no GUI) performs the blocking call and emits a result signal
  named `result_ready` (never `finished`, which shadows `QThread.finished`).
- The view model connects `QThread.finished` to:
  1. a slot that sets the Python worker/thread reference to `None` **before**
     `deleteLater`, then
  2. `deleteLater` for C++ cleanup.
- All worker signals are disconnected in teardown before destruction.
- Results cross the thread boundary via queued signal connections into the view
  model, which updates its properties on the GUI thread.

Rules:

- Application services must be thread-safe and must not touch Qt GUI objects
  directly; they communicate only through their own return values and ports.
- Cancellation is cooperative (a flag checked between operations); in-flight work
  is never hard-killed.
- No `QWidget`/QML object may be created or mutated from a worker thread.

---

# Domain Models & Ports

## Models

`Collection`, `RequestDef`, `KeyValue`, `Environment`, `ScriptResult`, `Assertion`,
`HttpExchange` (request/response abstraction). Pure dataclasses; serialization via
`to_dict()` / `from_dict()`; no Qt, no I/O.

## Ports (Protocols defined in `domain/ports/`)

| Port | Contract | Adapter (infrastructure) |
|------|----------|--------------------------|
| `StoragePort` | load/save collections, environments, ordering | `JsonStorageAdapter` |
| `HttpPort` | execute an HTTP exchange, return a response | `HttpxAdapter` |
| `ScriptPort` | run pre/post scripts, return `ScriptResult` | `ExecScriptAdapter` |
| `SchemaPort` | GraphQL introspection, OpenAPI discovery | `IntrospectionAdapter` |
| `LoggerPort` | emit structured log records | in-app log adapter |

## Domain Services (pure)

| Service | Responsibility |
|---------|----------------|
| `EnvironmentResolver` | `<paramName>` substitution against an environment |
| `RequestAssembler` | build a concrete request from `RequestDef` + environment |
| `AssertionEvaluator` | apply `assert_*` rules, accumulate pass/fail results |
| `RunnerPolicy` | collection-run sequencing rules (break-on-failure, env carry-forward, pass/fail decision) |

## Application Services (orchestration)

| Service | Flow |
|---------|------|
| `SendRequestService` | resolve env → run pre-script → HTTP → run post-script → persist env changes |
| `RunCollectionService` | iterate requests via `RunnerPolicy`, calling ports, streaming progress |
| `SchemaService` | introspect GraphQL / discover OpenAPI, cache per host |
| `EnvironmentService` | create/rename/delete/select environments, substitution invalidations |

---

# Feature-to-Layer Mapping

| Feature | Domain | Application | Infrastructure | UI (QML) |
|---------|--------|-------------|----------------|----------|
| Env substitution | `EnvironmentResolver` | expose resolved state | — | render highlighting, edit vars |
| Send request | `RequestAssembler` | `SendRequestService` (worker) | `HttpxAdapter` | Send button → slot |
| Scripting | `AssertionEvaluator`, `ScriptResult` | orchestrate pre/post | `ExecScriptAdapter` | script editors |
| Collection runner | `RunnerPolicy` | `RunCollectionService` (worker) | `HttpPort`/`ScriptPort` | runner dialog |
| GraphQL/OpenAPI | schema model + cache keys | `SchemaService` (worker) | `IntrospectionAdapter` | Fetch Schema button |
| Persistence | serialization models | trigger saves | `JsonStorageAdapter` | none (automatic) |
| Logs | log record model | route records | log adapter | log viewer |

---

# Forbidden Architectural Patterns

The following are forbidden:

- business logic in QML
- QML importing domain or infrastructure modules
- view models performing I/O directly
- domain importing any Qt module
- domain importing httpx / filesystem / `exec`
- application referencing concrete infrastructure classes
- global singletons and mutable module-level state (except the composition root)
- circular dependencies between layers
- long-running work on the GUI thread
- Qt widgets stored inside domain models
- accessing another object's protected/private attributes
- shadowing `QThread.finished` with a custom signal

---

# Testing Strategy

Regression-first: every feature and bug fix ships with automated tests.

## Testing Pyramid

### Unit Tests (`tests/unit/`)

Required for:

- domain services (substitution, assertion, runner policy)
- view models (QtCore-only, mocked services, `QCoreApplication`)
- infrastructure adapters (mocked `httpx.Client`, `tmp_path` storage)

No graphics environment required.

### Integration Tests (`tests/integration/`)

Required for UI behaviour. Use `pytest-qt` + `qtbot`:

- `QT_QPA_PLATFORM=offscreen` for headless execution
- load real `.qml` views against real view models wired to fake ports
- assert via `qtbot.waitSignal`, property reads, and widget/quick-item inspection

## Forbidden in tests

- network access in unit tests
- a graphics environment in unit tests
- time-dependent flaky tests
- untestable business logic

---

# Definition of Done

A task is complete only if:

- implementation is finished
- automated tests exist
- regression coverage exists
- architecture rules are respected (layer boundaries, DI, non-blocking)
- no business logic leaked into QML or infrastructure
- documentation is updated where applicable

---

# ADR Policy

Architectural changes require an Architecture Decision Record update. AI agents may
propose alternatives but may not introduce architectural changes without approval.
