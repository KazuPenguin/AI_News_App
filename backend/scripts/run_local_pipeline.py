"""
AI Research OS — ローカルパイプライン実行スクリプト

Lambdaにデプロイせずに手元でL1〜Post-L3の
キュレーションパイプライン（日次バッチ処理）全体をローカルテストするためのスクリプトです。
環境変数 (.env) から設定を読み込み実行します。
"""

import asyncio
import sys

from dotenv import load_dotenv

from batch.pipeline import run_pipeline
from utils.logger import logger


async def main() -> None:
    # Load environment variables from .env file
    load_dotenv()

    logger.info("Starting local pipeline execution...")
    try:
        log_entry = await run_pipeline()
        logger.info(
            "Local pipeline execution completed successfully.",
            extra={
                "processing_time_sec": log_entry.processing_time_sec,
                "l2_passed_count": log_entry.l2_passed_count,
                "l3_relevant_count": log_entry.l3_relevant_count,
                "figures_extracted": log_entry.figures_extracted,
                "error_count": len(log_entry.errors),
            },
        )
    except Exception:
        logger.error("Local pipeline execution failed", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
