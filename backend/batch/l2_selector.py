"""
AI Research OS — L2: pgvector ベクトル選別

OpenAI Embedding で論文ベクトルを生成し、DB に挿入後、
アンカーベクトルとのコサイン類似度で選別する。
"""

from __future__ import annotations

from openai import OpenAI

from batch.config import (
    ANCHOR_COUNT,
    EMBEDDING_MODEL,
    IMPORTANCE_WEIGHT_HIT_COUNT,
    IMPORTANCE_WEIGHT_MATCHED_QUERIES,
    IMPORTANCE_WEIGHT_MAX_SCORE,
    L2_THRESHOLD,
)
from utils.db import get_sync_connection
from utils.logger import logger
from utils.models import ArxivPaper, L2Paper, L2Result
from utils.secrets import get_openai_api_key


# ---------------------------------------------------------------------------
# Embedding 生成 (バッチ)
# ---------------------------------------------------------------------------
def _generate_embeddings(
    papers: list[ArxivPaper],
    client: OpenAI,
) -> list[list[float]]:
    """Title + Abstract を結合して Embedding を一括生成する。

    OpenAI Embedding API はバッチ入力をサポートしているため、
    1回の API コールで全論文の Embedding を取得する。
    """
    texts = [f"{p.title} {p.abstract}" for p in papers]

    # OpenAI API のバッチ上限 (2048) を超える場合は分割
    batch_size = 2048
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(input=batch, model=EMBEDDING_MODEL)
        all_embeddings.extend([d.embedding for d in response.data])

    return all_embeddings


# ---------------------------------------------------------------------------
# DB 挿入 (papers テーブル)
# ---------------------------------------------------------------------------
def _insert_papers(
    papers: list[ArxivPaper],
    embeddings: list[list[float]],
) -> None:
    """論文メタデータと Embedding を papers テーブルに INSERT する。

    重複 (arxiv_id UNIQUE制約) は ON CONFLICT DO NOTHING でスキップ。
    """
    conn = get_sync_connection()
    with conn.cursor() as cur:
        for paper, embedding in zip(papers, embeddings):
            cur.execute(
                """
                INSERT INTO papers (
                    arxiv_id, title, abstract, authors, pdf_url,
                    primary_category, all_categories, published_at,
                    matched_queries, embedding
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (arxiv_id) DO UPDATE SET
                    matched_queries = (
                        SELECT ARRAY(
                            SELECT DISTINCT unnest(
                                papers.matched_queries || EXCLUDED.matched_queries
                            )
                        )
                    ),
                    updated_at = NOW()
                """,
                (
                    paper.arxiv_id,
                    paper.title,
                    paper.abstract,
                    paper.authors,
                    paper.pdf_url,
                    paper.primary_category,
                    paper.all_categories,
                    paper.published_at,
                    paper.matched_queries,
                    str(embedding),
                ),
            )
    conn.commit()


# ---------------------------------------------------------------------------
# L2 スコアリング (pgvector)
# ---------------------------------------------------------------------------
def _compute_l2_scores(papers: list[ArxivPaper]) -> list[L2Result]:
    """全アンカーとのコサイン類似度を計算し、L2結果を返す。"""
    conn = get_sync_connection()
    results: list[L2Result] = []

    with conn.cursor() as cur:
        for paper in papers:
            # 全アンカーとの類似度を計算
            cur.execute(
                """
                SELECT
                    a.category_id,
                    1 - (p.embedding <=> a.embedding) AS cosine_similarity
                FROM papers p
                CROSS JOIN anchors a
                WHERE p.arxiv_id = %s AND a.is_active = TRUE
                ORDER BY a.category_id
                """,
                (paper.arxiv_id,),
            )
            rows = cur.fetchall()

            if not rows:
                logger.warning(
                    "No anchor scores for paper",
                    extra={"arxiv_id": paper.arxiv_id},
                )
                continue

            all_scores: dict[str, float] = {}
            scores: list[float] = []
            for row in rows:
                cat_id = int(row[0])
                score = float(row[1])
                all_scores[str(cat_id)] = round(score, 4)
                scores.append(score)

            max_score = max(scores)
            best_category_id = int(rows[scores.index(max_score)][0])
            hit_count = sum(1 for s in scores if s >= L2_THRESHOLD)
            matched_queries_count = len(paper.matched_queries)

            # importance_score の算出
            importance_score = (
                IMPORTANCE_WEIGHT_MAX_SCORE * max_score
                + IMPORTANCE_WEIGHT_HIT_COUNT * (hit_count / ANCHOR_COUNT)
                + IMPORTANCE_WEIGHT_MATCHED_QUERIES * (matched_queries_count / ANCHOR_COUNT)
            )

            passed = max_score >= L2_THRESHOLD

            results.append(
                L2Result(
                    arxiv_id=paper.arxiv_id,
                    max_score=round(max_score, 4),
                    best_category_id=best_category_id,
                    hit_count=hit_count,
                    importance_score=round(importance_score, 4),
                    all_scores=all_scores,
                    passed=passed,
                )
            )

    return results


# ---------------------------------------------------------------------------
# L2 結果を DB に更新
# ---------------------------------------------------------------------------
def _update_l2_results(results: list[L2Result]) -> None:
    """L2結果を papers テーブルに反映する。"""
    conn = get_sync_connection()
    with conn.cursor() as cur:
        for r in results:
            cur.execute(
                """
                UPDATE papers SET
                    best_category_id = %s,
                    max_score = %s,
                    hit_count = %s,
                    importance_score = %s,
                    all_scores = %s,
                    updated_at = NOW()
                WHERE arxiv_id = %s
                """,
                (
                    r.best_category_id,
                    r.max_score,
                    r.hit_count,
                    r.importance_score,
                    str(r.all_scores),  # JSONB として文字列化
                    r.arxiv_id,
                ),
            )
    conn.commit()


# ---------------------------------------------------------------------------
# L2 通過論文を L2Paper として返す
# ---------------------------------------------------------------------------
def _build_l2_papers(
    papers: list[ArxivPaper],
    results: list[L2Result],
) -> list[L2Paper]:
    """L2 を通過した論文を L2Paper オブジェクトとして構築する。"""
    paper_map = {p.arxiv_id: p for p in papers}
    l2_papers: list[L2Paper] = []

    for r in results:
        if not r.passed:
            continue
        p = paper_map.get(r.arxiv_id)
        if p is None:
            continue
        l2_papers.append(
            L2Paper(
                **p.model_dump(),
                best_category_id=r.best_category_id,
                max_score=r.max_score,
                hit_count=r.hit_count,
                importance_score=r.importance_score,
                all_scores=r.all_scores,
            )
        )

    return l2_papers


# ---------------------------------------------------------------------------
# メイン: L2 選別
# ---------------------------------------------------------------------------
def run_l2(papers: list[ArxivPaper]) -> list[L2Paper]:
    """L2: ベクトル選別を実行する。

    1. OpenAI Embedding を一括生成
    2. papers テーブルに INSERT
    3. pgvector でアンカーとのコサイン類似度を計算
    4. 閾値以上の論文を L2Paper として返す

    Args:
        papers: L1 で取得した論文リスト

    Returns:
        L2 を通過した L2Paper リスト
    """
    if not papers:
        logger.info("L2: No papers to process")
        return []

    logger.info("L2 selection started", extra={"input_count": len(papers)})

    # 1. Embedding 生成
    client = OpenAI(api_key=get_openai_api_key())
    embeddings = _generate_embeddings(papers, client)

    # 2. DB 挿入
    _insert_papers(papers, embeddings)

    # 3. L2 スコアリング
    results = _compute_l2_scores(papers)

    # 4. L2 結果を DB 更新
    _update_l2_results(results)

    # 5. 通過論文を構築
    passed = _build_l2_papers(papers, results)
    rejected = len(results) - len(passed)

    logger.info(
        "L2 selection completed",
        extra={
            "input_count": len(papers),
            "passed_count": len(passed),
            "rejected_count": rejected,
            "pass_rate": round(len(passed) / len(papers) * 100, 1) if papers else 0,
        },
    )

    return passed
