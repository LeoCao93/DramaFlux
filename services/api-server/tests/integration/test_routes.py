from fastapi.testclient import TestClient

from hongguo_api.main import create_app


class FakeHongguo:
    async def search(self, query: str, cursor: str | None = None) -> dict:
        return {"items": [{"series_id": "1", "title": query}], "next_cursor": cursor}

    async def latest(
        self,
        genre: str,
        today_only: bool,
        cursor: str | None = None,
    ) -> dict:
        return {"items": [], "genre": genre, "today_only": today_only, "cursor": cursor}

    async def rank(self, board: str, cursor: str | None = None) -> dict:
        return {"items": [], "board": board, "cursor": cursor}

    async def detail(self, series_id: str) -> dict:
        return {"series_id": series_id, "episodes": [{"video_id": "2"}]}

    async def resolve_video(self, video_id: str, quality: str) -> dict:
        return {"video_id": video_id, "requested_quality": quality}


def test_health_route_is_available() -> None:
    response = TestClient(create_app(FakeHongguo())).get("/health")
    assert response.status_code == 200
    assert response.json()["server"] == "ready"


def test_search_route_wraps_result_and_cursor() -> None:
    response = TestClient(create_app(FakeHongguo())).get(
        "/api/search",
        params={"q": "测试", "cursor": "next"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["items"][0]["title"] == "测试"
    assert payload["data"]["next_cursor"] == "next"
    assert payload["request_id"]


def test_latest_rank_detail_episode_and_video_routes() -> None:
    client = TestClient(create_app(FakeHongguo()))
    latest = client.get(
        "/api/latest",
        params={"genre": "short_play", "today_only": "true", "cursor": "c"},
    )
    rank = client.get("/api/rank", params={"board": "hot", "cursor": "r"})
    detail = client.get("/api/books/1")
    episodes = client.get("/api/books/1/episodes")
    video = client.get("/api/videos/2", params={"quality": "720p"})

    assert latest.json()["data"]["cursor"] == "c"
    assert rank.json()["data"]["cursor"] == "r"
    assert detail.json()["data"]["series_id"] == "1"
    assert episodes.json()["data"] == [{"video_id": "2"}]
    assert video.json()["data"]["requested_quality"] == "720p"


def test_search_rejects_blank_and_oversized_query() -> None:
    client = TestClient(create_app(FakeHongguo()))
    assert client.get("/api/search", params={"q": ""}).status_code == 422
    assert client.get("/api/search", params={"q": "x" * 101}).status_code == 422
