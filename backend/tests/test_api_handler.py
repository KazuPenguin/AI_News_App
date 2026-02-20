"""Tests for api.handler module — ヘルスチェックの基本テスト。"""


class TestHealthEndpoint:
    """GET /health が正常にレスポンスを返すことを検証する。"""

    def test_returns_200(self, api_client) -> None:  # type: ignore[no-untyped-def]
        resp = api_client.get("/health")
        assert resp.status_code == 200

    def test_returns_ok_body(self, api_client) -> None:  # type: ignore[no-untyped-def]
        resp = api_client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
