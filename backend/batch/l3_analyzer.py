"""
AI Research OS — L3: Gemini LLM 分析

L2通過論文に対して Gemini 2.0 Flash でJSON Mode分析を行い、
適合判定・カテゴリ分類・日本語要約・重要度判定を生成する。
5並列、200ms間隔、指数バックオフ付き。
"""

from __future__ import annotations

import asyncio
import json

from google import genai
from google.genai import types

from batch.config import (
    CATEGORY_NAMES,
    GEMINI_MODEL,
    L3_CONCURRENCY,
    L3_MAX_OUTPUT_TOKENS,
    L3_MAX_RETRIES,
    L3_REQUEST_INTERVAL_MS,
    L3_SYSTEM_PROMPT,
    L3_TEMPERATURE,
    L3_USER_PROMPT_TEMPLATE,
    BACKOFF_BASE_SEC,
)
from utils.db import get_async_connection
from utils.logger import logger
from utils.models import L2Paper, L3Response
from utils.secrets import get_gemini_api_key


# ---------------------------------------------------------------------------
# プロンプト構築
# ---------------------------------------------------------------------------
def build_l3_prompt(paper: L2Paper) -> str:
    """L3分析用のユーザープロンプトを構築する。"""
    category_name = CATEGORY_NAMES.get(paper.best_category_id, "Unknown")
    return L3_USER_PROMPT_TEMPLATE.format(
        title=paper.title,
        abstract=paper.abstract,
        best_category_id=paper.best_category_id,
        category_name=category_name,
        max_score=paper.max_score,
        hit_count=paper.hit_count,
    )


# ---------------------------------------------------------------------------
# Gemini API 呼び出し (1論文)
# ---------------------------------------------------------------------------
async def _call_gemini(
    client: genai.Client,
    paper: L2Paper,
) -> L3Response | None:
    """Gemini API を呼び出して L3Response を取得する。指数バックオフ付きリトライ。"""
    user_prompt = build_l3_prompt(paper)

    for attempt in range(L3_MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=L3_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=L3_TEMPERATURE,
                    max_output_tokens=L3_MAX_OUTPUT_TOKENS,
                ),
            )

            if response.text is None:
                logger.warning(
                    "L3 empty response",
                    extra={"arxiv_id": paper.arxiv_id, "attempt": attempt + 1},
                )
                continue

            parsed = json.loads(response.text)
            return L3Response(**parsed)

        except json.JSONDecodeError:
            logger.warning(
                "L3 JSON parse error",
                extra={"arxiv_id": paper.arxiv_id, "attempt": attempt + 1},
            )
        except Exception:
            wait = BACKOFF_BASE_SEC * (2**attempt)
            logger.warning(
                "L3 API error, retrying",
                extra={
                    "arxiv_id": paper.arxiv_id,
                    "attempt": attempt + 1,
                    "wait_sec": wait,
                },
                exc_info=True,
            )
            await asyncio.sleep(wait)

    logger.error("L3 all retries failed", extra={"arxiv_id": paper.arxiv_id})
    return None


# ---------------------------------------------------------------------------
# DB 更新 (L3結果)
# ---------------------------------------------------------------------------
async def _update_l3_result(arxiv_id: str, result: L3Response) -> None:
    """L3結果を papers テーブルに反映する。"""
    conn = await get_async_connection()
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE papers SET
                is_relevant = %s,
                category_id = %s,
                confidence = %s,
                importance = %s,
                summary_ja = %s,
                reasoning = %s,
                updated_at = NOW()
            WHERE arxiv_id = %s
            """,
            (
                result.is_relevant,
                result.category_id,
                result.confidence,
                result.importance,
                result.summary_ja,
                result.reasoning,
                arxiv_id,
            ),
        )
    await conn.commit()


# ---------------------------------------------------------------------------
# 1論文の処理 (セマフォ付き)
# ---------------------------------------------------------------------------
async def _process_paper(
    client: genai.Client,
    paper: L2Paper,
    semaphore: asyncio.Semaphore,
) -> tuple[str, L3Response | None]:
    """セマフォで並列数を制限しつつ、1論文を L3 分析する。"""
    async with semaphore:
        # リクエスト間隔
        await asyncio.sleep(L3_REQUEST_INTERVAL_MS / 1000)

        result = await _call_gemini(client, paper)
        if result is not None:
            await _update_l3_result(paper.arxiv_id, result)

        return paper.arxiv_id, result


# ---------------------------------------------------------------------------
# メイン: L3 分析
# ---------------------------------------------------------------------------
async def run_l3(papers: list[L2Paper]) -> list[L2Paper]:
    """L3: Gemini LLM 分析を実行する。

    Args:
        papers: L2 を通過した論文リスト

    Returns:
        L3 で is_relevant=True と判定された論文リスト
    """
    if not papers:
        logger.info("L3: No papers to process")
        return []

    logger.info("L3 analysis started", extra={"input_count": len(papers)})

    client = genai.Client(api_key=get_gemini_api_key())
    semaphore = asyncio.Semaphore(L3_CONCURRENCY)

    tasks = [_process_paper(client, p, semaphore) for p in papers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 結果集計
    relevant_papers: list[L2Paper] = []
    errors: list[str] = []
    paper_map = {p.arxiv_id: p for p in papers}

    for r in results:
        if isinstance(r, BaseException):
            errors.append(str(r))
            continue
        arxiv_id, l3_result = r
        if l3_result is not None and l3_result.is_relevant:
            paper = paper_map.get(arxiv_id)
            if paper is not None:
                relevant_papers.append(paper)

    logger.info(
        "L3 analysis completed",
        extra={
            "input_count": len(papers),
            "relevant_count": len(relevant_papers),
            "rejected_count": len(papers) - len(relevant_papers) - len(errors),
            "error_count": len(errors),
        },
    )

    return relevant_papers
