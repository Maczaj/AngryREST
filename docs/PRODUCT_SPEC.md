# PRODUCT_SPEC.md

# AngryREST

## Desktop REST / GraphQL Client

## Product Vision

A cross-platform desktop application for manual HTTP API testing and exploration. A Postman-like tool focused on REST and GraphQL workflows, scripting, environments, and collection-running — all running locally with zero cloud dependency.

The application is an offline-first local tool. There is no backend, no account, no sync.

---

# Product Goals

## Primary Goals

* Build, edit, and send arbitrary HTTP requests with full control over method, URL, headers, query params, and body
* Support multiple body content types: raw JSON, URL-encoded forms, multipart form data (with file uploads), and first-class GraphQL queries with variables
* Named, switchable environments for managing variable sets (dev / staging / prod)
* Pre-request and post-request scripting (Python) for dynamic token generation, assertion validation, and response extraction
* Sequential collection execution (runner) with pass/fail reporting
* Local JSON persistence — collections and environments saved to disk automatically
* Dark theme, cross-platform desktop UI (Linux / macOS / Windows)

## Non-Goals

* Cloud sync or remote storage of any kind
* User accounts, login, or auth
* Collaboration, sharing, or team features
* Request history / versioning
* Proxy or intercepting proxy
* WebSocket / gRPC / Socket.IO support
* API documentation generation
* Mock server
* Performance / load testing

---

# User Types

## Single Local User

There is one user type: a local developer using the application on their own machine. No login, no accounts, no multi-tenancy. All data lives in `~/.angryrest/`.

---

# First Launch

1. User opens application.
2. Main window appears with an empty collections panel.
3. User creates a collection, then creates requests within it.
4. No onboarding wizard, no welcome screen. The empty state shows "Select a request from the collection panel" placeholder text.

---

# Core Concepts

## Collection

A named group of requests. Collections contain an ordered list of request definitions. Collections are persisted as individual JSON files under `~/.angryrest/collections/<uuid>.json` with an `_order.json` file tracking the display order.

**Actions:**
* Create, rename, delete a collection
* Add requests to a collection
* Drag-and-drop reorder collections and requests
* Duplicate a request
* Run entire collection (sequential execution of all requests)

## Request

A single HTTP request definition. Each request stores:
* Name
* HTTP method (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, or custom)
* URL
* Query parameters (key-value list with per-row enable/disable toggles)
* Headers (key-value list with per-row enable/disable toggles)
* Body type selector: None, Form, JSON, GraphQL, Multipart
* Body content (depending on type)
* Pre-request script (Python, optional)
* Post-request script (Python, optional)

Body types:
- **None** — no body sent
- **Form** — URL-encoded form fields (key-value editor)
- **JSON** — raw JSON text editor with Format button and OpenAPI schema autocompletion
- **GraphQL** — query editor with variables panel, Format button, and schema introspection autocompletion
- **Multipart** — text fields (key-value) plus file fields (field name + file path with Browse button)

## KeyValue Pair

Fundamental data structure used for headers, query params, form fields, and multipart fields. Each pair has:
* Key (string)
* Value (string, supports `<param>` substitution)
* Enabled flag (boolean) — disabled rows are excluded from the request

## Environment

A named set of string variables (`key: value` pairs). Users create environments to represent different contexts (dev, staging, prod).

**Actions:**
* Create, rename, delete environments
* Add, edit, remove variables
* Select an active environment from the toolbar dropdown ("No Environment" is the default)
* Variables are referenced in URLs, headers, query params, and body content using `<paramName>` angle-bracket syntax

---

# Feature: Environment Variable Substitution

Anywhere a string value appears in the request definition (URL, header key/value, query param key/value, body content, form field value), the user may embed `<paramName>` placeholders.

At send time, the active environment's variables are substituted inline. Unmatched placeholders remain as-is (no error thrown).

**Parameter highlighting:**
* In the URL bar, query param values, header values, and body editors, `<paramName>` tokens are visually highlighted:
  * Green background if the parameter exists in the active environment
  * Red background if the parameter is not defined
* Switching the active environment triggers immediate re-highlighting everywhere
* Hovering over a highlighted parameter shows a tooltip: `paramName = value` or `paramName (not defined)`

---

# Feature: Scripting

Scripts are Python snippets executed via `exec()` in a sandboxed namespace. They run synchronously on a background thread (never blocking the UI).

## Pre-request Script

Runs **before** the HTTP request is sent. Purpose: compute dynamic values and inject them into the environment.

**Available namespace:**

| Name | Type | Description |
|------|------|-------------|
| `env` | `dict[str, str]` | Mutable copy of the active environment; changes persist for this request and carry forward in collection runs |
| `request` | `dict` | Read-only snapshot: `{"method": "POST", "url": "https://..."}`' |
| `json` | module | `json` stdlib module |
| `re` | module | `re` stdlib module |
| `base64` | module | `base64` stdlib module |
| `hashlib` | module | `hashlib` stdlib module |
| `uuid` | module | `uuid` stdlib module |
| `print` | callable | Writes to the script output panel |
| `log` / `logging` | logger / module | Writes to the in-app log viewer |

If the pre-script throws an exception, the request is aborted and an error is displayed in the response panel.

## Post-request Script

Runs **after** the HTTP response arrives. Purpose: assert expectations and extract values for subsequent requests.

**Additional namespace entries (everything from pre-script plus):**

| Name | Type | Description |
|------|------|-------------|
| `response` | `ResponseWrapper` | The HTTP response |
| `assert_status(code, msg="")` | callable | Fails if `response.status_code != code` |
| `assert_equals(actual, expected, msg="")` | callable | Fails if `actual != expected` |
| `assert_true(condition, msg="")` | callable | Fails if `condition` is falsy |
| `assert_contains(text, substring, msg="")` | callable | Fails if `substring not in text` |

**`ResponseWrapper` API:**

| Attribute / Method | Description |
|--------------------|-------------|
| `response.status_code` | Integer HTTP status code |
| `response.headers` | `dict[str, str]` of response headers |
| `response.elapsed_ms` | Roundtrip time in milliseconds |
| `response.size_bytes` | Response body size in bytes |
| `response.text()` | Body decoded as UTF-8 string |
| `response.json()` | Body parsed as JSON (raises on invalid JSON) |

Assertion failures raise `AssertionError`. Each assertion (pass or fail) appears in the Script Output tab with ✅ PASS or ❌ FAIL markers. The post-script result is marked as failed if any assertion fails.

The Script Output tab in the response panel shows:
* Pre-script output (if any)
* Post-script output (if any)
* Assertion results (pass/fail per assertion)

---

# Feature: GraphQL Support

Dedicated body type for GraphQL. When GraphQL is selected:

* A split panel shows the query editor on top and a variables (JSON) editor on bottom
* A "Fetch Schema" button triggers background introspection against the URL in the request's URL field
* The introspection request automatically forwards any enabled authentication header (`Authorization`, `X-Api-Key`, `Api-Key`, `X-Auth-Token`, `X-Token`, `Token`, `X-Access-Token`) found in the request's header list
* After fetching, the schema is cached in memory per host and used for context-aware field/type autocompletion
* A "Format" button pretty-prints the GraphQL query using the `graphql-core` library

**Autocompletion behavior:**
* Ctrl+Space triggers manual completion
* Typing 2+ identifier characters triggers automatic completion
* Completions are context-aware: inside a field selection, only fields of the parent type are offered; at the top level of a query/mutation, the root operation fields are offered
* Completions use a `QCompleter` popup that inserts the full field name

**GraphQL variables:**
* Written as JSON in the Variables text editor
* At send time, if Content-Type is `application/json` the request body is `{"query": "...", "variables": {...}}`; if Content-TType is `application/graphql` the raw query is sent

---

# Feature: OpenAPI / Swagger Support

When the JSON body type is selected:
* A "Fetch Schema" button triggers background OpenAPI spec discovery against the URL in the request's URL field
* The authentication header forwarding works the same as GraphQL schema fetching
* The app probes the following paths on the target host and caches the first spec found:
  `/openapi.json`, `/swagger.json`, `/api-docs`, `/api-docs.json`, `/v2/api-docs`, `/v3/api-docs`,`/swagger/v1/swagger.json`, `/api/openapi.json`, `/api/swagger.json`, `/api/v1/openapi.json`, `/api/v2/openapi.json`
* After fetching, property names from the spec are offered as JSON body autocompletions

---

# Feature: Collection Runner

Runs every request in a collection sequentially.

**Dialog elements:**
* Request list showing each request with its method and name
* Row-level status icons: � (pending), 🔄 (running),✅ (pass), ❌ (fail)
* Progress bar tracking requests completed / total
* Summary label showing final pass/fail/skipped counts
* Log text area showing per-request results
* Run, Stop, Close buttons

**Execution rules:**
* Pre-script runs before each request
* If pre-script fails → request is marked failed, runner stops (breaks on first failure)
* If HTTP request errors (connection refused, timeout, etc.) → request marked failed, runner stops
* Post-script runs after each successful HTTP response
* If post-script assertion fails → request marked failed, runner stops
* If response status is 200–399 and no post-script exists → request marked passed
* If response status is 400+ and no post-script exists → request marked failed, runner stops
* Changes to `env` carry forward between requests in the run

**Stop button:**
* Sets a flag checked between requests; aborts the run
* Already-executing request completes; no in-flght cancellation

---

# Feature: Persistance

**Save triggers:**
* Any change to collections or environments (rename, add, delete, edit, reorder, change request fields)
* After every request send (environment variables may have been modified by scripts)
* On window close

**Storage layout:**
```
~/.angryrest/collections/<uuid>.json   # one file per collection
~/.angryrest/collections/_order.json   # ordered list of collection IDs
~/.angryrest/environments.json         # all environments
```

**File format:** Indented JSON, `ensure_ascii=False`. All data is readable JSON.

---

# Feature: Logs

An in-app log viewer accessible from a "Logs" button in the status bar.

**Log categories:**
* APP — application-level messages (`angryrest`)
* HTTP — request/response logging (`angryrest.http`)
* SCRIPTS — script execution results (`angryrest.scripts`)

**Log dialog:**
* Left pane: scrollable list of log entries showing timestamp, level, category, and first line of message
* Right pane: full detail view of selected entry
* Color-coded by severity: ERROR (red), WARNING (yellow), DEBUG (gray)
* "Clear Logs" button empties the in-memory log buffer

**Status bar button:**
* Shows "Logs" normally
* Shows "Logs (N)" when there are log entries
* Shows "Logs (N errors!)" when there are errors

---

# Feature: Raw Request Preview

A read-only "Raw" tab in the request panel shows the request as it would be sent on the wire — HTTP method, path, headers, and body. Updated live as the user edits the request.

Substitution placeholders are resolved against the active environment. Multipart file contents are not loaded for the preview; only field names and file paths are shown.

---

# Feature: Response Caching

When the user switches between requests in the collections panel without re-sending, the last response for each request is replayed from an in-memory cache (per request ID). This avoids unnecessary network calls when browsing requests.

---

# Success Criteria

Users can:
* Create and manage collections of HTTP requests
* Define requests with any HTTP method, headers, query params, and body type
* Use angle-bracket `<param>` substitution to parameterize any request field
* Define named environments with key-value variables and switch between them
* See live highlighting of resolved/unresolved parameters
* Write Python pre-request scripts to generate auth tokens and compute dynamic values
* Write Python post-request scripts with built-in assertion helpers
* See script output and assertion results in the response panel
* Send GraphQL queries with auto-discovery schema introspection and field autocompletion
* Use OpenAPI auto-discovery for JSON body property autocompletion
* Run entire collections sequentially with pass/fail progress reporting
* View HTTP, script, and application logs in a dedicated log viewer
* All data persists automatically as human-readable JSON on disk