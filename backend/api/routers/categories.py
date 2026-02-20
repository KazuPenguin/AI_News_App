"""カテゴリエンドポイント。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from api.dependencies import CurrentUser, DbConn, get_current_user, get_db
from api.schemas import Category

router = APIRouter(prefix="/categories")


@router.get("")
def list_categories(
    conn: Annotated[DbConn, Depends(get_db)],
    _user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """GET /categories — カテゴリ一覧 + 論文数"""
    sql = """
        SELECT a.category_id, a.category_name,
               COUNT(p.id) FILTER (
                   WHERE p.is_relevant = TRUE AND p.detail_review IS NOT NULL
               ) AS paper_count
        FROM anchors a
        LEFT JOIN papers p ON p.category_id = a.category_id
        WHERE a.is_active = TRUE
        GROUP BY a.category_id, a.category_name
        ORDER BY a.category_id
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    categories = [Category(id=row[0], name=row[1], paper_count=row[2]).model_dump() for row in rows]

    return {"data": categories}
