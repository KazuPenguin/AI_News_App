"""Tests for batch.handler module."""

from batch.handler import main


class TestBatchHandler:
    """Batch handler が正常に呼び出せることを検証する。"""

    def test_returns_200(self, lambda_context) -> None:  # type: ignore[no-untyped-def]
        event = {"source": "aws.events"}
        result = main(event, lambda_context)
        assert result["statusCode"] == 200

    def test_returns_ok_body(self, lambda_context) -> None:  # type: ignore[no-untyped-def]
        event = {"source": "aws.events"}
        result = main(event, lambda_context)
        assert result["body"] == "OK"
