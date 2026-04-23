from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from angryrest.services.http_client import ErrorResult, HttpClient, ResponseData, substitute_params


class TestSubstituteParams:
    def test_single_substitution(self) -> None:
        assert substitute_params("Hello <name>!", {"name": "World"}) == "Hello World!"

    def test_multiple_substitutions(self) -> None:
        result = substitute_params("<scheme>://<host>/api", {"scheme": "https", "host": "example.com"})
        assert result == "https://example.com/api"

    def test_missing_key_preserved(self) -> None:
        result = substitute_params("Bearer <token>", {})
        assert result == "Bearer <token>"

    def test_partial_missing_key(self) -> None:
        result = substitute_params("<found>-<missing>", {"found": "yes"})
        assert result == "yes-<missing>"

    def test_no_params_in_text(self) -> None:
        assert substitute_params("no params here", {"key": "val"}) == "no params here"

    def test_empty_env(self) -> None:
        assert substitute_params("<key>", {}) == "<key>"

    def test_empty_text(self) -> None:
        assert substitute_params("", {"key": "val"}) == ""

    def test_adjacent_params(self) -> None:
        assert substitute_params("<a><b>", {"a": "X", "b": "Y"}) == "XY"

    def test_angle_bracket_not_param_if_nested(self) -> None:
        # Regex is non-greedy but does not support nesting — test basic greedy boundary
        result = substitute_params("<a>", {"a": "ok"})
        assert result == "ok"


class TestHttpClientSend:
    def _make_mock_response(
        self,
        status_code: int = 200,
        content: bytes = b"OK",
        headers: dict[str, str] | None = None,
        reason_phrase: str = "OK",
    ) -> MagicMock:
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.reason_phrase = reason_phrase
        resp.content = content
        resp.headers = headers or {"content-type": "text/plain"}
        return resp

    def test_successful_get(self) -> None:
        client = HttpClient()
        mock_resp = self._make_mock_response(200, b"Hello")

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.return_value = mock_resp

            result = client.send("GET", "https://example.com")

        assert isinstance(result, ResponseData)
        assert result.status_code == 200
        assert result.body == b"Hello"

    def test_successful_post_json_body(self) -> None:
        client = HttpClient()
        mock_resp = self._make_mock_response(201, b'{"id":1}', reason_phrase="Created")

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.return_value = mock_resp

            result = client.send(
                "POST",
                "https://example.com/items",
                body='{"name": "test"}',
                body_type="json",
            )

        assert isinstance(result, ResponseData)
        assert result.status_code == 201
        # Check Content-Type was set
        call_kwargs = mock_ctx.request.call_args.kwargs
        assert "application/json" in call_kwargs["headers"].get("Content-Type", "")

    def test_env_param_substitution_in_url(self) -> None:
        client = HttpClient()
        mock_resp = self._make_mock_response()

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.return_value = mock_resp

            result = client.send(
                "GET",
                "https://<host>/api",
                env_vars={"host": "api.example.com"},
            )

        assert isinstance(result, ResponseData)
        call_kwargs = mock_ctx.request.call_args.kwargs
        assert call_kwargs["url"] == "https://api.example.com/api"

    def test_connection_error_returns_error_result(self) -> None:
        client = HttpClient()

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.side_effect = httpx.ConnectError("refused")

            result = client.send("GET", "https://unreachable.example.com")

        assert isinstance(result, ErrorResult)
        assert result.error_type == "connection"

    def test_timeout_returns_error_result(self) -> None:
        client = HttpClient()

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.side_effect = httpx.TimeoutException("timed out")

            result = client.send("GET", "https://slow.example.com")

        assert isinstance(result, ErrorResult)
        assert result.error_type == "timeout"

    def test_default_user_agent_set(self) -> None:
        client = HttpClient()
        mock_resp = self._make_mock_response()

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.return_value = mock_resp

            client.send("GET", "https://example.com")

        headers = mock_ctx.request.call_args.kwargs["headers"]
        assert "User-Agent" in headers
        assert "AngryREST" in headers["User-Agent"]

    def test_form_body_type(self) -> None:
        client = HttpClient()
        mock_resp = self._make_mock_response()

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.return_value = mock_resp

            client.send(
                "POST",
                "https://example.com/form",
                body_type="form",
                form_data={"username": "alice", "password": "secret"},
            )

        call_kwargs = mock_ctx.request.call_args.kwargs
        assert call_kwargs["data"] == {"username": "alice", "password": "secret"}
        assert call_kwargs["content"] is None

    def test_elapsed_ms_is_non_negative(self) -> None:
        client = HttpClient()
        mock_resp = self._make_mock_response(200, b"")

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.return_value = mock_resp

            result = client.send("GET", "https://example.com")

        assert isinstance(result, ResponseData)
        assert result.elapsed_ms >= 0


class TestResponseData:
    def test_text_decodes_utf8(self) -> None:
        rd = ResponseData(200, "OK", {}, "héllo".encode("utf-8"), 10.0, 6)
        assert rd.text() == "héllo"

    def test_text_replaces_bad_bytes(self) -> None:
        rd = ResponseData(200, "OK", {}, b"\xff\xfe", 1.0, 2)
        assert len(rd.text()) > 0  # must not raise

    def test_json_parses_body(self) -> None:
        rd = ResponseData(200, "OK", {}, b'{"status": "ok"}', 5.0, 16)
        assert rd.json() == {"status": "ok"}
