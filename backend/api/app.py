"""
AI Research OS — FastAPI アプリケーション定義

全ルーターを登録し、Mangum で Lambda アダプタ化する。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mangum import Mangum
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.routers import bookmarks, categories, health, papers, users

app = FastAPI(title="AI Research OS API", version="1.0.0")

# ---------------------------------------------------------------------------
# ルーター登録
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(papers.router)
app.include_router(categories.router)
app.include_router(bookmarks.router)
app.include_router(users.router)


# ---------------------------------------------------------------------------
# 例外ハンドラ
# ---------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """HTTPException → {"error": {"code", "message"}} 形式でレスポンス。"""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        body: dict[str, Any] = {"error": detail}
    elif isinstance(detail, str):
        # JSON 文字列の場合はパース試行
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and "code" in parsed:
                body = {"error": parsed}
            else:
                body = {"error": {"code": "ERROR", "message": detail}}
        except (json.JSONDecodeError, TypeError):
            body = {"error": {"code": "ERROR", "message": detail}}
    else:
        body = {"error": {"code": "ERROR", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """バリデーションエラー → 400 INVALID_PARAMS"""
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "INVALID_PARAMS",
                "message": str(exc.errors()),
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """汎用例外 → 500 INTERNAL_ERROR"""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
            }
        },
    )


# ---------------------------------------------------------------------------
# Mangum Lambda ハンドラ
# ---------------------------------------------------------------------------
# API Gateway stage name が "v1" のため base_path を設定
handler = Mangum(app, api_gateway_base_path="/v1")
