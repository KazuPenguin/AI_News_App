"""
AI Research OS — Batch Lambda Handler

EventBridge (UTC 21:00 Mon-Fri) からトリガーされ、
L1 → L2 → L3 → Post-L3 のキュレーションパイプラインを実行する。
"""

from __future__ import annotations

import asyncio
from typing import Any

from utils.logger import logger, metrics


@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """EventBridge からトリガーされるエントリーポイント。

    asyncio.run() でパイプライン全体を実行する。
    """
    logger.info("Batch handler invoked")

    try:
        from batch.pipeline import run_pipeline

        log_entry = asyncio.run(run_pipeline())

        return {
            "statusCode": 200,
            "body": {
                "execution_date": log_entry.execution_date,
                "l1_dedup_count": log_entry.l1_dedup_count,
                "l2_passed_count": log_entry.l2_passed_count,
                "l3_relevant_count": log_entry.l3_relevant_count,
                "figures_extracted": log_entry.figures_extracted,
                "processing_time_sec": log_entry.processing_time_sec,
                "error_count": len(log_entry.errors),
            },
        }
    except Exception:
        logger.error("Pipeline execution failed", exc_info=True)
        return {"statusCode": 500, "body": "Pipeline execution failed"}
