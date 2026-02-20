"""
AI Research OS — DB 接続管理

psycopg v3 を使用した同期/非同期接続管理。
Lambda 環境ではプールを使わず、1接続を再利用する。
"""

from __future__ import annotations

from typing import Any

import psycopg
import psycopg.sql

from utils.logger import logger
from utils.secrets import get_db_connection_params

# ---------------------------------------------------------------------------
# 同期接続 (L1, L2 で使用)
# ---------------------------------------------------------------------------
_sync_conn: psycopg.Connection[Any] | None = None


def get_sync_connection() -> psycopg.Connection[Any]:
    """同期 DB 接続を取得する。Lambda invocation 内で再利用。"""
    global _sync_conn  # noqa: PLW0603
    if _sync_conn is None or _sync_conn.closed:
        params = get_db_connection_params()
        logger.info("Creating sync DB connection", extra={"host": params["host"]})
        _sync_conn = psycopg.connect(
            host=params["host"],
            port=int(params["port"]),
            dbname=params["dbname"],
            user=params["user"],
            password=params["password"],
            autocommit=False,
        )
    return _sync_conn


# ---------------------------------------------------------------------------
# 非同期接続 (L3, Post-L3 で使用)
# ---------------------------------------------------------------------------
_async_conn: psycopg.AsyncConnection[Any] | None = None


async def get_async_connection() -> psycopg.AsyncConnection[Any]:
    """非同期 DB 接続を取得する。Lambda invocation 内で再利用。"""
    global _async_conn  # noqa: PLW0603
    if _async_conn is None or _async_conn.closed:
        params = get_db_connection_params()
        logger.info("Creating async DB connection", extra={"host": params["host"]})
        _async_conn = await psycopg.AsyncConnection.connect(
            host=params["host"],
            port=int(params["port"]),
            dbname=params["dbname"],
            user=params["user"],
            password=params["password"],
            autocommit=False,
        )
    return _async_conn


# ---------------------------------------------------------------------------
# クリーンアップ
# ---------------------------------------------------------------------------
async def close_connections() -> None:
    """全 DB 接続をクローズする。Lambda handler 終了時に呼ぶ。"""
    global _sync_conn, _async_conn  # noqa: PLW0603
    if _sync_conn is not None and not _sync_conn.closed:
        _sync_conn.close()
        _sync_conn = None
        logger.info("Sync DB connection closed")

    if _async_conn is not None and not _async_conn.closed:
        await _async_conn.close()
        _async_conn = None
        logger.info("Async DB connection closed")
