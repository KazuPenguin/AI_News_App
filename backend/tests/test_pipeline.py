"""Tests for batch.pipeline module — オーケストレーション、エラー伝播の検証。

外部 API・DB 呼び出しは全てモックで置き換える。
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.models import ArxivPaper, BatchLogEntry, L2Paper


# ---------------------------------------------------------------------------
# テスト用データ
# ---------------------------------------------------------------------------
def _make_arxiv_paper(arxiv_id: str = "2402.12345") -> ArxivPaper:
    return ArxivPaper(
        arxiv_id=arxiv_id,
        title="Test Paper",
        abstract="Test abstract about LLMs.",
        authors=["Author"],
        primary_category="cs.CL",
        published_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
        matched_queries=[1],
    )


def _make_l2_paper(arxiv_id: str = "2402.12345") -> L2Paper:
    return L2Paper(
        arxiv_id=arxiv_id,
        title="Test Paper",
        abstract="Test abstract about LLMs.",
        authors=["Author"],
        primary_category="cs.CL",
        published_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
        matched_queries=[1],
        best_category_id=1,
        max_score=0.6,
        hit_count=2,
        importance_score=0.5,
        all_scores={"1": 0.6, "2": 0.4},
    )


# ---------------------------------------------------------------------------
# パイプラインのテスト
# ---------------------------------------------------------------------------
class TestPipeline:
    """パイプラインオーケストレーションの検証。"""

    @pytest.mark.asyncio
    @patch("batch.pipeline.close_connections", new_callable=AsyncMock)
    @patch("batch.pipeline.get_async_connection")
    @patch("batch.pipeline.run_post_l3", new_callable=AsyncMock)
    @patch("batch.pipeline.run_l3", new_callable=AsyncMock)
    @patch("batch.pipeline.run_l2")
    @patch("batch.pipeline.collect_papers")
    @patch("batch.pipeline.log_curation_stats")
    async def test_full_pipeline_success(
        self,
        mock_log_stats: MagicMock,
        mock_l1: MagicMock,
        mock_l2: MagicMock,
        mock_l3: AsyncMock,
        mock_post_l3: AsyncMock,
        mock_get_conn: MagicMock,
        mock_close: AsyncMock,
    ) -> None:
        """正常系: 全フェーズが成功する場合。"""
        # L1
        papers = [_make_arxiv_paper("2402.11111"), _make_arxiv_paper("2402.22222")]
        mock_l1.return_value = papers

        # L2
        l2_papers = [_make_l2_paper("2402.11111")]
        mock_l2.return_value = l2_papers

        # L3
        l3_papers = [_make_l2_paper("2402.11111")]
        mock_l3.return_value = l3_papers

        # Post-L3
        mock_post_l3.return_value = (1, 3, [])

        # DB接続 (summary取得 + batch_log挿入)
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[("2402.11111", "テスト要約")])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = AsyncMock()
        mock_get_conn.return_value = mock_conn

        from batch.pipeline import run_pipeline

        result = await run_pipeline()

        assert isinstance(result, BatchLogEntry)
        assert result.l1_dedup_count == 2
        assert result.l2_passed_count == 1
        assert result.l3_relevant_count == 1
        mock_close.assert_called_once()

    @pytest.mark.asyncio
    @patch("batch.pipeline.close_connections", new_callable=AsyncMock)
    @patch("batch.pipeline.get_async_connection")
    @patch("batch.pipeline.run_post_l3", new_callable=AsyncMock)
    @patch("batch.pipeline.run_l3", new_callable=AsyncMock)
    @patch("batch.pipeline.run_l2")
    @patch("batch.pipeline.collect_papers")
    @patch("batch.pipeline.log_curation_stats")
    async def test_l1_failure_continues(
        self,
        mock_log_stats: MagicMock,
        mock_l1: MagicMock,
        mock_l2: MagicMock,
        mock_l3: AsyncMock,
        mock_post_l3: AsyncMock,
        mock_get_conn: MagicMock,
        mock_close: AsyncMock,
    ) -> None:
        """L1 が失敗しても後続フェーズが空リストで実行される。"""
        mock_l1.side_effect = RuntimeError("arXiv API down")
        mock_l2.return_value = []
        mock_l3.return_value = []
        mock_post_l3.return_value = (0, 0, [])

        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = AsyncMock()
        mock_get_conn.return_value = mock_conn

        from batch.pipeline import run_pipeline

        result = await run_pipeline()

        assert result.l1_dedup_count == 0
        assert len(result.errors) >= 1
        assert "L1" in result.errors[0]

    @pytest.mark.asyncio
    @patch("batch.pipeline.close_connections", new_callable=AsyncMock)
    @patch("batch.pipeline.get_async_connection")
    @patch("batch.pipeline.run_post_l3", new_callable=AsyncMock)
    @patch("batch.pipeline.run_l3", new_callable=AsyncMock)
    @patch("batch.pipeline.run_l2")
    @patch("batch.pipeline.collect_papers")
    @patch("batch.pipeline.log_curation_stats")
    async def test_l2_failure_continues(
        self,
        mock_log_stats: MagicMock,
        mock_l1: MagicMock,
        mock_l2: MagicMock,
        mock_l3: AsyncMock,
        mock_post_l3: AsyncMock,
        mock_get_conn: MagicMock,
        mock_close: AsyncMock,
    ) -> None:
        """L2 が失敗しても L3 以降が空リストで実行される。"""
        mock_l1.return_value = [_make_arxiv_paper()]
        mock_l2.side_effect = RuntimeError("DB connection failed")
        mock_l3.return_value = []
        mock_post_l3.return_value = (0, 0, [])

        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = AsyncMock()
        mock_get_conn.return_value = mock_conn

        from batch.pipeline import run_pipeline

        result = await run_pipeline()

        assert result.l2_passed_count == 0
        assert any("L2" in e for e in result.errors)

    @pytest.mark.asyncio
    @patch("batch.pipeline.close_connections", new_callable=AsyncMock)
    @patch("batch.pipeline.get_async_connection")
    @patch("batch.pipeline.run_post_l3", new_callable=AsyncMock)
    @patch("batch.pipeline.run_l3", new_callable=AsyncMock)
    @patch("batch.pipeline.run_l2")
    @patch("batch.pipeline.collect_papers")
    @patch("batch.pipeline.log_curation_stats")
    async def test_empty_pipeline(
        self,
        mock_log_stats: MagicMock,
        mock_l1: MagicMock,
        mock_l2: MagicMock,
        mock_l3: AsyncMock,
        mock_post_l3: AsyncMock,
        mock_get_conn: MagicMock,
        mock_close: AsyncMock,
    ) -> None:
        """L1 が空リストを返す場合。"""
        mock_l1.return_value = []
        mock_l2.return_value = []
        mock_l3.return_value = []
        mock_post_l3.return_value = (0, 0, [])

        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = AsyncMock()
        mock_get_conn.return_value = mock_conn

        from batch.pipeline import run_pipeline

        result = await run_pipeline()

        assert result.l1_dedup_count == 0
        assert result.l2_passed_count == 0
        assert result.l3_relevant_count == 0
