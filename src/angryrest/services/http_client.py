from __future__ import annotations

import re
import time
from dataclasses import dataclass

import httpx

from angryrest.services import app_logger as _app_logger

_log = _app_logger.get_logger("http")


@dataclass
class ResponseData:
    status_code: int
    reason_phrase: str
    headers: dict[str, str]
    body: bytes
    elapsed_ms: float
    size_bytes: int

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self):
        import json

        return json.loads(self.body)


@dataclass
class ErrorResult:
    error_type: str  # "connection", "timeout", "dns", "ssl", "other"
    message: str


def substitute_params(text: str, env_vars: dict[str, str]) -> str:
    def replacer(match: re.Match) -> str:
        param_name = match.group(1)
        return env_vars.get(param_name, match.group(0))

    return re.sub(r"<([^>]+)>", replacer, text)


class HttpClient:
    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
        body: str | bytes | None = None,
        body_type: str = "none",
        form_data: dict[str, str] | None = None,
        file_fields: list[tuple[str, str]] | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> ResponseData | ErrorResult:
        env = env_vars or {}

        resolved_url = substitute_params(url, env)
        resolved_headers = {}
        if headers:
            for k, v in headers.items():
                resolved_headers[substitute_params(k, env).title()] = substitute_params(v, env)

        resolved_params = {}
        if query_params:
            for k, v in query_params.items():
                resolved_params[substitute_params(k, env)] = substitute_params(v, env)

        resolved_headers.setdefault("User-Agent", "AngryREST/0.0.1")

        content = None
        data = None
        json_data = None
        files: list[tuple[str, tuple[str, bytes, str]]] | None = None
        _body_preview: list[str] = []  # extra lines appended to the request log

        if body_type == "json" and body:
            resolved_body = substitute_params(body if isinstance(body, str) else body.decode(), env)
            resolved_headers.setdefault("Content-Type", "application/json")
            content = resolved_body.encode("utf-8")
            _body_preview = ["", resolved_body[:2000] + ("…" if len(resolved_body) > 2000 else "")]
        elif body_type == "graphql" and body:
            import json

            resolved_query = substitute_params(body if isinstance(body, str) else body.decode(), env)
            resolved_headers.setdefault("Content-Type", "application/graphql")
            if resolved_headers.get("Content-Type", "").lower() == "application/graphql":
                content = resolved_query.encode("utf-8")
                _body_preview = ["", resolved_query[:2000] + ("…" if len(resolved_query) > 2000 else "")]
            else:
                # User explicitly set Content-Type: application/json — use JSON wrapper
                graphql_payload: dict[str, object] = {"query": resolved_query}
                if form_data and form_data.get("__graphql_variables__"):
                    vars_str = substitute_params(form_data["__graphql_variables__"], env)
                    try:
                        graphql_payload["variables"] = json.loads(vars_str)
                    except (json.JSONDecodeError, ValueError):
                        pass
                content = json.dumps(graphql_payload).encode("utf-8")
                _body_preview = ["", json.dumps(graphql_payload, indent=2)[:2000]]
        elif body_type == "form" and form_data:
            resolved_form = {}
            for k, v in form_data.items():
                if k == "__graphql_variables__":
                    continue
                resolved_form[substitute_params(k, env)] = substitute_params(v, env)
            data = resolved_form
            _body_preview = ["", str(resolved_form)]

        files: list[tuple[str, tuple[str, bytes, str]]] | None = None
        if body_type == "multipart":
            import mimetypes
            import os

            resolved_text: dict[str, str] = {}
            if form_data:
                for k, v in form_data.items():
                    resolved_text[substitute_params(k, env)] = substitute_params(v, env)
            data = resolved_text or None

            resolved_files: list[tuple[str, tuple[str, bytes, str]]] = []
            for field_name, file_path in (file_fields or []):
                resolved_path = substitute_params(file_path, env)
                if not resolved_path:
                    continue
                filename = os.path.basename(resolved_path)
                mime_type, _ = mimetypes.guess_type(resolved_path)
                mime_type = mime_type or "application/octet-stream"
                try:
                    with open(resolved_path, "rb") as fh:
                        file_bytes = fh.read()
                except OSError as exc:
                    return ErrorResult("other", f"Cannot read file {resolved_path!r}: {exc}")
                resolved_files.append((substitute_params(field_name, env), (filename, file_bytes, mime_type)))
            files = resolved_files or None
            _body_preview = ["", f"[multipart: {len(resolved_text)} text field(s), {len(resolved_files)} file(s)]"]

        # --- Log outgoing request ---
        _log_lines = [f"→ {method.upper()} {resolved_url}"]
        for k, v in resolved_headers.items():
            _log_lines.append(f"  {k}: {v}")
        _log.info("\n".join(_log_lines + _body_preview))

        try:
            start = time.perf_counter()
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.request(
                    method=method.upper(),
                    url=resolved_url,
                    headers=resolved_headers or None,
                    params=resolved_params or None,
                    content=content,
                    data=data,
                    files=files,
                )
            elapsed = (time.perf_counter() - start) * 1000

            resp_headers = dict(response.headers)
            size = len(response.content)
            _log.info(
                f"\u2190 {response.status_code} {response.reason_phrase or ''}  "
                f"({elapsed:.1f}\u202fms, {size:,}\u202fB)"
            )
            return ResponseData(
                status_code=response.status_code,
                reason_phrase=response.reason_phrase or "",
                headers=resp_headers,
                body=response.content,
                elapsed_ms=round(elapsed, 1),
                size_bytes=size,
            )

        except httpx.ConnectError as e:
            _log.error(f"\u2717 [connection] {e}")
            return ErrorResult("connection", f"Connection refused or unreachable: {e}")
        except httpx.TimeoutException as e:
            _log.error(f"\u2717 [timeout] {e}")
            return ErrorResult("timeout", f"Request timed out: {e}")
        except httpx.HTTPError as e:
            _log.error(f"\u2717 [http] {e}")
            return ErrorResult("other", f"HTTP error: {e}")
        except Exception as e:
            _log.error(f"\u2717 {e}")
            return ErrorResult("other", str(e))
