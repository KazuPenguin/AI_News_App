"""Tests for batch.handler module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from batch.handler import main
from utils.models import BatchLogEntry


class TestBatchHandler:
    """Batch handler が正常に呼び出せることを検証する。"""

    @patch("batch.handler.asyncio")
    def test_returns_200_on_success(
        self,
        mock_asyncio: MagicMock,
        lambda_context: Any,
    ) -> None:
        log_entry = BatchLogEntry(
            execution_date="2026-02-19",
            date_range={"start": "202602180000", "end": "202602190000"},
            l1_dedup_count=100,
            l2_passed_count=40,
            l3_relevant_count=15,
            figures_extracted=45,
            processing_time_sec=600,
        )
        mock_asyncio.run.return_value = log_entry

        event = {"source": "aws.events"}
        result = main(event, lambda_context)
        assert result["statusCode"] == 200

    @patch("batch.handler.asyncio")
    def test_returns_pipeline_stats(
        self,
        mock_asyncio: MagicMock,
        lambda_context: Any,
    ) -> None:
        log_entry = BatchLogEntry(
            execution_date="2026-02-19",
            date_range={"start": "202602180000", "end": "202602190000"},
            l1_dedup_count=100,
            l2_passed_count=40,
            l3_relevant_count=15,
            figures_extracted=45,
            processing_time_sec=600,
        )
        mock_asyncio.run.return_value = log_entry

        event = {"source": "aws.events"}
        result = main(event, lambda_context)
        body = result["body"]
        assert body["l1_dedup_count"] == 100
        assert body["l3_relevant_count"] == 15

    @patch("batch.handler.asyncio")
    def test_returns_500_on_failure(
        self,
        mock_asyncio: MagicMock,
        lambda_context: Any,
    ) -> None:
        mock_asyncio.run.side_effect = RuntimeError("Pipeline crashed")

        event = {"source": "aws.events"}
        result = main(event, lambda_context)
        assert result["statusCode"] == 500
