"""
AI Research OS — パイプラインオーケストレーター

L1 → L2 → L3 → Post-L3 の4段階パイプラインを順次実行し、
batch_logs テーブルに結果を記録する。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from batch.l1_collector import collect_papers, compute_date_range
from batch.l2_selector import run_l2
from batch.l3_analyzer import run_l3
from batch.post_l3_reviewer import run_post_l3
from utils.db import close_connections, get_async_connection
from utils.logger import CurationStats, log_curation_stats, logger
from utils.models import BatchLogEntry


async def run_pipeline() -> BatchLogEntry:
    """パイプライン全体を実行する。

    Returns:
        バッチ実行ログ
    """
    start_time = time.time()
    start_date, end_date = compute_date_range()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    errors: list[str] = []

    logger.info("Pipeline started", extra={"execution_date": today})

    # -----------------------------------------------------------------------
    # L1: arXiv API 収集 (同期)
    # -----------------------------------------------------------------------
    try:
        l1_papers = collect_papers()
    except Exception as e:
        logger.error("L1 failed", exc_info=True)
        errors.append(f"L1: {e}")
        l1_papers = []

    l1_raw_count = len(l1_papers)
    l1_dedup_count = len(l1_papers)  # collect_papers() は重複排除済み

    # -----------------------------------------------------------------------
    # L2: pgvector 選別 (同期)
    # -----------------------------------------------------------------------
    try:
        l2_papers = run_l2(l1_papers)
    except Exception as e:
        logger.error("L2 failed", exc_info=True)
        errors.append(f"L2: {e}")
        l2_papers = []

    l2_passed_count = len(l2_papers)

    # -----------------------------------------------------------------------
    # L3: Gemini LLM 分析 (非同期)
    # -----------------------------------------------------------------------
    try:
        l3_papers = await run_l3(l2_papers)
    except Exception as e:
        logger.error("L3 failed", exc_info=True)
        errors.append(f"L3: {e}")
        l3_papers = []

    l3_relevant_count = len(l3_papers)

    # L3 の summary_ja を取得 (Post-L3 で使用)
    summaries: dict[str, str] = {}
    if l3_papers:
        try:
            conn = await get_async_connection()
            async with conn.cursor() as cur:
                arxiv_ids = [p.arxiv_id for p in l3_papers]
                placeholders = ",".join(["%s"] * len(arxiv_ids))
                await cur.execute(
                    f"SELECT arxiv_id, summary_ja FROM papers WHERE arxiv_id IN ({placeholders})",  # noqa: S608
                    arxiv_ids,
                )
                rows = await cur.fetchall()
                summaries = {r[0]: r[1] or "" for r in rows}
        except Exception as e:
            logger.warning("Failed to fetch summaries", exc_info=True)
            errors.append(f"Summary fetch: {e}")

    # -----------------------------------------------------------------------
    # Post-L3: PDF全文分析 + 図表抽出 (非同期)
    # -----------------------------------------------------------------------
    figures_extracted = 0
    try:
        success_count, figures_extracted, post_errors = await run_post_l3(l3_papers, summaries)
        errors.extend(post_errors)
    except Exception as e:
        logger.error("Post-L3 failed", exc_info=True)
        errors.append(f"Post-L3: {e}")

    # -----------------------------------------------------------------------
    # 処理時間 & ログ記録
    # -----------------------------------------------------------------------
    elapsed = int(time.time() - start_time)

    # CurationStats でメトリクス記録
    stats = CurationStats(
        l1_fetched=l1_dedup_count,
        l2_passed=l2_passed_count,
        l2_filtered=l1_dedup_count - l2_passed_count,
        l3_passed=l3_relevant_count,
        l3_filtered=l2_passed_count - l3_relevant_count,
    )
    log_curation_stats(stats)

    # BatchLogEntry の構築
    log_entry = BatchLogEntry(
        execution_date=today,
        date_range={"start": start_date, "end": end_date},
        l1_raw_count=l1_raw_count,
        l1_dedup_count=l1_dedup_count,
        l2_input_count=l1_dedup_count,
        l2_passed_count=l2_passed_count,
        l2_pass_rate=round(l2_passed_count / l1_dedup_count * 100, 1) if l1_dedup_count else 0,
        l3_input_count=l2_passed_count,
        l3_relevant_count=l3_relevant_count,
        l3_relevance_rate=(
            round(l3_relevant_count / l2_passed_count * 100, 1) if l2_passed_count else 0
        ),
        figures_extracted=figures_extracted,
        errors=errors,
        processing_time_sec=elapsed,
    )

    # batch_logs テーブルに INSERT
    try:
        conn = await get_async_connection()
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO batch_logs (
                    execution_date, date_range,
                    l1_raw_count, l1_dedup_count,
                    l2_input_count, l2_passed_count, l2_pass_rate,
                    l3_input_count, l3_relevant_count, l3_relevance_rate,
                    l3_input_tokens, l3_output_tokens, l3_cost_usd,
                    figures_extracted, errors, processing_time_sec
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    log_entry.execution_date,
                    json.dumps(log_entry.date_range),
                    log_entry.l1_raw_count,
                    log_entry.l1_dedup_count,
                    log_entry.l2_input_count,
                    log_entry.l2_passed_count,
                    log_entry.l2_pass_rate,
                    log_entry.l3_input_count,
                    log_entry.l3_relevant_count,
                    log_entry.l3_relevance_rate,
                    log_entry.l3_input_tokens,
                    log_entry.l3_output_tokens,
                    log_entry.l3_cost_usd,
                    log_entry.figures_extracted,
                    json.dumps(log_entry.errors),
                    log_entry.processing_time_sec,
                ),
            )
        await conn.commit()
    except Exception:
        logger.error("Failed to insert batch_log", exc_info=True)

    # クリーンアップ
    await close_connections()

    logger.info(
        "Pipeline completed",
        extra={
            "execution_date": today,
            "processing_time_sec": elapsed,
            "l1_dedup": l1_dedup_count,
            "l2_passed": l2_passed_count,
            "l3_relevant": l3_relevant_count,
            "figures": figures_extracted,
            "error_count": len(errors),
        },
    )

    return log_entry
