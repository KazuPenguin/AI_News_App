"""共通テストフィクスチャ"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import CurrentUser, get_current_user, get_db


# ---------------------------------------------------------------------------
# Lambda Context (バッチテスト用)
# ---------------------------------------------------------------------------
@dataclass
class FakeLambdaContext:
    """テスト用の疑似 Lambda Context オブジェクト。"""

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


# ---------------------------------------------------------------------------
# テスト用 DB コネクション (モック)
# ---------------------------------------------------------------------------
class FakeCursor:
    """テスト用の疑似カーソル。execute → fetchone/fetchall の結果をセットアップ可能。"""

    def __init__(self) -> None:
        self._results: list[list[Any]] = []
        self._index: int = 0
        self.last_query: str = ""
        self.last_params: tuple[Any, ...] | list[Any] = ()
        self._query_results: dict[str, list[Any]] = {}

    def execute(self, query: str, params: tuple[Any, ...] | list[Any] = ()) -> None:
        self.last_query = query
        self.last_params = params
        # クエリパターンに基づいて結果を返す
        if query in self._query_results:
            self._results = [self._query_results[query]]
        self._index = 0

    def fetchone(self) -> Any:
        if self._results and self._index < len(self._results):
            result = self._results[self._index]
            self._index += 1
            return result
        return None

    def fetchall(self) -> list[Any]:
        return self._results

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class FakeConnection:
    """テスト用の疑似 DB コネクション。"""

    def __init__(self) -> None:
        self._cursor = FakeCursor()
        self.committed = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    @property
    def closed(self) -> bool:
        return False


@pytest.fixture
def fake_conn() -> FakeConnection:
    """テスト用の疑似 DB コネクションを返す。"""
    return FakeConnection()


@pytest.fixture
def fake_user() -> CurrentUser:
    """テスト用の認証済みユーザー。"""
    return CurrentUser(user_id=1, cognito_sub="test-sub-123", email="test@example.com")


@pytest.fixture
def api_client(
    fake_conn: FakeConnection,
    fake_user: CurrentUser,
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient。DB と認証をオーバーライド。"""

    def _override_db() -> FakeConnection:
        return fake_conn  # type: ignore[return-value]

    def _override_user() -> CurrentUser:
        return fake_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    yield TestClient(app)
    app.dependency_overrides.clear()
