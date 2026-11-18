# UX_SPEC.md

# UX Principles

The application is a developer tool for manual API testing. It is used at a desk, with keyboard and mouse, on a large screen.

Primary design goals:
* High information density — show all request-building controls in one view
* Keyboard-first efficiency — URL bar, tab navigation between panels, keyboard shortcuts for common actions
* Visual clarity — color-coded HTTP methods, status codes, log severity levels
* Dark theme — standard for developer tools, reduces eye strain
* Resizable panels — three-panel layout (collections | request | response) with draggable splitters

The request panel is the most important area — it's where users spend most of their time.

---

# Visual Design System

## Color Palette

Dark theme throughout. All colors are chosen for readability on `#1e1e1e` backgrounds.

### Background Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `bg-primary` | `#1e1e1e` | Main window background |
| `bg-secondary` | `#252526` | Sidebar (collections panel), toolbar, status bar |
| `bg-input` | `#2d2d2d` | Text inputs, text editors |

### Accent Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `accent-focus` | `#007acc` | Focused input border |
| `accent-selection` | `#264f78` | Text selection background |
| `accent-selected` | `#094771` | Selected tree item |

### HTTP Method Colors

Used for method badges in the collections tree and method selector button.

| Method | Hex |
|--------|-----|
| GET | `#4ec9b0` (teal) |
| POST | `#569cd6` (blue) |
| PUT | `#dcdcaa` (yellow) |
| PATCH | `#2d8e6e` (dark green) |
| DELETE | `#f44747` (red) |
| HEAD | `#5a5a5a` (dark gray) |
| OPTIONS | `#808080` (gray) |
| Custom | `#d4d4d4` (light gray) |

### Response Status Code Colors

| Range | Hex | Meaning |
|-------|-----|---------|
| 2xx | `#4ec9b0` (teal) | Success |
| 3xx | `#569cd6` (blue) | Redirect |
| 4xx | `#dcdcaa` (yellow) | Client error |
| 5xx | `#f44747` (red) | Server error |

### Environment Parameter Highlight Colors

| State | Foreground | Background |
|-------|------------|------------|
| Resolved (param exists in env) | `#4ec9b0` (teal) | `#1e3a2f` (dark green) |
| Unresolved (param not defined) | `#f44747` (red) | `#3a1e1e` (dark red) |

### Script Syntax Highlighting Colors

| Token Type | Hex |
|------------|-----|
| Keywords | `#569cd6` (blue) |
| Strings | `#ce9178` (orange-brown) |
| Comments | `#6a9955` (green) |
| Script builtins (env, response, assert_*) | `#dcdcaa` (yellow) |
| Numbers | `#b5cea8` (pale green) |

### Log Severity Colors

| Level | Hex |
|-------|-----|
| ERROR | `#f48771` (red) |
| WARNING | `#cca700` (yellow) |
| DEBUG | `#808080` (gray) |
| INFO | default text color |

### Text Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `text-primary` | `#d4d4d4` | Primary text |
| `text-secondary` | `#cccccc` | Tree items, button text |
| `text-muted` | `#666666` | Placeholder text, disabled state |
| `text-status-bar` | `#969696` | Status bar |

### Border Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `border-default` | `#3c3c3c` | Borders, splitter handles |
| `border-button` | `#4a4a4a` | Button borders |

### Button States

| State | Background | Text |
|-------|------------|------|
| Default | `#3c3c3c` | `#cccccc` |
| Hover | `#4a4a4a` | `#cccccc` |
| Pressed | `#555555` | `#cccccc` |
| Disabled | `#2d2d2d` | `#666666` |

### Tree Item States

| State | Background |
|-------|------------|
| Normal | `#252526` |
| Hover | `#2a3d52` |
| Selected | `#094771` |

## Typography

System UI fonts for UI chrome; monospace for code/text areas.

* **UI elements** (buttons, labels, tree): `"Segoe UI", "Ubuntu", "Cantarell", sans-serif` at 12px
* **Status bar**: 11px
* **Code editors, URL bar, response body, logs**: `"Consolas", "Courier New", monospace` at 10–11px

No custom fonts. System fonts provide native feel and support all scripts with zero bundle overhead.

## Border Radius

* Buttons, inputs: `3px`
* Tree items: `3px`

## Icons

No icon library used. Emoji characters serve as status indicators:
* ⬜ — pending (collection runner)
* 🔄 — running (collection runner)
* ✅ — pass (assertion, runner)
* ❌ — fail (assertion, runner)
* ⏳ — sending (response panel loading state)
* ▶ — run collection
* ⋮ — collection context menu trigger (vertical ellipsis)
* × — delete row button

---

# Layout

## Main Window

Three-panel resizable splitter layout:

```
┌──────────────────────────────────────────────────────────┐
│  Toolbar: [Environment: ▼ dropdown] [Manage...] [▶ Run] │
├──────────┬───────────────────────┬───────────────────────┤
│          │                       │                       │
│          │                       │   Response Panel      │
│          │    Request Panel      │   (Body | Headers |   │
│Collections│    (method + URL +   │    Script Output)     │
│  Panel   │     tabs: Params |    │                       │
│  (tree)  │     Headers | Body |  │                       │
│          │     Pre | Post | Raw) │                       │
│          │                       │                       │
├──────────┴───────────────────────┴───────────────────────┤
│  Status bar: AngryREST vX.Y.Z                     [Logs]│
└──────────────────────────────────────────────────────────┘
```

**Default sizes:** Collections panel 300px, Request Panel fills remaining width, Response Panel fills remaining height. Response panel split is roughly 500px request / 400px response.

**Responsiveness:** All three dividers are user-draggable. No minimum sizes enforced beyond what Qt provides.

**Window:** Default 1400×900, centered on the primary screen on first launch.

---

## Collections Panel (Left)

A tree widget showing collections as top-level items and their requests as children.

**Top toolbar:**
* "+ Collection" button — creates a new collection (prompts for name via dialog)
* "+ Request" button — creates a new request in the selected collection (or first collection if none selected)

**Tree display:**
* Collection items: bold text, the collection name. A "⋮" button appears on hover at the right edge of the row.
* Request items: color-coded HTTP method badge (bold, method color) followed by the request name (regular weight, `#d4d4d4`)

**Interaction:**
* Click a request → loads it into the request panel and replays the cached response (if any)
* Click a collection → selects it (for use with "Run Collection")
* Hover over collection → "⋮" appears
* Click "⋮" → context menu: Run Collection, Rename, Add Request, Delete
* Right-click request → context menu: Rename, Duplicate, Delete
* Right-click empty area → context menu: New Collection
* Right-click collection → context menu: Run Collection, Rename, Add Request, Delete
* Drag-and-drop supported for reordering (both collections and requests within a collection)

**Deletion confirmation:** Deleting a collection or request shows a Yes/No confirmation dialog.

---

## Request Panel (Top-Right)

### Request Name Row
* "Name:" label + text input for the request display name

### Method + URL + Send Row
* **Method selector:** A push-button styled to show the current method in its color. Clicking opens a dropdown menu of HTTP methods (GET through OPTIONS) plus a "Custom..." option. Custom triggers an input dialog for any arbitrary method string. Fixed width 120px.
* **URL input:** A single-line monospace text input with `<param>` highlighting. Accepts any URL. Pressing Enter sends the request.
* **Send button:** Styled button, 80px wide. Triggers the request. Disabled while a request is in flight.

### Tab Bar (below URL row)

Six tabs:

1. **Query Params** — KeyValue editor (checkbox + key input + value input + delete button per row, "+ Add" button below)
2. **Headers** — Same KeyValue editor layout
3. **Body** — Body type dropdown selector + stacked content panel (see below)
4. **Pre-Script** — Monospace code editor with Python syntax highlighting and autocompletion for script builtins
5. **Post-Script** — Same code editor
6. **Raw** — Read-only monospace text showing the full HTTP request as it would be sent on the wire

### Body Editor (Tab 3)

**Body type selector:** Dropdown with options: None, Form, JSON, GraphQL, Multipart

**None:** Centered gray text: "This request has no body"

**Form:** KeyValue editor (same layout as Headers/Query Params)

**JSON:** 
* Toolbar: "Fetch Schema" button (triggers OpenAPI discovery) + "Format" button (pretty-prints the JSON)
* Text editor: Monospace editor with `<param>` highlighting and JSON property name autocompletion (powered by fetched OpenAPI schema)

**GraphQL:**
* Vertical splitter: Query editor on top, Variables editor on bottom
* Query toolbar: "Fetch Schema" button (triggers GraphQL introspection) + "Format" button (pretty-prints using graphql-core)
* Variables editor: Monospace text input, placeholder `{}`, max height 120px
* Query editor: Context-aware field completion via Ctrl+Space or auto-trigger after 2+ characters

**Multipart:**
* Vertical splitter: Text fields on top (KeyValue editor), File fields on bottom
* File fields table: checkbox + field name input + file path (read-only) + "…" browse button per row

### Script Editors (Tabs 4, 5)
* Monospace editor with Python-aware syntax highlighting (keywords, strings, comments, numbers, script builtins)
* Autocompletion popup for script namespace names (`env`, `request`, `response`, `assert_status`, `assert_equals`, `assert_true`, `assert_contains`, `json`, `re`, `base64`, `hashlib`, `uuid`, `print`)
* Placeholder text hints at available namespace
* Tab key inserts 4 spaces

### Raw Tab (Tab 6)
* Read-only preview built by resolving environment variables and constructing the HTTP request via httpx's `Client.build_request()`
* Shows: `METHOD /path HTTP/1.1`, headers, blank line, body
* For multipart: summarized view showing text and file fields

### Empty State
When no request is selected, the entire request panel shows centered gray placeholder text: "Select a request from the collection panel". All editing controls are hidden.

---

## Response Panel (Bottom-Right)

### Status Bar (horizontal row)
* **Status label:** Bold, colored by status code range. Shows `200 OK`, `404 Not Found`, etc. During loading: "⏳ Sending..." in yellow.
* **Time label:** Gray, shows `123.4 ms` or hidden during loading
* **Size label:** Gray, shows `1.2 KB` or hidden during loading

### Tab Bar

1. **Body** — Monospace read-only text. JSON responses are auto-detected (via Content-Type) and pretty-printed with 2-space indentation. The Pretty-Print button is displayed at the top of the Body tab when the response is JSON, toggling between raw and formatted modes.
2. **Headers** — Two-column table (Header | Value), sorted as-received. Stretch-to-fit columns. Read-only.
3. **Script Output** — Monospace read-only text showing structured output:
   * `=== Pre-Script Output ===` section
   * `=== Post-Script Output ===` section
   * `=== Assertions ===` section with `✅ PASS` / `❌ FAIL` per assertion
   * Tab title shows entry count: "Script Output (5)"

### Error Display
When a request fails (connection error, timeout, DNS, SSL, pre-script error):
* The body/headers/script tabs are hidden
* An error widget is shown: icon label (🔌 CONNECTION ERROR / ⏱ TIMEOUT / 🌐 DNS ERROR / 🔒 SSL ERROR / ⚠ ERROR) + descriptive message text

### Empty State
When no response has been received: centered gray placeholder "Send a request to see the response"

### Loading State
"⏳ Sending..." status text, tabs and error widget hidden

---

## Toolbar

Horizontal toolbar at the top of the window. Non-movable.

* "Environment:" label
* Environment dropdown — lists all environments plus "No Environment" at top
* "Manage..." button — opens the Environment Management dialog
* Separator
* "▶ Run Collection" button — runs the currently selected collection (or first collection if none selected)

---

## Status Bar

Horizontal bar at the bottom.
* Left: "AngryREST vX.Y.Z" version label (displays installed package version or "dev")
* Right: "Logs" button — flat style, shows "Logs (N errors!)" when errors exist, "Logs (N)" when entries exist, "Logs" when empty

---

# Dialogs

## Environment Management Dialog

Title: "Manage Environments"
Minimum size: 700×500

**Layout:** Horizontal splitter
* **Left pane (200px):** Environment list + toolbar (New, Rename, Delete buttons)
* **Right pane (500px):** Variables table for selected environment + toolbar (Add Variable, Remove Selected buttons)
* **Bottom:** Close button

**Variables table:** Two-column editable table (Key | Value), stretch-to-fit columns. Cell changes trigger immediate save signal.

**Behavior:** Selecting an environment in the list populates the variables table. Adding/editing/removing variables updates the environment's data in-place.

---

## Logs Dialog

Title: "Logs"
Default size: 860×520

**Layout:** Horizontal splitter
* **Left pane (290px):** Scrollable list of log entries. Each entry: `[HH:MM:SS] LEVEL    CATEGORY    first line of message`, color-coded by severity.
* **Right pane (570px):** Read-only monospace text showing full details of selected entry: timestamp with milliseconds, level, category, logger name, full message body.

**Bottom bar:** "Clear Logs" button (left) + "Close" button (right)

**Behavior:** Most recent entry auto-selected on open. Clearing logs empties both the list and detail view.

---

## Collection Runner Dialog

Title: "Run Collection: {collection name}"
Minimum size: 600×400

**Layout (vertical):**
* Request list — shows each request with status icon (⬜/🔄/✅/❌), method badge, name, and result summary after execution
* Progress bar — fills as requests complete
* Summary label — bold, shows final "Done: N passed, M failed, K skipped out of T"
* Log area — monospace read-only, max height 120px, shows per-request progress messages
* Buttons: Run, Stop (disabled until running), Close

**Behavior:** Run starts execution, Stop aborts after current request completes. Close closes the dialog (stops worker thread if running).

---

# User Flows

## Create and Send a Request

1. Click "+ Collection" to create a collection (e.g., "My API")
2. Click "+ Request" to add a request (e.g., "Get Users")
3. Request loads in the request panel
4. Set method (dropdown), enter URL, add headers/params as needed
5. Click "Send" or press Enter in the URL bar
6. Response appears in the response panel: status code (colored), timing, size, body

## Use Environments

1. Click "Manage..." in the toolbar
2. Create an environment (e.g., "Production") and add variables (`BASE_URL`, `API_KEY`)
3. Close dialog, select "Production" from the toolbar dropdown
4. Use `<BASE_URL>` in request URLs — placeholder appears highlighted green
5. Switch environment via dropdown — all placeholders re-highlight immediately

## Write a Pre-request Script

1. In the request panel, switch to the "Pre-Script" tab
2. Write Python to compute a value and store it in `env`:
   ```python
   env["AUTH_TOKEN"] = "Bearer " + hashlib.sha256(env["SECRET"].encode()).hexdigest()
   ```
3. Use `<AUTH_TOKEN>` in a header value
4. On send, the script runs first, sets the env var, then the header is substituted

## Write a Post-request Script

1. Switch to the "Post-Script" tab
2. Write assertions:
   ```python
   assert_status(200)
   body = response.json()
   assert_true(len(body["data"]) > 0, "Response must contain data")
   env["FIRST_ID"] = body["data"][0]["id"]
   ```
3. On send, after the response arrives, the script runs. Assertions appear in the Script Output tab.

## Run a Collection

1. Select a collection in the tree
2. Click "▶ Run Collection" in the toolbar (or right-click collection → Run)
3. Collection Runner dialog opens
4. Click "Run"
5. Each request executes in order with progress shown. Failures stop the run.
6. Review pass/fail summary

## Use GraphQL

1. Set URL to a GraphQL endpoint (e.g., `https://api.example.com/graphql`)
2. In the Body tab, select "GraphQL"
3. Write a query in the Query editor
4. Click "Fetch Schema" to introspect the endpoint and enable field autocompletion
5. Add variables as JSON in the Variables editor
6. Click Send

---

# Keyboard Interaction

* Enter in URL input → sends the request
* Tab between key and value cells in KeyValue editors (grid navigation)
* Ctrl+Space in script editors → trigger autocompletion
* Ctrl+Space in GraphQL editor → trigger field autocompletion
* Escape → dismiss autocompletion popup

---

# Empty States

| Context | Display |
|---------|---------|
| No request selected | "Select a request from the collection panel" centered in request panel |
| No response received | "Send a request to see the response" centered in response panel |
| No collections | Empty tree |
| No logs | Empty log list and detail pane |

---

# Feedback States

| Context | Display |
|---------|---------|
| Request in flight | Send button disabled, "⏳ Sending..." in response status |
| Request sent (2xx) | Teal status code, timing, size, body/headers/script tabs visible |
| Request sent (4xx/5xx) | Yellow/red status code — body still shown |
| Connection error | Red error banner: 🔌 CONNECTION ERROR + message |
| Timeout | Red error banner: ⏱ TIMEOUT + message |
| Collection run in progress | Per-request status icons update in real time |

---

# Cross-Platform Notes

* Linux: X11 and Wayland supported. Wayland has a known QComboBox popup dismiss bug — a custom `WaylandComboBox` subclass forces `hidePopup()` after selection.
* WSL2: Supported via WSLg (Windows 11) or VcXsrv (Windows 10). WSLg/Weston has a dropdown double-click limitation noted in docs.
* macOS and Windows: Tested but no platform-specific code.
* Method selector uses a `QPushButton`-based custom widget instead of `QComboBox` to avoid cross-platform styling issues.