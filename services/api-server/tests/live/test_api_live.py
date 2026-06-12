import os

import httpx


async def test_live_search_returns_items() -> None:
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:18000",
        timeout=60,
    ) as client:
        response = await client.get("/api/search", params={"q": "妈妈"})
        response.raise_for_status()
        assert response.json()["data"]["items"]


async def test_live_detail_and_video_resolution() -> None:
    series_id = os.environ["HONGGUO_LIVE_SERIES_ID"]
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:18000",
        timeout=60,
    ) as client:
        detail = await client.get(f"/api/books/{series_id}")
        detail.raise_for_status()
        episodes = detail.json()["data"]["episodes"]
        assert episodes
        video = await client.get(
            f"/api/videos/{episodes[0]['video_id']}",
            params={"quality": "1080p"},
        )
        assert video.status_code in {200, 422}
