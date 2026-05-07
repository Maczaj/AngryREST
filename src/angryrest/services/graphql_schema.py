from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx
from PySide6.QtCore import QObject, QThread, Signal

from angryrest.services import app_logger as _app_logger

_log = _app_logger.get_logger("graphql")

# ---------------------------------------------------------------------------
# Introspection query — fetches enough schema to build a completion list
# ---------------------------------------------------------------------------
_INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      name
      kind
      fields(includeDeprecated: false) {
        name
        type {
          name
          kind
          ofType {
            name
            kind
            ofType {
              name
              kind
            }
          }
        }
      }
      inputFields {
        name
        type {
          name
          kind
          ofType {
            name
            kind
            ofType {
              name
              kind
            }
          }
        }
      }
      enumValues(includeDeprecated: false) {
        name
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# In-memory cache: host (scheme + authority) → raw schema data dict
# ---------------------------------------------------------------------------
_schema_cache: dict[str, dict[str, Any]] = {}


def host_from_url(url: str) -> str:
    """Return the ``scheme://host:port`` part of *url*, or *url* on parse failure."""
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return url


def get_cached_schema(host: str) -> dict[str, Any] | None:
    """Return the cached schema for *host*, or ``None`` if not yet fetched."""
    return _schema_cache.get(host)


def extract_completions(schema: dict[str, Any]) -> list[str]:
    """Return a sorted de-duplicated list of field/value names from *schema*."""
    words: set[str] = set()
    try:
        types = schema.get("__schema", {}).get("types", [])
        for t in types:
            name = t.get("name", "")
            if name.startswith("__"):
                continue
            kind = t.get("kind", "")
            if kind in ("OBJECT", "INTERFACE", "INPUT_OBJECT"):
                for field in t.get("fields") or t.get("inputFields") or []:
                    words.add(field["name"])
            elif kind == "ENUM":
                for ev in t.get("enumValues") or []:
                    words.add(ev["name"])
    except Exception as exc:
        _log.warning("extract_completions: %s", exc)
    return sorted(words)


# ---------------------------------------------------------------------------
# Schema tree — maps each type to its fields and their return types
# ---------------------------------------------------------------------------

def _resolve_named_type(type_ref: dict[str, Any]) -> str:
    """Unwrap NON_NULL / LIST wrappers and return the named type's name."""
    while type_ref and type_ref.get("kind") in ("NON_NULL", "LIST"):
        type_ref = type_ref.get("ofType") or {}
    return type_ref.get("name") or ""


def build_schema_tree(schema: dict[str, Any]) -> dict[str, Any]:
    """Build a navigable type tree from introspection *schema* data.

    Returns a dict with keys:
    - ``query_type``: name of the root Query type (str | None)
    - ``mutation_type``: name of the root Mutation type (str | None)
    - ``subscription_type``: name of the root Subscription type (str | None)
    - ``type_fields``: dict[typename, dict[fieldname, return_typename]]
    """
    schema_data = schema.get("__schema", {})
    query_type: str | None = (schema_data.get("queryType") or {}).get("name")
    mutation_type: str | None = (schema_data.get("mutationType") or {}).get("name")
    subscription_type: str | None = (schema_data.get("subscriptionType") or {}).get("name")

    type_fields: dict[str, dict[str, str]] = {}

    for t in schema_data.get("types", []):
        name = t.get("name", "")
        if not name or name.startswith("__"):
            continue
        kind = t.get("kind", "")
        if kind not in ("OBJECT", "INTERFACE", "INPUT_OBJECT"):
            continue
        fields_list: list[dict[str, Any]] = t.get("fields") or t.get("inputFields") or []
        if not fields_list:
            continue
        entry: dict[str, str] = {}
        for field in fields_list:
            field_name: str = field.get("name", "")
            return_type = _resolve_named_type(field.get("type") or {})
            if field_name and return_type:
                entry[field_name] = return_type
        if entry:
            type_fields[name] = entry

    return {
        "query_type": query_type,
        "mutation_type": mutation_type,
        "subscription_type": subscription_type,
        "type_fields": type_fields,
    }


_OP_KEYS = ("query", "mutation", "subscription")
_OP_ROOT_MAP_KEYS = {"query", "mutation", "subscription"}


def get_completions_at_cursor(
    schema_tree: dict[str, Any],
    text: str,
    cursor_pos: int,
) -> list[str]:
    """Return field names valid at *cursor_pos* in *text* given *schema_tree*.

    Scans tokens while skipping argument lists, string literals, and comments to
    determine which GraphQL type the cursor is inside, then returns that type's
    field names.
    """
    type_fields: dict[str, dict[str, str]] = schema_tree.get("type_fields", {})
    query_type: str | None = schema_tree.get("query_type")
    mutation_type: str | None = schema_tree.get("mutation_type")
    subscription_type: str | None = schema_tree.get("subscription_type")

    _op_root = {
        "query": query_type,
        "mutation": mutation_type,
        "subscription": subscription_type,
    }

    text_before = text[:cursor_pos]
    type_stack: list[str | None] = []
    current_type: str | None = None

    # Two-slot sliding window of the last meaningful identifier tokens.
    prev2 = ""  # second-to-last identifier
    prev1 = ""  # last identifier
    after_colon = False  # True immediately after seeing `:` (alias separator)

    i = 0
    n = len(text_before)

    while i < n:
        ch = text_before[i]

        # --- Skip block strings ("""...""") ---
        if text_before[i : i + 3] == '"""':
            i += 3
            while i <= n - 3:
                if text_before[i : i + 3] == '"""':
                    i += 3
                    break
                i += 1
            else:
                i = n
            continue

        # --- Skip regular strings ---
        if ch in ('"', "'"):
            quote = ch
            i += 1
            while i < n:
                c = text_before[i]
                if c == "\\" and i + 1 < n:
                    i += 2
                elif c == quote:
                    i += 1
                    break
                else:
                    i += 1
            continue

        # --- Skip line comments ---
        if ch == "#":
            while i < n and text_before[i] != "\n":
                i += 1
            continue

        # --- Skip argument / variable-definition lists (parens depth-counted) ---
        # This also swallows any { } inside input-object literals in arguments.
        if ch == "(":
            depth = 1
            i += 1
            while i < n and depth > 0:
                c = text_before[i]
                # Handle strings inside args
                if text_before[i : i + 3] == '"""':
                    i += 3
                    while i <= n - 3:
                        if text_before[i : i + 3] == '"""':
                            i += 3
                            break
                        i += 1
                    else:
                        i = n
                    continue
                if c in ('"', "'"):
                    quote = c
                    i += 1
                    while i < n:
                        c2 = text_before[i]
                        if c2 == "\\" and i + 1 < n:
                            i += 2
                        elif c2 == quote:
                            i += 1
                            break
                        else:
                            i += 1
                    continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                i += 1
            # prev1 still holds the field/operation name before the arg list — keep it
            continue

        # --- Skip directives (@name; the following arg list is handled above) ---
        if ch == "@":
            i += 1
            while i < n and (text_before[i].isalnum() or text_before[i] == "_"):
                i += 1
            continue

        # --- Alias separator `:` ---
        if ch == ":":
            after_colon = True
            i += 1
            continue

        # --- Identifier ---
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (text_before[j].isalnum() or text_before[j] == "_"):
                j += 1
            ident = text_before[i:j]
            i = j
            if after_colon:
                # Identifier right after `:` is the real field name (alias target).
                # Use a sentinel for prev2 to prevent false operation-keyword hits.
                prev2 = "_ALIAS_"
                prev1 = ident
                after_colon = False
            else:
                prev2 = prev1
                prev1 = ident
            continue

        # --- Selection-set open ---
        if ch == "{":
            type_stack.append(current_type)
            if not prev1:
                # Shorthand anonymous query: `{ ... }`
                current_type = query_type
            elif prev1 in _OP_ROOT_MAP_KEYS:
                # `query {` / `mutation {` / `subscription {`
                current_type = _op_root[prev1]
            elif prev2 in _OP_ROOT_MAP_KEYS:
                # `query OperationName {` / `mutation OperationName(...) {`
                current_type = _op_root[prev2]
            elif prev2 == "on":
                # `... on TypeName {` or `fragment Foo on TypeName {`
                current_type = prev1 if prev1 in type_fields else None
            else:
                # Regular field selection set
                if current_type and current_type in type_fields:
                    current_type = type_fields[current_type].get(prev1)
                else:
                    current_type = None
            prev2 = ""
            prev1 = ""
            after_colon = False
            i += 1
            continue

        # --- Selection-set close ---
        if ch == "}":
            if type_stack:
                current_type = type_stack.pop()
            prev2 = ""
            prev1 = ""
            after_colon = False
            i += 1
            continue

        # Other characters (whitespace, commas, `!`, `$`, `[`, `]`, `&`, …)
        i += 1

    # Return completions for the resolved type, with progressive fallbacks.
    if current_type and current_type in type_fields:
        return sorted(type_fields[current_type].keys())
    if query_type and query_type in type_fields:
        return sorted(type_fields[query_type].keys())
    all_fields: set[str] = set()
    for fields in type_fields.values():
        all_fields.update(fields.keys())
    return sorted(all_fields)


# ---------------------------------------------------------------------------
# Well-known authentication / API-key header names (lower-cased for matching)
# ---------------------------------------------------------------------------
AUTH_HEADER_NAMES: frozenset[str] = frozenset({
    "authorization",
    "x-api-key",
    "api-key",
    "x-auth-token",
    "x-token",
    "token",
    "x-access-token",
})


# ---------------------------------------------------------------------------
# Background fetcher thread
# ---------------------------------------------------------------------------

class SchemaFetcher(QThread):
    """Fetches the GraphQL introspection schema from *url* in a background thread."""

    schema_ready = Signal(str, dict)   # host, schema data
    fetch_error = Signal(str, str)     # host, error message

    def __init__(
        self,
        url: str,
        extra_headers: dict[str, str] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self._extra_headers: dict[str, str] = extra_headers or {}

    def run(self) -> None:
        host = host_from_url(self._url)
        _log.info("Fetching GraphQL schema from %s", self._url)
        try:
            headers: dict[str, str] = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                **self._extra_headers,
            }
            resp = httpx.post(
                self._url,
                content=json.dumps({"query": _INTROSPECTION_QUERY}).encode(),
                headers=headers,
                timeout=15.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            payload = resp.json()
            if "errors" in payload and "data" not in payload:
                raise ValueError(payload["errors"][0].get("message", "GraphQL error"))
            data: dict[str, Any] = payload.get("data", {})
            _schema_cache[host] = data
            _log.info("Schema cached for %s (%d types)", host, len(
                data.get("__schema", {}).get("types", [])
            ))
            self.schema_ready.emit(host, data)
        except Exception as exc:
            _log.error("Schema fetch failed for %s: %s", host, exc)
            self.fetch_error.emit(host, str(exc))
