"""
AI Research OS — L1: arXiv API データ収集

6カテゴリのクエリを順次実行し、Atom XML をパースして ArxivPaper リストを返す。
3秒間隔のレートリミットを遵守し、重複排除を行う。
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

from batch.config import (
    ARXIV_BASE_URL,
    ARXIV_MAX_RETRIES,
    ARXIV_QUERIES,
    ARXIV_RATE_LIMIT_SEC,
    ARXIV_TIMEOUT_SEC,
)
from utils.logger import logger
from utils.models import ArxivPaper

# ---------------------------------------------------------------------------
# XML 名前空間
# ---------------------------------------------------------------------------
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


# ---------------------------------------------------------------------------
# 日付範囲の計算
# ---------------------------------------------------------------------------
def compute_date_range() -> tuple[str, str]:
    """前日 UTC 00:00 〜 当日 UTC 00:00 の日付範囲を返す。

    Returns:
        (start, end) タプル。YYYYMMDD0000 形式。
    """
    now_utc = datetime.now(timezone.utc)
    today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    start = yesterday.strftime("%Y%m%d0000")
    end = today.strftime("%Y%m%d0000")
    return start, end


# ---------------------------------------------------------------------------
# arXiv ID の抽出
# ---------------------------------------------------------------------------
def extract_arxiv_id(id_url: str) -> str:
    """arXiv URL から ID を抽出する。

    Args:
        id_url: "http://arxiv.org/abs/2402.12345v1" 形式

    Returns:
        "2402.12345" 形式の ID (バージョン番号を除去)
    """
    # URLの末尾から ID を取得し、バージョン番号 (vN) を除去
    match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?$", id_url)
    if match:
        return match.group(1)
    # 旧形式 ID のフォールバック (例: hep-ph/0601001)
    match = re.search(r"([a-z-]+/\d{7})(v\d+)?$", id_url)
    if match:
        return match.group(1)
    return id_url.split("/")[-1]


# ---------------------------------------------------------------------------
# XML パース
# ---------------------------------------------------------------------------
def parse_entries(xml_text: str, category_id: int) -> list[ArxivPaper]:
    """Atom XML レスポンスから論文エントリーをパースする。

    Args:
        xml_text: arXiv API の XML レスポンス本文
        category_id: このクエリのカテゴリID

    Returns:
        パースされた ArxivPaper のリスト
    """
    papers: list[ArxivPaper] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.error("XML parse error", extra={"category_id": category_id})
        return papers

    for entry in root.findall("atom:entry", NS):
        try:
            paper = _parse_single_entry(entry, category_id)
            if paper is not None:
                papers.append(paper)
        except Exception:
            logger.warning(
                "Failed to parse entry",
                extra={"category_id": category_id},
                exc_info=True,
            )
    return papers


def _parse_single_entry(entry: ET.Element, category_id: int) -> ArxivPaper | None:
    """1つの Atom entry 要素をパースする。"""
    id_elem = entry.find("atom:id", NS)
    if id_elem is None or id_elem.text is None:
        return None

    arxiv_id = extract_arxiv_id(id_elem.text)

    title_elem = entry.find("atom:title", NS)
    title = _normalize_text(title_elem.text if title_elem is not None and title_elem.text else "")

    summary_elem = entry.find("atom:summary", NS)
    abstract = _normalize_text(
        summary_elem.text if summary_elem is not None and summary_elem.text else ""
    )

    # 著者
    authors = []
    for author_elem in entry.findall("atom:author", NS):
        name_elem = author_elem.find("atom:name", NS)
        if name_elem is not None and name_elem.text:
            authors.append(name_elem.text)

    # PDF URL
    pdf_url: str | None = None
    for link_elem in entry.findall("atom:link", NS):
        if link_elem.get("title") == "pdf":
            pdf_url = link_elem.get("href")
            break

    # 発行日
    published_elem = entry.find("atom:published", NS)
    published_text = (
        published_elem.text if published_elem is not None and published_elem.text else ""
    )
    published_at = _parse_datetime(published_text)

    # カテゴリ
    primary_cat_elem = entry.find("arxiv:primary_category", NS)
    primary_category = (
        primary_cat_elem.get("term", "unknown") if primary_cat_elem is not None else "unknown"
    )

    all_categories = []
    for cat_elem in entry.findall("atom:category", NS):
        term = cat_elem.get("term")
        if term:
            all_categories.append(term)

    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        pdf_url=pdf_url,
        primary_category=primary_category,
        all_categories=all_categories,
        published_at=published_at,
        matched_queries=[category_id],
    )


def _normalize_text(text: str) -> str:
    """改行・余分な空白を正規化する。"""
    return re.sub(r"\s+", " ", text).strip()


def _parse_datetime(text: str) -> datetime:
    """ISO 8601 形式の日付文字列をパースする。"""
    if not text:
        return datetime.now(timezone.utc)
    # arXiv の形式: "2026-02-11T12:00:00Z"
    text = text.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 単一クエリ実行
# ---------------------------------------------------------------------------
def _fetch_query(
    query_template: str,
    max_results: int,
    start_date: str,
    end_date: str,
) -> str:
    """arXiv API に1回リクエストを送信する。リトライ付き。"""
    search_query = f"{query_template}+AND+submittedDate:[{start_date}+TO+{end_date}]"
    params = f"search_query={search_query}&start=0&max_results={max_results}"
    params += "&sortBy=submittedDate&sortOrder=descending"
    url = f"{ARXIV_BASE_URL}?{params}"

    for attempt in range(ARXIV_MAX_RETRIES):
        try:
            response = requests.get(url, timeout=ARXIV_TIMEOUT_SEC)
            if response.status_code == 200:
                return response.text
            if response.status_code == 503:
                wait = ARXIV_RATE_LIMIT_SEC * (3**attempt)
                logger.warning(
                    "arXiv 503, retrying",
                    extra={"attempt": attempt + 1, "wait_sec": wait},
                )
                time.sleep(wait)
                continue
            logger.error(
                "arXiv API error",
                extra={"status_code": response.status_code, "url": url[:200]},
            )
            return ""
        except requests.Timeout:
            logger.warning("arXiv timeout", extra={"attempt": attempt + 1})
            if attempt < ARXIV_MAX_RETRIES - 1:
                time.sleep(ARXIV_RATE_LIMIT_SEC)
        except requests.RequestException:
            logger.error("arXiv request failed", exc_info=True)
            return ""
    return ""


# ---------------------------------------------------------------------------
# 重複排除
# ---------------------------------------------------------------------------
def deduplicate(papers: list[ArxivPaper]) -> list[ArxivPaper]:
    """arXiv ID で重複排除し、matched_queries をマージする。"""
    seen: dict[str, ArxivPaper] = {}
    for paper in papers:
        if paper.arxiv_id not in seen:
            seen[paper.arxiv_id] = paper
        else:
            # matched_queries をマージ
            existing = seen[paper.arxiv_id]
            merged_queries = list(set(existing.matched_queries + paper.matched_queries))
            seen[paper.arxiv_id] = existing.model_copy(update={"matched_queries": merged_queries})
    return list(seen.values())


# ---------------------------------------------------------------------------
# メイン: 6クエリ実行 → 重複排除
# ---------------------------------------------------------------------------
def collect_papers() -> list[ArxivPaper]:
    """L1: arXiv API から論文を収集する。

    6カテゴリのクエリを順次実行し、重複排除後のリストを返す。

    Returns:
        重複排除済みの ArxivPaper リスト
    """
    start_date, end_date = compute_date_range()
    logger.info(
        "L1 collection started",
        extra={"start": start_date, "end": end_date},
    )

    all_papers: list[ArxivPaper] = []
    query_stats: list[dict[str, object]] = []

    for q in ARXIV_QUERIES:
        category_id = int(q["category_id"])
        category_name = str(q["category_name"])
        query_template = str(q["query"])
        max_results = int(q["max_results"])

        xml_text = _fetch_query(query_template, max_results, start_date, end_date)
        papers = parse_entries(xml_text, category_id) if xml_text else []

        query_stats.append(
            {
                "category": category_name,
                "raw_count": len(papers),
            }
        )

        all_papers.extend(papers)

        # レートリミット遵守
        time.sleep(ARXIV_RATE_LIMIT_SEC)

    # 重複排除
    total_raw = len(all_papers)
    deduped = deduplicate(all_papers)

    logger.info(
        "L1 collection completed",
        extra={
            "total_raw": total_raw,
            "after_dedup": len(deduped),
            "date_range": {"start": start_date, "end": end_date},
            "queries": query_stats,
        },
    )

    return deduped
