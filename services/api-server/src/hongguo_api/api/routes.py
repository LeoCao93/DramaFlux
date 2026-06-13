"""API Server 的公开 HTTP 路由。"""

import uuid
from typing import Annotated, Any, Literal, Protocol

from fastapi import APIRouter, Depends, Path, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from hongguo_api.api.schemas import ApiResponse
from hongguo_api.cache import CachedResult
from hongguo_api.pagination import PageRequest

Genre = Literal["short_play", "comic_series", "ai_series"]
RankBoard = Literal[
    "recommend",
    "hot",
    "new",
    "must_watch",
    "followed",
    "hot_search",
]
VideoQuality = Literal["360p", "480p", "540p", "720p", "1080p"]


class HongguoService(Protocol):
    """路由层依赖的缓存感知业务接口。"""

    async def search(
        self,
        query: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[object]: ...

    async def latest(
        self,
        genre: str,
        today_only: bool,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[object]: ...

    async def rank(
        self,
        board: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[object]: ...

    async def detail(self, series_id: str) -> CachedResult[object]: ...

    async def resolve_video(
        self,
        video_id: str,
        quality: str,
        fast: bool,
    ) -> CachedResult[object]: ...


def build_page_request(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
) -> PageRequest:
    """把查询参数转换为共享分页模型，并保持 FastAPI 的 422 语义。"""

    try:
        return PageRequest(page=page, page_size=page_size, cursor=cursor)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error


Pagination = Annotated[PageRequest, Depends(build_page_request)]
ResourceId = Annotated[str, Path(min_length=1, max_length=64)]


def build_router(service: HongguoService) -> APIRouter:
    """为指定缓存感知业务实现创建路由。"""

    router = APIRouter()

    def response(result: CachedResult[Any]) -> ApiResponse:
        return ApiResponse(
            data=result.value,
            cached=result.cached,
            request_id=str(uuid.uuid4()),
        )

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"server": "ready"}

    @router.get("/api/search", response_model=ApiResponse)
    async def search(
        pagination: Pagination,
        q: str = Query(min_length=1, max_length=100),
    ) -> ApiResponse:
        return response(
            await service.search(
                q,
                pagination.page,
                pagination.page_size,
                pagination.cursor,
            )
        )

    @router.get("/api/latest", response_model=ApiResponse)
    async def latest(
        pagination: Pagination,
        genre: Genre = "short_play",
        today_only: bool = True,
    ) -> ApiResponse:
        return response(
            await service.latest(
                genre,
                today_only,
                pagination.page,
                pagination.page_size,
                pagination.cursor,
            )
        )

    @router.get("/api/rank", response_model=ApiResponse)
    async def rank(
        pagination: Pagination,
        board: RankBoard = "hot",
    ) -> ApiResponse:
        return response(
            await service.rank(
                board,
                pagination.page,
                pagination.page_size,
                pagination.cursor,
            )
        )

    @router.get("/api/books/{series_id}", response_model=ApiResponse)
    async def detail(series_id: ResourceId) -> ApiResponse:
        return response(await service.detail(series_id))

    @router.get("/api/books/{series_id}/episodes", response_model=ApiResponse)
    async def episodes(series_id: ResourceId) -> ApiResponse:
        detail_result = await service.detail(series_id)
        detail_value = detail_result.value
        if hasattr(detail_value, "episodes"):
            episodes_value = detail_value.episodes
        elif isinstance(detail_value, dict):
            episodes_value = detail_value.get("episodes", [])
        else:
            episodes_value = []
        return response(
            CachedResult(value=episodes_value, cached=detail_result.cached)
        )

    @router.get("/api/videos/{video_id}", response_model=ApiResponse)
    async def video(
        video_id: ResourceId,
        quality: VideoQuality = "1080p",
        fast: bool = True,
    ) -> ApiResponse:
        return response(await service.resolve_video(video_id, quality, fast))

    return router
