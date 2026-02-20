"""Tests for batch.l3_analyzer module — プロンプト構築、レスポンス検証。"""

from __future__ import annotations

from datetime import datetime, timezone

from batch.config import CATEGORY_NAMES
from batch.l3_analyzer import build_l3_prompt
from utils.models import L2Paper, L3Response


# ---------------------------------------------------------------------------
# テスト用データ
# ---------------------------------------------------------------------------
def _make_l2_paper(**kwargs: object) -> L2Paper:
    """テスト用の L2Paper を作成する。"""
    defaults: dict[str, object] = {
        "arxiv_id": "2402.12345",
        "title": "Efficient KV Cache Compression for Long-Context LLM Serving",
        "abstract": "We propose a novel method for compressing KV cache in LLM inference.",
        "authors": ["Alice Smith", "Bob Chen"],
        "primary_category": "cs.CL",
        "published_at": datetime(2026, 2, 11, tzinfo=timezone.utc),
        "matched_queries": [1, 4],
        "best_category_id": 4,
        "max_score": 0.62,
        "hit_count": 2,
        "importance_score": 0.57,
        "all_scores": {"1": 0.41, "2": 0.28, "3": 0.33, "4": 0.62, "5": 0.19, "6": 0.12},
    }
    defaults.update(kwargs)
    return L2Paper(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_l3_prompt
# ---------------------------------------------------------------------------
class TestBuildL3Prompt:
    """L3 プロンプト構築のテスト。"""

    def test_contains_title(self) -> None:
        paper = _make_l2_paper()
        prompt = build_l3_prompt(paper)
        assert paper.title in prompt

    def test_contains_abstract(self) -> None:
        paper = _make_l2_paper()
        prompt = build_l3_prompt(paper)
        assert paper.abstract in prompt

    def test_contains_category_name(self) -> None:
        paper = _make_l2_paper(best_category_id=4)
        prompt = build_l3_prompt(paper)
        assert CATEGORY_NAMES[4] in prompt

    def test_contains_max_score(self) -> None:
        paper = _make_l2_paper(max_score=0.62)
        prompt = build_l3_prompt(paper)
        assert "0.62" in prompt

    def test_contains_hit_count(self) -> None:
        paper = _make_l2_paper(hit_count=2)
        prompt = build_l3_prompt(paper)
        assert "2/6" in prompt


# ---------------------------------------------------------------------------
# L3Response バリデーション
# ---------------------------------------------------------------------------
class TestL3Response:
    """L3Response Pydantic モデルの検証テスト。"""

    def test_valid_relevant_response(self) -> None:
        resp = L3Response(
            is_relevant=True,
            category_id=4,
            secondary_category_ids=[1],
            confidence=0.92,
            importance=4,
            summary_ja="KV Cacheを動的に圧縮し、vLLMスループットを2.3倍改善",
            reasoning="Direct contribution to inference optimization.",
        )
        assert resp.is_relevant is True
        assert resp.category_id == 4
        assert resp.importance == 4

    def test_valid_irrelevant_response(self) -> None:
        resp = L3Response(
            is_relevant=False,
            category_id=3,
            confidence=0.78,
            importance=1,
            summary_ja="対話分析における言語学的特徴量の影響を調査",
            reasoning="No systems-level contribution.",
        )
        assert resp.is_relevant is False
        assert resp.importance == 1

    def test_missing_optional_fields(self) -> None:
        """secondary_category_ids と reasoning はオプション。"""
        resp = L3Response(
            is_relevant=True,
            category_id=1,
            confidence=0.85,
            importance=3,
            summary_ja="テスト要約",
        )
        assert resp.secondary_category_ids == []
        assert resp.reasoning == ""

    def test_invalid_category_id(self) -> None:
        """category_id が 1-6 の範囲外。"""
        import pytest

        with pytest.raises(Exception):
            L3Response(
                is_relevant=True,
                category_id=7,
                confidence=0.5,
                importance=3,
                summary_ja="テスト",
            )

    def test_invalid_importance(self) -> None:
        """importance が 1-5 の範囲外。"""
        import pytest

        with pytest.raises(Exception):
            L3Response(
                is_relevant=True,
                category_id=1,
                confidence=0.5,
                importance=6,
                summary_ja="テスト",
            )

    def test_confidence_range(self) -> None:
        """confidence が 0.0-1.0 の範囲内。"""
        import pytest

        with pytest.raises(Exception):
            L3Response(
                is_relevant=True,
                category_id=1,
                confidence=1.5,
                importance=3,
                summary_ja="テスト",
            )
