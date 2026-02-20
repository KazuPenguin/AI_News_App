"""
AI Research OS — Secrets Manager ラッパー

AWS Secrets Manager から API キーや DB 接続情報を取得する。
コールドスタート時に1度だけ取得し、@lru_cache でキャッシュする。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

import boto3

from utils.logger import logger

# ---------------------------------------------------------------------------
# Secrets Manager クライアント (Lambda ライフサイクルで再利用)
# ---------------------------------------------------------------------------
_client: Any = None


def _get_client() -> Any:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = boto3.client("secretsmanager", region_name="ap-northeast-1")
    return _client


# ---------------------------------------------------------------------------
# 汎用取得関数
# ---------------------------------------------------------------------------
@lru_cache(maxsize=8)
def get_secret(secret_arn: str) -> dict[str, Any]:
    """Secrets Manager からシークレットを取得して JSON でパースする。

    Args:
        secret_arn: シークレットの ARN

    Returns:
        パースされた JSON オブジェクト
    """
    logger.info("Fetching secret", extra={"secret_arn": secret_arn[:60] + "..."})
    client = _get_client()
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response["SecretString"])  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# DB 接続情報
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_db_connection_params() -> dict[str, str]:
    """RDS 接続パラメータを返す。

    Returns:
        psycopg.connect() に渡せるパラメータ辞書
    """
    # パラメータが直接指定されている場合はそれを使う（ローカル開発用）
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        import urllib.parse

        parsed = urllib.parse.urlparse(db_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": str(parsed.port or 5432),
            "dbname": parsed.path.lstrip("/") or "ai_research",
            "user": parsed.username or "postgres",
            "password": parsed.password or "postgres",
        }

    secret_arn = os.environ.get("DB_SECRET_ARN", "")
    if not secret_arn:
        raise RuntimeError("DB_SECRET_ARN or DATABASE_URL 環境変数が未設定です")

    secret = get_secret(secret_arn)
    return {
        "host": secret["host"],
        "port": str(secret.get("port", 5432)),
        "dbname": secret.get("dbname", "ai_research"),
        "user": secret["username"],
        "password": secret["password"],
    }


# ---------------------------------------------------------------------------
# 外部 API キー
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_openai_api_key() -> str:
    """OpenAI API キーを返す。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        return api_key

    secret_arn = os.environ.get("OPENAI_SECRET_ARN", "")
    if not secret_arn:
        raise RuntimeError("OPENAI_SECRET_ARN or OPENAI_API_KEY 環境変数が未設定です")
    secret = get_secret(secret_arn)
    return secret["api_key"]  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def get_gemini_api_key() -> str:
    """Gemini API キーを返す。"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        return api_key

    secret_arn = os.environ.get("GEMINI_SECRET_ARN", "")
    if not secret_arn:
        raise RuntimeError("GEMINI_SECRET_ARN or GEMINI_API_KEY 環境変数が未設定です")
    secret = get_secret(secret_arn)
    return secret["api_key"]  # type: ignore[no-any-return]
