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
      }
      inputFields {
        name
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
