"""业务服务的内存 TTL 缓存装饰器。"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from cachetools import TTLCache


class HongguoService(Protocol):
    """缓存层对内层业务服务的最小能力要求。"""

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


T = TypeVar("T")


class CachedHongguoService:
    """在不修改业务客户端的前提下增加按接口区分的 TTL 缓存。

    该类与路由要求的协议保持相同，因此可以透明包装 ``HongguoClient``。
    """

    def __init__(
        self,
        service: HongguoService,
        *,
        maxsize: int = 512,
        search_ttl: float = 300,
        latest_ttl: float = 600,
        rank_ttl: float = 600,
        detail_ttl: float = 21_600,
        video_ttl: float = 1_800,
    ) -> None:
        self.service = service
        # 当前使用单个异步锁保护 cachetools 的非线程安全缓存结构，并避免并发穿透。
        self._lock = asyncio.Lock()
        self._caches = {
            "search": TTLCache(maxsize=maxsize, ttl=search_ttl),
            "latest": TTLCache(maxsize=maxsize, ttl=latest_ttl),
            "rank": TTLCache(maxsize=maxsize, ttl=rank_ttl),
            "detail": TTLCache(maxsize=maxsize, ttl=detail_ttl),
            "video": TTLCache(maxsize=maxsize, ttl=video_ttl),
        }

    async def _get(
        self,
        namespace: str,
        key: tuple[object, ...],
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        """读取缓存；未命中时调用 factory，并仅缓存成功结果。"""

        cache: TTLCache[tuple[object, ...], Any] = self._caches[namespace]
        async with self._lock:
            try:
                return cache[key]
            except KeyError:
                pass
            # factory 抛出异常时不会执行写入，因此失败响应不会被缓存。
            value = await factory()
            cache[key] = value
            return value

    async def search(self, query: str, cursor: str | None = None) -> object:
        return await self._get(
            "search",
            (query, cursor),
            lambda: self.service.search(query, cursor),
        )

    async def latest(
        self,
        genre: str,
        today_only: bool,
        cursor: str | None = None,
    ) -> object:
        return await self._get(
            "latest",
            (genre, today_only, cursor),
            lambda: self.service.latest(genre, today_only, cursor),
        )

    async def rank(self, board: str, cursor: str | None = None) -> object:
        return await self._get(
            "rank",
            (board, cursor),
            lambda: self.service.rank(board, cursor),
        )

    async def detail(self, series_id: str) -> object:
        return await self._get(
            "detail",
            (series_id,),
            lambda: self.service.detail(series_id),
        )

    async def resolve_video(self, video_id: str, quality: str) -> object:
        return await self._get(
            "video",
            (video_id, quality),
            lambda: self.service.resolve_video(video_id, quality),
        )
