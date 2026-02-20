"""Tests for papers API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tests.conftest import FakeConnection, FakeCursor


class TestHealthEndpoint:
    """GET /health"""

    def test_returns_200(self, api_client) -> None:  # type: ignore[no-untyped-def]
        resp = api_client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestListPapers:
    """GET /papers"""

    def test_returns_empty_list(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        # fetchall → 空、fetchone (COUNT) → 0
        conn: FakeConnection = fake_conn

        class PapersCursor(FakeCursor):
            def __init__(self) -> None:
                super().__init__()
                self._call_count = 0

            def execute(self, query: str, params: Any = ()) -> None:
                self._call_count += 1
                self.last_query = query
                self.last_params = params
                if "COUNT" in query:
                    self._results = [[0]]
                else:
                    self._results = []
                self._index = 0

        conn._cursor = PapersCursor()
        resp = api_client.get("/papers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["has_next"] is False

    def test_returns_papers(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        now = datetime(2026, 2, 15, tzinfo=timezone.utc)

        class PapersCursor(FakeCursor):
            def __init__(self) -> None:
                super().__init__()
                self._call_count = 0

            def execute(self, query: str, params: Any = ()) -> None:
                self._call_count += 1
                self.last_query = query
                self.last_params = params
                if "COUNT" in query:
                    self._results = [[1]]
                else:
                    self._results = [
                        # arxiv_id, title, category_id, category_name, importance,
                        # summary_ja, one_line_takeaway, authors, published_at, id,
                        # is_bookmarked, is_viewed
                        [
                            "2402.12345",
                            "Test Paper",
                            1,
                            "基盤モデル",
                            4,
                            "テスト要約",
                            "一行まとめ",
                            ["Author A"],
                            now,
                            42,
                            False,
                            True,
                        ]
                    ]
                self._index = 0

        conn._cursor = PapersCursor()
        resp = api_client.get("/papers")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["arxiv_id"] == "2402.12345"
        assert body["data"][0]["is_viewed"] is True


class TestGetPaperDetail:
    """GET /papers/{arxiv_id}"""

    def test_not_found(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        # fetchone → None
        conn._cursor._results = []
        resp = api_client.get("/papers/9999.99999")
        assert resp.status_code == 404

    def test_returns_detail(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        now = datetime(2026, 2, 15, tzinfo=timezone.utc)
        detail_review = {
            "one_line_takeaway": "テスト",
            "sections": [],
            "perspectives": {
                "ai_engineer": "AIエンジニア視点",
                "mathematician": "数学者視点",
                "business": "ビジネス視点",
            },
            "levels": {
                "beginner": "初級",
                "intermediate": "中級",
                "expert": "上級",
            },
            "figure_analysis": [],
        }
        conn._cursor._results = [
            [
                "2402.12345",
                "Test Paper",
                "Abstract text",
                ["Author A", "Author B"],
                "https://arxiv.org/pdf/2402.12345",
                1,
                "基盤モデル",
                4,
                now,
                "テスト要約",
                detail_review,
                False,
                True,
            ]
        ]
        resp = api_client.get("/papers/2402.12345")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["arxiv_id"] == "2402.12345"
        assert body["data"]["detail"]["one_line_takeaway"] == "テスト"


class TestRecordView:
    """POST /papers/{arxiv_id}/view"""

    def test_records_new_view(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)

        class ViewCursor(FakeCursor):
            def __init__(self) -> None:
                super().__init__()
                self._call_count = 0

            def execute(self, query: str, params: Any = ()) -> None:
                self._call_count += 1
                self.last_query = query
                self.last_params = params
                if "SELECT id FROM papers" in query:
                    self._results = [[42]]
                elif "INSERT INTO paper_views" in query:
                    self._results = [[now]]
                else:
                    self._results = []
                self._index = 0

        conn._cursor = ViewCursor()
        resp = api_client.post("/papers/2402.12345/view")
        assert resp.status_code == 201


class TestGetPaperFigures:
    """GET /papers/{arxiv_id}/figures"""

    def test_returns_figures(self, api_client, fake_conn) -> None:  # type: ignore[no-untyped-def]
        conn: FakeConnection = fake_conn
        conn._cursor._results = [
            [1, 0, "https://cdn.example.com/fig_0.png", 800, 600, "Caption 1"],
            [2, 1, "https://cdn.example.com/fig_1.png", 1200, 400, None],
        ]
        resp = api_client.get("/papers/2402.12345/figures")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["figure_index"] == 0
