"""ユーザーエンドポイント。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from api.dependencies import CurrentUser, DbConn, get_current_user, get_db
from api.schemas import MostViewedCategory, UpdateSettingsRequest, UserProfile, UserStats

router = APIRouter(prefix="/users")


@router.get("/me")
def get_profile(
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """GET /users/me — ユーザープロフィール"""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, email, display_name, auth_provider,
                      language, default_level, created_at
               FROM users WHERE id = %s""",
            (user.user_id,),
        )
        row = cur.fetchone()

    if not row:
        return {"data": None}

    profile = UserProfile(
        id=row[0],
        email=row[1],
        display_name=row[2],
        auth_provider=row[3],
        language=row[4] or "ja",
        default_level=row[5] or 2,
        created_at=row[6],
    )
    return {"data": profile.model_dump(mode="json")}


@router.put("/me/settings")
def update_settings(
    body: UpdateSettingsRequest,
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """PUT /users/me/settings — ユーザー設定の部分更新"""
    updates: list[str] = []
    params: list[Any] = []

    if body.display_name is not None:
        updates.append("display_name = %s")
        params.append(body.display_name)
    if body.language is not None:
        updates.append("language = %s")
        params.append(body.language)
    if body.default_level is not None:
        updates.append("default_level = %s")
        params.append(body.default_level)

    if updates:
        updates.append("updated_at = NOW()")
        set_clause = ", ".join(updates)
        params.append(user.user_id)
        with conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {set_clause} WHERE id = %s", params)
            conn.commit()

    # 更新後のプロフィールを返す
    return get_profile(conn, user)


@router.get("/me/stats")
def get_stats(
    conn: Annotated[DbConn, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """GET /users/me/stats — ユーザー統計"""
    with conn.cursor() as cur:
        # 閲覧数
        cur.execute(
            "SELECT COUNT(*) FROM paper_views WHERE user_id = %s",
            (user.user_id,),
        )
        row = cur.fetchone()
        papers_viewed = row[0] if row else 0

        # ブックマーク数
        cur.execute(
            "SELECT COUNT(*) FROM bookmarks WHERE user_id = %s",
            (user.user_id,),
        )
        row = cur.fetchone()
        bookmarks_count = row[0] if row else 0

        # 最多閲覧カテゴリ
        cur.execute(
            """SELECT p.category_id, a.category_name, COUNT(*) AS cnt
               FROM paper_views pv
               JOIN papers p ON p.id = pv.paper_id
               LEFT JOIN anchors a ON a.category_id = p.category_id
               WHERE pv.user_id = %s AND p.category_id IS NOT NULL
               GROUP BY p.category_id, a.category_name
               ORDER BY cnt DESC
               LIMIT 1""",
            (user.user_id,),
        )
        cat_row = cur.fetchone()
        most_viewed = None
        if cat_row and cat_row[0] is not None:
            most_viewed = MostViewedCategory(id=cat_row[0], name=cat_row[1] or "", count=cat_row[2])

        # 登録日
        cur.execute("SELECT created_at FROM users WHERE id = %s", (user.user_id,))
        user_row = cur.fetchone()
        member_since = user_row[0] if user_row else None

    stats = UserStats(
        papers_viewed=papers_viewed,
        bookmarks_count=bookmarks_count,
        most_viewed_category=most_viewed,
        member_since=member_since,
    )
    return {"data": stats.model_dump(mode="json")}
