from __future__ import annotations

import io
import json
import logging
import re
import base64
import hashlib
import uuid as uuid_mod
from dataclasses import dataclass, field
from typing import Any

from angryrest.services import app_logger as _app_logger
from angryrest.services.http_client import ResponseData

_log = _app_logger.get_logger("scripts")


def _log_script_result(result: ScriptResult, label: str) -> None:
    lines = [f"[{label}] {'OK' if result.success else 'FAILED'}"]
    if result.error:
        lines[0] += f"  {result.error}"
    if result.output.strip():
        lines.append("--- print output ---")
        lines.append(result.output.rstrip())
    if result.assertions:
        lines.append("--- assertions ---")
        for a in result.assertions:
            mark = "\u2713" if a.passed else "\u2717"
            lines.append(f"  {mark} {a.message}")
    msg = "\n".join(lines)
    if result.success:
        _log.info(msg)
    else:
        _log.error(msg)


@dataclass
class AssertionResult:
    passed: bool
    message: str


@dataclass
class ScriptResult:
    success: bool
    env: dict[str, str]
    output: str = ""
    error: str = ""
    assertions: list[AssertionResult] = field(default_factory=list)


class ScriptEngine:
    def run_pre_script(
        self,
        script: str,
        env: dict[str, str],
        request_info: dict[str, Any],
    ) -> ScriptResult:
        if not script.strip():
            return ScriptResult(success=True, env=env)

        env_copy = dict(env)
        output_buf = io.StringIO()

        namespace: dict[str, Any] = {
            "env": env_copy,
            "request": request_info,
            "log": _log,
            "logging": logging,
            "json": json,
            "re": re,
            "base64": base64,
            "hashlib": hashlib,
            "uuid": uuid_mod,
            "print": lambda *args, **kwargs: print(
                *args, **kwargs, file=output_buf
            ),
        }

        try:
            exec(script, namespace)  # noqa: S102
            result = ScriptResult(
                success=True,
                env=env_copy,
                output=output_buf.getvalue(),
            )
        except Exception as e:
            result = ScriptResult(
                success=False,
                env=env_copy,
                output=output_buf.getvalue(),
                error=f"{type(e).__name__}: {e}",
            )
        _log_script_result(result, "pre-script")
        return result

    def run_post_script(
        self,
        script: str,
        env: dict[str, str],
        response: ResponseData,
    ) -> ScriptResult:
        if not script.strip():
            return ScriptResult(success=True, env=env)

        env_copy = dict(env)
        output_buf = io.StringIO()
        assertions: list[AssertionResult] = []

        def assert_status(expected_code: int, msg: str = "") -> None:
            passed = response.status_code == expected_code
            message = msg or f"Expected status {expected_code}, got {response.status_code}"
            assertions.append(AssertionResult(passed=passed, message=message))
            if not passed:
                raise AssertionError(message)

        def assert_equals(actual: Any, expected: Any, msg: str = "") -> None:
            passed = actual == expected
            message = msg or f"Expected {expected!r}, got {actual!r}"
            assertions.append(AssertionResult(passed=passed, message=message))
            if not passed:
                raise AssertionError(message)

        def assert_true(condition: bool, msg: str = "") -> None:
            passed = bool(condition)
            message = msg or "Assertion failed: condition is not true"
            assertions.append(AssertionResult(passed=passed, message=message))
            if not passed:
                raise AssertionError(message)

        def assert_contains(text: str, substring: str, msg: str = "") -> None:
            passed = substring in text
            message = msg or f"Expected {text!r} to contain {substring!r}"
            assertions.append(AssertionResult(passed=passed, message=message))
            if not passed:
                raise AssertionError(message)

        class ResponseWrapper:
            def __init__(self, resp: ResponseData):
                self._resp = resp
                self.status_code = resp.status_code
                self.headers = resp.headers
                self.elapsed_ms = resp.elapsed_ms
                self.size_bytes = resp.size_bytes

            def text(self) -> str:
                return self._resp.text()

            def json(self) -> Any:
                return self._resp.json()

        namespace: dict[str, Any] = {
            "env": env_copy,
            "response": ResponseWrapper(response),
            "assert_status": assert_status,
            "assert_equals": assert_equals,
            "assert_true": assert_true,
            "assert_contains": assert_contains,
            "log": _log,
            "logging": logging,
            "json": json,
            "re": re,
            "base64": base64,
            "hashlib": hashlib,
            "uuid": uuid_mod,
            "print": lambda *args, **kwargs: print(
                *args, **kwargs, file=output_buf
            ),
        }

        try:
            exec(script, namespace)  # noqa: S102
            result = ScriptResult(
                success=True,
                env=env_copy,
                output=output_buf.getvalue(),
                assertions=assertions,
            )
        except AssertionError:
            result = ScriptResult(
                success=False,
                env=env_copy,
                output=output_buf.getvalue(),
                assertions=assertions,
            )
        except Exception as e:
            result = ScriptResult(
                success=False,
                env=env_copy,
                output=output_buf.getvalue(),
                error=f"{type(e).__name__}: {e}",
                assertions=assertions,
            )
        _log_script_result(result, "post-script")
        return result
