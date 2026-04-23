from __future__ import annotations

from typing import Any

import httpx
from PySide6.QtCore import QObject, QThread, Signal

from angryrest.services import app_logger as _app_logger
from angryrest.services.graphql_schema import host_from_url

_log = _app_logger.get_logger("openapi")

# ---------------------------------------------------------------------------
# Common paths where OpenAPI / Swagger specs are served
# ---------------------------------------------------------------------------
_PROBE_PATHS: list[str] = [
    "/openapi.json",
    "/swagger.json",
    "/api-docs",
    "/api-docs.json",
    "/v2/api-docs",
    "/v3/api-docs",
    "/swagger/v1/swagger.json",
    "/api/openapi.json",
    "/api/swagger.json",
    "/api/v1/openapi.json",
    "/api/v2/openapi.json",
]

# ---------------------------------------------------------------------------
# In-memory cache: host → raw spec dict
# ---------------------------------------------------------------------------
_schema_cache: dict[str, dict[str, Any]] = {}


def get_cached_schema(host: str) -> dict[str, Any] | None:
    """Return the cached OpenAPI spec for *host*, or ``None`` if not yet fetched."""
    return _schema_cache.get(host)


# ---------------------------------------------------------------------------
# Property extraction
# ---------------------------------------------------------------------------

def _extract_props(schema: Any, words: set[str]) -> None:
    """Recursively collect all property names from a JSON Schema object."""
    if not isinstance(schema, dict):
        return
    for prop_name, prop_schema in schema.get("properties", {}).items():
        words.add(prop_name)
        _extract_props(prop_schema, words)
    _extract_props(schema.get("items"), words)
    for key in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(key) or []:
            _extract_props(sub, words)


def extract_completions(spec: dict[str, Any]) -> list[str]:
    """Return a sorted de-duplicated list of property names from an OpenAPI spec."""
    words: set[str] = set()
    try:
        # OpenAPI v3: components.schemas
        for schema in spec.get("components", {}).get("schemas", {}).values():
            _extract_props(schema, words)
        # OpenAPI v2: definitions
        for schema in spec.get("definitions", {}).values():
            _extract_props(schema, words)
        # Path operations — body schemas
        for path_item in spec.get("paths", {}).values():
            if not isinstance(path_item, dict):
                continue
            for op in path_item.values():
                if not isinstance(op, dict):
                    continue
                # v3 requestBody
                for media in op.get("requestBody", {}).get("content", {}).values():
                    _extract_props(media.get("schema", {}), words)
                # v2 body parameters
                for param in op.get("parameters") or []:
                    if isinstance(param, dict) and param.get("in") == "body":
                        _extract_props(param.get("schema", {}), words)
    except Exception as exc:
        _log.warning("extract_completions: %s", exc)
    return sorted(words)


# ---------------------------------------------------------------------------
# Background fetcher thread
# ---------------------------------------------------------------------------

class OpenAPIFetcher(QThread):
    """Probes common OpenAPI/Swagger paths and caches the first valid spec found."""

    schema_ready = Signal(str, dict)  # host, spec
    fetch_error = Signal(str, str)    # host, error message

    def __init__(
        self,
        base_url: str,
        extra_headers: dict[str, str] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_url = base_url
        self._extra_headers: dict[str, str] = extra_headers or {}

    def run(self) -> None:
        host = host_from_url(self._base_url)
        _log.info("Probing OpenAPI/Swagger spec for %s", host)
        headers: dict[str, str] = {
            "Accept": "application/json",
            **self._extra_headers,
        }
        for path in _PROBE_PATHS:
            url = f"{host}{path}"
            try:
                resp = httpx.get(
                    url,
                    headers=headers,
                    timeout=10.0,
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    continue
                ct = resp.headers.get("content-type", "")
                if "json" not in ct and not resp.text.lstrip().startswith("{"):
                    continue
                spec: dict[str, Any] = resp.json()
                if not isinstance(spec, dict):
                    continue
                # Must look like a real spec
                if "paths" not in spec and "swagger" not in spec and "openapi" not in spec:
                    continue
                _schema_cache[host] = spec
                version = spec.get("openapi") or spec.get("swagger", "?")
                _log.info("OpenAPI %s spec found at %s", version, url)
                self.schema_ready.emit(host, spec)
                return
            except Exception:
                continue
        _log.error(
            "No OpenAPI/Swagger spec found for %s (probed %d paths)",
            host,
            len(_PROBE_PATHS),
        )
        self.fetch_error.emit(
            host,
            f"No OpenAPI/Swagger spec found at {host}.\n"
            f"Probed: {', '.join(_PROBE_PATHS)}",
        )
