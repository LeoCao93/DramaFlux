"""API Server 的公开 HTTP 路由。

路由层只负责参数校验、调用业务服务和包装响应，不负责签名、上游请求或解析。
"""

import uuid
from typing import Any, Protocol

from fastapi import APIRouter, Query

from hongguo_api.api.schemas import ApiResponse


class HongguoService(Protocol):
    """路由层依赖的结构化业务接口。

    实现类不需要显式继承本协议，只要提供相同的方法即可。生产环境注入的是
    ``CachedHongguoService``，测试可以注入轻量 Fake，缺失会话时则注入
    ``MissingSessionService``。
    """

    async def search(self, query: str, cursor: str | None = None) -> object: ...

    async def latest(
        self,
        genre: str,
        today_only: bool,
        cursor: str | None = None,
    ) -> object: ...

    async def rank(self, board: str, cursor: str | None = None) -> object: ...

    async def detail(self, series_id: str) -> object: ...

    async def resolve_video(self, video_id: str, quality: str) -> object: ...


def build_router(service: HongguoService) -> APIRouter:
    """为指定业务实现创建路由。

    ``service`` 被各路由闭包捕获，因此实现类的选择集中在 ``bootstrap_app.py``。
    """

    router = APIRouter()

    def response(data: Any) -> ApiResponse:
        """为每次成功请求生成独立 request_id 并包装统一响应。"""

        return ApiResponse(data=data, request_id=str(uuid.uuid4()))

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"server": "ready"}

    @router.get("/api/search", response_model=ApiResponse)
    async def search(
        q: str = Query(min_length=1, max_length=100),
        cursor: str | None = Query(default=None, max_length=4096),
    ) -> ApiResponse:
        return response(await service.search(q, cursor))

    @router.get("/api/latest", response_model=ApiResponse)
    async def latest(
        genre: str = Query(default="short_play", min_length=1, max_length=50),
        today_only: bool = True,
        cursor: str | None = Query(default=None, max_length=4096),
    ) -> ApiResponse:
        return response(await service.latest(genre, today_only, cursor))

    @router.get("/api/rank", response_model=ApiResponse)
    async def rank(
        board: str = Query(default="hot", pattern="^(recommend|hot|new)$"),
        cursor: str | None = Query(default=None, max_length=4096),
    ) -> ApiResponse:
        return response(await service.rank(board, cursor))

    @router.get("/api/books/{series_id}", response_model=ApiResponse)
    async def detail(series_id: str) -> ApiResponse:
        return response(await service.detail(series_id))

    @router.get("/api/books/{series_id}/episodes", response_model=ApiResponse)
    async def episodes(series_id: str) -> ApiResponse:
        # 详情解析器返回 Pydantic 模型；Fake 实现可能返回 dict，二者均可兼容。
        detail_value = await service.detail(series_id)
        if hasattr(detail_value, "episodes"):
            episodes_value = detail_value.episodes
        elif isinstance(detail_value, dict):
            episodes_value = detail_value.get("episodes", [])
        else:
            episodes_value = []
        return response(episodes_value)

    @router.get("/api/videos/{video_id}", response_model=ApiResponse)
    async def video(
        video_id: str,
        quality: str = Query(default="1080p", pattern=r"^\d{3,4}p$"),
    ) -> ApiResponse:
        return response(await service.resolve_video(video_id, quality))

    return router
