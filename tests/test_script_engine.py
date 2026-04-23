from __future__ import annotations

import pytest

from angryrest.services.http_client import ResponseData
from angryrest.services.script_engine import ScriptEngine, ScriptResult


def _make_response(
    status_code: int = 200,
    body: bytes = b'{"ok": true}',
    headers: dict[str, str] | None = None,
) -> ResponseData:
    return ResponseData(
        status_code=status_code,
        reason_phrase="OK",
        headers=headers or {"content-type": "application/json"},
        body=body,
        elapsed_ms=10.0,
        size_bytes=len(body),
    )


class TestPreScript:
    def setup_method(self) -> None:
        self.engine = ScriptEngine()

    def test_empty_script_returns_success(self) -> None:
        result = self.engine.run_pre_script("", {"k": "v"}, {})
        assert result.success is True
        assert result.env == {"k": "v"}

    def test_whitespace_only_script_returns_success(self) -> None:
        result = self.engine.run_pre_script("   \n  ", {}, {})
        assert result.success is True

    def test_env_mutation_is_returned(self) -> None:
        script = "env['token'] = 'abc123'"
        result = self.engine.run_pre_script(script, {}, {})
        assert result.success is True
        assert result.env["token"] == "abc123"

    def test_original_env_not_mutated(self) -> None:
        env = {"key": "original"}
        script = "env['key'] = 'changed'"
        self.engine.run_pre_script(script, env, {})
        assert env["key"] == "original"

    def test_print_captured_in_output(self) -> None:
        script = "print('hello from pre-script')"
        result = self.engine.run_pre_script(script, {}, {})
        assert "hello from pre-script" in result.output

    def test_syntax_error_returns_failure(self) -> None:
        result = self.engine.run_pre_script("def (:", {}, {})
        assert result.success is False
        assert result.error != ""

    def test_runtime_exception_returns_failure(self) -> None:
        result = self.engine.run_pre_script("raise ValueError('oops')", {}, {})
        assert result.success is False
        assert "ValueError" in result.error
        assert "oops" in result.error

    def test_stdlib_json_available(self) -> None:
        script = "env['parsed'] = str(json.loads('[1,2,3]'))"
        result = self.engine.run_pre_script(script, {}, {})
        assert result.success is True

    def test_request_info_accessible(self) -> None:
        script = "env['method'] = request['method']"
        result = self.engine.run_pre_script(script, {}, {"method": "POST"})
        assert result.success is True
        assert result.env["method"] == "POST"


class TestPostScript:
    def setup_method(self) -> None:
        self.engine = ScriptEngine()

    def test_empty_script_returns_success(self) -> None:
        result = self.engine.run_post_script("", {}, _make_response())
        assert result.success is True

    def test_assert_status_pass(self) -> None:
        result = self.engine.run_post_script(
            "assert_status(200)", {}, _make_response(200)
        )
        assert result.success is True
        assert len(result.assertions) == 1
        assert result.assertions[0].passed is True

    def test_assert_status_fail(self) -> None:
        result = self.engine.run_post_script(
            "assert_status(201)", {}, _make_response(200)
        )
        assert result.success is False
        assert result.assertions[0].passed is False

    def test_assert_equals_pass(self) -> None:
        script = "assert_equals(response.status_code, 200)"
        result = self.engine.run_post_script(script, {}, _make_response(200))
        assert result.success is True
        assert result.assertions[0].passed is True

    def test_assert_equals_fail(self) -> None:
        script = "assert_equals(1, 2)"
        result = self.engine.run_post_script(script, {}, _make_response())
        assert result.success is False
        assert result.assertions[0].passed is False

    def test_assert_true_pass(self) -> None:
        result = self.engine.run_post_script("assert_true(1 == 1)", {}, _make_response())
        assert result.success is True

    def test_assert_true_fail(self) -> None:
        result = self.engine.run_post_script("assert_true(False)", {}, _make_response())
        assert result.success is False

    def test_assert_contains_pass(self) -> None:
        result = self.engine.run_post_script(
            "assert_contains(response.text(), 'ok')", {}, _make_response(body=b'{"ok": true}')
        )
        assert result.success is True

    def test_assert_contains_fail(self) -> None:
        result = self.engine.run_post_script(
            "assert_contains('hello world', 'missing')", {}, _make_response()
        )
        assert result.success is False

    def test_multiple_assertions_collected_before_failure(self) -> None:
        script = (
            "assert_status(200)\n"
            "assert_equals(response.status_code, 999)\n"  # this fails and stops
        )
        result = self.engine.run_post_script(script, {}, _make_response(200))
        assert result.assertions[0].passed is True
        assert result.assertions[1].passed is False
        assert result.success is False

    def test_env_mutation_in_post_script(self) -> None:
        script = "env['captured'] = str(response.status_code)"
        result = self.engine.run_post_script(script, {}, _make_response(404))
        assert result.success is True
        assert result.env["captured"] == "404"

    def test_response_json_accessible(self) -> None:
        script = "assert_equals(response.json()['ok'], True)"
        result = self.engine.run_post_script(script, {}, _make_response(body=b'{"ok": true}'))
        assert result.success is True

    def test_response_headers_accessible(self) -> None:
        script = "assert_true('content-type' in response.headers)"
        result = self.engine.run_post_script(
            script, {}, _make_response(headers={"content-type": "application/json"})
        )
        assert result.success is True

    def test_runtime_exception_captured(self) -> None:
        script = "raise RuntimeError('post boom')"
        result = self.engine.run_post_script(script, {}, _make_response())
        assert result.success is False
        assert "RuntimeError" in result.error

    def test_custom_assertion_message_used(self) -> None:
        script = "assert_status(404, 'should be not found')"
        result = self.engine.run_post_script(script, {}, _make_response(200))
        assert "should be not found" in result.assertions[0].message

    def test_print_captured_in_output(self) -> None:
        script = "print('post output')"
        result = self.engine.run_post_script(script, {}, _make_response())
        assert "post output" in result.output
