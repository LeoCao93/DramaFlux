"""业务服务的内存 TTL 缓存装饰器。"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


class RawHongguoService(Protocol):
    """缓存层包装的原始业务服务，不包含缓存命中元数据。"""

    async def search(
        self,
        query: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> object: ...

    async def latest(
        self,
        genre: str,
        today_only: bool,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> object: ...

    async def rank(
        self,
        board: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> object: ...

    async def detail(self, series_id: str) -> object: ...

    async def resolve_video(
        self,
        video_id: str,
        quality: str,
        fast: bool,
    ) -> object: ...


@dataclass(frozen=True)
class CachedResult(Generic[T]):
    """业务值及其是否来自缓存。"""

    value: T
    cached: bool


class CachedHongguoService:
    """为原始业务服务增加按接口区分的 TTL 缓存。"""

    def __init__(
        self,
        service: RawHongguoService,
        *,
        maxsize: int = 512,
        search_ttl: float = 300,
        latest_ttl: float = 600,
        rank_ttl: float = 600,
        detail_ttl: float = 21_600,
        video_ttl: float = 1_800,
    ) -> None:
        self.service = service
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
    ) -> CachedResult[T]:
        """读取缓存；未命中时调用 factory，并仅缓存成功结果。"""

        cache: TTLCache[tuple[object, ...], Any] = self._caches[namespace]
        async with self._lock:
            try:
                return CachedResult(value=cache[key], cached=True)
            except KeyError:
                pass
            value = await factory()
            cache[key] = value
            return CachedResult(value=value, cached=False)

    async def search(
        self,
        query: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[object]:
        return await self._get(
            "search",
            (query, page, page_size, cursor),
            lambda: self.service.search(query, page, page_size, cursor),
        )

    async def latest(
        self,
        genre: str,
        today_only: bool,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[object]:
        return await self._get(
            "latest",
            (genre, today_only, page, page_size, cursor),
            lambda: self.service.latest(
                genre,
                today_only,
                page,
                page_size,
                cursor,
            ),
        )

    async def rank(
        self,
        board: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> CachedResult[object]:
        return await self._get(
            "rank",
            (board, page, page_size, cursor),
            lambda: self.service.rank(board, page, page_size, cursor),
        )

    async def detail(self, series_id: str) -> CachedResult[object]:
        return await self._get(
            "detail",
            (series_id,),
            lambda: self.service.detail(series_id),
        )

    async def resolve_video(
        self,
        video_id: str,
        quality: str,
        fast: bool,
    ) -> CachedResult[object]:
        if not fast:
            value = await self.service.resolve_video(video_id, quality, fast)
            return CachedResult(value=value, cached=False)
        return await self._get(
            "video",
            (video_id, quality, fast),
            lambda: self.service.resolve_video(video_id, quality, fast),
        )
