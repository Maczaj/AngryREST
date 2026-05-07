# AngryREST

![App logo](.github/assets/angry_logotype_full.png)

> ✍️ *Introduction goes here.*

---

## Features

### Request Building
- **All HTTP methods** — GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS and more
- **Multiple body types** — raw JSON, URL-encoded / multipart form data, GraphQL queries with variables
- **Headers & query parameters** — key-value editor with per-row enable/disable toggles
- **`<paramName>` substitution** — all URLs, headers, query params, and body content support environment variable interpolation using angle-bracket syntax

### Environments
- **Named environments** — create as many environments as needed (dev, staging, prod …)
- **Active environment selector** — switch context in one click; all substitutions update immediately
- **Live parameter highlighting** — placeholders that resolve to a defined variable glow green; unresolved ones turn red, making missing configuration impossible to miss

### Scripting
- **Pre-request scripts** — run arbitrary Python before a request is sent; mutate `env` variables, generate auth tokens, compute signatures, and modify request metadata
- **Post-request scripts** — inspect the response and run assertions; failures are reported per-assertion in the UI and the log viewer
- **Built-in assertion helpers**: `assert_status()`, `assert_equals()`, `assert_true()`, `assert_contains()`
- **Standard library available in scripts**: `json`, `re`, `base64`, `hashlib`, `uuid`, `print`, `logging`

### GraphQL
- **First-class GraphQL support** — dedicated body type with a separate variables panel
- **Schema introspection** — AngryREST fetches the remote schema automatically and offers field/type autocomplete while you type
- **API key auto-detection** — before sending the introspection request, AngryREST scans the request's header list for any well-known authentication header (`Authorization`, `X-Api-Key`, `Api-Key`, `X-Auth-Token`, `X-Token`, `Token`, `X-Access-Token`) and forwards it automatically, so protected schemas are fetched without any extra configuration

### OpenAPI / Swagger
- **API key auto-detection** — same mechanism as GraphQL: any enabled authentication header already present on the request is forwarded automatically when probing for the spec
- **Auto-discovery** — AngryREST probes the following paths on the target host and caches the first spec it finds:
  `/openapi.json`, `/swagger.json`, `/api-docs`, `/api-docs.json`, `/v2/api-docs`, `/v3/api-docs`,
  `/swagger/v1/swagger.json`, `/api/openapi.json`, `/api/swagger.json`, `/api/v1/openapi.json`, `/api/v2/openapi.json`
- **Body autocomplete** — property names from the spec are offered as completions in the JSON body editor

### Collection Runner
- **Sequential execution** — run every request in a collection in order with a single click
- **Live progress** — each request shows pass / fail status in real time as the run proceeds
- **Env propagation** — changes made to environment variables by pre/post scripts carry forward to subsequent requests in the same run
- **Stop at any time** — abort a run without losing results already captured

### Persistence & Logs
- **Automatic saving** — collections and environments persist to `~/.angryrest/` as human-readable JSON; nothing is lost on close
- **In-app log viewer** — browse HTTP, script, and application logs colour-coded by severity (INFO / WARNING / ERROR); click any entry to read the full detail

### UI
- **Dark theme** throughout with a resizable splitter layout
- **Cross-platform** — Linux (X11 & Wayland), macOS, and Windows; WSL2 supported via WSLg or a third-party X server

---

## Scripting Reference

Scripts are Python snippets executed with `exec()` in a sandboxed namespace. They run synchronously on a background thread — never on the UI thread.

### Pre-request script

Runs **before** the HTTP request is sent. Use it to compute dynamic values and inject them into the environment, which is then used for `<param>` substitution.

**Available namespace**

| Name | Type | Description |
|------|------|-------------|
| `env` | `dict[str, str]` | Mutable copy of the active environment; changes persist for this request and carry forward in collection runs |
| `request` | `dict` | Read-only snapshot: `{"method": "POST", "url": "https://..."}` |
| `json` | module | `json` stdlib module |
| `re` | module | `re` stdlib module |
| `base64` | module | `base64` stdlib module |
| `hashlib` | module | `hashlib` stdlib module |
| `uuid` | module | `uuid` stdlib module |
| `print` | callable | Writes to the script output panel |
| `log` / `logging` | logger / module | Writes to the in-app log viewer |

**Example — generate a Bearer token via HMAC-SHA256**

```python
import hmac

secret = env["API_SECRET"].encode()
timestamp = str(int(__import__("time").time()))
signature = hmac.new(secret, timestamp.encode(), hashlib.sha256).hexdigest()

env["AUTH_TOKEN"] = f"{timestamp}.{signature}"
print(f"Token generated for ts={timestamp}")
```

**Example — inject a UUID correlation ID**

```python
env["CORRELATION_ID"] = str(uuid.uuid4())
```

**Example — encode Basic Auth credentials**

```python
credentials = f'{env["USERNAME"]}:{env["PASSWORD"]}'
env["BASIC_AUTH"] = base64.b64encode(credentials.encode()).decode()
```

**Example — build a paginated URL offset**

```python
page = int(env.get("PAGE", "0"))
env["OFFSET"] = str(page * int(env.get("PAGE_SIZE", "20")))
```

---

### Post-request script

Runs **after** the response arrives. Use it to assert expectations and extract values for subsequent requests.

**Additional namespace entries (everything from pre-script plus)**

| Name | Type | Description |
|------|------|-------------|
| `response` | `ResponseWrapper` | The HTTP response (see below) |
| `assert_status(code, msg="")` | callable | Fails if `response.status_code != code` |
| `assert_equals(actual, expected, msg="")` | callable | Fails if `actual != expected` |
| `assert_true(condition, msg="")` | callable | Fails if `condition` is falsy |
| `assert_contains(text, substring, msg="")` | callable | Fails if `substring not in text` |

**`ResponseWrapper` API**

| Attribute / Method | Description |
|--------------------|-------------|
| `response.status_code` | Integer HTTP status code |
| `response.headers` | `dict[str, str]` of response headers |
| `response.elapsed_ms` | Round-trip time in milliseconds |
| `response.size_bytes` | Response body size in bytes |
| `response.text()` | Body decoded as UTF-8 string |
| `response.json()` | Body parsed as JSON (raises on invalid JSON) |

**Example — assert status and extract a token**

```python
assert_status(200, "Login must succeed")

body = response.json()
env["ACCESS_TOKEN"] = body["data"]["accessToken"]
env["REFRESH_TOKEN"] = body["data"]["refreshToken"]
print(f"Logged in, token expires in {body['data']['expiresIn']}s")
```

**Example — validate response shape**

```python
assert_status(201)

body = response.json()
assert_true("id" in body, "Response must contain an id field")
assert_true(isinstance(body["id"], str), "id must be a string")

env["CREATED_ID"] = body["id"]
```

**Example — regex extraction**

```python
assert_status(200)

location = response.headers.get("Location", "")
match = re.search(r"/orders/(\d+)", location)
assert_true(bool(match), "Location header must contain order ID")

env["ORDER_ID"] = match.group(1)
```

**Example — latency budget assertion**

```python
assert_status(200)
assert_true(response.elapsed_ms < 500, f"Response too slow: {response.elapsed_ms:.0f} ms")
```

**Example — multi-step collection login → use token → assert logout**

*Request 1 — POST /auth/login (post-script)*
```python
assert_status(200)
env["TOKEN"] = response.json()["token"]
```

*Request 2 — GET /profile (pre-script, uses `<TOKEN>` in Authorization header)*
```python
# Nothing needed — env["TOKEN"] set by request 1 carries forward automatically
```

*Request 3 — DELETE /auth/logout (post-script)*
```python
assert_status(204, "Logout must return 204 No Content")
```

---

## Setup

### Standard (Linux / macOS / Windows)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows PowerShell

pip install -e .[dev]
```

### WSL2 (Windows Subsystem for Linux)

Running a Qt GUI from WSL2 requires display forwarding.

#### Option A — WSLg (Windows 11, recommended)

WSLg ships with Windows 11 (build 22000+). No extra configuration needed — GUI windows appear automatically.

```bash
python3 -c "from PySide6.QtWidgets import QApplication; print('Qt OK')"
```

#### Option B — X server (Windows 10)

1. Install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) or [X410](https://x410.dev/) on Windows.
2. Launch VcXsrv with **Disable access control** checked.
3. Set the display variable inside WSL2:

```bash
export DISPLAY=$(ip route list default | awk '{print $3}'):0.0
# Add to ~/.bashrc to persist across sessions
```

#### Common WSL2 issues

| Problem | Fix |
|---------|-----|
| `Could not connect to display` | Ensure your X server is running, or that WSLg is enabled |
| `qt.qpa.xcb: could not connect to display` | Check `echo $DISPLAY` is set |
| Missing system libraries | `sudo apt install libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-keysyms1 libegl1` |
| Broken fonts / scaling | `export QT_SCALE_FACTOR=1` |
| Dropdowns require double-click | WSLg/Weston limitation — click the item, then click outside to dismiss. Does not affect native Linux, Windows, or macOS. |

---

## Running Locally

```bash
# Activate the virtual environment first
source .venv/bin/activate

# Run via module
python -m angryrest

# Or via the installed entry point
angryrest
```

With [poethepoet](https://github.com/nat-n/poethepoet) (`pip install poethepoet`):

```bash
poe run
```

---

## Running Tests

```bash
pytest                      # all tests
pytest -v                   # verbose output
pytest -x -q                # stop on first failure, quiet
```

With poe:

```bash
poe test          # verbose
poe test-fast     # stop on first failure
```

---

## Building a Standalone Executable

AngryREST can be packaged into a single-file executable with [PyInstaller](https://pyinstaller.org/).

```bash
# Install PyInstaller
pip install pyinstaller

# Build using the spec file
pyinstaller angryrest.spec
```

The output lands in `dist/`. With poe:

```bash
poe build
```

---

## Requirements

- Python 3.11+
- A graphical display (X11, Wayland, or Windows/macOS native)
