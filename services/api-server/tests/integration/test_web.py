from fastapi.testclient import TestClient

from hongguo_api.cache import CachedResult
from hongguo_api.main import create_app


class FakeHongguo:
    async def search(
        self,
        query: str,
        page: int,
        page_size: int,
        cursor: str | None = None,
    ) -> CachedResult[dict]:
        return CachedResult(
            value={
                "items": [{"title": query}],
                "page": page,
                "page_size": page_size,
                "next_cursor": cursor,
            },
            cached=False,
        )

    async def latest(
        self,
        genre: str,
        today_only: bool,
        page: int,
        page_size: int,
        cursor: str | None = None,
    ) -> CachedResult[dict]:
        del genre, today_only, page, page_size, cursor
        return CachedResult(value={"items": []}, cached=False)

    async def rank(
        self,
        board: str,
        page: int,
        page_size: int,
        cursor: str | None = None,
    ) -> CachedResult[dict]:
        del board, page, page_size, cursor
        return CachedResult(value={"items": []}, cached=False)

    async def detail(self, series_id: str) -> CachedResult[dict]:
        return CachedResult(value={"series_id": series_id, "episodes": []}, cached=False)

    async def resolve_video(
        self,
        video_id: str,
        quality: str,
        fast: bool,
    ) -> CachedResult[dict]:
        return CachedResult(
            value={"video_id": video_id, "quality": quality, "fast": fast},
            cached=False,
        )


def test_serves_known_web_routes_assets_and_framework_docs(tmp_path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    client = TestClient(create_app(FakeHongguo(), web_dist=tmp_path))

    assert client.get("/").text == "<div id='root'></div>"
    assert client.get("/docs").status_code == 200
    assert client.get("/pricing").status_code == 200
    assert client.get("/assets/app.js").text == "console.log('ok')"
    assert client.get("/internal/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/api/search", params={"q": "test"}).headers[
        "content-type"
    ].startswith("application/json")


def test_missing_web_build_does_not_break_api(tmp_path) -> None:
    client = TestClient(create_app(FakeHongguo(), web_dist=tmp_path))

    response = client.get("/")
    assert response.status_code == 503
    assert response.json()["code"] == "web_build_missing"
    assert client.get("/health").status_code == 200
