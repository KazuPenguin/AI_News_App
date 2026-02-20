"""ブックマークエンドポイント。"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.dependencies import CurrentUser, DbConn, get_current_user, get_db
from api.schemas import Bookmark, BookmarkPaper, CreateBookmarkRequest, Pagination

router = APIRouter(prefix="/bookmarks")


def _encode_cursor(created_at: datetime, bookmark_id: int) -> str:
    payload = {"created_at": created_at.isoformat(), "id": bookmark_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    return datetime.fromisoformat(payload["created_at"]), int(payload["id"])


@router.get("")
def list_bookmarks(
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    """GET /bookmarks — ブックマーク一覧（カーソルページネーション）"""
    conditions = ["bk.user_id = %s"]
    params: list[Any] = [user.user_id]

    if cursor is not None:
        cursor_dt, cursor_id = _decode_cursor(cursor)
        params.extend([cursor_dt, cursor_dt, cursor_id])
        conditions.append("(bk.created_at < %s OR (bk.created_at = %s AND bk.id < %s))")

    where_clause = " AND ".join(conditions)
    params.append(limit + 1)

    sql = f"""
        SELECT bk.id, bk.created_at,
               p.arxiv_id, p.title, p.category_id, a.category_name,
               p.importance, p.summary_ja
        FROM bookmarks bk
        JOIN papers p ON p.id = bk.paper_id
        LEFT JOIN anchors a ON a.category_id = p.category_id
        WHERE {where_clause}
        ORDER BY bk.created_at DESC, bk.id DESC
        LIMIT %s
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    has_next = len(rows) > limit
    if has_next:
        rows = rows[:limit]

    bookmarks = [
        Bookmark(
            bookmark_id=row[0],
            bookmarked_at=row[1],
            paper=BookmarkPaper(
                arxiv_id=row[2],
                title=row[3],
                category_id=row[4],
                category_name=row[5],
                importance=row[6],
                summary_ja=row[7],
            ),
        ).model_dump(mode="json")
        for row in rows
    ]

    next_cursor = None
    if has_next and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last[1], last[0])

    return {
        "data": bookmarks,
        "pagination": Pagination(
            next_cursor=next_cursor,
            has_next=has_next,
        ).model_dump(),
    }


@router.post("", status_code=201)
def add_bookmark(
    body: CreateBookmarkRequest,
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """POST /bookmarks — ブックマーク追加"""
    with conn.cursor() as cur:
        # paper_id 取得
        cur.execute("SELECT id FROM papers WHERE arxiv_id = %s", (body.arxiv_id,))
        paper_row = cur.fetchone()
        if not paper_row:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "PAPER_NOT_FOUND",
                    "message": f"Paper with arxiv_id '{body.arxiv_id}' not found",
                },
            )
        paper_id: int = paper_row[0]

        # 重複チェック
        cur.execute(
            "SELECT id FROM bookmarks WHERE user_id = %s AND paper_id = %s",
            (user.user_id, paper_id),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ALREADY_BOOKMARKED",
                    "message": f"Paper '{body.arxiv_id}' is already bookmarked",
                },
            )

        cur.execute(
            """INSERT INTO bookmarks (user_id, paper_id)
               VALUES (%s, %s)
               RETURNING id, created_at""",
            (user.user_id, paper_id),
        )
        result = cur.fetchone()
        conn.commit()

    if not result:
        raise HTTPException(status_code=500, detail="Failed to create bookmark")

    return {
        "data": {
            "bookmark_id": result[0],
            "bookmarked_at": result[1].isoformat(),
        }
    }


@router.delete("/{bookmark_id}", status_code=204)
def delete_bookmark(
    bookmark_id: int,
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    """DELETE /bookmarks/{id} — ブックマーク削除"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT user_id FROM bookmarks WHERE id = %s",
            (bookmark_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": "Bookmark not found"},
            )
        if row[0] != user.user_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FORBIDDEN",
                    "message": "You cannot delete other users' bookmarks",
                },
            )

        cur.execute("DELETE FROM bookmarks WHERE id = %s", (bookmark_id,))
        conn.commit()

    return Response(status_code=204)
