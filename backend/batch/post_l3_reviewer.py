"""
AI Research OS — Post-L3: PDF 全文分析 & 図表抽出

L3通過論文に対して:
1. PDF ダウンロード
2. Gemini 2.0 Flash で PDF 全文分析 (詳細解説生成)
3. PyMuPDF で図表抽出 → S3 アップロード
を3並列で実行する。
"""

from __future__ import annotations

import asyncio
import json
import os

import boto3
import fitz  # PyMuPDF
import httpx
from google import genai
from google.genai import types

from batch.config import (
    BACKOFF_BASE_SEC,
    CATEGORY_NAMES,
    FIGURE_MIN_HEIGHT,
    FIGURE_MIN_WIDTH,
    FIGURE_S3_PREFIX,
    GEMINI_MODEL,
    POST_L3_CONCURRENCY,
    POST_L3_MAX_OUTPUT_TOKENS,
    POST_L3_MAX_RETRIES,
    POST_L3_SYSTEM_PROMPT,
    POST_L3_TEMPERATURE,
    POST_L3_USER_PROMPT_TEMPLATE,
)
from utils.db import get_async_connection
from utils.logger import logger
from utils.models import DetailReview, ExtractedFigure, L2Paper
from utils.secrets import get_gemini_api_key


# ---------------------------------------------------------------------------
# PDF ダウンロード
# ---------------------------------------------------------------------------
async def download_pdf(pdf_url: str) -> bytes | None:
    """arXiv から PDF をダウンロードする。リトライ1回。"""
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()
                return response.content
        except Exception:
            logger.warning(
                "PDF download failed",
                extra={"url": pdf_url, "attempt": attempt + 1},
                exc_info=True,
            )
            if attempt == 0:
                await asyncio.sleep(2.0)
    return None


# ---------------------------------------------------------------------------
# Gemini PDF 全文分析
# ---------------------------------------------------------------------------
async def _generate_detail_review(
    client: genai.Client,
    paper: L2Paper,
    pdf_bytes: bytes,
    summary_ja: str,
) -> DetailReview | None:
    """Gemini 2.0 Flash で PDF 全文を分析し DetailReview を生成する。"""
    category_name = CATEGORY_NAMES.get(paper.best_category_id, "Unknown")
    user_prompt = POST_L3_USER_PROMPT_TEMPLATE.format(
        title=paper.title,
        arxiv_id=paper.arxiv_id,
        category_name=category_name,
        category_id=paper.best_category_id,
        importance_score=paper.importance_score,
        summary_ja=summary_ja,
    )

    for attempt in range(POST_L3_MAX_RETRIES):
        try:
            # PDF を Part として送信
            pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

            response = await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=[pdf_part, user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=POST_L3_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=POST_L3_TEMPERATURE,
                    max_output_tokens=POST_L3_MAX_OUTPUT_TOKENS,
                ),
            )

            if response.text is None:
                logger.warning(
                    "Post-L3 empty response",
                    extra={"arxiv_id": paper.arxiv_id, "attempt": attempt + 1},
                )
                continue

            parsed = json.loads(response.text)
            return DetailReview(**parsed)

        except json.JSONDecodeError:
            logger.warning(
                "Post-L3 JSON parse error",
                extra={"arxiv_id": paper.arxiv_id, "attempt": attempt + 1},
            )
        except Exception:
            wait = BACKOFF_BASE_SEC * (2**attempt)
            logger.warning(
                "Post-L3 API error, retrying",
                extra={
                    "arxiv_id": paper.arxiv_id,
                    "attempt": attempt + 1,
                    "wait_sec": wait,
                },
                exc_info=True,
            )
            await asyncio.sleep(wait)

    logger.error("Post-L3 all retries failed", extra={"arxiv_id": paper.arxiv_id})
    return None


# ---------------------------------------------------------------------------
# 図表抽出 (PyMuPDF) → S3 アップロード
# ---------------------------------------------------------------------------
def _extract_figures_from_pdf(
    arxiv_id: str,
    pdf_bytes: bytes,
) -> list[ExtractedFigure]:
    """PyMuPDF で PDF から画像を抽出する。"""
    figures: list[ExtractedFigure] = []
    bucket_name = os.environ.get("FIGURE_BUCKET", "")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        logger.error("Failed to open PDF", extra={"arxiv_id": arxiv_id}, exc_info=True)
        return figures

    s3_client = boto3.client("s3", region_name="ap-northeast-1")
    figure_index = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            width = base_image.get("width", 0)
            height = base_image.get("height", 0)
            image_bytes: bytes = base_image.get("image", b"")
            ext = base_image.get("ext", "png")

            # 小さすぎる画像 (アイコン等) をスキップ
            if width < FIGURE_MIN_WIDTH or height < FIGURE_MIN_HEIGHT:
                continue

            s3_key = f"{FIGURE_S3_PREFIX}{arxiv_id}/fig_{figure_index}.{ext}"

            # S3 アップロード
            if bucket_name:
                try:
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=image_bytes,
                        ContentType=f"image/{ext}",
                    )
                except Exception:
                    logger.warning(
                        "S3 upload failed",
                        extra={"s3_key": s3_key},
                        exc_info=True,
                    )
                    continue

            # CloudFront URL は環境変数から構築
            cdn_domain = os.environ.get("CDN_DOMAIN", "")
            s3_url = f"https://{cdn_domain}/{s3_key}" if cdn_domain else s3_key

            figures.append(
                ExtractedFigure(
                    figure_index=figure_index,
                    s3_key=s3_key,
                    s3_url=s3_url,
                    width=width,
                    height=height,
                    file_size_bytes=len(image_bytes),
                )
            )
            figure_index += 1

    doc.close()
    return figures


async def extract_and_upload_figures(
    arxiv_id: str,
    pdf_bytes: bytes,
) -> list[ExtractedFigure]:
    """図表抽出を非同期ラッパーで実行する (CPU処理のためスレッドプールで)。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_figures_from_pdf, arxiv_id, pdf_bytes)


# ---------------------------------------------------------------------------
# DB 更新
# ---------------------------------------------------------------------------
async def _update_paper_detail(arxiv_id: str, review: DetailReview) -> None:
    """詳細解説を papers テーブルに保存する。"""
    conn = await get_async_connection()
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE papers SET
                detail_review = %s,
                updated_at = NOW()
            WHERE arxiv_id = %s
            """,
            (json.dumps(review.model_dump(), ensure_ascii=False), arxiv_id),
        )
    await conn.commit()


async def _insert_paper_figures(
    arxiv_id: str,
    figures: list[ExtractedFigure],
) -> None:
    """抽出した図表を paper_figures テーブルに挿入する。"""
    if not figures:
        return

    conn = await get_async_connection()
    async with conn.cursor() as cur:
        # まず paper_id を取得
        await cur.execute("SELECT id FROM papers WHERE arxiv_id = %s", (arxiv_id,))
        row = await cur.fetchone()
        if row is None:
            logger.warning("Paper not found for figures", extra={"arxiv_id": arxiv_id})
            return
        paper_id: int = row[0]

        for fig in figures:
            await cur.execute(
                """
                INSERT INTO paper_figures (
                    paper_id, figure_index, s3_key, s3_url,
                    width, height, file_size_bytes, caption
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id, figure_index) DO UPDATE SET
                    s3_key = EXCLUDED.s3_key,
                    s3_url = EXCLUDED.s3_url,
                    width = EXCLUDED.width,
                    height = EXCLUDED.height,
                    file_size_bytes = EXCLUDED.file_size_bytes
                """,
                (
                    paper_id,
                    fig.figure_index,
                    fig.s3_key,
                    fig.s3_url,
                    fig.width,
                    fig.height,
                    fig.file_size_bytes,
                    fig.caption,
                ),
            )
    await conn.commit()


# ---------------------------------------------------------------------------
# 1論文の処理 (PDF分析 + 図表抽出 並列)
# ---------------------------------------------------------------------------
async def _process_relevant_paper(
    client: genai.Client,
    paper: L2Paper,
    summary_ja: str,
) -> tuple[DetailReview | None, list[ExtractedFigure]]:
    """L3通過論文に対する後処理: PDF分析 + 図表抽出を並列実行。"""
    # PDF ダウンロード
    pdf_bytes = await download_pdf(paper.pdf_url or "")
    if pdf_bytes is None:
        logger.warning("PDF download failed, skipping", extra={"arxiv_id": paper.arxiv_id})
        return None, []

    # 並列実行: Gemini分析 & PyMuPDF図表抽出
    analysis_task = asyncio.create_task(
        _generate_detail_review(client, paper, pdf_bytes, summary_ja)
    )
    figures_task = asyncio.create_task(extract_and_upload_figures(paper.arxiv_id, pdf_bytes))

    detail_review, figures = await asyncio.gather(analysis_task, figures_task)

    # DB更新
    if detail_review is not None:
        await _update_paper_detail(paper.arxiv_id, detail_review)
    await _insert_paper_figures(paper.arxiv_id, figures)

    return detail_review, figures


# ---------------------------------------------------------------------------
# メイン: Post-L3 バッチ実行
# ---------------------------------------------------------------------------
async def run_post_l3(
    papers: list[L2Paper],
    summaries: dict[str, str] | None = None,
) -> tuple[int, int, list[str]]:
    """Post-L3: PDF全文分析 + 図表抽出を実行する。

    Args:
        papers: L3 で is_relevant=True と判定された論文リスト
        summaries: arxiv_id → summary_ja のマッピング (L3結果から)

    Returns:
        (成功数, 図表抽出総数, エラーリスト) のタプル
    """
    if not papers:
        logger.info("Post-L3: No papers to process")
        return 0, 0, []

    logger.info("Post-L3 review started", extra={"input_count": len(papers)})

    client = genai.Client(api_key=get_gemini_api_key())
    semaphore = asyncio.Semaphore(POST_L3_CONCURRENCY)
    summaries = summaries or {}

    async def process_with_limit(
        paper: L2Paper,
    ) -> tuple[DetailReview | None, list[ExtractedFigure]]:
        async with semaphore:
            summary_ja = summaries.get(paper.arxiv_id, "")
            return await _process_relevant_paper(client, paper, summary_ja)

    tasks = [process_with_limit(p) for p in papers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 集計
    success_count = 0
    total_figures = 0
    errors: list[str] = []

    for r in results:
        if isinstance(r, BaseException):
            errors.append(str(r))
            continue
        review, figures = r
        if review is not None:
            success_count += 1
        total_figures += len(figures)

    logger.info(
        "Post-L3 review completed",
        extra={
            "input_count": len(papers),
            "success_count": success_count,
            "figures_extracted": total_figures,
            "error_count": len(errors),
        },
    )

    return success_count, total_figures, errors
