"""共通テストフィクスチャ"""

from dataclasses import dataclass, field

import pytest


@dataclass
class FakeLambdaContext:
    """テスト用の疑似 Lambda Context オブジェクト。

    aws-lambda-powertools の inject_lambda_context デコレータが
    必要とする属性を提供する。
    """

    function_name: str = "test-function"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:ap-northeast-1:123456789012:function:test-function"
    aws_request_id: str = "test-request-id-00000000"
    log_group_name: str = "/aws/lambda/test-function"
    log_stream_name: str = "2026/02/19/[$LATEST]test"
    identity: object = field(default=None)
    client_context: object = field(default=None)

    @staticmethod
    def get_remaining_time_in_millis() -> int:
        return 300000


@pytest.fixture
def lambda_context() -> FakeLambdaContext:
    """テスト用の Lambda Context を返すフィクスチャ。"""
    return FakeLambdaContext()
