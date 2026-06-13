from hongguo_api.cache import CachedHongguoService, CachedResult


class CountingService:
    def __init__(self) -> None:
        self.calls = 0

    async def search(
        self,
        query: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> dict:
        self.calls += 1
        return {
            "query": query,
            "page": page,
            "page_size": page_size,
            "cursor": cursor,
            "call": self.calls,
        }

    async def latest(
        self,
        genre: str,
        today_only: bool,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> dict:
        self.calls += 1
        return {
            "genre": genre,
            "today_only": today_only,
            "page": page,
            "page_size": page_size,
            "cursor": cursor,
            "call": self.calls,
        }

    async def rank(
        self,
        board: str,
        page: int,
        page_size: int,
        cursor: str | None,
    ) -> dict:
        self.calls += 1
        return {
            "board": board,
            "page": page,
            "page_size": page_size,
            "cursor": cursor,
            "call": self.calls,
        }

    async def detail(self, series_id: str) -> dict:
        self.calls += 1
        return {"series_id": series_id, "call": self.calls}

    async def resolve_video(
        self,
        video_id: str,
        quality: str,
        fast: bool,
    ) -> dict:
        self.calls += 1
        return {
            "video_id": video_id,
            "quality": quality,
            "fast": fast,
            "call": self.calls,
        }


async def test_cache_reports_miss_then_hit() -> None:
    source = CountingService()
    cached = CachedHongguoService(source)

    first = await cached.search("测试", 1, 30, None)
    second = await cached.search("测试", 1, 30, None)

    assert first == CachedResult(value=first.value, cached=False)
    assert second == CachedResult(value=first.value, cached=True)
    assert source.calls == 1


async def test_cache_keys_include_all_public_inputs() -> None:
    source = CountingService()
    cached = CachedHongguoService(source)

    await cached.search("测试", 1, 30, None)
    await cached.search("测试", 1, 50, None)
    await cached.latest("short_play", True, 1, 30, None)
    await cached.latest("short_play", False, 1, 30, None)
    await cached.rank("hot", 1, 30, None)
    await cached.rank("new", 1, 30, None)
    await cached.resolve_video("2", "1080p", True)
    await cached.resolve_video("2", "720p", True)

    assert source.calls == 8


async def test_fast_false_bypasses_video_cache() -> None:
    source = CountingService()
    cached = CachedHongguoService(source)

    first = await cached.resolve_video("2", "1080p", False)
    second = await cached.resolve_video("2", "1080p", False)

    assert first.cached is False
    assert second.cached is False
    assert first.value != second.value
    assert source.calls == 2


async def test_all_business_methods_report_cache_hits() -> None:
    source = CountingService()
    cached = CachedHongguoService(source)

    operations = [
        lambda: cached.latest("short_play", True, 1, 30, None),
        lambda: cached.rank("hot", 1, 30, None),
        lambda: cached.detail("1"),
        lambda: cached.resolve_video("2", "1080p", True),
    ]
    for operation in operations:
        first = await operation()
        second = await operation()
        assert first.cached is False
        assert second == CachedResult(value=first.value, cached=True)

    assert source.calls == 4
