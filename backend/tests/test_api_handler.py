"""Tests for api.handler module."""

import json

from api.handler import main


class TestHealthEndpoint:
    """GET /health が正常にレスポンスを返すことを検証する。"""

    def test_returns_200(self, lambda_context) -> None:  # type: ignore[no-untyped-def]
        event = {"path": "/health", "httpMethod": "GET"}
        result = main(event, lambda_context)
        assert result["statusCode"] == 200

    def test_returns_ok_body(self, lambda_context) -> None:  # type: ignore[no-untyped-def]
        event = {"path": "/health", "httpMethod": "GET"}
        result = main(event, lambda_context)
        body = json.loads(result["body"])
        assert body["status"] == "ok"


class TestUnimplementedEndpoint:
    """未実装パスが適切なレスポンスを返すことを検証する。"""

    def test_returns_200(self, lambda_context) -> None:  # type: ignore[no-untyped-def]
        event = {"path": "/papers", "httpMethod": "GET"}
        result = main(event, lambda_context)
        assert result["statusCode"] == 200

    def test_returns_not_implemented_message(self, lambda_context) -> None:  # type: ignore[no-untyped-def]
        event = {"path": "/papers", "httpMethod": "GET"}
        result = main(event, lambda_context)
        body = json.loads(result["body"])
        assert body["message"] == "Not implemented yet"
