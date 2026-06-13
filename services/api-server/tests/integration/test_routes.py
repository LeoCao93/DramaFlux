import pytest
from fastapi.testclient import TestClient

from hongguo_api.cache import CachedResult
from hongguo_api.main import create_app


class FakeHongguo:
    async def search(
        self,
        query: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[dict]:
        return CachedResult(
            value={
                "items": [{"series_id": "1", "title": query}],
                "next_cursor": cursor,
                "page": page,
                "page_size": page_size,
            },
            cached=True,
        )

    async def latest(
        self,
        genre: str,
        today_only: bool,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[dict]:
        return CachedResult(
            value={
                "items": [],
                "genre": genre,
                "today_only": today_only,
                "cursor": cursor,
                "page": page,
                "page_size": page_size,
            },
            cached=False,
        )

    async def rank(
        self,
        board: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[dict]:
        return CachedResult(
            value={
                "items": [],
                "board": board,
                "cursor": cursor,
                "page": page,
                "page_size": page_size,
            },
            cached=False,
        )

    async def detail(self, series_id: str) -> CachedResult[dict]:
        return CachedResult(
            value={
                "series_id": series_id,
                "author": "测试作者",
                "category": "都市",
                "categories": ["都市", "逆袭"],
                "duration": "20分钟",
                "publish_time": "2026-06-13 12:00:00",
                "episodes": [
                    {
                        "video_id": "2",
                        "first_pass_time": "2026-06-13 12:01:00",
                        "volume_name": "第一章",
                        "duration_seconds": 60,
                    }
                ],
            },
            cached=True,
        )

    async def resolve_video(
        self,
        video_id: str,
        quality: str,
        fast: bool,
    ) -> CachedResult[dict]:
        return CachedResult(
            value={
                "video_id": video_id,
                "vid": "model-vid",
                "vod_id": "stream-vod-id",
                "requested_quality": quality,
                "selected_quality": quality,
                "url": "https://video.test/stream?expires=1893456000",
                "backup_url": None,
                "encrypted": False,
                "expires_at": "2030-01-01T00:00:00Z",
                "fast": fast,
            },
            cached=fast,
        )


def test_health_route_is_available() -> None:
    response = TestClient(create_app(FakeHongguo())).get("/health")
    assert response.status_code == 200
    assert response.json()["server"] == "ready"


def test_search_route_forwards_page_inputs_and_reports_cache_hit() -> None:
    response = TestClient(create_app(FakeHongguo())).get(
        "/api/search",
        params={"q": "测试", "page": 2, "page_size": 50},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["items"][0]["title"] == "测试"
    assert payload["data"]["page"] == 2
    assert payload["data"]["page_size"] == 50
    assert payload["cached"] is True
    assert payload["request_id"]


def test_latest_rank_detail_episode_and_video_routes() -> None:
    client = TestClient(create_app(FakeHongguo()))
    latest = client.get(
        "/api/latest",
        params={
            "genre": "short_play",
            "today_only": "true",
            "page": 1,
            "page_size": 20,
            "cursor": "c",
        },
    )
    rank = client.get(
        "/api/rank",
        params={"board": "must_watch", "page": 1, "page_size": 10, "cursor": "r"},
    )
    detail = client.get("/api/books/1")
    episodes = client.get("/api/books/1/episodes")
    video = client.get(
        "/api/videos/2",
        params={"quality": "720p", "fast": "false"},
    )

    assert latest.json()["data"]["cursor"] == "c"
    assert latest.json()["data"]["page_size"] == 20
    assert rank.json()["data"]["board"] == "must_watch"
    assert rank.json()["data"]["page_size"] == 10
    assert detail.json()["data"]["series_id"] == "1"
    assert detail.json()["data"]["author"] == "测试作者"
    assert detail.json()["data"]["categories"] == ["都市", "逆袭"]
    assert detail.json()["data"]["duration"] == "20分钟"
    assert detail.json()["data"]["publish_time"] == "2026-06-13 12:00:00"
    assert detail.json()["cached"] is True
    assert episodes.json()["data"] == [
        {
            "video_id": "2",
            "first_pass_time": "2026-06-13 12:01:00",
            "volume_name": "第一章",
            "duration_seconds": 60,
        }
    ]
    assert episodes.json()["cached"] is True
    assert video.json()["data"]["requested_quality"] == "720p"
    assert video.json()["data"]["vid"] == "model-vid"
    assert video.json()["data"]["vod_id"] == "stream-vod-id"
    assert video.json()["data"]["expires_at"] == "2030-01-01T00:00:00Z"
    assert video.json()["data"]["fast"] is False
    assert video.json()["cached"] is False


def test_cursor_cannot_be_combined_with_later_page() -> None:
    response = TestClient(create_app(FakeHongguo())).get(
        "/api/search",
        params={"q": "测试", "cursor": "c", "page": 2},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/search", {"q": "测试", "page": 0}),
        ("/api/search", {"q": "测试", "page_size": 0}),
        ("/api/search", {"q": "测试", "page_size": 101}),
        ("/api/rank", {"board": "unknown"}),
        ("/api/videos/2", {"quality": "900p"}),
    ],
)
def test_route_rejects_unsupported_list_and_video_inputs(
    path: str,
    params: dict[str, object],
) -> None:
    assert TestClient(create_app(FakeHongguo())).get(path, params=params).status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        f"/api/books/{'1' * 65}",
        f"/api/books/{'1' * 65}/episodes",
        f"/api/videos/{'1' * 65}",
    ],
)
def test_route_rejects_oversized_ids(path: str) -> None:
    assert TestClient(create_app(FakeHongguo())).get(path).status_code == 422


def test_search_rejects_blank_and_oversized_query() -> None:
    client = TestClient(create_app(FakeHongguo()))
    assert client.get("/api/search", params={"q": ""}).status_code == 422
    assert client.get("/api/search", params={"q": "x" * 101}).status_code == 422
