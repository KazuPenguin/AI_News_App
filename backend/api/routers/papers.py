"""論文エンドポイント。"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import CurrentUser, DbConn, get_current_user, get_db
from api.schemas import (
    PaperDetail,
    PaperDetailData,
    PaperFigure,
    PaperSummary,
    Pagination,
    ViewResponse,
)

router = APIRouter(prefix="/papers")


def _encode_cursor(published_at: datetime, paper_id: int) -> str:
    """published_at + id からカーソル文字列を生成する。"""
    payload = {"published_at": published_at.isoformat(), "id": paper_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    """カーソル文字列を published_at, id にデコードする。"""
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    return datetime.fromisoformat(payload["published_at"]), int(payload["id"])


@router.get("")
def list_papers(
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    category_id: int | None = Query(default=None, ge=1, le=6),
    importance: int | None = Query(default=None, ge=1, le=5),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    """GET /papers — 論文一覧（カーソルベースページネーション）"""
    query_conditions = ["p.is_relevant = TRUE", "p.detail_review IS NOT NULL"]
    query_params: list[Any] = []

    if category_id is not None:
        query_params.append(category_id)
        query_conditions.append("p.category_id = %s")
    if importance is not None:
        query_params.append(importance)
        query_conditions.append("p.importance = %s")
    if from_date is not None:
        query_params.append(from_date)
        query_conditions.append("p.published_at >= %s")
    if to_date is not None:
        query_params.append(to_date)
        query_conditions.append("p.published_at <= %s")
    if cursor is not None:
        cursor_dt, cursor_id = _decode_cursor(cursor)
        query_params.extend([cursor_dt, cursor_dt, cursor_id])
        query_conditions.append("(p.published_at < %s OR (p.published_at = %s AND p.id < %s))")

    query_params.append(user.user_id)
    query_params.append(user.user_id)
    query_params.append(limit + 1)

    where_clause_sql = " AND ".join(query_conditions)

    sql = f"""
        SELECT p.arxiv_id, p.title, p.category_id, a.category_name,
               p.importance, p.summary_ja,
               (p.detail_review->>'one_line_takeaway') AS one_line_takeaway,
               p.authors, p.published_at, p.id,
               EXISTS(SELECT 1 FROM bookmarks b
                      WHERE b.paper_id = p.id AND b.user_id = %s) AS is_bookmarked,
               EXISTS(SELECT 1 FROM paper_views pv
                      WHERE pv.paper_id = p.id AND pv.user_id = %s) AS is_viewed
        FROM papers p
        LEFT JOIN anchors a ON a.category_id = p.category_id
        WHERE {where_clause_sql}
        ORDER BY p.published_at DESC, p.id DESC
        LIMIT %s
    """

    with conn.cursor() as cur:
        cur.execute(sql, query_params)
        rows = cur.fetchall()

    has_next = len(rows) > limit
    if has_next:
        rows = rows[:limit]

    papers: list[dict[str, Any]] = []
    for row in rows:
        # サムネイル: paper_figures の figure_index=0 の s3_url を使う
        # ここでは簡易的に None
        papers.append(
            PaperSummary(
                arxiv_id=row[0],
                title=row[1],
                category_id=row[2],
                category_name=row[3],
                importance=row[4],
                summary_ja=row[5],
                one_line_takeaway=row[6],
                authors=row[7] if row[7] else [],
                published_at=row[8],
                thumbnail_url=None,
                is_bookmarked=row[10],
                is_viewed=row[11],
            ).model_dump(mode="json")
        )

    next_cursor = None
    if has_next and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last[8], last[9])

    # total_count
    count_sql = f"""
        SELECT COUNT(*) FROM papers p
        LEFT JOIN anchors a ON a.category_id = p.category_id
        WHERE {where_clause_sql}
    """
    # count クエリには user_id と limit は不要なので params を調整
    count_params = query_params[:-3]  # user_id x2 + limit を除去
    with conn.cursor() as cur:
        cur.execute(count_sql, count_params)
        count_row = cur.fetchone()
        total_count = count_row[0] if count_row else 0

    return {
        "data": papers,
        "pagination": Pagination(
            next_cursor=next_cursor,
            has_next=has_next,
            total_count=total_count,
        ).model_dump(),
    }


@router.get("/{arxiv_id}")
def get_paper_detail(
    arxiv_id: str,
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """GET /papers/{arxiv_id} — 論文詳細"""
    sql = """
        SELECT p.arxiv_id, p.title, p.abstract, p.authors, p.pdf_url,
               p.category_id, a.category_name, p.importance, p.published_at,
               p.summary_ja, p.detail_review,
               EXISTS(SELECT 1 FROM bookmarks b
                      WHERE b.paper_id = p.id AND b.user_id = %s) AS is_bookmarked,
               EXISTS(SELECT 1 FROM paper_views pv
                      WHERE pv.paper_id = p.id AND pv.user_id = %s) AS is_viewed
        FROM papers p
        LEFT JOIN anchors a ON a.category_id = p.category_id
        WHERE p.arxiv_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user.user_id, user.user_id, arxiv_id))
        row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PAPER_NOT_FOUND",
                "message": f"Paper with arxiv_id '{arxiv_id}' not found",
            },
        )

    detail_review = row[10]
    detail = None
    if detail_review:
        if isinstance(detail_review, str):
            detail_review = json.loads(detail_review)
        detail = PaperDetailData.model_validate(detail_review)

    paper = PaperDetail(
        arxiv_id=row[0],
        title=row[1],
        abstract=row[2],
        authors=row[3] if row[3] else [],
        pdf_url=row[4],
        category_id=row[5],
        category_name=row[6],
        importance=row[7],
        published_at=row[8],
        summary_ja=row[9],
        detail=detail,
        is_bookmarked=row[11],
        is_viewed=row[12],
    )

    return {"data": paper.model_dump(mode="json")}


@router.get("/{arxiv_id}/figures")
def get_paper_figures(
    arxiv_id: str,
    conn: Annotated[DbConn, Depends(get_db)],
    _user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """GET /papers/{arxiv_id}/figures — 論文の図表一覧"""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT pf.id, pf.figure_index, pf.s3_url, pf.width, pf.height, pf.caption
               FROM paper_figures pf
               JOIN papers p ON p.id = pf.paper_id
               WHERE p.arxiv_id = %s
               ORDER BY pf.figure_index""",
            (arxiv_id,),
        )
        rows = cur.fetchall()

    figures = [
        PaperFigure(
            id=row[0],
            figure_index=row[1],
            s3_url=row[2],
            width=row[3],
            height=row[4],
            caption=row[5],
        ).model_dump(mode="json")
        for row in rows
    ]

    return {"data": figures}


@router.post("/{arxiv_id}/view", status_code=201)
def record_view(
    arxiv_id: str,
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """POST /papers/{arxiv_id}/view — 閲覧記録 UPSERT"""
    with conn.cursor() as cur:
        # まず paper_id を取得
        cur.execute("SELECT id FROM papers WHERE arxiv_id = %s", (arxiv_id,))
        paper_row = cur.fetchone()
        if not paper_row:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "PAPER_NOT_FOUND",
                    "message": f"Paper with arxiv_id '{arxiv_id}' not found",
                },
            )
        paper_id: int = paper_row[0]

        # UPSERT
        cur.execute(
            """INSERT INTO paper_views (user_id, paper_id)
               VALUES (%s, %s)
               ON CONFLICT (user_id, paper_id) DO NOTHING
               RETURNING viewed_at""",
            (user.user_id, paper_id),
        )
        result = cur.fetchone()
        if result:
            # 新規作成
            conn.commit()
            return {"data": ViewResponse(viewed_at=result[0]).model_dump(mode="json")}

        # 既存 → viewed_at を取得
        cur.execute(
            "SELECT viewed_at FROM paper_views WHERE user_id = %s AND paper_id = %s",
            (user.user_id, paper_id),
        )
        existing = cur.fetchone()
        viewed_at = existing[0] if existing else datetime.now()
        return {"data": ViewResponse(viewed_at=viewed_at).model_dump(mode="json")}
