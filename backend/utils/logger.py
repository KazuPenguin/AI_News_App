"""
AI Research OS — 共通ロガー & メトリクス

AWS Lambda Powertools を使用した構造化ログとカスタムメトリクスを提供。
キュレーションパイプライン (L1/L2/L3) の処理統計を記録するヘルパーを含む。
"""

from __future__ import annotations

from dataclasses import dataclass

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

# ---------------------------------------------------------------------------
# シングルトン Logger / Metrics
# ---------------------------------------------------------------------------
logger = Logger(service="ai-research-os")
metrics = Metrics(namespace="AIResearchOS")


# ---------------------------------------------------------------------------
# キュレーション統計データクラス
# ---------------------------------------------------------------------------
@dataclass
class CurationStats:
    """L1/L2/L3 各フェーズの処理数を保持する。"""

    l1_fetched: int = 0
    l2_passed: int = 0
    l2_filtered: int = 0
    l3_passed: int = 0
    l3_filtered: int = 0


# ---------------------------------------------------------------------------
# キュレーション統計のログ出力
# ---------------------------------------------------------------------------
def log_curation_stats(stats: CurationStats) -> None:
    """キュレーションパイプラインの各フェーズの処理数を構造化ログで出力し、
    CloudWatch カスタムメトリクスとしても記録する。

    Args:
        stats: L1/L2/L3 の処理数を含む CurationStats
    """
    logger.info(
        "Curation pipeline completed",
        extra={
            "l1_fetched": stats.l1_fetched,
            "l2_passed": stats.l2_passed,
            "l2_filtered": stats.l2_filtered,
            "l3_passed": stats.l3_passed,
            "l3_filtered": stats.l3_filtered,
            "l3_reach_rate": (
                round(stats.l3_passed / stats.l1_fetched * 100, 2) if stats.l1_fetched > 0 else 0.0
            ),
        },
    )

    # CloudWatch カスタムメトリクス
    metrics.add_metric(name="L1Fetched", unit=MetricUnit.Count, value=stats.l1_fetched)
    metrics.add_metric(name="L2Passed", unit=MetricUnit.Count, value=stats.l2_passed)
    metrics.add_metric(name="L3Passed", unit=MetricUnit.Count, value=stats.l3_passed)
    metrics.add_metric(
        name="L3ReachRate",
        unit=MetricUnit.Percent,
        value=(round(stats.l3_passed / stats.l1_fetched * 100, 2) if stats.l1_fetched > 0 else 0.0),
    )
