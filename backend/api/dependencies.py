"""
AI Research OS — FastAPI 共通依存

- get_db(): DB接続を返す
- get_current_user(): Cognito claims からユーザー情報を解決
"""

from __future__ import annotations

from typing import Annotated, Any

import psycopg
from fastapi import Depends, HTTPException, Request

from utils.db import get_sync_connection
from utils.logger import logger

# ---------------------------------------------------------------------------
# 型エイリアス
# ---------------------------------------------------------------------------
DbConn = psycopg.Connection[Any]


class CurrentUser:
    """認証済みユーザー情報。"""

    def __init__(self, user_id: int, cognito_sub: str, email: str) -> None:
        self.user_id = user_id
        self.cognito_sub = cognito_sub
        self.email = email


# ---------------------------------------------------------------------------
# DB 接続
# ---------------------------------------------------------------------------
def get_db() -> DbConn:
    """同期 DB 接続を返す。"""
    return get_sync_connection()


# ---------------------------------------------------------------------------
# 認証ユーザー解決
# ---------------------------------------------------------------------------
def get_current_user(request: Request, conn: Annotated[DbConn, Depends(get_db)]) -> CurrentUser:
    """Mangum が ASGI scope の aws.event に格納した Cognito claims から
    sub と email を取得し、users テーブルで user_id を解決する。
    初回アクセス時は auto-create する。
    """
    # Mangum 経由: request.scope["aws.event"]["requestContext"]["authorizer"]["claims"]
    claims: dict[str, Any] | None = None
    aws_event = request.scope.get("aws.event")
    if isinstance(aws_event, dict):
        authorizer = aws_event.get("requestContext", {}).get("authorizer", {})
        claims = authorizer.get("claims")

    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")

    cognito_sub: str = claims.get("sub", "")
    email: str = claims.get("email", "")
    auth_provider: str = "email"
    # Cognito の identities 属性から provider を推定
    identities_str = claims.get("identities", "")
    if "google" in str(identities_str).lower():
        auth_provider = "google"
    elif "apple" in str(identities_str).lower():
        auth_provider = "apple"

    if not cognito_sub or not email:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    # users テーブルで解決 (初回は auto-create)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE cognito_sub = %s",
            (cognito_sub,),
        )
        row = cur.fetchone()
        if row:
            user_id: int = row[0]
        else:
            # 初回アクセス: ユーザー自動作成
            logger.info("Auto-creating user", extra={"cognito_sub": cognito_sub})
            cur.execute(
                """INSERT INTO users (cognito_sub, email, auth_provider)
                   VALUES (%s, %s, %s)
                   RETURNING id""",
                (cognito_sub, email, auth_provider),
            )
            result = cur.fetchone()
            if result is None:
                raise HTTPException(status_code=500, detail="Failed to create user")
            user_id = result[0]
            conn.commit()

    return CurrentUser(user_id=user_id, cognito_sub=cognito_sub, email=email)
