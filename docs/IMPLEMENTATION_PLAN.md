# IMPLEMENTATION_PLAN.md

Feature-by-feature implementation plan. Each milestone delivers visible, testable behavior.
Build QML + MVVM per `ARCHITECTURE.md`. Reference old MVP code in git history only — no copy-paste.

---

## Milestone 1: App shell + Collections + Windows build

**User verifies:** Launch the app, dark-themed 3-panel splitter, create/rename/delete collections, persist across restart. Run script → standalone `AngryREST.exe`.

1. Directory scaffolding: `domain/`, `application/`, `infrastructure/`, `ui/qml/`, `tests/unit/`, `tests/integration/`
2. Domain models: `Collection`, `KeyValue` — dataclasses, `to_dict()` / `from_dict()`, unit tests
3. `StoragePort` protocol + `JsonStorageAdapter` — read/write `~/.angryrest/collections/`, unit tests
4. `CollectionsViewModel` (QObject) — `QAbstractListModel`, CRUD slots
5. QML shell: `MainWindow.qml` 3-panel splitter, `CollectionsPanel.qml` tree, dark theme
6. Composition root: `app.py` + `bootstrap.py` — wire adapters → view models → QML
7. Windows build: `angryrest.spec` (PyInstaller), `scripts/build-windows.bat`
8. Linux build: `scripts/build-linux.sh`
9. Unit + integration tests

---

## Milestone 2: Request builder

**User verifies:** Create requests in collections, edit method/URL/params/headers/body, persist changes.

1. `RequestDef` domain model — all fields, serialization, unit tests
2. Extended storage — save/load requests within collection files
3. `RequestViewModel` — properties for all request fields, dirty tracking
4. QML request panel: method selector, URL bar, tab bar (Params, Headers, Body, Pre-Script, Post-Script, Raw), KeyValue editors, body type selector + stacked editors
5. Empty state placeholder
6. Wire collections tree click → load request
7. Integration tests

---

## Milestone 3: Send request + Response display

**User verifies:** Enter URL → Send → see response status/headers/body. Core API testing loop works.

1. `HttpPort` protocol + `HttpxAdapter`, unit tests with mocked httpx
2. `SendRequestService` application service
3. `ResponseViewModel` — status, headers, body, timing, size, states
4. QML response panel: status bar, body tab, headers tab, loading/error/empty states
5. QThread `SendWorker` per AGENTS.md lifetime pattern
6. Wire Send button / Enter key → worker → response display
7. Integration tests

---

## Milestone 4: Environments + Variable substitution

**User verifies:** Create environments, `<param>` substitution with green/red highlighting.

1. `Environment` domain model, serialization, unit tests
2. Extended storage — `environments.json`
3. `EnvironmentResolver` domain service — extraction, substitution, undefined params, unit tests
4. `EnvironmentViewModel` — list, active selection, CRUD
5. QML toolbar env dropdown + Manage button
6. QML environment dialog — env list + variable table
7. Parameter highlighting in URL/headers/body
8. Wire substitution into `SendRequestService`
9. Integration tests

---

## Milestone 5: Scripting

**User verifies:** Pre/post Python scripts, assertion results in Script Output tab.

1. `ScriptPort` protocol + `ExecScriptAdapter`, unit tests
2. `ScriptResult` / `Assertion` models, `AssertionEvaluator`, unit tests
3. QML script editors — syntax highlighting, autocompletion
4. QML Script Output tab — pass/fail markers
5. Wire pre/post into `SendRequestService`
6. Integration tests

---

## Milestone 6: GraphQL + OpenAPI

**User verifies:** GraphQL editor with schema autocompletion, JSON editor with OpenAPI completions.

1. `SchemaPort` protocol + `IntrospectionAdapter`, unit tests
2. `SchemaService` application service — QThread worker, per-host cache
3. QML GraphQL body editor — split query/variables, Fetch Schema + Format, QCompleter popup
4. QML JSON body editor — Format button, OpenAPI property autocompletion
5. Integration tests

---

## Milestone 7: Collection Runner

**User verifies:** Run entire collection sequentially, progress bar, pass/fail per request.

1. `RunnerPolicy` domain service — break-on-failure, env carry-forward, pass/fail rules, unit tests
2. `RunCollectionService` application service — iterate via ports, cooperative stop
3. QML runner dialog — request list, progress, summary, log, Run/Stop/Close
4. QThread worker
5. Integration tests

---

## Milestone 8: Polish

**User verifies:** Raw preview, response caching, log viewer.

1. Raw request preview tab — live wire format with resolved variables
2. Response caching — per-request-ID in-memory, replay on selection switch
3. `LoggerPort` + `AppLogger` adapter — APP/HTTP/SCRIPTS categories
4. QML Logs dialog — entry list, detail pane, severity colors, status bar badge
5. Final empty/error/loading state polish
6. Integration tests

---

## Rules

- Every milestone updates relevant spec(s), writes tests, runs `poe test`
- `./scan-sonar.sh` after each milestone
- Feature branch + PR against `main` per AGENTS.md
- Subsequent milestones push to same PR branch