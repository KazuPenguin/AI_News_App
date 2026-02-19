"""
AI Research OS — API Lambda Handler (placeholder)

REST API エンドポイント:
  GET    /papers, /papers/:arxiv_id, /papers/:arxiv_id/figures
  POST   /papers/:arxiv_id/view
  GET    /categories
  GET    /bookmarks
  POST   /bookmarks
  DELETE /bookmarks/:id
  GET    /users/me, /users/me/stats
  PUT    /users/me/settings
  GET    /health
"""

from typing import Any

from utils.logger import logger


@logger.inject_lambda_context(log_event=True)
def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """API Gateway からプロキシ統合で呼ばれるエントリーポイント"""
    path = event.get("path", "/")
    method = event.get("httpMethod", "GET")
    logger.info("API request received", extra={"path": path, "method": method})

    if path == "/health":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": '{"status": "ok"}',
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"data": null, "message": "Not implemented yet"}',
    }
