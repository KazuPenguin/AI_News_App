"""ヘルスチェックエンドポイント。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, Any]:
    """GET /health → {"status": "ok"}"""
    return {"status": "ok"}
