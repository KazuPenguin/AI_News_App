"""
初期データとして、関連度の高い有名な論文をAPIから取得し、
パイプラインを通してDBにシードデータを投入するスクリプト。
"""

import asyncio
import time

import requests
from dotenv import load_dotenv

from batch.config import (
    ARXIV_BASE_URL,
    ARXIV_MAX_RETRIES,
    ARXIV_QUERIES,
    ARXIV_RATE_LIMIT_SEC,
    ARXIV_TIMEOUT_SEC,
)
from batch.l1_collector import deduplicate, parse_entries
from batch.l2_selector import run_l2
from batch.l3_analyzer import run_l3
from batch.post_l3_reviewer import run_post_l3
from utils.db import close_connections, get_async_connection
from utils.logger import logger
from utils.models import ArxivPaper

load_dotenv()


def fetch_seed_papers(max_results_per_category: int = 70) -> list[ArxivPaper]:
    all_papers: list[ArxivPaper] = []

    for q in ARXIV_QUERIES:
        category_id = int(str(q["category_id"]))
        category_name = str(q["category_name"])
        query_template = str(q["query"])

        # 日付範囲指定を外して関連度順（sortBy=relevance）で取得
        search_query = query_template
        params = f"search_query={search_query}&start=0&max_results={max_results_per_category}"
        params += "&sortBy=relevance&sortOrder=descending"
        url = f"{ARXIV_BASE_URL}?{params}"

        xml_text = ""
        for attempt in range(ARXIV_MAX_RETRIES):
            try:
                response = requests.get(url, timeout=ARXIV_TIMEOUT_SEC)
                if response.status_code == 200:
                    xml_text = response.text
                    break
                if response.status_code == 503:
                    wait = ARXIV_RATE_LIMIT_SEC * (3**attempt)
                    time.sleep(wait)
                    continue
                break
            except requests.Timeout:
                if attempt < ARXIV_MAX_RETRIES - 1:
                    time.sleep(ARXIV_RATE_LIMIT_SEC)
            except requests.RequestException:
                break

        if xml_text:
            papers = parse_entries(xml_text, category_id)
            all_papers.extend(papers)
            logger.info(
                "Fetched papers from arXiv", extra={"category": category_name, "count": len(papers)}
            )

        time.sleep(ARXIV_RATE_LIMIT_SEC)

    return deduplicate(all_papers)


async def main() -> None:
    logger.info("Starting seed process...")

    # 1. 関連度の高い論文を取得 (各カテゴリ 70件目安 -> 重複排除後 300件強を想定)
    l1_papers = fetch_seed_papers(max_results_per_category=70)
    logger.info("L1 collection finished", extra={"deduped_count": len(l1_papers)})

    if not l1_papers:
        logger.warning("No papers fetched.")
        return

    # 2. L2 選別 (ベクトル生成・保存もここで行われる)
    try:
        l2_papers = run_l2(l1_papers)
    except Exception:
        logger.error("L2 failed", exc_info=True)
        return

    logger.info("L2 finished", extra={"passed_count": len(l2_papers)})
    if not l2_papers:
        return

    # 3. L3 分析 (Gemini 判定・要約)
    try:
        l3_papers, _, _ = await run_l3(l2_papers)
    except Exception:
        logger.error("L3 failed", exc_info=True)
        return

    logger.info("L3 finished", extra={"relevant_count": len(l3_papers)})
    if not l3_papers:
        return

    # Post-L3 のために summary_ja を再取得
    summaries: dict[str, str] = {}
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
            summaries = {str(r[0]): (str(r[1]) if r[1] else "") for r in rows}
    except Exception:
        logger.warning("Failed to fetch summaries", exc_info=True)

    # 4. Post-L3 (PDF全文分析・図表抽出)
    try:
        success_count, figures_extracted, post_errors = await run_post_l3(l3_papers, summaries)
        logger.info(
            "Post-L3 finished",
            extra={"success": success_count, "figures": figures_extracted},
        )
        if post_errors:
            logger.warning("Post-L3 errors", extra={"errors": post_errors})
    except Exception:
        logger.error("Post-L3 failed", exc_info=True)

    await close_connections()
    logger.info("Seed process completed.")


if __name__ == "__main__":
    asyncio.run(main())
