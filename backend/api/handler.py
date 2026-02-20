"""
AI Research OS — API Lambda Handler

Mangum で FastAPI を Lambda アダプタ化したハンドラを re-export する。
CDK の CMD "api.handler.main" との互換性を維持。
"""

from api.app import handler

# CDK で CMD [ "api.handler.main" ] として参照される
main = handler
