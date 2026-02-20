"""Tests for bookmarks API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tests.conftest import FakeConnection, FakeCursor


class TestListBookmarks:
    """GET /bookmarks"""

    def test_returns_empty_list(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        conn._cursor._results = []
        resp = api_client.get("/bookmarks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["has_next"] is False

    def test_returns_bookmarks(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        now = datetime(2026, 2, 15, tzinfo=timezone.utc)
        conn._cursor._results = [
            # bk.id, bk.created_at, p.arxiv_id, p.title, p.category_id,
            # a.category_name, p.importance, p.summary_ja
            [42, now, "2402.12345", "Test Paper", 1, "基盤モデル", 4, "テスト要約"]
        ]
        resp = api_client.get("/bookmarks")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["bookmark_id"] == 42
        assert body["data"][0]["paper"]["arxiv_id"] == "2402.12345"


class TestAddBookmark:
    """POST /bookmarks"""

    def test_creates_bookmark(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)

        class BookmarkCursor(FakeCursor):
            def __init__(self) -> None:
                super().__init__()
                self._call_count = 0

            def execute(self, query: str, params: Any = ()) -> None:
                self._call_count += 1
                self.last_query = query
                self.last_params = params
                if "SELECT id FROM papers" in query:
                    self._results = [[42]]
                elif "SELECT id FROM bookmarks" in query:
                    self._results = []
                elif "INSERT INTO bookmarks" in query:
                    self._results = [[100, now]]
                else:
                    self._results = []
                self._index = 0

        conn._cursor = BookmarkCursor()
        resp = api_client.post("/bookmarks", json={"arxiv_id": "2402.12345"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["bookmark_id"] == 100

    def test_duplicate_returns_409(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn

        class DupCursor(FakeCursor):
            def __init__(self) -> None:
                super().__init__()
                self._call_count = 0

            def execute(self, query: str, params: Any = ()) -> None:
                self._call_count += 1
                self.last_query = query
                self.last_params = params
                if "SELECT id FROM papers" in query:
                    self._results = [[42]]
                elif "SELECT id FROM bookmarks" in query:
                    # 既にブックマーク済み
                    self._results = [[99]]
                else:
                    self._results = []
                self._index = 0

        conn._cursor = DupCursor()
        resp = api_client.post("/bookmarks", json={"arxiv_id": "2402.12345"})
        assert resp.status_code == 409

    def test_paper_not_found(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        conn._cursor._results = []
        resp = api_client.post("/bookmarks", json={"arxiv_id": "9999.99999"})
        assert resp.status_code == 404


class TestDeleteBookmark:
    """DELETE /bookmarks/{id}"""

    def test_deletes_own_bookmark(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn

        class DelCursor(FakeCursor):
            def __init__(self) -> None:
                super().__init__()
                self._call_count = 0

            def execute(self, query: str, params: Any = ()) -> None:
                self._call_count += 1
                self.last_query = query
                self.last_params = params
                if "SELECT user_id FROM bookmarks" in query:
                    self._results = [[1]]  # user_id=1 = テストユーザー
                else:
                    self._results = []
                self._index = 0

        conn._cursor = DelCursor()
        resp = api_client.delete("/bookmarks/42")
        assert resp.status_code == 204

    def test_forbidden_other_user(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn

        class ForbidCursor(FakeCursor):
            def __init__(self) -> None:
                super().__init__()

            def execute(self, query: str, params: Any = ()) -> None:
                self.last_query = query
                self.last_params = params
                if "SELECT user_id FROM bookmarks" in query:
                    self._results = [[999]]  # 別ユーザー
                else:
                    self._results = []
                self._index = 0

        conn._cursor = ForbidCursor()
        resp = api_client.delete("/bookmarks/42")
        assert resp.status_code == 403

    def test_not_found(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        conn._cursor._results = []
        resp = api_client.delete("/bookmarks/999")
        assert resp.status_code == 404
