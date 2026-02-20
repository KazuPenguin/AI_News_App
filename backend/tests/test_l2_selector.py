"""Tests for L2 selector — importance計算、閾値判定のユニットテスト。

DB・APIコールは含まない純粋なロジックテスト。
"""

from __future__ import annotations

from batch.config import (
    ANCHOR_COUNT,
    IMPORTANCE_WEIGHT_HIT_COUNT,
    IMPORTANCE_WEIGHT_MATCHED_QUERIES,
    IMPORTANCE_WEIGHT_MAX_SCORE,
    L2_THRESHOLD,
)
from utils.models import L2Result


def compute_importance(
    max_score: float,
    hit_count: int,
    matched_queries_count: int,
) -> float:
    """importance_score の計算ロジック (l2_selector._compute_l2_scores 内と同一)。"""
    return (
        IMPORTANCE_WEIGHT_MAX_SCORE * max_score
        + IMPORTANCE_WEIGHT_HIT_COUNT * (hit_count / ANCHOR_COUNT)
        + IMPORTANCE_WEIGHT_MATCHED_QUERIES * (matched_queries_count / ANCHOR_COUNT)
    )


# ---------------------------------------------------------------------------
# importance_score 計算
# ---------------------------------------------------------------------------
class TestImportanceScore:
    """importance_score の算出ロジックを検証する。"""

    def test_high_score_single_category(self) -> None:
        """高類似度 + 1カテゴリヒット → 専門性重視。"""
        score = compute_importance(max_score=0.7, hit_count=1, matched_queries_count=1)
        # 0.6 * 0.7 + 0.3 * (1/6) + 0.1 * (1/6) = 0.42 + 0.05 + 0.017 ≈ 0.487
        assert 0.48 < score < 0.50

    def test_moderate_score_multi_category(self) -> None:
        """中程度類似度 + 複数カテゴリヒット → 分野横断性。"""
        score = compute_importance(max_score=0.5, hit_count=4, matched_queries_count=3)
        # 0.6 * 0.5 + 0.3 * (4/6) + 0.1 * (3/6) = 0.30 + 0.20 + 0.05 = 0.55
        assert 0.54 < score < 0.56

    def test_max_score_all_hit(self) -> None:
        """最高スコアの場合。"""
        score = compute_importance(max_score=1.0, hit_count=6, matched_queries_count=6)
        # 0.6 * 1.0 + 0.3 * 1.0 + 0.1 * 1.0 ≈ 1.0
        assert abs(score - 1.0) < 1e-10

    def test_zero_score(self) -> None:
        """スコア0の場合。"""
        score = compute_importance(max_score=0.0, hit_count=0, matched_queries_count=0)
        assert score == 0.0

    def test_weights_sum_to_one(self) -> None:
        """重み係数の合計が1.0であること。"""
        total = (
            IMPORTANCE_WEIGHT_MAX_SCORE
            + IMPORTANCE_WEIGHT_HIT_COUNT
            + IMPORTANCE_WEIGHT_MATCHED_QUERIES
        )
        assert abs(total - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# L2 閾値判定
# ---------------------------------------------------------------------------
class TestL2Threshold:
    """L2通過閾値の判定を検証する。"""

    def test_above_threshold_passes(self) -> None:
        result = L2Result(
            arxiv_id="2402.12345",
            max_score=0.45,
            best_category_id=1,
            hit_count=2,
            importance_score=0.5,
            all_scores={"1": 0.45, "2": 0.30},
            passed=0.45 >= L2_THRESHOLD,
        )
        assert result.passed is True

    def test_below_threshold_fails(self) -> None:
        result = L2Result(
            arxiv_id="2402.12345",
            max_score=0.35,
            best_category_id=1,
            hit_count=0,
            importance_score=0.2,
            all_scores={"1": 0.35, "2": 0.20},
            passed=0.35 >= L2_THRESHOLD,
        )
        assert result.passed is False

    def test_exact_threshold_passes(self) -> None:
        result = L2Result(
            arxiv_id="2402.12345",
            max_score=L2_THRESHOLD,
            best_category_id=1,
            hit_count=1,
            importance_score=0.3,
            all_scores={"1": L2_THRESHOLD},
            passed=L2_THRESHOLD >= L2_THRESHOLD,
        )
        assert result.passed is True

    def test_threshold_value(self) -> None:
        """閾値が設計書の値 (0.40) であること。"""
        assert L2_THRESHOLD == 0.40
